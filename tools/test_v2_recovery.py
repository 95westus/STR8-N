"""Execute linked recovery firmware in a banked flash/FT245 model.

Checks mutation ordering and power-cut flash states; not electrical timing,
native 816 execution, or a promise that a physical interrupted chip is healthy.
"""
from collections import deque
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import nullcontext

import build_v2_recovery as fw

for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS','PY65_PATH') for p in os.environ.get(key,'').split(os.pathsep) if p),
    *sorted((fw.ROOT/'BUILD').glob('v*/local/test-deps'),reverse=True),
]):
    if (directory/'py65').is_dir(): sys.path.insert(0,str(directory))
from py65.devices.mpu65c02 import MPU as BaseMPU

REPORT = json.loads((fw.OUT/'build.json').read_text())
B, W, V = REPORT['boot'], REPORT['worker'], REPORT['vectors']
M = REPORT['monitors']
EQ = {'active':0x7d30,'config':0x7d80,'record':0x6700,'selected':0xf3}
PASSED = []


class PowerCut(Exception): pass


class Memory:
    def __init__(self, banks=None, usb=True):
        self.ram = bytearray(b'\x5a'*0x8000)
        self.banks = [bytearray(b'\xff'*0x8000) for _ in range(4)]
        if banks is None:
            for suffix,start in [('a000-dfff',0xa000),('e000-efff',0xe000),('f000-ffff',0xf000)]:
                data = (fw.OUT/f'{fw.STEM}-{suffix}.bin').read_bytes()
                self.banks[3][start-0x8000:start-0x8000+len(data)] = data
        else: self.banks = [bytearray(b) for b in banks]
        self.bank = 3
        self.ram[0x7fec] = 0
        self.ram[0x7fe0] = 0x0c
        self.ram[0x7fe3] = 0
        self.rx,self.tx = deque(),bytearray()
        self.usb = usb
        self.cpu = None
        self.unlock = 0
        self.busy = None
        self.events = []
        self.cut_after = None
        self.fault = None
        self.programmed = set()

    def __getitem__(self,a):
        if isinstance(a,slice): return [self[x] for x in range(*a.indices(65536))]
        if a>=0x8000:
            if self.busy:
                assert self.cpu.pc<0x8000, f'ROM fetch while flash busy: {self.cpu.pc:04X}'
                bank,target,value,ticks = self.busy
                assert self.bank==bank
                if ticks:
                    if self.fault!='timeout': self.busy=bank,target,value,ticks-1
                    return value^0x80
                self.busy=None
            return self.banks[self.bank][a-0x8000]
        if a==0x7fe0:
            return (self.ram[a]&~0x23)|(0 if self.rx else 2)|(0 if self.usb else 0x20)
        if a==0x7fe1 and not self.ram[0x7fe3]: return self.rx[0] if self.rx else 0
        return self.ram[a]

    def __setitem__(self,a,v):
        v &= 255
        if a<0x8000:
            old=self.ram[a]; self.ram[a]=v
            if a==0x7fec:
                assert v&0xee in (0xcc,0xce,0xec,0xee), f'Invalid flash-bank PCR mode: {v:02X}'
                self.bank=(0 if v&0x0e==0x0c else 1)|(0 if v&0xe0==0xc0 else 2)
            elif a==0x7fe0 and not old&8 and v&8 and self.rx: self.rx.popleft()
            elif a==0x7fe3 and v==255 and self.ram[0x7fe0]&4: self.tx.append(self.ram[0x7fe1])
            return
        assert self.cpu.pc<0x8000, f'Flash mutation from ROM {self.cpu.pc:04X}'
        if self.unlock==3:
            key=(self.bank,a)
            assert key not in self.programmed, f'Byte reprogrammed before erase: {key}'
            assert self.banks[self.bank][a-0x8000]==255, f'Programming non-erased byte: {key}'
            self.programmed.add(key)
            self.banks[self.bank][a-0x8000]=v
            self.busy=(self.bank,a,v,2)
            self.unlock=0
            self.mutated('program',a,v)
        elif a==0xd555 and v==0xf0:
            self.unlock=0; self.busy=None
        elif self.unlock in (0,4) and a==0xd555 and v==0xaa: self.unlock+=1
        elif self.unlock in (1,5) and a==0xaaaa and v==0x55: self.unlock+=1
        elif self.unlock==2 and a==0xd555 and v in (0xa0,0x80): self.unlock=3 if v==0xa0 else 4
        elif self.unlock==6 and v==0x30:
            base=a&0xf000
            self.banks[self.bank][base-0x8000:base-0x8000+4096]=b'\xff'*4096
            self.programmed={k for k in self.programmed if k[0]!=self.bank or k[1]&0xf000!=base}
            if self.fault=='erase_verify': self.banks[self.bank][base-0x8000+17]=0
            self.busy=(self.bank,a,255,2)
            self.unlock=0
            self.mutated('erase',base,255)
        else: raise AssertionError(f'Bad flash command {self.unlock}: {a:04X}={v:02X}')

    def mutated(self,kind,address,value):
        self.events.append((kind,self.bank,address,value))
        assert not (self.bank==3 and address>=0xf000), 'Fixed F mutated'
        if kind=='erase':
            snapshot=latest(self.banks)
            index=self.bank*8+(address>>12)-8
            assert snapshot and counts(snapshot)[index]>0, 'Erase issued without durable count'
        if self.cut_after==len(self.events): raise PowerCut


