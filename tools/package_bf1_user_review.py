"""Build separate minimal Windows/Linux OFFLINE review kits from allowlists.

No upload, release revision, board capture or firmware change is performed.
"""
import argparse
import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
DOCS=['README.md','QUICK_START.md','QUICK_START_MIGRATION.md','QUICK_START_WINDOWS.md',
      'QUICK_START_LINUX.md','MIGRATION_RECOVERY.md','OPERATOR_GUIDE.md','USER_GUIDE.md',
      'ASM_GUIDE.md','COMMAND_REFERENCE.md','TECHNICAL_MANUAL.md','ABI_REFERENCE.md',
      'THIRD_PARTY_NOTICES.md','FIRMWARE_CONTENTS.md']


def require(value,message):
    if not value:raise ValueError(message)


def link_document(name,text):
    """Keep user docs self-contained; excluded implementation references become text."""
    def link(match):
        label,target=match.groups()
        if re.match(r'[a-z]+:',target):return match.group(0)
        base=target.split('#')[0]
        if base in DOCS or base in ('diagrams/boot-and-apps.svg','diagrams/migration-and-recovery.svg','diagrams/drift-collection.svg'):return match.group(0)
        if base.startswith('../../BUILD/microchess-asm04/'):
            return '['+label+'](../uchess-source/'+Path(base).name+')'
        # These are audited repository source/evidence references, not private
        # files to be added to a minimal normal-user archive.
        return label+' (repository reference: `'+base.removeprefix('../../').removeprefix('../')+'`)'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,text)


def category(name):
    if name.startswith('docs/'):return 'manual'
    if name.startswith('uchess-source/'):return 'uchess-source-or-license'
    if name.startswith('firmware/') and name.endswith('.bin'):return 'firmware'
    if name.startswith('migration/'):
        if name.endswith('.py'):return 'required-tool-source'
        if name.endswith('.bin'):return 'required-component'
        if name.endswith('.s19'):return 'required-ram-installer-template'
        if name.endswith('.json'):return 'required-tool-manifest'
    if name.endswith(('.cmd','.sh')):return 'platform-launcher'
    if name in ('README.md','LICENSE','provenance.json'):return 'license-or-package-guide'
    raise ValueError('Unallowlisted public file: '+name)


def launchers(platform):
    if platform=='windows':
        common='''@echo off
setlocal
if defined STR8N_PYTHON goto custom
where py >nul 2>nul
if errorlevel 1 goto fallback
py -3 "%~dp0migration\\user_cli.py" %*
exit /b %errorlevel%
:custom
"%STR8N_PYTHON%" "%~dp0migration\\user_cli.py" %*
exit /b %errorlevel%
:fallback
python "%~dp0migration\\user_cli.py" %*
exit /b %errorlevel%
'''
        rows={'bf1.cmd':common}
        for name,command in [('beta4-to-bf1','beta4'),('wdcmonv2-to-bf1','wdcmonv2'),('bf1-recovery','recover')]:
            rows[name+'.cmd']='@echo off\r\ncall "%~dp0bf1.cmd" '+command+' %*\r\nexit /b %errorlevel%\r\n'
        rows['bf1.cmd']=common.replace('\n','\r\n')
    else:
        common='''#!/bin/sh
set -eu
HERE=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec "${STR8N_PYTHON:-python3}" "$HERE/migration/user_cli.py" "$@"
'''
        rows={'bf1.sh':common}
        for name,command in [('beta4-to-bf1','beta4'),('wdcmonv2-to-bf1','wdcmonv2'),('bf1-recovery','recover')]:
            rows[name+'.sh']='#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -P "$(dirname "$0")" && pwd)\nexec "$HERE/bf1.sh" '+command+' "$@"\n'
    return {n:t.encode('ascii') for n,t in rows.items()}


