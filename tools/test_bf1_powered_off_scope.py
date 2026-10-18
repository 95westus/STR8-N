"""Offline tests for owner-evidenced collection suspension and publication freshness."""
import argparse,copy,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from check_bf1_acceptance import collection_scope,required_rtc_fresh
from publish_bf1_prerelease import readiness
Q=Path(__file__).resolve().parents[1]/'output/qualification'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Q/'bf1-powered-off-scope-tests-2026-10-18-r1.json');args=parser.parse_args()
    active=dict(boards=['2205','2512','2604','2609'],powered_off_boards=['2205','2512'])
    state=dict(powered_off_boards=['2205','2512'],powered_on_boards=['2604','2609'],snapshot_boards=['2604','2609'])
    events=[dict(board='2512',event='power_off_announced',recorded_utc='2026-10-18T00:47:25+00:00')]
    required,suspended=collection_scope(active,state,events,['2512','2604','2609']);assert required==['2604','2609'] and set(suspended)=={'2512'}
    checks=[dict(name='owner-power-off-restricts-collection',passed=True)]
    for name,change in [('no-owner-event',lambda a,s,e:e.clear()),('later-power-return',lambda a,s,e:e.append(dict(board='2512',event='power_on_announced',recorded_utc='2026-10-18T00:48:00+00:00'))),('active-board-omitted',lambda a,s,e:s.update(snapshot_boards=['2604'])),('soak-board-off',lambda a,s,e:(a['powered_off_boards'].append('2604'),s['powered_off_boards'].append('2604'))),('state-disagreement',lambda a,s,e:s.update(powered_off_boards=['2205']))]:
        a,s,e=copy.deepcopy((active,state,events));change(a,s,e)
        try:collection_scope(a,s,e,['2512','2604','2609'])
        except AssertionError:checks.append(dict(name=name,passed=True,refused=True))
        else:raise AssertionError(name)
    ptr=json.loads((Q/'bf1-acceptance-current.json').read_text());r=json.loads(Path(ptr['report']).read_text());r['required_rtc_boards']=required;r['powered_off_collection_suspended']=suspended
    r['RTC']['2512'].update(fresh=False,collection_suspended=True,collection_required=False,latest_sample_age_hours=100)
    for board in required:r['RTC'][board]['fresh']=True
    r['prerelease_ready']=True;r['errors']={};r['soaks']['2609'].update(status='passed',application_RAM_restored=True,monitored_hours=4,complete_cycles=1,coverage_review_required=False);r['soaks']['2604'].update(state='running',coverage_review_required=False)
    r['distribution_qualification']=dict(status='passed')
    now=datetime.now(timezone.utc);assert readiness(r,now,now+timedelta(hours=1));checks.append(dict(name='stale-powered-off-history-does-not-block-active-streams',passed=True))
    for name,change in [('stale-2604',lambda x:x['RTC']['2604'].update(fresh=False)),('stale-2609',lambda x:x['RTC']['2609'].update(fresh=False)),('unevidenced-omission',lambda x:x.update(powered_off_collection_suspended={})),('falsely-fresh-off-board',lambda x:x['RTC']['2512'].update(fresh=True)),('short-soak',lambda x:x['soaks']['2609'].update(monitored_hours=3.99)),('RAM-not-restored',lambda x:x['soaks']['2609'].update(application_RAM_restored=False))]:
        case=copy.deepcopy(r);change(case);assert not readiness(case,now,now+timedelta(hours=1)),name;checks.append(dict(name=name,passed=True,refused=True))
    out=args.out;assert not out.exists();out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,board_access=False,publisher_sha256=hashlib.sha256(Path(__file__).with_name('publish_bf1_prerelease.py').read_bytes()).hexdigest(),evaluator_sha256=hashlib.sha256(Path(__file__).with_name('check_bf1_acceptance.py').read_bytes()).hexdigest()),indent=2)+'\n');print('PASS',len(checks),'powered-off collection/publication checks')
if __name__=='__main__':main()
