"""USB/CPU/NOR proof for exact 2609 MON-only and F-only C/D+MON RAM BINs.

No serial/device access. Every NOR mutation checks scope and erase reservation.
The linked hash opcodes are tested; repeated bank scans may then be accelerated.
"""
import argparse,json,types,shutil
from pathlib import Path
import prepare_mon_install_2609 as p
from test_b14_core import load_core
from test_b14_raw import start,feed

MENU=b'RAM MINSTALL ? V W I Q> '
REC=b'REC> '


class Model:
    def __init__(self,folder,cpu='65c816-e',fault=None,banks=None,accelerate=True):
        self.folder=Path(folder);self.plan=p.verify(self.folder);self.sy=p.base.r.read(self.folder/'symbols.json')
        self.source=[(self.folder/f'source-b{n}.bin').read_bytes() for n in range(4)]
        self.expected=[(self.folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        self.image=(self.folder/'payload'/self.plan['BIN']).read_bytes();self.fault=fault
        self.events=[];self.erases=[];self.checkpoints=[];self.prefixes=0;self.commit_addresses=[]
        self.ops=self.plan['operations'];self.original_banks=banks or self.source
        core,_=load_core();core.GENERATION=p.base.GENERATION
        h=self.h=core.Machine(p.TARGET,cpu,opaque=True)
        h.m.banks[:]=list(map(bytearray,self.original_banks));h.m.bank=3;h.m.tx.clear();h.m.rx.clear();h.m.acia_rx.clear();h.m.events.clear()
        h.c.pc=0xf004;h.c.p=0x34;h.c.sp=255
        if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
        h.run(lambda:bytes(h.m.tx).endswith(REC));assert not h.m.events
        h.port_command(1,b'C1\r');start(h,1)
        body=self.image[:-8] if fault=='truncated-RAM' else self.image
        feed(h,1,body);h.run(lambda:h.c.pc==0x200)
        if fault and fault.startswith('stale-'):h.m.banks[int(fault[-1])][0]^=1
        if fault=='RAM-image':h.m.ram[self.sy['MI_DATA_0']+40]^=1
        if fault=='RAM-worker':h.m.ram[0x7800]^=1
        if fault=='RAM-vectors':h.m.ram[0x7e20]^=1
        if fault=='timeout':h.m.fault='timeout'
        self.acia_before=bytes(h.m.acia_tx),list(h.m.acia_writes)
        model=self
        def mutated(memory,kind,address,value):
            assert memory.bank==3 and memory.cpu.pc<0x8000
            assert list(map(bytes,memory.banks[:3]))==model.source[:3],'B0/B1/B2 changed'
            assert bytes(memory.banks[3][:0x2000])==model.source[3][:0x2000],'B3:8/9 changed'
            assert bytes(memory.banks[3][0x6000:])==model.source[3][0x6000:],'B3:E/F changed'
            allowed=[op for op in model.ops if op['address']<=address<op['address']+256*op['pages']]
            assert allowed,'Mutation outside exact actions'
            if model.plan['mode']=='mon-only' and 0xc000<=address<0xe000:
                assert kind=='program' and 0xc100<=address<0xc300,'Existing C/D erased or overwritten'
                assert bytes(memory.banks[3][0x4000:0x4100])==model.source[3][0x4000:0x4100]
                assert bytes(memory.banks[3][0x4300:0x6000])==model.source[3][0x4300:0x6000]
            model.prefixes+=1
            if kind=='erase':
                model.erases.append(address)
                desired=[op['address'] for op in model.ops if op['erase']]
                assert model.erases==desired[:len(model.erases)],'Unplanned/repeated erase'
                rows=p.base.snbt_records(memory.banks)
                if not rows:
                    assert model.plan['mode']=='cd-mon' and address==0xd000 and model.erases==[0xd000],'Erase without journal reservation'
                else:
                    latest=max(rows)[2];index=24+(address>>12)-8
                    count=int.from_bytes(latest[64+3*index:67+3*index],'little')
                    assert count>=model.plan['counts_before'][index]+model.erases.count(address),'Erase lacked durable count'
                model.checkpoints.append(dict(case=f'erase-{address:04X}',banks=list(map(bytes,memory.banks))))
                if model.fault=='erase-'+f'{address>>12:X}':memory.banks[3][address-0x8000+17]=0
            if kind=='program':
                commits=[op for op in model.ops if address==op['address']+op['commit']]
                if commits:
                    op=commits[-1];body=(model.folder/f'action-{model.ops.index(op):02d}.bin').read_bytes()
                    assert value==0 and address not in model.commit_addresses
                    assert bytes(memory.banks[3][op['address']-0x8000:op['address']-0x8000+len(body)])==body,'Commit before complete body'
                    model.commit_addresses.append(address)
                if commits or address in (0xa000,0xa080,0xafff,0xb000,0xb080,0xbfff,0xc100,0xc200,0xd000):
                    model.checkpoints.append(dict(case=f'program-{address:04X}',banks=list(map(bytes,memory.banks))))
                if model.fault=='program-A' and address==0xa080:memory.banks[3][0x2000]^=1
                if model.fault=='commit-A' and address==0xa01f:memory.banks[3][0x201f]=255
                if model.fault=='tail-A' and address==0xa01f:memory.banks[3][0x2fff]=0
            memory.events.append((kind,memory.bank,address,value));model.events.append((kind,memory.bank,address,value))
        h.m.mutated=types.MethodType(mutated,h.m)
        native_step=h.c.step;self.native_step=native_step
        def step():
            c,m=h.c,h.m
            if accelerate and c.pc==model.sy['JI_HASH_RANGE']:
                first=int.from_bytes(m.ram[0xe0:0xe2],'little');stop=int.from_bytes(m.ram[0x6208:0x620a],'little') or 65536
                digest=p.base.wire.fnv(bytes(m[a] for a in range(first,stop)))
                m.ram[0x6200:0x6204]=digest.to_bytes(4,'little');m.ram[0xe0:0xe2]=(stop&65535).to_bytes(2,'little')
                c.a=(stop>>8)&255;c.x=0;c.p=(c.p&~0x83)|3;c.pc=(c.stPopWord()+1)&65535;return c
            return native_step()
        h.c.step=step

    def run(self,ending=MENU,limit=16_000_000):
        h=self.h;n=len(h.m.tx)
        h.run(lambda:(len(h.m.tx)>n and bytes(h.m.tx).endswith(ending)) or h.c.pc==self.sy['JI_HALT'],limit=limit)
        return bytes(h.m.tx[n:])

    def command(self,body,ending=MENU):
        self.h.m.rx.extend(body);return self.run(ending)

    def install(self):
        self.run()
        guard_fault=self.fault and (self.fault.startswith('stale-') or self.fault.startswith('RAM-') or self.fault=='truncated-RAM')
        if guard_fault:
            assert self.h.c.pc==self.sy['JI_HALT'] and not self.events
            return self.result()
        assert not self.events and bytes(self.h.m.tx).endswith(MENU)
        self.command(b'I\r',b'then Enter> ')
        self.command(self.plan['confirmation'].encode()+b'\r')
        if self.fault:
            assert self.h.c.pc==self.sy['JI_HALT']
            if self.fault in ('program-A','commit-A','tail-A'):assert 0xb000 not in self.erases
        else:
            assert list(map(bytes,self.h.m.banks))==self.expected
            assert self.erases==[op['address'] for op in self.ops if op['erase']]
            assert self.commit_addresses==[op['address']+op['commit'] for op in self.ops]
            assert bytes(self.h.m.ram[0x200:0x200+len(self.image)])==self.image,'Installer modified itself'
            assert self.acia_before==(bytes(self.h.m.acia_tx),list(self.h.m.acia_writes))
        return self.result()

    def result(self):
        return dict(passed=True,mode=self.plan['mode'],cpu=self.h.name,fault=self.fault,
                    erase_order=[f'{a:04X}' for a in self.erases],mutation_prefixes=self.prefixes,
                    B0_B1_B2_B3_8_9_E_F_preserved=True)


def hash_instructions(folder,cpu):
    model=Model(folder,cpu,accelerate=False);h=model.h
    for address,body in ((0x6000,bytes(range(256))),(0x60f3,b'boundary'+bytes(range(256)))):
        h.m.ram[address:address+len(body)]=body;stop=address+len(body)
        h.m.ram[0xe0:0xe2]=address.to_bytes(2,'little');h.m.ram[0x6208:0x620a]=stop.to_bytes(2,'little')
        h.c.pc=model.sy['JI_HASH_RANGE'];h.c.sp=255;h.c.stPushWord(0x1ff);h.run(lambda:h.c.pc==0x200)
        assert int.from_bytes(h.m.ram[0x6200:0x6204],'little')==p.base.wire.fnv(body)
    return dict(passed=True,case='actual-linked-FNV-'+cpu,mode=model.plan['mode'])


def boot_monitors(model):
    h=model.h;model.command(b'Q\r',REC)
    assert h.m.ram[h.b['BR_VALID']] and h.m.ram[0x6707]==ord('S')
    mutations=len(h.m.events)
    # Remove this app's shortcut before entering unrelated MON instructions.
    h.c.step=model.native_step
    for target in ('A','B'):
        h.port_command(1,b'C1\r')
        out=h.port_command(1,target.encode()+b'\r',b'B3> ')
        assert b'STR8-N 2.0proto' in out
        assert h.m.ram[0x7d30]==(0xa0 if target=='A' else 0xb0),'Wrong MON selected'
        h.port_command(1,b'J3\r',b'S=Recovery  A/B=Monitor  0-3=Bank\r\n')
        h.port_command(1,b'S',REC)
    assert len(h.m.events)==mutations and list(map(bytes,h.m.banks))==model.expected
    return dict(passed=True,case='both-MON-entry-and-J3-S-return-to-REC',mode=model.plan['mode'],cpu=h.name,no_flash_mutation=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plans',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();plans=args.plans.resolve();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    checks=[];normal={}
    def passed(row):
        checks.append(row);save=p.save;save(out/'progress.json',dict(completed=len(checks),checks=checks))
        print('PASS',len(checks),row.get('case','installer'),row.get('mode',''),row.get('cpu',''),row.get('fault') or '',flush=True)
    for mode in ('mon-only','cd-mon'):
        folder=plans/mode
        for cpu in ('65c816-e','65c02'):
            passed(hash_instructions(folder,cpu))
            model=Model(folder,cpu);passed(model.install());normal[(mode,cpu)]=model
            (out/f'{mode}-{cpu}-transcript.txt').write_bytes(bytes(model.h.m.tx))
            model.command(b'V\r');model.command(b'W\r');count=len(model.events)
            model.command(b'I\r');assert len(model.events)==count
            passed(boot_monitors(model))
        for fault in ('stale-0','stale-1','stale-2','stale-3','RAM-image','RAM-worker','RAM-vectors','truncated-RAM','erase-A','program-A','tail-A'):
            passed(Model(folder,fault=fault).install())
        if mode=='mon-only':passed(Model(folder,fault='commit-A').install())
        else:
            passed(Model(folder,fault='erase-D').install())
            passed(Model(folder,fault='erase-C').install())
        model=Model(folder);model.run()
        for ending in (b'\r',b'\n',b'\r\n'):
            for line in (b'?',b'V',b'W',b'NOT I'):
                model.command(line+ending);assert not model.events
            for wrong in (b'N',b'INSTALL MON ',b'INSTALL D/E MON',b'INSTALL CD MON X',b'\x03'):
                model.command(b'I'+ending,b'then Enter> ')
                model.command(wrong+(b'' if wrong==b'\x03' else ending));assert not model.events
        model.command(b'Q\r',REC)
        passed(dict(passed=True,case='read-only-commands-cancel-and-wrong-confirmations',mode=mode,no_flash_mutation=True))
        model=Model(folder);model.run();model.h.m.banks[0][0]^=1
        model.command(b'I\r',b'then Enter> ');model.command(model.plan['confirmation'].encode()+b'\r')
        assert model.h.c.pc==model.sy['JI_HALT'] and not model.events
        passed(dict(passed=True,case='preimages-rechecked-after-confirmation',mode=mode))
        checkpoints=normal[(mode,'65c816-e')].checkpoints
        for point in checkpoints:
            replay=Model(folder,banks=point['banks']);replay.run()
            assert replay.h.c.pc==replay.sy['JI_HALT'] and not replay.events
        passed(dict(passed=True,case='interrupted-and-completed-states-boot-REC-and-refuse-blind-replay',mode=mode,states=[p['case'] for p in checkpoints]))
        other=normal[('mon-only','65c816-e')].source if mode=='cd-mon' else [(plans/'cd-mon'/f'source-b{n}.bin').read_bytes() for n in range(4)]
        wrong=Model(folder,banks=other);wrong.run();assert wrong.h.c.pc==wrong.sy['JI_HALT'] and not wrong.events
        passed(dict(passed=True,case='wrong-starting-route-refused',mode=mode))
        for name in ('payload/'+p.base.r.read(folder/'plan.json')['BIN'],'source-b0.bin','action-00.bin','expected-b3.bin'):
            copy=out/(mode+'-tamper-'+Path(name).name);shutil.copytree(folder,copy)
            path=copy/name;raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])
            try:p.verify(copy)
            except ValueError:pass
            else:raise AssertionError('Host accepted changed '+name)
        passed(dict(passed=True,case='host-refuses-changed-payload-source-action-and-postimage',mode=mode,cases=4))
    assert normal[('mon-only','65c816-e')].expected==normal[('cd-mon','65c816-e')].expected
    passed(dict(passed=True,case='both-routes-produce-identical-final-banks-counts-and-config'))
    save=p.save
    save(out/'proof.json',dict(passed=True,hardware=False,serial_access=False,board_access=False,flashed=False,checks=len(checks),cases=checks,
        plans={m:p.base.digest(plans/m/'plan.json') for m in ('mon-only','cd-mon')},
        BIN_sha256={m:p.base.r.read(plans/m/'plan.json')['BIN_sha256'] for m in ('mon-only','cd-mon')},
        test_source_sha256=p.base.digest(__file__),limits=['CPU/NOR model only; no board or electrical power-cut qualification','USB only; ACIA not board-tested']))
    print('PASS',len(checks),'offline groups; stopped before hardware',flush=True)


if __name__=='__main__':main()
