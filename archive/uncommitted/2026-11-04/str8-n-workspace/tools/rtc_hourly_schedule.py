"""RTC/NIST schedule: optional initial nine-minute phase, then anchored hourly reads."""
import argparse,json,math,random,secrets,sys,time
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
PLAN=c.Q/'rtc-hourly-schedule.json';OUTPUT=c.Q/'rtc-hourly-controller-last.json'
ZONE=ZoneInfo('America/Chicago');rng=random.SystemRandom()
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def wake(t,now=None):return max(1,math.ceil((t-(time.time() if now is None else now))/60))
def initialize():
    assert not PLAN.exists(),'Review existing hourly schedule before replacing'
    state=c.read(c.STATE);assert state['active'] and not state.get('owner_stopped')
    now=time.time();local=datetime.fromtimestamp(now,ZONE);anchor=local.replace(hour=6,minute=0,second=0,microsecond=0).timestamp()
    first=anchor if now<anchor else anchor+math.floor((now-anchor)/3600)*3600
    analysis=c.read(Path(state['root'])/'latest-analysis.json')
    plan=dict(schema=1,active=True,timezone='America/Chicago',anchor_unix=anchor,anchor_local=datetime.fromtimestamp(anchor,ZONE).isoformat(),next_hour_unix=first,random_extra_2512_each_hour=True,extra_minute_range=[5,55],catchup_delay_minutes=[2,12],catchups={},hours={},last_issue_signatures=[],last_recommendations={b:r['recommendation'] for b,r in analysis['boards'].items()},created_utc=c.NOW(),authorization='collect all boards on a 1 hour schedule, starting at 6am local perform 1 random collection on 2512 within that hour. continue until stopped. if a board is unavailable, catch up on that board randomly',resets=False,clock_set=False,trim_change=False,PF_ACK=False,history_clear=False)
    c.save(PLAN,plan)
    old=c.Q/'rtc-phased-schedule.json'
    if old.exists():
        phase=c.read(old);phase.update(active=False,superseded_by=str(PLAN),superseded_utc=c.NOW());c.save(old,phase)
    state.update(interval_hours=1,hourly_schedule=str(PLAN),schedule_authorization=plan['authorization']);c.save(c.STATE,state)
    return dict(action='initialized',next_due=iso(first),next_interval_minutes=wake(first),hourly_plan=str(PLAN))
def ensure_hour(plan,stamp):
    key=str(int(stamp))
    if key not in plan['hours']:
        extra=stamp+rng.randint(5*60,55*60)
        plan['hours'][key]=dict(hour_unix=stamp,hour_local=datetime.fromtimestamp(stamp,ZONE).isoformat(),main_attempted=False,extra_due_unix=extra,extra_due_utc=iso(extra),extra_attempted=False)
    return plan['hours'][key]
def next_event(plan):
    events=[(plan['next_hour_unix'],'hourly',None)]
    phase=plan.get('intro_9minute',{})
    if phase.get('active') and phase['next_unix']<phase['end_unix']:
        events.append((phase['next_unix'],'initial-9-minute',None))
    events += [(h['extra_due_unix'],'extra-2512',key) for key,h in plan['hours'].items() if not h['extra_attempted']]
    events += [(v['due_unix'],'catchup',b) for b,v in plan['catchups'].items() if b not in plan.get('owner_blocked_boards',{})]
    return min(events,key=lambda x:x[0])
