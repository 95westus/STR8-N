"""Publish the audited one-ZIP revision with uchess.a, then audit its public download."""
import json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
import publish_bf1_recorded_results as p
import audit_bf1_published_zip as checker
ROOT=p.ROOT;Q=p.Q;OUT=ROOT/'output/releases/bf1-complete-release-2026-10-18-r2'
def main():
    prepared=p.read(OUT/'report.json');archive=Path(prepared['path']);p.require(prepared['passed'] and p.sha(archive)==prepared['sha256'],'Changed revised ZIP')
    audit=Q/'bf1-release-r2-content-audit-2026-10-18-r2/report.json';p.require(p.read(audit)['passed'] and p.read(audit)['zip_sha256']==prepared['sha256'],'Revised content/privacy audit missing')
    session=Q/'bf1-uchess-asm-session-2026-10-18-r1/report.json';p.require(p.read(session)['passed'] and len(p.read(session)['checks'])==2 and p.sha(session)==prepared['uchess_session_sha256'],'Changed ASM/S/T/R qualification')
    for platform in ('windows','linux'):
        path=Q/f'bf1-published-zip-{platform}-workflows-2026-10-18-r1.json';p.require(p.read(path)['passed'] and p.sha(path)==prepared['platform_workflows'][platform],'Changed platform path test')
    pointer=p.read(Q/'bf1-github-publication-current.json');old_path=Path(pointer['receipt']);p.require(p.sha(old_path)==pointer['sha256'],'Changed current receipt');old=p.read(old_path);assets=dict(old['assets'])
    assets[archive.name]=dict(path=str(archive),bytes=archive.stat().st_size,sha256=p.sha(archive));base='repos/'+old['repo']
    active=p.read(Q/'active-rtc-campaign.json');state=p.read(active['campaign_state']);p.require(not state['RTC_sampling_active'] and state['snapshot_boards']==[] and not state['soak_active'],'Owner-stopped campaign changed')
    release=p.gh('api',f"{base}/releases/{old['release_id']}");p.require(not release['draft'] and release['prerelease'] and release['tag_name']=='v2.0bf1','Wrong public prerelease');remote=p.verify_assets(release,assets)
    if not (OUT/'upload-intent.json').exists():p.save(OUT/'upload-intent.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),owner_request='Verify published ZIP, no WDCMONV2/private data, include uchess.a ASM session and S/T/R example',release_id=old['release_id'],new_asset=assets[archive.name],audit_sha256=p.sha(audit),session_test_sha256=p.sha(session),existing_published_assets_preserved=True))
    if archive.name not in remote:p.gh('api','--method','POST',f"https://uploads.github.com/{base}/releases/{old['release_id']}/assets?name={archive.name}",'-H','Content-Type: application/octet-stream','--input',archive)
    release=p.gh('api',f"{base}/releases/{old['release_id']}");remote=p.verify_assets(release,assets);p.require(set(remote)==set(assets),'Published revision asset set differs')
    url=remote[archive.name]['browser_download_url']
    intro=f"## Complete release ZIP — start here\n\n**[Download {archive.name}]({url})**\n\nOne ZIP contains all firmware BINs/apps, Windows and Linux migration/recovery\ntools, required S19s, complete manuals/quick starts, credited uChess source and\nchecksums. Revision 2 adds **uchess-source/uchess.a** and the worked\n**docs/UCHESS_ASM_SESSION.md** example: actual ASM 0.5 assembly, Store/Table/Restore,\nload-only restoration and run. The session passed with MON A and MON B in the\nW65C02 CPU model; board soaks and RTC sampling remain stopped.\n\nThe actual prior published download and this revision passed content/provenance\nand privacy audits: all BINs/apps and tools match qualified source-derived bytes;\nno WDCMONV2 images/code fingerprints, board captures, private host paths or\ncredential patterns were found. Windows/Linux packaged workflows were rechecked\nwith simulated serial endpoints. Linux physical serial migration remains untested.\n\nExtract the whole folder and start with README.md. No other bf1 package download\nis required. Previous revisions and individual assets are retained as optional\narchives; this revision is the primary complete release.\n\nSHA-256: `{prepared['sha256']}`\n\n---\n\n"
    body=release['body'];p.require(body.startswith('## Complete release ZIP — start here') and '\n---\n\n' in body,'Cannot safely update primary ZIP section')
    remainder=body.split('\n---\n\n',1)[1]
    body=intro+remainder
    body=body.replace('The all-assets checksum file covers the\noriginal and added downloads.','The older all-assets checksum file covers the component downloads; the\nprimary complete ZIP has the digest above and an internal SHA256SUMS.txt.')
    request=OUT/'notes-request.json';p.save(request,dict(body=body,prerelease=True,make_latest='false'));p.save(OUT/'release-before.json',release);release=p.gh('api','--method','PATCH',f"{base}/releases/{old['release_id']}",'--input',request)
    p.require(release['body'].startswith(intro),'Primary audited ZIP link not confirmed')
    downloaded=OUT/'published-release-r2.zip';http=urllib.request.Request(url,headers={'User-Agent':'STR8-N-release-audit'})
    with urllib.request.urlopen(http,timeout=60) as response:download=response.read()
    p.require(p.sha(archive)==checker.sha(download),'Published ZIP download differs from audited bytes')
    if not downloaded.exists():downloaded.write_bytes(download)
    else:p.require(p.sha(downloaded)==prepared['sha256'],'Prior downloaded revision differs')
    proof_dir=Q/'bf1-release-r2-published-content-audit-2026-10-18-r1'
    if not (proof_dir/'report.json').exists():checker.audit(downloaded,proof_dir)
    public_request=urllib.request.Request(f"https://api.github.com/{base}/releases/tags/v2.0bf1",headers={'User-Agent':'STR8-N-release-audit'})
    with urllib.request.urlopen(public_request,timeout=30) as response:public=json.load(response)
    p.require(public['id']==old['release_id'] and set(p.verify_assets(public,assets))==set(assets),'Anonymous public release verification failed')
    receipt=dict(published=True,repo=old['repo'],tag=old['tag'],release_id=old['release_id'],url=release['html_url'],published_at=release['published_at'],updated_utc=datetime.now(timezone.utc).isoformat(),source_commit=old['source_commit'],assets=assets,asset_count=len(assets),primary_release_zip=archive.name,primary_release_download=url,primary_release_sha256=prepared['sha256'],single_complete_release=True,release_revision=2,published_download_audit=str(proof_dir/'report.json'),published_download_audit_sha256=p.sha(proof_dir/'report.json'),uchess_a_source_and_ASM_session_included=True,ASM_S_T_R_qualified_both_slots=True,all_firmware_runtime_bytes_unchanged=True,base_publication=str(old_path),base_publication_sha256=p.sha(old_path),existing_assets_unchanged=True,full_release_qualified=False,RTC_known_issue_disclosed=True,soaks_and_RTC_sampling_stopped=True,board_access=False)
    p.save(OUT/'publication.json',receipt);p.save(Q/'bf1-github-publication-current.json',dict(receipt=str(OUT/'publication.json'),sha256=p.sha(OUT/'publication.json')))
    work=p.read(Q/'bf1-distribution-work-state.json');work.update(primary_release_zip=str(archive),primary_release_download=url,publication_receipt=str(OUT/'publication.json'),published_zip_audit=str(proof_dir/'report.json'),uchess_ASM_session=str(ROOT/'docs/bf1/UCHESS_ASM_SESSION.md'),uchess_ASM_S_T_R_qualified=True,soaks_and_RTC_restart_permitted=False);p.save(Q/'bf1-distribution-work-state.json',work)
    print(json.dumps(dict(published=True,download=url,sha256=prepared['sha256'],files=prepared['files'],published_zip_reaudited=True,uchess_a_and_S_T_R_example=True,soaks_and_RTC_sampling_stopped=True),indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,RuntimeError) as error:raise SystemExit('STOP: '+str(error))
