"""Offline accumulated error and adjacent-checkpoint rates with interval bounds."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
for deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',ROOT/'BUILD/plot-deps'):
    if deps.is_dir() and any(deps.rglob(f'*.{tag}-*.pyd')):sys.path.insert(0,str(deps));break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--baseline-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
s=json.loads(a.summary.read_text());index=json.loads(a.baseline_index.read_text());assert s['passed']
from rtc_history_policy import excluded_reports
excluded=excluded_reports(a.baseline_index)
reports={}
for path in (ROOT/'output/qualification').glob('*/[0-9][0-9][0-9][0-9]/report.json'):
    h=hashlib.sha256(path.read_bytes()).hexdigest()
    if h not in excluded:reports[h]=path
a.out.mkdir();errors=[];rates=[]
fig1,axes1=plt.subplots(4,1,figsize=(12,13),sharex=True);fig2,axes2=plt.subplots(4,1,figsize=(12,13),sharex=True)
for b,ax1,ax2 in zip(sorted(s['boards'],key=lambda x:x['board']),axes1,axes2):
    orig=next(x for x in index['boards'] if x['board']==b['board']);basepath=Path(orig['baseline_report']);assert hashlib.sha256(basepath.read_bytes()).hexdigest()==orig['baseline_sha256']
    baseline=json.loads(basepath.read_text());points=[baseline]
    for h in sorted(b['historical_samples'],key=lambda x:x['reference_utc']):
        path=reports[h['report_sha256']];r=json.loads(path.read_text());assert r['passed'] and Path(r['compared_baseline']).resolve()==basepath.resolve();points.append(r)
    def timing(r):
        u=r['reference_uncertainty_s'];reads=[x for x in r['readings'] if x['status']==0]
        return min(x['reference_start_unix'] for x in reads)-u,max(x['reference_end_unix'] for x in reads)+u
    x=[];y=[];lo=[];hi=[];rx=[];ry=[];rl=[];rh=[]
    for i,r in enumerate(points[1:],1):
        hours=(r['baseline_reference_unix']-baseline['baseline_reference_unix'])/3600
        low=r['rtc_minus_reference_interval_s'][0]-baseline['rtc_minus_reference_interval_s'][1];high=r['rtc_minus_reference_interval_s'][1]-baseline['rtc_minus_reference_interval_s'][0]
        errors.append(dict(board=b['board'],reference_utc=r['baseline_reference_utc'],elapsed_hours=hours,error_midpoint_s=(low+high)/2,error_half_width_s=(high-low)/2,error_low_s=low,error_high_s=high))
        x.append(hours);y.append((low+high)/2);lo.append(low);hi.append(high)
        prev=points[i-1];t0=timing(prev);t1=timing(r);dtlo=t1[0]-t0[1];dthi=t1[1]-t0[0];assert dtlo>0
        dlo=r['rtc_minus_reference_interval_s'][0]-prev['rtc_minus_reference_interval_s'][1];dhi=r['rtc_minus_reference_interval_s'][1]-prev['rtc_minus_reference_interval_s'][0]
        candidates=[v/t*1e6 for v in (dlo,dhi) for t in (dtlo,dthi)];pl,ph=min(candidates),max(candidates)
        rates.append(dict(board=b['board'],from_utc=prev['baseline_reference_utc'],to_utc=r['baseline_reference_utc'],elapsed_low_s=dtlo,elapsed_high_s=dthi,drift_low_s=dlo,drift_high_s=dhi,ppm_midpoint=(pl+ph)/2,ppm_half_width=(ph-pl)/2,ppm_low=pl,ppm_high=ph,seconds_day_low=pl*.0864,seconds_day_high=ph*.0864))
        rx.append(hours);ry.append((pl+ph)/2);rl.append(pl);rh.append(ph)
    for ax,xx,yy,ll,hh,label in ((ax1,x,y,lo,hi,'accumulated error s'),(ax2,rx,ry,rl,rh,'adjacent interval ppm')):
        ax.fill_between(xx,ll,hh,alpha=.18);ax.plot(xx,yy,'o-');ax.axhline(0,color='gray');ax.set_ylabel(b['board']+'\n'+label);ax.grid(alpha=.25)
for fig,axes,title,name in ((fig1,axes1,'Accumulated time error since post-trim baseline','accumulated-time-error'),(fig2,axes2,'Separate rates between consecutive verified checkpoints','interval-rates')):
    axes[-1].set_xlabel('Hours since post-trim baseline');fig.suptitle(title+'\nMeasurement bounds, not confidence intervals');fig.tight_layout(rect=(0,0,1,.96))
    for ext in ('png','svg'):fig.savefig(a.out/(name+'.'+ext),dpi=160)
for name,rows in (('accumulated-time-error',errors),('interval-rates',rates)):
    with (a.out/(name+'.csv')).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(a.out/'summary.json').write_text(json.dumps(dict(passed=True,hardware_accessed=False,source=str(a.summary),method='Accumulated error: offset minus baseline bounds. Adjacent rates: difference of consecutive absolute offset bounds divided by elapsed-time bounds spanning serial acquisition and NTP reference uncertainty. Adjacent intervals share endpoints and are correlated; not independent clock jitter measurements.',accumulated=errors,intervals=rates),indent=2))
print('PASS',a.out)
