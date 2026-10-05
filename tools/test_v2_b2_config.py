"""Persistent K/locator opcode tests with banked flash and injected faults."""
import hashlib
import json
import test_v2_b2 as base
from v2_b2_config import boot_pocket, checksum, decode_header, decode_locator, encode_header

firmware, boot, flash = base.firmware, base.boot, base.flash
CFG, RTS, MGR = base.CFG, base.RTS, base.MGR
send, call = base.send, base.call


def fresh():
    return base.original_boot_flash(3)


def reset(cpu):
    cpu.pc = boot.SYM['START']
    boot.hold(cpu)
    assert cpu.memory.bank == 3
    assert cpu.memory.ram[MGR['MG_READY']] == 1


def create(cpu, bank=3, sector='D', masks='00 3F 00 00'):
    out = send(cpu, f'K B{bank} {sector} {masks}\rY\r'.encode())
    assert b'Done' in out, out
    return out


def policy(mem):
    return bytes(mem.ram[RTS['RTS_POLICY']:RTS['RTS_POLICY']+4])


def check_creation_persistence_and_boot_settings():
    cpu, mem = fresh()
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 NOPOOL\r')
    assert not mem.events and policy(mem) == bytes(4)
    # Initialize local settings first; K must preserve them byte for byte.
    assert b'Done' in send(cpu, b'C 0 2 9000 20\rY\r')
    old_settings = bytes(mem.banks[3][0x7FD0:0x7FD7])
    old_core = bytes(mem.banks[3][0x7000:0x7FD0]) + bytes(mem.banks[3][0x7FE0:])
    old_module = bytes(mem.banks[3][0x6000:0x7000])
    old_others = [bytes(mem.banks[i]) for i in range(3)]
    mem.events.clear()
    create(cpu)
    header = bytes(mem.banks[3][0x5000:0x5010])
    pocket = bytes(mem.banks[3][0x7FD0:0x7FE0])
    assert header == encode_header(3, 13, (0, 0x3F, 0, 0))
    assert decode_locator(pocket) == (3, 13)
    assert pocket[:7] == old_settings
    assert old_core == bytes(mem.banks[3][0x7000:0x7FD0]) + bytes(mem.banks[3][0x7FE0:])
    assert bytes(mem.banks[3][0x6000:0x7000]) == old_module
    assert [bytes(mem.banks[i]) for i in range(3)] == old_others
    # Header completion precedes any locator mutation.
    complete = next(i for i,e in enumerate(mem.events) if e == ('program',3,0xD003,0x3F))
    assert all(e[1] == 3 and e[2] >= 0xF000 for e in mem.events[complete+1:])
    assert not any(e[0] == 'erase' and e[2] < 0xF000 for e in mem.events)
    reset(cpu)
    assert b'K 00 B3 D0 00 3F 00 00' in send(cpu, b'K\r')
    assert policy(mem) == b'\0\x3f\0\0'
    assert call(cpu, CFG['CF_LOCATE']) == (True, 3, 0xD0, 1)
    # Ordinary C edits retain the extended locator and checksum it again.
    assert b'Done' in send(cpu, b'C 0 1 2000 10\rY\r')
    assert decode_locator(mem.banks[3][0x7FD0:0x7FE0]) == (3, 13)
    reset(cpu)
    assert b'K 00 B3 D0' in send(cpu, b'K\r')


def check_move_reserved_sector_and_opaque_bank():
    cpu, mem = fresh()
    create(cpu)
    old_sector = bytes(mem.banks[3][0x5000:0x6000])
    # Explicit Bank 2 selection is permitted, but its config sector is excluded
    # even when the requested storage mask includes every lower sector.
    create(cpu, 2, 'A', '00 00 3F 00')
    assert decode_locator(mem.banks[3][0x7FD0:0x7FE0]) == (2, 10)
    assert decode_header(mem.banks[2][0x2000:0x2010], 2, 10) == b'\0\0\x3b\0'
    assert policy(mem) == b'\0\0\x3b\0'
    assert bytes(mem.banks[3][0x5000:0x6000]) == old_sector
    assert call(cpu, CFG['CF_LOCATE']) == (True, 2, 0xA0, 1)
    # Fill permitted sectors 8/9: allocation must skip config A and use B.
    mem.banks[2][:0x2000] = bytes(0x2000)
    before_config = bytes(mem.banks[2][0x2000:0x3000])
    mem.ram[0x2000] = 0xA5
    assert b'Done' in send(cpu, b'S 2000 2000 RESERVED\r')
    assert mem.banks[2][0x3000:0x3002] == b'SR'
    assert bytes(mem.banks[2][0x2000:0x3000]) == before_config
    # No signature search: another plausible sector never rescues a bad locator.
    mem.banks[3][0x5000:0x5010] = encode_header(3, 13, (0, 0x3F, 0, 0))
    mem.banks[2][0x200E] ^= 1
    before = [bytes(bank) for bank in mem.banks]
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 FAILCLOSED\r')
    assert policy(mem) == bytes(4)
    assert [bytes(bank) for bank in mem.banks] == before


