"""Validate pinned component intermediates before using them; no board access."""
import hashlib,json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def verify_inputs(root=ROOT):
    root = Path(root).resolve()
    lock = json.loads((root/'components/inputs/LOCK.json').read_text())
    for row in lock['inputs']:
        path = (root/row['path']).resolve()
        if not path.is_relative_to(root) or path.is_symlink():
            raise ValueError('Unsafe input path: '+row['path'])
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Pinned component input differs: '+row['path'])
    overrides=lock.get('host_source_overrides', {})
    if set(overrides)-{'terminal/nf_console.py'}:
        raise ValueError('Only the terminal Python source may override an accepted input')
    for name,row in overrides.items():
        if row['path']!='components/inputs/accepted-base1/'+name:
            raise ValueError('Unexpected host override path')
        pin=next((r for r in lock['inputs'] if r['path']==row['path']),None)
        if pin is None or pin['sha256']!=row['sha256'] or pin['kind']!='SANITIZED_HOST_SOURCE':
            raise ValueError('Host override must match the sanitized source pin')
    return lock

if __name__ == '__main__':
    lock = verify_inputs()
    print('PASS '+str(len(lock['inputs']))+' frozen/source/metadata pins; '+str(len(lock.get('reconstructed_inputs', [])))+' inputs must be rebuilt and matched; all non-F binary inputs require source reconstruction')
