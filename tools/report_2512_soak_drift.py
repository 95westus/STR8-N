"""Render receipt-backed soak and NIST drift charts without hardware access."""
import argparse
import csv
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ZONE=ZoneInfo('America/Chicago')


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def local(epoch):return datetime.fromtimestamp(epoch,timezone.utc).astimezone(ZONE)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    active=read(ROOT/'output/qualification/active-rtc-campaign.json')
    index=Path(active['baseline_index'])
    assert sha(index)==active['baseline_index_sha256']
    baseline=next(b for b in read(index)['boards'] if b['board']=='2512')
    baseline_report=Path(baseline['baseline_report']);assert sha(baseline_report)==baseline['baseline_sha256']
    initial=read(baseline_report);t0=initial['baseline_reference_unix']
    lo0,hi0=initial['rtc_minus_reference_interval_s'];mid0=(lo0+hi0)/2
    rows=[dict(reference_unix=t0,reference_local=local(t0).isoformat(),offset_mid_s=mid0,
               offset_low_s=lo0,offset_high_s=hi0,drift_mid_s=0.,drift_low_s=0.,drift_high_s=0.,
               report=str(baseline_report),report_sha256=sha(baseline_report),baseline=True)]
    for summary in sorted((ROOT/'output/qualification').glob('rtc-campaign-snapshot-*/summary.json')):
        observed=read(summary)
        if not observed.get('passed'):continue
        for board in observed['boards']:
            if board['board']!='2512' or board.get('baseline_index')!=str(index):continue
            path=Path(board['report']);assert sha(path)==board['report_sha256']
            r=read(path)
            assert r['passed'] and Path(r['compared_baseline'])==baseline_report
            assert r['baseline_reference_unix']>t0 and board['application_ram_restored']
            assert board['trim_steps']==baseline['trim_steps'] and board['control_register']==baseline['control_register']
            low,high=r['rtc_minus_reference_interval_s'];mid=(low+high)/2
            lower,upper=low-hi0,high-lo0
            assert r['drift_seconds_interval']==[lower,upper]
            rows.append(dict(reference_unix=r['baseline_reference_unix'],
                reference_local=local(r['baseline_reference_unix']).isoformat(),
                offset_mid_s=mid,offset_low_s=low,offset_high_s=high,
                drift_mid_s=mid-mid0,drift_low_s=lower,drift_high_s=upper,
                report=str(path),report_sha256=sha(path),baseline=False))
    rows.sort(key=lambda r:r['reference_unix'])
    campaign=read(Path(active['campaign_state']));current=Path(campaign['soak_run'])
    runs=[]
    for path in [*map(Path,campaign['previous_soak_runs']),current]:
        state=read(path/'status.json');units=state['passed_units']
        receipts=[]
        for report in path.glob('*/report.json'):
            prefix=report.parent.name.split('-',1)[0]
            if prefix.isdigit() and int(prefix)<units:
                data=read(report);assert data['passed'];receipts.append(report)
        assert len(receipts)==units,(path,len(receipts),units)
        runs.append(dict(run=path.name,status=state['state'],passed_units=units,
            completed_cycles=state['completed_cycles'],units_per_cycle=len(state['groups']),
            started_utc=state['started_utc'],is_current=path==current,
            ram_restored=read(path/'restore-needed.json').get('verified',False),
            latest_completed_unit_epoch=max(read(p)['finished'] for p in receipts) if receipts else None))
    now=datetime.now(timezone.utc);last=rows[-1];elapsed=last['reference_unix']-t0
    assert runs[-1]['status'] in ('running','yielding-to-drift')
    style={'font.family':'DejaVu Sans','font.size':11,'axes.spines.right':False,
           'axes.spines.top':False,'axes.labelcolor':'#273142','text.color':'#182534',
           'axes.titleweight':'bold','figure.facecolor':'white','axes.facecolor':'white',
           'savefig.facecolor':'white','xtick.color':'#425064','ytick.color':'#425064'}
    plt.rcParams.update(style);blue='#1768A8';gray='#8492A3'
    x=[local(r['reference_unix']) for r in rows]
    fig,axes=plt.subplots(2,1,figsize=(10.6,7.5),sharex=True)
    fig.subplots_adjust(left=.12,right=.96,top=.84,bottom=.17,hspace=.40)
    fig.suptitle('2512 clock drift since the new baseline',fontsize=18,fontweight='bold',y=.97)
    fig.text(.5,.914,local(t0).strftime('%b %d, %Y')+'  ·  CDT  ·  NIST reference  ·  trim −12 unchanged',
             ha='center',fontsize=11,color='#425064')
    for ax,field,label in [(axes[0],'offset','RTC minus NIST (seconds)'),
                            (axes[1],'drift','Change since baseline (seconds)')]:
        mid=[r[field+'_mid_s'] for r in rows]
        lower=[r[field+'_mid_s']-r[field+'_low_s'] for r in rows]
        upper=[r[field+'_high_s']-r[field+'_mid_s'] for r in rows]
        ax.errorbar(x,mid,yerr=[lower,upper],fmt='o',markersize=7,elinewidth=2,capsize=6,
                    color=blue,ecolor=blue,zorder=3)
        ax.axhline(0,color='#6E7885',linewidth=1,linestyle='--')
        ax.set_ylabel(label);ax.grid(axis='y',alpha=.16)
        ax.set_xlim(x[0]-timedelta(minutes=5),x[-1]+timedelta(minutes=8))
        for i,(xx,yy) in enumerate(zip(x,mid)):
            annotation=('Baseline ' if i==0 else '')+f'{yy:+.3f} s'
            ax.annotate(annotation,(xx,yy),xytext=(0,13),textcoords='offset points',ha='center',fontsize=10)
    axes[0].set_title('Absolute clock offset',loc='left',fontsize=12)
    axes[1].set_title('Relative drift — positive means gaining time',loc='left',fontsize=12)
    axes[1].set_xticks(x)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S',tz=ZONE))
    axes[1].set_xlabel('October 16 local time (CDT)')
    axes[1].set_ylim(min(r['drift_low_s'] for r in rows)-.16,max(r['drift_high_s'] for r in rows)+.22)
    fig.text(.12,.075,'Bars show acquisition bounds, including one-second RTC granularity and serial/NTP uncertainty.\n'
             'These are not statistical confidence intervals. Only three snapshots; no long-term rate is fitted.',
             fontsize=9,color='#425064',linespacing=1.5)
    fig.savefig(args.out/'rtc-drift.png',dpi=180);fig.savefig(args.out/'rtc-drift.svg');plt.close(fig)

    labels=['Initial run','EEPROM fixture corrected','Stable run / LED handoff','LED readback attempt','Current varied-LED run']
    assert len(labels)==len(runs)
    notes=['EEPROM comparison fixture stop; RAM restored',
           'Flash comparison fixture stop; RAM restored',
           '2 complete cycles; orderly handoff; RAM restored',
           'Monitor I/O-read harness stop; RAM restored',
           f"{runs[-1]['completed_cycles']} complete cycle(s); {runs[-1]['status']}"]
    fig,ax=plt.subplots(figsize=(12.0,5.4));fig.subplots_adjust(left=.23,right=.60,top=.78,bottom=.27)
    colors=[gray]*(len(runs)-1)+[blue]
    y=list(range(len(runs)))
    bars=ax.barh(y,[r['passed_units'] for r in runs],color=colors,height=.58)
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,max(r['passed_units'] for r in runs)*1.16)
    ax.set_xlabel('Passed workload units');ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
    ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0,pad=12)
    for bar,run,note in zip(bars,runs,notes):
        yy=bar.get_y()+bar.get_height()/2
        ax.text(run['passed_units']+1,yy,str(run['passed_units']),va='center',fontweight='bold')
        ax.text(1.07,yy,note,transform=ax.get_yaxis_transform(),va='center',fontsize=10,color='#425064')
    fig.suptitle('2512 soak progress — current run healthy',fontsize=18,fontweight='bold',y=.96)
    fig.text(.5,.855,'Receipt-backed counts as of '+now.astimezone(ZONE).strftime('%b %d, %Y  %H:%M:%S CDT'),
             ha='center',fontsize=11,color='#425064')
    fig.text(.23,.055,'Cycle definitions differ: stable r3 = 28 units; current r5 = 34 units (including 7 LED interludes).\n'
             'Earlier fixture/harness stops are retained; no failures recorded in the current run.',fontsize=9,color='#425064',linespacing=1.5)
    fig.savefig(args.out/'soak-progress.png',dpi=180);fig.savefig(args.out/'soak-progress.svg');plt.close(fig)
    result={'generated_utc':now.isoformat(),'generated_local':now.astimezone(ZONE).isoformat(),
            'baseline_reference_local':local(t0).isoformat(),'latest_reference_local':last['reference_local'],
            'elapsed_seconds':elapsed,'estimated_drift_seconds':last['drift_mid_s'],
            'drift_bounds_seconds':[last['drift_low_s'],last['drift_high_s']],
            'drift_resolved_from_zero':not(last['drift_low_s']<=0<=last['drift_high_s']),
            'latest_offset_seconds':last['offset_mid_s'],'latest_offset_bounds_seconds':[last['offset_low_s'],last['offset_high_s']],
            'observations':rows,'soak_runs':runs,'active_run':str(current),
            'baseline_index_sha256':sha(index),'settings_unchanged':True,'board_access_by_report':False,
            'chart_files':['rtc-drift.png','soak-progress.png','rtc-drift.svg','soak-progress.svg']}
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.out/'rtc-observations.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('observations','soak_runs')},indent=2))
    print('CURRENT',runs[-1],flush=True)


if __name__=='__main__':main()
