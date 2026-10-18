"""Fresh CPU/flash rehearsal of the exact two 2609 Windows beta4 plans."""
import argparse,json,hashlib,traceback
from pathlib import Path
import bf1_offline_recovery_model as harness

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plans',required=True,type=Path);a=ap.parse_args()
    receipt=a.plans/'CPU-report.json';assert not receipt.exists()
    preparation=read(a.plans/'preparation.json');assert preparation['passed']
    model,wire,_,_=harness.setup();mf=read(ROOT/'tmp/blg4/manifest.json');model.S=mf['symbols'];model.MANIFEST=mf;checks=[]
    try:
        for name,key in (('stage-beta4','stage_plan_sha256'),('beta4-to-bf1','forward_plan_sha256')):
            folder=a.plans/name;assert sha(folder/'plan.json')==preparation[key]
            plan=read(folder/'plan.json');assert sha(folder/'installer-model-only.s19')==plan['installer_sha256']
            source=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)]
            expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            assert [hashlib.sha256(b).hexdigest() for b in source]==plan['source_sha256']
            tx=plan['transaction'];allowed=set(map(tuple,tx['planned_erase_order']))
            class Memory(model.Memory):
                def __init__(self):
                    super().__init__(source,allowed,{},commit_records={});self.require_maintenance_commit=False
                def mutated(self,kind,address,value):
                    super().mutated(kind,address,value)
                    assert bytes(self.banks[0])==source[0],'B0 changed'
            m=Memory();cells,entry=wire.read_s19(folder/'installer-model-only.s19');assert entry==0x2000
            for address,value in cells.items():m.ram[address]=value
            cpu=model.CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r')
            for n,op in enumerate(tx['operations'][1:]):
                token=f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode()
                model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==model.S['MIG_HALT'])
                assert token in bytes(m.tx),'Installer refused the exact planned source'
                m.tx.clear();m.rx.extend((folder/f'transfer-{n:02d}.bin').read_bytes())
            model.run(cpu,lambda:cpu.pc==model.S['MIG_HALT'])
            assert b'MIGRATION VERIFIED' in m.tx and list(map(bytes,m.banks))==expected
            assert [[b,a>>12] for kind,b,a,v in m.events if kind=='erase']==tx['planned_erase_order']
            (folder/'CPU-events.json').write_text(json.dumps(m.events)+'\n')
            checks.append(dict(name=name,passed=True,fresh_CPU_execution=True,mutation_events=len(m.events),
                plan_sha256=sha(folder/'plan.json'),installer_sha256=plan['installer_sha256'],expected_sha256=plan['expected_sha256']))
            (a.plans/'CPU-progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,flush=True)
        receipt.write_text(json.dumps(dict(passed=True,cases=2,checks=checks,board_access=False,hardware_qualified=False,
            preparation_sha256=sha(a.plans/'preparation.json'),test_sha256=sha(Path(__file__))),indent=2)+'\n')
    except BaseException:
        (a.plans/'CPU-failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise

if __name__=='__main__':main()