class MPU(BaseMPU):
    def step(self):
        if self.memory.fault=='timeout' and self.pc==W['V2W_POLL']:
            self.stPop()
            self.pc=W['V2W_TIMEOUT']
            return
        if self.pc==W['V2W_BOOT_DELAY_OUTER']:
            self.pc=W['V2W_BOOT_DELAY_DONE']; return
        return super().step()


def latest(banks):
    valid=[]
    for offset in range(0x4000,0x6000,128):
        r=bytes(banks[3][offset:offset+128])
        if r[:4]==b'WC\x01\x00' and r[127]==0 and fw.crc(r[:120])==int.from_bytes(r[120:122],'little'):
            valid.append(r)
    return max(valid,key=lambda r:int.from_bytes(r[4:8],'little')) if valid else None


def counts(record): return [int.from_bytes(record[24+i*3:27+i*3],'little') for i in range(32)]


def run(cpu,stop,limit=4000000):
    for _ in range(limit):
        if stop(): return
        cpu.step()
    raise AssertionError(f'Execution limit at B{cpu.memory.bank}:{cpu.pc:04X}; output {bytes(cpu.memory.tx[-150:])!r}')


def waiting(cpu):
    return cpu.pc==W['V2W_GETC_WAIT'] and not cpu.memory.rx and not cpu.memory.ram[0xf9] and not cpu.memory.ram[0xf8]


def boot(banks=None,keys=b'',usb=True):
    mem=Memory(banks,usb); mem.rx.extend(keys)
    cpu=MPU(memory=mem,pc=0xf004); mem.cpu=cpu
    run(cpu,lambda:waiting(cpu))
    return cpu,mem


def command(cpu,line,limit=4000000):
    mem=cpu.memory; start=len(mem.tx); mem.rx.extend(line)
    run(cpu,lambda:waiting(cpu),limit)
    return bytes(mem.tx[start:])


def call(cpu,address,limit=4000000):
    cpu.stPushWord(0x1ff)
    cpu.pc=address
    run(cpu,lambda:cpu.pc==0x200,limit)
    return bool(cpu.p&cpu.CARRY)


def config(enable=0,bank=3,address=0xf007,delay=10,mode=0):
    r=bytearray([1,enable,bank,address&255,address>>8,delay,mode]+[0]*9)
    a=b=0
    for v in r[:14]: a=(a+v)&255; b=(b+a)&255
    r[14:]=bytes([a,b]); return bytes(r)


def test_boot():
    cpu,mem=boot()
    assert mem.ram[EQ['active']]==0xa0 and ('STR8-N '+fw.VERSION).encode() in mem.tx
    assert mem.ram[:0xe0]==b'\x5a'*0xe0
    assert mem.ram[0x200:0x6700]==b'\x5a'*0x6500
    f=bytes(mem.banks[3][0x7000:])
    for page in (0xa0,0xb0):
        banks=[bytes(b) for b in mem.banks]
        banks[3]=bytearray(banks[3]); banks[3][(page<<8)-0x8000+200]^=1
        _,broken=boot(banks)
        assert broken.ram[EQ['active']]==(0xb0 if page==0xa0 else 0xa0)
        assert broken.banks[3][0x7000:]==f
    banks=[bytearray(b) for b in mem.banks]
    for page in (0xa0,0xb0): banks[3][(page<<8)-0x8000+31]=255
    cpu,both=boot(banks)
    assert b'FIXED F RECOVERY' in both.tx and both.ram[EQ['active']]==0
    cpu,forced=boot(keys=b'S')
    assert b'FIXED F RECOVERY' in forced.tx
    command(cpu,b'B\r')
    assert forced.ram[EQ['active']]==0xb0 and ('STR8-N '+fw.VERSION).encode() in forced.tx
    # Invalid settings/journal cannot prevent boot or execute an unsafe target.
    banks=[bytearray(b) for b in mem.banks]; banks[3][0x4000:0x6000]=b'\xff'*8192
    cpu,unknown=boot(banks)
    assert b'JOURNAL INVALID' in command(cpu,b'W\r')
    assert b'Done' not in command(cpu,b'C 0 3 F007 0A\rY\r')
    assert not unknown.events
    assert b'Protected' not in command(cpu,b'F 8000 00\rY\rB3\r')
    assert not unknown.events and unknown.banks[3][0]==255


