"""Machine-code outage display and explicit ACK, including malformed stamps."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-rtc-powerfail'
import json
from pathlib import Path
from datetime import datetime

import test_v2_rtc_kernel as kernel
from beta4_migration import read_s19
from test_v2_rtc import MPU as BareCPU

ROOT=Path(__file__).resolve().parents[1]
CLOCK=ROOT/'BUILD/v2-clock-1.1'
META=json.loads((CLOCK/'build.json').read_text())
CELLS,ENTRY=read_s19(CLOCK/'clock.s19')
S=META['symbols']
EVENT=bytes.fromhex('03 05 07 70 04 05 07 70')


def boot(stopped=False):
    m=kernel.Memory()
    m.bus.rtc_regs[3]|=0x10
    m.bus.rtc_regs[0x18:0x20]=EVENT
    if stopped:
        m.bus.rtc_regs[0]&=0x7F
        m.bus.rtc_regs[3]&=~0x20
    cpu=kernel.model.MPU(memory=m,pc=0xF004);m.cpu=cpu
    kernel.model.run(cpu,lambda:kernel.model.waiting(cpu),12000000)
    return cpu,m


def launch(cpu):
    for a,v in CELLS.items():cpu.memory.ram[a]=v
    return kernel.model.command(cpu,b'G 2000\r',12000000)


def decode(stamp):
    memory=[0]*65536
    for a,v in CELLS.items():memory[a]=v
    memory[0x1800:0x1804]=stamp
    memory[0xD2:0xD4]=[0,0x18]
    cpu=BareCPU(memory=memory,pc=S['OF_DECODE']);cpu.stPushWord(0x1EFF)
    kernel.model.run(cpu,lambda:cpu.pc==0x1F00,5000)
    return bool(cpu.p&cpu.CARRY),[memory[S[k]] for k in ('OF_MONTH','OF_DAY','OF_HOUR','OF_MINUTE')]


def main():
    checks=[]
    for hour in range(24):
        for minute in (0,9,10,59):
            bcd=lambda x:(x//10)*16+x%10
            ok,fields=decode([bcd(minute),bcd(hour),0x29,0x62])
            assert ok and fields==[2,29,hour,minute]
            h=hour%12 or 12
            ok,fields=decode([bcd(minute),0x40|(0x20 if hour>=12 else 0)|bcd(h),0x29,0x62])
            assert ok and fields==[2,29,hour,minute]
    for stamp in ([0x60,5,7,0x70],[0x0A,5,7,0x70],[3,0x24,7,0x70],
        [3,0x40,7,0x70],[3,5,0,0x70],[3,5,0x31,0x64],[3,5,7,0x7F]):
        assert not decode(stamp)[0]
    checks.append('yearless BCD/calendar validation, all 12/24-hour conversions and malformed field rejection')
    print('PASS',checks[-1],flush=True)
    cpu,m=boot()
    assert b'[power-fail]' in m.tx and b'Power down: 10-07 05:03' in m.tx
    assert b'Power up:   10-07 05:04' in m.tx and not m.bus.writes
    cpu_stopped,stopped=boot(True)
    assert b'RTC stopped - use R CLOCK [power-fail]' in stopped.tx
    assert b'Power down: 10-07 05:03' in stopped.tx and not stopped.bus.writes
    checks.append('boot displays latch and decoded event with healthy or stopped time; latch not consumed')
    print('PASS',checks[-1],flush=True)
    launch(cpu)
    output=kernel.model.command(cpu,b'S\rACK\rNO\r',16000000)
    assert b'Power down: 10-07 05:03' in output and b'Type YES to confirm' in output and b'Canceled' in output
    assert m.bus.rtc_regs[3]&0x10 and not m.bus.writes
    for response in (b'Y\r',b'YES!\r',b'\x03',b'YES'+b'X'*300+b'\r'):
        kernel.model.command(cpu,b'ACK\r'+response,16000000)
        assert m.bus.rtc_regs[3]&0x10 and not m.bus.writes
    calendar=bytes(m.bus.rtc_regs[:3])+bytes(m.bus.rtc_regs[4:9])
    output=kernel.model.command(cpu,b'ACK\rYES\r',16000000)
    assert b'latch verified clear' in output and b'Power down: 10-07 05:03' in output
    assert not m.bus.rtc_regs[3]&0x10 and m.bus.rtc_regs[3]&8
    assert bytes(m.bus.rtc_regs[:3])+bytes(m.bus.rtc_regs[4:9])==calendar
    assert m.ram[0x66DC] and bytes(m.ram[0x66F0:0x66F8])==EVENT
    assert m.bus.writes==[(0x6F,3,0x0A)]
    count=len(m.bus.writes)
    output=kernel.model.command(cpu,b'ACK\r',12000000)
    assert b'nothing cleared' in output and b'Type YES' not in output and len(m.bus.writes)==count
    output=kernel.model.command(cpu,b'Q\r',12000000)
    assert b'[power-fail]' not in output
    checks.append('only exact confirmed ACK clears latch, preserves clock/backup/trim and retained decoded capture; no-event ACK writes nothing')
    print('PASS',checks[-1],flush=True)
    report=dict(passed=True,checks=checks,clock_sha256=META['sha256'],kernel_artifacts=kernel.REPORT['artifacts'])
    (kernel.fw.OUT/'powerfail-test-results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
