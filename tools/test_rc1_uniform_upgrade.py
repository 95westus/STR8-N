"""Source-matrix and linked RAM-installer qualification, no board access.

The inherited flash model accelerates busy polling and FNV range loops only.
Linked FNV is instruction-checked before acceleration on each CPU. No native
mode, EEPROM/SRAM/RTC writes or electrical/power-failure claims.
"""
import argparse
import ast
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();pkg=a.package.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    sys.path[:0]=[str(pkg),str(pkg/'engine')]
    import uniform_upgrade as u
    import runtime as r
    import legacy_transport as wire
    import install_transport as transport
    manifest=u.package(pkg);checks=[]
    def passed(name,**values):
        checks.append(dict(name=name,passed=True,**values));print('PASS',name,flush=True)
    def refuse(name,fn):
        try:fn()
        except (ValueError,AssertionError):passed(name)
        else:raise AssertionError('Accepted '+name)
    def capture(path,banks,board='MODEL',usb='MODEL-USB'):
        path.mkdir(parents=True);files={}
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):
                name=f'b{n}{suffix}.bin';(path/name).write_bytes(body)
                files[name]=dict(bytes=len(body),sha256=r.sha(body))
        body=bytes(i%251 for i in range(25344))
        for name,data in [('application-ram.bin',body),('restore-application-ram.s19',wire.s19(dict(enumerate(body,0x200)),0x200))]:
            (path/name).write_bytes(data);files[name]=dict(bytes=len(data),sha256=r.sha(data))
        u.legacy.save(path/'capture.json',dict(schema=1,board=board,usb_serial=usb,repeat_verified=True,files=files))
    image=(ROOT/'BUILD/rc1-debugger-v1g/firmware.bin').read_bytes()
    base=[bytearray(b'\xff'*32768)]+[bytearray(image[i:i+32768]) for i in range(0,len(image),32768)]
    base[0][123]=0x42;base[1][0x4a00:0x4a08]=b'USERDATA'
    _,_,row,_=r.latest(base)
    cases=[]
    for name,profile in manifest['profiles'].items():
        for page in (0xa0,0xb0):
            banks=list(map(bytearray,base))
            for s in profile['sectors']:
                start=s['address']-0x8000;banks[s['bank']][start:start+4096]=(pkg/s['file']).read_bytes()
            cfg=bytearray(r.preference(row[8:24],page,profile['generation']));cfg[6]=1;cfg[14:]=wire.config_sum(cfg)
            banks[3][0x4000:0x6000]=b'\xff'*8192;banks[3][0x4000:0x4080]=r.record(cfg,list(range(100,132)),1000)
            banks=list(map(bytes,banks));label=name+f'-{page:x}'
            cap=out/(label+'-capture');capture(cap,banks)
            plan=out/(label+'-plan');info=u.prepare(pkg,cap,plan);u.verify(pkg,plan)
            if name=='v1g':
                assert info['transaction'] is None and info['expected_sha256']==r.hashes(banks)
                assert not (plan/'installer-model-only.s19').exists()
                passed(label+' already-current is exact no-write, no journal/wear/RAM mutation')
            else:
                expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
                assert u.identify(pkg,manifest,expected)=='v1g'
                _,_,last,_=r.latest(expected)
                assert last[8:17]==cfg[:9] and last[21]==cfg[13] and expected[0]==banks[0]
                assert expected[1][0x4a00:0x4a08]==b'USERDATA'
                operations=info['transaction']['operations']
                if name=='v1f':assert len(operations)-1==3 and [o['address'] for o in operations[2:-1]]==[0xa000]
                after=out/(label+'-after');capture(after,expected)
                undo=out/(label+'-restore');rollback=u.restore(pkg,plan,after,undo)
                restored=[(undo/f'expected-b{n}.bin').read_bytes() for n in range(4)]
                assert u.identify(pkg,manifest,restored)==name
                assert r.latest(restored)[2][8:24]==cfg
                assert all(x>=y for x,y in zip(rollback['transaction']['reserved_counts'],info['transaction']['reserved_counts']))
                passed(label+' direct to v1g and immediate-source rollback preserve settings/data/preference/wear')
                cases.append((label,plan,banks))
                # All exact erased, precommit and completed boundaries are admitted.
                # F erased boundaries can require programmer transport on real hardware.
                count=0
                for number,(boundary,state) in enumerate(u.boundary_states(pkg,plan)):
                    cur=out/(label+f'-cut-{number}');capture(cur,state)
                    recovered=out/(label+f'-recover-{number}')
                    receipt=u.recover(pkg,plan,cur,recovered)
                    if receipt['transaction'] is not None:
                        final=[(recovered/f'expected-b{n}.bin').read_bytes() for n in range(4)]
                        assert u.identify(pkg,manifest,final)=='v1g'
                        assert r.latest(final)[2][8:24]==r.latest(expected)[2][8:24]
                        if boundary=='row-2-erased': cases.append((label+'-forward-recovery',recovered,state))
                    else:assert state==expected
                    count+=1
                passed(label+' exact-boundary forward recovery and completed-target no-write',boundaries=count)
    cases_for_upgrade=[item for item in cases if not item[0].endswith('-forward-recovery')]
    # A rollback must retain settings edited since the upgrade, not replay the
    # old snapshot's settings. Only known firmware sectors are restored.
    plan=cases_for_upgrade[-1][1]
    changed=[bytearray((plan/f'expected-b{n}.bin').read_bytes()) for n in range(4)]
    seq,_,last,_=r.latest(changed);cfg=bytearray(last[8:24]);cfg[6]^=1;cfg[14:]=wire.config_sum(cfg)
    counts=[int.from_bytes(last[24+3*i:27+3*i],'little') for i in range(32)]
    free=next(i for i in range(0x4000,0x6000,128) if changed[3][i:i+128]==b'\xff'*128)
    changed[3][free:free+128]=r.record(cfg,counts,seq+1);capture(out/'new-settings',changed)
    restored=u.restore(pkg,plan,out/'new-settings',out/'new-settings-restore')
    after=[(out/'new-settings-restore'/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    assert r.latest(after)[2][8:15]==cfg[:7]
    passed('rollback preserves newer owner settings instead of replaying stale escrow settings')
    original=cases_for_upgrade[-1][2]
    bad=list(map(bytearray,original));bad[1][0x2000]^=1;capture(out/'unknown',bad)
    refuse('unregistered generation50 debugger refused',lambda:u.prepare(pkg,out/'unknown',out/'bad-plan'))
    bad=list(map(bytearray,original));bad[3][0x7000]^=1;capture(out/'mixed',bad)
    refuse('mixed/corrupt system profile refused',lambda:u.prepare(pkg,out/'mixed',out/'mixed-plan'))
    capture(out/'wrong-board',[ (plan/f'expected-b{n}.bin').read_bytes() for n in range(4)],board='OTHER')
    refuse('rollback refuses another board escrow',lambda:u.restore(pkg,plan,out/'wrong-board',out/'wrong-restore'))
    path=plan/'transfer-01.bin';old=path.read_bytes();path.write_bytes(bytes([old[0]^1])+old[1:])
    refuse('transfer tamper refused before serial import',lambda:u.verify(pkg,plan));path.write_bytes(old)
    path=plan/'installer-model-only.s19';old=path.read_bytes();cells,entry=wire.read_s19(path);cells[entry]^=1;path.write_bytes(wire.s19(cells,entry))
    info=r.read(plan/'plan.json');changed=dict(info,installer_sha256=r.sha(path.read_bytes()));u.legacy.save(plan/'plan.json',changed)
    refuse('installer edit with rewritten saved hash refused',lambda:u.verify(pkg,plan));path.write_bytes(old);u.legacy.save(plan/'plan.json',info)
    bad=list(map(bytearray,original));bad[0][7]^=1;capture(out/'unexplained',bad)
    refuse('recovery refuses unexplained full-bank drift',lambda:u.recover(pkg,plan,out/'unexplained',out/'bad-recovery'))

    source=(ROOT/'tools/test_v2_recovery.py').read_text();tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Memory')
    scope={'deque':deque};exec(compile(ast.Module(body=[node],type_ignores=[]),'inherited-flash-model','exec'),scope)
    BaseMemory=scope['Memory'];symbols=r.read(ROOT/'tmp/blg4/manifest.json')['symbols']
    assert r.read(ROOT/'tmp/blg4/manifest.json')['integrated_sha256']==r.read(pkg/'engine/template/manifest.json')['integrated_sha256']
    sys.path[:0]=[str(ROOT/'BUILD/v1.30/local/test-deps'),str(ROOT/'BUILD/test-deps-816')]
    from py65.devices.mpu65c02 import MPU as CPU02
    from py65816.devices.mpu65c816 import MPU as CPU816
    from fetch_rc1_debugger_816_model import MODEL_SHA256
    assert r.sha(Path(sys.modules[CPU816.__module__].__file__).read_bytes())==MODEL_SHA256
    for is816,basecpu in ((False,CPU02),(True,CPU816)):
        cpu_name='65C816 E=1' if is816 else '65C02'
        class Memory(BaseMemory):
            def __init__(self,initial,info):
                super().__init__(initial);self.ram[0x7fec]=0xee;self.info=info;self.id_mode=False;self.erases=[0]*32
                self.allowed={(o['bank'],o['address']&0xf000) for o in info['transaction']['operations']}
            def __getitem__(self,address):
                assert 0<=address<=65535
                if self.id_mode and address in (0x8000,0x8001):return 0xbf if address==0x8000 else 0xb5
                return super().__getitem__(address)
            def __setitem__(self,address,value):
                assert 0<=address<=65535
                if address==0xd555 and value==0x90 and self.unlock==2:self.id_mode=True;self.unlock=0;return
                if self.id_mode and address==0x8000 and value==0xf0:self.id_mode=False;return
                super().__setitem__(address,value)
            def mutated(self,kind,address,value):
                assert (self.bank,address&0xf000) in self.allowed
                if kind=='erase':
                    i=self.bank*8+(address>>12)-8;self.erases[i]+=1
                    _,_,row,_=r.latest(self.banks)
                    assert int.from_bytes(row[24+3*i:27+3*i],'little')>=self.info['transaction']['counts_before'][i]+self.erases[i]
                self.events.append((kind,self.bank,address,value))
        class CPU(basecpu):
            accelerate=True
            def step(self):
                if is816:assert self.mode==1 and (self.dpr,self.dbr,self.pbr)==(0,0,0)
                if not is816 and self.pc==0x2001 and self.memory[self.pc]==0xfb:self.pc+=1;return self
                if self.accelerate and self.pc==symbols['MIG_HASH_RANGE']:
                    first=int.from_bytes(self.memory.ram[0xe0:0xe2],'little');stop=self.memory.ram[0x620c]
                    value=wire.fnv(bytes(self.memory[x] for x in range(first,(stop<<8) if stop else 65536)))
                    self.memory.ram[0x6204:0x6208]=value.to_bytes(4,'little');self.memory.ram[0xe0:0xe2]=bytes([0,stop])
                    self.a,self.x=stop,0;self.p|=self.CARRY|self.ZERO;self.pc=(self.stPopWord()+1)&65535;return self
                return super().step()
        def run(cpu,predicate,limit=20000000):
            for _ in range(limit):
                if predicate():return
                assert cpu.pc<0x8000;cpu.step()
            raise AssertionError(('timeout',hex(cpu.pc),bytes(cpu.memory.tx[-180:])))
        def fresh(plan,banks):
            info=r.read(plan/'plan.json');memory=Memory(banks,info);cells,entry=wire.read_s19(plan/'installer-model-only.s19')
            for address,value in cells.items():memory.ram[address]=value
            cpu=CPU(memory=memory,pc=entry);cpu.pc=entry;memory.cpu=cpu
            if is816:cpu.b=0xa5
            return cpu,memory
        cpu,memory=fresh(cases[0][1],cases[0][2]);sample=bytes(range(256));memory.ram[0x6000:0x6100]=sample
        memory.ram[0xe0:0xe2]=b'\0\x60';memory.ram[0x620c]=0x61
        cpu.pc=symbols['MIG_HASH_RANGE'];cpu.accelerate=False;cpu.stPushWord(0x1ff)
        run(cpu,lambda:cpu.pc==0x200);assert int.from_bytes(memory.ram[0x6204:0x6208],'little')==wire.fnv(sample)
        passed(cpu_name+' linked FNV before acceleration')
        for label,plan,banks in cases:
            cpu,memory=fresh(plan,banks);info=r.read(plan/'plan.json')
            class Endpoint:
                def monitor_load(self,path):assert path==plan/'installer-model-only.s19'
                def send(self,data):memory.rx.extend(data)
                def until(self,token,seconds=45):
                    run(cpu,lambda:token in memory.tx or cpu.pc==symbols['MIG_HALT'])
                    assert token in memory.tx,bytes(memory.tx[-200:]);end=memory.tx.index(token)+len(token)
                    reply=bytes(memory.tx[:end]);del memory.tx[:end];return reply
            with patch.object(transport.time,'sleep',return_value=None):result=transport.execute(Endpoint(),plan)
            run(cpu,lambda:cpu.pc==symbols['MIG_HALT'])
            expected=[(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            assert list(map(bytes,memory.banks))==expected
            assert [[e[1],e[2]>>12] for e in memory.events if e[0]=='erase']==info['transaction']['planned_erase_order']
            if is816:assert cpu.mode==1 and cpu.b==0xa5
            passed(cpu_name+' '+label+' actual packaged transport and RAM installer',transfers=result['transfers_completed'],erases=sum(memory.erases))
        cpu,memory=fresh(cases_for_upgrade[-1][1],cases_for_upgrade[-1][2]);memory.banks[0][0]^=1;memory.rx.extend(b'Y\r')
        run(cpu,lambda:cpu.pc==symbols['MIG_HALT']);assert not memory.events and b'REFUSED/FAILED' in memory.tx
        passed(cpu_name+' stale full-bank source refuses before any flash mutation')
    u.legacy.save(out/'report.json',dict(passed=True,board_access=False,native_debugging=False,RTC_drift_in_release_qualification=False,
        checks=checks,groups=len(checks),actual_installer_executions=2*len(cases),hash_ranges_accelerated=True,electrical_timing_tested=False,
        package_manifest_sha256=r.sha((pkg/'uniform-manifest.json').read_bytes()),test_source_sha256=r.sha(Path(__file__).read_bytes())))


if __name__=='__main__':main()
