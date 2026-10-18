"""Admit explicit, hash-bound post-recovery anchors without replacing baseline."""
import hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def recovery_segment(state,board,baseline_sha256):
    segment=state.get('rtc_measurement_segments',{}).get(board)
    if not segment:return None
    assert segment['original_baseline_sha256']==baseline_sha256
    path=Path(segment['anchor_report']);assert sha(path)==segment['anchor_sha256'],'Changed recovery anchor'
    r=read(path)
    assert r['board']==board and r['passed'] and r['clock_set_attempted'] and r['clock_advanced']
    assert r['original_baseline_sha256']==baseline_sha256 and r['ports_released']
    assert r['trim_steps']==-14 and r['control_register']==128 and r['oscillator_running'] and r['backup_enabled']
    auth=path.parent/'owner-authorization.json'
    assert sha(auth)==r['owner_authorization_sha256'] and read(auth)['owner_authorized']
    assert r['original_application_RAM_written'] and r['loader_acknowledged']
    assert all(x['status']==0 and x['raw'][7:9]==[128,14] for x in r['readings'])
    assert abs(r['final_reference_difference_s'])<=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s']
    assert segment['start_unix']==r['baseline_reference_unix']
    return dict(segment,anchor=r)

def segment_points(segment,root,baseline_index):
    """Only measurements against this anchor; no rate bridges an explicit SET."""
    r=segment['anchor'];points=[dict(time=r['baseline_reference_unix'],
        low=r['rtc_minus_reference_interval_s'][0],high=r['rtc_minus_reference_interval_s'][1],report=segment['anchor_report'])]
    for path in sorted(Path(root).glob('rtc-campaign-snapshot-*/summary.json')):
        summary=read(path)
        if not summary.get('passed'):continue
        for item in summary['boards']:
            if item['board']!=r['board'] or item.get('measurement_segment')!=segment['id']:continue
            assert summary['ports_released'] and item['application_ram_restored']
            assert Path(item['baseline_index'])==Path(baseline_index)
            rp=Path(item['report']);assert sha(rp)==item['report_sha256'];m=read(rp)
            assert m['passed'] and not m.get('clock_set_attempted',False)
            assert Path(m['compared_baseline'])==Path(segment['anchor_report'])
            assert item['trim_steps']==r['trim_steps'] and item['control_register']==r['control_register']
            assert m['baseline_reference_unix']>segment['start_unix']
            assert abs(m['final_reference_difference_s'])<=m['reference_uncertainty_s']+m['final_reference_check']['estimated_reference_uncertainty_s']
            lo,hi=m['rtc_minus_reference_interval_s']
            points.append(dict(time=m['baseline_reference_unix'],low=lo,high=hi,report=str(rp)))
    return sorted(points,key=lambda x:x['time'])
