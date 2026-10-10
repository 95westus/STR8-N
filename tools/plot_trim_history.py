"""Offline prefix fits from verified latest campaign offsets; no serial access."""
import csv,json,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
for deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',ROOT/'BUILD/plot-deps'):
    if deps.is_dir() and any(deps.rglob(f'*.{tag}-*.pyd')):
        sys.path.insert(0,str(deps));break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rtc_drift_fit import fit_offsets

root=Path('output/qualification/rtc-residual-drift-2026-10-10-230043Z')
summary=json.loads((root/'summary.json').read_text())
rows=[];fig,axes=plt.subplots(4,1,figsize=(13,14),sharex=True)
for ax,b in zip(axes,sorted(summary['boards'],key=lambda x:x['board'])):
    samples=[];times=[];nominal=[];low=[];high=[];operational=[]
    origin=datetime.fromisoformat(b['reference_utc'].replace('Z','+00:00'))-timedelta(hours=b['elapsed_hours'])
    for p in b['line_fit']['residuals']:
        bounds=[v+p['fitted_offset_s'] for v in p['residual_interval_s']]
        samples.append((p['elapsed_hours'],bounds))
        if len(samples)<2:continue
        fit=fit_offsets(samples,b['current_trim_steps'])
        if not fit['available']:continue
        steps=fit['recommended_trim_steps'];interval=fit['correction_steps_interval']
        keep=fit['slope_interval_ppm'][0]<=0<=fit['slope_interval_ppm'][1] or abs(steps)>127
        when=origin+timedelta(hours=p['elapsed_hours'])
        local=when.astimezone(timezone(timedelta(hours=-5)))
        rows.append(dict(board=b['board'],local_time=local.isoformat(),observations=len(samples)-1,nominal_trim=steps,trim_low=interval[0],trim_high=interval[1],operational_trim=0 if keep else steps,retain_zero=keep))
        times.append(local.replace(tzinfo=None));nominal.append(steps);low.append(interval[0]);high.append(interval[1]);operational.append(0 if keep else steps)
    ax.fill_between(times,low,high,alpha=.18,label='Measurement-bound implied trim range')
    ax.plot(times,nominal,'o-',label='Nominal fitted trim')
    ax.plot(times,operational,'x--',label='Operational recommendation')
    ax.axhline(0,color='gray',lw=.8);ax.set_ylim(-64,64);ax.set_ylabel(f"{b['board']} trim steps");ax.grid(alpha=.25)
axes[0].legend();axes[-1].set_xlabel('Local measurement time (CDT), October 9–10')
fig.suptitle('Recommended trim over time — prefix fits recalculated with excluded immediate sample removed\nShading is measurement bounds, not confidence; early ranges outside ±64 are clipped visually')
fig.autofmt_xdate();fig.tight_layout(rect=(0,0,1,.95))
for ext in ('png','svg'):fig.savefig(root/f'trim-history.{ext}',dpi=160)
with (root/'trim-history.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps([r for r in rows if r['observations']>=8]))