def build_files(kit,image_dir,platform):
    manifest=json.loads((kit/'kit-manifest.json').read_text(encoding='utf-8'))
    live=manifest['live_installation_enabled'];require(manifest['distribution_qualified'] is False,'Full-release qualification must remain false')
    if live:
        qualification=json.loads((kit/'hardware-qualification.json').read_text())
        require(qualification['empty_bank_routes_hardware_passed'] and qualification['portable_transport_tests_passed'],'Missing admitted hardware/transport proofs')
    files={}
    for name,info in manifest['files'].items():
        p=(kit/name).resolve();require(p.is_relative_to(kit.resolve()),'Escaping kit file')
        data=p.read_bytes();require(len(data)==info['bytes'] and sha(data)==info['sha256'],'Changed kit input')
        files['migration/'+name]=data
    files['migration/kit-manifest.json']=(kit/'kit-manifest.json').read_bytes()
    report=json.loads((image_dir/'report.json').read_text(encoding='utf-8'))
    image=(image_dir/report['filename']).read_bytes()
    require(report['passed'] and len(image)==98304 and sha(image)==report['sha256'],'App-image pin mismatch')
    files['firmware/'+report['filename']]=image
    fixed=(kit/'payload/str8n-v2-recovery-f000-ffff.bin').read_bytes()
    require(len(fixed)==4096 and fixed==image[0x17000:0x18000],'Fixed F component differs from complete image')
    files['firmware/str8n-2.0bf1-b3-f000-ffff.bin']=fixed
    for name,digest in report['uchess_source_sha256'].items():
        data=(image_dir/'uchess-source'/name).read_bytes();require(sha(data)==digest,'uChess attribution/source changed')
        files['uchess-source/'+name]=data
    for name in DOCS:
        text=(ROOT/'docs/bf1'/name).read_text(encoding='utf-8')
        files['docs/'+name]=link_document(name,text).encode('utf-8')
    render=json.loads((ROOT/'output/qualification/bf1-mermaid-render-2026-10-18-r3/report.json').read_text())
    require(render['passed'],'Missing rendered diagram qualification')
    for item in render['diagrams']:
        name=item['name']+'.svg';data=(ROOT/'docs/bf1/diagrams'/name).read_bytes()
        require(sha(data)==item['svg_sha256'],'Changed rendered diagram')
        files['docs/diagrams/'+name]=data
    files['LICENSE']=(ROOT/'LICENSE').read_bytes()
    quick='QUICK_START_WINDOWS.md' if platform=='windows' else 'QUICK_START_LINUX.md'
    files['README.md']=('''# STR8-N 2.0bf1 — OFFLINE REVIEW PACKAGE

This local review build is not a public release or a qualified installer.
Board capture/install are disabled. No WDCMONV2 or intermediate beta4 firmware
is included. Do not send model-only S19 files to a board manually.

Start with [the host quick start](docs/'''+quick+''').
See [all manuals](docs/README.md), [migration/recovery](docs/MIGRATION_RECOVERY.md)
and [firmware layout](docs/FIRMWARE_CONTENTS.md).

The same STR8-N-only firmware serves 65C02 and 65C816 emulation runtime.
The complete image includes UCHESS and S/R/T; preserving upgrade UCHESS
placement/conflict handling is still pending. The image is fresh provisioning,
not a preserving upgrade. Keep private backups outside this extracted kit.

Native 816 applications/tests, ACIA and crypto remain deferred. Publication is
held pending complete docs and both tested portable migration/recovery routes.
''').encode('utf-8')
    files.update(launchers(platform))
    if live:
        files['README.md']=('''# STR8-N 2.0bf1 — full-system migration candidate

Start with [the host quick start](docs/'''+quick+'''). The route launchers are
enabled for the exact admitted source/empty-bank scope. WDC uses the tested
original SXB6 65C816 source; beta4 uses the published generation-13 profile.
B0/B1/B2 must already be erased. The RAM tool checks all source-bank bytes
before any flash mutation and installs MON A/B, all providers/apps and UCHESS.
It does not stage or distribute WDCMONV2 or beta4 firmware.

Use Python 3.10+ and pyserial 3.5. Verify SHA256SUMS and run the kit verifier.
Keep the exact kit and all generated recovery/capture files privately.
The included 96 KiB STR8-N-only programmer image contains all supported apps
and S/R/T. File offset zero maps to full-device offset 32768 (B1); it excludes
B0. It is fresh provisioning with defaults, not a preserving upgrade or dump.

Read [all manuals](docs/README.md), [recovery](docs/MIGRATION_RECOVERY.md),
[firmware mapping](docs/FIRMWARE_CONTENTS.md) and [licenses](docs/THIRD_PARTY_NOTICES.md).
One firmware set serves 65C02 and 65C816 emulation runtime; native 816 apps,
ACIA and crypto remain deferred. No clock/trim setters are issued.

Local candidate only: publication/full release acceptance remain held. Earlier
RTC continuity failure and broader preservation remain open. Linux physical
serial migration has not been performed. Early factory-WDC cuts may need an
external programmer. General occupied-bank upgrades are not admitted.
''').encode('utf-8')
    files['provenance.json']=json.dumps(dict(version='2.0bf1',generation=48,candidate_id='batchfix-r1',
        image_sha256=report['sha256'],image_bytes=98304,bank_order=[1,2,3],full_device_base_offset=32768,
        MON_A='B3:A000',MON_B='B3:B000',same_firmware_for_65C02_and_65C816_emulation=True,
        runtime_scope='E=1; accepted existing startup CPU-detector exception',
        migration_kit_manifest_sha256=sha(files['migration/kit-manifest.json']),
        uchess_copyright='Kim-1 MicroChess (c) 1976-2005 Peter Jennings',
        uchess_credits=['Daryl Rictor','Bill Forster'],
        deferred=['native 816 applications/tests','ACIA','crypto'],
        source_or_capture_images_included=False,review_only=not live,distribution_qualified=False),indent=2).encode('utf-8')+b'\n'
    entries={}
    for name,data in files.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Escaping archive name')
        require(not any(x in name.lower() for x in ('beta4-bridge','serial.jsonl','eeprom.bin','sram.bin')),'Private/vendor package name')
        if name.endswith(('.md','.py','.json')):
            text=data.decode('utf-8')
            require(not re.search(r'C:[\\/](?:SRC|Users)[\\/]|output[\\/]qualification',text,re.I),'Private host path in '+name)
        entries[name]=dict(bytes=len(data),sha256=sha(data),category=category(name))
    package=dict(version='2.0bf1',platform=platform,review_only=not live,distribution_qualified=False,
                 live_installation_enabled=live,files=entries)
    files['package-manifest.json']=json.dumps(package,indent=2).encode('utf-8')+b'\n'
    files['SHA256SUMS']=''.join(sha(data)+'  '+name+'\n' for name,data in sorted(files.items())).encode('ascii')
    return files


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kit',type=Path,required=True);p.add_argument('--image-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();require(out.is_relative_to(ROOT) and not out.exists(),'Fresh workspace output directory required');out.mkdir(parents=True)
    receipts={}
    for platform in ('windows','linux'):
        files=build_files(a.kit.resolve(),a.image_dir.resolve(),platform)
        live=json.loads(files['package-manifest.json'])['live_installation_enabled']
        stem='str8n-2.0bf1-'+platform+'-migration'+('' if live else '-REVIEW')
        path=out/(stem+('.zip' if platform=='windows' else '.tar.gz'))
        if platform=='windows':
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,data in sorted(files.items()):
                    info=zipfile.ZipInfo(stem+'/'+name,date_time=(2026,10,18,0,0,0));info.create_system=3;info.external_attr=(0o100644<<16);info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
        else:
            import gzip
            with path.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as archive:
                for name,data in sorted(files.items()):
                    info=tarfile.TarInfo(stem+'/'+name);info.size=len(data);info.mode=0o755 if name.endswith('.sh') else 0o644;info.mtime=1792281600;archive.addfile(info,io.BytesIO(data))
        receipts[platform]=dict(filename=path.name,bytes=path.stat().st_size,sha256=sha(path.read_bytes()),files=len(files),review_only=not live,live_installation_enabled=live,distribution_qualified=False)
        if platform=='linux':
            zip_path=out/(stem+'.zip')
            with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,data in sorted(files.items()):
                    info=zipfile.ZipInfo(stem+'/'+name,date_time=(2026,10,18,0,0,0));info.create_system=3;info.external_attr=((0o100755 if name.endswith('.sh') else 0o100644)<<16);info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
            receipts[platform]['zip']=dict(filename=zip_path.name,bytes=zip_path.stat().st_size,sha256=sha(zip_path.read_bytes()))
    (out/'packages.json').write_text(json.dumps(dict(passed=True,packaging_only=True,packages=receipts,board_access=False,publication_permitted=False),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipts,indent=2))


if __name__=='__main__':main()
