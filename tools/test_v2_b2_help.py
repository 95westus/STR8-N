"""Execute the independently loaded H module against the unchanged b2 core."""
import hashlib
import json
import build_v2_b2_help as module
import test_v2_b2 as host

boot, MGR = host.boot, host.MGR
META = json.loads((module.OUT / 'manifest.json').read_text())
S19 = module.OUT / (module.NAME + '.s19')
IMAGE, ENTRY = module.assembler.read_s19(S19)
PINNED = (module.OUT / 'help-overlay.bin').read_bytes()


def install(cpu):
    for address, byte in IMAGE.items():
        cpu.memory.ram[address] = byte
    return host.send(cpu, b'G 2000\r')


def register(cpu, key, address=0x7100):
    ok, low, high, flags = host.lookup(cpu, 'COMMAND.REGISTER')
    assert ok and flags == 1
    result = host.call(cpu, low + high*256, ord(key), address & 255, address >> 8)
    cpu.pc = boot.SYM['V2_PROMPT']
    boot.hold(cpu)
    return result


def check_independent_help_and_lifetime():
    cpu, mem = host.original_boot_flash(3)
    before = [bytes(bank) for bank in mem.banks]
    question = host.send(cpu, b'?\r')
    assert b'B0-3 D addr [end]' in question and b'Registered:' not in question
    assert mem.ram[MGR['MG_READY']] == 1
    stream = S19.read_bytes().replace(b'\n', b'\r\n')
    assert b'Entry 2000' in host.send(cpu, b'L\r' + stream)
    assert all(mem.ram[a] == byte for a, byte in IMAGE.items())
    assert b'H registered' in host.send(cpu, b'G 2000\r')
    assert mem.ram[MGR['MG_COUNT']] == 15
    assert bytes(mem.ram[0x5800:0x5800+len(PINNED)]) == PINNED
    out = host.send(cpu, b'H\r')
    for text in (b'B0-3', b'D addr [end]', b'M addr bytes', b'F addr bytes',
                 b'G addr', b'L ', b'I start end', b'C 0|1 0-3 addr|V delay',
                 b'J0-3', b'?', b'H ', b'K [Bn 8-D m0 m1 m2 m3|OFF]',
                 b'S start end name [Bn]', b'R name [Bn]', b'T [Bn]',
                 b'Registered: K S R T H '):
        assert text in out, (text, out)
    assert b'Use H' in host.send(cpu, b'H X\r')
    assert b'Registered:' in host.send(cpu, b'h   \r')
    assert b'Bad cmd' in host.send(cpu, b'HELP\r')
    assert host.send(cpu, b'?\r')[1:] == question[1:]
    # Loading another application cannot invalidate the pinned handler/text.
    mem.ram[0x2000:0x5800] = bytes(0x3800)
    assert b'Registered: K S R T H ' in host.send(cpu, b'H\r')
    assert b'K 01' in host.send(cpu, b'K\r')  # Unassigned factory configuration.
    assert b'Bad cmd' not in host.send(cpu, b'T\r')
    assert [bytes(bank) for bank in mem.banks] == before and not mem.events
    cpu.pc = boot.SYM['START']
    boot.hold(cpu)
    assert mem.ram[MGR['MG_COUNT']] == 12
    assert b'Bad cmd' in host.send(cpu, b'H\r')
    assert b'H registered' in install(cpu)


def check_refusals_preserve_live_overlay():
    cpu, mem = host.ready()
    assert b'H registered' in install(cpu)
    state = bytes(mem.ram[0x5800:0x6000])
    assert b'H already registered' in install(cpu)
    assert bytes(mem.ram[0x5800:0x6000]) == state
    assert mem.ram[MGR['MG_COUNT']] == 15
    for address in (0x5800, 0x5FFF):
        cpu, mem = host.ready()
        assert register(cpu, 'X', address)[:2] == (True, 0)
        state = bytes(mem.ram[0x5800:0x6000])
        assert b'overlay busy' in install(cpu)
        assert bytes(mem.ram[0x5800:0x6000]) == state
        assert mem.ram[MGR['MG_COUNT']] == 15
    cpu, mem = host.ready()
    for key in 'ABXY':
        assert register(cpu, key)[:2] == (True, 0)
    state = bytes(mem.ram[0x5800:0x6000])
    assert b'registry full' in install(cpu)
    assert bytes(mem.ram[0x5800:0x6000]) == state
    assert mem.ram[MGR['MG_COUNT']] == 24
    cpu, mem = host.ready()
    mem.ram[MGR['MG_COUNT']] = 0xFF
    state = bytes(mem.ram[0x5800:0x6000])
    assert b'overlay busy' in install(cpu)
    assert bytes(mem.ram[0x5800:0x6000]) == state


