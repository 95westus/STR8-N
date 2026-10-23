"""Run linked ASM/source store/SRAM manager/DBG1 offline, with ABI-level SRAM.

The CPU executes all editor, packing, CRC, directory, allocation, publication,
restore and debugger instructions. Only the SRAM peripheral transfer at 66A6
is modeled. No serial library, network, ports or hardware writes are used.
"""
import argparse
import binascii
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/os.environ.get('STR8_SOURCE_BUILD','BUILD/current')
sys.path.insert(0, str(ROOT/'BUILD/v1.30/local/test-deps'))
from test_rc1_debugger import s19


def seal(record):
    record[60:62] = binascii.crc_hqx(record[:60], 0xFFFF).to_bytes(2,'big')
    return record


def formatted():
    data = bytearray(b'\xCE'*0x20000)
    data[:0x800] = bytes(0x800)
    data[:8] = b'SS\x01\x08\x08\0\x01\0'
    seal(data);data[63]=0xA5
    return data


def packed(lines):
    return b''.join(struct.pack('<HBB', n, len(text), 0)+text.encode()
                    for n,text in lines)


def capsule(source):
    return b'AS\1\10'+struct.pack('<HH', len(source), binascii.crc_hqx(source, 0xFFFF))+source


class Harness:
    initial_states = {}
    editor_states = {}

    def __init__(self, cpu_name='65c02', slot='A', data=None, edu=True, memory_factory=None):
        self.name=cpu_name;self.slot=slot;self.fresh=True;self.edu=edu
        self.symbols=json.loads((OUT/'symbols.json').read_text())
        self.asm=self.symbols['assembler/asm-app']
        self.ext=json.loads((OUT/'source-symbols.json').read_text())
        self.debug=json.loads((OUT/'debugger-build.json').read_text())['debugger_symbols']
        self.wait_targets=dict(asm=self.asm['READ_CHAR'], debug=self.debug['DBG_READ_CHAR'],
                               monitor=self.symbols['core/str8n-v2-worker']['V2W_GETC_WAIT'])
        self.transcripts=[];self.steps=0
        self.m=(memory_factory or Memory)((OUT/'firmware.bin').read_bytes(), data)
        self.m.edu=edu
        if cpu_name=='65c816-e':
            sys.path.insert(0,str(ROOT/'BUILD/test-deps-816'))
            from py65816.devices.mpu65c816 import MPU
            from fetch_rc1_debugger_816_model import MODEL_SHA256
            assert hashlib.sha256(Path(sys.modules[MPU.__module__].__file__).read_bytes()).hexdigest()==MODEL_SHA256
        else:
            from py65.devices.mpu65c02 import MPU
        self.cpu=MPU(memory=self.m,pc=0x200)
        self.cpu.pc=0x200;self.cpu.p=0x24;self.cpu.sp=255
        self.m.cpu=self.cpu
        if cpu_name=='65c816-e':self.cpu.b=0xA5
        key=(cpu_name,slot,edu,type(self.m).__name__)
        if key in self.initial_states:
            ram,registers,bank=self.initial_states[key]
            self.m.ram[:]=ram;self.m.bank=bank
            for name,value in registers.items():setattr(self.cpu,name,value)
            return
        for file in ('str8n-v2-worker','str8n-v2-vectors'):
            for address,v in s19(OUT/'s/core'/f'{file}.s19').items():self.m.ram[address]=v
        for address,v in s19(OUT/'s/batch/batch-gate.s19').items():self.m.ram[address]=v
        m=self.m
        m.ram[0x7D00]=3;m.ram[0x7D01]=0x16 if cpu_name=='65c816-e' else 2
        m.ram[0x7D30]=0xA0 if slot=='A' else 0xB0
        m.ram[0x7D0C]=255;m.ram[0x7D0A:0x7D0C]=b'\xff\x64'
        m.ram[0xF3]=3
        self.cpu.pc=m.ram[0x7D30]*256+0x48
        self.run(lambda:self.cpu.pc==self.symbols['core/monitor-'+slot.lower()+'0']['V2_RESET'])
        self.discovery()
        self.run(lambda:self.waiting('monitor'))
        names=('pc','sp','p','a','x','y')+(('b','mode','pbr','dbr','dpr') if cpu_name=='65c816-e' else ())
        self.initial_states[key]=(bytes(m.ram),{n:getattr(self.cpu,n) for n in names},m.bank)

    def discovery(self):
        m=self.m
        if self.edu:
            m.ram[0x7D04:0x7D0C]=b'SV\1\x0f\0\x65\xff\x64'
            m.ram[0x7D0C]=255
            m.ram[0x66A2:0x66A6]=b'SM\1\1';m.ram[0x66AE]=1
        else:
            m.ram[0x7D04:0x7D0C]=b'SV\1\0\0\0\xff\x66'
            m.ram[0x7D0C]=0

    def waiting(self, context):
        return (self.cpu.pc==self.wait_targets[context] and not self.m.rx
                and not self.m.ram[0xF9] and not self.m.ram[0xF8])

    def run(self, predicate, limit=3000000):
        trace=deque(maxlen=12)
        for _ in range(limit):
            if predicate():return
            c=self.cpu;m=self.m;self.steps+=1
            trace.append((m.bank,c.pc,c.sp))
            if c.pc==0x66A6:
                assert self.edu, 'SRAM service used on a bare SXB'
                m.transfer(c);continue
            if m.bank==3 and c.pc==0xE014:
                # Fixture device discovery: no RTC/I2C peripherals are modeled
                # here. Re-advertise the SRAM transfer ABI on monitor entry.
                self.discovery()
                c.pc=(c.stPopWord()+1)&65535;continue
            if c.pc==0x7AF8: # Existing monitor's hardware delay only.
                c.pc=(c.stPopWord()+1)&65535;continue
            if self.name=='65c816-e':
                assert c.mode==1 and (c.pbr,c.dbr,c.dpr)==(0,0,0),list(trace)
            op=m[c.pc]
            if self.name=='65c02' and op&15==15: # py65 lacks WDC bit branches.
                z=m[(c.pc+1)&65535];o=m[(c.pc+2)&65535]
                bit=bool(m[z]&(1<<((op>>4)&7)))
                taken=bit if op&128 else not bit
                c.pc=(c.pc+3+(o if o<128 else o-256 if taken else 0))&65535 if taken else (c.pc+3)&65535
            else:
                try:c.step()
                except Exception as exc:raise AssertionError((list(trace),bytes(m.tx[-200:]))) from exc
        raise AssertionError(('timeout',list(trace),bytes(self.m.tx[-300:]),self.m.ram[0x6300:0x6320].hex()))

    def command(self, text, context='asm', contains=None):
        if '--trace' in sys.argv:print('COMMAND',text,context,flush=True)
        start=len(self.m.tx);self.m.rx.extend(text.encode()+b'\r')
        self.run(lambda:self.waiting(context),limit=getattr(self,'command_limit',3000000))
        result=bytes(self.m.tx[start:]).decode('ascii')
        self.transcripts.append(dict(command=text,context=context,output=result))
        if contains is not None:assert contains in result,(text,result)
        assert not self.m.flash_writes
        if self.name=='65c816-e':assert self.cpu.b==0xA5
        return result

    def open(self):
        key=(self.name,self.slot,self.edu,type(self.m).__name__)
        if self.fresh and key in self.editor_states:
            # Reuse a byte-exact CPU/RAM snapshot at a clean ASM prompt for
            # independent fault fixtures. The complete cycle above exercises
            # actual named application launch/re-entry in each CPU/slot pair.
            ram,registers,bank=self.editor_states[key]
            self.m.ram[:]=ram;self.m.bank=bank
            for name,value in registers.items():setattr(self.cpu,name,value)
            self.fresh=False
            return ''
        result=self.command('ASM',contains='STR8-N ASM')
        if self.fresh:
            names=('pc','sp','p','a','x','y')+(('b','mode','pbr','dbr','dpr') if self.name=='65c816-e' else ())
            self.editor_states[key]=(bytes(self.m.ram),{n:getattr(self.cpu,n) for n in names},self.m.bank)
        self.fresh=False
        return result

    def source(self):
        end=int.from_bytes(self.m.ram[0x6300:0x6302],'little')
        return bytes(self.m.ram[0x3300:end])

    def set_source(self, source, dirty=1):
        assert len(source)<=7168
        self.m.ram[0x3300:0x3300+len(source)]=source
        self.m.ram[0x6300:0x6302]=(0x3300+len(source)).to_bytes(2,'little')
        self.m.ram[0x6310]=dirty

    def records(self):
        return [(i,bytes(self.m.data[64+i*64:128+i*64])) for i in range(8)
                if self.m.data[127+i*64]==0xA5]

    def latest(self, name):
        rows=[r for _,r in self.records() if r[16:32]==name.encode().ljust(16,b'\0')]
        r=max(rows,key=lambda r:int.from_bytes(r[10:12],'little'))
        n=int.from_bytes(r[6:8],'little');a=r[14]*256
        return r,bytes(self.m.data[a:a+n])

    def put(self, name, body, load=0x200, entry=0):
        """Inject a sealed test fixture; production saves always use CPU code."""
        rows=self.records();i=next(i for i in range(8) if self.m.data[127+i*64]!=0xA5)
        page=max([8]+[r[14]+(int.from_bytes(r[6:8],'little')+255)//256 for _,r in rows])
        r=bytearray(64);r[:4]=b'SP\1\0'
        struct.pack_into('<HHHHH',r,4,load,len(body),entry,len(rows)+1,binascii.crc_hqx(body,0xFFFF))
        r[14]=page;r[15]=1;r[16:32]=name.encode().ljust(16,b'\0');seal(r);r[63]=0xA5
        self.m.data[page*256:page*256+len(body)]=body
        self.m.data[64+i*64:128+i*64]=r
        return i,page


class Memory:
    def __init__(self, image, data=None):
        self.ram=bytearray(32768);self.bank=3
        self.banks=[bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0,len(image),32768)]
        self.rx=deque();self.tx=bytearray();self.flash_writes=[]
        self.ram[0x7FEC]=0xEE;self.ram[0x7FE0]=0x0C
        self.data=formatted() if data is None else bytearray(data)
        self.present=True;self.fault=None;self.cut=None;self.writes=0;self.transfers=[]

    def __getitem__(self,a):
        if isinstance(a,slice):return [self[i] for i in range(*a.indices(65536))]
        assert 0<=a<=65535,hex(a)
        if a>=0x8000:return self.banks[self.bank][a-0x8000]
        if a==0x7FE0:return self.ram[a]&~0x23 | (0 if self.rx else 2)
        if a==0x7FE1 and not self.ram[0x7FE3]:return self.rx[0] if self.rx else 0
        return self.ram[a]

    def __setitem__(self,a,v):
        assert 0<=a<=65535,hex(a)
        v&=255
        if a>=0x8000:
            self.flash_writes.append((self.bank,a,v));raise AssertionError(self.flash_writes[-1])
        old=self.ram[a];self.ram[a]=v
        if a==0x7FEC:self.bank=(1 if v&2 else 0)|(2 if v&0x20 else 0)
        elif a==0x7FE0 and not old&8 and v&8 and self.rx:self.rx.popleft()
        elif a==0x7FE3 and v==255 and self.ram[0x7FE0]&4:self.tx.append(self.ram[0x7FE1])

    def transfer(self,c):
        r=self.ram[0x6650:0x6660];op=r[0];a=int.from_bytes(r[2:5],'little')
        p=int.from_bytes(r[5:7],'little');n=r[7];status=0;done=0
        self.transfers.append((op,a,p,n))
        if not self.present:status=7
        elif op==0:self.ram[0x665B:0x665F]=bytes((0,0,2,0x81))
        elif op not in (1,2) or not 1<=n<=64 or a+n>0x20000 or p<0x200 or p+n>0x6500:status=9
        elif op==2 and self.ram[0x66AE]:status=6
        else:
            status,limit=self.fault(op,a,p,n) if self.fault else (0,n)
            if op==1:self.ram[p:p+limit]=self.data[a:a+limit]
            else:
                for i in range(limit):
                    self.data[a+i]=self.ram[p+i];self.writes+=1
                    if self.cut:self.cut(self.writes,a+i)
            done=limit
        self.ram[0x6658]=status;self.ram[0x6659]=done
        c.a=status;c.p=(c.p&~1)|(1 if status==0 else 0)
        c.pc=(c.stPopWord()+1)&65535


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cpu',choices=('65c02','65c816-e'),default='65c02');ap.add_argument('--trace',action='store_true')
    a=ap.parse_args();checks=[];transcripts=[]
    harness_digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def passed(name):checks.append(name);print('PASS',name,flush=True)
    program=[(10,'ORG $0200'),(20,'SEI'),(30,'CLD'),(35,'JSR wipe'),(40,'LDX #$01'),
             (50,'BRK $01'),(60,'INX'),(70,'BRK $02'),(80,'JMP $7E67'),
             (90,'wipe: LDA #$00'),(100,'STA $10'),(110,'LDA #$33'),(120,'STA $11'),
             (130,'LDY #$00'),(140,'LDA #$A7'),(150,'page: STA ($10),Y'),(160,'INY'),
             (170,'BNE page'),(180,'INC $11'),(190,'LDX $11'),(200,'CPX #$4F'),
             (210,'BNE page'),(220,'RTS'),(230,'END')]
    for slot in ('A','B'):
        h=Harness(a.cpu,slot);h.open()
        for n,line in program:h.command(f'{n} {line}')
        source=h.source();h.command('SAVE SRAM DEMO',contains='Source saved')
        r,body=h.latest('DEMO');assert body==capsule(source) and r[8:10]==b'\0\0'
        assert h.m.ram[0x6310]==0 and h.m.ram[0x6306]==0
        h.command('ASM',contains='OK ')
        length=int.from_bytes(h.m.ram[0x6302:0x6304],'little');binary=bytes(h.m.ram[0x200:0x200+length])
        h.command('QUIT','monitor');h.command('G 0200','debug',contains='PC=0209')
        assert h.m.ram[0x3300:0x4F00]==b'\xA7'*7168
        h.command('S','debug',contains='X=02')
        h.command('C','debug',contains='PC=020C')
        h.command('X','monitor');h.open()
        # The actual assembled guest has overwritten every source-buffer byte.
        assert h.m.ram[0x3300:0x4F00]==b'\xA7'*7168
        h.command('LOAD SRAM DEMO',contains='Source loaded');assert h.source()==source
        h.command('ASM',contains='OK ');assert bytes(h.m.ram[0x200:0x200+length])==binary
        h.command('40 LDX #$05');h.command('SAVE SRAM DEMO',contains='Source saved')
        assert len(h.records())==2 and h.m.ram[0x6310]==0
        h.command('ASM',contains='OK ');h.command('QUIT','monitor')
        h.command('G 0200','debug',contains='X=05');h.command('N','debug',contains='X=06')
        h.command('C','debug');h.command('C','monitor')
        h.open();h.command('LOAD SRAM DEMO',contains='Source loaded')
        assert b'LDX #$05' in h.source()
        assert h.m.ram[0x66AE]==1 and not h.m.ram[0x6370]
        # A cold fixture retains only external SRAM; all CPU RAM is rebuilt.
        cold=Harness(a.cpu,slot,h.m.data);cold.open();cold.command('LOAD SRAM DEMO',contains='Source loaded')
        assert cold.source()==h.source()
        transcripts+=h.transcripts+cold.transcripts
    passed('MON A/B: edit-save-assemble-BRK-step/next-continue/abort-reopen-load-edit-replace-reassemble-debug; retained SRAM reload after fresh CPU initialization')
    (OUT/f'source-transcripts-{a.cpu}.json').write_text(json.dumps(transcripts,indent=2)+'\n')
    # Empty and exactly full source buffers, plus canonical cached mode bytes.
    h=Harness(a.cpu);h.open();h.command('SAVE SRAM EMPTY',contains='Source saved')
    h.command('LOAD SRAM EMPTY',contains='Source loaded');assert h.source()==b''
    full=packed([(i,';'+'X'*119) for i in range(1,58)]+[(58,';'+'Y'*95)])
    assert len(full)==7168
    h.set_source(full);h.command('SAVE SRAM MAXIMUM',contains='Source saved')
    h.set_source(b'',dirty=0);h.command('LOAD SRAM MAXIMUM',contains='Source loaded');assert h.source()==full
    h.command('ASM',contains='OK ')
    h.set_source(packed([(10,'LDA #1'),(20,'END')]))
    h.command('ASM',contains='OK ');h.command('SAVE SRAM CACHE',contains='Source saved')
    assert h.latest('CACHE')[1]==capsule(packed([(10,'LDA #1'),(20,'END')]))
    passed('empty and exact 7168-byte source round trips; post-assembly mode cache canonicalization')
    h=Harness(a.cpu);h.open();h.set_source(packed(program));h.command('SAVE SRAM KEEP',contains='Source saved')
    h.command('40 LDX #$09');before=h.source();snapshot=bytes(h.m.data)
    h.command('LOAD SRAM KEEP\rNO',contains='Load cancelled');assert h.source()==before
    assert h.m.ram[0x6310]==1 and bytes(h.m.data)==snapshot
    h.command('LOAD SRAM KEEP\rYES',contains='Source loaded');assert h.source()==packed(program)
    for cmd in ('SAVE DISK X','SAVE SRAM','SAVE SRAM A.B','SAVE SRAM ABCDEFGHIJKLMNOPQ','SAVE SRAM X EXTRA'):
        h.command(cmd,contains='Use SAVE/LOAD');assert h.source()==packed(program)
    h.command('SAVE SRAM abcdefghijklmnop',contains='Source saved');h.latest('ABCDEFGHIJKLMNOP')
    passed('dirty-load confirmation, cancellation, explicit provider, syntax/name limits and 16-character case-normalized names')
    # Malformed capsules have valid outer storage checksums, isolating parser guards.
    base=packed([(10,'SEI'),(20,'END')]);good=capsule(base)
    bads=[b'XX'+good[2:],good[:2]+b'\2'+good[3:],good[:3]+b'\7'+good[4:],
          good[:4]+b'\xFF\xFF'+good[6:],good[:6]+bytes([good[6]^1])+good[7:],
          capsule(base[:-1]),capsule(struct.pack('<HBB',0,3,0)+b'SEI'),
          capsule(packed([(20,'SEI'),(10,'END')])),capsule(packed([(10,'SEI'),(10,'END')])),
          capsule(b'\x01\0\x79\0'+b'A'*121),capsule(b'\x01\0\x01\0\x01'),
          capsule(b'\x01\0\x01\1A'),capsule(b'\x01\0\0\0')]
    for i,body in enumerate(bads):
        h=Harness(a.cpu);h.open();h.set_source(packed([(1,';preserve me')]),dirty=0)
        h.put('BAD',body);before=h.source()
        h.command('LOAD SRAM BAD',contains='Invalid source image');assert h.source()==before
    passed(f'{len(bads)} sealed malformed source envelopes/line records refuse without replacing live source')
    # Refuse unsafe saved destinations before copying, even when otherwise valid.
    for load,entry,body in ((0x3300,0,good),(0x6300,0,good),(0x201,0,good),
                            (0x200,0x200,good),(0x200,0,b'1234567'),(0x200,0,bytes(7177))):
        h=Harness(a.cpu);h.open();h.set_source(base,dirty=0);h.put('BAD',body,load,entry)
        before=bytes(h.m.ram[0x200:0x6500]);h.command('LOAD SRAM BAD',contains='Source storage: 44')
        assert h.source()==base
        # Scratch output itself remains untouched by a pre-copy refusal.
        assert h.m.ram[0x200:0x3300]==before[:0x3100]
    passed('checked restore refuses wrong destination, executable entry, short and oversized envelopes before scratch/source copy')
    # Storage error paths preserve source, previous committed version and policy.
    for fault in ('missing','unformatted','directory-full','payload-crc','metadata-crc','partial-load','partial-save'):
        h=Harness(a.cpu);h.open();h.set_source(base);h.command('SAVE SRAM KEEP',contains='Source saved')
        h.set_source(packed([(10,'CLD'),(20,'END')]),dirty=0);before=h.source()
        if fault=='missing':h.m.present=False
        elif fault=='unformatted':h.m.data[:0x800]=bytes(0x800)
        elif fault=='directory-full':
            for i in range(7):h.put(f'P{i}',good)
        elif fault=='payload-crc':
            r,_=h.latest('KEEP');h.m.data[r[14]*256+8]^=1
        elif fault=='metadata-crc':h.m.data[64+h.records()[0][0]*64+4]^=1
        elif fault=='partial-load':
            h.m.fault=lambda op,addr,ptr,n:(7,max(0,n-1)) if op==1 and ptr==0x200 else (0,n)
        elif fault=='partial-save':
            h.m.fault=lambda op,addr,ptr,n:(7,max(0,n-1)) if op==2 and addr>=0x800 else (0,n)
        command='SAVE SRAM KEEP' if fault in ('directory-full','partial-save') else 'LOAD SRAM KEEP'
        result=h.command(command)
        assert 'Source storage:' in result,(fault,result,h.m.transfers[-5:])
        assert h.source()==before and h.m.ram[0x66AE]==1
        assert h.m.ram[0x6370]==0 and h.m.ram[0x6306]==0
        if fault=='partial-save':
            h.m.fault=None;h.command('LOAD SRAM KEEP',contains='Source loaded');assert h.source()==base
    passed('absent/unformatted/full/corrupt/partial storage failures preserve source; failed replacement retains previous version; write protection and bank restored')
    # Current WORK-managed v2 layouts share the existing saved-program store.
    for kib in (16,32,48,64):
        data=formatted();data[2]=2;data[5:7]=(kib*4).to_bytes(2,'little')
        data[8:12]=(1).to_bytes(4,'little');seal(data)
        data[0x240:0x280]=data[:64]
        h=Harness(a.cpu,data=data);h.open();h.set_source(full)
        header=bytes(h.m.data[:64]);reserved=bytes(h.m.data[0x240:0x800]);workspace=bytes(h.m.data[kib*1024:])
        h.command('SAVE SRAM MAX',contains='Source saved')
        h.command('SAVE SRAM MAX',contains='Source storage: 43' if kib==16 else 'Source saved')
        h.set_source(b'',dirty=0);h.command('LOAD SRAM MAX',contains='Source loaded');assert h.source()==full
        assert bytes(h.m.data[:64])==header and bytes(h.m.data[0x240:0x800])==reserved
        assert bytes(h.m.data[kib*1024:])==workspace
    # Verify the new check does not restrict unrelated normal manager restores.
    h=Harness(a.cpu);h.open();h.put('GENERIC',b'ordinary RAM data',0x3000)
    request=bytearray(32);request[0]=2;request[8:24]=b'GENERIC'.ljust(16,b'\0')
    h.m.ram[0x6320:0x6340]=request;h.m[0x7FEC]=0xEC
    h.cpu.a=0x20;h.cpu.x=0x63;h.cpu.stPushWord(0x1FF)
    h.cpu.pc=h.symbols['xip/utilities']['SM_C_API']
    h.run(lambda:h.cpu.pc==0x200)
    assert h.cpu.a==0 and h.cpu.p&1 and h.m.ram[0x3000:0x3011]==b'ordinary RAM data'
    passed('v2 WORK layouts at 16/32/48/64 KiB preserve management/workspace; full-source replacement capacity refusal is safe; ordinary manager restores unchanged')
    # Cut every metadata publication byte plus representative payload boundaries.
    class Cut(Exception):pass
    h=Harness(a.cpu);h.open();h.set_source(base);h.command('SAVE SRAM KEEP',contains='Source saved')
    baseline=bytes(h.m.data);new=packed([(10,'CLD'),(20,'END')]);n=len(capsule(new))
    # Manager writes payload once; reads it back, then writes 64-byte metadata
    # once plus its commit marker. Exact write counts are measured below.
    cuts=[1,n//2,n,*range(n+1,n+66)]
    for cut in cuts:
        h=Harness(a.cpu,data=baseline);h.open();h.set_source(new)
        def interrupt(count,address):
            if count==cut:raise Cut()
        h.m.cut=interrupt
        try:h.command('SAVE SRAM KEEP')
        except Cut:pass
        else:raise AssertionError(('cut not reached',cut,h.m.writes))
        cold=Harness(a.cpu,data=h.m.data);cold.open();cold.command('LOAD SRAM KEEP',contains='Source loaded')
        assert cold.source()==(new if cut==n+65 else base),(cut,cold.source())
    passed(f'{len(cuts)} replacement write-cut/restart cases: previous source before commit, new source after commit')
    report=dict(passed=True,cpu=a.cpu,checks=checks,check_groups=len(checks),
                write_cut_cases=len(cuts),malformed_source_cases=len(bads),board_access=False,
                serial_ports_opened=False,flash_writes=0,peripheral_model='SRAM transfer ABI at 66A6; linked manager executes',
                firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),
                harness_sha256=harness_digest)
    (OUT/f'source-test-{a.cpu}.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS all source-store checks',a.cpu,flush=True)


if __name__=='__main__':main()
