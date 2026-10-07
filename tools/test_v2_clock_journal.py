"""CLOCK history views, confirmations, absent EEPROM and bank preservation."""
import json,os
from pathlib import Path
from test_v2_journal import boot,call,event,OUT,k
from build_v2_clock_journal import OUT as DEFAULT_CLOCK
CLOCK=Path(os.environ.get('STR8_CLOCK_BUILD',str(DEFAULT_CLOCK)))
from beta4_migration import read_s19

META=json.loads((CLOCK/'build.json').read_text());CELLS,e=read_s19(CLOCK/'clock.s19')

def launch(cpu):
    for a,v in CELLS.items():cpu.memory.ram[a]=v
    return k.model.command(cpu,b'G 2000\r',16000000)

def main():
    cpu,m=boot();assert call(cpu,3,key=b'AL')==0
    for n in (1,2,3):
        m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(n);assert call(cpu,1)==0
    output=launch(cpu);assert ('CLOCK '+META['version']).encode() in output
    output=k.model.command(cpu,b'HISTORY\r',16000000)
    assert output.index(b'seq 00000003')<output.index(b'seq 00000002')<output.index(b'seq 00000001')
    assert b'Power down: 10-07 05:03' in output
    output=k.model.command(cpu,b'SHOW 2\r',16000000);assert b'seq 00000002' in output and b'Recorded at' in output
    before=bytes(m.bus.ee[:128]);flag=m.bus.rtc_regs[3]
    output=k.model.command(cpu,b'CLEAR 2\rNO\rCLEAR ALL\rYES\r',16000000);assert bytes(m.bus.ee[:128])==before
    output=k.model.command(cpu,b'CLEAR 2\rYES\rHISTORY\r',16000000);assert b'seq 00000002' not in output.split(b'History cleared.')[-1]
    assert m.bus.rtc_regs[3]==flag
    output=k.model.command(cpu,b'CLEAR ALL\rDELETE ALL\rHISTORY\r',20000000);assert b'No saved event' in output and m.bus.rtc_regs[3]==flag
    k.model.command(cpu,b'Q\r',12000000)
    print('PASS history newest-first/SHOW; CLEAR n and strong CLEAR ALL do not alter RTC latch/time')
    # A live event with confirmed ACK is archived by CLOCK, then acknowledged.
    m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(7);launch(cpu)
    output=k.model.command(cpu,b'ACK\rYES\rHISTORY\r',20000000);assert b'UTC time keeps running unchanged.' in output and b'latch verified clear' in output and b'seq 00000001' in output
    k.model.command(cpu,b'Q\r',12000000)
    # History calls from RAM preserve caller bank using the client's guarded bridge.
    launch(cpu)
    for b in range(4):
        pcr=(m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[b];m[0x7FEC]=pcr
        output=k.model.command(cpu,b'HISTORY\r',16000000);assert b'seq 00000001' in output and m.ram[0x7FEC]==pcr
    k.model.command(cpu,b'Q\r',12000000)
    launch(cpu);m.bus.devices.pop(0x57)
    output=k.model.command(cpu,b'HISTORY\rR\rQ\r',16000000);assert b'History unavailable' in output and b'UTC 2026-' in output
    print('PASS ACK archives before clear; journal bridge preserves all banks; absent EEPROM retains time functions')
    (CLOCK/'test-results.json').write_text(json.dumps(dict(passed=True,sha256=META['sha256'],s19_sha256=META['s19_sha256'],kernel_artifacts=k.REPORT['artifacts']),indent=2)+'\n')

if __name__=='__main__':main()
