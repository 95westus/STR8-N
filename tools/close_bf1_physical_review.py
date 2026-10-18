"""Close the bounded physical-review revision without any board access."""
import argparse,json,hashlib,zipfile,tomllib
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--soak-evidence',type=Path,required=True);ap.add_argument('--process-receipt',type=Path,required=True);a=ap.parse_args()
    archive=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r4.zip';package=read(archive.with_suffix('.package.json'))
    assert package['verified'] and sha(archive)==package['archive_sha256']
    kit=Path(package['extraction']);audit_path=Q/'bf1-review-integrity-2026-10-17-r4/report.json';audit=read(audit_path)
    assert audit['passed'] and audit['cases']==33 and all(c['passed'] for c in audit['checks'])
    assert sha(ROOT/'tools/test_bf1_physical_review.py')==audit['test_sha256'] and sha(ROOT/'tools/test_bf1_shared_review.py')==audit['base_test_sha256']
    prior=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r3.zip'
    assert sha(prior)==package['previous_archive_sha256']=='2d03bc3de329e44176056adcf92d570c0e2ebd07ab8c4e8e1ba4a9328396c0c4'
    unchanged=[]
    with zipfile.ZipFile(prior) as old,zipfile.ZipFile(archive) as new:
        manifest=read(kit/'review-manifest.json')
        assert len(new.namelist())==len(set(new.namelist()))==package['files']
        assert set(new.namelist())==set(manifest['files'])|{'review-manifest.json'}
        for name in new.namelist():assert new.read(name)==(kit/name).read_bytes()
        for name in old.namelist():
            if name.startswith(('release/candidates/','examples/','docs/bf1/')) or name in ('reference-build.json','helper-reference.json','build_helper.py'):
                assert old.read(name)==new.read(name);unchanged.append(name)
    previous=read(Q/'bf1-review-gate-2026-10-17-r3/checkpoint.json');assert previous['passed']
    hardware=read(Q/'bf1-2609-hardware-2026-10-17/shared-cpu-acceptance.json')
    for name,digest in hardware['protected_review_zip_sha256'].items():assert sha(ROOT/'output/releases'/name)==digest
    frozen=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    for name,digest in frozen['artifact_hashes'].items():assert sha(Path(frozen['frozen_source_directory'])/'BUILD/v2-beta35-candidate'/name)==digest
    reference=read(kit/'reference-build.json')
    for name,info in reference['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==info['sha256']
    active=read(Q/'active-rtc-campaign.json');sp=Path(active['campaign_state']);state=read(sp)
    assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    assert state['soak_board']=='2604' and set(state['snapshot_boards'])=={'2512','2604','2609'}
    guard=read(Q/'device-operations/2609.json');assert guard['state']=='idle' and not guard['block_snapshot']
    soak=read(a.soak_evidence);process=read(a.process_receipt)
    assert soak['passed'] and soak['run']==state['soak_run'] and soak['state']=='running'
    assert process['ProcessId']==soak['pid'] and 'run_bf1_2604_soak.py' in process['CommandLine']
    assert state['soak_run'].replace('\\','/') in process['CommandLine'].replace('\\','/')
    for name in ('2512-powered-soak-and-rtc-drift','2512-nist-snapshot-every-three-hours'):
        assert tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text())['status']=='ACTIVE'
    assert tomllib.loads((Path.home()/'.codex'/'automations'/'beta35-prerelease-qualification'/'automation.toml').read_text())['status']=='PAUSED'
    physical=read(kit/'evidence/physical/index.json');scope=read(kit/'release/bf1-prerelease/acceptance-scope.json')
    out=Q/'bf1-review-gate-2026-10-17-r4';out.mkdir(exist_ok=False)
    for name in ('package_bf1_physical_review.py','test_bf1_physical_review.py','close_bf1_physical_review.py'):(out/name).write_bytes((ROOT/'tools'/name).read_bytes())
    result=dict(passed=True,candidate_id='batchfix-r1',version='2.0bf1',generation=48,
        status='bounded_2609_physical_recovery_and_review_integrity_passed_owner_acceptance_pending',
        observed_utc=datetime.now(timezone.utc).isoformat(),archive=str(archive.resolve()),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
        files=package['files'],sources=97,artifacts=19,package_checks=33,local_links=json.loads(package['stdout'])['local_links'],
        prior_review_checkpoint_sha256=sha(Q/'bf1-review-gate-2026-10-17-r3/checkpoint.json'),
        unchanged_prior_build_manual_example_files=len(unchanged),new_firmware_builds_or_ABI_suites_claimed=False,
        physical_evidence=physical,physical_cases=2,original_restoration_passed=True,
        physical_limits=['2609 two verified transfer boundaries only','No mid-erase/program or arbitrary byte timing qualification','No 2604 electrical behavior qualification'],
        remaining_gates=scope['remaining_gates'],next_offline_gate=None,
        integrity_audit=dict(path=str(audit_path.resolve()),sha256=sha(audit_path)),
        soak=dict(board='2604',passed_units=soak['actual_passed_unit_reports'],completed_cycles=soak['completed_cycles'],evidence_sha256=sha(a.soak_evidence),process_receipt_sha256=sha(a.process_receipt)),
        snapshot_boards=['2512','2604','2609'],powered_off_boards=['2205'],baseline_sha256=active['baseline_index_sha256'],
        deferred=['native 816','ACIA','crypto'],board_access=False,clocks_trims_changed=False,
        release_qualified=False,installation_permitted=False,publication_permitted=False)
    publish(out/'checkpoint.json',result)
    pointer=dict(candidate_id='batchfix-r1',report=str((out/'checkpoint.json').resolve()),report_sha256=sha(out/'checkpoint.json'),status=result['status'],installation_permitted=False,release_qualified=False,publication_permitted=False)
    publish(Q/'bf1-review-current.json',pointer);publish(Q/'batchfix-r1-current.json',pointer)
    publish(archive.with_suffix('.json'),dict(passed=True,archive_sha256=sha(archive),checkpoint=pointer['report'],checkpoint_sha256=pointer['report_sha256'],release_qualified=False,installation_permitted=False,publication_permitted=False))
    state['2609_role']='bf1 A48/B48 powered on, bounded physical recovery cases complete; RTC-only, no workload soak'
    state['2609_physical_gate'].update(state='Bounded original-restoration and both power-cut recovery cases completed; owner acceptance/coverage decision pending',review_checkpoint=pointer['report'],review_checkpoint_sha256=pointer['report_sha256'])
    publish(sp,state)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
