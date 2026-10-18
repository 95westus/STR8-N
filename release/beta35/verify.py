#!/usr/bin/env python3
"""Offline verification of an extracted beta35 review kit; never accesses boards."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from build import crc, read_s19


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root/'manifest.json').read_text())
    meta = json.loads((root/'release.json').read_text())
    require(manifest['version']==meta['version']=='2.0b35', 'Wrong version')
    require(manifest['generation']==meta['generation']==47, 'Wrong generation')
    require(manifest['installation_permitted'] is False, 'Review kit must not permit installation')
    names = set(manifest['files'])
    require(len({n.casefold() for n in names})==len(names), 'Case-colliding names')
    for name,info in manifest['files'].items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name,
                'Unsafe package path: '+name)
        data = (root/name).read_bytes()
        require(len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],
                'Size/hash mismatch: '+name)
    observed = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
                and '__pycache__' not in p.relative_to(root).parts}
    require(observed==names|{'manifest.json'}, 'Missing or unexpected package files')
    provenance = json.loads((root/'source-provenance.json').read_text())
    require({n for n in names if n.startswith('source/')}==set(provenance), 'Source inventory mismatch')
    for name,info in provenance.items():
        require(manifest['files'][name]['sha256']==info['sha256'], 'Source provenance mismatch: '+name)
        if name.endswith(('.asm','.inc')):
            module = PurePosixPath(name).parts[1]
            for include in re.findall(r'\bINCLUDE\s+"([^"]+)"',(root/name).read_text(),re.I):
                require('source/'+module+'/'+include in names or include in meta['generated_includes'].get(module,[]),
                        'Missing source include: '+name+' -> '+include)
    require({n[8:] for n in names if n.startswith('payload/')}==set(meta['expected']), 'Payload allowlist mismatch')
    for name,info in meta['expected'].items():
        require(manifest['files']['payload/'+name]==info, 'Payload identity mismatch: '+name)

    def data(name):
        return (root/'payload'/name).read_bytes()

    clock = data('clock/clock.bin')
    storage = data('clock/storage.bin')
    require(b'CLOCK 1.10' in clock and b'CLOCK 1.9' not in clock, 'Stale CLOCK')
    require(storage[:8]==b'SR\x01\x3f\x00\x20'+len(clock).to_bytes(2,'little')
            and storage[8:24]==b'CLOCK'.ljust(16,b'\0') and storage[24:24+len(clock)]==clock
            and storage[24+len(clock):]==b'\xff'*(len(storage)-24-len(clock)), 'CLOCK record mismatch')
    require(read_s19(root/'payload/clock/clock.s19')==dict(enumerate(clock,0x2000)), 'CLOCK S19 mismatch')
    app = data('assembler/asm-e000.bin')
    vectors = data('assembler/vectors-f000.bin')
    require(app[:4]==b'AP\x01\x01' and int.from_bytes(app[4:6],'little')==len(app)
            and crc(app[:14])==int.from_bytes(app[14:16],'little'), 'ASM header mismatch')
    require(vectors[:len(app)-4096]==app[4096:], 'ASM payload overlap mismatch')
    require(vectors[-4:-2]==b'\x67\x7e','ASM HOLD vector mismatch')
    for name in ['str8n-rtc-component-8000-8fff.bin','xip/utilities.bin','boot-status/asset.bin',
                 'battery/asset.bin','local-display/asset.bin','pf-worker/asset.bin','version/asset.bin',
                 'str8n-v2-recovery-e000-efff.bin']:
        require(crc(data(name))==0, 'Invalid seal: '+name)
    journal = data('str8n-journal-9000-9fff.bin')
    require(crc(journal[:3072])==0 and journal[3072:]==b'\xff'*1024,'Journal template mismatch')
    require(data('version/asset.bin')[0x300:0x600]==data('pf-worker/asset.bin'),'PF asset mismatch')
    slot = data('str8n-v2-recovery-slot-b0.bin')
    require(slot[:4]==b'MI\x01\xb0' and int.from_bytes(slot[8:12],'little')==47
            and slot[31]==0 and crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little'),
            'Monitor slot seal/generation mismatch')
    layout = json.loads((root/'layout.json').read_text())
    require(layout['installation_permitted'] is False and layout['version']=='2.0b35', 'Invalid layout status')
    occupied = set()
    for segment in layout['segments']:
        bank,address,count,offset = (segment[k] for k in ('bank','address','bytes','offset'))
        require(bank in (1,2,3) and 0x8000<=address<address+count<=0x10000, 'Invalid mapped range')
        require(offset>=0 and offset+count<=len(data(segment['file'])), 'Invalid payload slice')
        cells = {(bank,a) for a in range(address,address+count)}
        require(not cells&occupied, 'Overlapping mapped ranges')
        occupied |= cells
    require(layout['deferred']==['ACIA','crypto'], 'Deferred scope changed')
    return {'passed':True,'files':len(names)+1,'sources':len(provenance),
            'payloads':len(meta['expected']),'mapped_ranges':len(layout['segments']),
            'version':'2.0b35','generation':47,'installation_permitted':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path)
    print(json.dumps(verify(parser.parse_args().kit),indent=2))
