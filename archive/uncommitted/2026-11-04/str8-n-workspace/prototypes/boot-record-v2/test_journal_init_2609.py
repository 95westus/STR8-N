"""Execute the F raw loader and RAM initializer on CPU/NOR models, USB only.

No serial import/device access. Repeated FNV scans may be accelerated after
separate instruction-level tests of this exact linked hash implementation.
Every NOR mutation checks preservation of all non-C/D bytes, including B0.
"""
import argparse
import copy
import json
import types
from pathlib import Path

import prepare_journal_init_2609 as planmod
from installer.common import save
from installer.engine import legacy_transport as wire
from test_b14_core import load_core
from test_b14_raw import start, feed

PROMPT = b'RAM JINIT ? V W I Q> '
REC = b'REC> '
CONFIRM = b'type INIT C/D then Enter> '


class Model:
    def __init__(self, plan, cpu='65c816-e', fault=None, banks=None, accelerate=True):
        self.path=Path(plan)
        self.plan=planmod.verify(plan)
        self.sy=json.loads((self.path/'symbols.json').read_text())
        self.source=[(self.path/f'source-b{n}.bin').read_bytes() for n in range(4)]
        self.expected=[(self.path/f'expected-b{n}.bin').read_bytes() for n in range(4)]
        self.prefixes=0;self.checkpoints=[];self.erases=[];self.commits=[];self.fault=fault
        core,_=load_core();core.GENERATION=planmod.GENERATION
        h=self.h=core.Machine(planmod.TARGET,cpu,opaque=True)
        h.m.banks[:]=list(map(bytearray,banks or self.source));h.m.bank=3
        h.m.tx.clear();h.m.acia_tx.clear();h.m.rx.clear();h.m.acia_rx.clear();h.m.events.clear()
        h.c.pc=0xf004;h.c.p=0x34;h.c.sp=255
        if cpu=='65c816-e':h.c.mode=1;h.c.dpr=h.c.dbr=h.c.pbr=0
        h.run(lambda:bytes(h.m.tx).endswith(REC))
        assert not h.m.events
        start(h,1)
        self.image=(self.path/'payload/2609-journal-init-RAM.bin').read_bytes()
        feed(h,1,self.image);h.run(lambda:h.c.pc==0x200)
        self.app_ram=bytes(h.m.ram[0x200:0x200+len(self.image)])
        self.acia_before=bytes(h.m.acia_tx),list(h.m.acia_writes)
        if fault and fault.startswith('stale-'):h.m.banks[int(fault[-1])][0]^=1
        if fault=='RAM-image':h.m.ram[self.sy['JI_ROW_C']+80]^=1
        if fault=='RAM-worker':h.m.ram[0x7800]^=1
        if fault=='RAM-vectors':h.m.ram[0x7e20]^=1
        if fault=='erase-verify':h.m.fault='erase_verify'
        if fault=='timeout':h.m.fault='timeout'
        model=self

        def mutated(memory,kind,address,value):
            assert memory.cpu.pc<0x8000,'ROM executing while NOR busy'
            assert memory.bank==3 and 0xc000<=address<0xe000,(kind,memory.bank,hex(address))
            assert list(map(bytes,memory.banks[:3]))==model.source[:3],'B0/B1/B2 modified'
            assert bytes(memory.banks[3][:0x4000])==model.source[3][:0x4000],'B3:8-B modified'
            assert bytes(memory.banks[3][0x6000:])==model.source[3][0x6000:],'B3:E/F modified'
            model.prefixes+=1
            if kind=='erase':
                model.erases.append(address)
                assert model.erases==list(planmod.ORDER[:len(model.erases)]),'Unexpected/repeated erase'
                if address==0xc000:
                    records=planmod.snbt_records(memory.banks)
                    assert any(off==0x5000 and row[64:160]==model.expected[3][0x5040:0x50a0] for _,off,row in records),'C erase lacked durable full D reservation'
                model.checkpoints.append(dict(case=f'erase-{address:04X}',banks=list(map(bytes,memory.banks))))
            if kind=='program' and address in (0xd000,0xd0fe,0xd0ff,0xc000,0xc0fe,0xc0ff):
                if address&255==255:
                    assert value==0 and not any(k=='program' and (a&0xf000)==(address&0xf000) and (a&255)==255 for k,_,a,_ in memory.events),'Commit not last/once'
                    model.commits.append(address)
                model.checkpoints.append(dict(case=f'program-{address:04X}',banks=list(map(bytes,memory.banks))))
            if kind=='program' and model.fault=='program-verify' and address==0xd000:memory.banks[3][0x5000]^=1
            if kind=='program' and model.fault=='commit-verify' and address==0xd0ff:memory.banks[3][0x50ff]=255
            if kind=='program' and model.fault=='tail-verify' and address==0xd0ff:memory.banks[3][0x5101]=0
            memory.events.append((kind,memory.bank,address,value))
        h.m.mutated=types.MethodType(mutated,h.m)
        original=h.c.step

        def step():
            c,m=h.c,h.m
            if accelerate and c.pc==model.sy['JI_HASH_RANGE']:
                first=int.from_bytes(m.ram[0xe0:0xe2],'little');stop=int.from_bytes(m.ram[0x6208:0x620a],'little') or 65536
                value=wire.fnv(bytes(m[a] for a in range(first,stop)))
                m.ram[0x6200:0x6204]=value.to_bytes(4,'little');m.ram[0xe0:0xe2]=(stop&65535).to_bytes(2,'little')
                c.a=(stop>>8)&255;c.x=0;c.p=(c.p&~0x83)|3;c.pc=(c.stPopWord()+1)&65535
                return c
            return original()
        h.c.step=step

    def run(self, ending=PROMPT):
        h=self.h
        n=len(h.m.tx)
        h.run(lambda:(len(h.m.tx)>n and bytes(h.m.tx).endswith(ending)) or h.c.pc==self.sy['JI_HALT'])
        return bytes(h.m.tx[n:])

    def command(self, data, ending=PROMPT):
        self.h.m.rx.extend(data)
        return self.run(ending)

    def execute(self):
        h=self.h
        self.run()
        if self.fault and (self.fault.startswith('stale-') or self.fault.startswith('RAM-')):
            assert h.c.pc==self.sy['JI_HALT'] and not h.m.events
            return self.result()
        assert bytes(h.m.tx).endswith(PROMPT) and not h.m.events
        self.command(b'I\r',CONFIRM)
        self.command(b'INIT C/D\r')
        if self.fault:
            assert h.c.pc==self.sy['JI_HALT'] and self.erases==[0xd000]
            assert 0xc000 not in self.erases
        else:
            assert list(map(bytes,h.m.banks))==self.expected
            assert self.erases==[0xd000,0xc000] and self.commits==[0xd0ff,0xc0ff]
            assert planmod.snbt_records(h.m.banks)
            assert bytes(h.m.ram[0x200:0x200+len(self.image)])==self.app_ram,'App self-modified'
            assert self.acia_before==(bytes(h.m.acia_tx),list(h.m.acia_writes)),'Initializer touched ACIA'
        return self.result()

    def result(self):
        return dict(passed=True,cpu=self.h.name,fault=self.fault,erase_attempts=len(self.erases),
                    mutation_prefixes=self.prefixes,every_nonCD_byte_preserved=True,
                    B0_backup_preserved=True,USB_only=True)


