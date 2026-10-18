"""Offline interval-based combined 2512/2604/2609 campaign report and scientific plots."""
import argparse,csv,hashlib,html,json
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from rtc_campaign_segments import recovery_segment,segment_points
ROOT=Path(__file__).resolve().parents[1];ZONE=ZoneInfo('America/Chicago')
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');index=Path(active['baseline_index']);assert sha(index)==active['baseline_index_sha256']
    baseline=read(index);sources={str(index):sha(index)};boards={};excluded=[]
    state=read(Path(active['campaign_state']))
    recoveries={b:recovery_segment(state,b,active['baseline_index_sha256']) for b in ('2512','2604','2609')}
    state_copy=a.out/'campaign-state-at-report.json';state_copy.write_text(json.dumps(state,indent=2)+'\n');sources[str(state_copy.resolve())]=sha(state_copy)
    events=Path(state['events']);event_bytes=events.read_bytes()
    power_events=[json.loads(line) for line in event_bytes.decode('utf-8').splitlines() if line.strip()]
    for board in ('2512','2604','2609'):
      base=next(b for b in baseline['boards'] if b['board']==board);bp=Path(base['baseline_report']);assert sha(bp)==base['baseline_sha256'];initial=read(bp)
      records=[(initial,bp,True)]
      for folder in sorted((ROOT/'output/qualification').glob('rtc-campaign-snapshot-*')):
        sp=folder/'summary.json'
        if not sp.exists():
          if (folder/'failure.json').exists():excluded.append(str(folder/'failure.json'))
          continue
        summary=read(sp)
        if not summary.get('passed'):excluded.append(str(sp));continue
        for item in summary['boards']:
          if item['board']!=board or Path(item.get('baseline_index',''))!=index:continue
          rp=Path(item['report']);assert sha(rp)==item['report_sha256'];r=read(rp)
          if item.get('measurement_segment'):
            assert recoveries[board] and item['measurement_segment']==recoveries[board]['id']
            assert Path(r['compared_baseline'])==Path(recoveries[board]['anchor_report'])
            continue # Admitted separately below; never subtract the pre-SET baseline.
          assert r['passed'] and Path(r['compared_baseline'])==bp and item['application_ram_restored'] and summary['ports_released']
          assert item['trim_steps']==base['trim_steps'] and item['control_register']==base['control_register']
          sources[str(sp)]=sha(sp);records.append((r,rp,False))
      observations=[];t0=initial['baseline_reference_unix'];l0,h0=initial['rtc_minus_reference_interval_s']
      for r,rp,isbase in sorted(records,key=lambda row:row[0]['baseline_reference_unix']):
        sources[str(rp)]=sha(rp);t=r['baseline_reference_unix'];lo,hi=r['rtc_minus_reference_interval_s'];dt=t-t0;dl,dh=(0.,0.) if isbase else (lo-h0,hi-l0)
        if not isbase:assert [dl,dh]==r['drift_seconds_interval']
        diff=r.get('final_reference_difference_s');tol=r.get('reference_uncertainty_s',0)+r.get('final_reference_check',{}).get('estimated_reference_uncertainty_s',0)
        if diff is not None:assert abs(diff)<=tol
        observations.append(dict(board=board,reference_unix=t,local_time=datetime.fromtimestamp(t,timezone.utc).astimezone(ZONE).isoformat(),elapsed_hours=dt/3600,baseline=isbase,
          offset_mid_s=(lo+hi)/2,offset_low_s=lo,offset_high_s=hi,drift_mid_s=((lo+hi)-(l0+h0))/2,drift_low_s=dl,drift_high_s=dh,
          rate_mid_ppm=None if not dt else (((lo+hi)-(l0+h0))/2)/dt*1e6,rate_low_ppm=None if not dt else dl/dt*1e6,rate_high_ppm=None if not dt else dh/dt*1e6,
          ntp_final_difference_s=diff,ntp_final_tolerance_s=tol,report=str(rp),report_sha256=sha(rp)))
      assert len(observations)>1
      pairs=[((y['offset_low_s']-x['offset_high_s'])/(y['reference_unix']-x['reference_unix'])*1e6,(y['offset_high_s']-x['offset_low_s'])/(y['reference_unix']-x['reference_unix'])*1e6) for i,x in enumerate(observations) for y in observations[i+1:]]
      interval=[max(v[0] for v in pairs),min(v[1] for v in pairs)]
      boards[board]=dict(observations=observations,latest=observations[-1],snapshot_count=len(observations),trim_steps=base['trim_steps'],control_register=base['control_register'],constant_rate_interval_ppm=interval,constant_rate_model_consistent=interval[0]<=interval[1],zero_rate_consistent=interval[0]<=0<=interval[1],interpretation='Powered-on campaign; the beta35 workload later stopped while RTC collection continued' if board=='2512' else 'Baseline-to-return interval includes powered-off operation plus powered-on time before/after switching; not a pure powered-off rate. Subsequent samples measure powered-on drift without replacing baseline.')
      if board in ('2604','2609'):
        controlled=[e for e in power_events if e.get('board')==board and e.get('event') in ('controlled_power_off_user_confirmed','controlled_power_on_user_confirmed')]
        returns=[datetime.fromisoformat(e['recorded_utc']).timestamp() for e in controlled if e['event']=='controlled_power_on_user_confirmed']
        cutoff=max(returns) if returns else observations[1]['reference_unix']
        powered=[o for o in observations[1:] if o['reference_unix']>=cutoff]
        anchor=powered[0] if powered else None;latest=powered[-1] if powered else None
        span=latest['reference_unix']-anchor['reference_unix'] if powered else 0
        dl=latest['offset_low_s']-anchor['offset_high_s'] if powered else None;dh=latest['offset_high_s']-anchor['offset_low_s'] if powered else None
        boards[board]['controlled_power_events']=controlled
        if controlled:
          boards[board]['interpretation']='Baseline-to-sample measurements span mixed power states, including controlled qualification interruptions. The separate powered-on segment starts after the latest user-confirmed return; intervals crossing an interruption are not pure powered-on drift.'
        boards[board]['powered_on_since_return']=dict(anchor_reference_utc=datetime.fromtimestamp(anchor['reference_unix'],timezone.utc).isoformat() if anchor else None,anchor_report=anchor['report'] if anchor else None,original_baseline_replaced=False,samples=len(powered),elapsed_hours=span/3600,rate_estimable_from_multiple_samples=bool(span),drift_interval_s=None if not span else [dl,dh],mean_rate_interval_ppm=None if not span else [dl/span*1e6,dh/span*1e6],latest_reported_return_utc=datetime.fromtimestamp(cutoff,timezone.utc).isoformat(),currently_reported_powered_off=board in active['powered_off_boards'],note='Separate segment starts at the first measurement after the latest reported power return. Earlier observations and original baseline are retained. Switch times are user reports, not precise electrical measurements. Firmware, temperature and workload effects are not isolated.')
    for board,data in boards.items():
      off=board in active['powered_off_boards'];data.update(currently_reported_powered_off=off,collection_status='suspended-owner-powered-off' if off else 'powered-on-sampling',latest_observation_is_historical=off)
      failure=state.get('rtc_continuity_breaks',{}).get(board)
      if failure:
        fp=Path(failure['status_report']);assert sha(fp)==failure['status_sha256'];sources[str(fp)]=sha(fp)
      data['continuity_failed']=bool(failure and not failure.get('resolved',False))
      if data['continuity_failed']:
        fp=Path(failure['status_report']);assert sha(fp)==failure['status_sha256'];sources[str(fp)]=sha(fp)
        data.update(collection_status='stopped-invalid-RTC',latest_observation_is_historical=True,
            current_clock_valid=False,continuity_failure=failure,
            interpretation='RTC stopped/invalid and its settings differ from baseline. All plotted successful measurements precede the detected continuity failure and are historical. They do not establish current clock health or drift. Preserve the original baseline; no rate may be extrapolated across this break.')
      if off:
        announcements=[e for e in power_events if e.get('board')==board and e.get('event') in ('power_off_announced','controlled_power_off_user_confirmed')]
        event=max(announcements,key=lambda e:e['recorded_utc']) if announcements else None
        data['power_off_reported_utc']=event['recorded_utc'] if event else None
        data['interpretation']='Owner reports this board powered off; RTC sampling is suspended. Plotted observations end at the last powered-on sample and are historical, not current readings. The new powered-off interval has no return measurement yet; its drift cannot be estimated. Original baseline retained.'
      if recoveries[board]:
        segment=recoveries[board];points=segment_points(segment,ROOT/'output/qualification',index)
        first,last=points[0],points[-1];span=last['time']-first['time']
        for point in points:sources[point['report']]=sha(Path(point['report']))
        data['recovery_segment']=dict(id=segment['id'],points=points,anchor_report=segment['anchor_report'],
            elapsed_hours=span/3600,rate_interval_ppm=None if not span else [
                (last['low']-first['high'])/span*1e6,(last['high']-first['low'])/span*1e6],
            current_offset_interval_s=[last['low'],last['high']],rates_across_SET_excluded=True)
        data.update(collection_status='powered-on-post-recovery-segment',current_clock_valid=True,
            latest_observation_is_historical=True,original_baseline_series_closed=True,
            interpretation='The original series below is historical and closed by an RTC continuity failure. Owner-authorized NIST sync restored original trim -14 and control $80. Current collection uses the separate post-recovery segment; no drift or rate bridges SET. The original four-board baseline and failure evidence remain retained.')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    for board,data in boards.items():
      obs=data['observations'];fig,axes=plt.subplots(3,1,figsize=(11,10),layout='constrained',sharex=True)
      for ax,prefix,label in zip(axes,['offset','drift','rate'],['RTC minus NIST (s)','Change from original baseline (s)','Baseline-to-sample mean rate (ppm)']):
        points=obs if prefix!='rate' else obs[1:];unit='ppm' if prefix=='rate' else 's';x=[datetime.fromtimestamp(o['reference_unix'],timezone.utc) for o in points];m=[o[f'{prefix}_mid_{unit}'] for o in points];lo=[o[f'{prefix}_low_{unit}'] for o in points];hi=[o[f'{prefix}_high_{unit}'] for o in points]
        ax.errorbar(x,m,yerr=[[v-l for v,l in zip(m,lo)],[h-v for v,h in zip(m,hi)]],fmt='o',capsize=5,color={'2512':'#1667a6','2604':'#a85d12','2609':'#6a50a7'}[board]);ax.axhline(0,color='gray',ls='--');ax.set_ylabel(label);ax.grid(alpha=.2)
      axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%m-%d\n%H:%M',tz=ZONE));axes[-1].set_xlabel('America/Chicago (CDT)');fig.suptitle(f'{board} RTC drift — {len(obs)} snapshots, trim {data["trim_steps"]} unchanged\n'+('Powered-on RTC campaign; acquisition bounds' if board=='2512' else 'Mixed-power baseline; powered-on samples after return'))
      if data['currently_reported_powered_off']:fig.suptitle(f'{board} RTC drift — powered OFF; collection suspended\nHistorical powered-on samples, acquisition uncertainty bounds; trim unchanged')
      if data['continuity_failed']:fig.suptitle(f'{board} RTC STOPPED / INVALID — continuity interrupted\nHistorical successful samples only; current settings differ from baseline')
      if data.get('recovery_segment'):fig.suptitle(f'{board} historical RTC series — closed by clock continuity failure\nSeparate post-recovery segment shown in companion chart; no rate across SET')
      fig.savefig(a.out/f'{board}-drift.png',dpi=160);fig.savefig(a.out/f'{board}-drift.svg');plt.close(fig)
      if data.get('recovery_segment'):
        points=data['recovery_segment']['points'];first=points[0]
        fig,axes=plt.subplots(2,1,figsize=(11,7),layout='constrained',sharex=True)
        for ax,drift in zip(axes,(False,True)):
          for i,point in enumerate(points):
            low=point['low']-(first['high'] if drift else 0);high=point['high']-(first['low'] if drift else 0)
            if drift and i==0:low=high=0
            mid=(low+high)/2
            ax.errorbar(datetime.fromtimestamp(point['time'],timezone.utc),mid,yerr=[[mid-low],[high-mid]],fmt='o',capsize=5)
          ax.set_ylabel('Change from recovery anchor (s)' if drift else 'RTC minus NIST (s)');ax.grid(alpha=.2);ax.axhline(0,color='gray',ls='--')
        axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%m-%d\n%H:%M:%S',tz=ZONE))
        if len(points)==1:axes[-1].set_xlim(datetime.fromtimestamp(first['time']-60,timezone.utc),datetime.fromtimestamp(first['time']+60,timezone.utc))
        fig.suptitle(f'{board} post-recovery RTC segment — trim -14, control $80\nNIST sync starts a separate segment; original baseline retained')
        fig.savefig(a.out/f'{board}-recovery-segment.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
    for ax,prefix,title in zip(axes,['offset','drift'],['Latest RTC minus NIST (s)','Drift from original baseline (s)']):
      for i,(board,data) in enumerate(boards.items()):
        if data.get('recovery_segment'):
          if prefix=='drift':continue # No meaningful pre-SET baseline drift for a reset clock.
          low,high=data['recovery_segment']['current_offset_interval_s'];mid=(low+high)/2
          ax.errorbar(mid,i,xerr=[[mid-low],[high-mid]],fmt='s',capsize=6,color='#6a50a7');continue
        o=data['latest'];m=o[prefix+'_mid_s'];lo=o[prefix+'_low_s'];hi=o[prefix+'_high_s'];ax.errorbar(m,i,xerr=[[m-lo],[hi-m]],fmt='o',capsize=6,color={'2512':'#1667a6','2604':'#a85d12','2609':'#6a50a7'}[board])
      ax.set_yticks(range(len(boards)),[b+(' RECOVERED · new segment' if d.get('recovery_segment') else (' INVALID · last ' if d['continuity_failed'] else ' OFF · last ' if d['currently_reported_powered_off'] else ' · ')+d['latest']['local_time'][11:16]+' CDT') for b,d in boards.items()]);ax.set_ylim(len(boards)-.4,-.6);ax.axvline(0,color='gray',ls='--');ax.grid(axis='x',alpha=.2);ax.set_xlabel(title)
    fig.suptitle('2512, 2604 and 2609 RTC campaign\nSequential measurements; bars are acquisition uncertainty bounds, not a board ranking')
    fig.savefig(a.out/'comparison.png',dpi=160);fig.savefig(a.out/'comparison.svg');plt.close(fig)
    event_copy=a.out/'power-events-at-report.jsonl';event_copy.write_bytes(event_bytes);sources[str(event_copy.resolve())]=sha(event_copy)
    result=dict(passed=True,generated_local=datetime.now(timezone.utc).astimezone(ZONE).isoformat(),boards=boards,sources=sources,excluded_summaries=sorted(set(excluded)),original_baseline_preserved=True,board_access=False,clock_trim_changed=False,installation_permitted=False,method='Acquisition uncertainty bounds, not statistical confidence intervals. Drift interval [sample low - baseline high, sample high - baseline low]. Mean rate scales interval by elapsed reference time. Constant-rate feasibility intersects every pairwise interval constraint; a mixed-power interval is not evidence of constant physical rate. Shared baseline uncertainty is not counted as independent repeated evidence.',recommendation='Leave clocks/trims unchanged; collect powered-on 2604/2609 samples and longer-span 2512 samples. Do not rank boards by midpoint or infer temperature/power causality from return samples.')
    result['recommendation']='Leave clocks/trims unchanged; continue powered-on sampling on authorized 2604/2609. Keep 2205/2512 off until owner reports return. Retain 2512 historical samples and original baseline; estimate its new powered-off interval only after a future preserving return snapshot. Do not rank boards by midpoint or infer temperature/power causality.'
    result.update(generator_setters_issued=False,explicit_recovery_segments=[b for b in boards if recoveries[b]],
        observed_settings_preserved_across_entire_campaign=not any(recoveries.values()))
    if any(recoveries.values()):result['recommendation']='Continue 2604 RTC collection and the separate post-recovery 2609 segment. Keep clocks/trims unchanged after the authorized restoration. Do not bridge the SET with a drift rate. Keep 2205/2512 off; publication remains held for unresolved qualification gates.'
    if any(d['continuity_failed'] for d in boards.values()):
      result.update(known_RTC_continuity_failure=True,observed_settings_preserved=False)
      result['recommendation']='Continue 2604 collection; retain 2609 historical measurements and its stopped/invalid RTC evidence. Keep 2205/2512 off. Do not restore time/trim automatically, treat older samples as current, or bridge the continuity break with a drift rate. A clock restoration and new segment require a separate owner decision; the original baseline remains retained.'
    (a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'observations.csv').open('w',newline='') as f:
      writer=csv.DictWriter(f,fieldnames=list(boards['2512']['observations'][0]));writer.writeheader();writer.writerows([o for b in boards.values() for o in b['observations']])
    sections=[]
    for board,data in boards.items():
      if data.get('recovery_segment'):
        seg=data['recovery_segment'];sections.append(f'<h2>{board}: current post-recovery segment</h2><p>Latest RTC minus NIST interval {seg["current_offset_interval_s"]} s; {len(seg["points"])} samples over {seg["elapsed_hours"]:.3f} h. Rate interval: {seg["rate_interval_ppm"]} ppm. Seven-day acceptance remains pending. Trim restored to -14, control $80; no rate bridges SET.</p><img src="{board}-recovery-segment.png" alt="Separate RTC post-recovery offset and drift segment"><h3>Retained pre-recovery history</h3>')
      settings_note='restored to original settings after an explicit owner-authorized sync; this numeric series is pre-recovery history' if data.get('recovery_segment') else ('baseline settings only; current RTC is stopped/invalid' if data['continuity_failed'] else 'unchanged')
      v=data['latest'];sections.append(f'<h2>{board}</h2><p>{html.escape(data["interpretation"])}</p><p>{data["snapshot_count"]} snapshots; elapsed {v["elapsed_hours"]:.3f} h; latest RTC–NIST {v["offset_mid_s"]:+.6f} s [{v["offset_low_s"]:+.6f}, {v["offset_high_s"]:+.6f}]. Drift {v["drift_mid_s"]:+.6f} s [{v["drift_low_s"]:+.6f}, {v["drift_high_s"]:+.6f}]. Endpoint rate {v["rate_mid_ppm"]:+.3f} ppm [{v["rate_low_ppm"]:+.3f}, {v["rate_high_ppm"]:+.3f}].</p><p>Constant-rate feasible interval: {data["constant_rate_interval_ppm"]}; zero consistent: {data["zero_rate_consistent"]}.</p><img src="{board}-drift.png" alt="{board} offset, drift and rate uncertainty plots"><p>Latest reference: {v["local_time"]}. Trim {data["trim_steps"]}; control {data["control_register"]}, {settings_note}.</p>')
      if board in ('2604','2609'):
        segment=data['powered_on_since_return'];sections.append('<p>Powered-on segment after latest reported return: '+(f'{segment["elapsed_hours"]:.3f} hours, mean-rate bounds {segment["mean_rate_interval_ppm"]} ppm.' if segment['rate_estimable_from_multiple_samples'] else f'{segment["samples"]} samples; at least two are needed for a separate powered-on rate.')+' Earlier observations and the original baseline are retained; intervals crossing a controlled interruption are excluded from this segment.</p>')
    (a.out/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>2512, 2604 and 2609 RTC campaign</title><style>body{font:17px system-ui;max-width:1120px;margin:40px auto;padding:0 24px;color:#172b3a}img{width:100%}p{line-height:1.55}</style><h1>2512, 2604 and 2609 RTC drift</h1><p>Generated '+html.escape(result['generated_local'])+'. Original four-board baseline retained. Measurements are sequential, not simultaneous.</p><img src="comparison.png" alt="Latest offsets and baseline drift, with uncertainty bounds">'+''.join(sections)+'<h2>Method and limits</h2><p>'+html.escape(result['method'])+'</p><p>'+html.escape(result['recommendation'])+'</p><p>2604 and 2609 each have a user-reported return ending their continuous powered-off interval; exact switch time is unknown. No outage-duration estimate is used. No pure powered-off rate or board ranking is claimed.</p><p>Full measurement provenance and hashes: report.json. Tabular observations: observations.csv.</p>',encoding='utf-8')
    files={p.name:sha(p) for p in a.out.iterdir() if p.is_file()};(a.out/'manifest.json').write_text(json.dumps(dict(files=files,generator=str(Path(__file__).resolve()),generator_sha256=sha(Path(__file__))),indent=2)+'\n')
    (ROOT/'output/qualification/rtc-powered-campaign-report-current.json').write_text(json.dumps(dict(report=str((a.out/'report.html').resolve()),data=str((a.out/'report.json').resolve()),data_sha256=sha(a.out/'report.json'),manifest_sha256=sha(a.out/'manifest.json'),boards=list(boards),generated_local=result['generated_local'],baseline_index_sha256=sha(index)),indent=2)+'\n');print(json.dumps({b:d['latest'] for b,d in boards.items()},indent=2))
if __name__=='__main__':main()
