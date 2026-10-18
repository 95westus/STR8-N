"""Close the final source-session notice after both actual rc1 model runs passed."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from stage_rc1_source import api,ROOT,OUT,REPO
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def main():
    proof=read(ROOT/'output/qualification/rc1-uchess-model-r2/report.json');assert proof['passed'] and len(proof['checks'])==2
    p=ROOT/'docs/rc1/THIRD_PARTY_NOTICES.md';old=p.read_text(encoding='utf-8');new=old.replace('Its existing ASM 0.4\nexample needs a current rc1/ASM 0.5 qualification before final release claims.','The compact source was assembled with the actual rc1 ASM 0.5 instructions\nand exercised through S/T/R and gameplay under both MON A and MON B in the\nW65C02 model. The session preserves the supplied UCHESS and creates UCHDEMO;\nno fresh physical board execution is claimed.')
    assert new!=old;p.write_text(new,encoding='utf-8')
    source=read(OUT/'source-commit.json');tree=api('POST',f'repos/{REPO}/git/trees',dict(base_tree=source['source_tree'],tree=[dict(path='docs/rc1/THIRD_PARTY_NOTICES.md',mode='100644',type='blob',content=new)]))
    commit=api('POST',f'repos/{REPO}/git/commits',dict(message='Finalize rc1 uChess attribution and completed ASM/S/T/R qualification notice',tree=tree['sha'],parents=[source['source_commit']]))
    shutil.copyfile(OUT/'source-commit.json',OUT/'source-commit-r2.json');source.update(source_commit=commit['sha'],source_tree=tree['sha']);source['files']['docs/rc1/THIRD_PARTY_NOTICES.md']=sha(p.read_bytes());save(OUT/'source-commit.json',source)
    archive=OUT/'str8n-v2.0rc1-release.zip';shutil.copyfile(archive,OUT/'pre-final-notice-candidate.zip')
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()};infos=z.infolist()
    prefix='str8n-2.0rc1/';notice=prefix+'docs/THIRD_PARTY_NOTICES.md';files[notice]=new.replace('../../release/rc1-uchess/','../uchess-source/').encode()
    manifest=json.loads(files[prefix+'release-manifest.json']);manifest['source_commit']=commit['sha'];manifest['files']['docs/THIRD_PARTY_NOTICES.md']=dict(bytes=len(files[notice]),sha256=sha(files[notice]));files[prefix+'release-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    files[prefix+'SHA256SUMS.txt']=''.join(sha(b)+'  '+n[len(prefix):]+'\n' for n,b in sorted(files.items()) if not n.endswith('/SHA256SUMS.txt')).encode()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for info in infos:z.writestr(info,files[info.filename])
    with zipfile.ZipFile(OUT/'source-link-fix-original-candidate.zip') as z:
        unchanged=[n for n in files if n not in (notice,prefix+'release-manifest.json',prefix+'SHA256SUMS.txt')];assert all(z.read(n)==files[n] for n in unchanged)
    report=read(OUT/'package-report.json');shutil.copyfile(OUT/'package-report.json',OUT/'package-report-r2.json');report.update(source_commit=commit['sha'],bytes=archive.stat().st_size,sha256=sha(archive.read_bytes()));save(OUT/'package-report.json',report)
    tests=read(OUT/'platform-tests.json');shutil.copyfile(OUT/'platform-tests.json',OUT/'platform-tests-pre-final-notice.json');tests.update(zip_sha256=report['sha256'],only_changes=['source commit and final attribution notice in release manifest','completed uChess model qualification notice','checksums']);save(OUT/'platform-tests.json',tests)
    save(OUT/'final-notice-reuse.json',dict(passed=True,all_firmware_tools_templates_examples_byte_identical=True,source_commit=commit['sha'],zip_sha256=report['sha256'],unchanged_files=len(unchanged),notice_bound_to_both_passed_model_slots=True))
    print('PASS final attribution/docs and source commit:',commit['sha'],'; all tested executable inputs unchanged')
if __name__=='__main__':main()
