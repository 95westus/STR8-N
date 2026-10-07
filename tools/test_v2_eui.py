"""Exercise protected EUI reads independently of RTC validity; no data writes."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-eui')
import json
from pathlib import Path
from beta4_migration import read_s19
from test_v2_journal import Memory,call,EQ,OUT,k

ROOT=Path(__file__).resolve().parents[1]
IDENTITY=bytes.fromhex('5410ecb664d3')
CLOCK=ROOT/'BUILD/v2-clock-1.3'
CELLS,ENTRY=read_s19(CLOCK/'clock.s19')

def boot(fault=None,identity=IDENTITY):
    m=Memory();m.bus.ee[0xF2:0xF8]=identity
    if fault=='stopped':m.bus.rtc_regs[0]&=0x7F;m.bus.rtc_regs[3]&=~0x20
    elif fault=='invalid':m.bus.rtc_regs[4]=0
    elif fault=='rtc-absent':m.bus.devices.pop(0x6F)
    elif fault=='no-edu':m.bus.devices.pop(0x6F);m.bus.devices.pop(0x57)
    cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu
    k.model.run(cpu,lambda:k.model.waiting(cpu),22000000)
    return cpu,m

def launch(cpu):
    for a,v in CELLS.items():cpu.memory.ram[a]=v
    return k.model.command(cpu,b'G 2000\r',22000000)

def main():
    checks=[]
    for fault in (None,'stopped','invalid','rtc-absent','no-edu'):
        cpu,m=boot(fault)
        expected=b'RTCC: EUI unavailable' if fault=='no-edu' else b'RTCC: EUI 54:10:EC:B6:64:D3'
        assert expected in m.tx and not m.bus.writes and not m.events
        factory=bytes(m.bus.ee[0xF0:0xF8]);before=bytes(m.bus.ee);registers=bytes(m.bus.rtc_regs)
        output=launch(cpu);assert b'CLOCK 1.3' in output and expected in output
        output=k.model.command(cpu,b'EUI\rSTATUS\r',22000000);assert output.count(expected)>=2
        assert not m.bus.writes and not m.events and bytes(m.bus.ee)==before and bytes(m.bus.rtc_regs)==registers
        k.model.command(cpu,b'Q\r',20000000)
        output=k.model.command(cpu,b'TIME\r',20000000);assert b'RTCC: EUI' not in output
        assert bytes(m.bus.ee[0xF0:0xF8])==factory
    checks.append('boot/CLOCK EUI and STATUS work independently of stopped/invalid/absent RTC; no-EDU failure is bounded; TIME stays compact')
    print('PASS',checks[-1],flush=True)
    for identity in (bytes(6),bytes([255])*6):
        cpu,m=boot(identity=identity);assert b'RTCC: EUI unavailable' in m.tx and not m.bus.writes
    cpu,m=boot();assert call(cpu,6)==0 and bytes(m.ram[EQ['J_EUI']:EQ['J_EUI']+6])==IDENTITY
    assert not m.bus.writes
    # Direct private write requests still reject the protected identity region.
    meta=json.loads((OUT/'journal/build.json').read_text())
    m.ram[EQ['EE_ADDR']]=0xF2;m.ram[EQ['EE_COUNT']]=6;m.ram[EQ['EE_WRITE']]=1
    m.ram[EQ['EE_PTR']]=0xA0;m.ram[EQ['EE_PTR']+1]=0x6B
    cpu.stPushWord(0x01FF);cpu.pc=meta['ee_entry'];k.model.run(cpu,lambda:cpu.pc==0x0200,4000000)
    assert cpu.a==9 and not m.bus.writes and bytes(m.bus.ee[0xF2:0xF8])==IDENTITY
    checks.append('identity is six bytes from F2-F7; erased/zero IDs are unavailable; protected writes remain denied')
    print('PASS',checks[-1],flush=True)
    (OUT/'eui-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],clock_sha256=json.loads((CLOCK/'build.json').read_text())['sha256'],hardware_tested=False),indent=2)+'\n')

if __name__=='__main__':main()