def check_registered_keys_and_rts_coexistence():
    cpu, mem = host.ready()
    assert b'H registered' in install(cpu)
    # Independent X lives outside H's reserved overlay. Listing must not call it.
    mem.ram[0x3000] = 0
    mem.ram[0x7400:0x7408] = b'\xa9\xa5\x8d\x00\x30\xa9\x01\x60'
    assert register(cpu, 'X', 0x7400)[:2] == (True, 0)
    assert b'Registered: K S R T H X ' in host.send(cpu, b'H\r')
    assert mem.ram[0x3000] == 0
    assert b'Bad cmd' not in host.send(cpu, b'X\r')
    assert mem.ram[0x3000] == 0xA5
    source = bytes(range(16))
    mem.ram[0x3000:0x3010] = source
    assert b'Done' in host.send(cpu, b'S 3000 300F HELPTEST\r')
    assert b'HELPTEST' in host.send(cpu, b'T\r')
    assert b'Registered: K S R T H X ' in host.send(cpu, b'H\r')
    mem.ram[0x3000:0x3010] = bytes(16)
    assert b'Done' in host.send(cpu, b'R HELPTEST\r')
    assert mem.ram[0x3000:0x3010] == source
    # A corrupt selected configuration disables storage, while help still works.
    mem.banks[3][0x5000] ^= 1
    before = [bytes(bank) for bank in mem.banks]
    assert b'Registered: K S R T H X ' in host.send(cpu, b'H\r')
    assert b'RTS error 07' in host.send(cpu, b'S 3000 300F BLOCKED\r')
    assert [bytes(bank) for bank in mem.banks] == before


def check_missing_corrupt_and_wrong_bank():
    for case in ('missing', 'descriptor', 'core', 'runtime', 'selected', 'resident'):
        cpu, mem = host.original_boot_flash(0 if case == 'resident' else 3)
        if case != 'resident':
            # Exercise the loader's initialization path, not an already pinned image.
            assert host.call(cpu, MGR['MG_INIT_ENTRY'])[0]
            cpu.pc = boot.SYM['V2_PROMPT']
            boot.hold(cpu)
        if case == 'missing':
            mem.banks[3][0x6000:0x7000] = b'\xff'*4096
        elif case == 'descriptor':
            mem.banks[3][0x6003] ^= 1
        elif case == 'core':
            mem.banks[3][0x7100] ^= 1
        elif case == 'runtime':
            mem.banks[3][0x6200] ^= 1
        elif case == 'selected':
            host.send(cpu, b'B2\r')
        else:
            host.send(cpu, b'B3\r')  # Core resident in bank 0; selected bank 3.
        state = bytes(mem.ram[0x5800:0x6000])
        before = [bytes(bank) for bank in mem.banks]
        assert b'H requires a valid bank-3 b2 manager' in install(cpu), case
        assert bytes(mem.ram[0x5800:0x6000]) == state, case
        assert [bytes(bank) for bank in mem.banks] == before and not mem.events
        assert mem.ram[MGR['MG_COUNT']] == 0, case


def main():
    checks = [check_independent_help_and_lifetime,
              check_refusals_preserve_live_overlay,
              check_registered_keys_and_rts_coexistence,
              check_missing_corrupt_and_wrong_bank]
    for check in checks:
        check()
        print('PASS:', check.__name__, flush=True)
    (module.OUT / 'help-tests.json').write_text(json.dumps({
        'passed': [check.__name__ for check in checks],
        'module_sha256': hashlib.sha256(S19.read_bytes()).hexdigest(),
        'firmware_sha256': hashlib.sha256(boot.IMAGE).hexdigest(),
        'core_bytes_added': 0, 'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