def run():
    plan=c.read(PLAN);state=c.read(c.STATE);now=time.time()
    if not plan['active'] or not state['active'] or state.get('owner_stopped'):
        result=dict(action='pause_automation',notify=False,reason='Stopped by owner; no port opened');c.save(OUTPUT,result);return result
    due,kind,key=next_event(plan)
    if now+.25<due:
        result=dict(action='wait',notify=False,next_due=iso(due),next_interval_minutes=wake(due,now));c.save(OUTPUT,result);return result
    requested=set();events=[]
    phase=plan.get('intro_9minute',{})
    if phase.get('active') and phase['next_unix']<phase['end_unix'] and phase['next_unix']<=now+.25:
        scheduled=phase['next_unix'];step=phase['interval_seconds']
        # Coalesce overdue slots into one collection, never replay a burst.
        cutoff=min(now,phase['end_unix']-.000001)
        missed=max(0,math.floor((cutoff-scheduled)/step))
        current=scheduled+missed*step
        phase['next_unix']=current+step
        phase['active']=phase['next_unix']<phase['end_unix']
        phase['attempted_slots']=phase.get('attempted_slots',0)+1
        phase['coalesced_missed_slots']=phase.get('coalesced_missed_slots',0)+missed
        if not phase['active']:phase['last_initial_slot_UTC']=iso(current)
        hour=plan['anchor_unix']+math.floor((current-plan['anchor_unix'])/3600)*3600
        h=ensure_hour(plan,hour)
        if not h['extra_attempted'] and h['extra_due_unix']<=now+180:
            earliest=now+180;latest=hour+3540
            h['extra_due_unix']=rng.uniform(earliest,latest) if earliest<latest else now+rng.randint(2*60,12*60)
            h['extra_due_utc']=iso(h['extra_due_unix'])
        h['main_attempted']=True;h['main_cadence']='initial nine-minute phase'
        requested.update(c.BOARDS)
        events.append(dict(kind='initial-9-minute',hour=str(int(hour)),scheduled=current,coalesced_missed_slots=missed))
    if plan['next_hour_unix']<=now+.25:
        scheduled=plan['next_hour_unix']
        current=scheduled+max(0,math.floor((now-scheduled)/3600))*3600
        h=ensure_hour(plan,current)
        if h['extra_due_unix']<=now+180:
            earliest=now+180;latest=current+3540
            h['extra_due_unix']=rng.uniform(earliest,latest) if earliest<latest else now+rng.randint(2*60,12*60)
            h['extra_due_utc']=iso(h['extra_due_unix'])
        h['main_attempted']=True
        h['missed_earlier_hour_slots']=int((current-scheduled)/3600)
        requested.update(c.BOARDS);events.append(dict(kind='hourly',hour=str(int(current)),scheduled=scheduled))
        plan['next_hour_unix']=current+3600
    for hour,h in plan['hours'].items():
        if not h['extra_attempted'] and h['extra_due_unix']<=now+.25:
            h['extra_attempted']=True;requested.add('2512');events.append(dict(kind='extra-2512',hour=hour,scheduled=h['extra_due_unix']))
    for board,data in plan['catchups'].items():
        if data['due_unix']<=now+.25:requested.add(board);events.append(dict(kind='catchup',board=board,scheduled=data['due_unix']))
    held=plan.get('owner_blocked_boards',{})
    requested.difference_update(held)
    for board in held:plan['catchups'].pop(board,None)
    if not requested:
        c.save(PLAN,plan)
        following,_,_=next_event(plan)
        result=dict(action='wait',notify=False,reason='Requested boards are owner-held; no port opened',next_due=iso(following),next_interval_minutes=wake(following))
        c.save(OUTPUT,result);return result
    before=state.get('last_summary');error=None;busy=False
    try:
      with serial_lease('drift',timeout=30):
        state=c.read(c.STATE);assert state['active'] and not state.get('owner_stopped'),'Owner stop takes precedence'
        argv=sys.argv;sys.argv=[str(ROOT/'tools/rtc_drift_campaign.py'),'--collect',*[part for b in c.BOARDS if b in requested for part in ('--board',b)]]
        try:c.main()
        except Exception as exc:error=repr(exc)
        finally:sys.argv=argv
    except TimeoutError as exc:error=str(exc);busy=True
    after=c.read(c.STATE);summary_path=after.get('last_summary');success=set()
    issues=after.get('last_issues',[]) if not error else [dict(board=b,error=error) for b in requested]
    if not error and summary_path and summary_path!=before:
        summary=c.read(summary_path)
        success={x['board'] for x in summary.get('boards',[]) if x.get('RAM_restored')}
        success-={i['board'] for i in issues if i.get('board') and not str(i.get('error','')).startswith('Native TIME reports PF latched')}
    failed=requested-success
    for board in success:plan['catchups'].pop(board,None)
    for board in failed:
        prior=plan['catchups'].get(board,{})
        retry=time.time()+rng.randint(2*60,12*60)
        plan['catchups'][board]=dict(due_unix=retry,due_utc=iso(retry),attempts=prior.get('attempts',0)+1,missed_events=prior.get('missed_events',[])+[e for e in events if e['kind'] in ('hourly','initial-9-minute') or e.get('board')==board or (e['kind']=='extra-2512' and board=='2512')],reason=next((i.get('error') for i in issues if i.get('board')==board),'No accepted board sample'))
    for event in events:
        if 'hour' in event:
            h=plan['hours'][event['hour']]
            h['last_attempt_utc']=c.NOW();h['last_summary']=summary_path
            if event['kind']=='extra-2512':h['extra_succeeded']='2512' in success
            if event['kind'] in ('hourly','initial-9-minute'):h['main_successful_boards']=sorted(success)
    issue_map=plan.get('issues_by_board',{})
    for board in requested:issue_map[board]=[i for i in issues if i.get('board')==board]
    signatures=sorted(json.dumps(dict(board=i.get('board'),error=i.get('error')),sort_keys=True) for values in issue_map.values() for i in values)
    analysis=c.read(Path(after['root'])/'latest-analysis.json')
    recommendations={b:r['recommendation'] for b,r in analysis['boards'].items()}
    changed={b:r for b,r in recommendations.items() if r!=plan['last_recommendations'].get(b)}
    new=after.get('last_new_PF_events',[]) if not error and summary_path!=before else []
    recovered=[b for b in success if b in c.read(PLAN).get('catchups',{})]
    notify=not busy and bool([i for i in signatures if i not in plan['last_issue_signatures']] or new or changed or recovered)
    result=dict(action='deferred' if busy else 'collected',notify=notify,events=events,requested_boards=sorted(requested),accepted_boards=sorted(success),pending_catchups=plan['catchups'],issues=issues,new_PF_events=new,changed_trim_recommendations=changed,recovered_boards=recovered,summary=summary_path,collection_error=error)
    plan.update(issues_by_board=issue_map,last_attempt_utc=c.NOW(),last_issue_signatures=signatures,last_recommendations=recommendations,last_result=result)
    c.save(PLAN,plan)
    following,_,_=next_event(plan);result.update(next_due=iso(following),next_interval_minutes=wake(following))
    c.save(OUTPUT,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--initialize',action='store_true');p.add_argument('--run',action='store_true');args=p.parse_args()
    print('HOURLY_CONTROLLER_RESULT',json.dumps(initialize() if args.initialize else run(),indent=2))