def check_invalid_configuration_and_recovery():
    for offset in (0, 1, 2, 3, 4, 8, 9, 14, 15):
        cpu, mem = fresh()
        base.install_policy(mem)
        assert call(cpu, base.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
        mem.banks[3][0x5000+offset] ^= 0x40
        # Tested after initialization: cached policy must be withdrawn too.
        assert call(cpu, CFG['CF_LOCATE'])[:2] == (False, 2), offset
        assert policy(mem) == bytes(4)
        assert not mem.events
        reset(cpu)
        assert b'B3>' in mem.tx
        assert b'RTS error 07' in send(cpu, b'S 2000 2000 BAD\r')
    for index, value in ((7, 0xC2), (8, 4), (9, 0xE0), (9, 0xA1)):
        cpu, mem = fresh()
        base.install_policy(mem)
        pocket = bytearray(mem.banks[3][0x7FD0:0x7FE0])
        pocket[index] = value
        pocket[14:] = checksum(pocket[:14])
        mem.banks[3][0x7FD0:0x7FE0] = pocket
        assert call(cpu, base.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
        assert call(cpu, CFG['CF_LOCATE'])[:2] == (False, 1)
        assert policy(mem) == bytes(4) and not mem.events
    cpu, mem = fresh()
    base.install_policy(mem)
    mem.banks[3][0x7FDF] ^= 1
    reset(cpu)
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 BADBOOT\r')
    assert policy(mem) == bytes(4)
    # Repair is possible by selecting an erased destination, preserving the
    # corrupt old sector as evidence instead of erasing it automatically.
    old = bytes(mem.banks[3][0x5000:0x6000])
    create(cpu, 1, 'D', '00 3F 00 00')
    assert bytes(mem.banks[3][0x5000:0x6000]) == old
    assert policy(mem) == b'\0\x1f\0\0'


def check_refusal_cancel_and_off():
    cpu, mem = fresh()
    before = [bytes(bank) for bank in mem.banks]
    for command in (b'K B4 D 00 00 00 00\r', b'K B3 E 00 00 00 00\r',
                    b'K B3 F 00 00 00 00\r', b'K B3 7 00 00 00 00\r',
                    b'K B3 D 40 00 00 00\r', b'K B3 D 00 00 00\r',
                    b'K OFF MORE\r', b'K B3 D 00 00 00 00 EXTRA\r'):
        assert b'Bad config' in send(cpu, command), command
        assert [bytes(bank) for bank in mem.banks] == before
        assert not mem.events
    assert b'Canceled' in send(cpu, b'K B3 D 00 3F 00 00\rN\r')
    assert [bytes(bank) for bank in mem.banks] == before and not mem.events
    # An erased header is insufficient if opaque data exists elsewhere.
    mem.banks[2][0x2FFF] = 0x12
    before = [bytes(bank) for bank in mem.banks]
    assert b'Config sector occupied' in send(cpu, b'K B2 A 00 00 01 00\r')
    assert [bytes(bank) for bank in mem.banks] == before and not mem.events
    create(cpu)
    sector = bytes(mem.banks[3][0x5000:0x6000])
    assert b'Done' in send(cpu, b'K OFF\rY\r')
    assert decode_locator(mem.banks[3][0x7FD0:0x7FE0]) is None
    assert policy(mem) == bytes(4)
    assert bytes(mem.banks[3][0x5000:0x6000]) == sector
    reset(cpu)
    assert b'K 00\r\n' in send(cpu, b'K\r')
    assert call(cpu, CFG['CF_LOCATE'])[:2] == (False, 0)
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 OFF\r')


def check_same_sector_update_and_direct_service():
    cpu, mem = fresh()
    create(cpu)
    # Reserved tail survives a header update that requires erasing its sector.
    mem.banks[3][0x5010:0x5018] = b'FUTURE!!'
    mem.events.clear()
    create(cpu, masks='00 01 00 00')
    assert bytes(mem.banks[3][0x5010:0x5018]) == b'FUTURE!!'
    assert any(e[0] == 'erase' and e[2] == 0xD000 for e in mem.events)
    assert policy(mem) == b'\0\1\0\0'
    assert mem.ram[0x7100:0x7102] == b'EM'
    # A corrupted sector also disables direct RTS.SAVE clients, not only CLI.
    mem.banks[3][0x500E] ^= 1
    mem.ram[0x2100:0x2117] = bytes((1,0,0x80,0,0x20,0,0x20)) + b'API' + bytes(13)
    before = [bytes(bank) for bank in mem.banks]
    assert call(cpu, RTS['SR_API_SAVE'], 0, 0x21)[:2] == (False, 1)
    assert [bytes(bank) for bank in mem.banks] == before
    assert policy(mem) == bytes(4)


def check_destination_faults_keep_old_locator():
    for fault in ('timeout', 'verify'):
        cpu, mem = fresh()
        create(cpu)
        pocket = bytes(mem.banks[3][0x7FD0:0x7FE0])
        old_sector = bytes(mem.banks[3][0x5000:0x6000])
        mem.events.clear()
        mem.fault = fault
        out = send(cpu, b'K B1 D 00 01 00 00\rY\r')
        assert b'Config flash fail' in out and b'Done' not in out, out
        assert bytes(mem.banks[3][0x7FD0:0x7FE0]) == pocket
        assert bytes(mem.banks[3][0x5000:0x6000]) == old_sector
        assert mem.banks[1][0x5003] != 0x3F
        assert mem.bank == 3 and not mem.busy
        assert policy(mem) == b'\0\x3f\0\0'
    # Loss after a completed new header but before locator update leaves the
    # old selected sector authoritative; the orphan is not searched for.
    cpu, mem = fresh()
    create(cpu)
    mem.banks[1][0x5000:0x5010] = encode_header(1, 13, (0,1,0,0))
    reset(cpu)
    assert b'K 00 B3 D0' in send(cpu, b'K\r')


def check_locator_failure_stays_in_ram_and_retries():
    for fault in ('timeout', 'verify'):
        cpu, mem = fresh()
        create(cpu)
        before_core = bytes(mem.banks[3][0x7000:0x7FD0])
        before_vectors = bytes(mem.banks[3][0x7FE0:])
        original_mutated = mem.mutated

        def fault_at_locator(kind, address, value):
            if mem.bank == 3 and address >= 0xF000:
                mem.fault = fault
            original_mutated(kind, address, value)

        mem.mutated = fault_at_locator
        mem.rx.extend(b'K B1 D 00 01 00 00\rY\r')
        boot.run(cpu, lambda: cpu.pc == flash.W['V2W_RESET_WAIT'], limit=8_000_000)
        assert b'Flash fail; Y retry/reset' in mem.tx
        assert cpu.pc < 0x8000 and mem.ram[boot.SYM['V2_NMI_HOLD']] == 1
        desired = bytes(mem.ram[0x6100:0x7100])
        assert desired[:0xFD0] == before_core and desired[0xFE0:] == before_vectors
        assert decode_locator(desired[0xFD0:0xFE0]) == (1, 13)
        assert decode_header(mem.banks[1][0x5000:0x5010], 1, 13) == b'\0\1\0\0'
        mem.rx.extend(b'N')
        for _ in range(1000):
            cpu.step()
            assert cpu.pc < 0x8000
        mem.mutated = original_mutated
        mem.fault = None
        mem.rx.extend(b'Y')
        boot.run(cpu, lambda: boot.waiting(cpu), limit=8_000_000)
        assert bytes(mem.banks[3][0x7000:]) == desired
        assert mem.ram[boot.SYM['V2_NMI_HOLD']] == 0
        assert policy(mem) == b'\0\1\0\0'
        reset(cpu)
        assert b'K 00 B1 D0 00 01 00 00' in send(cpu, b'K\r')


def check_active_sector_fault_and_marker_failure():
    cpu, mem = fresh()
    create(cpu)
    pocket = bytes(mem.banks[3][0x7FD0:0x7FE0])
    core = bytes(mem.banks[3][0x7000:])
    mem.fault = 'timeout'
    out = send(cpu, b'K B3 D 00 01 00 00\rY\r')
    assert b'Config flash fail' in out and b'Done' not in out, out
    assert bytes(mem.banks[3][0x7000:]) == core
    assert bytes(mem.banks[3][0x7FD0:0x7FE0]) == pocket
    assert policy(mem) == bytes(4)
    assert call(cpu, CFG['CF_LOCATE'])[:2] == (False, 2)
    mem.fault = None
    reset(cpu)
    assert b'K 02' in send(cpu, b'K\r')
    assert b'RTS error 07' in send(cpu, b'S 2000 2000 BAD\r')
    # A marker write can physically succeed but fail its busy/readback check.
    # The locator must still remain on the previous verified selection.
    cpu, mem = fresh()
    create(cpu)
    pocket = bytes(mem.banks[3][0x7FD0:0x7FE0])
    original_mutated = mem.mutated

    def fail_commit(kind, address, value):
        if mem.bank == 1 and address == 0xD003 and value == 0x3F:
            mem.fault = 'timeout'
        original_mutated(kind, address, value)

    mem.mutated = fail_commit
    out = send(cpu, b'K B1 D 00 01 00 00\rY\r')
    assert b'Config flash fail' in out and b'Done' not in out, out
    assert bytes(mem.banks[3][0x7FD0:0x7FE0]) == pocket
    assert policy(mem) == b'\0\x3f\0\0'


def main():
    checks = [check_creation_persistence_and_boot_settings,
              check_move_reserved_sector_and_opaque_bank,
              check_invalid_configuration_and_recovery,
              check_refusal_cancel_and_off,
              check_same_sector_update_and_direct_service,
              check_destination_faults_keep_old_locator,
              check_locator_failure_stays_in_ram_and_retries,
              check_active_sector_fault_and_marker_failure]
    passed = []
    for check in checks:
        check()
        passed.append(check.__name__)
        print('PASS:', check.__name__, flush=True)
    (firmware.OUT / 'extended-config-tests.json').write_text(json.dumps({
        'version': firmware.VERSION, 'passed': passed,
        'image_sha256': hashlib.sha256(boot.IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
