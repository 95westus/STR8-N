"""Offline battery interval estimate, correcting observed powered-on tails."""
import csv,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
for deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',ROOT/'BUILD/plot-deps'):
    if deps.is_dir() and any(deps.rglob(f'*.{tag}-*.pyd')):
        sys.path.insert(0,str(deps));break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

prepath=ROOT/'output/qualification/rtc-residual-drift-2026-10-11-033931Z/summary.json'
postpath=ROOT/'output/qualification/rtc-residual-drift-2026-10-11-121944Z/summary.json'
pre=json.loads(prepath.read_text());post=json.loads(postpath.read_text())
assert pre['passed'] and post['passed'] and pre['baseline_index_sha256']==post['baseline_index_sha256']
off=datetime.fromisoformat('2026-10-10T23:00:00-05:00');on=datetime.fromisoformat('2026-10-11T07:17:00-05:00')
duration=(on-off).total_seconds();prior={b['board']:b for b in pre['boards']}
out=ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('rtc-battery-comparison-%Y-%m-%d-%H%M%SZ');out.mkdir()
rows=[]
for b in sorted(post['boards'],key=lambda b:b['board']):
    p=prior[b['board']]
    for s in (p,b):
        report=Path(s['report']);assert hashlib.sha256(report.read_bytes()).hexdigest()==s['report_sha256']
        raw=json.loads(report.read_text());assert raw['passed'] and not raw['trim_changed'] and not raw.get('clock_set_attempted',False)
        assert s['current_trim_steps']==0
    start=datetime.fromisoformat(p['reference_utc'].replace('Z','+00:00'));end=datetime.fromisoformat(b['reference_utc'].replace('Z','+00:00'))
    assert start<off<on<end
    powered_seconds=(off-start).total_seconds()+(end-on).total_seconds()
    delta=[b['utc_offset_seconds'][0]-p['utc_offset_seconds'][1],b['utc_offset_seconds'][1]-p['utc_offset_seconds'][0]]
    fit=p['line_fit'];assert fit['available'];rate=fit['slope_ppm'];lo,hi=fit['slope_interval_ppm']
    battery=[delta[0]-powered_seconds*hi/1e6,delta[1]-powered_seconds*lo/1e6]
    nominal=(sum(b['utc_offset_seconds'])/2-sum(p['utc_offset_seconds'])/2-powered_seconds*rate/1e6)
    ppm=[v/duration*1e6 for v in battery]
    rows.append(dict(board=b['board'],battery_hours=duration/3600,powered_tail_minutes=powered_seconds/60,
       offset_change_low_s=delta[0],offset_change_high_s=delta[1],
       battery_drift_nominal_s=nominal,battery_drift_midpoint_s=sum(battery)/2,battery_drift_half_width_s=(battery[1]-battery[0])/2,
       battery_drift_low_s=battery[0],battery_drift_high_s=battery[1],battery_ppm_nominal=nominal/duration*1e6,
       battery_ppm_midpoint=sum(ppm)/2,battery_ppm_half_width=(ppm[1]-ppm[0])/2,battery_ppm_low=ppm[0],battery_ppm_high=ppm[1],
       battery_seconds_day_midpoint=sum(ppm)/2*.0864,battery_seconds_day_half_width=(ppm[1]-ppm[0])/2*.0864,
       prior_campaign_slope_ppm=rate,prior_slope_low=lo,prior_slope_high=hi))
result=dict(passed=True,hardware_accessed=False,off_local=off.isoformat(),on_local=on.isoformat(),battery_seconds=duration,
    method='Post minus pre UTC-offset bounds, less powered-on tails using pre-outage whole-campaign compatible slope bounds. Conservative marginal interval arithmetic; prior fit includes earlier battery/soak periods, not a pure mains-only control.',
    assumptions='Reported switch times treated as exact for calculation; power-off was approximate and no numerical timing uncertainty was supplied. Bounds exclude unspecified switch-time error. Constant prior rate over powered tails; no UTC or trim change.',
    sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (prepath,postpath)],boards=rows)
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
with (out/'battery-comparison.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,ax=plt.subplots(figsize=(12,6))
for i,r in enumerate(rows):
    ax.errorbar(r['battery_ppm_midpoint'],i+.12,xerr=r['battery_ppm_half_width'],fmt='o',capsize=5,color='#2367af',label='Battery interval estimate bounds' if i==0 else None)
    ax.plot([r['prior_slope_low'],r['prior_slope_high']],[i-.12]*2,lw=3,color='#cc7b28',label='Pre-outage campaign fit bounds' if i==0 else None)
    ax.plot(r['prior_campaign_slope_ppm'],i-.12,'s',color='#cc7b28')
ax.set_yticks(range(4),[r['board'] for r in rows]);ax.invert_yaxis();ax.axvline(0,color='gray',lw=1)
ax.set_xlabel('ppm (positive = clock gaining)');ax.set_ylabel('Board');ax.grid(axis='x',alpha=.25);ax.legend()
ax.set_title('Battery interval: October 10 23:00 to October 11 07:17 CDT — 8 h 17 min\nPowered-on tails corrected; measurement/model bounds, not confidence intervals')
fig.text(.02,.01,'Switch times are user-reported; unspecified timing uncertainty is not included. Prior fit mixes earlier operating states.',fontsize=9)
fig.tight_layout(rect=(0,.04,1,1))
for ext in ('png','svg'):fig.savefig(out/f'battery-comparison.{ext}',dpi=160)
print(out);print(json.dumps(rows,indent=2))
