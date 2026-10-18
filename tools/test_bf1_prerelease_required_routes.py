"""Offline publication refusals and exact public asset/extraction checks."""
import argparse,copy,json,hashlib,zipfile,tempfile,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from publish_bf1_prerelease import readiness
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,default=Q/'bf1-prerelease-gate-tests-2026-10-17-r2.json');args=ap.parse_args()
    checks=[];pointer=read(Q/'bf1-acceptance-current.json');base=read(Path(pointer['report']))
    # This regression fixture represents the original three-powered-board scope.
    # Owner-evidenced powered-off scope is exercised separately.
    base.pop('required_rtc_boards',None);base.pop('powered_off_collection_suspended',None)
    base['distribution_qualification']=dict(status='passed')
    base['migration_routes']={k:dict(status='passed',board='2512') for k in ('2512-wdcmonv2-to-bf1','2512-v2.0b4-to-bf1')};base['prerelease_ready']=True;base['soaks']['2609'].update(status='passed',application_RAM_restored=True,monitored_hours=4.0,complete_cycles=12,coverage_review_required=False)
    base['soaks']['2604'].update(state='running',coverage_review_required=False);base['errors']={}
    for v in base['RTC'].values():v['fresh']=True
    now=datetime(2026,10,18,4,0,tzinfo=timezone.utc);expires=now+timedelta(hours=1)
    assert readiness(base,now,expires);checks.append(dict(name='ready-pilot-with-long-gates-pending',passed=True))
    changes=[('short-soak',lambda r:r['soaks']['2609'].update(monitored_hours=3.99)),('RAM-not-restored',lambda r:r['soaks']['2609'].update(application_RAM_restored=False)),('no-complete-cycle',lambda r:r['soaks']['2609'].update(complete_cycles=0)),('pilot-failed',lambda r:r['soaks']['2609'].update(status='inspection-required')),('2604-stopped',lambda r:r['soaks']['2604'].update(state='stopped-on-failure')),('2604-gap',lambda r:r['soaks']['2604'].update(coverage_review_required=True)),('2609-gap',lambda r:r['soaks']['2609'].update(coverage_review_required=True)),('stale-RTC',lambda r:r['RTC']['2512'].update(fresh=False)),('unresolved-failure',lambda r:r['errors'].update(board='failure'))]
    for name,change in changes:
        v=copy.deepcopy(base);change(v);assert not readiness(v,now,expires),name;checks.append(dict(name=name,passed=True,refused=True))
    for name,change in [('missing-required-route',lambda r:r['migration_routes'].pop('2512-wdcmonv2-to-bf1')),('unqualified-required-route',lambda r:r['migration_routes']['2512-v2.0b4-to-bf1'].update(status='pending')),('wrong-route-board',lambda r:r['migration_routes']['2512-v2.0b4-to-bf1'].update(board='2609'))]:
        v=copy.deepcopy(base);change(v);assert not readiness(v,now,expires),name;checks.append(dict(name=name,passed=True,refused=True))
    for name,change in [('missing-distribution-qualification',lambda r:r.pop('distribution_qualification')),('docs-or-portable-kit-pending',lambda r:r['distribution_qualification'].update(status='pending'))]:
        v=copy.deepcopy(base);change(v);assert not readiness(v,now,expires),name;checks.append(dict(name=name,passed=True,refused=True))
    assert not readiness(base,expires,expires);checks.append(dict(name='tonight-window-expired',passed=True,refused=True))
    prep=read(OUT/'preparation.json');draft=read(OUT/'draft.json');assert sha(OUT/'preparation.json')==draft['preparation_sha256']
    for info in prep['assets'].values():assert sha(Path(info['path']))==info['sha256']
    with tempfile.TemporaryDirectory(prefix='bf1-public-verify-',dir=ROOT/'tmp') as tmp:
        k=Path(tmp)
        with zipfile.ZipFile(OUT/'str8n-2.0bf1-prerelease.zip') as z:
            assert len(z.namelist())==len(set(z.namelist())) and all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist());z.extractall(k)
        manifest=read(k/'public-manifest.json')
        for name,info in manifest['files'].items():assert sha(k/name)==info['sha256'] and (k/name).stat().st_size==info['bytes']
        for row in (k/'SHA256SUMS').read_text().splitlines():
            digest,name=row.split('  ',1);assert sha(k/name)==digest
        pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
        assert manifest['artifacts']==pin['artifacts'] and manifest['sources']==97
        for name,info in pin['artifacts'].items():assert sha(k/'release/candidates/batchfix-r1/payload'/name)==info['sha256']
        for p in k.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if re.match(r'[a-z]+:',link):continue
                path=(p.parent/link.split('#')[0]).resolve();assert path.is_relative_to(k.resolve()) and path.is_file()
        checks.append(dict(name='public-extraction-checksums-source-pins-19-artifacts-links',passed=True))
        assert not any(p.name.lower() in ('b0.bin','b1.bin','b2.bin','b3.bin','eeprom.bin','sram.bin','serial.jsonl') for p in k.rglob('*'));checks.append(dict(name='no-device-backups-or-serial-logs',passed=True))
    receipt=dict(passed=True,cases=len(checks),checks=checks,publisher_sha256=sha(ROOT/'tools/publish_bf1_prerelease.py'),test_sha256=sha(Path(__file__)),preparation_sha256=sha(OUT/'preparation.json'),draft_sha256=sha(OUT/'draft.json'),board_access=False,network_access=False)
    p=args.out;assert not p.exists();p.write_text(json.dumps(receipt,indent=2)+'\n');print('PASS',len(checks),'public package and publication gate checks')
if __name__=='__main__':main()