def test_choice_and_maps():
    # Each selection path gets one dot run before the menu, none after it.
    for keys,active in ((b'',0xa0),(b'\r',0xa0),(b'A\r',0xa0),(b'B\r',0xb0),(b'S',None)):
        _,chosen=boot(keys=keys)
        output=bytes(chosen.tx)
        menu=output.index(b'MONITOR A gen ')
        assert output[:menu].count(b'.')==160
        assert output.startswith(b'\r\n'+b'.'*160+b'\r\n')
        assert all(len(line)<=79 for line in output.splitlines() if line!=b'.'*160)
        assert b'.' not in output[menu:].replace(fw.VERSION.encode(),b'')
        if active is None:assert b'FIXED F RECOVERY' in output
        else:assert chosen.ram[EQ['active']]==active
    cpu,mem=boot(keys=b'B\r')
    assert mem.ram[EQ['active']]==0xb0
    assert b'MONITOR A gen ' in mem.tx and b'MONITOR B gen ' in mem.tx
    assert b'Enter default [3s]' in mem.tx
    assert b'VALID default' in mem.tx
    banks=[bytearray(b) for b in mem.banks]
    banks[3][0x4000:0x4080]=fw.metadata(config(enable=1,bank=1,address=0x9000))
    cpu,explicit=boot(banks,keys=b'A\r')
    assert explicit.ram[EQ['active']]==0xa0 and explicit.bank==3
    banks[3][0x2000+200]^=1
    cpu,fallback=boot(banks,keys=b'AS')
    assert b'MONITOR A INVALID' in fallback.tx and b'FIXED F RECOVERY' in fallback.tx
    cpu,mem=boot();before=[bytes(b) for b in mem.banks]
    output=command(cpu,b'U\r')
    assert b'U A|B' in output and b'REC>' not in output and not mem.events
    # Map utility is a stored program, shared by monitor M and maintenance M.
    import build_bank_maint_recovery as bm
    program,entry=fw.link.read_s19(bm.OUT/(bm.NAME+'.s19'))
    code=bytes(program[a] for a in range(entry,max(program)+1))
    header=b'SR\x01\x3f'+entry.to_bytes(2,'little')+len(code).to_bytes(2,'little')+fw.MAINT_LABEL.encode().ljust(16,b'\x00')
    mem.banks[3][:24+len(code)]=header+code
    data=b'SR\x01\x3f'+(0x1000).to_bytes(2,'little')+(16).to_bytes(2,'little')+b'BETA2'+bytes(11)+bytes(16)
    mem.banks[1][:len(data)]=data
    before=[bytes(b) for b in mem.banks]
    for cmd in (b'M\r',b'M 2\r'):
        output=command(cpu,cmd,8000000)
        assert b'BANK RANGE CONTENTS ACCESS' in output,output
        assert b'B3 8000-' in output and ('SR '+fw.MAINT_LABEL).encode() in output
        assert b'C000-DFFF Config/wear journal' in output
        assert b'writable' in output and b'protected' in output
        assert b'S record; + continued' not in output
        assert b'J/j journal' not in output and b'* active.' not in output
        assert b'ERASE-ATTEMPTS are hexadecimal' not in output
        assert b'Erased does not mean available.' in output
        assert max(map(len,output.splitlines()))<=79,output
        assert b'B3>' in output and b'BM>' not in output
    output=command(cpu,b'M 1\r',8000000)
    assert b'B3 S  +  A* B  J  j  X  R' in output,output
    assert b'S record; + continued' in output and b'* active.' in output
    assert b'E = all FF' not in output
    assert max(map(len,output.splitlines()))<=79,output
    output=command(cpu,b'M 3\r',8000000)
    assert b'B3:D D000-DFFF E 000000' in output,output
    assert b'E = all FF; U = programmed. ERASE-ATTEMPTS are hexadecimal.' in output
    assert b'S record; + continued' not in output and b'* active.' not in output
    assert f"VALID gen {REPORT['generation']:08X} active".encode() in output
    assert max(map(len,output.splitlines()))<=79,output
    assert b'Bad' not in command(cpu,b'M 2200 12 34\r')
    assert mem.ram[0x2200:0x2202]==bytes((0x12,0x34))
    assert ('BANK MAINT '+bm.VERSION).encode() in command(cpu,('R '+fw.MAINT_LABEL+'\r').encode(),8000000)
    for cmd,text in ((b'M\r',b'BANK RANGE'),(b'M 1\r',b'B3 S'),(b'M 3\r',b'ERASE-ATTEMPTS')):
        output=command(cpu,cmd,8000000);assert text in output and b'BM>' in output
        assert (b'S record; + continued' in output)==(cmd==b'M 1\r')
        assert (b'E = all FF' in output)==(cmd==b'M 3\r')
        assert max(map(len,output.splitlines()))<=79,output
    for cmd in (b'T\r',b'T 0-3\r'):
        output=command(cpu,cmd,8000000)
        assert b'B1:8000' in output and b'B3:8000' in output and b'BM>' in output,output
    assert b'Bad hex' in command(cpu,b'T 3-0\r',8000000)
    assert b'BM>' in mem.tx[-50:]
    command(cpu,b'Q\r')
    assert [bytes(b) for b in mem.banks]==before and not mem.events


