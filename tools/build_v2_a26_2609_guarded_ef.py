"""Build board-2609 alpha25-to-alpha26 guarded E/F RAM updaters.

Uses the archived alpha25 install targets and its on-board verification logs.
No host flash readback is requested. Each updater checks its live sector.
"""
import hashlib
import json
from pathlib import Path
import build_v2_a25 as old
import build_v2_a26 as new
from build_v2_a25_guarded_ef import make_updater

PRIOR = old.ROOT / 'BUILD/board/a25-2609'
OUT = new.ROOT / 'BUILD/board/a26-2609'
OLD_E_SHA = '2114c567136f4d8d79a2836a26e78d39e7308e35097c6eb6e87eeb77368fdf98'
OLD_F_SHA = '651fecf38f5ad1a82bd1254e64ea0361d92053ca0f6226a0d3daa2d7aa74b2a3'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_log(path, updater_hash, exact, verified):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    sent = b''.join(bytes.fromhex(row['hex']) for row in rows
                    if row['direction'] == 'TX' and row['text'].startswith(('S0', 'S1', 'S9')))
    received = b''.join(bytes.fromhex(row['hex']) for row in rows
                        if row['direction'] == 'RX')
    if (sha(sent) != updater_hash or exact not in received or
            verified not in received or
            not any(row['direction'] == 'TX' and row['hex'] == '59' for row in rows)):
        raise ValueError(f'Prior board install proof incomplete: {path}')
    return sha(path.read_bytes())


def main():
    previous = json.loads((PRIOR / 'manifest.json').read_text())
    old_e, old_f = ((PRIOR / name).read_bytes() for name in ('new-e.bin', 'new-f.bin'))
    if (len(old_e) != 4096 or len(old_f) != 4096 or
            sha(old_e) != OLD_E_SHA or sha(old_f) != OLD_F_SHA or
            sha(old_e) != previous['new_e_sha256'] or
            sha(old_f) != previous['new_f_sha256']):
        raise ValueError('Archived alpha25 board-2609 E/F identity changed')
    e_proof = verified_log(PRIOR / 'e-install.jsonl', previous['e_updater_sha256'],
                           b'B3:E exact; TYPE Y to repair>', b'B3:E VERIFIED; RESET')
    f_proof = verified_log(PRIOR / 'f-install.jsonl', previous['f_updater_sha256'],
                           b'B3:F exact; TYPE Y to update>', b'B3:F VERIFIED; RESET')
    candidate = (new.OUT / f'{new.STEM}-e000-ffff.bin').read_bytes()
    if len(candidate) != 8192:
        raise ValueError('Build alpha26 before preparing board updater')
    new_e, new_f = candidate[:4096], candidate[4096:]
    if (new_e[:4] != b'RT\x02\x00' or
            new_e[0x800:0x805] != b'SR\x01\x01\x18' or
            old_f[-32:] != new_f[-32:]):
        raise ValueError('E descriptor, S/R ABI, or F vectors changed unexpectedly')
    # The old $EF00-$EFFF tail is all zero; a26 intentionally frees it.
    if old_e[0xF00:] != bytes(256) or new_e[0xF00:] != b'\xff'*256:
        raise ValueError('Board E tail does not match the freed a26 pocket')
    worker = json.loads((old.OUT / 'build.json').read_text())['worker']
    next_worker = json.loads((new.OUT / 'build.json').read_text())['worker']
    for symbol in ('V2W_SNAPSHOT', 'V2W_MUTATE'):
        if worker[symbol] != next_worker[symbol]:
            raise ValueError(f'Flash worker address changed: {symbol}')
    OUT.mkdir(parents=True, exist_ok=True)
    e_path, e_symbols = make_updater(
        'str8n-v2-alpha26-board2609-e-install-2000',
        new.SOURCE / 'str8n-v2-e-repair-2000.asm', old_e, new_e, None,
        worker, OUT)
    f_path, f_symbols = make_updater(
        'str8n-v2-alpha26-board2609-f-install-2000',
        new.SOURCE / 'str8n-v2-f-update-2000.asm', old_f, new_f, new_e,
        worker, OUT)
    for name, data in (('old-e.bin', old_e), ('old-f.bin', old_f),
                       ('new-e.bin', new_e), ('new-f.bin', new_f)):
        (OUT / name).write_bytes(data)
    report = dict(board='W65C816SXB COM8 FT245 A10MPQXCA, board 2609',
                  source='archived alpha25 board-2609 verified E/F',
                  old_e_sha256=sha(old_e), old_f_sha256=sha(old_f),
                  new_e_sha256=sha(new_e), new_f_sha256=sha(new_f),
                  previous_e_install_log_sha256=e_proof,
                  previous_f_install_log_sha256=f_proof,
                  e_updater=str(e_path), e_updater_sha256=sha(e_path.read_bytes()),
                  e_updater_end=e_symbols['E_END'],
                  f_updater=str(f_path), f_updater_sha256=sha(f_path.read_bytes()),
                  f_updater_end=f_symbols['E_END'],
                  host_flash_readback_requested=False,
                  board_installed_by_builder=False)
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
