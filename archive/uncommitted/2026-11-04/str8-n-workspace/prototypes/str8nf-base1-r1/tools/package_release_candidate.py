"""Package existing frozen files once; no assembly, models, ports or publication."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from verify_base1 import verify as verify_components
from verify_release_kit import verify as verify_kit

ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
EVIDENCE=(
    'validation/console-2512-hardware.json','validation/2512-upgrade-base1-acceptance.json',
    'validation/2512-b0-powercut-acceptance.json','validation/2512-cd-recovery-acceptance.json',
    'validation/2512-wdc-migration-acceptance.json','validation/2512-programmer-f-cd-acceptance.json',
    'validation/2609-rc1-zip-upgrade-acceptance.json')
RUNTIME=(
    'README.md','LICENSE','CHANGELOG.md','layout.json','release.json','checkpoint.json',
    'identity.json','F_FREEZE.json','profiles.json','requirements-console.txt','firmware/minimal-manifest.json',
    'examples/base1-b0-9000.asm','src/include/str8n-v2-public.inc','src/include/str8n-v2-eq.inc',
    'tools/nf_console.py','tools/console_core.py','tools/nf_recovery.py','tools/nf_opaque.py',
    'tools/oip.py','tools/map_catalog.py','tools/boot_identity.py','tools/verify_base1.py',
    'tools/verify_release_kit.py','migration-host/README.md','migration-host/nf_migrate.py',
    'migration-host/nf_migrate_live.py','migration-host/nf_provision_live.py','migration-host/nf_upgrade.py',
    'migrator/build.py','migrator/PROTOCOL.md','migrator/payload/template.bin',
    'migrator/payload/engine-manifest.json','migrator/payload/archive.bin',
    'migrator/payload/archive-manifest.json','migrator/upgrade/payload/template.bin',
    'migrator/upgrade/payload/engine-manifest.json')


def git(*args):
    return subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True).stdout


def manifest(root,kind,release,commit):
    files={path.relative_to(root).as_posix():dict(bytes=path.stat().st_size,sha256=sha(path))
           for path in sorted(root.rglob('*')) if path.is_file()}
    body=dict(schema=1,project='STR8N-F',profile='BASE1',artifact_type=kind,
        toolkit_version=release['version'],status=release['status'],
        source_commit=commit,release_line=release['release_line'],RAM='~32KB shared physical RAM',
        F_bytes=4096,F_sha256=sha(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin'),
        F_version='0.3.0',F_generation='00000001',host_console_version='0.1.0',
        hardware_qualified=False,qualified_scope=release['qualified_scope'],
        hardware_evidence=list(EVIDENCE),packaged_migration_test='NOT_RUN',
        prior_packaged_migration_test=release.get('prior_packaged_migration_test'),
        prior_tested_operator_ZIP_sha256=release.get('prior_tested_operator_ZIP_sha256'),
        firmware_builds_for_packaging=0,CPU_simulations=0,serial_access=False,
        board_2205_accessed=False,published=False,files=files)
    (root/'MANIFEST.json').write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
    verify_kit(root)
    return body


def zip_tree(root,out):
    target=out/(root.name+'.zip')
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            if not path.is_file():continue
            entry=zipfile.ZipInfo(root.name+'/'+path.relative_to(root).as_posix(),(1980,1,1,0,0,0))
            entry.create_system=3;entry.external_attr=0o100644<<16
            archive.writestr(entry,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return target


def package(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required; old archives are preserved')
    assert not git('status','--porcelain').strip(),'Commit the source checkpoint before packaging'
    commit=git('rev-parse','HEAD').decode().strip();release=read(ROOT/'release.json')
    fw=verify_components(ROOT)
    for name in EVIDENCE:
        receipt=read(ROOT/name);assert receipt['passed'],name
        for rel,digest in receipt.get('tested_files',{}).items():assert sha(ROOT/rel)==digest,rel
        for rel,digest in receipt.get('source_sha256',{}).items():assert sha(ROOT/rel)==digest,rel
    for stem,meta,key in (
        ('migrator/payload/template.bin','migrator/payload/engine-manifest.json','template_sha256'),
        ('migrator/payload/archive.bin','migrator/payload/archive-manifest.json','archive_sha256'),
        ('migrator/upgrade/payload/template.bin','migrator/upgrade/payload/engine-manifest.json','template_sha256')):
        assert sha(ROOT/stem)==read(ROOT/meta)[key],stem
    tracked=[name.decode() for name in git('ls-files','-z').split(b'\0') if name]
    forbidden={'build','dist','private','backups','logs','__pycache__','.git'}
    for name in tracked:
        path=ROOT/name
        assert not forbidden.intersection(Path(name).parts),name
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),name
    out.mkdir(parents=True)
    name='STR8N-F-BASE1-'+release['version']
    kit=out/name;source=out/(name+'-source')
    kit.mkdir();source.mkdir()
    runtime=set(RUNTIME)|{f'firmware/payload/{n}' for n in fw['artifacts']}
    runtime|={p.relative_to(ROOT).as_posix() for p in (ROOT/'docs').glob('*.md')}
    runtime|={p.relative_to(ROOT).as_posix() for p in (ROOT/'validation').glob('*.json')}
    for folder,names in ((kit,sorted(runtime)),(source,tracked)):
        for rel in names:
            path=ROOT/rel;assert path.is_file() and not path.is_symlink(),rel
            target=folder/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    manifest(kit,'operator',release,commit);manifest(source,'source',release,commit)
    assets=[zip_tree(kit,out),zip_tree(source,out)]
    direct=out/'STR8N-F-BOOT-4096.bin';shutil.copyfile(ROOT/'firmware/payload'/direct.name,direct)
    assets.append(direct)
    records={path.name:dict(bytes=path.stat().st_size,sha256=sha(path)) for path in assets}
    for path in assets:
        path.with_suffix(path.suffix+'.sha256').write_text(sha(path)+'  '+path.name+'\n',encoding='ascii')
    (out/'SHA256SUMS.txt').write_text(''.join(record['sha256']+'  '+name+'\n' for name,record in records.items()),encoding='ascii')
    receipt=dict(schema=1,source_commit=commit,toolkit_version=release['version'],assets=records,
        hardware_cases=release['qualified_scope'],packaged_migration_test='NOT_RUN',
        prior_packaged_migration_test=release.get('prior_packaged_migration_test'),
        prior_tested_operator_ZIP_sha256=release.get('prior_tested_operator_ZIP_sha256'),
        Python_serial_terminal_included=True,firmware_builds=0,CPU_simulations=0,serial_access=False,
        board_2205_accessed=False,published=False)
    (out/'PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('Saved operator/source ZIPs, Python terminal and exact frozen 4K F; this new ZIP has no live trial')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    package(parser.parse_args().out)
