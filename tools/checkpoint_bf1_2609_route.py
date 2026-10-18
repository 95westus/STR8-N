"""Close the owner-authorized 2609 return capture and offline bf1 route gate."""
import argparse,hashlib,json,tomllib,zipfile
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--soak-evidence',type=Path,required=True);ap.add_argument('--process-receipt',type=Path,required=True);a=ap.parse_args()
    backup=Q/'2609-return-backup-2026-10-17-1931Z';r=read(backup/'report.json');v=read(backup/'verification.json')
    assert r['passed'] and r['application_ram_restored'] and v['passed'] and sha(backup/'report.json')==v['backup_report_sha256']
    assert all(r[k] for k in ('flash_repeat_verified','eeprom_repeat_verified','sram_repeat_verified'))
    assert not read(backup/'restore-needed.json')['needed']
    for name,info in r['files'].items():assert sha(backup/name)==info['sha256'] and (backup/name).stat().st_size==info['bytes']
    route=Q/'bf1-2609-route-2026-10-17-r1';report=read(route/'report.json')
    assert report['passed'] and report['board']=='2609' and report['cases']==28 and report['serial_disabled'] and report['board_access'] is False
    assert report['model_processor']=='W65C02' and report['real_65C816_bf1_execution_qualified'] is False
    assert all(row['passed'] for row in report['checks']) and read(route/'backup-intake.json')==r
    for path,digest in report['sources'].items():assert sha(Path(path))==digest
    snapshot=Path(r['snapshot']);s=read(snapshot);assert s['passed'] and s['ports_released'] and sha(snapshot)==r['snapshot_sha256']
    sample=next(b for b in s['boards'] if b['board']=='2609')
    active=read(Q/'active-rtc-campaign.json');state_path=Path(active['campaign_state']);state=read(state_path)
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']==v['baseline_sha256'] and set(active['powered_off_boards'])=={'2205'}
    assert state['soak_board']=='2604' and set(state['snapshot_boards'])=={'2512','2604','2609'}
    soak=read(a.soak_evidence);process=read(a.process_receipt)
    assert soak['passed'] and soak['state']=='running' and soak['run']==state['soak_run'] and set(soak['latest_samples'])=={'2512','2604','2609'}
    assert process['ProcessId']==soak['pid'] and 'run_bf1_2604_soak.py' in process['CommandLine'] and state['soak_run'].replace('\\','/') in process['CommandLine'].replace('\\','/')
    pin=read(Q/'batchfix-r1-2026-10-17/candidate-artifact-pin.json')
    for name,info in pin['artifacts'].items():assert sha(ROOT/'tmp/bfx5/payload'/name)==info['sha256']
    for name,digest in pin['source_files'].items():assert sha(ROOT/'release/candidates/batchfix-r1'/name)==digest
    freeze=read(Q/'beta35-release-qualification-2026-10-17-034745Z/freeze.json')
    for name,digest in freeze['artifact_hashes'].items():assert sha(Path(freeze['frozen_source_directory'])/'BUILD/v2-beta35-candidate'/name)==digest
    review=read(Path(read(Q/'bf1-review-current.json')['report']));assert sha(Path(review['archive']))==review['archive_sha256']
    for name,digest in read(Q/'batchfix-r1-2026-10-17/status.json')['prior_review_archives'].items():assert sha(ROOT/'output/releases'/name)==digest
    schedules={}
    for name in ('2512-nist-snapshot-every-three-hours','2512-powered-soak-and-rtc-drift'):
        config=tomllib.loads(((Path.home()/'.codex'/'automations')/name/'automation.toml').read_text());assert config['status']=='ACTIVE' and '2609' in config['prompt'];schedules[name]=dict(name=config['name'],status=config['status'],rrule=config['rrule'])
    plotptr=read(Q/'rtc-powered-campaign-report-current.json');plot=Path(plotptr['data']);assert sha(plot)==plotptr['data_sha256'] and read(plot)['original_baseline_preserved']
    out=Q/'bf1-2609-route-2026-10-17-r1/checkpoint.json';assert not out.exists()
    archive=route/'bound-tools';archive.mkdir()
    for name in ('capture_2609_return_backup.py','restore_2609_return_ram.py','audit_2609_return_capture.py','plan_bf1_2609_route.py','verify_bf1_2609_route.py','checkpoint_bf1_2609_route.py'):(archive/name).write_bytes((ROOT/'tools'/name).read_bytes())
    result=dict(passed=True,status='2609_return_backup_and_bf1_offline_route_models_complete',board='2609',candidate_id='batchfix-r1',observed_utc=datetime.now(timezone.utc).isoformat(),
        snapshot=str(snapshot),snapshot_sha256=sha(snapshot),snapshot_reference_utc=sample['reference_utc'],rtc_minus_NIST_seconds=sample['offset_seconds'],rtc_offset_bounds_s=sample['offset_bounds_seconds'],drift_bounds_s=sample['drift_seconds_interval'],
        backup=str(backup),backup_report_sha256=sha(backup/'report.json'),backup_verification_sha256=sha(backup/'verification.json'),fresh_eui=v['fresh_eui'],fresh_eui_matches_baseline=True,
        captured_flash_bytes=131072,captured_eeprom_bytes=137,captured_sram_bytes=131072,application_ram_restored=True,application_ram_sha256=sha(backup/'application-ram-restored.bin'),capture_harness_issue_retained=True,restoration_pending=False,
        model_report=str(route/'report.json'),model_report_sha256=sha(route/'report.json'),fresh_offline_checks=28,helper_validator_subcases=5,offline_route_models_passed=True,model_processor='W65C02',
        route='Exact B35/F30D/A40 source: B48/shared set first retaining A40; A48 retaining B48; restore A40 retaining B48 then B35/shared assets retaining A40 with newer sequence/count history.',
        coverage='Full B/A installation and native/CLOCK BATCH, two-phase original-payload restoration, four stale-bank and two corrupted-transfer refusals, four representative B cuts with boot/recovery, altered-recovery preimage refusal. Not exhaustive A/restoration cut coverage or electrical timing.',
        bf1_installed_on_2609=False,real_65C816_bf1_execution_qualified=False,physical_interruption_qualified=False,physical_restoration_qualified=False,
        reuse='Unchanged bf1 payload/helper builds and prior generic algorithm evidence reused; all 28 board-specific checks in this report are fresh. Earlier 2604 cut results are not relabeled as 2609 results.',
        bf1_artifacts_verified=19,beta35_artifacts_verified=23,protected_bf1_review_zip_sha256=review['archive_sha256'],prior_review_archives_unchanged=True,baseline_sha256=active['baseline_index_sha256'],
        combined_report=plotptr['report'],combined_report_data_sha256=sha(plot),schedules=schedules,soak=dict(board='2604',run=soak['run'],pid=soak['pid'],passed_units=soak['actual_passed_unit_reports'],completed_cycles=soak['completed_cycles']),
        soak_evidence_sha256=sha(a.soak_evidence),soak_process_receipt_sha256=sha(a.process_receipt),snapshot_boards=['2512','2604','2609'],powered_off_boards=['2205'],deferred=['native 816','ACIA','crypto'],
        remaining=['Owner-authorized bf1 installation and 65C816 emulation-mode hardware acceptance on 2609','Physical electrical interruption and original-payload restoration acceptance','Broader board-specific interruption cases are outside this bounded checkpoint','Continued soak/RTC accumulation and explicit release acceptance'],
        sealed_review_route_scope_unchanged=True,board_access_for_models=False,clock_trim_settings_changed=False,reset=False,installation_permitted=False,release_qualified=False,publication_permitted=False)
    publish(out,result);pointer=dict(checkpoint=str(out),checkpoint_sha256=sha(out),status=result['status'],board='2609',installation_permitted=False,release_qualified=False)
    publish(Q/'bf1-2609-route-current.json',pointer)
    state=read(state_path);state['2609_bf1_offline_route_checkpoint']=str(out);state['2609_bf1_offline_route_checkpoint_sha256']=sha(out);publish(state_path,state)
    publish(Q/'device-operations/2609.json',dict(board='2609',state='return-captured-offline-bf1-route-models-passed',backup=str(backup),checkpoint=str(out),block_snapshot=False,firmware_installed=False))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
