"""Check an extracted STR8N-F operator kit. No board access/build/simulation."""
import hashlib
import json
from pathlib import Path


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['project'] != 'STR8N-F' or manifest['kind'] != 'operator-kit':
        raise ValueError('Not a STR8N-F operator kit')
    declared = manifest['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
              and p.name != 'MANIFEST.json'}
    if actual != set(declared):
        raise ValueError('Missing or unexpected kit files')
    for name, info in declared.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or path.is_symlink():
            raise ValueError('Invalid kit path: '+name)
        data = path.read_bytes()
        if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
            raise ValueError('Kit checksum mismatch: '+name)
    for name, info in manifest['components'].items():
        data = (root/name).read_bytes()
        address = int(info['address'], 16)
        if info['kind'] == 'RAM tool':
            if address != 0x200 or address+len(data) > 0x6500:
                raise ValueError('RAM tool extent mismatch')
        elif len(data) != 4096 or address not in (0xa000, 0xb000, 0xf000):
            raise ValueError('ROM component extent mismatch')
    boot = (root/'firmware/STR8N-F-BOOT-4096.bin').read_bytes()
    if boot[:4] != b'SN\x02\0' or boot[0xffc:0xffe] != b'\x04\xf0':
        raise ValueError('F header or reset vector mismatch')
    print('PASS STR8N-F', manifest['version'], ':', len(declared),
          'kit files; checksums and destinations; no port/build/simulation')
    return manifest


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()
    verify(args.root)
