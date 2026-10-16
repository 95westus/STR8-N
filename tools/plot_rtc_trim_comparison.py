"""Offline comparison of pre-trim and post-trim feasible fitted rates."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
for deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',ROOT/'BUILD/plot-deps'):
    if deps.is_dir() and any(deps.rglob(f'*.{tag}-*.pyd')):sys.path.insert(0,str(deps));break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--post-summary',type=Path,default=ROOT/'output/qualification/rtc-residual-drift-2026-10-12-055000Z/summary.json')
parser.add_argument('--out',type=Path)
args=parser.parse_args()
paths=[ROOT/'output/qualification/rtc-residual-drift-2026-10-11-203425Z/summary.json',args.post_summary]
pre,post=[json.loads(p.read_text()) for p in paths]
rows=[];before={b['board']:b for b in pre['boards']}
out=args.out or ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('rtc-before-after-trim-%Y-%m-%d-%H%M%SZ');out.mkdir()
assert pre['passed'] and post['passed']
assert {b['board'] for b in post['boards']}=={'2205','2512','2604','2609'}, 'Complete four-board comparison required'
for b in sorted(post['boards'],key=lambda b:b['board']):
    p=before[b['board']]
    for item in (p,b):assert hashlib.sha256(Path(item['report']).read_bytes()).hexdigest()==item['report_sha256']
    a=p['line_fit'];z=b['line_fit'];assert a['available'] and z['available']
    blo,bhi=a['slope_interval_ppm'];alo,ahi=z['slope_interval_ppm']
    abs_after_low=0 if alo<=0<=ahi else min(abs(alo),abs(ahi));abs_after_high=max(abs(alo),abs(ahi))
    improvement=[blo-abs_after_high,bhi-abs_after_low]
    rows.append(dict(board=b['board'],trim=b['current_trim_steps'],before_hours=p['elapsed_hours'],after_hours=b['elapsed_hours'],
        before_ppm=a['slope_ppm'],before_low=blo,before_high=bhi,after_ppm=z['slope_ppm'],after_low=alo,after_high=ahi,
        before_seconds_day=a['slope_ppm']*.0864,after_seconds_day=z['slope_ppm']*.0864,
        nominal_absolute_error_reduction_percent=100*(1-abs(z['slope_ppm'])/abs(a['slope_ppm'])),
        expected_residual_ppm=a['slope_ppm']+b['current_trim_steps']*1.0172526,
        absolute_rate_improvement_low_ppm=improvement[0],absolute_rate_improvement_high_ppm=improvement[1],
        improvement_demonstrated_by_bounds=improvement[0]>0))
result=dict(passed=True,hardware_accessed=False,sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
    method='Compare compatible free-intercept fitted slopes: final zero-trim campaign versus latest excluded-immediate post-trim campaign. Absolute-rate improvement bounds = absolute pre-rate interval minus absolute post-rate interval. Not confidence intervals; no statistical significance claim.',boards=rows)
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
with (out/'before-after.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,ax=plt.subplots(figsize=(12,6))
for i,r in enumerate(rows):
    for name,dy,color in [('before',-.12,'#bd6b22'),('after',.12,'#2367af')]:
        mid=r[name+'_ppm'];lo=r[name+'_low'];hi=r[name+'_high']
        ax.errorbar(mid,i+dy,xerr=[[mid-lo],[hi-mid]],fmt='o',capsize=5,color=color,label=name.title()+' trim fit bounds' if i==0 else None)
ax.set_yticks(range(4),[r['board'] for r in rows]);ax.invert_yaxis();ax.axvline(0,color='gray',ls='--');ax.grid(axis='x',alpha=.25);ax.set_xlabel('Fitted drift ppm; zero is ideal');ax.legend()
ax.set_title(f"Before vs after trim — all four boards\nAbout {rows[0]['before_hours']:.1f} hours before / {rows[0]['after_hours']:.1f} hours after; measurement bounds, not confidence intervals")
fig.tight_layout()
for ext in ('png','svg'):fig.savefig(out/f'before-after-trim.{ext}',dpi=160)
print(out);print(json.dumps(rows,indent=2))
