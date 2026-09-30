"""Build a guarded E-only weekday display update for installed alpha25 board 2205."""
import argparse
import hashlib
import json
from pathlib import Path

import build_v2_a25 as a25
from build_v2_a25_guarded_ef import make_updater

EXPECTED_EF = '0b8dce25c9adfe8a106a4fa1b2df0edcb0ce965738aa813675f79dc17cacfdbd'
EXPECTED_F = '651fecf38f5ad1a82bd1254e64ea0361d92053ca0f6226a0d3daa2d7aa74b2a3'
OUT_DEFAULT = a25.ROOT / 'BUILD/board/a25-dow'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first_readback', type=Path)
    parser.add_argument('second_readback', type=Path)
    parser.add_argument('--out', type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    first = args.first_readback.read_bytes()
    second = args.second_readback.read_bytes()
    if len(first) != 8192 or first != second or sha(first) != EXPECTED_EF:
        raise ValueError('E/F readbacks differ from the installed alpha25 image')
    old_e, old_f = first[:4096], first[4096:]
    built = (a25.OUT / f'{a25.STEM}-e000-ffff.bin').read_bytes()
    if len(built) != 8192:
        raise ValueError('Build alpha25 E/F before the weekday updater')
    new_e, new_f = built[:4096], built[4096:]
    if sha(old_f) != EXPECTED_F or old_f != new_f:
        raise ValueError('F changed; E-only update is not safe')
    if old_e[0x800:] != new_e[0x800:]:
        raise ValueError('S/R/T code or protected E tail changed')
    if old_e[:4] != new_e[:4] or new_e[:4] != b'RT\x01\x00':
        raise ValueError('RTC extension descriptor changed')
    if old_e == new_e:
        raise ValueError('No weekday change to install')
    worker = json.loads((a25.OUT / 'build.json').read_text())['worker']
    path, symbols = make_updater(
        'str8n-v2-alpha25-board2205-dow-e-2000',
        a25.SOURCE / 'str8n-v2-edu-status-e-update-2000.asm', old_e, new_e,
        old_f, worker, args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'old-e.bin').write_bytes(old_e)
    (args.out / 'new-e.bin').write_bytes(new_e)
    (args.out / 'expected-f.bin').write_bytes(old_f)
    manifest = {
        'board': 'W65C02SXB COM3 with EDU, board 2205',
        'source_ef_sha256': sha(first), 'old_e_sha256': sha(old_e),
        'old_f_sha256': sha(old_f), 'new_e_sha256': sha(new_e),
        'new_f_sha256': sha(new_f),
        'e_updater': str(path), 'e_updater_sha256': sha(path.read_bytes()),
        'e_updater_end': symbols['E_END'],
        'board_installed_by_builder': False,
    }
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
