"""Register the proven owner recovery as a separate segment; no board access."""
import json,time
from pathlib import Path
from rtc_campaign_segments import read,sha,recovery_segment
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'

def main():
    active=read(Q/'active-rtc-campaign.json');path=Q/'2609-RTC-owner-recovery-2026-10-18-r1/report.json';r=read(path)
    tests=Q/'2609-RTC-recovery-segment-tests-2026-10-18-r1.json'
    assert read(tests)['passed'] and read(tests)['cases']==8
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    state_path=Path(active['campaign_state']);state=read(state_path)
    assert not state.get('rtc_measurement_segments',{}).get('2609')
    segment=dict(id='2609-post-RTC-recovery-2026-10-18-r1',anchor_report=str(path),anchor_sha256=sha(path),
        original_baseline_sha256=active['baseline_index_sha256'],start_unix=r['baseline_reference_unix'],
        reason='Explicit owner-authorized NIST sync after stopped/invalid RTC; no rate across SET')
    state.setdefault('rtc_measurement_segments',{})['2609']=segment
    assert recovery_segment(state,'2609',active['baseline_index_sha256'])
    failure=state['rtc_continuity_breaks']['2609']
    assert sha(Path(failure['status_report']))==failure['status_sha256']
    failure.update(resolved=True,resolution='Clock operation recovered; original continuity failure and uncertain root cause retained',
        recovery_report=str(path),recovery_report_sha256=sha(path),reset_or_time_restore_authorized=True,
        original_baseline_sha256=active['baseline_index_sha256'],migration_preservation_pass_inferred=False)
    assignment=state['2609_windows_migration_assignment']
    assignment.update(status='Firmware tools complete, final bf1 boot passed; owner-recovered RTC-only, no workload restart',
        hardware_checkpoint=str(Q/'bf1-2609-windows-firmware-checkpoint-2026-10-18-r1.json'))
    previous=Q/'2609-RTC-owner-recovery-2026-10-18-r1/campaign-state-before-registration.json'
    assert not previous.exists();publish(previous,read(state_path));publish(state_path,state)
    active['explicit_RTC_recoveries']={'2609':dict(report=str(path),sha256=sha(path),new_measurement_segment=segment['id'])}
    publish(Q/'active-rtc-campaign.json',active)
    work_path=Q/'bf1-distribution-work-state.json';work=read(work_path)
    publish(path.parent/'distribution-state-before-registration.json',work)
    job=work['2609_windows_hardware'] if '2609_windows_hardware' in work else None
    if job is None:
        job=next(value for value in work.values() if isinstance(value,dict) and 'RTC_recovery_authorized' in value)
    job.update(RTC_recovery_authorized=True,RTC_recovery_decision_pending=False,RTC_fault_unresolved=False,
        RTC_qualification_failed_and_unresolved=True,RTC_recovery_report=str(path),RTC_measurement_segment=segment['id'],
        RTC_current_clock_recovered=True,beta4_staging_passed=True,
        blocker='Current clock recovered; original migration RTC preservation/root-cause qualification and portable live/recovery gates remain open',
        firmware_testing_checkpoint='Both firmware tools completed; final bf1 boot passed; RAM written/acknowledged without host readback; RTC recovered with separate owner authorization',
        next_gate='Offline Windows/Linux live launcher/recovery qualification and RTC preservation cause review; no hardware operation authorized by offline tasks')
    publish(work_path,work)
    plan_path=Q/'bf1-tonight-publication-plan.json';plan=read(plan_path)
    publish(path.parent/'publication-plan-before-registration.json',plan)
    plan['tools']['check_bf1_acceptance.py']=sha(ROOT/'tools/check_bf1_acceptance.py')
    plan.update(publication_hold=True,publication_automation_paused=True,publication_automation_status='PAUSED',
        RTC_operational_recovery_report=str(path),RTC_operational_recovery_report_sha256=sha(path),
        RTC_preservation_qualification_still_required=True)
    publish(plan_path,plan)
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['state']=='RTC-recovered-segment-registration' and guard['block_snapshot']
    guard.update(state='RTC-only-post-owner-recovery',block_snapshot=False,rtc_continuity_broken=True,
        current_RTC_valid=True,measurement_segment=segment['id'],no_workload_soak_restart=True,
        reason='Final bf1 booted; authorized RTC recovery passed. Sample only within new segment; no automatic setters.')
    publish(marker,guard)
    publish(path.parent/'registration.json',dict(passed=True,board='2609',segment=segment,
        original_baseline_preserved=True,tests_sha256=sha(tests),board_access=False,
        sampling_unblocked=True,publication_held=True,registered_unix=time.time()))
    print('PASS separate 2609 RTC segment registered; original baseline retained; sampling unblocked; publication held')

if __name__=='__main__':main()
