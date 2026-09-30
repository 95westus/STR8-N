"""Stage alpha24 B3:E for board 2609 from its exact live E/F readback.

Host-only preparation. Preserve E000-E7FF and EF00-EFFF byte-for-byte; replace
only E800-EEFF with the matched alpha24 S/R extension. No serial access.
"""
import argparse
import hashlib
import json
from pathlib import Path

import build_v2_a24 as a24


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live_ef', type=Path, help='exact 8192-byte B3 E/F readback')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()

    live = args.live_ef.read_bytes()
    if len(live) != 8192:
        raise ValueError('Expected exactly 8192 live B3 E/F bytes')
    old_e, old_f = live[:4096], live[4096:]
    if old_e != bytes(4096):
        raise ValueError('Board 2609 E preimage is not the observed all-zero sector')
    built_f = (a24.OUT / f'{a24.STEM}-f000-ffff.bin').read_bytes()
    if old_f != built_f or sha(old_f) != '43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a':
        raise ValueError('Live B3:F does not match the installed alpha24 image')
    built_e = (a24.OUT / f'{a24.STEM}-e000-efff.bin').read_bytes()
    if len(built_e) != 4096 or built_e[:0x800] != b'\xff' * 0x800 \
            or built_e[0xF00:] != b'\xff' * 0x100 \
            or built_e[0x800:0x805] != b'SR\x01\x01\x18':
        raise ValueError('Alpha24 E build is not the expected isolated S/R image')

    staged = old_e[:0x800] + built_e[0x800:0xF00] + old_e[0xF00:]
    if staged[:0x800] != old_e[:0x800] or staged[0xF00:] != old_e[0xF00:]:
        raise ValueError('E preservation check failed')
    lines = [a24.record('0', 0, b'STR8-N 2.0a24 B3 E board 2609')]
    lines.extend(a24.record('1', address, staged[address - 0xE000:address - 0xE000 + 32])
                 for address in range(0xE000, 0xF000, 32))
    lines.append(a24.record('9', 0xF004))
    s19_data = ('\n'.join(lines) + '\n').encode('ascii')
    args.out.mkdir(parents=True, exist_ok=True)
    bin_path = args.out / 'str8n-v2-alpha24-board2609-e-preserved.bin'
    s19_path = args.out / 'str8n-v2-alpha24-board2609-e-preserved.s19'
    manifest_path = args.out / 'manifest.json'
    for path in (bin_path, s19_path, manifest_path):
        if path.exists():
            raise FileExistsError(f'Refusing to replace staged evidence: {path}')
    bin_path.write_bytes(staged)
    s19_path.write_bytes(s19_data)
    parsed, entry = a24.read_s19(s19_path)
    if entry != 0xF004 or a24.dense_image(parsed, 0xE000, 0xF000) != staged:
        raise ValueError('Staged E S19 did not round-trip exactly')
    manifest = {
        'board': '2609 W65C816SXB',
        'source_ef_sha256': sha(live),
        'source_e_sha256': sha(old_e),
        'source_f_sha256': sha(old_f),
        'built_e_sha256': sha(built_e),
        'staged_e_sha256': sha(staged),
        'staged_s19_sha256': sha(s19_data),
        'preserved_ranges': ['E000-E7FF', 'EF00-EFFF'],
        'replaced_range': 'E800-EEFF',
        'board_installed': False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='ascii')
    print(json.dumps(manifest, indent=2))
    print(f'STAGED S19 = {s19_path}')


if __name__ == '__main__':
    main()
