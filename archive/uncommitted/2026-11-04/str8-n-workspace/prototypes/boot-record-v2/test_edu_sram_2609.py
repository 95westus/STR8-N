"""Execute ES1/client/installer opcodes against CPU, NOR and bit-level SPI models."""
import argparse,types
from pathlib import Path
import prepare_edu_sram_2609 as p
from test_b14_core import load_core
from test_b14_raw import start,feed
from edu_sram_model import attach

core,_=load_core();core.GENERATION=p.base.GENERATION
REC=b'REC> ';MENU=b'RAM MINSTALL ? V W I Q> ';EDU=b'EDU RO> '


def machine(build,cpu,banks=None,**opts):
    h=core.Machine(build,cpu,opaque=True)
    h.m.banks[:]=list(map(bytearray,banks or [(build/f'expected-b{n}.bin').read_bytes() for n in range(4)]))
    h.c.pc=0xf004;h.c.sp=255;h.c.p=0x34
    if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
    h.run(lambda:bytes(h.m.tx).endswith(REC));h.port_command(1,b'C1\r')
    attach(h,**opts);h.flash_before=list(map(bytes,h.m.banks));return h


def call(h,address,flags=0x34):
    c=h.c;c.pc=address;c.sp=255;c.p=flags;c.stPushWord(0x1ff)
    h.run(lambda:c.pc==0x200)
    assert c.sp==255 and c.p&0x0c==flags&0x0c and bool(c.p&1)==(c.a==0)
    return c.a


def request(h,address=0,count=1,buffer=0x6100,op=1,reserved=0):
    h.m.ram[0x6000:0x6020]=bytes(32)
    h.m.ram[0x6000:0x6008]=bytes((op,address&255,address>>8&255,address>>16&255,count,buffer&255,buffer>>8,reserved))


def intact(h,before,mode):
    v=h.via
    assert bytes(v.chip.data)==before and v.chip.mode==mode and not v.chip.writes and not v.chip.mode_writes
    assert all(f['device']==0 and f['tx'][0] in (3,5) for f in v.frames)
    assert list(map(bytes,h.m.banks))==h.flash_before and not h.m.events and h.m.bank==3
    assert (v.ddr,v.pcr,v.acr,v.ier)==(0,0,0,0x80)


