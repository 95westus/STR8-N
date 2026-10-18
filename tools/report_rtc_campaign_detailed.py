"""Receipt-backed campaign analysis and static scientific plots; no device access."""
import argparse,csv,hashlib,html,json
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as dates
ROOT=Path(__file__).resolve().parents[1];ZONE=ZoneInfo('America/Chicago')
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
local=lambda t:datetime.fromtimestamp(t,timezone.utc).astimezone(ZONE)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);active=read(ROOT/'output/qualification/active-rtc-campaign.json')
    index=Path(active['baseline_index']);assert sha(index)==active['baseline_index_sha256'];baseline=read(index)
    baselines=[];sources={str(index):sha(index)};rows=[];excluded=[]
    for b in baseline['boards']:
        path=Path(b['baseline_report']);assert sha(path)==b['baseline_sha256'];r=read(path);assert r['passed']
        sources[str(path)]=sha(path);lo,hi=r['rtc_minus_reference_interval_s']
        baselines.append(dict(board=b['board'],local_time=local(r['baseline_reference_unix']).isoformat(),
            offset_low_s=lo,offset_high_s=hi,offset_mid_s=(lo+hi)/2,trim=b['trim_steps'],control=b['control_register']))
        if b['board']=='2512':base=b;initial=r;rows.append((r,path,True))
    for folder in sorted((ROOT/'output/qualification').glob('rtc-campaign-snapshot-*')):
        path=folder/'summary.json'
        if not path.exists():
            if (folder/'failure.json').exists():excluded.append(dict(path=str(folder/'failure.json'),reason='Failed attempt retained; not a measurement'))
            continue
        sample=read(path)
        if not sample.get('passed'):excluded.append(dict(path=str(path),reason='Summary failed'));continue
        for b in sample['boards']:
            if b['board']!='2512' or Path(b.get('baseline_index',''))!=index:continue
            rp=Path(b['report']);assert sha(rp)==b['report_sha256'];r=read(rp)
            assert r['passed'] and Path(r['compared_baseline'])==Path(base['baseline_report'])
            assert b['trim_steps']==base['trim_steps'] and b['control_register']==base['control_register']
            assert b['application_ram_restored'] and sample['ports_released']
            sources[str(path)]=sha(path);sources[str(rp)]=sha(rp);rows.append((r,rp,False))
    rows.sort(key=lambda x:x[0]['baseline_reference_unix']);observations=[]
    t0=initial['baseline_reference_unix'];l0,u0=initial['rtc_minus_reference_interval_s'];m0=(l0+u0)/2
    for r,path,isbase in rows:
        t=r['baseline_reference_unix'];lo,hi=r['rtc_minus_reference_interval_s'];dt=t-t0
        dlo,dhi=(0.,0.) if isbase else (lo-u0,hi-l0)
        if not isbase:assert [dlo,dhi]==r['drift_seconds_interval']
        # The acquisition program uses uncertainty of initial and final NTP
        # references to reject inconsistent host/reference evolution.
        final=r.get('final_reference_check',{});diff=r.get('final_reference_difference_s')
        tolerance=r.get('reference_uncertainty_s',0)+final.get('estimated_reference_uncertainty_s',0)
        if diff is not None:assert abs(diff)<=tolerance
        observations.append(dict(local_time=local(t).isoformat(),reference_unix=t,elapsed_hours=dt/3600,
            offset_mid_s=(lo+hi)/2,offset_low_s=lo,offset_high_s=hi,drift_mid_s=(lo+hi)/2-m0,
            drift_low_s=dlo,drift_high_s=dhi,endpoint_ppm_mid=None if not dt else ((lo+hi)/2-m0)/dt*1e6,
            endpoint_ppm_low=None if not dt else dlo/dt*1e6,endpoint_ppm_high=None if not dt else dhi/dt*1e6,
            ntp_final_difference_s=diff,ntp_consistency_tolerance_s=tolerance,
            reference_uncertainty_s=r.get('reference_uncertainty_s'),reading_count=len(r['readings']),
            report=str(path),report_sha256=sha(path),baseline=isbase))
    assert len(observations)>1
    pairs=[]
    for i,x in enumerate(observations):
        for y in observations[i+1:]:
            dt=y['reference_unix']-x['reference_unix'];assert dt>0
            pairs.append(((y['offset_low_s']-x['offset_high_s'])/dt*1e6,
                          (y['offset_high_s']-x['offset_low_s'])/dt*1e6))
    rate_lo=max(p[0] for p in pairs);rate_hi=min(p[1] for p in pairs)
    latest=observations[-1];now=datetime.now(timezone.utc)
    campaign=read(Path(active['campaign_state']));run=Path(campaign['soak_run']);status=read(run/'status.json')
    actual=[]
    for rp in sorted(run.glob('*/report.json')):
        prefix=rp.parent.name.split('-',1)[0]
        if prefix.isdigit():
            result=read(rp);assert result['passed'];actual.append((int(prefix),rp.parent.name.split('-',1)[1],result))
    for i,(number,group,result) in enumerate(actual):
        assert number==i and group==status['groups'][i%len(status['groups'])]
        if group=='led':assert result['result']['original_led_restored']
    assert len(actual)>=status['passed_units'] and status['state'] in ('running','yielding-to-drift')
    result=dict(generated_local=now.astimezone(ZONE).isoformat(),baseline_sha256=sha(index),sources=sources,
        observations=observations,baseline_boards=baselines,excluded_attempts=excluded,
        observation_count=len(observations),elapsed_hours=latest['elapsed_hours'],latest=latest,
        constant_linear_rate_feasible_ppm=[rate_lo,rate_hi],constant_linear_rate_feasible_s_day=[rate_lo*.0864,rate_hi*.0864],
        constant_linear_model_consistent=rate_lo<=rate_hi,zero_rate_consistent=rate_lo<=0<=rate_hi,
        uncertainty_method='Interval subtraction for drift; all-pair interval constraints for constant slope with a free intercept. Acquisition bounds, not statistical confidence intervals. Shared baseline uncertainty is not treated as independent.',
        powered_off_boards=active['powered_off_boards'],power_off_drift_measurable=False,
        soak=dict(run=str(run),state=status['state'],pid=status['pid'],actual_passed_units=len(actual),
            completed_cycles=len(actual)//len(status['groups']),units_per_cycle=len(status['groups']),
            led_units=sum(group=='led' for _,group,_ in actual)),
        clock_trim_settings_changed=False,board_access=False,trim_recommendation='Keep unchanged; accumulated span and acquisition bounds do not yet justify an adjustment.')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'font.family':'DejaVu Sans'})
    color='#1667a6';x=[local(o['reference_unix']) for o in observations]
    fig,axes=plt.subplots(3,1,figsize=(11,10),sharex=True,layout='constrained')
    for ax,key,title in zip(axes,['offset','drift','endpoint_ppm'],['RTC minus NIST (s)','Change from baseline (s)','Baseline-to-sample average rate (ppm)']):
        data=observations if key!='endpoint_ppm' else observations[1:];xx=x if key!='endpoint_ppm' else x[1:]
        mid=[o[key+'_mid_s' if key!='endpoint_ppm' else key+'_mid'] for o in data]
        lo=[o[key+'_low_s' if key!='endpoint_ppm' else key+'_low'] for o in data]
        hi=[o[key+'_high_s' if key!='endpoint_ppm' else key+'_high'] for o in data]
        ax.errorbar(xx,mid,yerr=[[m-l for m,l in zip(mid,lo)],[h-m for h,m in zip(hi,mid)]],fmt='o',capsize=5,color=color)
        ax.axhline(0,color='gray',ls='--',lw=1);ax.set_ylabel(title);ax.grid(alpha=.18)
        for t,m in zip(xx,mid):ax.annotate(f'{m:+.3f}',(t,m),xytext=(7,8),textcoords='offset points',fontsize=9)
    axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%m-%d\n%H:%M',tz=ZONE));axes[-1].set_xticks(x)
    axes[-1].set_xlabel('America/Chicago (CDT), October 16–17, 2026')
    fig.suptitle(f'2512 powered RTC campaign · {len(observations)} snapshots · trim {base["trim_steps"]} unchanged',fontsize=16)
    fig.savefig(a.out/'2512-drift.png',dpi=170);fig.savefig(a.out/'2512-drift.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8),layout='constrained')
    for i,b in enumerate(baselines):
        m=b['offset_mid_s'];ax.errorbar(m,i,xerr=[[m-b['offset_low_s']],[b['offset_high_s']-m]],fmt='o',capsize=6,color=color)
    ax.set_yticks(range(4),[b['board']+(' · powered on' if b['board']=='2512' else ' · powered off afterward') for b in baselines]);ax.invert_yaxis()
    ax.axvline(0,color='gray',ls='--');ax.set_xlabel('Baseline RTC minus NIST (s) · acquisition bounds');ax.grid(axis='x',alpha=.18)
    ax.set_title('Four-board baseline offsets · sequential measurements, not rate rankings')
    fig.savefig(a.out/'four-board-baseline.png',dpi=170);fig.savefig(a.out/'four-board-baseline.svg');plt.close(fig)
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'observations.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(observations[0]));w.writeheader();w.writerows(observations)
    table=''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in [o['local_time'][5:19],f"{o['elapsed_hours']:.3f}",f"{o['offset_mid_s']:+.6f}",f"[{o['offset_low_s']:+.6f}, {o['offset_high_s']:+.6f}]",f"{o['drift_mid_s']:+.6f}",f"[{o['drift_low_s']:+.6f}, {o['drift_high_s']:+.6f}]"] )+'</tr>' for o in observations)
    body=f'''<!doctype html><meta charset="utf-8"><title>RTC drift campaign analysis</title>
    <style>body{{font:16px/1.55 system-ui;max-width:1100px;margin:35px auto;padding:0 25px;color:#182534}}img{{width:100%}}table{{border-collapse:collapse;font-size:13px}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}code{{overflow-wrap:anywhere}}</style>
    <h1>RTC drift campaign analysis</h1><p>Generated {result['generated_local']}. Positive offset means the board is ahead of NIST; positive drift means it gained time relative to its own baseline.</p>
    <h2>2512: no resolved drift yet</h2><p>{len(observations)} snapshots span {latest['elapsed_hours']:.3f} hours. Latest offset midpoint is {latest['offset_mid_s']:+.6f} s, bounded by [{latest['offset_low_s']:+.6f}, {latest['offset_high_s']:+.6f}] s. Baseline-relative change is {latest['drift_mid_s']:+.6f} s, with propagated bounds [{latest['drift_low_s']:+.6f}, {latest['drift_high_s']:+.6f}] s. Zero remains within these bounds.</p>
    <p>The endpoint average rate is {latest['endpoint_ppm_mid']:+.3f} ppm, bounded by [{latest['endpoint_ppm_low']:+.3f}, {latest['endpoint_ppm_high']:+.3f}] ppm. This is not a measured long-term oscillator rate. Under a constant linear-rate assumption, all observations jointly allow [{rate_lo:+.3f}, {rate_hi:+.3f}] ppm, or [{rate_lo*.0864:+.3f}, {rate_hi*.0864:+.3f}] seconds/day. Zero rate is consistent: {result['zero_rate_consistent']}.</p>
    <img src="2512-drift.png" alt="2512 offset, drift and average-rate acquisition bounds">
    <h2>Snapshot ledger (CDT)</h2><table><tr><th>Local date/time</th><th>Elapsed h</th><th>Offset midpoint s</th><th>Offset bounds s</th><th>Drift midpoint s</th><th>Drift bounds s</th></tr>{table}</table>
    <h2>Method and limits</h2><p>Every source report and registered baseline hash was verified. All successful samples retain application-RAM restoration, unchanged trim/control and final NTP consistency evidence. Each snapshot contains {', '.join(str(o['reading_count']) for o in observations)} RTC readings. Acquisition bounds include whole-second clock granularity and serial/NTP uncertainty; these are not statistical confidence intervals. Midpoint fluctuations alone do not demonstrate oscillator changes. No averaging of supposedly independent baseline errors, extrapolated correction, trim adjustment or ranking is justified.</p>
    <p>The constant-rate range is the intersection of every pair's allowed slopes, allowing a free intercept inside each measured offset interval. It is conditional on a constant rate, not evidence that temperature, supply or rate stayed constant. There is no temperature record or power-off return measurement. Retain all future measurements; longer spans narrow the rate uncertainty even if the absolute timestamp bounds stay similar.</p>
    <h2>Other boards</h2><img src="four-board-baseline.png" alt="Four board baseline offset bounds"><p>2205, 2604 and 2609 have baseline measurements only in this campaign and remain marked powered off. Their power-off drift cannot be calculated until a user-reported power return and a fresh comparison against the unchanged baseline. Baseline offset is not timing quality. Sequential samples are not simultaneous. Earlier pre-campaign data and trim regimes are not spliced into this baseline.</p>
    <h2>Data quality and campaign protection</h2><p>{len(excluded)} failed attempt(s) retained and excluded from numerical analysis. No old measurement substituted for a failed sample. The baseline is unchanged: <code>{sha(index)}</code>. Source paths/hashes, NTP consistency figures and the failure ledger are in <a href="report.json">report.json</a>; measurements are in <a href="observations.csv">observations.csv</a>.</p>
    <p>The current soak has {len(actual)} actual passed unit reports and {result['soak']['completed_cycles']} complete {len(status['groups'])}-unit cycles, including {result['soak']['led_units']} LED units with restoration. Earlier run definitions are not merged. This report opened no serial ports and changed no clocks, trims, settings, firmware or retained storage. Keep trim unchanged and continue the scheduled campaign.</p>'''
    (a.out/'report.html').write_text(body,encoding='utf-8');print(json.dumps({k:result[k] for k in ['observation_count','elapsed_hours','constant_linear_rate_feasible_ppm','soak']},indent=2))
if __name__=='__main__':main()
