"""Owner-authorized phased RTC campaign controller. Collections only; never reboots."""
import argparse,json,math,random,secrets,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
PLAN=c.Q/'rtc-phased-schedule.json'
OUTPUT=c.Q/'rtc-phased-controller-last.json'
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def initialize(summary):
    assert not PLAN.exists(),'Existing phase plan requires explicit review before replacement'
    state=c.read(c.STATE);assert state['active'] and not state.get('owner_stopped')
    receipt=c.read(summary);assert receipt['passed'] and {x['board'] for x in receipt['boards']}==set(c.BOARDS)
    t=time.time();seed=secrets.randbits(64);rng=random.Random(seed)
    entries=[(32,'32-minute phase 1'),(64,'32-minute phase 1'),(96,'32-minute phase 1'),(120,'close first 2-hour phase'),(300,'3-hour interval complete'),(332,'32-minute phase 2'),(364,'32-minute phase 2'),(396,'32-minute phase 2'),(420,'close second 2-hour phase')]
    minute=420;gaps=[]
    while True:
        gap=rng.randint(16,48)
        if minute+gap>=600:break
        minute+=gap;gaps.append(gap);entries.append((minute,'random 16-48 minutes'))
    entries.append((600,'close random phase; enter every 3 hours'))
    points=c.read(Path(state['root'])/'points.json')
    plan=dict(schema=1,active=True,automation_id='all-board-rtc-drift-every-3-hours',anchor_unix=t,anchor_utc=iso(t),initial_summary=str(Path(summary).resolve()),initial_summary_sha256=c.sha(summary),random_seed=seed,random_gaps_minutes=gaps,random_range_minutes=[16,48],phase_windows_hours=[[0,2,'every 32 minutes'],[2,5,'every 3 hours'],[5,7,'every 32 minutes'],[7,10,'random 16-48 minutes'],[10,None,'every 3 hours']],events=[dict(offset_minutes=m,due_unix=t+m*60,due_utc=iso(t+m*60),phase=label,status='pending') for m,label in entries],steady_next_unix=t+780*60,initial_point_times={b:max(p['time'] for p in points if p['board']==b) for b in c.BOARDS},one_time_reboots_complete=True,reboots_on_scheduled_runs=False,clock_set=False,trim_change=False,PF_ACK=False,PF_history_clear=False,last_issue_signatures=[],last_recommendations={b:r['recommendation'] for b,r in c.read(Path(state['root'])/'latest-analysis.json')['boards'].items()})
    c.save(PLAN,plan)
    return dict(initialized=True,plan=str(PLAN),anchor_utc=plan['anchor_utc'],next_due=plan['events'][0]['due_utc'],next_interval_minutes=32,ten_hour_phase_end=iso(t+600*60),steady_first_due=iso(plan['steady_next_unix']))
def remaining(plan,now):
    pending=[e for e in plan['events'] if e['status']=='pending']
    due=min(pending,key=lambda e:e['due_unix']) if pending else dict(due_unix=plan['steady_next_unix'],phase='every 3 hours',status='pending')
    return due,max(1,math.ceil((due['due_unix']-now)/60))
def run():
    state=c.read(c.STATE);plan=c.read(PLAN)
    if not plan['active'] or not state['active'] or state.get('owner_stopped'):
        result=dict(action='pause_automation',notify=False,reason='Campaign stopped by owner; no board ports opened');c.save(OUTPUT,result);return result
    event,interval=remaining(plan,time.time())
    if time.time()+.25<event['due_unix']:
        result=dict(action='wait',notify=False,next_due=iso(event['due_unix']),next_interval_minutes=interval);c.save(OUTPUT,result);return result
    try:
      with serial_lease('drift',timeout=30):
        plan=c.read(PLAN);state=c.read(c.STATE)
        assert plan['active'] and state['active'] and not state.get('owner_stopped'),'Owner stop takes precedence'
        event,interval=remaining(plan,time.time())
        if time.time()+.25<event['due_unix']:
            return dict(action='wait',notify=False,next_due=iso(event['due_unix']),next_interval_minutes=interval)
        due=event['due_unix'];before=c.read(c.STATE);error=None
        argv=sys.argv;sys.argv=[str(ROOT/'tools/rtc_drift_campaign.py'),'--collect']
        try:c.main()
        except Exception as exc:error=repr(exc)
        finally:sys.argv=argv
        after=c.read(c.STATE)
        if error:issues=[dict(board='campaign',error=error)];new=[]
        else:issues=after.get('last_issues',[]);new=after.get('last_new_PF_events',[])
        signatures=sorted(json.dumps(dict(board=i.get('board'),error=i.get('error')),sort_keys=True) for i in issues)
        analysis=c.read(Path(after['root'])/'latest-analysis.json')
        recommendations={b:r['recommendation'] for b,r in analysis['boards'].items()}
        changed_recs={b:r for b,r in recommendations.items() if r!=plan['last_recommendations'].get(b)}
        newly_failed=[i for i in signatures if i not in plan['last_issue_signatures']]
        recovered=bool(plan['last_issue_signatures']) and not signatures
        transition=(event['phase']=='close random phase; enter every 3 hours' or time.time()>=plan['anchor_unix']+600*60) and not plan.get('ten_hour_notified',False)
        result=dict(action='collected',notify=bool(newly_failed or new or changed_recs or recovered or transition),scheduled_due=iso(due),phase=event['phase'],issues=issues,new_PF_events=new,changed_trim_recommendations=changed_recs,recovered=recovered,ten_hour_phases_complete=transition,summary=after.get('last_summary'),collection_error=error)
        for e in plan['events']:
            if e['status']=='pending' and e['due_unix']<=time.time():
                e.update(status='attempted' if e['due_unix']==due else 'missed-coalesced',attempt_utc=c.NOW(),summary=after.get('last_summary'))
        if not any(e['status']=='pending' for e in plan['events']):
            while plan['steady_next_unix']<=time.time():plan['steady_next_unix']+=180*60
        plan.update(ten_hour_notified=plan.get('ten_hour_notified',False) or transition,last_issue_signatures=signatures,last_recommendations=recommendations,last_attempt_utc=c.NOW(),last_result=result)
        c.save(PLAN,plan)
        post={}
        points=c.read(Path(after['root'])/'points.json')
        for b in c.BOARDS:
            ps=sorted([p for p in points if p['board']==b and p['time']>=plan['initial_point_times'][b]],key=lambda p:p['time'])
            post[b]=c.fit(ps)
        c.save(Path(after['root'])/'post-reboot-analysis.json',dict(generated_utc=c.NOW(),epoch=plan['anchor_utc'],physical_power_continuity_separate=True,boards=post))
        following,minutes=remaining(plan,time.time());result.update(next_due=iso(following['due_unix']),next_interval_minutes=minutes)
        c.save(OUTPUT,result);return result
    except TimeoutError as exc:
        result=dict(action='deferred',notify=False,reason=str(exc),next_due=iso(event['due_unix']),next_interval_minutes=5,no_board_port_opened=True)
        c.save(OUTPUT,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--initialize',type=Path);p.add_argument('--run',action='store_true');args=p.parse_args()
    result=initialize(args.initialize) if args.initialize else run()
    print('PHASE_CONTROLLER_RESULT',json.dumps(result,indent=2))

