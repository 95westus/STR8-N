"""Offline matched battery/mains comparison; no Gaussian confidence claims."""
import csv,json,sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1];tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
for deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',ROOT/'BUILD/plot-deps'):
    if deps.is_dir() and any(deps.rglob(f'*.{tag}-*.pyd')):sys.path.insert(0,str(deps));break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=ROOT/'output/qualification/rtc-residual-drift-2026-10-11-203425Z'
latest=json.loads((out/'summary.json').read_text())
start=json.loads((ROOT/'output/qualification/rtc-residual-drift-2026-10-11-121944Z/summary.json').read_text())
battery=json.loads((ROOT/'output/qualification/rtc-battery-comparison-2026-10-11-122557Z/summary.json').read_text())
prior={b['board']:b for b in start['boards']};bat={b['board']:b for b in battery['boards']};rows=[]
for b in latest['boards']:
    p=prior[b['board']];bb=bat[b['board']]
    elapsed=(datetime.fromisoformat(b['reference_utc'].replace('Z','+00:00'))-datetime.fromisoformat(p['reference_utc'].replace('Z','+00:00'))).total_seconds()
    low=(b['utc_offset_seconds'][0]-p['utc_offset_seconds'][1])/elapsed*1e6
    high=(b['utc_offset_seconds'][1]-p['utc_offset_seconds'][0])/elapsed*1e6
    rows.append(dict(board=b['board'],matched_hours=29820/3600,actual_observation_hours=elapsed/3600,
        mains_ppm_midpoint=(low+high)/2,mains_ppm_half_width=(high-low)/2,mains_ppm_low=low,mains_ppm_high=high,
        mains_matched_drift_low_s=low*29820/1e6,mains_matched_drift_high_s=high*29820/1e6,
        battery_ppm_midpoint=bb['battery_ppm_midpoint'],battery_ppm_half_width=bb['battery_ppm_half_width'],
        battery_ppm_low=bb['battery_ppm_low'],battery_ppm_high=bb['battery_ppm_high'],
        mains_minus_battery_low_ppm=low-bb['battery_ppm_high'],mains_minus_battery_high_ppm=high-bb['battery_ppm_low']))
result=dict(passed=True,hardware_accessed=False,boards=rows,
    assumption='Continuous mains power from07:17 to15:34 is user-instructed, not independently logged. No intervening outage reported. Constant mains rate assumed over endpoint tails.',
    timing='Use actual acquisition UTC reference times: observations start3–5minutes after07:17 and finish after15:34. Convert rate over actual elapsed time to29820seconds; this extrapolates endpoint tails under constant-rate assumption. Battery off23:00 approximate, unspecified timing error not quantified.',
    conclusion='Measurement-bound compatibility only; no defined equivalence tolerance or defensible stochastic model, so no statistical equivalence/95%confidence assertion. Conservative difference bounds allow dependence through shared readings.')
(out/'matched-power-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
with (out/'matched-power-comparison.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,ax=plt.subplots(figsize=(12,6))
for i,r in enumerate(rows):
    for key,dy,color in [('battery',-.12,'#2367af'),('mains',.12,'#cf772b')]:
        ax.errorbar(r[key+'_ppm_midpoint'],i+dy,xerr=r[key+'_ppm_half_width'],fmt='o',capsize=5,color=color,label=key.title()+' bounds' if i==0 else None)
ax.set_yticks(range(4),[r['board'] for r in rows]);ax.invert_yaxis();ax.axvline(0,color='gray');ax.grid(axis='x',alpha=.25);ax.set_xlabel('Drift ppm');ax.legend()
ax.set_title('Matched 8 h 17 min battery/mains intervals — all four boards\nMeasurement/model bounds; overlap does not establish statistical equivalence')
fig.tight_layout()
for ext in ('png','svg'):fig.savefig(out/f'matched-power-comparison.{ext}',dpi=160)
print(json.dumps(rows))
for b in latest['boards']:
    print(json.dumps(dict(board=b['board'],time=b['reference_utc'],elapsed=b['elapsed_hours'],uncertainty=b['measurement_uncertainty'],stats=b['statistics'],fit={k:v for k,v in b['line_fit'].items() if k in ('slope_ppm','slope_interval_ppm','slope_uncertainty_minus_ppm','slope_uncertainty_plus_ppm','intercept_seconds','residual_rmse_seconds','residual_sample_std_seconds','max_absolute_residual_seconds')},trim=b['recommended_trim'])))
