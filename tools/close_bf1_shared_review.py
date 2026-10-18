"""Close the shared CPU review revision and next physical gate readiness."""
import argparse, hashlib, json, tomllib, zipfile
from pathlib import Path
from datetime import datetime, timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--soak-evidence',type=Path,required=True);ap.add_argument('--process-receipt',type=Path,required=True);a=ap.parse_args()
    archive=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r3.zip';package=read(archive.with_suffix('.package.json'))
    assert package['verified'] and sha(archive)==package['archive_sha256'];kit=Path(package['extraction'])
    out=Q/'bf1-review-gate-2026-10-17-r3';assert not (out/'checkpoint.json').exists()
    audit_path=Q/'bf1-review-integrity-2026-10-17-r3/report.json';audit=read(audit_path)
    assert audit['passed'] and audit['cases']==25 and all(v['passed'] for v in audit['checks'])
    assert sha(ROOT/'tools/test_bf1_shared_review.py')==audit['test_sha256']
    old_archive=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r2.zip'
    assert sha(old_archive)==package['previous_archive_sha256']=='042500224adf7fa68aac1057192512eca539cac06b238457b9eea5b77402993b'
    unchanged=[]
    with zipfile.ZipFile(old_archive) as old,zipfile.ZipFile(archive) as new:
        manifest=read(kit/'review-manifest.json')
        assert len(new.namelist())==len(set(new.namelist()))==155
        assert set(new.namelist())==set(manifest['files'])|{'review-manifest.json'}
        for name in new.namelist():assert new.read(name)==(kit/name).read_bytes()
        for name in old.namelist():
            if name.startswith(('release/candidates/','examples/')) or name in ('reference-build.json','helper-reference.json','build_helper.py'):
                assert old.read(name)==new.read(name);unchanged.append(name)
    prior=read(Q/'bf1-review-gate-2026-10-17-r2/checkpoint.json');assert prior['passed']
    for key in ('firmware_build','helper_build'):
        ref=prior['evidence'][key];assert sha(Path(ref['path']))==ref['sha256']
    build=read(Path(prior['evidence']['firmware_build']['path']));ref=read(kit/'reference-build.json')
    assert build['passed'] and build['source_only'] and not build['binary_inputs']
    assert len(build['compiled'])==27 and build['source_files']==ref['source_files'] and build['artifacts']==ref['artifacts']
    for name,info in ref['artifacts'].items():
        assert sha(ROOT/'tmp/bfx5/payload'/name)==info['sha256']
        assert sha(ROOT/'tmp/bf1kb1/payload'/name)==info['sha256']
    frozen=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    for name,digest in frozen['artifact_hashes'].items():assert sha(Path(frozen['frozen_source_directory'])/'BUILD/v2-beta35-candidate'/name)==digest
    hardware=Q/'bf1-2609-hardware-2026-10-17/shared-cpu-acceptance.json';h=read(hardware)
    assert sha(hardware)==package['shared_hardware_checkpoint_sha256']
    for name,digest in h['protected_review_zip_sha256'].items():assert sha(ROOT/'output/releases'/name)==digest
    readiness=read(out/'recovery-gate-readiness.json')
    assert readiness['passed'] and not readiness['physical_interruption_performed'] and not readiness['live_restoration_performed']
    assert readiness['current_hardware_checkpoint_sha256']==sha(hardware)
    active=read(Q/'active-rtc-campaign.json');campaign=read(Path(active['campaign_state']))
    assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    assert set(campaign['snapshot_boards'])=={'2512','2604','2609'} and campaign['soak_board']=='2604'
    soak=read(a.soak_evidence);process=read(a.process_receipt)
    assert soak['passed'] and soak['run']==campaign['soak_run'] and soak['state']=='running'
    assert process['ProcessId']==soak['pid'] and 'run_bf1_2604_soak.py' in process['CommandLine']
    assert campaign['soak_run'].replace('\\','/') in process['CommandLine'].replace('\\','/')
    guard=read(Q/'device-operations/2609.json');assert guard['state']=='idle' and not guard['block_snapshot']
    schedules={}
    for name in ('2512-powered-soak-and-rtc-drift','2512-nist-snapshot-every-three-hours'):
        cfg=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text());assert cfg['status']=='ACTIVE';schedules[name]='ACTIVE'
    assert tomllib.loads((Path.home()/'.codex'/'automations'/'beta35-prerelease-qualification'/'automation.toml').read_text())['status']=='PAUSED'
    docs={p.name:sha(p) for p in (ROOT/'docs/bf1').glob('*.md')}
    for name,digest in docs.items():assert sha(kit/'docs/bf1'/name)==digest
    result=dict(passed=True,candidate_id='batchfix-r1',version='2.0bf1',generation=48,
        status='shared_cpu_review_package_integrity_passed_physical_gate_prepared',observed_utc=datetime.now(timezone.utc).isoformat(),
        archive=str(archive.resolve()),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,files=155,
        sources=97,artifacts=19,local_links=json.loads(package['stdout'])['local_links'],package_checks=25,
        previous_review_archive_unchanged=True,hardware_checkpoint_sha256=sha(hardware),
        manual_revision_hashes=docs,manual_scope='65C02 and 65C816 emulation runtime; prior W65C02 model results remain attributed',
        build_reuse=dict(prior_review_checkpoint_sha256=sha(Q/'bf1-review-gate-2026-10-17-r2/checkpoint.json'),
                        byte_identical_input_or_output_files=len(unchanged),firmware_links_reused=27,artifacts_identical=19,
                        helper_bytes=585,new_firmware_or_helper_builds_claimed=False,prior_model_example_checks_reused=26),
        integrity_audit=dict(path=str(audit_path.resolve()),sha256=sha(audit_path)),
        next_gate_readiness=dict(path=str((out/'recovery-gate-readiness.json').resolve()),sha256=sha(out/'recovery-gate-readiness.json')),
        next_gate='Physical electrical interruption and original-payload restoration acceptance; needs coordinated owner hardware session and fresh preimages',
        physical_gate_completed=False,next_offline_gate=None,
        remaining_gates=read(kit/'release/bf1-prerelease/acceptance-scope.json')['remaining_gates'],
        soak=dict(board='2604',passed_units=soak['actual_passed_unit_reports'],completed_cycles=soak['completed_cycles'],
                  evidence_sha256=sha(a.soak_evidence),process_receipt_sha256=sha(a.process_receipt)),
        schedules=schedules,snapshot_boards=['2512','2604','2609'],powered_off_boards=['2205'],
        baseline_sha256=active['baseline_index_sha256'],deferred=['native 816','ACIA','crypto'],
        beta35_artifacts_verified=len(frozen['artifact_hashes']),board_access=False,clocks_trims_settings_changed=False,
        installation_permitted=False,release_qualified=False,publication_permitted=False)
    for name in ('package_bf1_shared_review.py','test_bf1_shared_review.py','close_bf1_shared_review.py'):
        (out/name).write_bytes((ROOT/'tools'/name).read_bytes())
    publish(out/'checkpoint.json',result)
    pointer=dict(candidate_id='batchfix-r1',report=str((out/'checkpoint.json').resolve()),report_sha256=sha(out/'checkpoint.json'),
                 status=result['status'],installation_permitted=False,release_qualified=False,publication_permitted=False)
    publish(Q/'bf1-review-current.json',pointer);publish(Q/'batchfix-r1-current.json',pointer)
    publish(archive.with_suffix('.json'),dict(passed=True,archive_sha256=sha(archive),checkpoint=pointer['report'],
            checkpoint_sha256=pointer['report_sha256'],release_qualified=False,installation_permitted=False,publication_permitted=False))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
