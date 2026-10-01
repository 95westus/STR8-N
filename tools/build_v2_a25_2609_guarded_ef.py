"""Build exact-image alpha24-to-alpha25 E/F updaters for board 2609.

Uses its archived, verified alpha24 E/F image; performs no serial readback.
The RAM updaters themselves require exact live-sector matches before writes.
"""
import hashlib
import json
from pathlib import Path

import build_v2_a24 as old
import build_v2_a25 as new
from build_v2_a25_guarded_ef import make_updater

SOURCE = new.ROOT / 'output/qualification/board-2609-inventory-2026-09-30/a24-post-e-ef.bin'
OUT = new.ROOT / 'BUILD/board/a25-2609'
EXPECTED = '5864227879b4298ace8d9c5a6d637cda1347a6c6b4c6ebbdf0505555b58f535c'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    before = SOURCE.read_bytes()
    if len(before) != 8192 or sha(before) != EXPECTED:
        raise ValueError('Archived board-2609 alpha24 E/F identity changed')
    old_e, old_f = before[:4096], before[4096:]
    canonical_f = (old.OUT / f'{old.STEM}-f000-ffff.bin').read_bytes()
    if old_f != canonical_f or sha(old_e) != '49d1e50d3c933d6228bb92f80078b6ac53ec38a1d865f91e84e7cc5ed0da37bf':
        raise ValueError('Archived alpha24 sectors differ from qualified identities')
    candidate = (new.OUT / f'{new.STEM}-e000-ffff.bin').read_bytes()
    if len(candidate) != 8192:
        raise ValueError('Build alpha25 first')
    new_e = bytearray(candidate[:4096])
    new_e[0xF00:] = old_e[0xF00:]
    new_e = bytes(new_e)
    new_f = candidate[4096:]
    if new_e[:4] != b'RT\x01\x00' or new_e[0x800:0x805] != b'SR\x01\x01\x18':
        raise ValueError('Alpha25 E descriptor changed')
    if old_f[-32:] != new_f[-32:]:
        raise ValueError('F configuration/vector tail changed')
    worker = json.loads((old.OUT / 'build.json').read_text())['worker']
    newer_worker = json.loads((new.OUT / 'build.json').read_text())['worker']
    for symbol in ('V2W_SNAPSHOT', 'V2W_MUTATE'):
        if worker[symbol] != newer_worker[symbol]:
            raise ValueError(f'Flash worker address changed: {symbol}')
    OUT.mkdir(parents=True, exist_ok=True)
    e_path, e_symbols = make_updater(
        'str8n-v2-alpha25-board2609-e-install-2000',
        new.SOURCE / 'str8n-v2-e-repair-2000.asm', old_e, new_e, None,
        worker, OUT)
    f_path, f_symbols = make_updater(
        'str8n-v2-alpha25-board2609-f-install-2000',
        new.SOURCE / 'str8n-v2-f-update-2000.asm', old_f, new_f, new_e,
        worker, OUT)
    for label, image in (('old-e', old_e), ('old-f', old_f),
                         ('new-e', new_e), ('new-f', new_f)):
        (OUT / f'{label}.bin').write_bytes(image)
    manifest = {
        'board': 'W65C816SXB COM8 FT245 A10MPQXCA, board 2609',
        'source_ef_sha256': sha(before), 'source': str(SOURCE),
        'old_e_sha256': sha(old_e), 'old_f_sha256': sha(old_f),
        'new_e_sha256': sha(new_e), 'new_f_sha256': sha(new_f),
        'e_updater': str(e_path), 'e_updater_sha256': sha(e_path.read_bytes()),
        'e_updater_end': e_symbols['E_END'],
        'f_updater': str(f_path), 'f_updater_sha256': sha(f_path.read_bytes()),
        'f_updater_end': f_symbols['E_END'],
        'source_from_archived_board_proof': True,
        'host_flash_readback_requested': False,
        'board_installed_by_builder': False,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
