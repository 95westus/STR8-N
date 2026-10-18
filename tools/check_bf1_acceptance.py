"""Read-only bf1 soak/RTC acceptance assessment; never changes devices or gates."""
import argparse,hashlib,json,re,time,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
from rtc_campaign_segments import recovery_segment,segment_points
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def collection_scope(active,state,ledger,boards):
    off=set(active['powered_off_boards']);assert off==set(state['powered_off_boards']) and '2205' in off
    assert off.issubset(set(active['boards'])),'Unknown powered-off board'
    assert not off.intersection({'2604','2609'}),'Required soak/sampling board reported off'
    required=sorted(set(boards)-off)
    assert required==sorted(state['snapshot_boards']) and set(required)==set(state['powered_on_boards']).intersection(boards)
    suspended={}
    for board in set(boards)&off:
        events=[e for e in ledger if e.get('board')==board and e.get('event') in ('power_off_announced','controlled_power_off_user_confirmed','power_on_announced','controlled_power_on_user_confirmed')]
        assert events,'No owner power evidence for suspended RTC stream'
        latest=max(events,key=lambda e:datetime.fromisoformat(e['recorded_utc']))
        assert latest['event'] in ('power_off_announced','controlled_power_off_user_confirmed'),'Latest owner event is not power off'
        suspended[board]=latest['recorded_utc']
    return required,suspended

def required_rtc_fresh(report):
    required=report.get('required_rtc_boards',list(report['RTC']))
    omitted=set(report['RTC'])-set(required)
    suspended=report.get('powered_off_collection_suspended',{})
    return (bool(required) and {'2512','2604','2609'}.issubset(report['RTC']) and {'2604','2609'}.issubset(required)
            and all(b in report['RTC'] and report['RTC'][b]['fresh'] for b in required)
            and all(b in suspended and report['RTC'][b].get('collection_suspended') is True and report['RTC'][b].get('collection_required') is False and report['RTC'][b]['fresh'] is False for b in omitted))

def apply_known_rtc_failure(board,assessment,state):
    failure=state.get('rtc_continuity_breaks',{}).get(board)
    if not failure:return None
    if failure.get('resolved',False):
        assert recovery_segment(state,board,failure['original_baseline_sha256']), 'Resolved RTC fault needs a verified new segment'
        path=Path(failure['status_report']);assert sha(path)==failure['status_sha256'],'Changed retained RTC failure evidence'
        assert read(path)['board']==board and read(path)['passed'] is False
        return None
    path=Path(failure['status_report']);assert sha(path)==failure['status_sha256'],'Changed RTC failure evidence'
    status=read(path);assert status['board']==board and status['passed'] is False
    assessment.update(status='failed-clock-continuity',fresh=False,current_clock_valid=False,
        historical_measurements_retained=True,continuity_failure_evidence=str(path),
        continuity_failure_detected_utc=failure['detected_utc'])
    return 'Known stopped/invalid RTC; earlier successful samples do not establish current clock health'

def rate_gate(points,limits):
    if len(points)<2:return dict(status='pending-duration',samples=len(points),span_hours=0,rate_interval_ppm=None)
    first,last=points[0],points[-1];span=last['time']-first['time'];assert span>0
    lo=(last['low']-first['high'])/span*1e6;hi=(last['high']-first['low'])/span*1e6
    half=(hi-lo)/2;target=limits['target_abs_rate_ppm']
    if span<limits['minimum_powered_segment_hours']*3600:status='pending-duration'
    elif half>limits['maximum_rate_uncertainty_halfwidth_ppm']:status='pending-precision'
    elif lo>=-target and hi<=target:status='passed'
    elif hi < -target or lo > target:status='clock-performance-review'
    else:status='inconclusive-collect-longer'
    gaps=[(b['time']-a['time'])/3600 for a,b in zip(points,points[1:])]
    return dict(status=status,samples=len(points),span_hours=span/3600,rate_interval_ppm=[lo,hi],uncertainty_halfwidth_ppm=half,maximum_sample_gap_hours=max(gaps),collection_gap_review_required=max(gaps)>limits['maximum_gap_hours'])