def test_config_and_rollover():
    cpu,mem=boot(); f=bytes(mem.banks[3][0x7000:]); lower=[bytes(b) for b in mem.banks[:3]]
    command(cpu,b'B1\r')
    assert b'Done' in command(cpu,b'C 0 3 F007 0A\rY\r')
    assert latest(mem.banks)[8:24]==config()
    assert mem.ram[EQ['selected']]==1 and mem.bank==3
    events=len(mem.events)
    command(cpu,b'C 0 3 F007 0A\rY\r')
    assert len(mem.events)==events
    assert b'C 00 03 F007 0A' in command(cpu,b'C\r')
    for delay in range(11,80):
        assert b'Done' in command(cpu,f'C 0 3 F007 {delay:02X}\rY\r'.encode()), delay
    assert latest(mem.banks)[8:24]==config(delay=79)
    actual=[0]*32
    for kind,bank,a,_ in mem.events:
        if kind=='erase': actual[bank*8+(a>>12)-8]+=1
    assert counts(latest(mem.banks))==actual and sum(actual)>=1
    assert mem.banks[3][0x7000:]==f and [bytes(b) for b in mem.banks[:3]]==lower
    assert all((a&0xf000) in (0xc000,0xd000) for _,bank,a,_ in mem.events)
    cpu,restarted=boot(mem.banks)
    assert restarted.ram[0x7d80:0x7d90]==config(delay=79)
    output=command(cpu,b'W\r')
    assert b'B3:F 000000' in output and b'B3:C 000001' in output


def test_counts_and_guards():
    cpu,mem=boot()
    for bank in range(4):
        command(cpu,f'B{bank}\r'.encode())
        yes=b'Y\rB3\r' if bank==3 else b'Y\r'
        assert b'Done' in command(cpu,b'F 8123 00\r'+yes)
        before=len(mem.events)
        assert b'Done' in command(cpu,b'F 8123 00\r'+yes)
        assert len(mem.events)==before
        assert b'Done' in command(cpu,b'F 8123 FF\r'+yes)
        assert counts(latest(mem.banks))[bank*8]==1
    command(cpu,b'B3\r'); before=[bytes(b) for b in mem.banks]
    for page in ('A','B','C','D','E','F'):
        assert b'Protected' in command(cpu,f'F {page}000 00\r'.encode())
        assert b'Protected' in command(cpu,f'I 8000 {page}FFF\r'.encode())
    assert [bytes(b) for b in mem.banks]==before
    # Saturating count and generation limits fail closed.
    for saturated in ('count','sequence'):
        banks=[bytearray(b) for b in mem.banks]
        ct=counts(latest(banks)); ct[0]=0xffffff if saturated=='count' else 1
        banks[3][0x4000:0x6000]=fw.metadata(counts=ct,sequence=0xffffffff if saturated=='sequence' else 1)+b'\xff'*(8192-128)
        cpu,sat=boot(banks); command(cpu,b'B0\r')
        sat.banks[0][0]=0
        command(cpu,b'F 8000 FF\rY\r')
        assert not sat.events and sat.banks[0][0]==0


def newer(page,generation):
    sym=M[f'{page:02x}']; start=(page<<8)+128
    image=(fw.OUT/f'{fw.STEM}-slot-{page:02x}.bin').read_bytes()
    length=sym['V2_END']-start
    return fw.slot_image(image[128:128+length],sym,page,generation)


def update(cpu,page,data):
    mem=cpu.memory; start=len(mem.tx)
    mem.rx.extend(f'U {"A" if page==0xa0 else "B"}\rY\r'.encode()+data)
    run(cpu,lambda:waiting(cpu),6000000)
    return bytes(mem.tx[start:])


