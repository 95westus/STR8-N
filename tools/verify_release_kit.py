"""Verify a fresh extracted kit, without opening a port or building firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import re

REQUIRED=(
    'README.md','requirements-console.txt','firmware/minimal-manifest.json',
    'firmware/payload/STR8N-F-BOOT-4096.bin','tools/nf_console.py','tools/console_core.py',
    'tools/nf_recovery.py','tools/verify_base1.py','tools/boot_identity.py',
    'migration-host/nf_migrate.py','migration-host/nf_migrate_live.py',
    'migration-host/nf_provision_live.py','migration-host/nf_upgrade.py',
    'migrator/build.py','migrator/payload/template.bin','migrator/payload/archive.bin',
    'migrator/payload/engine-manifest.json','migrator/payload/archive-manifest.json',
    'migrator/upgrade/payload/template.bin','migrator/upgrade/payload/engine-manifest.json',
    'docs/SERIAL_CONSOLE.md','docs/INSTALLATION.md','docs/LIVE_CD_PROVISIONING.md',
    'docs/JOURNAL_F_UPGRADE.md','docs/RELEASE_WORKFLOW.md','migration-host/README.md')
sha=lambda body:hashlib.sha256(body).hexdigest()


def verify(root):
    root=Path(root).resolve();manifest=json.loads((root/'MANIFEST.json').read_text())
    assert manifest['F_bytes']==4096 and manifest['profile']=='BASE1'
    assert manifest['packaged_migration_test']=='NOT_RUN'
    assert manifest['host_console_version']=='0.1.0'
    declared=manifest['files']
    assert all(name in declared for name in REQUIRED),'Missing runtime dependency'
    actual={p.relative_to(root).as_posix() for p in root.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert actual==set(declared)|{'MANIFEST.json'},'Unexpected/missing kit files'
    for name,record in declared.items():
        path=root/name
        assert path.resolve().is_relative_to(root) and not path.is_symlink(),name
        body=path.read_bytes()
        assert len(body)==record['bytes'] and sha(body)==record['sha256'],name
    f=(root/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f)==4096 and sha(f)==manifest['F_sha256']
    fw=json.loads((root/'firmware/minimal-manifest.json').read_text())
    for name,record in fw['artifacts'].items():
        body=(root/'firmware/payload'/name).read_bytes()
        assert len(body)==record['bytes'] and sha(body)==record['sha256'],name
    assert (root/'requirements-console.txt').read_text().strip()=='pyserial==3.5'
    # Local guide links must work in the extracted tree without checkout paths.
    for name in declared:
        if not name.endswith('.md'):continue
        path=root/name
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            target=target.split('#',1)[0]
            resolved=(path.parent/target).resolve()
            assert resolved.is_relative_to(root) and resolved.exists(),f'{name}: {target}'
    # Receipt bindings refer to tested production files, not private lab outputs.
    for receipt_name in manifest['hardware_evidence']:
        receipt=json.loads((root/receipt_name).read_text())
        assert receipt['passed'],receipt_name
        for name,digest in receipt.get('tested_files',{}).items():
            if name in declared:assert sha((root/name).read_bytes())==digest,name
        for name,digest in receipt.get('source_sha256',{}).items():
            if name in declared:assert sha((root/name).read_bytes())==digest,name
    print(f'PASS {len(declared)} {manifest["artifact_type"]} files; terminal/migration dependencies, hashes and links; ZIP live migration NOT RUN')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1])
    verify(parser.parse_args().root)
