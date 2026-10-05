"""Dynamic service ABI and compatibility tests on assembled banked opcodes."""
import hashlib
import json
import test_v2_b2 as host

COUNT, TABLE = 0x7DEB, 0x7600


def publish(cpu, name, version=1, kind=1, target=0x7800, name_address=0x7700,
            descriptor_address=0x2400, reserved=0):
    ok, lo, hi, service_kind = host.lookup(cpu, 'SERVICE.REGISTER')
    assert ok and service_kind == 1
    if name is not None:
        encoded = name.encode('ascii')+b'\0'
        cpu.memory.ram[name_address:name_address+len(encoded)] = encoded
    descriptor = name_address.to_bytes(2, 'little')+bytes((version, kind))+target.to_bytes(2, 'little')
    if descriptor_address < 0x7900:
        cpu.memory.ram[descriptor_address:descriptor_address+6] = descriptor
    return host.call(cpu, lo+256*hi, descriptor_address & 255,
                     descriptor_address >> 8, reserved)[:2]


def check_lookup_versions_and_calls():
    cpu, mem = host.ready()
    before_commands = mem.ram[0x7DCB], bytes(mem.ram[0x7DD0:0x7DE8])
    mem.ram[0x7800:0x7803] = b'\xa9\x42\x60'
    assert publish(cpu, 'DEMO.VALUE') == (True, 0)
    ok, lo, hi, kind = host.lookup(cpu, 'DEMO.VALUE')
    assert (ok, lo+256*hi, kind) == (True, 0x7800, 1)
    assert host.call(cpu, lo+256*hi)[1] == 0x42
    assert publish(cpu, 'DEMO.VALUE', version=2, kind=0, target=0x7808,
                   name_address=0x7720) == (True, 0)
    mem.ram[0x7808] = 0xA5
    ok, lo, hi, kind = host.lookup(cpu, 'DEMO.VALUE', 2)
    assert (ok, lo+256*hi, kind, mem[lo+256*hi]) == (True, 0x7808, 0, 0xA5)
    assert host.lookup(cpu, 'DEMO.VALUE', 3)[:2] == (False, 2)
    assert host.lookup(cpu, 'demo.value')[:2] == (False, 1)
    assert host.lookup(cpu, 'NO.SERVICE')[:2] == (False, 1)
    # Same name as static directory with a new version is found after static v1.
    assert publish(cpu, 'CONSOLE.PUTC', version=2, name_address=0x7740) == (True, 0)
    assert host.lookup(cpu, 'CONSOLE.PUTC', 1)[1:3] == (0x6D, 0x7E)
    assert host.lookup(cpu, 'CONSOLE.PUTC', 2)[1:3] == (0, 0x78)
    # A flash provider can keep its descriptor, name and data in resident C.
    mem.banks[3][0x4700:0x470A] = b'ROM.VALUE\0'
    mem.banks[3][0x4780:0x4786] = bytes.fromhex('00 C7 01 00 90 C7')
    mem.banks[3][0x4790] = 0x55
    ok, low, high, kind = host.lookup(cpu, 'SERVICE.REGISTER')
    assert ok and kind == 1
    assert host.call(cpu, low+256*high, 0x80, 0xC7, 0)[:2] == (True, 0)
    assert host.lookup(cpu, 'ROM.VALUE') == (True, 0x90, 0xC7, 0)
    assert mem[0xC790] == 0x55
    assert (mem.ram[0x7DCB], bytes(mem.ram[0x7DD0:0x7DE8])) == before_commands
    # Caller may reuse the copied descriptor; pinned name/code are retained.
    mem.ram[0x2400:0x2406] = bytes(6)
    assert host.lookup(cpu, 'DEMO.VALUE')[0]


def check_refusals_and_full_table():
    cpu, mem = host.ready()
    def refused(expected, **kwargs):
        state = bytes(mem.ram[TABLE:TABLE+48]), mem.ram[COUNT]
        assert publish(cpu, **kwargs) == (False, expected), kwargs
        assert (bytes(mem.ram[TABLE:TABLE+48]), mem.ram[COUNT]) == state
    refused(2, name='CONSOLE.PUTC')
    for broken_count in (1, 5, 49, 255):
        mem.ram[COUNT] = broken_count
        refused(1, name='BAD.COUNT')
    mem.ram[COUNT] = 0
    for kwargs in (dict(name=''), dict(name='A'*32), dict(name='BAD NAME'),
                   dict(name='BAD', version=0), dict(name='BAD', kind=2),
                   dict(name='BAD', reserved=1), dict(name='BAD', target=0x2000),
                   dict(name='BAD', target=0x7F80), dict(name='BAD', name_address=0x57F0),
                   dict(name='A', name_address=0x5FFF),
                   dict(name='BAD', descriptor_address=0x78FB),
                   dict(name='BAD', descriptor_address=0xFFFF)):
        refused(1, **kwargs)
    assert publish(cpu, 'A'*31) == (True, 0)
    refused(2, name='A'*31)
    for i in range(1, 8):
        assert publish(cpu, f'DEMO.{i}', name_address=0x7700+i*32) == (True, 0)
    assert mem.ram[COUNT] == 48
    refused(3, name='NINTH', name_address=0x7680)
    assert all(host.lookup(cpu, f'DEMO.{i}')[0] for i in range(1, 8))


def check_lifetime_corruption_and_missing_storage():
    cpu, mem = host.ready()
    assert publish(cpu, 'DEMO.RESET') == (True, 0)
    # Revalidating the same image refreshes policy without losing registrations.
    assert host.call(cpu, host.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
    assert host.lookup(cpu, 'DEMO.RESET')[0]
    cpu.pc = host.boot.SYM['START']
    host.boot.hold(cpu)
    assert mem.ram[COUNT] == 0
    assert host.call(cpu, host.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
    assert host.lookup(cpu, 'DEMO.RESET')[:2] == (False, 1)
    for damage in ('missing', 'payload', 'service-code'):
        cpu, mem = host.original_boot_flash(3)
        if damage == 'missing':
            mem.banks[3][0x3000:0x4000] = b'\xff'*4096
        elif damage == 'payload':
            mem.banks[3][0x3008] ^= 1
        else:
            mem.banks[3][host.firmware.SERVICE_ROM_START-0x8000] ^= 1
        cpu.pc = host.boot.SYM['START']
        host.boot.hold(cpu)
        assert not host.call(cpu, host.REPORT['manager_rom']['MG_ROM_INIT_ENTRY'])[0]
        assert mem.ram[COUNT] == 0 and mem.ram[host.MGR['MG_READY']] == 0
        cpu.pc = host.boot.SYM['V2_PROMPT']
        host.boot.hold(cpu)
        assert b'B0-3 D addr' in host.send(cpu, b'?\r')
        assert b'RTS unavailable' in host.send(cpu, b'T\r')


def main():
    checks = [check_lookup_versions_and_calls, check_refusals_and_full_table,
              check_lifetime_corruption_and_missing_storage]
    for check in checks:
        check()
        print('PASS:', check.__name__, flush=True)
    (host.firmware.OUT / 'service-registration-tests.json').write_text(json.dumps(dict(
        passed=[check.__name__ for check in checks],
        ef_sha256=hashlib.sha256(host.boot.IMAGE).hexdigest(),
        manager_storage_sha256=hashlib.sha256((host.firmware.OUT /
            f'{host.firmware.STEM}-b000-bfff.bin').read_bytes()).hexdigest(),
        physical_hardware_tested=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
