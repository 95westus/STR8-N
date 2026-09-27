"""Build and verify a scoped STR8-N 2.0a22 candidate ZIP."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import build_v2_a22 as a22

ROOT = a22.ROOT
OUT = ROOT / 'output/release/str8n-v2-a22-rc'
TOP_SHA = '1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439'
E_CODE_SHA = 'fcb0a253fa802c5e44ce48bba22c4b004a49b6dfe8b6563a9d8891ea75875401'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(script):
    subprocess.run([sys.executable, str(ROOT / 'tools' / script)], cwd=ROOT, check=True)


def main():
    run('build_v2_a22.py')
    run('build_v2_a22_bank_maint.py')
    run('test_v2_a22_bank_maint.py')
    run('build_v2_a22_wdcmon_ram.py')
    base = a22.OUT
    top = (base / f'{a22.STEM}-f000-ffff.bin').read_bytes()
    e = (base / f'{a22.STEM}-e000-efff.bin').read_bytes()
    if sha(top) != TOP_SHA or sha(e[0x800:0xF00]) != E_CODE_SHA:
        raise ValueError('candidate identity changed; review board evidence before packaging')
    if e[:0x800] != b'\xff' * 0x800 or e[0xF00:] != b'\xff' * 0x100:
        raise ValueError('dense E image changes reserved bytes')
    files = {
        'README.md': ROOT / 'docs/STR8N_V2_A22_RC_PACKAGE_README.md',
        'LICENSE': ROOT / 'LICENSE',
        'START-STR8N-V2-A22.ps1': ROOT / 'tools/wdcmonv2/START-STR8N-V2-A22.ps1',
        'TOOLS/start_wdcmonv2_ram.ps1': ROOT / 'tools/wdcmonv2/start_wdcmonv2_ram.ps1',
        'TOOLS/str8n-v2-bank-maint-2000.s19': base / 'str8n-v2-bank-maint-2000.s19',
        'DOC/STR8N_V2_A22_QUICKSTART.md': ROOT / 'docs/STR8N_V2_A22_QUICKSTART.md',
        'DOC/STR8N_V2_A22_OPERATORS_GUIDE.md': ROOT / 'docs/STR8N_V2_A22_OPERATORS_GUIDE.md',
        'DOC/STR8N_V2_A22_TECHNICAL_MANUAL.md': ROOT / 'docs/STR8N_V2_A22_TECHNICAL_MANUAL.md',
        'DOC/STR8N_V2_A22_SR_CANDIDATE.md': ROOT / 'docs/STR8N_V2_A22_SR_CANDIDATE.md',
        'DOC/STR8N_V2_A22_COM3_INSTALL_2026-09-26.md': ROOT / 'docs/STR8N_V2_A22_COM3_INSTALL_2026-09-26.md',
        'DOC/STR8N_V2_A22_REGRESSION_2026-09-26.md': ROOT / 'docs/STR8N_V2_A22_REGRESSION_2026-09-26.md',
        'DOC/STR8N_V2_RC1_GETTING_STARTED_816.md': ROOT / 'docs/STR8N_V2_RC1_GETTING_STARTED_816.md',
        'FIRMWARE/str8n-v2-alpha22-wdcmonv2-install-2000.s19':
            ROOT / 'BUILD/v2-alpha22-wdcmon-ram/str8n-v2-alpha22-wdcmonv2-install-2000.s19',
    }
    for suffix in ('f000-ffff.bin', 'e000-efff.bin', 'e000-efff.s19',
                   'e000-ffff.bin', 'e000-ffff.s19', 'b3-top-update-2000.s19'):
        name = f'{a22.STEM}-{suffix}'
        files[f'FIRMWARE/{name}'] = base / name
    package = {name: path.read_bytes() for name, path in files.items()}
    manifest = {
        'release': 'STR8-N 2.0a22 release candidate',
        'scope': 'W65C02SXB/EDU COM3 E/F pair; stock migration F only',
        'bank3_f_sha256': TOP_SHA,
        'e_extension_code_sha256': E_CODE_SHA,
        'stock_wdcmonv2_firmware_included': False,
        'owner_bank_archives_included': False,
        'files': {name: sha(data) for name, data in sorted(package.items())},
    }
    package['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    OUT.mkdir(parents=True, exist_ok=True)
    zip_path = OUT / 'str8n-v2-a22-rc.zip'
    with ZipFile(zip_path, 'w', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(package.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
    with ZipFile(zip_path) as archive:
        if set(archive.namelist()) != set(package):
            raise ValueError('ZIP inventory mismatch')
        for name, expected in manifest['files'].items():
            if sha(archive.read(name)) != expected:
                raise ValueError(f'ZIP hash mismatch: {name}')
    print(f'{zip_path}: SHA-256 {sha(zip_path.read_bytes())}; {len(package)} files')


if __name__ == '__main__':
    main()
