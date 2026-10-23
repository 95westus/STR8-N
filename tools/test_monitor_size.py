"""Offline differential monitor/loader/flash/batch and branch-condition tests."""
import argparse
from pathlib import Path
import re,sys
from functools import lru_cache
from prepare_monitor_size import offline,read,protected
from str8build.formats import save,sha,record
ROOT=Path(__file__).resolve().parents[1]

@lru_cache(maxsize=262144)
def crc_state(value,byte):
    hi=(value>>8)^byte;lo=value&255;a=hi;carry=0
    for _ in range(8):
        carry=hi>>7;hi=((hi<<1)|(lo>>7))&255;lo=(lo<<1)&255
        if carry:lo^=0x21;hi^=0x10;a=hi
    return lo|(hi<<8),a,carry
def fast_crc(cpu,memory,address):
    value,a,carry=crc_state(int.from_bytes(memory.ram[address:address+2],'little'),cpu.a)
    memory.ram[address:address+2]=value.to_bytes(2,'little');cpu.a=a;cpu.x=0
    cpu.p=(cpu.p&~0x83)|2|carry;cpu.pc=(cpu.stPopWord()+1)&65535
def crc_model_check(control):
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    from types import SimpleNamespace
    symbols=read(control/'symbols.json')['core/str8n-v2-boot'];entry=symbols['J_CRC_BYTE'];address=symbols['J_CRC']
    count=0
    for CPU in (CPU02,CPU816):
        old=[0]*65536;old[0x8000:]=list((control/'firmware.bin').read_bytes()[0x10000:]);new=list(old)
        real=CPU(memory=old,pc=entry);fast=CPU(memory=new,pc=entry)
        for initial in (0,65535,0x8000,0x7fff,0x1234,0x55aa):
            for byte in range(256):
                for c,mem in ((real,old),(fast,new)):
                    c.pc=entry;c.sp=0xff;c.p=0x7d;c.a=byte;c.x=0x59;c.y=0x63
                    if CPU is CPU816:c.b=0xa5
                    mem[address:address+2]=initial.to_bytes(2,'little');c.stPushWord(0x1ff)
                while real.pc!=0x200:real.step()
                fast_crc(fast,SimpleNamespace(ram=new),address)
                assert (real.pc,real.a,real.x,real.y,real.sp,real.p)==(fast.pc,fast.a,fast.x,fast.y,fast.sp,fast.p)
                assert old[address:address+2]==new[address:address+2]
                if CPU is CPU816:assert real.b==fast.b==0xa5 and real.mode==fast.mode==1
                count+=1
    return count

def branch_cases(control,candidate):
    sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816')]
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    oldsy=read(control/'symbols.json');newsy=read(candidate/'symbols.json');pairs=read(candidate/'monitor-size-build.json')['pairs']
    cases=0
    for CPU in (CPU02,CPU816):
        for slot in ('a0','b0'):
            key='core/monitor-'+slot;oldmem=[0]*65536;newmem=[0]*65536
            oldmem[0x8000:]=list((control/'firmware.bin').read_bytes()[0x10000:])
            newmem[0x8000:]=list((candidate/'firmware.bin').read_bytes()[0x10000:])
            a,b=CPU(memory=oldmem,pc=0x200),CPU(memory=newmem,pc=0x200)
            for p in pairs:
                before=oldsy[key][p['skip']]-5;after=newsy[key][p['skip']]-2
                for flags in range(256):
                    status=flags|0x30 if CPU is CPU816 else flags
                    for c,pc in ((a,before),(b,after)):
                        c.pc=pc;c.p=status;c.a=0x42;c.x=0x37;c.y=0x19;c.sp=0xe5
                        if CPU is CPU816:c.b=0xa5
                    a.step()
                    if a.pc==before+2:a.step()
                    b.step()
                    expected=newsy[key][p['skip']] if a.pc==oldsy[key][p['skip']] else newsy[key][p['dest']]
                    assert b.pc==expected and (a.a,a.x,a.y,a.sp,a.p)==(b.a,b.x,b.y,b.sp,b.p)
                    if CPU is CPU816:assert a.mode==b.mode==1 and a.b==b.b==0xa5
                    cases+=1
    return cases

