"""Exact-plan RAM installer/NOR tests for VX1; no hardware access."""
import argparse,types
from pathlib import Path
import prepare_version_caps_2609 as p
from test_version_caps_2609 import machine,REC,MENU
from test_b14_raw import start,feed


class Install:
    def __init__(self,build,cpu='65c816-e',fault=None,banks=None):
        self.build=Path(build);self.plan=p.verify(self.build);self.fault=fault;self.events=[];self.erases=[];self.points=[];self.prefixes=0
        self.source=[(self.build/f'source-b{n}.bin').read_bytes() for n in range(4)]
        self.expected=[(self.build/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        h=self.h=machine(self.build,cpu,banks=banks or self.source,slot=None)
        self.sy=h.sy['installer'];h.port_command(1,b'C1\r');start(h,1)
        self.image=(self.build/'payload/2609-VERSION-CAPS-RAM.bin').read_bytes()
        feed(h,1,self.image);h.run(lambda:h.c.pc==0x200)
        if fault and fault.startswith('stale-'):h.m.banks[int(fault[-1])][0]^=1
        if fault=='RAM-image':h.m.ram[self.sy['MI_DATA_0']+40]^=1
        if fault=='RAM-worker':h.m.ram[0x7800]^=1
        if fault=='timeout':h.m.fault='timeout'
        model=self
        def mutated(memory,kind,address,value):
            assert memory.bank==3 and memory.cpu.pc<0x8000
            assert list(map(bytes,memory.banks[:3]))==model.source[:3]
            assert bytes(memory.banks[3][:0x2000])==model.source[3][:0x2000] and bytes(memory.banks[3][0x7000:])==model.source[3][0x7000:]
            assert bytes(memory.banks[3][0x4000:0x4300])==model.source[3][0x4000:0x4300] and bytes(memory.banks[3][0x4600:0x6000])==model.source[3][0x4600:0x6000]
            assert any(op['address']<=address<op['address']+op['pages']*256 for op in model.plan['operations'])
            if kind=='erase':
                model.erases.append(address);assert model.erases==[0xe000,0xa000,0xb000][:len(model.erases)]
                latest=max(p.b.snbt_records(memory.banks))[2];index=24+(address>>12)-8
                assert int.from_bytes(latest[64+index*3:67+index*3],'little')==model.plan['counts_before'][index]+1
                model.points.append((f'erase-{address:04X}',list(map(bytes,memory.banks))))
                if fault=='erase-'+f'{address>>12:X}':memory.banks[3][address-0x8000+17]=0
            if kind=='program':
                for n,op in enumerate(model.plan['operations']):
                    if address==op['address']+op['commit']:
                        body=(model.build/f'action-{n:02d}.bin').read_bytes()
                        assert bytes(memory.banks[3][op['address']-0x8000:op['address']-0x8000+len(body)])==body,'Commit before full body'
                        model.points.append((f'commit-{address:04X}',list(map(bytes,memory.banks))))
                if fault=='program-E' and address==0xe080:memory.banks[3][0x6000]^=1
            model.prefixes+=1;model.events.append((kind,address));memory.events.append((kind,memory.bank,address,value))
        h.m.mutated=types.MethodType(mutated,h.m);original=h.c.step
        def step():
            c,m=h.c,h.m
            if c.pc==model.sy['JI_HASH_RANGE']:
                first=int.from_bytes(m.ram[0xe0:0xe2],'little');stop=int.from_bytes(m.ram[0x6208:0x620a],'little') or 65536
                value=p.b.wire.fnv(bytes(m[a] for a in range(first,stop)))
                m.ram[0x6200:0x6204]=value.to_bytes(4,'little');m.ram[0xe0:0xe2]=(stop&65535).to_bytes(2,'little')
                c.a=(stop>>8)&255;c.x=0;c.p=(c.p&~0x83)|3;c.pc=(c.stPopWord()+1)&65535;return c
            return original()
        h.c.step=step
    def run(self,token=MENU):
        h=self.h;n=len(h.m.tx);h.run(lambda:(len(h.m.tx)>n and bytes(h.m.tx).endswith(token)) or h.c.pc==self.sy['JI_HALT'])
    def send(self,body,token=MENU):self.h.m.rx.extend(body);self.run(token)
    def execute(self):
        self.run()
        if self.fault and (self.fault.startswith('stale-') or self.fault.startswith('RAM-')):
            assert self.h.c.pc==self.sy['JI_HALT'] and not self.events;return
        self.send(b'I\r',b'then Enter> ');self.send(b'INSTALL VERSION\r')
        if self.fault:assert self.h.c.pc==self.sy['JI_HALT']
        else:
            assert list(map(bytes,self.h.m.banks))==self.expected
            assert self.erases==[0xe000,0xa000,0xb000]
            assert bytes(self.h.m.ram[0x200:0x200+len(self.image)])==self.image
            self.send(b'V\r');self.send(b'Q\r',REC)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True);checks=[];normal=None
    def passed(case,**kw):
        checks.append(dict(passed=True,case=case,**kw));p.save(out/'progress.json',dict(completed=len(checks),checks=checks));print('PASS',len(checks),case,flush=True)
    for cpu in ('65c816-e','65c02'):
        model=Install(args.build,cpu);model.execute();normal=model
        (out/(cpu+'-installer-console.txt')).write_bytes(bytes(model.h.m.tx))
        passed('exact-install-and-REC-'+cpu,prefixes=model.prefixes,B0_and_F_preserved=True,counts=model.plan['counts_after'])
    for fault in ('stale-0','stale-1','stale-2','stale-3','RAM-image','RAM-worker','erase-E','program-E','erase-A','erase-B','timeout'):
        model=Install(args.build,fault=fault);model.execute();passed('refuse-'+fault,erases=model.erases)
    model=Install(args.build);model.run()
    for wrong in (b'N',b'INSTALL MON',b'INSTALL VERSION ',b'\x03'):
        model.send(b'I\r',b'then Enter> ');model.send(wrong+(b'' if wrong==b'\x03' else b'\r'));assert not model.events
    model.send(b'Q\r',REC);passed('cancel-wrong-confirmation-no-write')
    for name,banks in normal.points:
        model=Install(args.build,banks=banks);model.run();assert model.h.c.pc==model.sy['JI_HALT'] and not model.events
    passed('interrupted-and-completed-states-return-REC-and-refuse-original-plan',states=[name for name,banks in normal.points])
    p.save(out/'proof.json',dict(passed=True,hardware=False,serial_access=False,flashed=False,checks=len(checks),cases=checks,
        plan_sha256=p.b.digest(Path(args.build)/'plan.json'),test_source_sha256=p.b.digest(__file__)))
    print('PASS',len(checks),'installer groups; no board access',flush=True)
