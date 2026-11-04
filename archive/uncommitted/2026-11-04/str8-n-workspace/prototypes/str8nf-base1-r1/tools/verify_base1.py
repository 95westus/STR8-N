"""Verify frozen BASE1 bytes, metadata and tool bindings; no CPU/device work."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from boot_identity import decode

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def verify(root=ROOT):
    root=Path(root).resolve()
    manifest=json.loads((root/'firmware/minimal-manifest.json').read_text())
    lock=json.loads((root/'F_FREEZE.json').read_text())
    identity=json.loads((root/'identity.json').read_text())
    assert manifest['profile']=='BASE1' and manifest['compatibility']=='PR05'
    assert not manifest['execution_qualified'] and not manifest['hardware_access']
    f=root/'firmware/payload/STR8N-F-BOOT-4096.bin'
    assert f.stat().st_size==4096 and sha(f)==lock['sha256']==manifest['F_sha256']
    parsed=decode(f.read_bytes())
    assert lock['identity']==identity
    for name in ('product','F_version','F_generation','profile','private_contract','public_ABI_major'):
        assert parsed[name]==identity[name],name
    assert manifest['F_generation']=='00000001' and manifest['SNBT_monitor_generation']=='8000000F'
    for name,record in manifest['artifacts'].items():
        path=root/'firmware/payload'/name
        assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
    # Operator kits carry public ABI includes; only a full source checkout
    # also contains src/core and must supply every production source pin.
    if (root/'src/core').exists():
        for name,digest in lock['sources'].items():assert sha(root/name)==digest,name
        # The production build pins its source snapshot. Later, separate lab
        # sources do not belong to those six binaries and require no rebuild.
        for name,digest in manifest['source'].items():
            path=root/name
            assert path.resolve().is_relative_to(root) and not path.is_symlink(),name
            assert sha(path)==digest,'Built component source changed: '+name
    # Match the actual wire markers rather than allowing a renamed host/tool mix.
    opaque=(root/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    readback=(root/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert b'OPAQUE BASE1 / PR05 I Q> \0' in opaque
    assert b'RAM SERVICE BASE1> \0' in readback
    planning=(root/'migration-host/nf_migrate.py').read_text()
    live=(root/'migration-host/nf_migrate_live.py').read_text()
    assert f"F_SHA256 = '{sha(f)}'" in planning
    assert f"READBACK_SHA256 = '{hashlib.sha256(readback).hexdigest()}'" in live
    assert f'len(readback) == {len(readback)}' in live
    assert 'SNBT_MONITOR_GENERATION = 0x8000000f' in planning
    assert len(manifest['artifacts'])==6 and 'STR8N-F-MAP-RAM.bin' in manifest['artifacts']
    print('PASS BASE1 static files: frozen 4K F identity, six components, source and host bindings; hardware scope is separate')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();verify(args.root)
