"""Verify selected H/X initialize before application entry without FT245."""
import hashlib
import json
import test_v2_b2_autoload as test


def main():
    cpu, mem = test.fresh()
    test.edit(cpu,'+X')
    test.edit(cpu,'+H')
    assert b'Done' in test.host.send(cpu,b'C 1 3 2000 A\rY\r')
    mem.ft245_present = False
    start = len(mem.tx)
    cpu.pc = test.host.boot.SYM['START']
    test.host.boot.run(cpu,lambda:cpu.pc==0x2000,limit=8_000_000)
    assert test.keys(mem) == b'KRSTXH'
    assert len(mem.tx) == start
    assert mem.ram[test.host.boot.SYM['V2_CONSOLE']] == 0xFF
    assert mem.bank == 3 and not mem.events[-1][0] == 'erase'
    # Connected application startup also keeps its complete hold window ahead
    # of registration, while all selected commands exist at application entry.
    mem.ft245_present = True
    start = len(mem.tx)
    cpu.pc = test.host.boot.SYM['START']
    test.host.boot.run(cpu,lambda:cpu.pc==0x2000,limit=8_000_000)
    out = bytes(mem.tx[start:])
    assert out.startswith(b'.' * 10), out
    assert out.startswith(b'.' * 10 + b'\r\nK registered'), out
    assert test.keys(mem) == b'KRSTXH'
    result = dict(passed=['selected H/X, no FT245 output, C application reached'],
        physical_hardware_tested=False,
        firmware_sha256=hashlib.sha256(test.host.boot.IMAGE).hexdigest(),
        manager_storage_sha256=hashlib.sha256((test.host.firmware.OUT /
            (test.host.firmware.STEM+'-b000-bfff.bin')).read_bytes()).hexdigest(),
        provider_sha256=hashlib.sha256(test.HX).hexdigest())
    (test.host.firmware.OUT/'autoload-headless-tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: selected providers before headless application entry',flush=True)


if __name__ == '__main__':
    main()
