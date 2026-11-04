"""Seal g0034 sources and bounded results, excluding private board escrows."""
import argparse,json,shutil,zipfile
from pathlib import Path
from str8build.formats import save,sha
ROOT=Path(__file__).resolve().parents[1]
BOARDS=('2512','2604','2609')

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    meta=json.loads((build/'r10-build.json').read_text());assert meta['current_features_retained'] and meta['boot_header']=='STR8-N 2.0rc1 g0034'
    assert sha((build/'firmware.bin').read_bytes())==meta['firmware_sha256'] and not out.exists()
    out.mkdir(parents=True)
    def copy(source,name):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    copy(build/'firmware.bin','firmware/str8n-2.0rc1-g0034.bin')
    for name in ('str8n-v2-recovery-f000-ffff.bin','str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin','version/asset.bin','xip/utilities.bin'):
        copy(build/'payload'/name,'components/'+name)
    tests=('console-tests.json','debugger-test.json','debugger-test-65c816-e.json','asm-dev-tests.json','console-edit-tests.json','generation-header-tests.json')
    for name in tests:
        result=json.loads((build/name).read_text());assert result['passed'];copy(build/name,'qualification/'+name)
    for board in BOARDS:
        folder=ROOT/f'output/qualification/rc1-r10p2-install-{board}/{board}';plan=ROOT/f'output/qualification/rc1-r10p2-plan-{board}'
        install=json.loads((folder/'flash-report.json').read_text());rec=json.loads((folder/'recovery/recovery-report.json').read_text())
        assert install['passed'] and rec['passed'] and install['firmware_sha256']==meta['firmware_sha256'] and rec['physical_reset_during_test'] is False
        for name in ('flash-report.json','boot-after-installer.txt','version-after.txt'):copy(folder/name,f'qualification/{board}/'+name)
        for name in ('recovery-report.json','J3-S-software-entry.txt'):copy(folder/'recovery'/name,f'qualification/{board}/'+name)
        copy(plan/'model-proof.json',f'qualification/{board}/installer-model-proof.json')
    copy(build/'r10-build.json','qualification/r10-build.json')
    match=ROOT/'output/qualification/rc1-g0034-three-board-match.json'
    evidence=json.loads(match.read_text());assert evidence['passed'] and evidence['firmware_sha256']==meta['firmware_sha256'] and evidence['all_three_same_firmware']
    copy(match,'qualification/three-board-match.json')
    text=(ROOT/'docs/rc1/R10_G0034.md').read_text()
    for board in BOARDS:
        text=text.replace(f'../../output/qualification/rc1-r10p2-install-{board}/{board}/recovery/','qualification/'+board+'/')
        text=text.replace(f'../../output/qualification/rc1-r10p2-install-{board}/{board}/','qualification/'+board+'/')
    text=text.replace('[the earlier result](R10_RECOVERY.md)','the separately recorded earlier generation-51 result on 2512')
    text=text.replace('../../output/qualification/rc1-g0034-three-board-match.json','qualification/three-board-match.json')
    (out/'README.md').write_text(text)
    for path in (ROOT/'src/current').rglob('*'):
        if path.is_file() and path.suffix in ('.asm','.inc','.json'):copy(path,'source/'+path.relative_to(ROOT/'src/current').as_posix())
    for name in ('build_rc1_r10.py','test_rc1_r10_recovery.py','test_rc1_generation_header.py'):
        copy(ROOT/'tools'/name,'tools/'+name)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(out.rglob('*')) if p.is_file()}
    assert not any('capture' in name.lower() or 'application-ram' in name or name.endswith('.jsonl') for name in files)
    save(out/'release-manifest.json',dict(version='2.0rc1',generation=52,generation_display='0034',generation_radix=16,distribution='RC1 r10',patch=2,
        firmware_build='rc1-r10p2-current',firmware_sha256=meta['firmware_sha256'],parent_sha256=meta['parent_sha256'],
        current_features_retained=True,hardware_qualified_boards=list(BOARDS),native_applications=False,native_debugging=False,
        published=False,local_staging_only=True,private_escrows_excluded=True,files=files))
    archive=out.parent/(out.name+'.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)|{'release-manifest.json'}
        for name,row in files.items():assert sha(z.read(name))==row['sha256']
    save(out.parent/(out.name+'-archive-check.json'),dict(passed=True,sha256=sha(archive.read_bytes()),members=len(files)+1))
    print('PASS sealed g0034 archive',archive,flush=True)

if __name__=='__main__':main()
