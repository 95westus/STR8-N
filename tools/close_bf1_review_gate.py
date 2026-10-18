"""Bind final bf1 review ZIP, extracted builds and integrity audit; no devices."""
import argparse,hashlib,json,tomllib,zipfile
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--soak-evidence',type=Path,required=True);ap.add_argument('--process-receipt',type=Path,required=True);a=ap.parse_args()
    archive=ROOT/'output/releases/str8n-2.0bf1-local-review-2026-10-17-r2.zip';package=read(archive.with_suffix('.package.json'))
    assert package['verified'] and sha(archive)==package['archive_sha256'];kit=Path(package['extraction'])
    audit_path=Q/'bf1-review-integrity-2026-10-17-r2/report.json';audit=read(audit_path);assert audit['passed'] and audit['cases']==19 and all(v['passed'] for v in audit['checks'])
    assert sha(ROOT/'tools/test_bf1_review.py')==audit['test_sha256']
    build_root=ROOT/'tmp/bf1kb1';br=build_root/'build-report.json';build=read(br);ref=read(kit/'reference-build.json')
    assert build['passed'] and build['source_only'] and not build['binary_inputs'] and len(build['compiled'])==27 and build['artifacts']==ref['artifacts'] and build['source_files']==ref['source_files']
    # The first extraction was freshly rebuilt. Only verifier scope checks
    # changed for r2; prove the complete build inputs, artifacts and helper
    # inputs are identical before reusing that build result for the final ZIP.
    first=ROOT/'tmp/bf1k1';changed=[]
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('review-manifest.json'))
        assert len(z.namelist())==len(set(z.namelist()))==145 and set(z.namelist())==set(manifest['files'])|{'review-manifest.json'}
        for name,info in manifest['files'].items():
            data=z.read(name);assert dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())==info
            assert (kit/name).read_bytes()==data
            if (first/name).read_bytes()!=data:changed.append(name)
    assert set(changed)=={'verify_review.py','review-allowlist.json'} or set(changed)=={'verify_review.py'}
    # review-allowlist may retain identical bytes; manifest is separately bound.
    for name,info in ref['artifacts'].items():
        path=build_root/'payload'/name;assert sha(path)==info['sha256'] and path.stat().st_size==info['bytes']
    assert sha(first/'release/candidates/batchfix-r1/build.py')==sha(kit/'release/candidates/batchfix-r1/build.py')==build['build_script_sha256']==ref['builder_sha256']
    hr=ROOT/'tmp/bf1kh1/build-report.json';helper=read(hr);href=read(kit/'helper-reference.json');assert helper['passed'] and helper['bytes']==585 and helper['binary_sha256']==href['binary_sha256']
    assert sha(ROOT/'tmp/bf1kh1/reservation.bin')==href['binary_sha256']
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,digest in pin['source_files'].items():assert sha(ROOT/'release/candidates/batchfix-r1'/name)==digest
    for name,info in pin['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==info['sha256']
    frozen=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    for name,digest in frozen['artifact_hashes'].items():assert sha(Path(frozen['frozen_source_directory'])/'BUILD/v2-beta35-candidate'/name)==digest
    prior=read(Q/'batchfix-r1-2026-10-17/status.json')
    for name,digest in prior['prior_review_archives'].items():assert sha(ROOT/'output/releases'/name)==digest
    active=read(Q/'active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    assert set(active['powered_off_boards'])=={'2205','2609'}
    campaign=read(Path(active['campaign_state']));soak=read(a.soak_evidence);process=read(a.process_receipt)
    assert campaign['soak_board']=='2604' and soak['passed'] and soak['run']==campaign['soak_run'] and soak['state']=='running'
    assert process['ProcessId']==soak['pid'] and 'run_bf1_2604_soak.py' in process['CommandLine'] and campaign['soak_run'].replace('\\','/') in process['CommandLine'].replace('\\','/')
    schedules={}
    for name in ('2512-powered-soak-and-rtc-drift','2512-nist-snapshot-every-three-hours'):
        config=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text());assert config['status']=='ACTIVE';schedules[name]=config['status']
    assert tomllib.loads((Path.home()/'.codex'/'automations'/'beta35-prerelease-qualification'/'automation.toml').read_text())['status']=='PAUSED'
    manual=Q/'bf1-manual-gate-2026-10-17-r1/checkpoint.json';m=read(manual)
    assert sha(manual)==package['manual_checkpoint_sha256']
    for name,digest in m['documents'].items():assert sha(ROOT/'docs/bf1'/name)==digest
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('package_bf1_review.py','test_bf1_review.py','close_bf1_review_gate.py'):(a.out/name).write_bytes((ROOT/'tools'/name).read_bytes())
    refs={'integrity_audit':audit_path,'firmware_build':br,'helper_build':hr,'manual_checkpoint':manual,'soak_evidence':a.soak_evidence,'soak_process_receipt':a.process_receipt,'r1_failed_scope_test':Q/'bf1-review-integrity-2026-10-17-r1/report.failure.json'}
    result=dict(passed=True,candidate_id='batchfix-r1',version='2.0bf1',generation=48,status='local_review_package_and_integrity_gate_passed',observed_utc=datetime.now(timezone.utc).isoformat(),
        archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,files=145,sources=97,artifacts=19,local_links=36,package_checks=19,
        fresh_extracted_firmware_build=dict(links=27,artifacts_identical=19,source_extraction=str(first),final_extraction=str(kit),final_build_inputs_byte_identical=True,new_links_claimed_for_r2=False,meaning='One fresh 27-link build this turn, from r1 extraction. All inputs/outputs are byte-identical in r2; reused explicitly after verifier-only correction.'),
        fresh_extracted_helper_build=dict(bytes=585,binary_sha256=href['binary_sha256'],identical_final_inputs=True),
        evidence={name:dict(path=str(path.resolve()),sha256=sha(path)) for name,path in refs.items()},
        corrected_verifier_gap='r1 accepted a rehashed broadened route description. r2 requires the exact approved 2604 migration scope. r1 archive and failed test preserved.',
        firmware_or_helper_sources_modified=False,beta35_artifacts_verified=len(frozen['artifact_hashes']),prior_review_archives_unchanged=True,baseline_sha256=active['baseline_index_sha256'],
        deferred=['native 816','ACIA','crypto'],processor_execution_scope='W65C02',schedules=schedules,prerelease_automation='PAUSED',
        soak=dict(board='2604',run=soak['run'],pid=soak['pid'],passed_units=soak['actual_passed_unit_reports'],completed_cycles=soak['completed_cycles']),snapshot_boards=['2512','2604'],powered_off_boards=['2205','2609'],
        completed_gate='Candidate-specific local review package and integrity audit',remaining_gates=['Physical electrical interruption and original-payload restoration acceptance on the exact supported route','Long-term preserving bf1 soak and RTC accumulation; duration/acceptance threshold still requires owner decision','Explicit scoped release acceptance'],
        next_offline_gate=None,scope_policy_snapshot='release/bf1-prerelease/acceptance-scope.json workflow queue is the earlier manual checkpoint snapshot; this completed-gate record supersedes its queued package task.',
        board_access=False,clock_trim_settings_changed=False,installation_permitted=False,release_qualified=False,publication_permitted=False)
    publish(a.out/'checkpoint.json',result)
    publish(a.out/'manifest.json',dict(files={p.name:sha(p) for p in a.out.iterdir() if p.is_file()}))
    pointer=dict(candidate_id='batchfix-r1',report=str((a.out/'checkpoint.json').resolve()),report_sha256=sha(a.out/'checkpoint.json'),status=result['status'],installation_permitted=False,release_qualified=False,publication_permitted=False)
    publish(Q/'bf1-review-current.json',pointer);publish(Q/'batchfix-r1-current.json',pointer)
    publish(archive.with_suffix('.json'),dict(archive_sha256=sha(archive),checkpoint=pointer['report'],checkpoint_sha256=pointer['report_sha256'],passed=True,release_qualified=False,installation_permitted=False,publication_permitted=False))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
