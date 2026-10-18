"""Create r4 from sealed r3, adding bounded physical receipts, never device data."""
import json,hashlib,zipfile,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';G=Q/'bf1-2609-physical-gate-2026-10-17-r1'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def main():
    prior=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r3.zip'
    assert sha(prior.read_bytes())=='2d03bc3de329e44176056adcf92d570c0e2ebd07ab8c4e8e1ba4a9328396c0c4'
    archive=prior.with_name('str8n-2.0bf1-local-review-2026-10-17-r4.zip');kit=ROOT/'tmp/bf1k4'
    assert not archive.exists() and not kit.exists()
    with zipfile.ZipFile(prior) as z:files={n:z.read(n) for n in z.namelist() if n not in ('review-manifest.json','review-allowlist.json')}
    changes={};receipts={}
    def add(name,p):
        data=p.read_bytes();files[name]=data;changes[name]=sha(data)
    for name in ('README.md','NEXT_GATE.md','REMAINING_GATES.md','verify_review.py','verify_physical.py'):
        add(name,ROOT/'release/bf1-prerelease/review-shared'/name)
    add('release/bf1-prerelease/acceptance-scope.json',ROOT/'release/bf1-prerelease/shared-cpu-scope.json')
    for number in (1,2):
        cut=G/f'power-cut-{number}';cp=read(cut/'checkpoint.json')
        assert cp['passed'] and cp['hardware_power_interruption_and_recovery_passed']
        pairs={'checkpoint':cut/'checkpoint.json',**{k:Path(v['path']) for k,v in cp['refs'].items()}}
        for name,p in pairs.items():
            if name!='checkpoint':assert sha(p.read_bytes())==cp['refs'][name]['sha256']
            local=f'evidence/physical/case-{number}/{name}.json';add(local,p)
            receipts[f'case-{number}-{name}']=dict(file=local,sha256=sha(p.read_bytes()))
    original=G/'original-restoration-checkpoint.json';assert read(original)['passed']
    add('evidence/physical/original-restoration.json',original)
    receipts['original-restoration']=dict(file='evidence/physical/original-restoration.json',sha256=sha(original.read_bytes()))
    for phase in ('restore-A40','restore-B35'):
        for label,p in (('transaction',G/phase/'report.json'),('hardware',G/(phase+'-checks')/'report.json')):
            add(f'evidence/physical/{phase}-{label}.json',p)
    index=dict(scope='2609 verified transfer boundaries only',receipts=receipts,
               mid_erase_program_qualified=False,arbitrary_byte_timing_qualified=False,
               **{'2604_electrical_qualified':False},
               original_baseline_preserved=True,clocks_trims_unchanged=True,
               next_gate='Owner scope/coverage acceptance and soak/RTC duration thresholds; separate release decision',
               deferred=['native 816','ACIA','crypto'],release_qualified=False,installation_permitted=False,publication_permitted=False)
    files['evidence/physical/index.json']=(json.dumps(index,indent=2)+'\n').encode()
    summary=json.loads(files['review-evidence-summary.json']);summary.update(
        physical_results='2609 original A40/B35 payload restoration and two verified-transfer-boundary power-cut/fallback/recovery cases',
        physical_receipt='evidence/physical/index.json',
        physical_limits='No mid-erase/program, arbitrary byte timing or 2604 electrical qualification',
        next_gate=index['next_gate'],prior_build_and_model_evidence='Reused unchanged from r3; no fresh firmware builds or ABI suites claimed')
    files['review-evidence-summary.json']=(json.dumps(summary,indent=2)+'\n').encode()
    files['review-allowlist.json']=(json.dumps(sorted([*files,'review-allowlist.json']),indent=2)+'\n').encode()
    manifest=dict(candidate_id='batchfix-r1',version='2.0bf1',generation=48,installation_permitted=False,release_qualified=False,publication_permitted=False,deferred=['native 816','ACIA','crypto'],files={n:dict(bytes=len(v),sha256=sha(v)) for n,v in sorted(files.items())})
    files['review-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    with zipfile.ZipFile(archive,'x') as z:
        for n,data in sorted(files.items()):
            info=zipfile.ZipInfo(n,(2026,10,17,0,0,0));info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()));z.extractall(kit)
    result=subprocess.run([sys.executable,'-B',str(kit/'verify_review.py'),str(kit)],capture_output=True,text=True)
    receipt=dict(verified=result.returncode==0,archive=str(archive.resolve()),archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,files=len(files),extraction=str(kit.resolve()),previous_archive_sha256=sha(prior.read_bytes()),changed_or_added=changes,stdout=result.stdout,stderr=result.stderr,board_access=False,created_utc=datetime.now(timezone.utc).isoformat(),packager_sha256=sha(Path(__file__).read_bytes()))
    archive.with_suffix('.package.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert result.returncode==0,(result.stdout,result.stderr)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