def provider(build,cpu,passed):
    for mode in (0,0x40,0x80):
        h=machine(build,cpu,mode=mode);v=h.via;before=bytes(v.chip.data);pcr=h.m.ram[0x7fec]
        assert call(h,0x8004)==0 and call(h,0x8007)==0 and not v.reads and not v.writes
        assert h.m.ram[0x600a:0x6010]==bytes((255,0x81,0,0,2,1))
        for address,count,buffer in ((0,1,0x2000),(0xfffe,64,0x6100),(0x10000,64,0x6100),(0x1ffc0,64,0x64c0),(0x1ffff,1,0x64ff)):
            request(h,address,count,buffer);assert call(h,0x800a,0x3c)==0
            assert bytes(h.m.ram[buffer:buffer+count])==before[address:address+count]
            assert h.m.ram[0x6008:0x600b]==bytes((0,count,mode))
            assert h.m.ram[0x7fec]==pcr;intact(h,before,mode)
        frames=v.frames
        assert all(len(f['tx'])==(2 if f['tx'][0]==5 else 5) and f['clocks']==len(f['tx'])*8 for f in frames)
        passed(cpu,f'all-three-modes-boundaries-read-only-{mode:02X}',frames=len(frames))
    h=machine(build,cpu);v=h.via;assert call(h,0x8004)==0
    bad=[dict(address=0x20000),dict(address=0x1ffff,count=2),dict(count=0),dict(count=65),dict(buffer=0x1fff),
         dict(buffer=0x64ff,count=2),dict(buffer=0xffff,count=2),dict(buffer=0xfff0,count=64),dict(buffer=0x6500),
         dict(buffer=0x5ff0,count=64),dict(buffer=0x6000),dict(buffer=0x601f),dict(op=2),dict(reserved=1)]
    for opts in bad:
        request(h,**opts);assert call(h,0x800a)==3,opts
    assert not v.reads and not v.writes
    passed(cpu,'invalid-count-array-wrap-buffer-wrap-request-overlap-write-opcodes',cases=len(bad))
    for field,value in (('ier',0x90),('pcr',0x80),('acr',2),('ddr',4),('ifr',0x18)):
        h=machine(build,cpu);v=h.via;assert call(h,0x8004)==0;setattr(v,field,value);request(h)
        assert call(h,0x800a)==1 and v.port_reads==0 and not v.writes and getattr(v,field)==value
        if field!='ifr':assert call(h,0x800d)==1 and v.port_reads==0 and not v.writes
    h=machine(build,cpu);v=h.via;v.ifr=0x1a;assert call(h,0x8004)==0 and call(h,0x8007)==0
    assert v.ifr==0x1a and v.port_reads==0
    assert call(h,0x800d)==0 and v.ifr==2 and v.port_reads==1 and not v.writes
    request(h);assert call(h,0x800a)==0 and h.m.ram[0x600b]==0x81
    h=machine(build,cpu);v=h.via;v.ifr=0x18;v.clear_flags=False;assert call(h,0x8004)==0
    assert call(h,0x800d)==1 and v.ifr==0x18 and not v.writes
    passed(cpu,'idle-owner-guards-and-explicit-disabled-CB-acknowledgment')
    h=machine(build,cpu);assert call(h,0x8004)==0;h.m.ram[0x6504]=1;request(h)
    req=bytes(h.m.ram[0x6000:0x6020]);state=bytes(h.m.ram[0x6500:0x6600])
    for entry in (0x8004,0x8007,0x800a,0x800d):
        assert call(h,entry)==1 and bytes(h.m.ram[0x6000:0x6020])==req and bytes(h.m.ram[0x6500:0x6600])==state
    assert not h.via.reads and not h.via.writes
    h=machine(build,cpu);request(h);assert call(h,0x800a)==2 and not h.via.reads
    h=machine(build,cpu);h.m.ram[0x7e60]^=1;assert call(h,0x8004)==8 and not h.via.reads
    passed(cpu,'busy-reentry-request-state-preserved-uninitialized-and-ABI-refusal')
    for opts,status in ((dict(present=False),7),(dict(stuck='high'),7),(dict(stuck='low'),0),(dict(mode=0x20),7)):
        h=machine(build,cpu,**opts);assert call(h,0x8004)==0;request(h)
        assert call(h,0x800a)==status and h.m.ram[0x600b]&0x80
        if opts.get('stuck')=='low':assert h.m.ram[0x6100]==0
        if h.via.chip:assert not h.via.chip.writes and not h.via.chip.mode_writes
    passed(cpu,'absent-invalid-mode-refusal-stuck-low-is-explicitly-not-presence-proof')
    h=machine(build,cpu);v=h.via;v.ddr=0xd0;v.latch=0x4f;v.acr=0x80;v.pcr=3;v.ier=0x82
    assert call(h,0x8004)==0;request(h,count=64);assert call(h,0x800a)==0
    assert (v.ddr,v.latch&0xd0,v.acr,v.pcr,v.ier)==(0xd0,0x40,0x80,3,0x82)
    passed(cpu,'unrelated-driven-VIA-latch-DDR-PCR-ACR-IER-preserved')


