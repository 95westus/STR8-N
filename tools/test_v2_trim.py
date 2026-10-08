"""Exercise confirmed normal trim, parser, caller banks and transfer faults."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-trim')
import json, binascii
from pathlib import Path
from beta4_migration import read_s19
from test_v2_journal import boot, call, EQ, OUT, k
from build_v2_rtc_trim import merge_identity_tail
ROOT=Path(__file__).resolve().parents[1]
CLOCK=ROOT/'BUILD/v2-clock-1.5'
CM=json.loads((CLOCK/'build.json').read_text()); CELLS,e=read_s19(CLOCK/'clock.s19')

def launch(cpu):
    cpu.pc=0x7E67; k.model.run(cpu,lambda:k.model.waiting(cpu),18000000)
    for a,v in CELLS.items():cpu.memory.ram[a]=v
    return k.model.command(cpu,b'G 2000\r',18000000)

def raw(steps):return abs(steps)|(0x80 if steps>0 else 0)

def main():
    checks=[]
    def passed(message):
        checks.append(message);print('PASS',message,flush=True)
    cpu,m=boot();m.bus.rtc_regs[7]=0x83;m.bus.rtc_regs[8]=0x25;m.bus.rtc_regs[3]|=0x10
    prior=bytes(m.bus.rtc_regs);ee=bytes(m.bus.ee);flash=[bytes(b) for b in m.banks];m.bus.writes.clear()
    assert call(cpu,10,param=0x94,key=b'XX')==6 and not m.bus.writes
    assert call(cpu,10,param=0x80,key=b'TR')==9 and not m.bus.writes
    assert m.ram[EQ['J_KEY']:EQ['J_KEY']+2]==b'\0\0'
    for steps in range(-127,128):
        assert call(cpu,10,param=raw(steps),key=b'TR')==0,steps
        assert m.bus.rtc_regs[7]==0x83 and m.bus.rtc_regs[8]==raw(steps)
        assert bytes(m.bus.rtc_regs[:7])==prior[:7] and bytes(m.bus.rtc_regs[9:])==prior[9:]
    assert all(dev==0x6F and address==8 for dev,address,value in m.bus.writes)
    assert bytes(m.bus.ee)==ee and [bytes(b) for b in m.banks]==flash
    writes=list(m.bus.writes);assert call(cpu,10,param=0xFF,key=b'TR')==0 and m.bus.writes==writes
    passed('all 255 signed step values, canonical zero, consumed intent; only OSCTRIM changes; calendar/PF/EEPROM/flash preserved; repeat is read-only')
    m.bus.rtc_regs[7]=0x87;m.bus.rtc_regs[8]=0x25;m.bus.writes.clear()
    assert call(cpu,10,param=0x94,key=b'TR')==0
    assert m.bus.writes==[(0x6F,7,0x83),(0x6F,8,0x94)] and m.bus.rtc_regs[7]==0x83
    for control in (0x90,0xA0,0xC0):
        m.bus.rtc_regs[7]=control;m.bus.writes.clear()
        assert call(cpu,10,param=0x94,key=b'TR')==6 and m.bus.rtc_regs[7]==control and not m.bus.writes
    m.bus.devices.pop(0x6F);assert call(cpu,10,param=0x94,key=b'TR')==2 and not m.bus.writes
    passed('coarse disabled/verified before new trim; other controls preserved; active alarm/SQW and absent RTC refuse writes')
    for ignore in (7,8):
        cpu,m=boot();m.bus.rtc_regs[7]=0x84;m.bus.rtc_regs[8]=0x25;m.bus.writes.clear()
        original=m.bus.rising
        def fault(sda,original=original,m=m,ignore=ignore):
            old=m.bus.rtc_regs[ignore];before=len(m.bus.writes);original(sda)
            if len(m.bus.writes)>before and m.bus.writes[-1][:2]==(0x6F,ignore):m.bus.rtc_regs[ignore]=old
        m.bus.rising=fault
        assert call(cpu,10,param=0x94,key=b'TR')==7
        assert m.bus.rtc_regs[8]==0x25
        if ignore==7:assert m.bus.writes==[(0x6F,7,0x80)]
        m.bus.rising=original
        assert call(cpu,10,param=0x94,key=b'TR')==0
    cpu,m=boot();m.bus.rtc_regs[7]=0x84;m.bus.rtc_regs[8]=0x25;m.bus.writes.clear();original=m.bus.rising
    def nack_after_control(sda):
        before=len(m.bus.writes);original(sda)
        if len(m.bus.writes)>before and m.bus.writes[-1][:2]==(0x6F,7):m.bus.devices.pop(0x6F)
    m.bus.rising=nack_after_control
    assert call(cpu,10,param=0x94,key=b'TR')==2 and m.bus.rtc_regs[8]==0x25
    passed('ignored writes and device disappearance return errors; no new trim after failed coarse readback; locks recover')
    cpu,m=boot();m.bus.rtc_regs[7]=0x80;m.bus.rtc_regs[8]=0;m.bus.writes.clear()
    assert b'CLOCK 1.5' in launch(cpu)
    output=k.model.command(cpu,b'TRIM\rSTATUS\r',18000000)
    assert b'Trim 0 steps; coarse OFF; OSCTRIM $00' in output and not m.bus.writes
    invalid=(b'TRIM +',b'TRIM -',b'TRIM 128',b'TRIM -128',b'TRIM 255',b'TRIM 999',b'TRIM 1000',b'TRIM 0000',b'TRIM 1X',b'TRIM +1 X',b'TRIM  1',b'COARSE ON')
    for cmd in invalid:
        output=k.model.command(cpu,cmd+b'\r',18000000)
        assert b'Invalid command/date' in output and b'Type YES' not in output and not m.bus.writes,cmd
    for reply in (b'NO\r',b'Y\r',b'YES EXTRA\r',b'\x1b',b'\x03'):
        output=k.model.command(cpu,b'TRIM -20\r'+reply,18000000)
        assert b'Canceled' in output and not m.bus.writes
    for steps,cmd in ((-127,b'-127'),(-20,b'-20'),(-1,b'-1'),(0,b'0'),(1,b'+1'),(20,b'20'),(127,b'+127'),(0,b'-0'),(0,b'+000')):
        output=k.model.command(cpu,b'TRIM '+cmd+b'\rYES\r',18000000)
        display=(f'{steps:+}' if steps else '0').encode()
        assert b'Requested trim: '+display+b' steps; coarse OFF.' in output,(cmd,output)
        assert b'Trim '+display+b' steps; coarse OFF;' in output and m.bus.rtc_regs[8]==raw(steps),(cmd,output)
    for bank in range(4):
        pcr=(m.ram[0x7FEC]&0x11)|(0xCC,0xCE,0xEC,0xEE)[bank];m[0x7FEC]=pcr
        output=k.model.command(cpu,b'TRIM +20\rYES\rTRIM -20\rYES\r',24000000)
        assert m.ram[0x7FEC]==pcr and b'Trim -20 steps; coarse OFF' in output
    m.bus.rtc_regs[7]|=4
    output=k.model.command(cpu,b'TRIM\rTRIM 0\rYES\rQ\r',18000000)
    assert b'coarse ON' in output and b'Trim 0 steps; coarse OFF' in output
    assert m.bus.rtc_regs[7]==0x80 and m.bus.rtc_regs[8]==0 and not m.events
    passed('CLOCK read-only status, signed parser/bounds, cancellation/exact YES, directions/extremes/zero, all caller banks and coarse recovery')
    # Synthetic identity only: no board backups used by this test.
    old=(ROOT/'BUILD/v2-rtc-binding/str8n-journal-9000-9fff.bin').read_bytes()
    body=b'EI\x01\0'+(1).to_bytes(4,'little')+bytes.fromhex('020000000001')+bytes([255])*14
    record=body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')+b'\xff\0'
    old=old[:3072]+record+bytes([255])*992
    candidate=(OUT/'str8n-journal-9000-9fff.bin').read_bytes();merged=merge_identity_tail(old,candidate)
    assert merged[3072:]==old[3072:] and k.fw.crc(merged[:3072])==0
    passed('synthetic identity tail retained in compatible candidate upgrade')
    (OUT/'trim-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts'],clock_sha256=CM['sha256'],hardware_tested=False),indent=2)+'\n')
if __name__=='__main__':main()