def differential(control,candidate,out,imports_only=False):
    import test_rc1_source_store as harness
    from installer.flash_model import Memory as NOR
    class Memory(harness.Memory):
        def __init__(self,image,data=None):
            super().__init__(image,data)
            self.unlock=0;self.busy=None;self.programmed=set();self.fault=None;self.usb=True;self.events=[]
        def __getitem__(self,a):
            return NOR.__getitem__(self,a) if isinstance(a,int) and a>=0x8000 else super().__getitem__(a)
        def __setitem__(self,a,v):
            if a>=0x8000:return NOR.__setitem__(self,a,v)
            return super().__setitem__(a,v)
        def mutated(self,kind,address,value):self.events.append((kind,self.bank,address,value))
    class FastHarness(harness.Harness):
        def run(self,*args,**kw):
            if not getattr(self,'crc_hook',False):
                step=self.cpu.step;entry=self.symbols['core/str8n-v2-boot']['J_CRC_BYTE'];address=self.symbols['core/str8n-v2-boot']['J_CRC']
                def accelerated():
                    if self.cpu.pc==entry and self.m.bank==3:fast_crc(self.cpu,self.m,address);return self.cpu
                    return step()
                self.cpu.step=accelerated;self.crc_hook=True
            return super().run(*args,**kw)
    # Full parser rejection and atomicity cases, plus actual simulated journal/NOR writes.
    commands=['?','B4','B0 X','B0','B3','D 0200 020F','D FFFF 0000','D 7EFF 7F01','D 0200 X',
        'M 0200 11 22 33','D 0200 0203','M 0200 44 XX','M 64FF 55 66','M 7F00 00',
        'G','G01FF','G6700','G0200JUNK','G 0200 EXTRA',
        'C','C 00 03 F007 0A\rN','C 00 03 F007 0B\rY','C','P','P A','P B','W',
        'B0','F 8000 AA\rN','F 8000 AA\rY','D 8000 8000','F 8000 FF\rY','D 8000 8000',
        'B1','F A000 11','B3','F F000 11','F A000 11','U Z','P Z','T 4',
        'BATCH D 0200 0201;D 0202 0203','BATCH D 0200;BOGUS','BATCH ;D 0200','?']
    s19good='L\r'+record('1',0x210,b'\x11\x22\x33')+'\r'+record('9',0x210)
    s19bad='L\r'+record('1',0x220,b'\x44\x55')[:-2]+'00\r'
    s19protected='L\r'+record('1',0x64ff,b'\x66\x77')+'\r'+record('9',0x64ff)
    commands += [s19good,'D 0210 0212',s19bad,s19protected,'D 64FF 64FF',
        'D 0200\t0202','D 0200\x01','X'*43,'D 0200 0202\x08\x083','?']
    if imports_only:
        body=bytes((i*17+9)&255 for i in range(4096))
        stream='\r'.join(record('1',0x8000+i,body[i:i+32]) for i in range(0,4096,32))
        commands=['I 8000 8FFF','B0','I 8001 8FFF','I 8000 8FFE','I 8000 7FFF',
            'I 8000 8FFF\rN',
            'I 8000 8FFF\rY\r'+record('1',0x8020,b'\x11')+'\r',
            'I 8000 8FFF\rY\r'+record('1',0x8000,b'\x22')+'\r'+record('9',0x8000),
            'I 8000 8FFF\rY\r'+record('1',0x8000,b'\x33')+'\r\x03',
            'I 8000 8FFF\rY\r'+stream+'\r'+record('9',0x8000),
            'D 8000 801F','D 8FF0 8FFF','B3','W']
    rows=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            for edu in (False,True):
                hs=[]
                for build in (control,candidate):
                    harness.OUT=build;harness.Harness.initial_states.clear();harness.Harness.editor_states.clear()
                    h=FastHarness(cpu,slot,edu=edu,memory_factory=Memory);h.command_limit=25000000;hs.append(h)
                initial=[list(map(bytes,h.m.banks)) for h in hs]
                captures=[]
                for text in commands:
                    save(out/'progress.json',dict(cpu=cpu,slot=slot,edu=edu,command=text,completed_profiles=rows))
                    replies=[h.command(text,'monitor') for h in hs]
                    assert replies[0]==replies[1],(cpu,slot,edu,text,replies)
                    assert hs[0].m.ram[0x200:0x6500]==hs[1].m.ram[0x200:0x6500],('APP changed',text)
                    assert hs[0].m.events==hs[1].m.events,('NOR mutations changed',text)
                    assert hs[0].m.data==hs[1].m.data,('SRAM changed',text)
                    for bank in range(4):
                        deltas=[{i:v for i,v in enumerate(h.m.banks[bank]) if v!=initial[n][bank][i]} for n,h in enumerate(hs)]
                        assert deltas[0]==deltas[1],('Flash state differs',text,bank)
                    captures.append(dict(command=text,reply=replies[1]))
                label=f'{cpu}-{slot}-{int(edu)}';save(out/(label+'.json'),dict(passed=True,commands=captures,simulated_flash_events=len(hs[1].m.events)))
                rows.append(dict(cpu=cpu,slot=slot,edu=edu,commands=len(commands),passed=True))
                print('PASS monitor differential',label,len(commands),'commands',flush=True)
    return rows
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',required=True,type=Path);p.add_argument('--candidate',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--imports-only',action='store_true');a=p.parse_args()
    offline();before=protected();control,candidate,out=a.control.resolve(),a.candidate.resolve(),a.out.resolve()
    assert not out.exists();out.mkdir(parents=True)
    cases=branch_cases(control,candidate);print('PASS exhaustive branch states',cases,flush=True)
    crc_cases=crc_model_check(control);print('PASS test-only unchanged-helper state model',crc_cases,flush=True)
    rows=differential(control,candidate,out,a.imports_only)
    assert before==protected()
    save(out/'report.json',dict(passed=True,board_access=False,serial_network_used=False,imports_only=a.imports_only,branch_state_cases=cases,profiles=rows,firmware_sha256=sha((candidate/'firmware.bin').read_bytes()),test_sha256=sha(Path(__file__).read_bytes()),unchanged_ROM_helper_accelerated=True,helper_state_validation_cases=crc_cases,physical_electrical_timing_tested=False))
if __name__=='__main__':main()