def client(build,cpu,out,passed):
    h=machine(build,cpu);h.via.ifr=0x1a;sy=h.sy['core/edu-client'];start(h,1);feed(h,1,(build/'payload'/p.CLIENT).read_bytes())
    h.run(lambda:bytes(h.m.tx).endswith(EDU) or h.c.pc==sy['EC_HALT']);assert bytes(h.m.tx).endswith(EDU)
    assert not h.via.reads and not h.via.writes
    for line in (b'?',b'S',b'V'):
        reply=h.port_command(1,line+b'\r',EDU)
        h.run(lambda:not h.m.rx and h.c.pc==h.w['V2W_GETC'])
    assert h.via.ifr==0x1a and h.via.port_reads==0
    assert b'STATUS COMPLETED MODE: 01 ' in h.port_command(1,b'R 00000 01\r',EDU)
    assert not h.via.writes
    h.port_command(1,b'A\r',EDU);assert h.via.ifr==2 and h.via.port_reads==1
    before=bytes(h.via.chip.data)
    for line in (b'R 00000 01',b'R 0FFFE 40',b'R 1FFFF 01'):
        reply=h.port_command(1,line+b'\r',EDU);assert b'STATUS COMPLETED MODE: 00 ' in reply
    intact(h,before,0x40)
    frames=len(h.via.frames)
    for line in (b'W',b'FORMAT',b'EDU OFF',b'R 20000 01',b'R 1FFFF 02',b'R 00000 00',b'R 00000 41',b'R 0000 01',b'R 00000 01 X',b'R Z0000 01'):
        h.port_command(1,line+b'\r',EDU)
    assert len(h.via.frames)==frames
    h.port_command(1,b'Q\r',REC);intact(h,before,0x40)
    (out/f'simulated-{cpu}-client.txt').write_bytes(bytes(h.m.tx));passed(cpu,'RAM-client-help-info-VIA-explicit-ack-reads-invalid-input-Q-REC')
    for fault in ('missing','provider','image','F','RA','worker','vectors'):
        h=machine(build,cpu);start(h,1);feed(h,1,(build/'payload'/p.CLIENT).read_bytes());h.run(lambda:h.c.pc==0x200)
        if fault=='missing':h.m.banks[3][:4096]=b'\xff'*4096
        if fault=='provider':h.m.banks[3][0x201]^=1
        if fault=='image':h.m.ram[sy['EC_HELP_TEXT']]^=1
        if fault=='F':h.m.banks[3][0x7f80]^=1
        if fault=='RA':h.m.ram[0x7e60]^=1
        if fault=='worker':h.m.ram[h.w['V2W_ERASE_RAW']]^=1
        if fault=='vectors':h.m.ram[0x7e20]^=1
        h.c.step();h.run(lambda:h.c.pc==sy['EC_HALT'] or bytes(h.m.tx).endswith(REC))
        assert not h.via.reads and not h.via.writes and not h.m.events
        if fault in ('missing','provider'):assert b'ES1 unavailable' in h.m.tx
        else:assert h.c.pc==sy['EC_HALT']
    passed(cpu,'RAM-client-missing-corrupt-provider-and-five-startup-guard-refusals')