def test_updates():
    cpu,mem=boot(); old=bytes(mem.banks[3][0x2000:0x3000]); fixed=bytes(mem.banks[3][0x7000:])
    output=update(cpu,0xb0,newer(0xb0,REPORT['generation']+1))
    assert b'IMAGE COMMITTED' in output and mem.ram[EQ['active']]==0xb0, output[-200:]
    assert mem.banks[3][0x2000:0x3000]==old and mem.banks[3][0x7000:]==fixed
    assert counts(latest(mem.banks))[27]==1
    before=len(mem.events)
    assert b'REFUSED' in update(cpu,0xa0,newer(0xa0,REPORT['generation']+0))
    assert len(mem.events)==before
    cpu,mem=boot()
    bad=bytearray(newer(0xb0,REPORT['generation']+1)); bad[500]^=1
    assert b'REFUSED' in update(cpu,0xb0,bad) and not mem.events
    cpu,mem=boot()
    bad=bytearray(newer(0xb0,REPORT['generation']+1)); bad[20]^=1
    assert b'REFUSED' in update(cpu,0xb0,bad) and not mem.events
    # Both broken images can be rebuilt using F alone, without a monitor.
    banks=[bytearray(b) for b in mem.banks]
    for offset in (0x201f,0x301f): banks[3][offset]=255
    cpu,mem=boot(banks)
    assert b'IMAGE COMMITTED' in update(cpu,0xa0,newer(0xa0,REPORT['generation']+2))
    assert mem.ram[EQ['active']]==0xa0
    # A valid but unwanted newer image can be bypassed manually in fixed F.
    cpu,mem=boot(keys=b'S')
    assert b'IMAGE COMMITTED' in update(cpu,0xb0,newer(0xb0,REPORT['generation']+1))
    cpu,mem=boot(mem.banks,keys=b'S')
    command(cpu,b'A\r'); assert mem.ram[EQ['active']]==0xa0


