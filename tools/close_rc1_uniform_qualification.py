"""Close both-board uniform qualification from sealed evidence; no board access."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
IMAGE='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
REGISTER='fccf71436d7711e47ac852a6b2edcc02af0908dcc188b3908b3b742a9f69676d'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True)
    a=ap.parse_args();run=a.run.resolve();assert run.is_relative_to(Q) and not (run/'report.json').exists()
    ad=READ(run/'admission-v2.json');auth=READ(run/'owner-authorization.json')
    assert auth['owner_authorized'] and auth['publish_only_after_qualification']
    assert not auth['native_debugging'] and not auth['native_applications'] and not auth['RTC_drift_in_release_qualification']
    assert SHA(run/'owner-authorization.json')==ad['owner_authorization_sha256']
    for group in ('source_sha256','evidence_sha256'):
        for path,digest in ad[group].items():assert SHA(path)==digest,path
    kit=Path(ad['kit']);base=Path(ad['CPU_proof_kit']);manifest=READ(kit/'uniform-manifest.json')
    assert SHA(kit/'uniform-manifest.json')==ad['uniform_manifest_sha256']
    for name in READ(base/'uniform-manifest.json')['files']:
        if name!='upgrade.py':assert (base/name).read_bytes()==(kit/name).read_bytes(),name
    assert manifest['host_protocol_provenance']['changed_runtime_members']==['upgrade.py']
    model=Q/'rc1-uniform-model-development-r4/report.json';bootstrap=Q/'rc1-uniform-bootstrap-development-r3/report.json'
    host=Q/'rc1-uniform-host-workflow-development-r2.json'
    assert READ(model)['passed'] and READ(model)['actual_installer_executions']==24
    assert READ(bootstrap)['passed'] and READ(bootstrap)['actual_complete_installer_executions']==8
    assert READ(host)['passed'] and READ(host)['cases']==12 and READ(host)['uniform_manifest_sha256']==ad['uniform_manifest_sha256']
    assert READ(Q/'serial-coordination/owner.json')['kind']=='idle'
    boards={};direct=fixtures=0;route_seconds=0.;staging_seconds=0.
    for board in ('2604','2609'):
        audit=READ(run/board/'board-final-audit.json');assert audit['passed'] and audit['actual_workers_exited']
        for name,digest in audit['evidence_sha256'].items():assert SHA(run/name)==digest,name
        marker=READ(Q/'device-operations'/f'{board}.json')
        assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
        assert not any(marker.get(k) for k in ('uniform_upgrade_worker_active','application_RAM_restore_pending','physical_reset_pending','block_snapshot','current_soak_worker_pid'))
        assert marker['uniform_upgrade_board_qualification_passed'] and marker['uniform_upgrade_board_audit_sha256']==SHA(run/board/'board-final-audit.json')
        assert len(audit['routes'])==2 and audit['persistent_breakpoint_hits']==64 and audit['reserved_erase_attempts']==90
        private=READ(Path(ad['trial_roots'][board])/'report.json')
        assert private['passed'] and len(private['checks'])==4 and all(c['passed'] for c in private['checks'])
        boards[board]=dict(audit_sha256=SHA(run/board/'board-final-audit.json'),routes=audit['routes'],
            original_RAM_bytes=25344,original_RAM_restored=True,EEPROM_bytes_preserved=137,SRAM_bytes_preserved=131072,
            settings_preserved=True,original_MON_restored=True,reserved_erase_attempts=90,
            already_current_no_write_verified=True,E1_verified=board=='2609')
        direct+=sum(v['transfers'] for v in audit['routes'].values())
        route_seconds+=sum(v['monitored_seconds'] for v in audit['routes'].values())
        for phase in ('stage-wdc','stage-beta4'):
            folder=run/board/'live-v2'/phase
            if not folder.exists():folder=run/board/'live'/phase
            value=READ(folder/'report.json');ex=READ(folder/'process-exit.json')
            assert ex['actual_exit_verified'] and ex['source_report_sha256']==SHA(folder/'report.json')
            assert value['transaction_device_verified'] and value['transfers_completed']==(23 if phase=='stage-wdc' else 22)
            if board=='2604' and phase=='stage-beta4':
                assert not value['passed'] and ex['exit_code']==1
                assert READ(run/board/'live-v2/migrate-beta4/source-admission-audit.json')['corrected_prior_post_boot_source_check']
            else:assert value['passed'] and ex['exit_code']==0
            fixtures+=value['transfers_completed']
            staging_seconds+=(datetime.fromisoformat(value['finished_utc'])-datetime.fromisoformat(value['started_utc'])).total_seconds()
    assert direct==fixtures==90
    register=Q/'rc1-v1g-register-edits-qualification-r1-2026-10-20-225008Z/report.json';assert SHA(register)==REGISTER
    assert SHA(ROOT/'BUILD/rc1-debugger-v1g/firmware.bin')==IMAGE
    closed=datetime.now(timezone.utc)
    report=dict(passed=True,release_ready=True,target_firmware_sha256=IMAGE,
        qualified_uniform_manifest_sha256=ad['uniform_manifest_sha256'],CPU_proof_uniform_manifest_sha256=ad['CPU_proof_uniform_manifest_sha256'],
        host_protocol_revision=2,direct_physical_routes_passed=4,boards=boards,
        current_v1g_no_write_boards=['2604','2609'],new_host_checks=12,
        inherited_CPU_model_installer_executions=32,private_fixture_CPU_executions=8,
        CPU_models_inherited_with_exact_runtime_member_equivalence=True,
        inherited_R_register_edits_report_sha256=REGISTER,actual_firmware_failures=0,
        host_protocol_qualification_failures=1,host_protocol_failure_resolved=True,
        host_protocol_history='development-history-v2.json',monitor_terminal_state_correction='2604/current-v2/monitor-terminal-state-correction.json',
        both_full_original_RAM_restored=True,both_full_EEPROM_SRAM_preserved=True,all_workers_actual_exit_verified=True,
        direct_device_verified_transfers=direct,fixture_device_verified_transfers=fixtures,total_reserved_erase_attempts=180,
        direct_route_monitored_seconds=round(route_seconds,6),fixture_phase_monitored_seconds=round(staging_seconds,6),
        monitored_durations_include_owner_RESET_wait=True,new_continuous_soak_claimed=False,
        overall_qualification_elapsed_seconds=(closed-datetime.fromisoformat(auth['created_utc'])).total_seconds(),
        native_debugging=False,native_applications=False,RTC_drift_in_release_qualification=False,RTC_drift_is_promotion_gate=False,
        RTC_issue_deferred=True,intermediate_generation49=False,host_platform='Windows',
        supported_target_runtime=['65C02','65C816 E=1'],vendor_images_exported=False,private_backups_exported=False,
        electrical_power_failure_atomicity_claimed=False,board_access_during_closeout=False,
        admission_sha256=SHA(run/'admission-v2.json'),model_report_sha256=SHA(model),bootstrap_report_sha256=SHA(bootstrap),host_report_sha256=SHA(host),
        closed_utc=closed.isoformat(),closeout_source_sha256=SHA(__file__))
    (run/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    # Seal private evidence locally; only selected safe JSON projections enter a release.
    files={p.relative_to(run).as_posix():SHA(p) for p in sorted(run.rglob('*')) if p.is_file() and p.name!='final-checksums.json'}
    (run/'final-checksums.json').write_text(json.dumps(dict(passed=True,files=files,private_evidence_not_for_distribution=True),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
