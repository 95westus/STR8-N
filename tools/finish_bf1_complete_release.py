"""Verify and publish the single complete ZIP as the primary bf1 release download."""
import json,os,subprocess,urllib.request,zipfile
from pathlib import Path
from datetime import datetime,timezone
import publish_bf1_recorded_results as p
ROOT=p.ROOT;Q=p.Q;OUT=ROOT/'output/releases/bf1-complete-release-2026-10-18-r1'
def main():
    report=p.read(OUT/'report.json');archive=Path(report['path']);p.require(report['passed'] and p.sha(archive)==report['sha256'],'Combined release ZIP changed')
    test_dir=OUT/'clean extraction';p.require(not test_dir.exists(),'Keep previous extraction evidence');test_dir.mkdir()
    with zipfile.ZipFile(archive) as z:
        p.require(all((test_dir/n).resolve().is_relative_to(test_dir) for n in z.namelist()),'ZIP escapes extraction root');z.extractall(test_dir)
    root=test_dir/'str8n-2.0bf1';manifest=p.read(root/'release-manifest.json');actual={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file()}
    p.require(actual==set(manifest['files'])|{'release-manifest.json','SHA256SUMS.txt'},'Combined archive contains unlisted files')
    for name,info in manifest['files'].items():p.require((root/name).stat().st_size==info['bytes'] and p.sha(root/name)==info['sha256'],'Combined file digest mismatch '+name)
    for row in (root/'SHA256SUMS.txt').read_text().splitlines():
        digest,name=row.split('  ',1);p.require(p.sha(root/name)==digest,'Checksum mismatch '+name)
    commands=[];env=dict(os.environ,STR8N_PYTHON=os.sys.executable,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    linux='/mnt/c/'+root.resolve().as_posix()[3:]
    for platform in ('Windows','Linux'):
        for operation in ('verify','status'):
            if platform=='Windows':cmd='"'+os.environ['COMSPEC']+'" /d /s /c ""'+str(root/'bf1.cmd')+'" '+operation+'"'
            else:cmd=['wsl.exe','-d','Ubuntu-24.04','--exec','/usr/bin/env','STR8N_PYTHON=/usr/bin/python3','PYTHONDONTWRITEBYTECODE=1','/bin/sh',linux+'/bf1.sh',operation]
            result=subprocess.run(cmd,cwd=test_dir,env=env,capture_output=True,text=True,timeout=60);p.require(result.returncode==0,platform+' combined launcher failed: '+result.stderr)
            if operation=='verify':p.require('PASS bf1 kit hashes' in result.stdout,'Combined kit verification failed')
            else:p.require(json.loads(result.stdout)['live_installation_enabled'],'Combined live scope lost')
            commands.append(dict(platform=platform,operation=operation,passed=True,stdout=result.stdout))
    p.save(OUT/'tests.json',dict(passed=True,commands=commands,all_74_files_and_checksums_verified=True,prior_tested_runtime_bytes_unchanged=True,board_access=False))
    pointer=p.read(Q/'bf1-github-publication-current.json');old_path=Path(pointer['receipt']);p.require(p.sha(old_path)==pointer['sha256'],'Current publication receipt changed');old=p.read(old_path)
    existing=old['assets'];name=archive.name;assets={**existing,name:dict(path=str(archive),bytes=archive.stat().st_size,sha256=p.sha(archive))};base='repos/'+old['repo']
    release=p.gh('api',f"{base}/releases/{old['release_id']}");p.require(not release['draft'] and release['prerelease'] and release['tag_name']=='v2.0bf1','Wrong public release')
    remote=p.verify_assets(release,assets);p.require(set(existing)<=set(remote),'Existing published asset missing')
    if not (OUT/'upload-intent.json').exists():p.save(OUT/'upload-intent.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),owner_request='I want a ZIP for a release; one complete release deliverable',release_id=old['release_id'],new_asset=assets[name],existing_assets_unchanged=True))
    if name not in remote:p.gh('api','--method','POST',f"https://uploads.github.com/{base}/releases/{old['release_id']}/assets?name={name}",'-H','Content-Type: application/octet-stream','--input',archive)
    release=p.gh('api',f"{base}/releases/{old['release_id']}");remote=p.verify_assets(release,assets);p.require(set(remote)==set(assets),'Complete ZIP public asset missing')
    url=remote[name]['browser_download_url'];intro=f"## Complete release ZIP — start here\n\n**[Download {name}]({url})**\n\nOne ZIP contains both Windows/Linux migration and recovery tools, the full-system\nand boot/core BINs, MON A/MON B/F components, required S19s, all manuals and\nquick starts, rendered diagrams, credited uChess source and checksums. Extract\nthe whole folder and start with README.md. No other bf1 package download is required.\n\nSHA-256: `{assets[name]['sha256']}`\n\nIndividual downloads below are optional alternatives.\n\n---\n\n"
    if not release['body'].startswith('## Complete release ZIP — start here'):
        p.save(OUT/'release-before.json',release);request=OUT/'notes-request.json';p.save(request,dict(body=intro+release['body'],prerelease=True,make_latest='false'));release=p.gh('api','--method','PATCH',f"{base}/releases/{old['release_id']}",'--input',request)
    p.require(release['body'].startswith(intro),'Primary ZIP release instructions not confirmed')
    request=urllib.request.Request(f"https://api.github.com/{base}/releases/tags/v2.0bf1",headers={'User-Agent':'STR8-N-release-verification'})
    with urllib.request.urlopen(request,timeout=30) as response:public=json.load(response)
    p.require(public['id']==old['release_id'] and set(p.verify_assets(public,assets))==set(assets),'Anonymous public ZIP verification failed')
    receipt=dict(published=True,repo=old['repo'],tag=old['tag'],release_id=old['release_id'],url=release['html_url'],published_at=release['published_at'],updated_utc=datetime.now(timezone.utc).isoformat(),source_commit=old['source_commit'],assets=assets,asset_count=len(assets),primary_release_zip=name,primary_release_download=url,primary_release_sha256=assets[name]['sha256'],single_complete_release=True,tests_sha256=p.sha(OUT/'tests.json'),base_publication=str(old_path),base_publication_sha256=p.sha(old_path),existing_assets_unchanged=True,public_anonymous_verification=True,full_release_qualified=False,RTC_known_issue_disclosed=True,soaks_and_RTC_sampling_stopped=True,board_access=False)
    p.save(OUT/'publication.json',receipt);p.save(Q/'bf1-github-publication-current.json',dict(receipt=str(OUT/'publication.json'),sha256=p.sha(OUT/'publication.json')))
    work=p.read(Q/'bf1-distribution-work-state.json');work.update(primary_release_zip=str(archive),primary_release_download=url,single_complete_release_zip=True,publication_receipt=str(OUT/'publication.json'),soaks_and_RTC_restart_permitted=False);p.save(Q/'bf1-distribution-work-state.json',work)
    print(json.dumps(dict(published=True,download=url,bytes=archive.stat().st_size,sha256=assets[name]['sha256'],single_complete_release=True,soaks_and_RTC_sampling_stopped=True),indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,RuntimeError) as error:raise SystemExit('STOP: '+str(error))
