"""Publish the explicitly owner-amended scoped prerelease; never access board ports."""
import argparse,hashlib,json,os,subprocess,sys,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def save(path,obj):
    path=Path(path)
    with path.open('w',encoding='utf-8') as stream:json.dump(obj,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def gh(*args):
    result=subprocess.run(['gh',*map(str,args)],capture_output=True,text=True,timeout=120)
    if result.returncode:raise RuntimeError('GitHub operation failed; inspect release ID before retry: '+result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else None
def validate(plan,now,state):
    require(plan['scope']=='owner-accepted-recorded-results' and plan['repo']=='95westus/STR8-N' and plan['release_id']==416090350 and plan['tag']=='v2.0bf1','Wrong publication identity/scope')
    require(now<datetime.fromisoformat(plan['expires_utc']),'Owner publication window expired')
    require(plan['same_release_only'] and plan['no_same_name_asset_replacement'] and plan['retain_prior_sealed_bytes'] and not plan['full_release_qualified'],'Sealed revision/release scope changed')
    auth_path=Path(plan['owner_authorization']);require(sha(auth_path)==plan['owner_authorization_sha256'],'Changed owner authorization');auth=read(auth_path)
    require(plan['expires_utc']==auth['expires_utc']=='2026-10-18T05:00:00+00:00','Publication window was extended without authorization')
    require(auth['accepted_as_recorded'] and auth['RTC_issue_accepted_for_disclosed_prerelease'] and not auth['RTC_failure_resolved'] and auth['keep_soaks_stopped'] and auth['keep_RTC_sampling_stopped'],'Missing accepted recorded-results/RTC disclosure scope')
    require(sha(plan['policy'])==plan['policy_sha256'],'Changed acceptance policy');policy=read(plan['policy']);require(policy['prerelease']['recorded_results_scope'] and policy['prerelease']['owner_scope_authorization_sha256']==plan['owner_authorization_sha256'],'Wrong current prerelease policy')
    require(not policy['prerelease']['requires_active_2604_worker'] and not policy['prerelease']['requires_current_RTC_sampling'] and policy['prerelease']['RTC_preservation_failure_accepted_as_known_issue'],'Owner stop/known-issue amendment missing')
    require(not state['RTC_sampling_active'] and state['snapshot_boards']==[] and not state['soak_active'],'Owner-stopped campaign unexpectedly active')
    for item in policy['prerelease']['accepted_soak_receipts'].values():require(item['accepted_as_recorded'] and sha(item['receipt'])==item['sha256'],'Changed accepted stop evidence')
    require(sha(plan['distribution_checkpoint'])==plan['distribution_checkpoint_sha256'],'Changed distribution qualification');qualification=read(plan['distribution_checkpoint'])
    require(qualification['passed'] and not qualification['RTC_preservation_failure_closed'],'Wrong distribution/RTC claim')
    for key in policy['prerelease']['required_distribution_qualification']:require(qualification[key] is True,'Incomplete distribution gate '+key)
    for item in qualification['evidence'].values():require(sha(item['path'])==item['sha256'] and read(item['path'])['passed'],'Changed qualification evidence')
    require(sha(plan['platform_test'])==plan['platform_test_sha256'] and read(plan['platform_test'])['passed'],'Changed platform test')
    require(sha(plan['original_draft'])==plan['original_draft_sha256'],'Original sealed draft receipt changed')
    require(len(plan['assets'])==6 and not(set(plan['assets'])&set(plan['superseded_sealed_assets'])),'Wrong revision asset set')
    for name,info in {**plan['assets'],**plan['superseded_sealed_assets']}.items():
        path=Path(info['path']);require(path.name==name and path.stat().st_size==info['bytes'] and sha(path)==info['sha256'],'Changed current or preserved sealed asset '+name)
    require(sha(plan['notes'])==plan['notes_sha256'],'Changed disclosure notes')
    notes=Path(plan['notes']).read_text(encoding='utf-8')
    for text in ('3.880169','8.290165','unresolved','Linux physical serial migration has not been performed','owner-stopped','B3-only'):require(text in notes,'Required disclosure missing: '+text)
    image=Path(plan['assets']['str8n-2.0bf1-apps-str8n-only.bin']['path']).read_bytes();fixed=Path(plan['assets']['str8n-2.0bf1-b3-f000-ffff.bin']['path']).read_bytes()
    require(len(image)==98304 and len(fixed)==4096 and image[0x17000:0x18000]==fixed,'Complete/F image mismatch')
    require(hashlib.sha256(image).hexdigest()==qualification['complete_firmware_sha256'],'Changed app-complete image')
    return dict(passed=True,scope=plan['scope'],full_release_qualified=False,hardware_access=False)
def stopped_workers():
    query="@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'run_bf1_260[49]_soak\\.py' } | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,timeout=30)
    require(result.returncode==0,'Cannot independently inspect stopped worker processes')
    value=json.loads(result.stdout) if result.stdout.strip() else [];require(not value,'A workload worker is running despite owner stop')
    return dict(passed=True,active_matching_workers=0,query='Exact bf1 2604/2609 runner commands; read-only CIM')
def verify_assets(release,assets,allow_old=None):
    remote={x['name']:x for x in release['assets']};allowed=set(assets)|set(allow_old or {})
    require(set(remote)<=allowed,'Unexpected GitHub asset; do not publish')
    for name,value in remote.items():
        expected=(assets if name in assets else allow_old)[name]
        require(value['size']==expected['bytes'] and value.get('digest')=='sha256:'+expected['sha256'],'GitHub asset digest/size mismatch '+name)
    return remote
def existing_tag_commit(base,tag):
    result=subprocess.run(['gh','api',f'{base}/git/ref/tags/{tag}'],capture_output=True,text=True,timeout=30)
    if result.returncode:
        require('HTTP 404' in result.stderr,'Cannot verify existing publication tag')
        return None
    obj=json.loads(result.stdout)['object']
    if obj['type']=='tag':obj=gh('api',f"{base}/git/tags/{obj['sha']}")['object']
    require(obj['type']=='commit','Publication tag is not a commit')
    return obj['sha']
def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args()
    pointer=read(Q/'bf1-scoped-publication-plan-current.json');plan_path=Path(pointer['plan']);require(sha(plan_path)==pointer['sha256'],'Publication plan pointer mismatch');plan=read(plan_path);out=plan_path.parent
    policy_pointer=read(Q/'bf1-acceptance-policy-current.json');require(policy_pointer['sha256']==plan['policy_sha256'],'Current policy changed')
    active=read(Q/'active-rtc-campaign.json');require(sha(active['baseline_index'])==active['baseline_index_sha256'],'Immutable RTC baseline changed');state=read(active['campaign_state'])
    local=validate(plan,datetime.now(timezone.utc),state);processes=stopped_workers()
    base='repos/'+plan['repo'];release=gh('api',f"{base}/releases/{plan['release_id']}")
    existing=existing_tag_commit(base,plan['tag']);require(existing is None or existing==plan['source_commit'],'Existing publication tag points at a different source; no mutation permitted')
    require(release['id']==plan['release_id'] and release['target_commitish']==plan['source_commit'] and release['prerelease'],'Remote release identity/source changed')
    require(release['tag_name'] in (plan['tag'],'untagged-0361cd2f41a6778dff22'),'Unexpected remote tag')
    remote=verify_assets(release,plan['assets'],plan['superseded_sealed_assets']);intent=out/'publication-intent.json'
    require(release['draft'] or intent.exists(),'Release is public without this scoped publication intent')
    check=dict(passed=True,checked_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(plan_path),local=local,processes=processes,remote_release_id=release['id'],remote_draft=release['draft'],remote_assets=len(remote),publish_requested=a.publish)
    save(out/('readiness-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ')+'.json'),check)
    if not a.publish:print(json.dumps(check,indent=2));return
    pin=read(out/'publication-tool-pin.json')
    require(sha(Path(__file__))==pin['publisher_sha256'] and sha(pin['test_report'])==pin['test_report_sha256'] and read(pin['test_report'])['passed'],'Publisher tests/tool pin mismatch')
    if release['draft']:
        staging_intent=out/'asset-revision-intent.json'
        if not staging_intent.exists():save(staging_intent,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),release_id=release['id'],plan_sha256=sha(plan_path),new_assets=plan['assets'],prior_assets_preserved=plan['superseded_sealed_assets'],overwrite_existing_names=False))
        if not (out/'remote-before.json').exists():save(out/'remote-before.json',release)
        for name,info in plan['assets'].items():
            release=gh('api',f"{base}/releases/{plan['release_id']}");remote=verify_assets(release,plan['assets'],plan['superseded_sealed_assets'])
            if name in remote:continue
            gh('api','--method','POST',f"https://uploads.github.com/{base}/releases/{plan['release_id']}/assets?name={name}",'-H','Content-Type: application/octet-stream','--input',info['path'])
        release=gh('api',f"{base}/releases/{plan['release_id']}");remote=verify_assets(release,plan['assets'],plan['superseded_sealed_assets']);require(set(plan['assets'])<=set(remote),'New assets incomplete')
        # Retire obsolete draft associations only after all replacement-revision
        # names/digests verify; original bytes and receipts remain sealed locally.
        for name in plan['superseded_sealed_assets']:
            if name in remote:
                info=plan['superseded_sealed_assets'][name];require(sha(info['path'])==info['sha256'],'Lost sealed prior asset')
                gh('api','--method','DELETE',f"{base}/releases/assets/{remote[name]['id']}")
        release=gh('api',f"{base}/releases/{plan['release_id']}");remote=verify_assets(release,plan['assets']);require(set(remote)==set(plan['assets']),'Draft revision asset set incomplete')
        request=out/'stage-request.json';save(request,dict(tag_name=plan['tag'],target_commitish=plan['source_commit'],name='STR8-N 2.0bf1 — scoped prerelease',body=Path(plan['notes']).read_text(encoding='utf-8'),draft=True,prerelease=True,make_latest='false'))
        release=gh('api','--method','PATCH',f"{base}/releases/{plan['release_id']}",'--input',request)
        require(release['draft'] and release['tag_name']==plan['tag'] and release['body']==Path(plan['notes']).read_text(encoding='utf-8'),'Staged notes/tag mismatch')
        save(out/'draft-revision-verified.json',dict(passed=True,release=release,plan_sha256=sha(plan_path),prior_assets_retired_from_draft_only=True,prior_sealed_bytes_preserved=True))
        validate(plan,datetime.now(timezone.utc),read(active['campaign_state']));stopped_workers()
        if not intent.exists():save(intent,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),release_id=release['id'],plan_sha256=sha(plan_path),policy_sha256=plan['policy_sha256'],owner_authorization_sha256=plan['owner_authorization_sha256'],assets_verified=True,notes_sha256=plan['notes_sha256']))
        request=out/'publish-request.json';save(request,dict(draft=False,prerelease=True,make_latest='false'))
        release=gh('api','--method','PATCH',f"{base}/releases/{plan['release_id']}",'--input',request)
    require(not release['draft'] and release['prerelease'] and release['tag_name']==plan['tag'],'Publication not confirmed')
    remote=verify_assets(gh('api',f"{base}/releases/{plan['release_id']}"),plan['assets']);require(set(remote)==set(plan['assets']),'Published asset set mismatch')
    tag=gh('api',f"{base}/git/ref/tags/{plan['tag']}")
    obj=tag['object']
    if obj['type']=='tag':obj=gh('api',f"{base}/git/tags/{obj['sha']}")['object']
    require(obj['type']=='commit' and obj['sha']==plan['source_commit'],'Published tag source mismatch')
    public_url=f"https://api.github.com/{base}/releases/tags/{plan['tag']}"
    request=urllib.request.Request(public_url,headers={'User-Agent':'STR8-N-release-verification','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:public=json.load(response)
    require(public['id']==plan['release_id'] and not public['draft'] and public['prerelease'],'Anonymous public prerelease verification failed')
    require(set(verify_assets(public,plan['assets']))==set(plan['assets']),'Anonymous public asset mismatch')
    receipt=dict(published=True,repo=plan['repo'],tag=plan['tag'],release_id=release['id'],url=release['html_url'],published_at=release['published_at'],source_commit=plan['source_commit'],assets=plan['assets'],plan_sha256=sha(plan_path),owner_authorization_sha256=plan['owner_authorization_sha256'],public_anonymous_verification=True,asset_count=6,scope=plan['scope'],RTC_known_issue_disclosed=True,soaks_accepted_as_recorded=True,soaks_and_RTC_sampling_stopped=True,full_release_qualified=False,generic_installation_permitted=False,board_access=False)
    save(out/'publication.json',receipt);save(Q/'bf1-github-publication-current.json',dict(receipt=str(out/'publication.json'),sha256=sha(out/'publication.json')))
    legacy=read(Q/'bf1-tonight-publication-plan.json');legacy.update(publication_hold=False,publication_completed=True,publication_receipt=str(out/'publication.json'),superseded_by_scoped_plan=str(plan_path),legacy_publisher_must_not_run=True,publication_automation_paused=True);save(Q/'bf1-tonight-publication-plan.json',legacy)
    work=read(Q/'bf1-distribution-work-state.json');work.update(status='scoped-prerelease-published',owner_publication_hold=False,publication_completed=True,publication_receipt=str(out/'publication.json'),soaks_and_RTC_restart_permitted=False);save(Q/'bf1-distribution-work-state.json',work)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,RuntimeError) as error:raise SystemExit('STOP: '+str(error))
