"""Offline recovery admission and no-cross-SET-rate regression checks."""
import copy,json,tempfile
from pathlib import Path
from atomic_json import publish
from rtc_campaign_segments import recovery_segment,segment_points,sha,read
from check_bf1_acceptance import rate_gate,apply_known_rtc_failure
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'

def main():
    active=read(Q/'active-rtc-campaign.json');path=Q/'2609-RTC-owner-recovery-2026-10-18-r1/report.json';r=read(path)
    segment=dict(id='2609-post-RTC-recovery-2026-10-18-r1',anchor_report=str(path),anchor_sha256=sha(path),
        original_baseline_sha256=active['baseline_index_sha256'],start_unix=r['baseline_reference_unix'])
    state=dict(rtc_measurement_segments={'2609':segment});checks=[]
    admitted=recovery_segment(state,'2609',active['baseline_index_sha256']);assert admitted
    checks.append('Actual hash-bound recovery and owner authorization admitted')
    assert recovery_segment(state,'2604',active['baseline_index_sha256']) is None
    checks.append('2604 remains on its unchanged original measurement segment')
    bad=copy.deepcopy(state);bad['rtc_measurement_segments']['2609']['anchor_sha256']='0'*64
    try:recovery_segment(bad,'2609',active['baseline_index_sha256'])
    except AssertionError:checks.append('Altered recovery anchor refused')
    else:raise AssertionError('Tampered anchor admitted')
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
        root=Path(tmp);points=segment_points(admitted,root,active['baseline_index'])
        # Deliberately extreme older values are irrelevant: only segment-bound summaries enter.
        folder=root/'rtc-campaign-snapshot-old';folder.mkdir()
        publish(folder/'summary.json',dict(passed=True,boards=[dict(board='2609',measurement_segment='old')]))
        assert segment_points(admitted,root,active['baseline_index'])==points and len(points)==1
        checks.append('Older pre-SET measurements excluded rather than treated as new drift')
        policy=read(Path(read(Q/'bf1-acceptance-policy-current.json')['policy']))
        gate=rate_gate(points,policy['RTC']);assert gate['status']=='pending-duration' and gate['rate_interval_ppm'] is None
        checks.append('Recovery anchor alone remains pending; no invented rate or acceptance pass')
        m=copy.deepcopy(r);m.update(clock_set_attempted=False,baseline_reference_unix=r['baseline_reference_unix']+10800,
            compared_baseline=str(path),rtc_minus_reference_interval_s=[.1,.7])
        report=folder/'new-report.json';publish(report,m)
        item=dict(board='2609',measurement_segment=segment['id'],baseline_index=active['baseline_index'],
            report=str(report),report_sha256=sha(report),trim_steps=-14,control_register=128,application_ram_restored=True)
        publish(folder/'summary.json',dict(passed=True,ports_released=True,boards=[item]))
        points=segment_points(admitted,root,active['baseline_index']);assert len(points)==2
        gate=rate_gate(points,policy['RTC']);assert gate['span_hours']==3 and gate['status']=='pending-duration'
        checks.append('Future same-segment samples yield only within-segment rate bounds')
        m['compared_baseline']='wrong-anchor';publish(report,m);item['report_sha256']=sha(report)
        publish(folder/'summary.json',dict(passed=True,ports_released=True,boards=[item]))
        try:segment_points(admitted,root,active['baseline_index'])
        except AssertionError:checks.append('Wrong comparison anchor refused')
        else:raise AssertionError('Wrong baseline admitted')
    missing=dict(rtc_continuity_breaks={'2609':dict(resolved=True,original_baseline_sha256=active['baseline_index_sha256'])})
    try:apply_known_rtc_failure('2609',{},missing)
    except AssertionError:checks.append('Fault cannot be cleared without an admitted recovery segment')
    else:raise AssertionError('Unproven resolution admitted')
    active_state=read(Path(active['campaign_state']))
    if active_state.get('rtc_measurement_segments',{}).get('2609'):
        bad=copy.deepcopy(active_state);bad['rtc_continuity_breaks']['2609']['status_sha256']='0'*64
        try:apply_known_rtc_failure('2609',{},bad)
        except AssertionError:checks.append('Recovered status still verifies retained failure evidence')
        else:raise AssertionError('Altered retained fault evidence admitted')
    output=Q/'2609-RTC-recovery-segment-tests-2026-10-18-r2.json';assert not output.exists()
    publish(output,dict(passed=True,cases=len(checks),checks=checks,board_access=False,
        anchor_sha256=sha(path),segment_module_sha256=sha(ROOT/'tools/rtc_campaign_segments.py')))
    print('PASS',len(checks),'RTC recovery segment regression checks; no board access')

if __name__=='__main__':main()
