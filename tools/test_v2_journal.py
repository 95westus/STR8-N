"""Execute journal with EEPROM page/write-cycle model and fault injection."""
import os
os.environ.setdefault('STR8_RTC_BUILD','BUILD/v2-rtc-journal')
import json
from pathlib import Path
import test_v2_rtc_kernel as k
from test_v2_i2c import Devices

OUT=k.fw.OUT
NEW_MESSAGES=b'RTCC: PF logged, ACK' in (OUT/'str8n-rtc-component-8000-8fff.bin').read_bytes()
EQ={}
for line in (Path(__file__).resolve().parents[1]/'tools/v2-rtc/journal-eq.inc').read_text().splitlines():
    pieces=line.split()
    if len(pieces)>=3 and pieces[1]=='EQU':
        value=pieces[2]
        if value.startswith('$'):EQ[pieces[0]]=int(value[1:],16)
        elif value.isdigit():EQ[pieces[0]]=int(value)


class EEPROM(Devices):
    def __init__(self,array=None,busy=2,fail_stop=None,ack_fail=False):
        super().__init__();self.ee=bytearray([255]*256);self.ee[0xFF]=0
        if array is not None:self.ee[:128]=array
        self.devices[0x57]=self.ee;self.pending=[];self.busy=0;self.delay=busy;self.fail_stop=fail_stop;self.write_stops=0
        self.ack_fail=ack_fail
    def rising(self,sda):
        last=self.mode=='rx' and self.bit==7
        phase=self.phase
        address=self.pointer
        old=self.ee[address] if address<256 else 0
        blocked=last and phase=='address' and (self.value<<1|int(sda))>>1==0x57 and self.busy>0
        if blocked:
            saved=self.devices.pop(0x57);self.busy-=1
        before=len(self.writes)
        super().rising(sda)
        if self.ack_fail and last and phase=='data' and self.selected==0x6F and address==3 and len(self.writes)>before:
            self.rtc_regs[3]|=0x10  # Fault: chip flag fails to clear after ACK write.
        if blocked:self.devices[0x57]=saved
        if last and phase=='data' and self.selected==0x57 and len(self.writes)>before:
            device,addr,value=self.writes.pop();self.ee[addr]=old
            self.pending.append((addr,value))
    def __setitem__(self,address,value):
        previous=self.master_levels() if address in (0x7FC3,0x7FCF) else None
        super().__setitem__(address,value)
        if previous is not None:
            now=self.master_levels()
            if previous&1 and now&1 and not previous&0x80 and now&0x80 and self.pending:
                self.write_stops+=1
                if self.fail_stop!=self.write_stops:
                    for addr,v in self.pending:
                        assert 0<=addr<128,'Factory/status write attempted'
                        self.ee[addr]=v;self.writes.append((0x57,addr,v))
                self.pending.clear();self.busy=self.delay


class Memory(k.Memory):
    def __init__(self,array=None,busy=2,fail_stop=None,ack_fail=False):
        super().__init__();self.banks[3][4096:8192]=(OUT/'str8n-journal-9000-9fff.bin').read_bytes()
        self.bus=EEPROM(array,busy,fail_stop,ack_fail);self.bus.ram=self.ram


def boot(array=None,event=None,**options):
    m=Memory(array,**options)
    if event:
        m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event
    cpu=k.model.MPU(memory=m,pc=0xF004);m.cpu=cpu
    k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
    return cpu,m


def call(cpu,op,param=0,key=b'\0\0'):
    m=cpu.memory;m.ram[EQ['J_PARAM']]=param;m.ram[EQ['J_KEY']:EQ['J_KEY']+2]=key
    cpu.x=op;cpu.stPushWord(0x01FF);cpu.pc=0x9004
    k.model.run(cpu,lambda:cpu.pc==0x0200,12000000)
    return cpu.a


def event(minute):return bytes((minute,5,7,0x70,minute+1,5,7,0x70))


