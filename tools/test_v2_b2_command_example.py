"""Run the complete flash command example in the banked 65C02 host model."""
import hashlib
import json
import build_v2_b2_command_example as module
import test_v2_b2 as host

META = json.loads((module.OUT / 'manifest.json').read_text())
SECTOR = (module.OUT / (module.NAME + '.bin')).read_bytes()


def ready():
    cpu, mem = host.ready()
    mem.banks[3][0x4000:0x5000] = SECTOR
    return cpu, mem


def initialize(cpu):
    return host.send(cpu, b'G C700\r')


def register(cpu, key, address):
    ok, low, high, kind = host.lookup(cpu, 'COMMAND.REGISTER')
    assert ok and kind == 1
    result = host.call(cpu, low+256*high, ord(key), address & 255, address >> 8)
    cpu.pc = host.boot.SYM['V2_PROMPT']
    host.boot.hold(cpu)
    return result


def check_commands_and_lifetime():
    cpu, mem = ready()
    app = bytes(mem.ram[0x0200:0x6100])
    flash = [bytes(bank) for bank in mem.banks]
    initialize(cpu)
    assert mem.ram[0x7400:0x7406] == b'\x4c\x00\xc3\x4c\x00\xca'
    assert mem.ram[host.MGR['MG_COUNT']] == 18
    assert b'Registered: K S R T X H ' in host.send(cpu, b'H\r')
    for line, expected in (
        (b'X\r', b'Use X HELLO or X ECHO text'),
        (b'X HELLO\r', b'HELLO FROM X'),
        (b'x\thello  \r', b'HELLO FROM X'),
        (b'X ECHO Hello world\r', b'HELLO WORLD\r\n'),
        (b'X ECHO\r', b'\r\n'),
        (b'X HELLOX\r', b'Use X HELLO or X ECHO text'),
        (b'X HELLO EXTRA\r', b'Use X HELLO or X ECHO text'),
        (b'X ECHOX text\r', b'Use X HELLO or X ECHO text'),
        (b'X UNKNOWN\r', b'Use X HELLO or X ECHO text'),
        (b'XY\r', b'Bad cmd')):
        assert expected in host.send(cpu, line), line
    assert bytes(mem.ram[0x0200:0x6100]) == app
    for bank in range(4):
        host.send(cpu, f'B{bank}\r'.encode('ascii'))
        assert b'HELLO FROM X' in host.send(cpu, b'X HELLO\r')
    host.send(cpu, b'B3\r')
    # Code and strings remain valid after the user application is replaced.
    mem.ram[0x0200:0x5800] = bytes(0x5600)
    assert b'HELLO FROM X' in host.send(cpu, b'X HELLO\r')
    initialize(cpu)
    assert mem.ram[host.MGR['MG_COUNT']] == 18  # Idempotent.
    assert [bytes(bank) for bank in mem.banks] == flash and not mem.events
    # Reset withdraws registrations. An initializer must run again.
    cpu.pc = host.boot.SYM['START']
    host.boot.hold(cpu)
    assert b'Bad cmd' in host.send(cpu, b'X HELLO\r')
    initialize(cpu)
    assert b'HELLO FROM X' in host.send(cpu, b'X HELLO\r')


def check_conflicts_and_capacity():
    for key, address in (('X', 0x7600), ('Y', 0x7403), ('Y', 0x7404)):
        cpu, mem = ready()
        assert register(cpu, key, address)[:2] == (True, 0)
        before = bytes(mem.ram[0x7400:0x7406])
        assert b'X/stub conflict or registry full' in initialize(cpu)
        assert bytes(mem.ram[0x7400:0x7406]) == before
    cpu, mem = ready()
    for key in 'VWYZ':
        assert register(cpu, key, 0x7600)[:2] == (True, 0)
    before = bytes(mem.ram[0x7400:0x7406])
    assert b'X/stub conflict or registry full' in initialize(cpu)
    assert bytes(mem.ram[0x7400:0x7406]) == before
    # Invalid E descriptor refuses before touching the manager stubs.
    cpu, mem = ready()
    mem.banks[3][0x6000] ^= 1
    before = bytes(mem.ram[0x7400:0x7406])
    assert b'X requires a valid bank-3 b2 manager' in initialize(cpu)
    assert bytes(mem.ram[0x7400:0x7406]) == before


def check_autostart_and_storage():
    cpu, mem = ready()
    # The boot pocket points to this provider's initializer, which chains H.
    assert b'Done' in host.send(cpu, b'C 1 3 C700 0A\rY\r')
    cpu.pc = host.boot.SYM['START']
    host.boot.run(cpu, lambda: host.boot.waiting(cpu), limit=12_000_000)
    assert b'HELLO FROM X' in host.send(cpu, b'X HELLO\r')
    assert b'Registered: K S R T X H ' in host.send(cpu, b'H\r')
    payload = bytes(range(16))
    mem.ram[0x3000:0x3010] = payload
    assert b'Done' in host.send(cpu, b'S 3000 300F XTEST\r')
    mem.ram[0x3000:0x3010] = bytes(16)
    assert b'Done' in host.send(cpu, b'R XTEST\r')
    assert mem.ram[0x3000:0x3010] == payload
    assert b'HELLO FROM X' in host.send(cpu, b'X HELLO\r')


def main():
    checks = [check_commands_and_lifetime, check_conflicts_and_capacity,
              check_autostart_and_storage]
    for check in checks:
        check()
        print('PASS:', check.__name__, flush=True)
    (module.OUT / 'command-example-tests.json').write_text(json.dumps(dict(
        passed=[check.__name__ for check in checks],
        firmware_sha256=hashlib.sha256(host.boot.IMAGE).hexdigest(),
        module_sha256=hashlib.sha256(SECTOR).hexdigest(),
        physical_hardware_tested=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
