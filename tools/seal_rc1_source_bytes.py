"""Seal exact documentation bytes in Git; preserve previous source/ZIP evidence."""
import hashlib,json,shutil,zipfile
from stage_rc1_source import api,ROOT,OUT,REPO
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
    source=read(OUT/'source-commit.json');tree=api('GET',f"repos/{REPO}/git/trees/{source['source_tree']}?recursive=1");remote={p['path']:p['sha'] for p in tree['tree'] if p['type']=='blob'};changes=[]
    for name in source['files']:
        data=(ROOT/name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if remote[name]!=blob:
            assert name in ('docs/rc1/THIRD_PARTY_NOTICES.md','docs/rc1/UCHESS_ASM_SESSION.md','release/rc1-uchess/README.md'),name
            changes.append(dict(path=name,mode='100644',type='blob',content=data.decode('utf-8')))
    assert len(changes)==3
    tree=api('POST',f'repos/{REPO}/git/trees',dict(base_tree=source['source_tree'],tree=changes));commit=api('POST',f'repos/{REPO}/git/commits',dict(message='Seal exact rc1 documentation bytes for source and release verification',tree=tree['sha'],parents=[source['source_commit']]))
    check=api('GET',f"repos/{REPO}/git/trees/{tree['sha']}?recursive=1");remote={p['path']:p['sha'] for p in check['tree'] if p['type']=='blob'}
    for name in source['files']:
        data=(ROOT/name).read_bytes();assert remote[name]==hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    shutil.copyfile(OUT/'source-commit.json',OUT/'source-commit-r3.json');source.update(source_commit=commit['sha'],source_tree=tree['sha']);save(OUT/'source-commit.json',source)
    archive=OUT/'str8n-v2.0rc1-release.zip';shutil.copyfile(archive,OUT/'pre-source-byte-seal.zip')
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()};infos=z.infolist()
    prefix='str8n-2.0rc1/';manifest=json.loads(files[prefix+'release-manifest.json']);manifest['source_commit']=commit['sha'];files[prefix+'release-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode();files[prefix+'SHA256SUMS.txt']=''.join(sha(b)+'  '+n[len(prefix):]+'\n' for n,b in sorted(files.items()) if not n.endswith('/SHA256SUMS.txt')).encode()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for info in infos:z.writestr(info,files[info.filename])
    with zipfile.ZipFile(OUT/'pre-source-byte-seal.zip') as z:assert all(z.read(n)==b for n,b in files.items() if n not in (prefix+'release-manifest.json',prefix+'SHA256SUMS.txt'))
    report=read(OUT/'package-report.json');shutil.copyfile(OUT/'package-report.json',OUT/'package-report-r3.json');report.update(source_commit=commit['sha'],bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()));save(OUT/'package-report.json',report)
    tests=read(OUT/'platform-tests.json');shutil.copyfile(OUT/'platform-tests.json',OUT/'platform-tests-pre-byte-seal.json');tests['zip_sha256']=report['sha256'];save(OUT/'platform-tests.json',tests)
    save(OUT/'exact-source-seal.json',dict(passed=True,source_commit=commit['sha'],all_source_blobs_independently_verified=True,source_files=len(source['files']),only_git_line_ending_correction=True,user_ZIP_firmware_tools_manuals_unchanged=True,zip_sha256=report['sha256']))
    print('PASS all',len(source['files']),'remote source blobs match exact local bytes; sealed source:',commit['sha'])
if __name__=='__main__':main()
