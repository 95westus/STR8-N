"""Offline refusal tests for the revised, explicitly accepted prerelease scope."""
import copy,json
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import publish_bf1_recorded_results as p
def main():
    pointer=p.read(p.Q/'bf1-scoped-publication-plan-current.json');plan=p.read(pointer['plan']);out=Path(pointer['plan']).parent;active=p.read(p.Q/'active-rtc-campaign.json');state=p.read(active['campaign_state']);now=datetime(2026,10,18,3,0,tzinfo=timezone.utc);checks=[]
    target=p.Q/'bf1-recorded-publication-gate-tests-2026-10-18-r1.json';assert not target.exists()
    def passed(name):checks.append(dict(name=name,passed=True))
    def refused(name,call):
        try:call()
        except (ValueError,KeyError,FileNotFoundError):passed(name)
        else:raise AssertionError('Accepted prohibited publication: '+name)
    assert p.validate(plan,now,state)['passed'];passed('Owner-accepted recorded results and disclosed RTC issue are admitted without claiming numeric gate passes')
    policy=p.read(plan['policy']);assert policy['soaks']['2609']['minimum_monitored_hours']==4 and policy['RTC']['minimum_powered_segment_hours']==168
    assert not policy['prerelease']['full_release_qualified'];passed('Original four-hour/endurance/RTC numerical targets retained for full acceptance')
    refused('Expired owner publication window refuses',lambda:p.validate(plan,datetime(2026,10,18,5,0,tzinfo=timezone.utc),state))
    for key,value in [('tag','v2.1'),('release_id',1),('scope','generic'),('full_release_qualified',True),('notes_sha256','0'*64),('policy_sha256','0'*64),('original_draft_sha256','0'*64),('expires_utc','2026-10-19T05:00:00+00:00')]:
        changed=copy.deepcopy(plan);changed[key]=value;refused('Changed '+key+' refuses',lambda changed=changed:p.validate(changed,now,state))
    changed=copy.deepcopy(plan);next(iter(changed['assets'].values()))['sha256']='0'*64;refused('Changed asset digest refuses',lambda:p.validate(changed,now,state))
    for key,value in [('RTC_sampling_active',True),('snapshot_boards',['2609']),('soak_active',True)]:
        changed=copy.deepcopy(state);changed[key]=value;refused('Unexpected active campaign '+key+' refuses',lambda changed=changed:p.validate(plan,now,changed))
    original_read=p.read
    for field in ('accepted_as_recorded','RTC_issue_accepted_for_disclosed_prerelease','keep_soaks_stopped','keep_RTC_sampling_stopped'):
        def altered_read(path,field=field):
            obj=original_read(path)
            if str(path)==plan['owner_authorization']:obj[field]=False
            return obj
        with patch.object(p,'read',altered_read):refused('Missing owner consent '+field+' refuses',lambda:p.validate(plan,now,state))
    def incomplete(path):
        obj=original_read(path)
        if str(path)==plan['distribution_checkpoint']:obj['linux_migration_recovery_package_tested']=False
        return obj
    with patch.object(p,'read',incomplete):refused('Incomplete Linux package gate refuses',lambda:p.validate(plan,now,state))
    remote=dict(assets=[dict(id=n,name=name,size=info['bytes'],digest='sha256:'+info['sha256']) for n,(name,info) in enumerate(plan['assets'].items(),1)])
    assert len(p.verify_assets(remote,plan['assets']))==6;passed('Exact six-asset public revision verified')
    bad=copy.deepcopy(remote);bad['assets'][0]['digest']='sha256:'+'0'*64;refused('Remote digest mismatch refuses',lambda:p.verify_assets(bad,plan['assets']))
    bad=copy.deepcopy(remote);bad['assets'].append(dict(id=99,name='unreviewed.bin',size=1,digest='sha256:'+'0'*64));refused('Unreviewed remote asset refuses',lambda:p.verify_assets(bad,plan['assets']))
    result=dict(passed=True,cases=len(checks),checks=checks,publisher_sha256=p.sha(Path(p.__file__)),test_sha256=p.sha(Path(__file__)),board_access=False,GitHub_access=False,publication=False)
    p.save(target,result);p.save(out/'publication-tool-pin.json',dict(publisher_sha256=result['publisher_sha256'],test_report=str(target),test_report_sha256=p.sha(target),test_sha256=result['test_sha256']))
    print('PASS',len(checks),'revised publication admission/refusal checks; no hardware or GitHub mutation')
if __name__=='__main__':main()