def test_promotion():
    cpu,mem=boot();command(cpu,b'C 0 3 V 0A\rY\r')
    generation=REPORT['generation']
    assert b'Preferred A' in command(cpu,b'P A\r')
    base=[bytes(b) for b in mem.banks];wear=counts(latest(base))
    # Installing a newer candidate does not replace the proven default.
    assert b'IMAGE COMMITTED' in update(cpu,0xb0,newer(0xb0,generation+1))
    assert mem.ram[EQ['active']]==0xa0
    assert bytes(mem.banks[3][0x2000:0x3000])==base[3][0x2000:0x3000]
    cpu,trial=boot(mem.banks,keys=b'B\r')
    assert trial.ram[EQ['active']]==0xb0
    before=[bytes(b) for b in trial.banks]
    # Even a one-time candidate session cannot overwrite the proven slot.
    assert b'REFUSED' in command(cpu,b'U A\r') and not trial.events
    command(cpu,b'B\r')
    assert b'Bad range' in command(cpu,b'P B extra\r') and not trial.events
    output=command(cpu,b'P B\r')
    assert f'Preferred B {generation+1:08X}'.encode() in output
    assert counts(latest(trial.banks))==counts(latest(before))
    assert not any(event[0]=='erase' for event in trial.events)
    assert trial.banks[3][0x2000:0x4000]==before[3][0x2000:0x4000]
    assert trial.banks[3][0x7000:]==before[3][0x7000:]
    assert boot(trial.banks)[1].ram[EQ['active']]==0xb0
    mutations=len(trial.events)
    unchanged=len(trial.events);command(cpu,b'P B\r');assert len(trial.events)==unchanged
    # C and wear saves retain the exact promoted generation and valid checksum.
    preference=bytes(latest(trial.banks)[15:21])
    command(cpu,b'C 0 3 V 0B\rY\r')
    assert bytes(latest(trial.banks)[15:21])==preference
    assert b'C 00 03 V 0B' in command(cpu,b'C\r')
    # Torn promotion never publishes a partial preference; the last commit wins.
    for cut in (1,mutations//2,mutations-1,mutations):
        cpu,torn=boot(before,keys=b'B\r');torn.cut_after=cut
        try:command(cpu,b'P B\r')
        except PowerCut:pass
        else:raise AssertionError(f'Promotion cut {cut} did not trigger')
        preferred=latest(torn.banks)[16]
        assert preferred in (0xa0,0xb0)
        assert boot(torn.banks)[1].ram[EQ['active']]==preferred
        assert counts(latest(torn.banks))==counts(latest(before))
    # A corrupt promoted image falls back; invalid images cannot be promoted.
    broken=[bytearray(b) for b in trial.banks];broken[3][0x3000+200]^=1
    cpu,fallback=boot(broken);assert fallback.ram[EQ['active']]==0xa0
    assert b'Bad range' in command(cpu,b'P B\r') and not fallback.events
    assert b'Preferred A' in command(cpu,b'P A\r')
    # Binding to generation prevents a replacement inheriting promotion.
    stale=[bytearray(b) for b in base]
    cfg=bytearray(latest(stale)[8:24]);cfg[9:13]=(generation-1).to_bytes(4,'little')
    a=b=0
    for v in cfg[:14]:a=(a+v)&255;b=(b+a)&255
    cfg[14:]=bytes((a,b));stale[3][0x4000:0x6000]=fw.metadata(cfg)+b'\xff'*(8192-128)
    assert boot(stale)[1].ram[EQ['active']]==0xa0


def test_power_cuts():
    cpu,mem=boot(); base=[bytes(b) for b in mem.banks]
    command(cpu,b'C 0 3 F007 0A\rY\r')
    mutations=len(mem.events)
    for cut in (1,10,mutations-1,mutations):
        cpu,m=boot(base); m.cut_after=cut
        try: command(cpu,b'C 0 3 F007 0A\rY\r')
        except PowerCut: pass
        else: raise AssertionError(f'Cut {cut} did not trigger')
        snap=latest(m.banks)
        assert snap[8:24] in (b'\xff'*16,config())
        cpu,reboot=boot(m.banks)
        assert reboot.ram[EQ['active']]==0xa0
        assert b'Done' in command(cpu,b'C 0 3 F007 0B\rY\r')
    cpu,m=boot(base); update(cpu,0xb0,newer(0xb0,REPORT['generation']+1)); n=len(m.events)
    # Before count commit, after count commit, erase, payload and image commit.
    erase=next(i+1 for i,e in enumerate(m.events) if e[0]=='erase')
    for cut in (1,erase-1,erase,erase+10,n-1,n):
        cpu,m=boot(base); m.cut_after=cut
        try: update(cpu,0xb0,newer(0xb0,REPORT['generation']+1))
        except PowerCut: pass
        else: raise AssertionError(f'Cut {cut} did not trigger')
        _,reboot=boot(m.banks)
        assert reboot.ram[EQ['active']] in (0xa0,0xb0)
        assert m.banks[3][0x2000:0x3000]==base[3][0x2000:0x3000]
        assert m.banks[3][0x7000:]==base[3][0x7000:]
        ct=counts(latest(m.banks))[27]
        assert ct>=(1 if cut>=erase else 0)


def test_rollover_failure():
    # Source near capacity and occupied peer: verify pre-erase durability,
    # including own-journal counts and retries after a power interruption.
    m=Memory(); cfg=config()
    m.banks[3][0x4000:0x6000]=b'\xff'*8192
    for i in range(31): m.banks[3][0x4000+i*128:0x4080+i*128]=fw.metadata(cfg,sequence=i+2)
    m.banks[3][0x5000:0x5080]=fw.metadata(cfg,sequence=1)
    cpu,m=boot(m.banks)
    assert b'Done' in command(cpu,b'C 0 3 F007 0B\rY\r')
    assert counts(latest(m.banks))[29]==1
    events=m.events; erase=next(i+1 for i,e in enumerate(events) if e[0]=='erase')
    before=Memory().banks
    before[3][0x4000:0x6000]=b'\xff'*8192
    for i in range(31): before[3][0x4000+i*128:0x4080+i*128]=fw.metadata(cfg,sequence=i+2)
    before[3][0x5000:0x5080]=fw.metadata(cfg,sequence=1)
    for cut in (erase-1,erase,erase+1,len(events)-1):
        cpu,m=boot(before); m.cut_after=cut
        try: command(cpu,b'C 0 3 F007 0B\rY\r')
        except PowerCut: pass
        cpu,reboot=boot(m.banks)
        assert counts(latest(reboot.banks))[29]>=1
        # Full source plus dirty peer must fail closed rather than erase again
        # without somewhere to durably record a further attempt.
        output=command(cpu,b'C 0 3 F007 0C\rY\r')
        if cut==erase:
            assert b'Done' in output
            assert not any(e[0]=='erase' for e in reboot.events)
        elif cut==erase-1 or cut>erase:
            assert b'Done' not in output and not reboot.events


def test_sr_and_abi():
    for slot in ('A','B'):
        cpu,mem=boot(keys=b'S'); command(cpu,f'{slot}\r'.encode())
        mem.ram[0x2000:0x2040]=bytes(range(64))
        assert b'Done' in command(cpu,b'S 1 8123 2000 203F TEST\r')
        mem.ram[0x2000:0x2040]=b'\0'*64
        assert b'Done' in command(cpu,b'R 1 8123 L\r')
        assert mem.ram[0x2000:0x2040]==bytes(range(64))
        assert b'TEST' in command(cpu,b'T 1\r')
        before=len(mem.events)
        assert b'Done' not in command(cpu,b'S 3 A000 2000 203F BAD\r')
        assert len(mem.events)==before
        # Initialized RAM PUTC works with any flash bank selected.
        for bank in range(4):
            mem.bank=bank; mem.ram[0x7fec]=(0xcc,0xce,0xec,0xee)[bank]
            cpu.a=ord('!'); call(cpu,0x7e6d)
            assert mem.bank==bank and mem.tx[-1]==ord('!')
        mem.bank=3; mem.ram[0x7fec]=0xee
        cpu.pc=0x7e67; run(cpu,lambda:waiting(cpu))
        assert mem.ram[EQ['active']]==(0xa0 if slot=='A' else 0xb0)


def test_transfer_and_faults():
    # Cross-sector, maximum-size S19 records retain bytes and transfer state
    # while the count journal saves/restores monitor scratch.
    cpu,mem=boot(); command(cpu,b'B1\r')
    mem.banks[1][:8192]=b'\0'*8192
    data=bytes((i*19)&255 for i in range(8192))
    stream=b'I 8000 9FFF\rY\r'+b''.join((fw.link.record('1',0x8000+i,data[i:i+252])+'\r\n').encode() for i in range(0,len(data),252))
    stream+=(fw.link.record('9',0x8000)+'\r\n').encode()
    assert b'Done' in command(cpu,stream,8000000)
    assert mem.banks[1][:8192]==data
    assert counts(latest(mem.banks))[8:10]==[1,1]
    cpu,mem=boot(); mem.fault='timeout'
    assert b'Done' not in command(cpu,b'C 0 3 F007 0A\rY\r')
    assert latest(mem.banks)[8:24]==b'\xff'*16
    mem.fault=None
    assert b'Done' in command(cpu,b'C 0 3 F007 0A\rY\r')
    # A failed erase and retry each receive a persistent attempt count.
    cpu,mem=boot(); command(cpu,b'B0\r')
    mem.banks[0][0]=0; mem.fault='erase_verify'
    assert b'Done' not in command(cpu,b'F 8000 FF\rY\r')
    assert counts(latest(mem.banks))[0]==1
    mem.fault=None
    assert b'Done' in command(cpu,b'F 8011 FF\rY\r')
    assert counts(latest(mem.banks))[0]==2
    # Headless startup and configured handoffs still use the new config location.
    banks=Memory().banks
    banks[3][0x4000:0x4080]=fw.metadata(config(enable=1,bank=1,address=0x9000))
    mem=Memory(banks,usb=False); cpu=MPU(memory=mem,pc=0xf004); mem.cpu=cpu
    run(cpu,lambda:mem.bank==1 and cpu.pc==0x9000,5000000)


def test_sr_cli():
    # Empty defaults, explicit ranges, bank aliases and malformed ranges.
    cpu,mem=boot()
    for cmd in (b'T\r',b'T 0-3\r',b'T B3\r'):
        assert b'Bad' not in command(cpu,cmd,8000000)
    for cmd in (b'T 3-0\r',b'T 0-4\r',b'T 0-3 EXTRA\r',b'R\r',b'R TEST EXTRA\r'):
        assert b'Bad hex' in command(cpu,cmd,8000000)
    program=bytes((0x4c,0x07,0xf0)) # Return through the resident HOLD entry.
    for bank,address,label in ((1,0x8000,'TEST'),(3,0x8000,'LOCAL')):
        mem.ram[0x2000:0x2003]=program
        assert b'Done' in command(cpu,f'S {bank} {address:04X} 2000 2002 {label}\r'.encode())
    for cmd in (b'T\r',b'T 0-3\r'):
        table=command(cpu,cmd,8000000)
        assert b'B1:8000' in table and b'B3:8000' in table
    table=command(cpu,b'T 0-2\r',8000000)
    assert b'TEST' in table and b'LOCAL' not in table
    for cmd in (b'R TEST L\r',b'R B1 TEST L\r',b'R 1 8000 L\r'):
        mem.ram[0x2000:0x2003]=bytes(3)
        assert b'Done' in command(cpu,cmd,8000000)
        assert mem.ram[0x2000:0x2003]==program
    for cmd in (b'R TEST\r',b'R 1 TEST\r',b'R 1 8000\r'):
        output=command(cpu,cmd,8000000)
        assert ('STR8-N '+fw.VERSION).encode() in output
        assert mem.bank==3
    assert b'SR error 05' in command(cpu,b'R MISSING\r',8000000)
    mem.ram[0x2000:0x2003]=program
    assert b'Done' in command(cpu,b'S 3 8020 2000 2002 TEST\r')
    mem.ram[0x2000:0x2003]=b'xyz'
    assert b'SR error 06' in command(cpu,b'R TEST\r',8000000)
    assert mem.ram[0x2000:0x2003]==b'xyz'
    assert b'Done' in command(cpu,b'R 3 TEST L\r',8000000)
    # Pending records are listed but never selected by name or restored.
    mem.banks[3][0x8020-0x8000+3]=255
    assert b'SR error 05' in command(cpu,b'R 3 TEST L\r',8000000)
    # Scan skips valid payload extents: apparent nested headers are not records.
    mem.banks[1][0x200:0x218]=mem.banks[1][:24]
    mem.banks[1][6:8]=(0x300).to_bytes(2,'little')
    assert command(cpu,b'T 1\r',8000000).count(b'B1:')==1


def test_maintenance():
    import build_bank_maint_recovery as maint
    report=json.loads((maint.OUT/'manifest.json').read_text())
    memory,entry=fw.link.read_s19(maint.OUT/(maint.NAME+'.s19'))
    cpu,mem=boot()
    for a,v in memory.items(): mem.ram[a]=v
    cpu.pc=entry
    run(cpu,lambda:waiting(cpu))
    inventory=command(cpu,b'M\r',8000000)
    assert b'Monitor slot A' in inventory and b'protected' in inventory
    assert b'Config/wear journal [reserved]' in inventory
    for page in ('A','B','C','D','E','F'):
        command(cpu,f'E 3 {page}\r'.encode())
        assert not mem.events
    mem.banks[0][0]=0
    assert b'VERIFIED' in command(cpu,b'E 0 8\rY\r')
    assert counts(latest(mem.banks))[0]==1
    command(cpu,b'Q\r')
    assert ('STR8-N '+fw.VERSION).encode() in mem.tx and mem.ram[EQ['active']]==0xa0


def test_migration():
    import build_v2_recovery_migration as migration
    source=bytearray(b'\xff'*32768)
    source[:8192]=bytes((i*7)&255 for i in range(8192))
    source[0x6000:]= (fw.ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-e000-ffff.bin').read_bytes()
    source[0x7fd0:0x7fe0]=config(delay=22)
    order,payloads,guards,expected=migration.plan(source)
    occupied=bytearray(source); occupied[0x2000]=0
    try: migration.plan(occupied)
    except ValueError: pass
    else: raise AssertionError('Occupied slots accepted without authorization')
    try: migration.plan(source[:-1])
    except ValueError: pass
    else: raise AssertionError('Short readback accepted')
    # Retain fixtures under disposable BUILD for inspection; mode-0700 temp
    # directories can become inaccessible under the Windows workspace sandbox.
    fixture=fw.OUT/('migration-test-'+uuid.uuid4().hex[:12])
    fixture.mkdir()
    with nullcontext(str(fixture)) as directory:
        target=migration.build(source,Path(directory)/'kit')
        manifest=json.loads((target.parent/'manifest.json').read_text())
        ram,entry=fw.link.read_s19(target)
        class MigrationMemory(Memory):
            def mutated(self,kind,address,value): self.events.append((kind,self.bank,address,value))
        mem=MigrationMemory(); mem.banks[3][:]=source
        other=[bytes(b) for b in mem.banks[:3]]
        for a,v in ram.items(): mem.ram[a]=v
        cpu=MPU(memory=mem,pc=entry); mem.cpu=cpu
        mem.rx.extend(b'Y\r'+b''.join(payloads[p] for p in order))
        run(cpu,lambda:cpu.pc==manifest['symbols']['MIG_HALT'],100000000)
        assert b'MIGRATION VERIFIED' in mem.tx,bytes(mem.tx)
        assert mem.banks[3]==expected and [bytes(b) for b in mem.banks[:3]]==other
        assert mem.banks[3][:8192]==source[:8192]
        cpu,reboot=boot(mem.banks)
        assert reboot.ram[0x7d80:0x7d90]==config(delay=22)
        assert counts(latest(reboot.banks))[26:]==[1]*6
        # Changed source after the captured readback refuses before any write.
        mem=MigrationMemory(); mem.banks[3][:]=source; mem.banks[3][0]^=1
        for a,v in ram.items(): mem.ram[a]=v
        cpu=MPU(memory=mem,pc=entry); mem.cpu=cpu; mem.rx.extend(b'Y\r')
        run(cpu,lambda:cpu.pc==manifest['symbols']['MIG_HALT'],10000000)
        assert not mem.events and b'REFUSED/FAILED' in mem.tx
        # A changed source DURING reception is caught by the second guard.
        mem=MigrationMemory(); mem.banks[3][:]=source
        for a,v in ram.items(): mem.ram[a]=v
        cpu=MPU(memory=mem,pc=entry); mem.cpu=cpu; mem.rx.extend(b'Y\r')
        run(cpu,lambda:cpu.pc==manifest['symbols']['MIG_RECEIVE'],10000000)
        mem.banks[3][0]^=1; mem.rx.extend(payloads[order[0]])
        run(cpu,lambda:cpu.pc==manifest['symbols']['MIG_HALT'],10000000)
        assert not mem.events and b'REFUSED/FAILED' in mem.tx


def main():
    (fw.OUT/'test-results.json').unlink(missing_ok=True)
    for test in (test_boot,test_choice_and_maps,test_config_and_rollover,test_counts_and_guards,test_updates,test_promotion,
                 test_power_cuts,test_rollover_failure,test_sr_and_abi,
                 test_transfer_and_faults,test_sr_cli,test_maintenance,test_migration):
        started=time.monotonic(); test(); PASSED.append(test.__name__)
        print(f'PASS: {test.__name__} ({time.monotonic()-started:.1f}s)',flush=True)
    (fw.OUT/'test-results.json').write_text(json.dumps(dict(passed=PASSED,
        artifacts=REPORT['artifacts'],physical_hardware_tested=False,native_816_execution_tested=False),indent=2)+'\n')


if __name__=='__main__': main()
