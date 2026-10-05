"""Execute basic manager/RTS opcodes in the banked 65C02 host model."""
import hashlib
import json
import sys
import build_v2_b2 as firmware
import v2_b2_config as config

sys.modules['build_v2'] = firmware
sys.modules['build_v2_a23'] = firmware
import test_v2_a23_sr as harness
boot, flash = harness.boot, harness.flash
REPORT = json.loads((firmware.OUT / 'build.json').read_text())
MGR, RTS = REPORT['manager'], REPORT['rts']
CFG = REPORT['extended_config']
_base_boot_flash = flash.boot_flash
# Reset now validates optional flash before the prompt; allow its CRC loops.
def manager_hold(cpu):
    boot.run(cpu, lambda: boot.waiting(cpu), limit=5_000_000)
boot.hold = manager_hold
flash.hold = manager_hold


def original_boot_flash(bank=0, ft245_present=True):
    mem = flash.FlashMemory(bank, ft245_present=ft245_present)
    if bank == 3:
        mem.banks[3][0x3000:0x4000] = (firmware.OUT / f'{firmware.STEM}-b000-bfff.bin').read_bytes()
    cpu = flash.MPU(memory=mem, pc=boot.SYM['START'])
    mem.cpu = cpu
    boot.run(cpu, lambda: boot.waiting(cpu), limit=5_000_000)
    return cpu, mem


def install_policy(mem, masks=(0, 0x3F, 0, 0), bank=3, sector=13):
    offset = (sector - 8) * 0x1000
    mem.banks[bank][offset:offset+16] = config.encode_header(bank, sector, masks)
    mem.banks[3][0x7FD0:0x7FE0] = config.boot_pocket(
        mem.banks[3][0x7FD0:0x7FE0], bank=bank, sector=sector)


def configured_boot_flash(bank=0, ft245_present=True):
    cpu, mem = original_boot_flash(bank, ft245_present)
    if bank == 3:
        install_policy(mem)
    return cpu, mem


flash.boot_flash = configured_boot_flash


def send(cpu, line):
    return flash.send(cpu, line, limit=25_000_000)


def check_named_roundtrip():
    cpu, mem = flash.boot_flash(3)
    assert b'STR8-N 2.0b2' in mem.tx
    assert mem.ram[MGR['MG_READY']] == 1
    source = bytes(range(32))
    mem.ram[0x2000:0x2020] = source
    untouched = [bytes(bank) for bank in mem.banks]
    out = send(cpu, b'S 2000 201F DEMO\r')
    assert b'Done' in out, out
    assert mem.bank == 3 and mem.ram[MGR['MG_READY']] == 1
    assert mem.ram[MGR['MG_COUNT']] == 12
    assert mem.banks[1][:4] == b'SR\x01\x3f'
    assert mem.banks[1][8:24] == b'DEMO' + bytes(12)
    assert mem.banks[1][24:56] == source
    assert all(bytes(mem.banks[b]) == untouched[b] for b in (0, 2, 3))
    assert not any(e[0] == 'erase' for e in mem.events)
    out = send(cpu, b'T\r')
    assert b'B1 8000 2000-201F 0020 C DEMO' in out, out
    mem.ram[0x2000:0x2020] = bytes(32)
    out = send(cpu, b'R DEMO\r')
    assert b'Done' in out and mem.ram[0x2000:0x2020] == source, out
    before = [bytes(bank) for bank in mem.banks]
    out = send(cpu, b'S 2000 201F DEMO\r')
    assert b'RTS error 02' in out, out
    assert [bytes(bank) for bank in mem.banks] == before
    assert b'RTS error 06' in send(cpu, b'R MISSING\r')
    assert b'Bad cmd' in send(cpu, b'THING\r')
    assert b'Bad hex/name' in send(cpu, b'S 2000 201F\r')
    assert b'Done' in send(cpu, b'R DEMO B1\r')
    assert b'RTS error 06' in send(cpu, b'R DEMO B2\r')
    assert b'RTS error 07' in send(cpu, b'S 2000 201F OTHER B2\r')
    assert mem.bank == 3


