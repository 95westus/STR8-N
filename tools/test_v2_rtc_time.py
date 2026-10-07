"""Execute TIME and the read-only example; prove no RTC/EEPROM/flash writes."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-time')
import json
from pathlib import Path
from beta4_migration import read_s19
from test_v2_journal import boot,call,event,EQ,OUT,k

ROOT=Path(__file__).resolve().parents[1]

def main():
    checks=[]
    cpu,m=boot();assert call(cpu,3,key=b'AL')==0
    cpu.pc=0x7E67;k.model.run(cpu,lambda:k.model.waiting(cpu),16000000)
    # Latch an event after boot; TIME must not use boot's save/ACK path.
    m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(3)
    before=bytes(m.bus.ee);m.bus.writes.clear()
    output=k.model.command(cpu,b'TIME\r',20000000)
    assert b'UTC 2026-12-31 23:59:58' in output and b'Power down' not in output and b'PF logged' not in output
    assert m.bus.rtc_regs[3]&0x10 and bytes(m.bus.ee)==before and not m.bus.writes and not m.events
    assert m.ram[0x7D25]==0
    output=k.model.command(cpu,b'TIME X\r',16000000);assert b'UTC 2026-' not in output
    output=k.model.command(cpu,b'T\r',16000000);assert b'UTC 2026-' not in output
    output=k.model.command(cpu,b'?\r',16000000);assert b'TIME' in output
    checks.append('TIME prints UTC only, preserves live evidence and keeps TABLE/T and argument parsing unchanged')
    print('PASS',checks[-1],flush=True)
    cells,entry=read_s19(ROOT/'BUILD/v2-time-example/time-example.s19')
    def example(cpu):
        for a,v in cells.items():cpu.memory.ram[a]=v
        return k.model.command(cpu,b'G 2000\r',20000000)
    for bank in range(4):
        cpu,m=boot();m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(4)
        m.ram[0x7D26]=0  # Normal HOLD return, not a new boot.
        m.bus.writes.clear();before=bytes(m.bus.ee)
        k.model.command(cpu,f'B{bank}\r'.encode(),16000000)
        output=example(cpu);assert b'UTC 2026-12-31 23:59:58' in output
        assert bytes(m.bus.ee)==before and m.bus.rtc_regs[3]&0x10 and not m.bus.writes and not m.events
        meta=json.loads((ROOT/'BUILD/v2-time-example/build.json').read_text())
        copy=m.ram[meta['symbols']['MY_TIME']:meta['symbols']['MY_TIME']+8]
        assert bytes(copy)==bytes((0xEA,7,12,31,2,23,59,58))
    checks.append('example validates discovery, copies binary UTC and runs through all four caller banks without writes')
    print('PASS',checks[-1],flush=True)
    for fault in ('absent','stopped','invalid','software'):
        cpu,m=boot();m.ram[0x7D26]=0
        if fault=='absent':m.bus.devices.pop(0x6F)
        elif fault=='stopped':m.bus.rtc_regs[0]&=0x7F;m.bus.rtc_regs[3]&=~0x20
        elif fault=='invalid':m.bus.rtc_regs[4]=0
        else:m.ram[0x7D04]=0
        m.bus.writes.clear()
        if fault!='software':
            output=k.model.command(cpu,b'TIME\r',20000000)
            expected=(b'RTCC: Time unavailable',b'RTCC: Time stopped',b'RTCC: Time invalid') if k.REPORT.get('eui_binding') else (b'RTC unavailable',b'RTC stopped',b'RTC time invalid')
            assert expected[0 if fault=='absent' else 1 if fault=='stopped' else 2] in output
        output=example(cpu);assert b'UTC unavailable; error ' in output and not m.bus.writes and not m.events
    checks.append('missing RTC/software and stopped/invalid calendars fail safely in the example; TIME reports bounded clock status')
    print('PASS',checks[-1],flush=True)
    (OUT/'time-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],example_sha256=meta['sha256'],physical_hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
