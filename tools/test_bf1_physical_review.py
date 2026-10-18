"""Run the prior verifier regression plus semantic physical-evidence refusals."""
import json,hashlib,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=Q/'bf1-review-integrity-2026-10-17-r4';KIT=ROOT/'tmp/bf1k4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    r=subprocess.run([sys.executable,str(ROOT/'tools/test_bf1_shared_review.py'),str(KIT),'--report',str(OUT/'base-report.json')])
    assert r.returncode==0
    checks=json.loads((OUT/'base-report.json').read_text())['checks']
    def run(name,file,mutate,expected,parent=False):
        with tempfile.TemporaryDirectory(prefix='bf1-physical-',dir=ROOT/'tmp') as tmp:
            k=Path(tmp)/'kit';shutil.copytree(KIT,k)
            def write(n,data):
                p=k/n;p.write_text(json.dumps(data,indent=2)+'\n')
                m=k/'review-manifest.json';v=json.loads(m.read_text());v['files'][n]=dict(bytes=p.stat().st_size,sha256=sha(p));m.write_text(json.dumps(v))
            value=json.loads((k/file).read_text());mutate(value);write(file,value)
            # Rebind every parent receipt so the semantic check must refuse.
            index='evidence/physical/index.json';v=json.loads((k/index).read_text())
            if parent:
                for ref in v['receipts'].values():
                    if ref['file']==file:ref['sha256']=sha(k/file)
                if file.endswith(('/hardware.json','/admission.json')):
                    cp='evidence/physical/case-2/checkpoint.json';c=json.loads((k/cp).read_text())
                    key=Path(file).stem;c['refs'][key]['sha256']=sha(k/file);write(cp,c)
                    v['receipts']['case-2-checkpoint']['sha256']=sha(k/cp)
                write(index,v)
            r=subprocess.run([sys.executable,'-B',str(k/'verify_review.py'),str(k)],capture_output=True,text=True)
            (OUT/(name+'.json')).write_text(json.dumps(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr),indent=2)+'\n')
            assert r.returncode!=0 and expected in r.stderr,(name,r.stdout,r.stderr)
            checks.append(dict(name=name,passed=True,refused=True));print('PASS',name,flush=True)
    prefix='evidence/physical/'
    run('physical-broadened-board',prefix+'index.json',lambda v:v.update(**{'2604_electrical_qualified':True}),'Electrical scope broadened')
    run('physical-mid-erase-claim',prefix+'index.json',lambda v:v.update(mid_erase_program_qualified=True),'Electrical scope broadened')
    run('physical-rebound-permission',prefix+'case-2/checkpoint.json',lambda v:v.update(release_qualified=True),'Physical permission flags',True)
    run('physical-rebound-payload-erase',prefix+'case-2/checkpoint.json',lambda v:v.update(A_payload_reerased_during_recovery=True),'Wear-aware A recovery',True)
    run('physical-rebound-mode',prefix+'case-2/hardware.json',lambda v:v['cpu_mode_after'].update(emulation_mode_before_probe=False),'Physical emulation contract',True)
    run('physical-rebound-RAM',prefix+'case-2/hardware.json',lambda v:v.update(pre_interruption_RAM_restored=False),'Physical hardware completion',True)
    run('physical-rebound-PF',prefix+'case-2/admission.json',lambda v:v['EEPROM_expected_PF_event'].update(sequence=34),'Physical PF evidence',True)
    run('physical-index-binding',prefix+'case-2/recovery.json',lambda v:v.update(transfers_completed=3),'Physical receipt binding')
    result=dict(passed=True,cases=len(checks),checks=checks,base_test_sha256=sha(ROOT/'tools/test_bf1_shared_review.py'),test_sha256=sha(Path(__file__)),kit=str(KIT),board_access=False)
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
