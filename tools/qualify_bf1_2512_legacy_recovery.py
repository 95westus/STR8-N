"""Seal CPU traces and reject stale/forged legacy recovery preimages offline."""
import argparse,json
from pathlib import Path
import plan_bf1_2512_legacy as p
import bf1_2512_legacy_recovery as recovery

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plans',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
    root=a.plans.resolve();report=p.read(root/'report.json');assert report['passed'] and report['planner_sha256']==p.sha(Path(p.__file__).read_bytes())
    manifest_path=root/'recovery-trace-certificate.json';assert not manifest_path.exists()
    files={path.relative_to(root).as_posix():p.sha(path.read_bytes()) for path in sorted(root.rglob('*')) if path.is_file()}
    certificate=dict(passed=True,offline_only=True,root=str(root),files=files,scope='Hash-bound CPU execution receipts and exact mutation traces; not hardware acceptance')
    manifest_path.write_text(json.dumps(certificate,indent=2)+'\n');digest=p.sha(manifest_path.read_bytes());checks=[]
    for item in report['checks']:
        if not item['name'].endswith('-replay-attested'):continue
        prefix=item['name'].removesuffix('-replay-attested');case=prefix.split('-convert-')[0]+'-convert';count=item['cut_event_count']
        folder=root/(prefix+'-recover');current=[(folder/f'source-b{n}.bin').read_bytes() for n in range(4)]
        tx,data,expected=recovery.prepare(manifest_path,digest,case,count,current);old=p.read(folder/'plan.json')
        assert tx==old['transaction'] and p.hashes(expected)==old['expected_sha256']
        checks.append(dict(name=prefix+' exact recovery admission matches CPU-tested plan',passed=True,cut_event_count=count))
        if prefix.endswith('-provider-erase'):
            alternate,_,_=recovery.prepare(manifest_path,digest,case,count-1,current)
            assert alternate==tx
            checks.append(dict(name=prefix+' identical blank-sector erase preimages retain the same conservative reservation',passed=True))
        attacks=[('wrong-certificate',lambda:recovery.prepare(manifest_path,'0'*64,case,count,current)),
            ('wrong-zero-prefix',lambda:recovery.prepare(manifest_path,digest,case,0,current))]
        for bank in (0,1,3):
            bad=list(map(bytearray,current));bad[bank][0x123]^=1
            attacks.append(('unexplained-bank-'+str(bank),lambda bad=bad:recovery.prepare(manifest_path,digest,case,count,bad)))
        for label,action in attacks:
            try:action()
            except (AssertionError,ValueError):checks.append(dict(name=prefix+' '+label+' refused',passed=True))
            else:raise AssertionError('Forged recovery admitted: '+label)
    assert checks
    result=dict(passed=True,cases=len(checks),checks=checks,trace_certificate=str(manifest_path),trace_certificate_sha256=digest,CPU_report_sha256=p.sha((root/'report.json').read_bytes()),recovery_source_sha256=p.sha(Path(recovery.__file__).read_bytes()),test_source_sha256=p.sha(Path(__file__).read_bytes()),board_access=False,hardware_qualified=False,publication_permitted=False)
    a.out.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'replay-bound legacy recovery admission checks')
if __name__=='__main__':main()
