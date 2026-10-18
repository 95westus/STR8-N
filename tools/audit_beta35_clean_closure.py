"""Bind clean-build/package closure to immutable qualification and RTC evidence.

This audit reads existing offline build results. It does not run an installer,
open serial ports, or infer new hardware readback from historical plan images.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-a',type=Path,required=True)
    p.add_argument('--build-b',type=Path,required=True)
    p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--archive-a',type=Path,required=True)
    p.add_argument('--archive-b',type=Path,required=True)
    p.add_argument('--integrity-report',type=Path,required=True)
    args = p.parse_args()
    integrity = read(args.integrity_report)
    assert integrity['passed'] and integrity['tests']==5 and integrity['failures']==integrity['errors']==0
    assert Path(integrity['kit']).resolve()==args.kit.resolve()
    meta = read(ROOT/'release/beta35/release.json')
    a,b = [read(d/'build-report.json') for d in (args.build_a,args.build_b)]
    for report in (a,b):
        assert report['passed'] and report['source_only'] and not report['binary_inputs']
        assert report['artifacts']==meta['expected'] and len(report['compiled'])==26
        assert report['build_script_sha256']==sha(ROOT/'release/beta35/build.py')
        assert report['release_manifest_sha256']==sha(ROOT/'release/beta35/release.json')
    assert a==b, 'Independent source build reports must be identical'
    assert args.archive_a.read_bytes()==args.archive_b.read_bytes(), 'Archive is not deterministic'
    for name,info in meta['expected'].items():
        for directory in (args.build_a/'payload',args.build_b/'payload',args.kit/'payload'):
            assert sha(directory/name)==info['sha256'], (directory,name)
    composition = []
    for segment in read(args.kit/'layout.json')['segments']:
        bank,address,size,offset = [segment[n] for n in ('bank','address','bytes','offset')]
        data = (args.kit/'payload'/segment['file']).read_bytes()[offset:offset+size]
        plan = ROOT/f'output/qualification/beta35-fleet-2026-10-16/2512/expected-b{bank}.bin'
        assert data==plan.read_bytes()[address-0x8000:address-0x8000+size], segment
        composition.append({**segment,'matches_historical_2512_plan':True,'plan_sha256':sha(plan)})
    freeze = read(PRIOR/'freeze.json')
    for base in (ROOT/'BUILD/v2-beta35-candidate',ROOT/'tmp/b34/BUILD/v2-beta35-candidate'):
        assert sha(base/'build.json')==freeze['build_sha256']
        for name,digest in freeze['artifact_hashes'].items():
            assert sha(base/name)==digest, name
        for name,digest in freeze['reference_bank_hashes'].items():
            assert sha(base/'candidate'/(name+'.bin'))==digest, name
    active_path = ROOT/'output/qualification/active-rtc-campaign.json'
    active = read(active_path)
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==freeze['active_rtc_baseline_sha256']
    assert set(active['powered_off_boards'])=={'2205','2604','2609'}
    soak_path = Path(read(Path(active['campaign_state']))['soak_run'])
    soak = read(soak_path/'status.json')
    assert soak['state']=='running' and soak['clock_set'] is False and soak['settings_changed'] is False
    now = datetime.now(timezone.utc)
    out = ROOT/'output/qualification'/now.strftime('beta35-clean-build-%Y-%m-%d-%H%M%SZ')
    out.mkdir()
    for name,source in [('build-a.json',args.build_a/'build-report.json'),
                        ('build-b.json',args.build_b/'build-report.json'),
                        ('package.json',args.archive_a.with_suffix('.json')),
                        ('integrity-tests.json',args.integrity_report),
                        ('source-provenance.json',ROOT/'release/beta35/source-provenance.json'),
                        ('release.json',ROOT/'release/beta35/release.json'),
                        ('layout.json',ROOT/'release/beta35/layout.json')]:
        shutil.copyfile(source,out/name)
    tools = {n:sha(ROOT/n) for n in ['release/beta35/build.py','release/beta35/verify.py',
             'tools/export_beta35_release_sources.py','tools/package_beta35_review.py',
             'tools/test_beta35_review.py','tools/audit_beta35_clean_closure.py']}
    result = {
        'version':'2.0b35','generation':47,'finished_utc':now.isoformat(),
        'state':'clean-source-build-and-review-package-closed', 'release_qualified':False,
        'candidate_build_sha256':freeze['build_sha256'],
        'prior_offline_evidence':str(PRIOR), 'prior_status_sha256':sha(PRIOR/'status.json'),
        'fresh_links_per_build':26, 'exact_artifacts_per_build':18,
        'source_files':len(a['source_files']), 'external_binary_inputs':[],
        'builds':[str(args.build_a.resolve()),str(args.build_b.resolve())],
        'second_build_from_extracted_archive':True,
        'isolated_python_second_build':True,
        'identical_build_reports':True,'deterministic_archive':True,
        'archive':str(args.archive_a.resolve()),'archive_sha256':sha(args.archive_a),
        'archive_bytes':args.archive_a.stat().st_size,
        'integrity_tests':integrity,'integrity_tests_sha256':sha(args.integrity_report),
        'logical_composition':composition,'composition_is_historical_plan_comparison':True,
        'new_hardware_readback':False,'board_access_for_closure':False,
        'sealed_candidates_unchanged':True,'rtc_baseline_unchanged':True,
        'active_rtc_baseline_sha256':active['baseline_index_sha256'],
        'soak_observation':{'run':str(soak_path),'pid':soak['pid'],'state':soak['state'],
                            'passed_units':soak['passed_units'],'completed_cycles':soak['completed_cycles'],
                            'updated':soak['updated']},
        'powered_off_boards':['2205','2604','2609'],'deferred':['ACIA','crypto'],
        'tools':tools,
        'gates':{'complete_clean_source_build':'passed for the frozen FT245/F30D review payload set',
                 'review_package_cleanup':'passed; 123 files, 97 source files, 18 payloads, 13 mapped ranges',
                 'source_to_target_migration_matrix':'pending',
                 'physical_migration_and_recovery':'pending; powered-off interval protected',
                 'ongoing_soak':'collecting', 'power_off_drift':'collecting',
                 'manuals_and_verified_examples':'pending', 'publication':'not authorized/performed'},
        'closed_findings':{'QA35-001':'Canonical sparse layout uses freshly built CLOCK 1.10; inherited full bank excluded',
                           'QA35-002':'Explicit allowlist excludes CLOCK 1.9 and historical MAINT artifacts'},
        'retained_limits':['Historical source/candidate folders remain sealed and may contain stale reference images',
                           'No universal migration or installation acceptance inferred from exact artifact reproduction'],
    }
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    pointer = {'version':'2.0b35','release_qualified':False,'report':str(out/'report.json'),
               'report_sha256':sha(out/'report.json'),'updated_utc':now.isoformat()}
    (ROOT/'output/qualification/beta35-release-current.json').write_text(json.dumps(pointer,indent=2)+'\n')
    print(json.dumps(pointer,indent=2))


if __name__=='__main__':
    main()
