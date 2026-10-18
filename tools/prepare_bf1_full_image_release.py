"""Prepare an additive full-image draft revision, preserving all prior assets."""
import json,hashlib,shutil,zipfile,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';OUT=ROOT/'output/releases/bf1-github-prerelease-2026-10-17'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    tests=Q/'bf1-full-image-tests-2026-10-17-r2/report.json';r=read(tests);assert r['passed'] and r['cases']==11
    image_dir=Q/'bf1-full-image-2026-10-17-r1';layout=read(image_dir/'firmware-layout.json')
    assert sha(image_dir/layout['filename'])==r['image_sha256']==layout['sha256']
    assert sha(ROOT/'release/bf1-prerelease/build_full_image.py')==r['composer_sha256']==layout['composer_sha256']
    old=read(OUT/'preparation.json');archive=OUT/'revisions/components-only';archive.mkdir(parents=True,exist_ok=False)
    for name in ('preparation.json','draft.json','release-notes.md'):shutil.copyfile(OUT/name,archive/name)
    shutil.copyfile(Q/'bf1-tonight-publication-plan.json',archive/'publication-plan.json')
    package=OUT/'package-full-image-r1';shutil.copytree(Path(old['package']),package)
    for name in ('public-manifest.json','SHA256SUMS'):(package/name).unlink()
    for p in (ROOT/'docs/bf1').glob('*.md'):shutil.copyfile(p,package/'docs/bf1'/p.name)
    shutil.copyfile(ROOT/'docs/STR8N_BF1_FULL_FIRMWARE_IMAGE.md',package/'docs/STR8N_BF1_FULL_FIRMWARE_IMAGE.md')
    (package/'release/bf1-prerelease').mkdir(parents=True);shutil.copyfile(ROOT/'release/bf1-prerelease/build_full_image.py',package/'release/bf1-prerelease/build_full_image.py')
    firmware=package/'firmware';firmware.mkdir()
    for name in ('str8n-2.0bf1-firmware.bin','firmware-layout.json','str8n-2.0bf1-firmware.sha256'):shutil.copyfile(image_dir/name,firmware/name)
    base_ref=read(ROOT/'tmp/bfx5/build-report.json')
    (firmware/'full-image-reference.json').write_text(json.dumps(dict(version='2.0bf1',generation=48,artifacts=base_ref['artifacts']),indent=2)+'\n')
    summary={k:r[k] for k in ('passed','cases','checks','image_sha256','manifest_sha256','composer_sha256','test_sha256','model_processor','shared_CPU_hardware_receipt_sha256','CPU_compatibility','new_full_image_hardware_installation','native_816_execution_tested','board_access','finished_utc')}
    (firmware/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')
    p=package/'README.md';s=p.read_text(encoding='utf-8');s=s.replace('# STR8-N 2.0bf1 pilot prerelease','# STR8-N 2.0bf1 complete firmware — pilot prerelease')
    s=s.replace('All 19 exact pinned binary/application artifacts are under', '''The complete **128 KiB** image is `firmware/str8n-2.0bf1-firmware.bin`.
Use the **same file** for 65C02 and 65C816 emulation-mode runtime. It contains
MON A, MON B and all matching providers, with fresh generic configuration and
a fresh wear baseline; it is not a preserving upgrade image. See the
[full-image guide and MON A/MON B naming](docs/STR8N_BF1_FULL_FIRMWARE_IMAGE.md).

All 19 exact pinned binary/application artifacts are under''')
    s+='''

Reproduce the whole image from these verified components:

```text
python release/bf1-prerelease/build_full_image.py --payload release/candidates/batchfix-r1/payload --reference firmware/full-image-reference.json --out C:\\tmp\\bf1image
```

Bank order is B0/B1/B2/B3, 32768 bytes each. MON A is B3:$A000 (file offset
$1A000); MON B is B3:$B000 (file offset $1B000). A0/B0 in internal component
names denotes those hexadecimal pages, not new monitor names or CPU types.
The new whole-image layout has offline boot/fallback/BATCH qualification;
its identical component firmware has prior shared-CPU hardware evidence.
It has not been physically reprogrammed onto the active soak boards.
''';p.write_text(s,encoding='utf-8')
    previous_manifest=read(Path(old['package'])/'public-manifest.json')
    manifest={k:v for k,v in previous_manifest.items() if k!='files'}
    manifest.update(derived_complete_image=dict(filename='firmware/str8n-2.0bf1-firmware.bin',bytes=layout['bytes'],sha256=layout['sha256'],shared_CPU_image=True,fresh_provisioning_only=True),full_image_offline_cases=r['cases'])
    manifest['files']={p.relative_to(package).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(package.rglob('*')) if p.is_file()}
    (package/'public-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (package/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(package).as_posix()}\n' for p in sorted(package.rglob('*')) if p.is_file()))
    for p in package.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if re.match(r'[a-z]+:',link):continue
            target=(p.parent/link.split('#')[0]).resolve();assert target.is_relative_to(package.resolve()) and target.is_file(),(p,link)
    bundle=OUT/'str8n-2.0bf1-firmware-package.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(package.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(package).as_posix())
    for src,name in ((image_dir/layout['filename'],layout['filename']),(image_dir/'firmware-layout.json','str8n-2.0bf1-firmware-layout.json')):shutil.copyfile(src,OUT/name)
    added=[bundle,OUT/layout['filename'],OUT/'str8n-2.0bf1-firmware-layout.json']
    sums=OUT/'str8n-2.0bf1-firmware-assets.sha256';sums.write_text(''.join(f'{sha(p)}  {p.name}\n' for p in added));added.append(sums)
    assets=old['assets']|{p.name:dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in added}
    result=dict(prepared=True,revision='additive full-image r1',owner_authorized_complete_image=True,created_utc=datetime.now(timezone.utc).isoformat(),directory=str(OUT.resolve()),package=str(package.resolve()),source_count=97,artifact_count=19,derived_complete_images=1,assets=assets,full_image_test_report_sha256=sha(tests),previous_preparation_sha256=sha(archive/'preparation.json'),full_release_qualified=False,board_access=False)
    (OUT/'preparation-full-image-r1.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
