"""Pin separate candidate evidence without altering beta35 or any device."""
import argparse,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--build',required=True,type=Path);ap.add_argument('--model',required=True,type=Path);ap.add_argument('--admission',required=True,type=Path);ap.add_argument('--pending',action='store_true');a=ap.parse_args()
    candidate=ROOT/'release/candidates/batchfix-r1';ev=ROOT/'output/qualification/batchfix-r1-2026-10-17';ev.mkdir(exist_ok=True)
    build=read(a.build/'build-report.json');assert build['passed'] and build['candidate_id']=='batchfix-r1'
    provenance=read(candidate/'source-provenance.json')
    for name,info in provenance.items():assert sha(candidate/name)==info['sha256']==build['source_files'][name]
    for name,info in build['artifacts'].items():assert sha(a.build/'payload'/name)==info['sha256']
    assert sha(candidate/'build.py')==build['build_script_sha256']
    admission=read(a.admission);assert admission['passed'] and admission['cases']==26 and admission['source_build_report_sha256']==sha(a.build/'build-report.json')
    assert sha(ROOT/'tools/test_batchfix_admission.py')==admission['test_sha256']
    reproduction_path=ROOT/'output/qualification/batchfix-r1-reproduction-2026-10-17.json';reproduction=read(reproduction_path)
    assert reproduction['passed'] and reproduction['first_build_report_sha256']==sha(a.build/'build-report.json') and reproduction['byte_identical_artifacts']==19
    report=a.model/'report.json';model=None
    if not a.pending:
        model=read(report);assert model['passed'] and model['source_build_report_sha256']==sha(a.build/'build-report.json')
        assert sha(ROOT/'tools/qualify_batchfix_candidate.py')==model['test_sha256']
        assert model['persistent_model_devices_unchanged'] and model['serial_disabled']
        archive=ev/'validated-build';assert not archive.exists();shutil.copytree(a.build,archive)
        for name in ['qualify_batchfix_candidate.py','test_batchfix_admission.py','checkpoint_batchfix_candidate.py']:shutil.copyfile(ROOT/'tools'/name,ev/name)
        save(ev/'candidate-artifact-pin.json',dict(candidate_id='batchfix-r1',generation=48,build_report_sha256=sha(a.build/'build-report.json'),artifacts=build['artifacts'],source_files=build['source_files'],installation_permitted=False,release_qualified=False))
    freeze=read(ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    for name,digest in freeze['artifact_hashes'].items():assert sha(ROOT/'BUILD/v2-beta35-candidate'/name)==digest
    assert sha(ROOT/'BUILD/v2-beta35-candidate/build.json')==freeze['build_sha256']
    prior_zips={'str8n-2.0b35-review.zip':'dc7c854f71852a853eac48dbf0070560feb64c8c47df0441d496a5062d7afa1f','str8n-2.0b35-B-target-review-2026-10-17-r2.zip':'2333a9deade33c6b00064625454e62d43c0057b9e0c9b1985526aed3dcee031a'}
    for name,digest in prior_zips.items():assert sha(ROOT/'output/releases'/name)==digest
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==freeze['active_rtc_baseline_sha256']
    campaign=read(Path(active['campaign_state']));run=Path(campaign['soak_run']);soak=read(run/'status.json');assert soak['state']=='running' and set(campaign['powered_off_boards'])=={'2205','2604','2609'}
    sym=read(a.build/'symbols.json');assert sym['xip/utilities']['B29_ENGINE']==0xd0ea
    progress=read(a.model/'progress.json') if (a.model/'progress.json').exists() else []
    result=dict(candidate_id='batchfix-r1',display_version='2.0bf1',generation=48,clock_version='1.11',updated_utc=datetime.now(timezone.utc).isoformat(),
        status='offline_model_running' if a.pending else 'initial_offline_native_CLOCK_BATCH_fix_models_passed',
        source_directory=str(candidate),source_provenance_sha256=sha(candidate/'source-provenance.json'),derivation_sha256=sha(candidate/'derivation.json'),
        build_report=str((a.build/'build-report.json').resolve()),build_report_sha256=sha(a.build/'build-report.json'),fresh_links=len(build['compiled']),candidate_artifacts=len(build['artifacts']),
        model_directory=str(a.model.resolve()),model_report_sha256=None if a.pending else sha(report),model_cases_passed=len(progress) if a.pending else model['cases'],
        explicitly_reused_model_cases=None if a.pending else model['reused_completed_case_count'],fresh_model_cases=None if a.pending else model['fresh_case_count'],
        admission_report=str(a.admission.resolve()),admission_report_sha256=sha(a.admission),admission_cases=26,
        independent_source_reproduction=dict(report=str(reproduction_path),sha256=sha(reproduction_path),fresh_links_per_build=27,byte_identical_artifacts=19),
        beta35_payloads_and_scoped_review_unchanged=True,protected_baseline_sha256=active['baseline_index_sha256'],prior_review_archives=prior_zips,
        soak_observation=dict(run=str(run),pid=soak['pid'],state=soak['state'],passed_units=soak['passed_units'],completed_cycles=soak['completed_cycles'],worker_unchanged=True),
        failed_model_evidence=['output/qualification/batchfix-r1-model-2026-10-17','output/qualification/batchfix-r1-model-2026-10-17-debug','output/qualification/batchfix-r1-model-2026-10-17-r2','output/qualification/batchfix-r1-model-2026-10-17-r3'],
        legacy_marker_harness_correction='Legacy A leaves unused RAM marker 5A, not zero; require disabled capability (neither B9 nor BA). Original failure retained, 18 already-passed cases explicitly attested/reused; source firmware and fixture inputs unchanged.',
        retained_assembler_failure='tmp/bfx4/s/xip/utilities.log.json: long-branch expansion needed after exact CLOCK admission was added',
        model_scope='Bounded fake-device A/B/mixed-component handoff, query/error/cancel, capability and admission checks; no hardware or migration route qualification',
        remaining=['Broader candidate regression and review before any release qualification','Both-slot migration/install/restoration and interruption qualification are separate work','Hardware/native/electrical and long-term acceptance remain unqualified; no board access authorized'],
        board_access=False,clock_trim_settings_changed=False,deferred=['ACIA','crypto'],hardware_qualified=False,installation_permitted=False,release_qualified=False)
    save(ev/'status.json',result);save(ROOT/'output/qualification/batchfix-r1-current.json',dict(candidate_id='batchfix-r1',report=str(ev/'status.json'),report_sha256=sha(ev/'status.json'),status=result['status'],installation_permitted=False,release_qualified=False))
    save(candidate/'candidate-state.json',dict(candidate_id='batchfix-r1',status=result['status'],owner_local_evidence=str(ev/'status.json'),owner_local_evidence_sha256=sha(ev/'status.json'),installation_permitted=False,release_qualified=False))
    print(json.dumps(dict(status=result['status'],model_cases=result['model_cases_passed'],admission_cases=26,source=str(candidate),soak=result['soak_observation']),indent=2))
if __name__=='__main__':main()