def call(cpu, entry, a=0, x=0, y=0):
    cpu.sp = 0xFF
    cpu.stPushWord(0x01FF)
    cpu.a, cpu.x, cpu.y = a, x, y
    cpu.pc = entry
    boot.run(cpu, lambda: cpu.pc == 0x0200, limit=5_000_000)
    assert cpu.sp == 0xFF
    return bool(cpu.p & cpu.CARRY), cpu.a, cpu.x, cpu.y


def lookup(cpu, name, version=1):
    cpu.memory.ram[0x2100:0x2100+len(name)+1] = name.encode('ascii') + b'\0'
    return call(cpu, MGR['MG_LOOKUP_ENTRY'], 0, 0x21, version)


def ready():
    cpu, mem = flash.boot_flash(3)
    assert call(cpu, REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
    cpu.pc = boot.SYM['V2_PROMPT']
    boot.hold(cpu)
    return cpu, mem


def check_lookup_registration():
    cpu, mem = ready()
    ok, low, high, flags = lookup(cpu, 'CONSOLE.PUTC')
    assert ok and low + 256*high == boot.VSYM['STR8V2_RAM_PUTC'] and flags == 1
    assert lookup(cpu, 'CONSOLE.PUTC', 2)[:2] == (False, 2)
    assert lookup(cpu, 'NO.SUCH.SERVICE')[:2] == (False, 1)
    ok, low, high, flags = lookup(cpu, 'STORAGE.POLICY')
    assert ok and low+256*high == RTS['RTS_POLICY'] and flags == 0
    assert mem.ram[RTS['RTS_POLICY']:RTS['RTS_POLICY']+4] == b'\0\x3f\0\0'
    ok, low, high, flags = lookup(cpu, 'COMMAND.REGISTER')
    assert ok and flags == 1
    register = low+256*high
    assert call(cpu, register, ord('S'), 0, 0x58)[:2] == (False, 2)
    assert call(cpu, register, ord('X'), 0, 0x20)[:2] == (False, 1)
    # Independently registered X returns handled; no manager rebuild required.
    mem.ram[0x5800:0x5803] = b'\xa9\x01\x60'
    assert call(cpu, register, ord('X'), 0, 0x58)[:2] == (True, 0)
    cpu.pc = boot.SYM['V2_PROMPT']
    boot.hold(cpu)
    out = send(cpu, b'X\r')
    assert b'Bad cmd' not in out and b'RTS unavailable' not in out, out
    assert mem.ram[MGR['MG_COUNT']] == 15
    for key in b'ABC':
        assert call(cpu, register, key, 0, 0x58)[:2] == (True, 0)
    assert call(cpu, register, ord('Y'), 0, 0x58)[:2] == (False, 3)
    assert mem.ram[MGR['MG_COUNT']] == 24


def check_core_catalog_and_recovery_dispatch():
    cpu, mem = ready()
    count_before = mem.ram[MGR['MG_COUNT']]
    ok, low, high, flags = lookup(cpu, 'COMMAND.CORE')
    assert ok and flags == 0
    descriptor = low+256*high
    assert descriptor == REPORT['core_commands']['descriptor']
    fmt, count = mem.ram[descriptor:descriptor+2]
    keys = int.from_bytes(mem.ram[descriptor+2:descriptor+4], 'little')
    targets = int.from_bytes(mem.ram[descriptor+4:descriptor+6], 'little')
    assert (fmt, count) == (1, 10)
    assert bytes(mem[keys+i] for i in range(count)) == b'BDMGLFICJ?'
    handlers = ('V2_COMMAND_B', 'V2_COMMAND_D', 'V2_COMMAND_M', 'V2_COMMAND_G',
                'V2_COMMAND_L', 'V2_COMMAND_F', 'V2_COMMAND_I', 'V2_COMMAND_C',
                'V2_COMMAND_J', 'V2_SHOW_HELP')
    for index, name in enumerate(handlers):
        pointer = mem[targets+2*index]+256*mem[targets+2*index+1]
        assert pointer == boot.SYM[name]
    assert mem.ram[MGR['MG_COUNT']] == count_before == 12
    assert lookup(cpu, 'COMMAND.CORE', 2)[:2] == (False, 2)
    # Metadata is not a callable provider; F targets remain inadmissible.
    ok, low, high, _ = lookup(cpu, 'COMMAND.REGISTER')
    assert ok
    assert call(cpu, low+256*high, ord('X'),
                boot.SYM['V2_COMMAND_D'] & 255, boot.SYM['V2_COMMAND_D'] >> 8)[:2] == (False, 1)
    # Registered names cannot override the independent recovery dispatcher.
    mem.ram[0x2200] = 0
    mem.ram[0x5800:0x5808] = b'\xa9\xa5\x8d\x00\x22\xa9\x01\x60'
    assert call(cpu, low+256*high, ord('B'), 0, 0x58)[:2] == (True, 0)
    cpu.pc = boot.SYM['V2_PROMPT']
    boot.hold(cpu)
    assert b'Bad cmd' not in send(cpu, b'B2\r')
    assert mem.ram[0x2200] == 0 and mem.ram[boot.SYM['V2_SELECTED']] == 2
    # Missing manager/config still permits core memory edit, load/run and help.
    for bank in (0, 3):
        cpu, mem = original_boot_flash(bank)
        mem.banks[bank][0x6000:0x7000] = b'\xff'*4096
        before = [bytes(data) for data in mem.banks]
        assert b'B0-3 D addr [end]' in send(cpu, b'?\r')
        assert b'Bad ' not in send(cpu, b'M 2000 A5\r')
        assert b'2000: A5' in send(cpu, b'D 2000 2000\r')
        stub = b'\xa9\x5a\x20\x6d\x7e\x4c\x67\x7e'
        stream = (firmware.record('1', 0x2000, stub)+'\r\n'+
                  firmware.record('9', 0x2000)+'\r\n').encode()
        assert b'Entry 2000' in send(cpu, b'L\r'+stream)
        assert b'Z' in send(cpu, b'G 2000\r')
        assert b'RTS unavailable' in send(cpu, b'T\r')
        assert mem.ram[MGR['MG_COUNT']] == 0
        assert [bytes(data) for data in mem.banks] == before and not mem.events
    assert REPORT['resident_bytes'] == 4039
    assert REPORT['free_before_config'] == 9


def check_placement_policy():
    cpu, mem = ready()
    policy = RTS['RTS_POLICY']
    install_policy(mem, (0, 1, 0, 0))
    # A valid record owns its erased payload, too.
    mem.ram[0x2000:0x2040] = b'\xff'*64
    assert b'Done' in send(cpu, b'S 2000 203F ERASED\r')
    first = bytes(mem.banks[1][:88])
    mem.ram[0x2000:0x2020] = bytes(range(32))
    assert b'Done' in send(cpu, b'S 2000 201F NEXT\r')
    assert bytes(mem.banks[1][:88]) == first
    assert mem.banks[1][88:90] == b'SR'
    # Fragmented free space cannot cross excluded sector 9.
    cpu, mem = ready()
    install_policy(mem, (0, 5, 0, 0))
    mem.banks[1][:0xFF0] = bytes(0xFF0)
    mem.ram[0x2000:0x2020] = bytes(range(32))
    excluded = bytes(mem.banks[1][0x1000:0x2000])
    assert b'Done' in send(cpu, b'S 2000 201F GAP\r')
    assert mem.banks[1][0x2000:0x2002] == b'SR'
    assert bytes(mem.banks[1][0x1000:0x2000]) == excluded
    # A contiguous permitted pair permits one record crossing its boundary.
    cpu, mem = ready()
    install_policy(mem, (0, 3, 0, 0))
    mem.banks[1][:0xFF0] = bytes(0xFF0)
    mem.ram[0x2000:0x2020] = bytes(range(32))
    assert b'Done' in send(cpu, b'S 2000 201F CROSS\r')
    assert mem.banks[1][0xFF0:0xFF2] == b'SR'
    assert mem.banks[1][0x1008:0x1028] == bytes(range(32))
    assert mem.ram[0x7100:0x7102] == b'EM'
    assert not any(e[0] == 'erase' for e in mem.events)


def check_ambiguity_pending_and_bounds():
    cpu, mem = ready()
    policy = RTS['RTS_POLICY']
    install_policy(mem, (0, 1, 1, 0))
    mem.ram[0x2000:0x2020] = bytes(range(32))
    assert b'Done' in send(cpu, b'S 2000 201F NAME B1\r')
    assert b'Done' in send(cpu, b'S 2000 201F NAME B2\r')
    mem.ram[0x2000:0x2020] = bytes(32)
    assert b'RTS error 05' in send(cpu, b'R NAME\r')
    assert mem.ram[0x2000:0x2020] == bytes(32)
    assert b'Done' in send(cpu, b'R NAME B2\r')
    mem.banks[2][3] = 0x7F
    assert b'RTS error 04' in send(cpu, b'R NAME B2\r')
    assert b'RTS error 02' in send(cpu, b'S 2000 201F NAME B2\r')
    snapshot = [bytes(b) for b in mem.banks]
    for command in (b'S 57FF 5800 BAD\r', b'S 5800 5800 BAD\r',
                    b'S 01FF 0200 BAD\r', b'S 2001 2000 BAD\r',
                    b'S 2000 2000 SEVENTEENCHARLABEL\r', b'R NAME B4\r'):
        assert b'Bad hex/name' in send(cpu, command), command
        assert [bytes(b) for b in mem.banks] == snapshot


def check_missing_corrupt_and_lifetime():
    for offset in (0, 1, 2):
        cpu, mem = flash.boot_flash(3)
        mem.banks[3][0x6000+offset] ^= 0x40
        assert b'RTS unavailable' in send(cpu, b'T\r')
        assert mem.ram[MGR['MG_READY']] == 0 and not mem.events
    cpu, mem = flash.boot_flash(3)
    mem.banks[3][REPORT['manager_rom']['MG_IMAGE']-0x8000+30] ^= 1
    cpu.pc = boot.SYM['START']
    boot.hold(cpu)
    assert b'RTS unavailable' in send(cpu, b'T\r')
    assert mem.ram[MGR['MG_COUNT']] == 0 and not mem.events
    cpu, mem = ready()
    # Mutable boot configuration does not invalidate private-core bindings.
    mem.banks[3][0x7FD5] ^= 1
    assert call(cpu, REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
    # A changed core does; stale registrations are withdrawn.
    mem.banks[3][0x7F90] ^= 1
    assert not call(cpu, REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
    assert mem.ram[MGR['MG_COUNT']] == 0 and mem.ram[MGR['MG_READY']] == 0
    cpu, mem = ready()
    cpu.pc = boot.SYM['START']
    boot.hold(cpu)
    assert mem.ram[MGR['MG_READY']] == 1 and mem.ram[MGR['MG_COUNT']] == 12
    assert mem.bank == 3


def check_application_limit_and_staging():
    cpu, mem = flash.boot_flash(3)
    assert b'B3>' in send(cpu, b'M 57FF 42\r') and mem.ram[0x57FF] == 0x42
    for address in (0x5800, 0x6000, 0x6100, 0x70FF, 0x7100, 0x7500, 0x78FF):
        old = mem.ram[address]
        assert b'Protected' in send(cpu, f'M {address:04X} 00\r'.encode())
        assert mem.ram[address] == old
    for address, payload in ((0x57FF, b'A'), (0x57FF, b'AB'), (0x5800, b'A')):
        old = bytes(mem.ram[0x5800:0x7900])
        stream = b'L\r' + (firmware.record('1', address, payload)+'\r\n').encode()
        stream += (firmware.record('9', 0x2000)+'\r\n').encode()
        out = send(cpu, stream)
        if len(payload) == 1 and address == 0x57FF:
            assert b'Entry' in out and mem.ram[0x57FF] == ord('A'), out
        else:
            assert b'Protected' in out, out
            assert bytes(mem.ram[0x5800:0x7900]) == old
    # C's F-sector write uses 6100-70FF and leaves manager/overlay RAM alone.
    before_overlay = bytes(mem.ram[0x5800:0x6000])
    before_manager = bytes(mem.ram[0x7100:0x7900])
    out = send(cpu, b'C 0 1 2000 10\rY\r')
    assert b'Done' in out, out
    assert bytes(mem.ram[0x5800:0x6000]) == before_overlay
    assert bytes(mem.ram[0x7100:0x7900]) == before_manager


def check_faults_cancel_and_low_level_policy():
    for fault in ('timeout', 'verify'):
        cpu, mem = ready()
        install_policy(mem, (0, 1, 0, 0))
        mem.ram[0x2000:0x2020] = bytes(range(32))
        before = [bytes(b) for b in mem.banks]
        mem.fault = fault
        out = send(cpu, b'S 2000 201F FAULT\r')
        assert b'RTS error 03' in out and b'Done' not in out, out
        assert mem.bank == 3 and not mem.busy
        assert mem.banks[1][3] != 0x3F
        assert all(bytes(mem.banks[b]) == before[b] for b in (0, 2, 3))
        assert not any(e[0] == 'erase' for e in mem.events)
    cpu, mem = ready()
    assert b'Canceled' in send(cpu, b'T\r\x03')
    assert mem.bank == 3 and mem.ram[boot.SYM['V2_CANCEL_REQUEST']] == 0
    # No automatic erase when the sole permitted sector is full.
    install_policy(mem, (0, 1, 0, 0))
    mem.banks[1][:0x1000] = bytes(0x1000)
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 FULL\r')
    assert not mem.events
    # Discovered low-level APIs enforce policy too, and save commits last.
    cpu, mem = ready()
    install_policy(mem, (0, 1, 0, 0))
    assert call(cpu, CFG['CF_LOCATE'])[0]
    mem.ram[0x2000] = 0xA5
    request = bytes((2, 0, 0x80, 0, 0x20, 0, 0x20)) + b'API' + bytes(13)
    mem.ram[0x2100:0x2117] = request
    assert call(cpu, RTS['SR_API_SAVE'], 0, 0x21)[:2] == (False, 1)
    assert call(cpu, RTS['SR_API_RESTORE'], 0, 0x21)[:2] == (False, 4)
    assert not mem.events
    mem.ram[0x2100] = 1
    assert call(cpu, RTS['SR_API_SAVE'], 0, 0x21)[:2] == (True, 0)
    assert mem.banks[1][:4] == b'SR\x01\x3f'
    assert mem.events[-1][0] == 'program' and mem.events[-1][2:] == (0x8003, 0x3F)
    mem.ram[0x2000] = 0
    assert call(cpu, RTS['SR_API_RESTORE'], 0, 0x21)[:2] == (True, 0)
    assert mem.ram[0x2000] == 0xA5


def check_established_public_abi():
    boot.check_handoffs()
    boot.check_vectors()
    boot.check_capability_abi()
    boot.check_ram_abi_all_banks(acia_enabled=False)


def main():
    checks = [check_named_roundtrip, check_lookup_registration,
              check_core_catalog_and_recovery_dispatch,
              check_placement_policy, check_ambiguity_pending_and_bounds,
              check_missing_corrupt_and_lifetime, check_application_limit_and_staging,
              check_faults_cancel_and_low_level_policy, check_established_public_abi]
    passed = []
    for check in checks:
        check()
        passed.append(check.__name__)
        print('PASS:', check.__name__, flush=True)
    (firmware.OUT / 'manager-rts-tests.json').write_text(json.dumps({
        'version': firmware.VERSION, 'passed': passed,
        'image_sha256': hashlib.sha256(boot.IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
