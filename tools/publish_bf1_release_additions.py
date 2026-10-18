"""Add owner-requested A/B/core/manual assets without replacing any published byte."""
import json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
import publish_bf1_recorded_results as p
ROOT=p.ROOT;Q=p.Q;OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17/revisions/monitor-core-docs-r1'
def main():
    plan=p.read(OUT/'preparation-r2.json');p.require(plan['passed'] and plan['no_existing_asset_replacement'],'Unqualified additions')
    p.require(p.sha(plan['base_publication'])==plan['base_publication_sha256'] and p.read(plan['base_publication'])['published'],'Changed base publication receipt')
    p.require(p.sha(plan['core_test'])==plan['core_test_sha256'] and p.read(plan['core_test'])['passed'],'Changed B3 core model qualification')
    p.require(p.read(plan['core_test'])['model_only'] and not p.read(plan['core_test'])['hardware_core_only_installation_tested'],'Core qualification overstated')
    assets={**plan['existing_assets'],**plan['new_assets']};p.require(not(set(plan['existing_assets'])&set(plan['new_assets'])) and len(assets)==11,'Additions overlap published names')
    for name,info in assets.items():p.require(Path(info['path']).name==name and Path(info['path']).stat().st_size==info['bytes'] and p.sha(info['path'])==info['sha256'],'Changed asset '+name)
    addition=(OUT/'release-notes-addition.md').read_text(encoding='utf-8');p.require(p.sha(OUT/'release-notes-addition.md')==plan['notes_addition_sha256'],'Changed documentation addition')
    active=p.read(Q/'active-rtc-campaign.json');state=p.read(active['campaign_state']);p.require(not state['RTC_sampling_active'] and not state['soak_active'] and state['snapshot_boards']==[],'Owner-stopped campaign state changed')
    base='repos/'+plan['repo'];release=p.gh('api',f"{base}/releases/{plan['release_id']}")
    p.require(not release['draft'] and release['prerelease'] and release['tag_name']==plan['tag'] and release['target_commitish']==plan['source_commit'],'Published release identity changed')
    remote=p.verify_assets(release,assets);p.require(set(plan['existing_assets'])<=set(remote),'Published original asset missing')
    if not (OUT/'upload-intent.json').exists():p.save(OUT/'upload-intent.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),owner_request=plan['owner_request'],release_id=release['id'],preparation_sha256=p.sha(OUT/'preparation-r2.json'),new_assets=plan['new_assets'],overwrite_or_delete_existing_assets=False))
    if not (OUT/'release-before.json').exists():p.save(OUT/'release-before.json',release)
    for name,info in plan['new_assets'].items():
        release=p.gh('api',f"{base}/releases/{plan['release_id']}");remote=p.verify_assets(release,assets)
        if name in remote:continue
        p.gh('api','--method','POST',f"https://uploads.github.com/{base}/releases/{plan['release_id']}/assets?name={name}",'-H','Content-Type: application/octet-stream','--input',info['path'])
    release=p.gh('api',f"{base}/releases/{plan['release_id']}");p.require(set(p.verify_assets(release,assets))==set(assets),'New public asset set incomplete')
    if '## Boot/core, full-system and component choices' not in release['body']:
        body=release['body']+addition;request=OUT/'notes-request.json';p.save(request,dict(body=body,prerelease=True,make_latest='false'));release=p.gh('api','--method','PATCH',f"{base}/releases/{plan['release_id']}",'--input',request)
    p.require(release['body'].endswith(addition),'Release documentation does not match prepared addition')
    p.require(p.existing_tag_commit(base,plan['tag'])==plan['source_commit'],'Published source tag changed')
    request=urllib.request.Request(f"https://api.github.com/{base}/releases/tags/{plan['tag']}",headers={'User-Agent':'STR8-N-release-verification'})
    with urllib.request.urlopen(request,timeout=30) as response:public=json.load(response)
    p.require(public['id']==plan['release_id'] and not public['draft'] and public['prerelease'] and set(p.verify_assets(public,assets))==set(assets),'Anonymous public verification failed')
    receipt=dict(published=True,repo=plan['repo'],tag=plan['tag'],release_id=plan['release_id'],url=release['html_url'],published_at=release['published_at'],updated_utc=datetime.now(timezone.utc).isoformat(),source_commit=plan['source_commit'],assets=assets,asset_count=11,base_publication=plan['base_publication'],base_publication_sha256=plan['base_publication_sha256'],preparation_sha256=p.sha(OUT/'preparation-r2.json'),existing_six_assets_unchanged=True,public_anonymous_verification=True,core_only_model_qualified=True,physical_core_only_tested=False,full_release_qualified=False,RTC_known_issue_disclosed=True,soaks_and_RTC_sampling_stopped=True,board_access=False)
    p.save(OUT/'publication.json',receipt);p.save(Q/'bf1-github-publication-current.json',dict(receipt=str(OUT/'publication.json'),sha256=p.sha(OUT/'publication.json')))
    work=p.read(Q/'bf1-distribution-work-state.json');work.update(publication_receipt=str(OUT/'publication.json'),published_monitor_and_core_bins=True,published_separate_docs=True,published_asset_count=11,release_paths_guide=str(ROOT/'docs/STR8N_BF1_RELEASE_PATHS.md'),soaks_and_RTC_restart_permitted=False);p.save(Q/'bf1-distribution-work-state.json',work)
    print(json.dumps(dict(published=True,url=receipt['url'],asset_count=11,added=list(plan['new_assets']),existing_assets_unchanged=True,soaks_and_RTC_sampling_stopped=True),indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,RuntimeError) as error:raise SystemExit('STOP: '+str(error))
