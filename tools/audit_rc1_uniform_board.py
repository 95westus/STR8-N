"""Audit closed uniform-upgrade routes and full preservation from files only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=('2604','2609'),required=True)
    a=ap.parse_args();run=a.run.resolve();assert run.is_relative_to(Q)
    ad=READ(run/'admission-v2.json');kit=Path(ad['kit']);board=a.board;bindings={}
    def proof(path):
        path=Path(path);bindings[path.relative_to(run).as_posix()]=SHA(path);return READ(path)
    def exited(folder):
        value=proof(folder/'report.json');identity=proof(folder/'process-identity.json');exit_proof=proof(folder/'process-exit.json')
        assert value['passed'] and identity['passed'] and exit_proof['actual_exit_verified'] and exit_proof['exit_code']==0
        assert value['native_debugging'] is False and value['RTC_drift_in_release_qualification'] is False
        assert value['pid']==identity['pid']==exit_proof['pid']
        assert exit_proof['source_report_sha256']==SHA(folder/'report.json')
        assert not any(value.get(k) for k in ('failure','restoration_failure','application_RAM_restore_pending','original_RAM_restore_pending','physical_reset_pending'))
        return value
    for group in ('source_sha256','evidence_sha256'):
        for path,digest in ad[group].items():assert SHA(path)==digest,path
    sys.path.insert(0,str(kit/'engine'));import runtime as r
    assert Path(r.__file__).resolve()==(kit/'engine/runtime.py').resolve()
    original=Path(ad['original_backups'][board]);initial=proof(original/'report.json')
    assert initial['passed'] and initial['RAM_restored'] and initial['full_RAM_rereads']==2
    trial=Path(ad['trial_roots'][board]);model=proof(trial/'report.json');assert model['passed']
    routes={};total_hits=0
    for phase,source in [('migrate-wdc','wdcmonv2-'+('65C02' if board=='2604' else '65C816')),('migrate-beta4','beta4')]:
        folder=run/board/'live-v2'/phase
        if not folder.exists():folder=run/board/'live'/phase
        value=exited(folder);workflow=proof(folder/'workflow/report.json')
        assert workflow['passed'] and workflow['source_profile']==source and workflow['target_profile']=='v1g'
        assert value['workflow_receipt_sha256']==SHA(folder/'workflow/report.json')
        expected=next(row for row in model['checks'] if row['name']==phase)
        assert workflow['transaction_device_verified'] and workflow['host_memory_readbacks']
        assert workflow['transfers_completed']==expected['transfers'] and workflow['all_four_banks_verified']
        assert workflow['RAM_restored'] and workflow['full_RAM_rereads']==2
        assert value['full_original_RAM_restored'] and value['full_original_RAM_rereads']==2
        assert value['original_RAM_sha256']==SHA(original/'capture/application-ram.bin')
        assert value['all_four_target_banks_verified'] and value['settings_verified_against_plan']
        assert set(value['slots'])=={'A','B'}
        for slot in value['slots'].values():
            assert slot['passed'] and slot['smoke_cases']==4 and slot['breakpoint_hits']==16 and slot['C_S_N_D_M_U']
            total_hits+=slot['breakpoint_hits']
        if board=='2609':
            for when in ('mode_before_smoke','mode_after_smoke'):
                mode=value[when];assert mode['E1_verified'] and mode['DBR']==mode['PBR']==mode['direct_page']==0 and not mode['native_debugging']
        actual_plan=folder/'workflow/plan';planned=trial/phase
        assert SHA(actual_plan/'installer-model-only.s19')==expected['installer_sha256']==SHA(planned/'installer-model-only.s19')
        assert READ(actual_plan/'plan.json')['transaction']==READ(planned/'plan.json')['transaction']
        assert workflow['final_flash_sha256']==[SHA(planned/f'expected-b{n}.bin') for n in range(4)]
        routes[source]=dict(passed=True,monitor_slots=['A','B'],smoke_cases=8,breakpoint_hits=32,
            transfers=workflow['transfers_completed'],original_RAM_rereads=2,actual_worker_exit_verified=True,
            host_revision=2 if folder.parent.name=='live-v2' else 1,
            monitored_seconds=(datetime.fromisoformat(value['finished_utc'])-datetime.fromisoformat(value['started_utc'])).total_seconds())
    if board=='2604':
        old=proof(run/board/'live/stage-beta4/report.json');old_exit=proof(run/board/'live/stage-beta4/process-exit.json')
        correction=proof(run/board/'live-v2/migrate-beta4/source-admission-audit.json')
        assert not old['passed'] and old_exit['actual_exit_verified'] and old_exit['exit_code']==1
        assert old['transaction_device_verified'] and correction['passed'] and correction['corrected_prior_post_boot_source_check']
        assert correction['original_failed_report_sha256']==SHA(run/board/'live/stage-beta4/report.json')
    final_dir=run/board/'final';final=exited(final_dir);current_dir=run/board/'current-v2';current=exited(current_dir)
    no_write=proof(current_dir/'independent-no-write-audit.json')
    assert no_write['passed'] and no_write['no_RAM_loader_or_execution_commands'] and no_write['no_flash_programming_commands']
    assert current['already_current'] and current['all_four_banks_verified'] and current['application_RAM_unchanged'] and not current['flash_written']
    before=[(original/f'capture/b{n}.bin').read_bytes() for n in range(4)]
    after=[(final_dir/f'capture/b{n}.bin').read_bytes() for n in range(4)]
    for n in range(4):
        assert after[n]==(final_dir/f'capture/b{n}-repeat.bin').read_bytes()==(trial/f'migrate-beta4/expected-b{n}.bin').read_bytes()
    assert all(before[n]==after[n] for n in (0,1,2))
    assert before[3][:0x4000]==after[3][:0x4000] and before[3][0x6000:]==after[3][0x6000:]
    _,_,old_row,_=r.clean_journal(before);_,_,new_row,_=r.clean_journal(after)
    assert old_row[8:24]==new_row[8:24]
    initial_counts=[int.from_bytes(old_row[24+3*n:27+3*n],'little') for n in range(32)]
    final_counts=[int.from_bytes(new_row[24+3*n:27+3*n],'little') for n in range(32)]
    planned_counts=READ(trial/'migrate-beta4/plan.json')['transaction']['reserved_counts']
    assert final_counts==planned_counts and all(b>=a for a,b in zip(initial_counts,final_counts))
    erases=sum(len(READ(trial/phase/'plan.json')['transaction']['planned_erase_order']) for phase in ('stage-wdc','migrate-wdc','stage-beta4','migrate-beta4'))
    assert sum(final_counts)-sum(initial_counts)==erases
    ram=(original/'capture/application-ram.bin').read_bytes()
    assert len(ram)==25344 and (final_dir/'capture/application-ram.bin').read_bytes()==ram
    assert final['RAM_restored'] and final['full_RAM_rereads']==2 and final['flash_repeat_verified'] and final['flash_unchanged']
    assert not final['flash_written'] and not final['persistent_devices_written']
    for device,size in [('eeprom',137),('SRAM',131072)]:
        data=(original/(device+'.bin')).read_bytes()
        assert len(data)==size and data==(original/(device+'-repeat.bin')).read_bytes()
        assert data==(final_dir/(device+'.bin')).read_bytes()==(final_dir/(device+'-repeat.bin')).read_bytes()
        assert initial[device+'_sha256']==final[device+'_sha256']==hashlib.sha256(data).hexdigest()
    assert initial['active_page']==final['active_page']==(0xb0 if board=='2604' else 0xa0)
    assert initial['clock_controls_before']==initial['clock_controls_after']==final['clock_controls_before']==final['clock_controls_after']
    if board=='2609':assert initial['E1_verified'] and final['E1_verified']
    assert current['final_flash_sha256']==final['all_four_bank_sha256']==r.hashes(after)
    report=dict(passed=True,board=board,routes=routes,persistent_breakpoint_hits=total_hits,
        original_RAM_restored=True,full_original_RAM_bytes=25344,final_RAM_rereads=2,
        EEPROM_137_bytes_unchanged=True,SRAM_131072_bytes_unchanged=True,original_settings_unchanged=True,
        original_MON_restored=True,original_flash_unchanged_except_exact_planned_wear_journals=True,
        exact_planned_final_wear_counts=True,reserved_erase_attempts=erases,already_current_no_write_verified=True,
        actual_workers_exited=True,host_protocol_failure_retained_and_resolved=board=='2604',
        actual_firmware_failures=0,host_protocol_qualification_failures=1 if board=='2604' else 0,
        native_debugging=False,native_applications=False,RTC_drift_in_release_qualification=False,
        board_access_by_auditor=False,evidence_sha256=bindings,auditor_sha256=SHA(__file__),
        audited_utc=datetime.now(timezone.utc).isoformat())
    path=run/board/'board-final-audit.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='evidence_sha256'},indent=2))


if __name__=='__main__':main()