class Install:
    def __init__(self,build,cpu='65c816-e',fault=None,banks=None):
        self.build=build;self.plan=p.verify(build);self.events=[];self.erases=[];self.points=[];self.fault=fault
        self.source=[(build/f'source-b{n}.bin').read_bytes() for n in range(4)]
        self.expected=[(build/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        h=self.h=machine(build,cpu,banks or self.source);self.sy=h.sy['core/ram-mon-install'];start(h,1)
        image=(build/'payload'/p.INSTALLER).read_bytes();feed(h,1,image);h.run(lambda:h.c.pc==0x200)
        if fault and fault.startswith('stale-'):h.m.banks[int(fault[-1])][0]^=1
        if fault=='image':h.m.ram[self.sy['MI_DATA_0']+40]^=1
        if fault=='worker':h.m.ram[0x7800]^=1
        if fault=='timeout':h.m.fault='timeout'
        model=self
        def mutated(memory,kind,address,value):
            assert memory.bank==3 and memory.cpu.pc<0x8000
            assert list(map(bytes,memory.banks[:3]))==model.source[:3]
            assert bytes(memory.banks[3][0x1000:0x4600])==model.source[3][0x1000:0x4600] and bytes(memory.banks[3][0x4700:])==model.source[3][0x4700:]
            assert 0x8000<=address<0x9000 or 0xc600<=address<0xc700
            if kind=='erase':
                model.erases.append(address);assert model.erases==[0x8000]
                latest=max(p.base.snbt_records(memory.banks))[2]
                assert int.from_bytes(latest[8:12],'little')==1021 and int.from_bytes(latest[136:139],'little')==27
                model.points.append(('erase',list(map(bytes,memory.banks))))
                if fault=='erase':memory.banks[3][17]=0
            if kind=='program':
                for i,op in enumerate(model.plan['operations']):
                    if address==op['address']+op['commit']:
                        data=(build/f'action-{i:02d}.bin').read_bytes();off=op['address']-0x8000
                        assert bytes(memory.banks[3][off:off+len(data)])==data
                        model.points.append((f'commit-{address:04X}',list(map(bytes,memory.banks))))
                if fault=='program' and address==0x8080:memory.banks[3][0]^=1
            model.events.append((kind,address));memory.events.append((kind,memory.bank,address,value))
        h.m.mutated=types.MethodType(mutated,h.m);original=h.c.step
        def step():
            c,m=h.c,h.m
            if c.pc==model.sy['JI_HASH_RANGE']:
                lo=int.from_bytes(m.ram[0xe0:0xe2],'little');hi=int.from_bytes(m.ram[0x6208:0x620a],'little') or 65536
                value=p.jb.wire.fnv(bytes(m[a] for a in range(lo,hi)))
                m.ram[0x6200:0x6204]=value.to_bytes(4,'little');m.ram[0xe0:0xe2]=(hi&65535).to_bytes(2,'little')
                c.a=hi>>8&255;c.x=0;c.p=(c.p&~0x83)|3;c.pc=(c.stPopWord()+1)&65535;return c
            return original()
        h.c.step=step
    def run(self,token=MENU):
        h=self.h;n=len(h.m.tx);h.run(lambda:len(h.m.tx)>n and bytes(h.m.tx).endswith(token) or h.c.pc==self.sy['JI_HALT'])
    def send(self,text,token=MENU):self.h.m.rx.extend(text);self.run(token)
    def execute(self):
        self.run()
        if self.fault in ('stale-0','stale-1','stale-2','stale-3','image','worker'):
            assert self.h.c.pc==self.sy['JI_HALT'] and not self.events;return
        self.send(b'W\r');self.send(b'I\r',b'then Enter> ');self.send(b'INSTALL EDU\r')
        if self.fault:assert self.h.c.pc==self.sy['JI_HALT']
        else:
            assert list(map(bytes,self.h.m.banks))==self.expected and self.erases==[0x8000]
            self.send(b'V\r');self.send(b'Q\r',REC)
        assert not self.h.via.writes and not self.h.via.reads


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();build,out=args.build.resolve(),args.out.resolve();info=p.verify(build);assert not out.exists();out.mkdir(parents=True);cases=[]
    def passed(cpu,case,**kw):
        cases.append(dict(passed=True,cpu=cpu,case=case,**kw));p.base.save(out/'progress.json',dict(cases=cases,completed=len(cases)))
        print('PASS',len(cases),cpu,case,flush=True)
    for cpu in ('65c816-e','65c02'):
        provider(build,cpu,passed);client(build,cpu,out,passed)
        model=Install(build,cpu);model.execute();normal=model
        (out/f'simulated-{cpu}-installer.txt').write_bytes(bytes(model.h.m.tx));passed(cpu,'exact-plan-reservation-before-one-erase-commit-last-readback-Q-REC',mutations=len(model.events))
    for fault in ('stale-0','stale-1','stale-2','stale-3','image','worker','erase','program','timeout'):
        model=Install(build,fault=fault);model.execute();passed('65c816-e','installer-refuse-'+fault)
    model=Install(build);model.run()
    for wrong in (b'N\r',b'INSTALL EDU \r',b'\x03'):
        model.send(b'I\r',b'then Enter> ');model.send(wrong);assert not model.events
    model.send(b'Q\r',REC);passed('65c816-e','installer-cancel-wrong-confirmation-no-write')
    for name,banks in normal.points:
        model=Install(build,banks=banks);model.run();assert model.h.c.pc==model.sy['JI_HALT'] and not model.events
    passed('65c02','interrupted-and-completed-state-refuse-original-plan',states=[n for n,b in normal.points])
    assert not p.base.ATTEMPTS
    p.base.save(out/'qualification.json',dict(passed=True,hardware=False,serial_access=False,board_access=False,flash_writes=0,SRAM_writes=0,
        checks=len(cases),cases=cases,build_sha256=p.base.digest(build/'plan.json'),checker_sha256=p.base.digest(__file__),
        peripheral_model_sha256=p.base.digest(p.HERE/'edu_sram_model.py'),BIN_sha256=info['BIN_sha256']))
    print('PASS',len(cases),'groups; no device access',flush=True)


if __name__=='__main__':main()
