"""Add receipt-verified cooperative calibration observations to fleet reporting."""
import hashlib
import json
from pathlib import Path

def merged_points(state, points):
    path=Path(state.get('calibration_campaigns',{}).get('2604',{}).get('control',''))
    if not path.is_file():
        return points
    control=json.loads(path.read_text())
    # Never fit observations from an earlier clock/trim segment into a new one.
    if control.get('segment_boundary')!=state.get('segment_boundaries',{}).get('2604'):
        return points
    paths={Path(control['start_report']),Path(control['last_report'])}
    paths.update(path.parent.glob('2604-ntp-sample-*/report.json'))
    receipts={}
    for p in sorted(paths):
        r=json.loads(p.read_text())
        if not (r.get('board')=='2604' and r.get('passed') and r.get('profile')=='2604-NTP-COOP-T2-1'):
            continue
        if not all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_hooks_preserved','all_flash_banks_unchanged','original_prompt_restored','port_released')):
            continue
        after=r.get('after',{})
        if all(k in after for k in ('time','UTC','low','high','mid')):
            receipts[after['time']]=(p,r,after)
    result=list(points)
    for point in control['points']:
        entry=receipts.get(point['time'])
        if entry is None:
            continue
        p,r,after=entry
        assert all(point[k]==after[k] for k in ('time','UTC','low','high','mid')),f'Calibration point differs from saved receipt: {p}'
        raw=bytes.fromhex(r['before_raw']) if r.get('mode')=='sample' else None
        if raw is not None:
            assert raw[8]==control['trim_raw'] and not raw[3]&16
            ctrl=raw[7]
        else:
            ctrl=r['original_control']
        value=dict(board='2604',time=point['time'],UTC=point['UTC'],low=point['low'],high=point['high'],offset=point['mid'],trim_raw=control['trim_raw'],trim=-(control['trim_raw']&127) if not control['trim_raw']&128 else control['trim_raw']&127,control=ctrl,trim_verified=True,control_verified=True,PF_latched=False,events=[],report=str(p),report_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),capture_profile='2604-NTP-COOP-T2-1',source='Dedicated cooperative NIST calibration')
        if not any(q['board']=='2604' and q['time']==value['time'] for q in result):
            result.append(value)
    return result
