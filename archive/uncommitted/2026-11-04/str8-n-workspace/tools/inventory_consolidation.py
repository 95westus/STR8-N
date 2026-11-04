"""Read-only repository/release inventory and private asset verification.

Consumes GitHub connector snapshots. gh is used ONLY for authenticated GETs
and binary downloads. No checkout/fetch/push/tag/remote/settings mutations.
Archives are listed, never extracted or executed. Output stays owner-local.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPOS=('95westus/STR8-N','95westus/STR8N-F')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def snapshot(folder,name):
    raw=json.loads((folder/name).read_text(encoding='utf-8'))
    if raw.get('isError'):
        raise ValueError('Connector snapshot failed: '+name)
    return json.loads(raw['structuredContent']['content'])


def gh_get(endpoint,output=None):
    command=['gh','api','--method','GET',endpoint]
    if output:
        command+=['--header','Accept: application/octet-stream']
        with output.open('xb') as stream:
            result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,timeout=120)
        return result.returncode,result.stderr.decode('utf-8',errors='replace')[:600]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    if result.returncode:
        return {'read_succeeded':False,'error':result.stderr.strip()[:600]}
    return {'read_succeeded':True,'data':json.loads(result.stdout)}


def git(path,*args):
    r=subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True,timeout=30)
    if r.returncode:raise RuntimeError('Local git read failed: '+str(path)+' '+r.stderr[:200])
    return r.stdout.strip()


def local_inventory():
    candidates=[ROOT,ROOT/'bootstrap-opaque',ROOT/'release/str8nf-v0.2.0']
    candidates += [p for p in ROOT.parent.iterdir() if p.is_dir() and 'str8' in p.name.lower()]
    records=[]; seen=set()
    for path in candidates:
        if path.resolve() in seen or not (path/'.git').exists():continue
        seen.add(path.resolve())
        records.append(dict(path=str(path),head=git(path,'rev-parse','HEAD'),branch=git(path,'branch','--show-current'),
            remotes=git(path,'remote','-v').splitlines(),
            tracking=git(path,'for-each-ref','--format=%(refname:short)|%(objectname)|%(upstream:short)|%(upstream:track)','refs/heads').splitlines(),
            tags=git(path,'for-each-ref','--format=%(refname:strip=2)|%(objectname)|%(objecttype)|%(*objectname)','refs/tags').splitlines(),
            worktrees=git(path,'worktree','list','--porcelain'),
            tracked_changes=git(path,'status','--porcelain=v1','--untracked-files=no').splitlines(),
            untracked_paths=git(path,'ls-files','--others','--exclude-standard').splitlines()))
    return records


def archive_index(path):
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                entries=[dict(path=x.filename,bytes=x.file_size) for x in z.infolist()]
        elif path.name.endswith(('.tar.gz','.tgz','.tar')):
            with tarfile.open(path,'r:*') as t:
                entries=[dict(path=x.name,bytes=x.size) for x in t.getmembers()]
        else:return None
        flags=[x['path'] for x in entries if re.search(r'wdcmon|private|escrow|capture|backup|vendor|secret|credential|\.env(?:$|/)',x['path'],re.I)]
        licenses=[x['path'] for x in entries if re.search(r'license|copying|notice',x['path'],re.I)]
        return dict(entries=entries,entry_count=len(entries),license_paths=licenses,
                    review_path_flags=flags,content_executed=False,extracted=False,
                    classification='PATH_NAMES_ONLY_NOT_A_CONTENT_OR_REDISTRIBUTION_CLEARANCE')
    except (OSError,ValueError,tarfile.TarError,zipfile.BadZipFile) as error:
        return dict(error=str(error),classification='ARCHIVE_REVIEW_PENDING')


def run(source,out):
    source,out=Path(source).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    (out/'.gitignore').write_text('*\n',encoding='ascii')
    started=datetime.now(timezone.utc).isoformat()
    local=local_inventory();save(out/'local-clones-before.json',local)
    repositories=[];releases=[];tags=[];assets=[];integrations=[]
    for repo in REPOS:
        short=repo.split('/')[1]
        meta=snapshot(source,short+'-repository.json')
        branches=snapshot(source,short+'-branches.json')
        rows=snapshot(source,short+'-releases.json')
        refs=snapshot(source,short+'-tag-refs.json')
        if len(branches)>=100 or len(rows)>=100:
            raise ValueError('Additional collection pages required')
        repositories.append(dict(full_name=repo,id=meta['id'],visibility=meta['visibility'],
            default_branch=meta['default_branch'],head=next(b['commit']['sha'] for b in branches if b['name']==meta['default_branch']),
            archived=meta['archived'],license=(meta.get('license') or {}).get('spdx_id'),has_pages=meta['has_pages'],
            created_at=meta['created_at'],updated_at=meta['updated_at'],pushed_at=meta['pushed_at'],
            url=meta['html_url'],clone_url=meta['clone_url'],branches=branches,
            branches_complete=len(branches)<100,releases_complete=len(rows)<100))
        annotation={}
        for file in source.glob(short+'-annotated-*.json'):
            data=snapshot(source,file.name);annotation[data['sha']]=data
        for ref in refs:
            obj=ref['object']; chain=[]
            while obj['type']=='tag':
                data=annotation[obj['sha']];chain.append(data);obj=data['object']
            tags.append(dict(repository=repo,name=ref['ref'][10:],ref=ref['ref'],
                object_sha=ref['object']['sha'],object_type=ref['object']['type'],commit_sha=obj['sha'],
                annotation=chain,release_exists=any(r['tag_name']==ref['ref'][10:] for r in rows)))
        for row in rows:
            tag=next((t for t in tags if t['repository']==repo and t['name']==row['tag_name']),None)
            release=dict(repository=repo,visibility=meta['visibility'],id=row['id'],tag=row['tag_name'],
                title=row['name'],url=row['html_url'],draft=row['draft'],prerelease=row['prerelease'],
                created_at=row['created_at'],published_at=row['published_at'],updated_at=row.get('updated_at'),
                target_commitish=row['target_commitish'],resolved_tag_commit=tag['commit_sha'] if tag else None,
                body=row.get('body') or '',assets=len(row['assets']),
                zipball_url=row['zipball_url'],tarball_url=row['tarball_url'],
                source_archive_backup='NOT_DOWNLOADED_IN_THIS_PASS',
                disposition='PRESERVE_EXISTING_PUBLIC_RELEASE' if meta['visibility']=='public' else 'REVIEW_BEFORE_PUBLIC_MIGRATION')
            if not row['assets']:release['disposition']='ASSETLESS_ANNOUNCEMENT_OR_LINK_REVIEW'
            releases.append(release)
            for a in row['assets']:
                assets.append(dict(repository=repo,release_id=row['id'],tag=row['tag_name'],id=a['id'],name=a['name'],
                    bytes=a['size'],api_digest=a.get('digest'),content_type=a['content_type'],
                    created_at=a['created_at'],updated_at=a['updated_at'],download_count=a['download_count'],
                    download_url=a['browser_download_url'],api_url=a['url'],
                    publication_review='EXISTING_PUBLIC' if meta['visibility']=='public' else 'REQUIRES_REVIEW'))
        for endpoint in ('actions/workflows?per_page=100','actions/permissions','rulesets?per_page=100',
                         'branches/'+meta['default_branch']+'/protection','hooks?per_page=100','environments?per_page=100'):
            result=gh_get('repos/'+repo+'/'+endpoint)
            # Webhook endpoints/URLs can contain credentials. Keep only IDs,
            # active state and event names; never record config URLs or secrets.
            if endpoint.startswith('hooks') and result.get('read_succeeded'):
                result['data']=[{k:x.get(k) for k in ('id','name','active','events')} for x in result['data']]
            integrations.append(dict(repository=repo,endpoint=endpoint,result=result))
    save(out/'repositories.json',repositories);save(out/'releases.json',releases)
    save(out/'tags.json',tags);save(out/'integrations.json',integrations)
    save(out/'assets.json',assets)
    print(f'Metadata: {len(repositories)} repositories, {len(releases)} releases, {len(tags)} tags, {len(assets)} assets',flush=True)
    def download(asset):
        # Asset ID namespace avoids collisions and treats remote filenames as
        # labels. Only the final basename is used within the fixed directory.
        if Path(asset['name']).name!=asset['name'] or re.search(r'[\\/:]',asset['name']):
            return dict(asset,verified=False,error='Unsafe asset filename')
        folder=out/'assets'/asset['repository'].split('/')[1]/str(asset['id']);folder.mkdir(parents=True)
        path=folder/asset['name']
        code,error=gh_get('repos/'+asset['repository']+'/releases/assets/'+str(asset['id']),path)
        result=dict(asset,local_file=path.relative_to(out).as_posix(),download_exit_code=code)
        if code:result.update(verified=False,error=error);return result
        data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
        result.update(actual_bytes=len(data),sha256=digest,
            size_matches=len(data)==asset['bytes'],
            api_digest_matches=asset['api_digest']=='sha256:'+digest if asset['api_digest'] else None)
        result['verified']=result['size_matches'] and result['api_digest_matches'] is not False
        index=archive_index(path)
        if index is not None:
            indexfile=folder/'archive-index.json';save(indexfile,index)
            result.update(archive_index=indexfile.relative_to(out).as_posix(),
                archive_entries=index.get('entry_count'),license_paths=index.get('license_paths',[]),
                review_path_flags=index.get('review_path_flags',[]))
        return result
    downloaded=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(download,a) for a in assets]
        for job in as_completed(jobs):
            result=job.result();downloaded.append(result)
            print(('VERIFIED ' if result['verified'] else 'FAILED ')+result['repository']+' '+result['name'],flush=True)
            save(out/'asset-verification-progress.json',downloaded)
    downloaded.sort(key=lambda x:(x['repository'],x['tag'],x['name']))
    save(out/'assets-verified.json',downloaded)
    duplicate_groups={}
    for item in downloaded:
        if item.get('verified'):duplicate_groups.setdefault(item['sha256'],[]).append(dict(repository=item['repository'],tag=item['tag'],name=item['name']))
    duplicate_groups={h:v for h,v in duplicate_groups.items() if len(v)>1}
    names={}
    for item in assets:names.setdefault(item['name'],[]).append(dict(repository=item['repository'],tag=item['tag'],id=item['id']))
    repeated_names={n:v for n,v in names.items() if len(v)>1}
    tag_names={}
    for item in tags:tag_names.setdefault(item['name'],[]).append(dict(repository=item['repository'],commit_sha=item['commit_sha']))
    tag_collisions={n:v for n,v in tag_names.items() if len(v)>1}
    save(out/'collisions.json',dict(tag_name_collisions=tag_collisions,repeated_asset_names=repeated_names,
                                  identical_asset_hashes=duplicate_groups))
    local_after=local_inventory();save(out/'local-clones-after.json',local_after)
    # This script creates an untracked tool/output in the parent working tree;
    # compare Git HEAD/remotes/tags, not the unrelated untracked-file list.
    unchanged=all(all(before[k]==after[k] for k in ('head','branch','remotes','tags')) for before,after in zip(local,local_after))
    report=dict(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
        repositories=len(repositories),releases=len(releases),tags=len(tags),assets=len(assets),
        assets_verified=sum(x['verified'] for x in downloaded),asset_bytes=sum(x['bytes'] for x in assets),
        api_digests_available=sum(bool(x['api_digest']) for x in assets),
        tag_collisions=len(tag_collisions),repeated_asset_names=list(repeated_names),
        identical_asset_hash_groups=len(duplicate_groups),local_heads_remotes_tags_unchanged=unchanged,
        remote_operations='GET_ONLY',pushed=False,renamed=False,visibility_changed=False,published=False,
        not_complete=['Full Git mirror/bundle backups','Auto-generated source zipball/tarball backups',
                      'Content/licensing clearance for private assets','External clones and automation remotes outside this workspace',
                      'Integration endpoints that returned permission/not-found errors'],
        inventory_complete_for_releases=all(x['releases_complete'] for x in repositories),
        asset_hash_verification_passed=all(x['verified'] for x in downloaded))
    save(out/'report.json',report)
    lines=['# Repository and release inventory — private working snapshot','',
           'Read-only inventory. No remote writes, publication, visibility changes or repository renames.','',
           '| Repository | Visibility | Branches | Tags | Releases | Assets |','| --- | --- | ---: | ---: | ---: | ---: |']
    for r in repositories:
        repo=r['full_name'];lines.append(f"| {repo} | {r['visibility']} | {len(r['branches'])} | {sum(t['repository']==repo for t in tags)} | {sum(t['repository']==repo for t in releases)} | {sum(t['repository']==repo for t in assets)} |")
    lines+=['','| Source | Release | Type | Assets | Proposed handling |','| --- | --- | --- | ---: | --- |']
    for r in releases:lines.append(f"| {r['repository']} | {r['tag']} | {'prerelease' if r['prerelease'] else 'release'} | {r['assets']} | {r['disposition']} |")
    lines+=['',f"Downloaded/verified assets: {report['assets_verified']}/{len(assets)}; {report['asset_bytes']:,} bytes.",
            f"Exact tag-name collisions: {len(tag_collisions)}. Repeated asset filenames: {', '.join(repeated_names) or 'none'}.",
            '','Keep releases in separate namespaces. An identical filename is not evidence of identical content.',
            'Hash verification confirms captured bytes; it does not clear private assets for publication.',
            '','## Remaining inventory work','']+['- '+x for x in report['not_complete']]
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshots',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run(args.snapshots,args.out)