def hash_opcodes(plan,cpu):
    h=Model(plan,cpu=cpu,accelerate=False).h
    sy=json.loads((Path(plan)/'symbols.json').read_text())
    for first,body in ((0x6000,bytes(range(256))),(0x60f3,bytes(range(256))+b'odd'),(0xff00,bytes(range(256)))):
        if first>=0x8000:h.m.banks[3][first-0x8000:]=body
        else:h.m.ram[first:first+len(body)]=body
        stop=(first+len(body))&65535
        h.m.ram[0xe0:0xe2]=first.to_bytes(2,'little');h.m.ram[0x6208:0x620a]=stop.to_bytes(2,'little')
        h.c.pc=sy['JI_HASH_RANGE'];h.c.sp=255;h.c.stPushWord(0x1ff)
        h.run(lambda:h.c.pc==0x200)
        assert int.from_bytes(h.m.ram[0x6200:0x6204],'little')==wire.fnv(body)
        assert h.m.ram[0xe0:0xe2]==stop.to_bytes(2,'little')
    return dict(passed=True,case='actual-linked-FNV-opcodes-'+cpu,cases=3,acceleration=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--full-preflight',action='store_true',help='Execute all RAM/four-bank FNV opcodes without hash acceleration')
    args=p.parse_args();out=args.out.resolve();assert not out.exists();out.mkdir(parents=True)
    checks=[]
    def passed(row):
        checks.append(row);save(out/'progress.json',dict(completed=len(checks),checks=checks))
        print('PASS',len(checks),row.get('case',row.get('cpu')),row.get('fault') or '',flush=True)
    for cpu in ('65c816-e','65c02'):passed(hash_opcodes(args.plan,cpu))
    normal=[]
    for cpu in ('65c816-e','65c02'):
        model=Model(args.plan,cpu);row=model.execute();row['case']='D-then-C-initialize-'+cpu;passed(row);normal.append(model)
        transcript=bytes(model.h.m.tx)
        (out/f'transcript-{cpu}.txt').write_bytes(transcript)
        model.command(b'V\r');model.command(b'W\r')
        assert b'F stays 30' in model.h.m.tx
        mutations=len(model.h.m.events)
        model.command(b'I\r');assert len(model.h.m.events)==mutations
        model.command(b'Q\r',REC)
        assert model.h.m.bank==3 and list(map(bytes,model.h.m.banks))==model.expected
        assert model.h.m.ram[model.h.b['BR_VALID']] and model.h.m.ram[0x6707]==ord('S'),'F did not admit recovery record'
        assert model.h.m.ram[0x6708:0x670c]==model.plan['sequences'][1].to_bytes(4,'little')
        passed(dict(passed=True,case='postimage-V-W-no-repeat-I-and-Q-to-F-REC-'+cpu,latest_S_record_admitted=True,MON_absent=True))
    for fault in ('stale-0','stale-1','stale-2','stale-3','RAM-image','RAM-worker','RAM-vectors','erase-verify','program-verify','commit-verify','tail-verify','timeout'):
        passed(Model(args.plan,fault=fault).execute())
    for ending in (b'\r',b'\n',b'\r\n'):
        model=Model(args.plan);model.run()
        for command in (b'?',b'V',b'W',b'NO',b'II',b''):
            model.command(command+ending);assert not model.h.m.events
        for confirmation in (b'N',b'INIT D/E',b'INIT C/D ',b'INIT C/D EXTRA LONG',b'\x03'):
            model.command(b'I'+ending,CONFIRM)
            model.command(confirmation+(b'' if confirmation==b'\x03' else ending))
            assert not model.h.m.events
        model.command(b'Q'+ending,REC);assert not model.h.m.events
        passed(dict(passed=True,case='read-only-commands-cancellation-wrong-confirmation-'+ending.hex(),no_flash_mutation=True))
    partials=[]
    for point in normal[0].checkpoints:
        # The two complete postimages are also refused as stale input by a new
        # invocation. No automatic retry erases/counts over a changed source.
        replay=Model(args.plan,banks=point['banks']);replay.run()
        assert replay.h.c.pc==replay.sy['JI_HALT'] and not replay.h.m.events
        partials.append(dict(case=point['case'],original_plan_refused_before_erase=True))
    passed(dict(passed=True,case='changed-interrupted-and-completed-preimages-refuse-blind-replay',states=partials))
    info=planmod.verify(args.plan)
    for field,value in (('counts',0xffffff),('sequence',0xffffffff)):
        history=dict(board='2609',history_unknown_mask='ffffffff',counts=info['counts_before'].copy(),sequence=info['sequences'][0]-1,config=info['config_before'])
        if field=='counts':history['counts'][28]=value
        else:history[field]=value
        try:planmod.rows(history)
        except ValueError:pass
        else:raise AssertionError('Overflow accepted')
        passed(dict(passed=True,case='host-refuses-'+field+'-overflow'))
    for name in ('payload/2609-journal-init-RAM.bin','source-b0.bin','expected-b3.bin','snapshot-D.bin'):
        folder=out/('tamper-'+Path(name).name);shutil=__import__('shutil');shutil.copytree(args.plan,folder)
        path=folder/name;raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])
        try:planmod.verify(folder)
        except ValueError:pass
        else:raise AssertionError('Host accepted changed '+name)
        passed(dict(passed=True,case='host-refuses-changed-'+name))
    if args.full_preflight:
        model=Model(args.plan,accelerate=False)
        print('RUN all four bank preimage scans with actual CPU instructions',flush=True)
        model.run();assert not model.h.m.events and bytes(model.h.m.tx).endswith(PROMPT)
        passed(dict(passed=True,case='all-RAM-and-four-bank-FNV-opcodes-without-acceleration',CPU='65c816-e',bytes_checked=2734+1000+196+131072))
    save(out/'proof.json',dict(passed=True,hardware=False,board_access=False,serial_access=False,flashed=False,
        checks=len(checks),cases=checks,plan_sha256=planmod.digest(Path(args.plan)/'plan.json'),
        image_sha256=info['image_sha256'],test_source_sha256=planmod.digest(__file__),
        exact_counts=info['counts_reserved'],B0_backup_sha256=info['B0_backup_sha256'],
        limits=['CPU/NOR/USB model only; no board/electrical power-cut qualification',
                'The first D erase has host-reserved accounting; onboard durability starts at the first D commit',
                'No MON installation and no ACIA hardware qualification']))
    print('PASS',len(checks),'offline groups; no ports opened or board writes',flush=True)


if __name__=='__main__':main()
