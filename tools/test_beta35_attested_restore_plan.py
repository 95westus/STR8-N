"""Verify all receipt-bound restoration plans; no instructions or hardware executed."""
import argparse,json,traceback
from pathlib import Path
from datetime import datetime,timezone
import plan_beta35_attested_restoration as a
c=a.c;p=a.p
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    cp=p.read(c.EVIDENCE/'transaction-model-checkpoint.json');source=Path(cp['report']);prior=p.read(source);build=Path(cp['build_report']).parent;checks=[]
    assert p.sha(source.read_bytes())==cp['report_sha256']
    def record(name,**kw):checks.append(dict(name=name,passed=True,**kw));print('PASS',name,flush=True)
    try:
        for case in prior['checks']:
            label=case['name'];board=label.split('-')[0] if label.endswith('-complete') else '2512'
            backup=c.old.fixture(board);info=p.read(build/board/'plan.json');folder=source.parent/label
            banks=[(folder/f'b{i}.bin').read_bytes() for i in range(4)];events=p.read(folder/'events.json')
            if label.startswith('stale-bank-'):
                try:a.restoration(banks,backup,certificate=case,events=events,upgrade_plan=info)
                except ValueError as e:record(label+' refused',reason=str(e))
                else:raise AssertionError('Stale image admitted')
                continue
            tx,data,expected=a.restoration(banks,backup,certificate=case,events=events,upgrade_plan=info)
            assert all(expected[i]==backup[i] for i in (0,1,2))
            assert expected[3][:0x4000]==backup[3][:0x4000] and expected[3][0x6000:]==backup[3][0x6000:]
            seq,off,r,valid=c.latest(expected);assert r[8:24]==c.latest(backup)[2][8:24]
            counts=[int.from_bytes(r[24+i*3:27+i*3],'little') for i in range(32)]
            assert counts==tx['reserved_counts'] and all(counts[i]>=tx['counts_before'][i] for i in range(32))
            for i in range(32):assert counts[i]==tx['counts_before'][i]+sum(b*8+s-8==i for b,s in tx['planned_erase_order'])
            target=args.out/label;target.mkdir();(target/'plan.json').write_text(json.dumps(tx,indent=2)+'\n')
            record(label+' plans exact payload restore with retained counts',additional_erases=len(tx['planned_erase_order']),
                counts_before=tx['counts_before'],counts_after=counts,source_sha256=p.bank_hashes(banks),expected_sha256=p.bank_hashes(expected))
        # A fabricated certificate must fail even if its hash agrees with its
        # supplied bytes; an arbitrary new source is not an accepted fixture.
        fake=dict(case,name='forged-case')
        try:a.restoration(banks,backup,certificate=fake,events=events,upgrade_plan=info)
        except ValueError as e:record('fabricated certificate refused',reason=str(e))
        else:raise AssertionError('Unregistered certificate admitted')
        wrong=json.loads(json.dumps(info));wrong['source_sha256']=p.bank_hashes(banks)
        try:a.restoration(banks,backup,certificate=case,events=events,upgrade_plan=wrong)
        except ValueError as e:record('fabricated upgrade plan refused',reason=str(e))
        else:raise AssertionError('Unregistered upgrade plan admitted')
    except Exception:
        (args.out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    result=dict(passed=True,cases=len(checks),checks=checks,source_report_sha256=cp['report_sha256'],
        finished_utc=datetime.now(timezone.utc).isoformat(),test_sha256=p.sha(Path(__file__).read_bytes()),
        attestation_sha256=p.sha(Path(a.__file__).read_bytes()),composer_sha256=p.sha(Path(c.__file__).read_bytes()),
        restored_plan_cases=sum('additional_erases' in v for v in checks),instruction_execution=False,
        wear_aware_restoration_qualified=False,physical_restoration_qualified=False,board_access=False,
        installation_permitted=False,release_qualified=False)
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(checks),'attested restoration planning checks')
if __name__=='__main__':main()
