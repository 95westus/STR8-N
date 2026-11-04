"""Offline schedule transitions; all hardware and capture calls are mocked."""
import sys,copy,contextlib,importlib.util
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'C:/SRC/STR8-N/tools')
source=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('rtc_hourly_schedule.py')
spec=importlib.util.spec_from_file_location('schedule_candidate',source);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Random:
 def randint(self,a,b):return a
 def uniform(self,a,b):return a

def plan():
 return dict(active=True,anchor_unix=0,next_hour_unix=7200,catchups={},hours={str(h):dict(hour_unix=h,extra_due_unix=h+1800,extra_attempted=True,main_attempted=False) for h in (0,3600)},last_issue_signatures=[],last_recommendations={b:'Keep current trim' for b in s.c.BOARDS},intro_9minute=dict(active=True,start_unix=1000,end_unix=4600,next_unix=1000,interval_seconds=540))
def run(now,p=None,stopped=False,busy=False):
 p=copy.deepcopy(p or plan());state=dict(active=not stopped,owner_stopped=stopped,root='fake-root',last_summary='old',last_issues=[],last_new_PF_events=[]);db={str(s.PLAN):p,str(s.c.STATE):state,str(Path('fake-root')/'latest-analysis.json'):dict(boards={b:dict(recommendation='Keep current trim') for b in s.c.BOARDS})};calls=[]
 def read(path):return copy.deepcopy(db[str(path)])
 def save(path,value):db[str(path)]=copy.deepcopy(value)
 @contextlib.contextmanager
 def lease(*a,**k):
  if busy:raise TimeoutError('Serial lease unavailable; no board port opened')
  yield
 def collect():
  selected=[s.sys.argv[i+1] for i,x in enumerate(s.sys.argv) if x=='--board'];calls.append(selected)
  db['new']=dict(boards=[dict(board=b,RAM_restored=True) for b in selected]);db[str(s.c.STATE)]['last_summary']='new'
 with patch.object(s.c,'read',side_effect=read),patch.object(s.c,'save',side_effect=save),patch.object(s.c,'main',side_effect=collect),patch.object(s,'serial_lease',lease),patch.object(s.time,'time',return_value=now),patch.object(s,'rng',Random()):r=s.run()
 return r,db.get(str(s.PLAN)),calls
checks=[]
r,p,calls=run(999);assert r['action']=='wait' and not calls;checks.append('early wake opens no ports')
r,p,calls=run(1000);assert len(calls)==1 and set(calls[0])==set(s.c.BOARDS) and p['intro_9minute']['next_unix']==1540 and p['next_hour_unix']==7200;checks.append('all four at first slot; hourly anchor retained')
r,p,calls=run(2701);assert len(calls)==1 and p['intro_9minute']['next_unix']==3160 and r['events'][0]['coalesced_missed_slots']==3;checks.append('missed nine-minute slots coalesced without bursts')
r,p,calls=run(4550);assert len(calls)==1 and not p['intro_9minute']['active'] and s.next_event(p)[0]==7200;checks.append('last dense slot transitions to anchored hourly')
p=plan();p['intro_9minute']['active']=False;r,p,calls=run(4601,p);assert r['action']=='wait' and not calls;checks.append('no dense collection after phase ends')
r,p,calls=run(7200);assert len(calls)==1 and {e['kind'] for e in r['events']}=={'initial-9-minute','hourly'} and p['next_hour_unix']==10800;checks.append('late dense + hourly events share one collection')
r,p,calls=run(1000,stopped=True);assert r['action']=='pause_automation' and not calls;checks.append('owner stop wins over initial phase')
r,p,calls=run(1000,busy=True);assert r['action']=='deferred' and not r['notify'] and not calls and set(p['catchups'])==set(s.c.BOARDS) and p['intro_9minute']['next_unix']==1540;checks.append('busy lease stays quiet with bounded catch-ups')
p=plan();p['hours']['0'].update(extra_attempted=False,extra_due_unix=990);r,p,calls=run(1000,p);assert len(calls)==1 and [e['kind'] for e in r['events']]==['initial-9-minute'] and p['hours']['0']['extra_due_unix']>=1180;checks.append('random 2512 extra remains additional')
p=plan();p.pop('intro_9minute');r,p,calls=run(1000,p);assert r['action']=='wait' and not calls;checks.append('ordinary hourly schedules unchanged')
print('PASS',len(checks),'offline schedule cases')
for check in checks:print('-',check)
