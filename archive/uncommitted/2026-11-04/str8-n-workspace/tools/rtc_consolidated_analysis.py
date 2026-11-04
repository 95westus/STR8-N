"""Consolidate saved fleet and cooperative RTC evidence; never open hardware."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from rtc_calibration_points import merged_points

def main():
    state=c.read(c.STATE); root=Path(state['root'])
    raw=c.read(root/'points.json'); points=merged_points(state,raw)
    events=c.read(root/'events.json'); boards={}
    lines=['# Consolidated RTC / NIST drift analysis','',f'Generated {c.NOW()}. Positive offset means RTC ahead; positive ppm means gaining.','',
      '| Board | Latest UTC | Offset seconds [bounds] | ppm [compatible bounds] | Span hours | Points | Trim |',
      '|---|---|---|---|---:|---:|---:|']
    for board in c.BOARDS:
        ps=sorted((p for p in points if p['board']==board),key=lambda p:p['time']); last=ps[-1]
        boundary=max(state['baselines'][board]['time'],state.get('segment_boundaries',{}).get(board,{}).get('time',0),*[e['up'] for e in events if e['board']==board and e['up']<=last['time']])
        current=[p for p in ps if p['time']>=boundary and p['trim']==last['trim'] and p['control']==last['control']]
        fit=c.fit(current)
        boards[board]=dict(latest=last,fit=fit,segment_start_unix=boundary,cooperative_points=sum(p.get('capture_profile')=='2604-NTP-COOP-T2-1' for p in current))
        rate=f"{fit['ppm']:+.3f} [{fit['bounds_ppm'][0]:+.3f}, {fit['bounds_ppm'][1]:+.3f}]" if fit.get('available') else fit['reason']
        lines.append(f"| {board} | {last['UTC']} | {last['offset']:+.6f} [{last['low']:+.6f}, {last['high']:+.6f}] | {rate} | {fit.get('hours',0):.3f} | {len(current)} | {last['trim']} |")
    lines+=['','2604 includes receipt-verified dedicated cooperative calibration and hourly captures within the same clock/trim/control segment. Older segments remain in their original files and are excluded from current fits. All compatible observations are retained; no averaging away uncertainty or pooling across a time-setting boundary.','', 'Bounds are measurement compatibility intervals under the saved model, not statistical confidence intervals. The dedicated calibration readiness criteria still govern automatic trim application.']
    out=dict(generated_utc=c.NOW(),boards=boards,source_point_count=len(raw),verified_cooperative_points=len(points)-len(raw),historical_points_unchanged=True)
    c.save(root/'latest-consolidated-analysis.json',out)
    (root/'consolidated-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(out))

if __name__=='__main__':main()
