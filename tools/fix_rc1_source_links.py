"""Resolve repository source links without changing any tested user-tool bytes."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from stage_rc1_source import api,ROOT,OUT,REPO
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
    source=read(OUT/'source-commit.json');changed=[]
    for name in ('docs/rc1/THIRD_PARTY_NOTICES.md','docs/rc1/UCHESS_ASM_SESSION.md'):
        p=ROOT/name;s=p.read_text(encoding='utf-8').replace('../uchess-source/','../../release/rc1-uchess/');p.write_text(s,encoding='utf-8');changed.append(p)
    p=ROOT/'release/rc1-uchess/README.md';p.write_text(p.read_text(encoding='utf-8').replace('../docs/UCHESS_ASM_SESSION.md','../../docs/rc1/UCHESS_ASM_SESSION.md'),encoding='utf-8');changed.append(p)
    tree=api('POST',f'repos/{REPO}/git/trees',dict(base_tree=source['source_tree'],tree=[dict(path=p.relative_to(ROOT).as_posix(),mode='100644',type='blob',content=p.read_text(encoding='utf-8')) for p in changed]))
    commit=api('POST',f'repos/{REPO}/git/commits',dict(message='Resolve rc1 manual and credited uChess source links in repository layout',tree=tree['sha'],parents=[source['source_commit']]))
    shutil.copyfile(OUT/'source-commit.json',OUT/'source-commit-r1.json')
    source.update(source_commit=commit['sha'],source_tree=tree['sha'])
    for p in changed:source['files'][p.relative_to(ROOT).as_posix()]=sha(p.read_bytes())
    save(OUT/'source-commit.json',source)
    archive=OUT/'str8n-v2.0rc1-release.zip';old=archive.read_bytes();shutil.copyfile(archive,OUT/'source-link-fix-original-candidate.zip')
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()};infos=z.infolist()
    prefix='str8n-2.0rc1/';manifest=json.loads(files[prefix+'release-manifest.json']);manifest['source_commit']=commit['sha'];files[prefix+'release-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    files[prefix+'SHA256SUMS.txt']=''.join(sha(b)+'  '+n[len(prefix):]+'\n' for n,b in sorted(files.items()) if not n.endswith('/SHA256SUMS.txt')).encode()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for info in infos:z.writestr(info,files[info.filename])
    with zipfile.ZipFile(OUT/'source-link-fix-original-candidate.zip') as z:
        unchanged=[n for n in files if n not in (prefix+'release-manifest.json',prefix+'SHA256SUMS.txt')];assert all(z.read(n)==files[n] for n in unchanged)
    report=read(OUT/'package-report.json');shutil.copyfile(OUT/'package-report.json',OUT/'package-report-r1.json');report.update(source_commit=commit['sha'],bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()));save(OUT/'package-report.json',report)
    tests=read(OUT/'platform-tests.json');shutil.copyfile(OUT/'platform-tests.json',OUT/'platform-tests-original-execution.json');tests.update(zip_sha256=report['sha256'],reused_for_byte_identical_software_inputs=True,original_execution_receipt_sha256=sha((OUT/'platform-tests-original-execution.json').read_bytes()),original_zip_sha256=sha(old),only_changes=['source commit reference in release manifest','checksum of manifest']);save(OUT/'platform-tests.json',tests)
    save(OUT/'source-link-fix-reuse.json',dict(passed=True,source_commit=commit['sha'],unchanged_files=len(unchanged),all_firmware_tools_templates_examples_manuals_byte_identical=True,original_zip_sha256=sha(old),new_zip_sha256=report['sha256'],platform_tests_reused_for_identical_software_inputs=True))
    print('PASS source links resolved; user ZIP software/docs unchanged; metadata now references',commit['sha'])
if __name__=='__main__':main()
