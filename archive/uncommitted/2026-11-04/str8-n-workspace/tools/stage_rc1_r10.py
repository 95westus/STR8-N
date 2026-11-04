"""Seal a local RC1 r10 archive with public sources and bounded evidence."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from str8build.formats import save,sha
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--install',type=Path,required=True)
    p.add_argument('--recovery',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    build=args.build.resolve();out=args.out.resolve();assert not out.exists()
    meta=json.loads((build/'r10-build.json').read_text());assert sha((build/'firmware.bin').read_bytes())==meta['firmware_sha256']
    install=json.loads((args.install/'flash-report.json').read_text());rec=json.loads((args.recovery/'recovery-report.json').read_text())
    assert install['passed'] and rec['passed'] and rec['physical_reset_during_test'] is False
    out.mkdir(parents=True);(out/'firmware').mkdir();(out/'qualification').mkdir();(out/'tools').mkdir()
    shutil.copyfile(build/'firmware.bin',out/'firmware/str8n-2.0rc1-r10-recovery1.bin')
    for name in ('str8n-v2-recovery-f000-ffff.bin','str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin','version/asset.bin','xip/utilities.bin'):
        path=out/'components'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(build/'payload'/name,path)
    for source,dest in ((build/'s',out/'source'),(build/'debugger',out/'source/debugger')):
        for path in source.rglob('*'):
            if path.is_file() and path.suffix in ('.asm','.inc','.json') and not path.name.endswith('.log.json'):
                target=dest/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for name in ('r10-build.json','console-tests.json','debugger-test.json','debugger-test-65c816-e.json'):
        shutil.copyfile(build/name,out/'qualification'/name)
    for folder,names in ((args.install,('flash-report.json','boot-after-installer.txt','version-after.txt')),
                         (args.recovery,('recovery-report.json','J3-S-software-entry.txt','J3-default-B-boot.txt'))):
        for name in names:shutil.copyfile(folder/name,out/'qualification'/name)
    shutil.copyfile(ROOT/'output/qualification/rc1-r10-2512-plan-20261023/model-proof.json',out/'qualification/installer-model-proof.json')
    text=(ROOT/'docs/rc1/R10_RECOVERY.md').read_text()
    for parent in ('../../output/qualification/rc1-r10-2512-install-20261023/install/',
                   '../../output/qualification/rc1-r10-2512-recovery-20261023/recovery/'):
        text=text.replace(parent,'qualification/')
    (out/'README.md').write_text(text)
    for name in ('build_rc1_r10.py','test_rc1_r10_recovery.py','test_rc1_debugger.py'):
        shutil.copyfile(ROOT/'tools'/name,out/'tools'/name)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(out.rglob('*')) if p.is_file()}
    assert not any('capture' in n.lower() or n.endswith('.jsonl') or 'application-ram' in n for n in files)
    save(out/'release-manifest.json',dict(distribution='RC1 r10',firmware_build=meta['identity'],generation=51,
        firmware_sha256=meta['firmware_sha256'],parent_sha256=meta['parent_sha256'],hardware_qualified_boards=['2512'],
        supported_CPUs=['65C02','65C816 E=1'],native_applications_tested=False,native_debugging=False,
        local_staging_only=True,published=False,private_escrows_excluded=True,files=files))
    archive=out.parent/(out.name+'.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,row in files.items():assert sha(z.read(name))==row['sha256']
        assert json.loads(z.read('release-manifest.json'))==json.loads((out/'release-manifest.json').read_text())
    save(out.parent/(out.name+'-archive-check.json'),dict(passed=True,members=len(files)+1,sha256=sha(archive.read_bytes()),archive=archive.name))
    print('PASS staged and verified',archive,flush=True)

if __name__=='__main__':main()