def audit_soak(board,rule,now):
    run=Path(rule['run']);s=read(run/'status.json');assert s['board']==board
    assert sha(Path(s['baseline_index']))==s['baseline_sha256']
    runner=ROOT/'tools'/f'run_bf1_{board}_soak.py';assert sha(runner)==s['runner_sha256']
    assert sha(ROOT/'tools'/f'bf1_{board}_readonly.py')==s['adapter_sha256']
    assert sha(ROOT/'tools/soak_led_patterns.py')==s['led_patterns_sha256']
    assert sha(Path(s['hardware_report']))==s['hardware_report_sha256']
    for p in run.glob('source-*.py'):assert sha(ROOT/'tools'/p.name[7:])==sha(p)
    units=[]
    for p in sorted(run.glob('*/report.json')):
        m=re.fullmatch(r'(\d{6})-(.+)',p.parent.name)
        if m:
            r=read(p);assert r['passed'],str(p)
            assert int(m[1])==len(units) and m[2]==s['groups'][len(units)%len(s['groups'])]
            if m[2]=='led':assert r['result']['original_led_restored']
            if board=='2609':
                for k in ('cpu_mode_before','cpu_mode_after'):
                    mode=r[k];assert mode['emulation_mode_before_probe'] and mode['dbr']==mode['pbr']==mode['direct_page']==0 and mode['entry_decimal_clear'] and mode['entry_irq_disabled']
            units.append((p,r))
    assert len(units)>=s['passed_units'] and len(s['groups'])==34
    assert not Path(str(run)+'.stderr.log').read_text().strip()
    amended_stop=False
    owner_reassigned=bool(board=='2609' and rule.get('owner_reassigned_to_windows_migrations'))
    owner_stopped=bool(rule.get('owner_requested_stop'))
    owner_receipt=None
    if owner_stopped:
        path=Path(rule['owner_stop_receipt']);assert sha(path)==rule['owner_stop_receipt_sha256']
        owner_receipt=read(path)
        assert owner_receipt['owner_authorized'] and owner_receipt['board']==board and owner_receipt['worker_pid']==s['pid']
        assert owner_receipt['safe_stop'] and owner_receipt['original_RAM_verified'] and owner_receipt['process_exited']
        assert (run/'STOP').exists() and s['state']=='stopped-by-request'
    if owner_reassigned:
        path=Path(rule['owner_stop_receipt']);assert sha(path)==rule['owner_stop_receipt_sha256']
        owner_receipt=read(path)
        assert owner_receipt['owner_authorized'] and owner_receipt['board']==board and owner_receipt['worker_pid']==s['pid']
        assert owner_receipt['safe_stop'] and owner_receipt['no_four_hour_pass_inferred']
    if board=='2609' and s['state']=='stopped-by-request' and rule.get('owner_duration_amendment') and not owner_reassigned:
        receipt=read(run/rule['safe_stop_receipt'])
        start=datetime.fromisoformat(s['duration_started_utc']).timestamp()
        assert receipt['owner_authorized'] and receipt['board']==board and receipt['worker_pid']==s['pid']
        assert receipt['total_hours']==rule['minimum_monitored_hours']==4
        assert receipt['deadline_unix']==start+4*3600
        assert datetime.fromisoformat(receipt['requested_utc']).timestamp()>=receipt['deadline_unix']
        amended_stop=True
    restore=read(run/'restore-needed.json')
    owner_restoring=owner_reassigned and s['state']=='stopped-by-request' and restore['needed']
    if owner_restoring:assert now-datetime.fromisoformat(owner_receipt['requested_utc']).timestamp()<600,'Owner-requested RAM restoration has not finished within ten minutes'
    complete=s['state'] in ('completed','completed-duration') or amended_stop or owner_stopped or (owner_reassigned and s['state']=='stopped-by-request' and not owner_restoring)
    running=s['state'] in ('running','yielding-to-drift','initializing') or owner_restoring
    assert running or complete,'Stopped or failed worker: '+s['state']
    process=None
    if running:
        assert now-s['updated']<600,'Worker status stale'
        pid=int(s['pid'])
        cmd=f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | Select-Object ProcessId,CommandLine | ConvertTo-Json"
        result=subprocess.run(['powershell','-NoProfile','-Command',cmd],capture_output=True,text=True,check=True)
        process=json.loads(result.stdout);assert process['ProcessId']==pid and runner.name in process['CommandLine'] and str(run).replace('\\','/') in process['CommandLine'].replace('\\','/')
        if board=='2609' and rule.get('owner_duration_amendment') and not owner_reassigned:
            control=read(Q/'bf1-2609-duration-amendment-current.json')
            assert control['run']==str(run) and control['total_hours']==rule['minimum_monitored_hours']==4
            assert sha(Path(control['helper']))==control['helper_sha256']
            if now<control['deadline_unix']:
                helper_query=f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(control['helper_pid'])}' | Select-Object ProcessId,CommandLine | ConvertTo-Json"
                helper=json.loads(subprocess.run(['powershell','-NoProfile','-Command',helper_query],capture_output=True,text=True,check=True).stdout)
                assert helper['ProcessId']==control['helper_pid'] and Path(control['helper']).name in helper['CommandLine'],'Four-hour STOP helper missing'
            else:
                assert (run/rule['safe_stop_receipt']).exists() and (run/'STOP').exists(),'Four-hour STOP not requested'
                assert now<=control['deadline_unix']+900,'Four-hour STOP overdue by more than 15 minutes'
    assert sha(run/'application-ram-original.bin')==restore['sha256']
    if complete:assert not restore['needed'] and restore['verified'] and s['application_ram_restored']
    else:assert restore['needed']
    start=datetime.fromisoformat(s.get('duration_started_utc',s['started_utc'])).timestamp()
    end=datetime.fromisoformat(s.get('finished_utc',owner_receipt['monitored_end_utc'] if owner_stopped else '')).timestamp() if complete else now
    elapsed=(end-start)/3600;cycles=len(units)//34
    receipt_times=[start]+[u['finished'] for _,u in units]+[end]
    max_gap=max((b-a for a,b in zip(receipt_times,receipt_times[1:])),default=0)
    healthy_coverage=max_gap<=600
    passed=elapsed>=rule['minimum_monitored_hours'] and cycles>=rule['minimum_complete_cycles'] and healthy_coverage
    if board=='2609':passed=passed and complete and not owner_reassigned
    status=('owner-stopped-for-windows-migration' if complete else 'owner-stop-pending') if owner_reassigned else ('passed' if passed else 'pending')
    if owner_stopped:status='owner-stopped';passed=False
    return dict(board=board,run=str(run),state=s['state'],status=status,actual_passed_units=len(units),complete_cycles=cycles,monitored_hours=elapsed,maximum_receipt_gap_seconds=max_gap,coverage_review_required=not healthy_coverage,application_RAM_restored=complete and restore['verified'],process=process,status_sha256=sha(run/'status.json'),restore_receipt_sha256=sha(run/'restore-needed.json'),owner_reassigned_to_windows_migrations=owner_reassigned)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path);a=ap.parse_args()
    pointer=read(Q/'bf1-acceptance-policy-current.json');policy_path=Path(pointer['policy']);assert sha(policy_path)==pointer['sha256'];p=read(policy_path)
    assert p['owner_accepted'] and sha(Path(p['baseline_index']))==p['baseline_sha256']
    active=read(Q/'active-rtc-campaign.json');assert active['baseline_index_sha256']==p['baseline_sha256']
    state=read(Path(active['campaign_state']));events=Path(state['events']);ledger=[json.loads(line) for line in events.read_text().splitlines() if line.strip()]
    required,suspended=collection_scope(active,state,ledger,p['RTC']['boards'])
    assert not suspended or p['RTC'].get('owner_powered_off_collection_suspended') is True
    now=time.time();soaks={};errors={}
    for board,rule in p['soaks'].items():
        try:soaks[board]=audit_soak(board,rule,now)
        except Exception as e:errors[board]=str(e);soaks[board]=dict(status='inspection-required',error=str(e))
    measurements={b:[] for b in p['RTC']['boards']};failed=[];sources={}
    index=read(Path(p['baseline_index']))
    for b in index['boards']:
        if b['board'] in measurements:
            rp=Path(b['baseline_report']);assert sha(rp)==b['baseline_sha256'];r=read(rp);lo,hi=r['rtc_minus_reference_interval_s'];measurements[b['board']].append(dict(time=r['baseline_reference_unix'],low=lo,high=hi,report=str(rp)));sources[str(rp)]=sha(rp)
    for sp in sorted(Q.glob('rtc-campaign-snapshot-*/summary.json')):
        summary=read(sp)
        if not summary.get('passed'):failed.append(str(sp));continue
        assert summary['ports_released']
        for b in summary['boards']:
            board=b['board']
            if board not in measurements:continue
            rp=Path(b['report']);assert sha(rp)==b['report_sha256'] and b['application_ram_restored'];r=read(rp);assert r['passed']
            base=next(x for x in index['boards'] if x['board']==board)
            assert b['trim_steps']==base['trim_steps'] and b['control_register']==base['control_register']
            assert Path(b['baseline_index'])==Path(p['baseline_index'])
            tolerance=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s'];assert abs(r['final_reference_difference_s'])<=tolerance
            lo,hi=r['rtc_minus_reference_interval_s'];measurements[board].append(dict(time=r['baseline_reference_unix'],low=lo,high=hi,report=str(rp)));sources[str(rp)]=sha(rp)
    rtc={}
    for board,points in measurements.items():
        points=sorted(points,key=lambda x:x['time']);returns=[datetime.fromisoformat(e['recorded_utc']).timestamp() for e in ledger if e.get('board')==board and e.get('event') in ('power_on_announced','controlled_power_on_user_confirmed')]
        cutoff=max(returns) if returns else points[0]['time'];end=datetime.fromisoformat(suspended[board]).timestamp() if board in suspended else now;segment=[x for x in points if cutoff<=x['time']<=end]
        recovery=recovery_segment(state,board,p['baseline_sha256'])
        if recovery:
            points=segment_points(recovery,Q,p['baseline_index']);cutoff=recovery['start_unix']
            segment=[x for x in points if cutoff<=x['time']<=end]
            for x in points:sources[x['report']]=sha(Path(x['report']))
        assessment=rate_gate(segment,p['RTC']);age=(now-points[-1]['time'])/3600
        assessment.update(latest_sample_age_hours=age,fresh=0<=age<p['RTC']['maximum_sample_age_hours'],original_baseline_preserved=True,segment_start_report=segment[0]['report'] if segment else None,latest_return_utc=datetime.fromtimestamp(cutoff,timezone.utc).isoformat())
        assessment.update(collection_required=board in required,collection_suspended=board in suspended)
        if recovery:assessment.update(measurement_segment=recovery['id'],
            explicit_clock_recovery=True,rates_across_clock_set_excluded=True,current_clock_valid=True,
            recovery_anchor=recovery['anchor_report'],original_measurements_retained=True)
        if board in suspended:assessment.update(powered_segment_status=assessment['status'],status='powered-off-collection-suspended',fresh=False,power_off_reported_utc=suspended[board])
        issue=apply_known_rtc_failure(board,assessment,state)
        if issue:errors['RTC-'+board]=issue
        rtc[board]=assessment
    migrations={}
    for route in p['prerelease'].get('required_migration_routes',[]):
        marker=Q/(route+'-acceptance-current.json')
        if not marker.exists():
            migrations[route]=dict(status='pending',board='2512',reason='Separate offline and hardware route acceptance required');continue
        pointer=read(marker);cp_path=Path(pointer['checkpoint']);assert sha(cp_path)==pointer['sha256'];cp=read(cp_path)
        assert cp['route_id']==route and cp['board']=='2512' and cp['target_version']=='2.0bf1'
        assert cp['passed'] and cp['offline_qualified'] and cp['hardware_qualified'] and cp['original_RAM_restored'] and cp['clocks_trims_unchanged'] and cp['retained_storage_preserved']
        assert cp['baseline_sha256']==p['baseline_sha256']
        assert {'offline','hardware','restoration'}.issubset(cp['evidence']), 'Separate offline, hardware and restoration receipts required'
        for ref in cp['evidence'].values():assert sha(Path(ref['path']))==ref['sha256'] and read(Path(ref['path']))['passed']
        migrations[route]=dict(status='passed',board='2512',checkpoint=str(cp_path),checkpoint_sha256=sha(cp_path))
    distribution=dict(status='pending',reason='Complete documentation and tested portable migration/recovery kit required')
    distribution_pointer=Q/'bf1-distribution-qualification-current.json'
    if distribution_pointer.exists():
        dp=read(distribution_pointer);receipt=Path(dp['checkpoint']);assert sha(receipt)==dp['sha256'];d=read(receipt)
        assert d['passed'] and all(d[k] is True for k in p['prerelease']['required_distribution_qualification'])
        assert d['candidate_id']=='batchfix-r1' and d['version']=='2.0bf1'
        for item in d['evidence'].values():assert sha(Path(item['path']))==item['sha256'] and read(Path(item['path']))['passed']
        distribution=dict(status='passed',checkpoint=str(receipt),checkpoint_sha256=dp['sha256'])
    ready=soaks['2609']['status']=='passed' and not errors and required_rtc_fresh(dict(RTC=rtc,required_rtc_boards=required,powered_off_collection_suspended=suspended)) and all(v['status']=='passed' for v in migrations.values()) and distribution['status']=='passed'
    result=dict(schema=1,observed_utc=datetime.now(timezone.utc).isoformat(),policy_sha256=sha(policy_path),baseline_sha256=p['baseline_sha256'],soaks=soaks,RTC=rtc,migration_routes=migrations,errors=errors,failed_snapshot_summaries_retained=failed,measurement_sources=sources,power_events_sha256=sha(events),prerelease_ready=ready,full_acceptance_ready=ready and soaks['2604']['status']=='passed' and all(v['status']=='passed' and not v.get('collection_gap_review_required',False) for v in rtc.values()),release_qualified=False,generic_installation_permitted=False,board_access=False,clock_trim_changes=False)
    result.update(required_rtc_boards=required,powered_off_collection_suspended=suspended,distribution_qualification=distribution)
    destination=a.out or Q/('bf1-acceptance-check-'+datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%SZ')+'.json');assert not destination.exists();destination.write_text(json.dumps(result,indent=2)+'\n')
    (Q/'bf1-acceptance-current.json').write_text(json.dumps(dict(report=str(destination.resolve()),sha256=sha(destination),observed_utc=result['observed_utc'],prerelease_ready=ready,full_acceptance_ready=result['full_acceptance_ready']),indent=2)+'\n')
    print(json.dumps(dict(report=str(destination.resolve()),soaks=soaks,RTC=rtc,migration_routes=migrations,errors=errors,prerelease_ready=ready),indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
