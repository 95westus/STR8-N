"""Fresh CPU/flash execution of the five exact owner empty-bank fixture plans."""
import argparse,json,hashlib,os,traceback
from pathlib import Path
import bf1_offline_recovery_model as harness
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/qualification/bf1-empty-bank-tests-2026-10-18-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--plans',type=Path,default=OUT);args=parser.parse_args();OUT=args.plans.resolve()
    assert OUT.is_relative_to(ROOT/'output/qualification')
    prep=read(OUT/'preparation.json');assert prep['passed'] and not (OUT/'CPU-report.json').exists()
    model,wire,_,_=harness.setup();mf=read(ROOT/'tmp/blg4/manifest.json');model.S=mf['symbols'];model.MANIFEST=mf;checks=[]
    (OUT/'CPU-job.json').write_text(json.dumps(dict(pid=os.getpid(),state='running')))
    try:
        for name,digest in prep['plans'].items():
            folder=OUT/name;assert sha(folder/'plan.json')==digest;plan=read(folder/'plan.json');tx=plan['transaction']
            source=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)];expected=[(folder/f'expected-b{n}.bin').read_bytes() for n in range(4)]
            allowed=set(map(tuple,tx['planned_erase_order']))
            class Memory(model.Memory):
                def __init__(self):
                    super().__init__(source,allowed,{},commit_records={});self.require_maintenance_commit=False
                def mutated(self,kind,address,value):
                    super().mutated(kind,address,value)
                    if name!='2604-empty-B0':assert bytes(self.banks[0])==source[0]
            memory=Memory();cells,entry=wire.read_s19(folder/'installer-model-only.s19')
            for address,value in cells.items():memory.ram[address]=value
            # The 816 prologue was separately tested on hardware; execute the
            # complete shared E=1 worker here, not a native-mode CPU simulation.
            cpu=model.CPU(memory=memory,pc=0x2000);memory.cpu=cpu;memory.rx.extend(b'Y\r')
            ops=tx['operations'] if name=='2609-WDC-to-full-bf1' else tx['operations'][1:]
            for n,op in enumerate(ops):
                token=f"SEND 4096 BYTES FOR B{op['bank']}:{op['address']>>12:X}\r\n".encode()
                model.run(cpu,lambda:token in bytes(memory.tx) or cpu.pc==model.S['MIG_HALT'])
                assert token in bytes(memory.tx),'Exact source refused: '+name
                memory.tx.clear();memory.rx.extend((folder/f'transfer-{n:02d}.bin').read_bytes())
            model.run(cpu,lambda:cpu.pc==model.S['MIG_HALT'])
            assert b'MIGRATION VERIFIED' in memory.tx and list(map(bytes,memory.banks))==expected
            assert [[b,a>>12] for kind,b,a,v in memory.events if kind=='erase']==tx['planned_erase_order']
            (folder/'CPU-events.json').write_text(json.dumps(memory.events)+'\n')
            checks.append(dict(name=name,passed=True,fresh_CPU_execution=True,shared_E1_worker=True,native_CPU_simulated=False,
                plan_sha256=digest,installer_sha256=sha(folder/'installer-model-only.s19'),mutation_events=len(memory.events),transfers=len(ops)))
            (OUT/'CPU-progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,len(ops),'transfers',flush=True)
        (OUT/'CPU-report.json').write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,preparation_sha256=sha(OUT/'preparation.json'),board_access=False,hardware_qualified=False),indent=2)+'\n')
        (OUT/'CPU-job.json').write_text(json.dumps(dict(pid=os.getpid(),state='completed')))
    except BaseException:
        (OUT/'CPU-failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc())));raise

if __name__=='__main__':main()
