"""FLASH busy LEDs must return to normal at the prompt, including failure paths."""
import argparse
from pathlib import Path
import test_bank_monitor as app

LED = 0x7fa0


def run(build):
    checks = []
    def ok(h,name,busy=None):
        assert h.m.ram[LED] == 1, (h.name,name,hex(h.m.ram[LED]))
        if busy is not None:
            assert busy and all(v & 0xf0 == 0xf0 for v in busy), busy[:10]
        checks.append(dict(cpu=h.name,name=name,idle_LED='01',busy_seen=busy is not None))
        print('PASS',h.name,name,flush=True)
    for cpu in ('65c02','65c816-e'):
        h = app.Machine(build,cpu); h.boot(); ok(h,'startup')
        for port in (1,2):
            h.cmd(b'B0\r',port)
            h.m.arm((0,0x90)); busy = []
            h.m.observer = lambda m: busy.append(m.ram[LED])
            byte = h.sector(0,0x90)[0] ^ 255
            line = f'F 9000 {byte:02X}\r'.encode()
            assert b'OK: verified sector' in h.write(line,port)
            h.m.assert_preserved(); ok(h,f'port{port}-program',busy)
            h.m.arm((0,0x90))
            assert b'identical; no erase' in h.write(line,port)
            assert not h.m.events; ok(h,f'port{port}-identical-edit')
            h.m.arm((0,0x90)); busy = []
            h.m.observer = lambda m: busy.append(m.ram[LED])
            assert b'OK: verified sector' in h.write(b'I 9000\r',port)
            assert h.sector(0,0x90) == b'\xff'*4096
            ok(h,f'port{port}-erase',busy)
            h.m.arm((0,0x90))
            assert b'identical; no erase' in h.write(b'I 9000\r',port)
            assert not h.m.events; ok(h,f'port{port}-already-erased')
            assert b'Cancelled' in h.write(b'F 9000 00\r',port,yes=b'NO\r')
            assert not h.m.events; ok(h,f'port{port}-cancel')
            assert b'REFUSED:' in h.cmd(b'I\r',port)
            assert b'REFUSED:' in h.cmd(b'F 8000 55\r',port)
            assert not h.m.events; ok(h,f'port{port}-syntax-protection')
            h.m.arm((0,0x90)); busy = []
            h.m.observer = lambda m: busy.append(m.ram[LED])
            h.m.fault = 'erase_verify'
            assert b'FAILED: flash/readback' in h.write(b'F 9000 00\r',port)
            h.m.fault = None
            h.m.assert_preserved(); ok(h,f'port{port}-erase-failure',busy)
        h.m.observer = None
        # A fresh machine isolates the failed journal from earlier wear history.
        h = app.Machine(build,cpu); h.boot()
        h.m.banks[3][0x4000+50] ^= 1
        h.m.arm((0,0x90))
        assert b'durable wear reservation' in h.write(b'F 9000 00\r')
        assert not h.m.events; ok(h,'invalid-journal-refusal')
        for origin in (0x9000,):
            h = app.Machine(build,cpu,origin); h.boot(); ok(h,'alternate-9000-startup')
    result = dict(passed=True,hardware=False,serial_access=False,groups=len(checks),tests=checks,
        checker_sha256=app.base.sha(Path(__file__).read_bytes()),
        build_report_sha256=app.base.sha((build/'bank-monitor-build.json').read_bytes()))
    app.base.save(build/'bank-monitor-led-tests.json',result)
    print('PASS',len(checks),'LED groups')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--build',type=Path,required=True)
    run(p.parse_args().build.resolve())
