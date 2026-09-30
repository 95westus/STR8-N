"""Build alpha24 bank maintenance S19 and its exact ASM-F2 .a carrier."""
import hashlib
import json
import shutil

import build_v2_a24 as a24
from build_v2_rc_a import make_carrier

STATIC_MACHINE_SHA256 = '9dda57fe5a9ab0744c3db40b6ea3507efbc8ad15d2ddb2e66d8a623ad2559736'


def main():
    report = json.loads((a24.OUT / 'build.json').read_text())
    stage = a24.OUT / 'bank-maint-asm'
    stage.mkdir(parents=True, exist_ok=True)
    (stage / 'bank-maint-worker.inc').write_text(''.join(
        f'{name:24} EQU     ${report["worker"][name]:04X}\n'
        for name in ('V2W_SELECT', 'V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')
    name = 'str8n-v2-bank-maint-2000'
    memory, symbols = a24.assemble(name, 0x2000, shutil.which('wdc02as'),
                                    shutil.which('wdcln'),
                                    source_file=a24.SOURCE / (name + '.asm'),
                                    include_dirs=(stage,))
    end = symbols['BM_END']
    if symbols['START'] != 0x2000 or end > 0x6900:
        raise ValueError('Bank maintenance image is outside application RAM')
    image = a24.dense_image(memory, 0x2000, end)
    machine_sha256 = hashlib.sha256(image).hexdigest()
    if machine_sha256 != STATIC_MACHINE_SHA256:
        raise ValueError('alpha24 bank maintenance changed the static alpha22 machine image')
    lines = [a24.record('0', 0, b'STR8-N v2 bank maint')]
    lines.extend(a24.record('1', address, image[address-0x2000:address-0x2000+32])
                 for address in range(0x2000, end, 32))
    lines.append(a24.record('9', 0x2000))
    s19 = a24.OUT / (name + '.s19')
    s19.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a24.read_s19(s19)
    if parsed != memory or entry != 0x2000:
        raise ValueError('Bank maintenance S19 round trip failed')
    apps = a24.ROOT / 'tools/v2-apps'
    apps.mkdir(exist_ok=True)
    canonical_s19 = apps / (name + '.s19')
    canonical_s19.write_bytes(s19.read_bytes())
    carrier = apps / (name + '.a')
    make_carrier(memory, carrier,
                 'Bank map, guarded copy and erase; requires the STR8-N v2 RAM worker.',
                 origin='alpha24')
    manifest = {
        'version': a24.VERSION, 'entry': '2000', 'bytes': len(image),
        'machine_sha256': machine_sha256,
        's19_sha256': hashlib.sha256(s19.read_bytes()).hexdigest(),
        'carrier_sha256': hashlib.sha256(carrier.read_bytes()).hexdigest(),
        'board_tested': False,
    }
    (a24.OUT / 'bank-maint-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{s19}: {len(image)} bytes; .a {carrier}')


if __name__ == '__main__':
    main()
