"""Package the existing N/F payloads into operator and source ZIPs. No rebuild."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
import package
import verify_system
from verify import public_files
from verify_package import verify as verify_kit

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()


def make(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh output directory')
    system = verify_system.check()
    core = json.loads((ROOT/'firmware/manifest.json').read_text())
    release = json.loads((ROOT/'release.json').read_text())
    all_components = dict(core['artifacts'], **system['artifacts'])
    out.mkdir(parents=True)
    name = release['project']+'-'+release['tag']
    kit = out/name
    kit.mkdir()
    components = {}
    selected = ('STR8N-F-BOOT-4096.bin', 'STR8N-F-CONFIG-RAM.bin',
                'STR8N-F-OPAQUE-RAM.bin', 'STR8N-F-DEMO-RAM.bin',
                'STR8N-F-READBACK-RAM.bin', 'STR8N-F-MON-BASE-A.bin',
                'STR8N-F-MON-BASE-B.bin')
    for filename in selected:
        optional = filename.startswith('STR8N-F-MON-')
        relative = ('optional/monitors/' if optional else 'firmware/')+filename
        target = kit/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'firmware/payload'/filename, target)
        info = all_components[filename]
        assert sha(target.read_bytes()) == info['sha256']
        components[relative] = dict(info, kind='RAM tool' if info['address'] == '0200' else 'ROM sector', optional=optional)
    (kit/'docs').mkdir()
    for path in (ROOT/'docs').glob('*.md'):
        if path.name in ('QUICK_START.md', 'OPERATOR_GUIDE.md', 'INSTALLATION.md',
                         'OPAQUE_PROTOCOL.md', 'IMAGE_CONTRACT.md', 'READBACK.md',
                         'RELEASE_NOTES.md', 'RELEASE_STATUS.md'):
            text = path.read_text(encoding='utf-8')
            # Source-only references remain exact tagged source links in the
            # compact runtime kit, rather than broken local paths.
            text = text.replace('(UNIFIED_SYSTEM.md)', f'(https://github.com/95westus/STR8N-F/blob/{release["tag"]}/docs/UNIFIED_SYSTEM.md)')
            text = text.replace('(../validation/hardware-summary.json)', f'(https://github.com/95westus/STR8N-F/blob/{release["tag"]}/validation/hardware-summary.json)')
            for source in ('str8n-v2-public.inc', 'str8n-v2-eq.inc'):
                text = text.replace('(../src/include/'+source+')', f'(https://github.com/95westus/STR8N-F/blob/{release["tag"]}/src/include/{source})')
            (kit/'docs'/path.name).write_text(text, encoding='utf-8', newline='\n')
    (kit/'tools').mkdir()
    shutil.copy2(ROOT/'tools/oip.py', kit/'tools/oip.py')
    shutil.copy2(ROOT/'tools/verify_package.py', kit/'verify_package.py')
    shutil.copy2(ROOT/'LICENSE', kit/'LICENSE')
    (kit/'START_HERE.md').write_text(f'''# STR8N-F {release['version']} operator kit

F-sector boot and recovery for WDC 65C02/65C816 emulation, USB/FT245.

1. Run `python verify_package.py` to check files and component destinations.
2. Read [installation boundaries](docs/INSTALLATION.md) before any programming.
3. Follow the [quick start](docs/QUICK_START.md) on a compatible provisioned board.

`firmware/STR8N-F-BOOT-4096.bin` is a 4096-byte B3:F000 ROM sector.
The other four BINs in `firmware/` load at RAM $0200 through REC / L.
The optional MONs are separate B3:A/B ROM sectors, not RAM loader input.
No whole-device image or owner WDC backup is supplied.

Raw L runs after about three seconds of transfer silence without declared
length/CRC. CONFIG settings save immediately. Journal I is blank-only.
OIP1 requires paced header/payload sends and a verified target preimage.
The kit is not an automatic factory migrator or live host installer.

The package version is {release['version']}; F stays b15 / PR04 / 8000000F.
This is an early toolkit release; full 1.0 factory acceptance is not claimed.
EDU/SPI/RTC and the future WORK message journal are optional/outside this kit.

Read [commands](docs/OPERATOR_GUIDE.md), [opaque image contract](docs/IMAGE_CONTRACT.md),
[binary export](docs/READBACK.md), and [scope/evidence](docs/RELEASE_STATUS.md).
The [matching source release](https://github.com/95westus/STR8N-F/releases/tag/{release['tag']})
contains the unified source and optional development modules.
''', encoding='utf-8', newline='\n')
    files = {p.relative_to(kit).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
             for p in sorted(kit.rglob('*')) if p.is_file()}
    manifest = dict(project='STR8N-F', version=release['version'], kind='operator-kit',
                    firmware_lineage=release['firmware_lineage'], files=files, components=components)
    (kit/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    verify_kit(kit)
    runtime_zip = out/(name+'.zip')
    with zipfile.ZipFile(runtime_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(kit.rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo(name+'/'+path.relative_to(kit).as_posix(), (1980,1,1,0,0,0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    public = public_files()
    source_zip = package.package(out/'source', public)
    shutil.copy2(source_zip, out/source_zip.name)
    assets = [runtime_zip, out/source_zip.name]
    for asset in assets:
        (out/(asset.name+'.sha256')).write_text(sha(asset.read_bytes())+'  '+asset.name+'\n', encoding='ascii')
    report = dict(passed=True, version=release['version'], firmware_rebuilt=False,
        assembly_builds=0, CPU_simulations=0, board_access=False,
        core_F_sha256=all_components['STR8N-F-BOOT-4096.bin']['sha256'],
        assets={p.name:dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in assets},
        operator_components=components, source_files=len(public))
    (out/'RELEASE-MANIFEST.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('PASS operator/source release artifacts; existing payloads; no board/build/simulation')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    make(a.out)