def main():
    checks=[]
    cpu,m=boot();assert m.ram[0x7D19:0x7D21]==b'PJ\x01\x01\x04\x90\x00\x6B'
    assert call(cpu,0)==0 and not m.bus.writes
    assert call(cpu,3,key=b'AL')==0
    assert all(m.bus.ee[x*32:x*32+3]==b'PF\x01' and m.bus.ee[x*32+31]==0 for x in range(4))
    checks.append('read-only scan and explicit initialization, page-aligned writes and bounded busy polling')
    print('PASS',checks[-1],flush=True)
    for n in range(1,7):
        m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(n)
        assert call(cpu,1)==0,(n,hex(cpu.a))
        assert not m.bus.rtc_regs[3]&0x10
        assert call(cpu,0)==0 and m.ram[EQ['J_VALID']]
    records=[m.bus.ee[i*32:(i+1)*32] for i in range(4)]
    assert sorted(int.from_bytes(r[8:12],'little') for r in records)==[3,4,5,6]
    assert all(r[31]==0xA5 and r[30]==0 for r in records)
    checks.append('six successive events rotate across four durable records; ACK only after verified commit')
    print('PASS',checks[-1],flush=True)
    m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(9)
    assert call(cpu,4)==0
    before=bytes(m.bus.ee[:128]);assert m.bus.rtc_regs[3]&0x10
    assert call(cpu,4)==0 and bytes(m.bus.ee[:128])==before
    assert call(cpu,1)==0 and not m.bus.rtc_regs[3]&0x10
    checks.append('pending latched event is deduplicated on retry; distinct post-ACK event gets a new sequence')
    print('PASS',checks[-1],flush=True)
    assert call(cpu,2,param=0,key=b'XX')==6
    flag=m.bus.rtc_regs[3]
    assert call(cpu,2,param=0,key=b'CL')==0 and m.bus.rtc_regs[3]==flag
    assert call(cpu,0)==0 and not m.ram[EQ['J_VALID']]&1
    assert call(cpu,3,key=b'AL')==0 and call(cpu,0)==0 and m.ram[EQ['J_VALID']]==0
    checks.append('CLEAR/CLEAR ALL require intent and remove history without changing time or live latch')
    print('PASS',checks[-1],flush=True)
    factory=bytes(m.bus.ee[0xF0:0xF8]);assert factory==bytes([255]*8) and m.bus.ee[0xFF]==0
    # Failure during payload programming cannot acknowledge the event.
    cpu,f=boot(fail_stop=3);f.bus.rtc_regs[3]|=0x10;f.bus.rtc_regs[0x18:0x20]=event(3)
    result=call(cpu,1);assert result!=0 and f.bus.rtc_regs[3]&0x10 and not any(dev==0x6F for dev,addr,v in f.bus.writes)
    cpu,p=boot();p.bus.ee[0xFF]=0x0C;p.bus.rtc_regs[3]|=0x10;p.bus.rtc_regs[0x18:0x20]=event(4)
    assert call(cpu,1)==6 and p.bus.rtc_regs[3]&0x10 and not p.bus.writes
    foreign=bytes(range(128));cpu,f=boot(foreign,event(5));assert bytes(f.bus.ee[:128])==foreign and f.bus.rtc_regs[3]&0x10
    assert b'RTCC: PF logging failed.' in f.tx if NEW_MESSAGES else b'latch kept' in f.tx
    checks.append('corrupt write/protected EEPROM/foreign layout leave live evidence latched; factory/status untouched')
    print('PASS',checks[-1],flush=True)
    cpu,auto=boot(event=event(8));assert not auto.bus.rtc_regs[3]&0x10
    assert b'RTCC: PF logged, ACK' in auto.tx if NEW_MESSAGES else b'saved to EEPROM' in auto.tx
    saved=bytes(auto.bus.ee[:128]);cpu,again=boot(saved);assert not again.bus.writes and call(cpu,0)==0
    checks.append('real boot saves/commits/ACKs; later boot without event does not write EEPROM')
    print('PASS',checks[-1],flush=True)
    if NEW_MESSAGES:
        cpu,failed=boot(event=event(10),ack_fail=True)
        assert failed.bus.rtc_regs[3]&0x10 and failed.ram[EQ['J_OUTCOME']]==1
        assert failed.bus.ee[31]==0xA5 and failed.bus.ee[30]==0xFF
        assert b'RTCC: PF logged, unverified ACK' in failed.tx and b'PF logging failed.' not in failed.tx
        cpu,marked=boot(event=event(11),fail_stop=7)
        assert not marked.bus.rtc_regs[3]&0x10 and marked.ram[EQ['J_OUTCOME']]==3
        assert marked.bus.ee[30]==0xFF and b'RTCC: PF logged, ACK' in marked.tx
        checks.append('RTCC messages distinguish failed logging, durable save/unverified ACK and verified ACK despite clearance-marker failure')
        print('PASS',checks[-1],flush=True)
        legacy=Memory();legacy.banks[3][4096:8192]=(k.ROOT/'BUILD/v2-rtc-journal/str8n-journal-9000-9fff.bin').read_bytes()
        legacy.bus.rtc_regs[3]|=0x10;legacy.bus.rtc_regs[0x18:0x20]=event(12)
        cpu=k.model.MPU(memory=legacy,pc=0xF004);legacy.cpu=cpu
        k.model.run(cpu,lambda:k.model.waiting(cpu),20000000)
        assert legacy.ram[EQ['J_DESC']]==0 and legacy.bus.rtc_regs[3]&0x10 and not legacy.bus.writes
        assert b'RTCC: PF logging failed.' in legacy.tx
        checks.append('new banner rejects older journal component without writing EEPROM or clearing live evidence')
        print('PASS',checks[-1],flush=True)
    (OUT/'journal-test-results.json').write_text(json.dumps(dict(passed=True,checks=checks,artifacts=k.REPORT['artifacts']),indent=2)+'\n')


if __name__=='__main__':main()
