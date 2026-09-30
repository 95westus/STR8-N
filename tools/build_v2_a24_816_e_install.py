"""Build an exact-image B3:E RAM updater for board 2609; no board access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_a24 as a24


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_ef', type=Path)
    parser.add_argument('staged_e', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()

    source = args.source_ef.read_bytes()
    new = args.staged_e.read_bytes()
    if len(source) != 8192 or len(new) != 4096:
        raise ValueError('Source E/F must be 8192 bytes; staged E must be 4096 bytes')
    old, source_f = source[:4096], source[4096:]
    if old != bytes(4096):
        raise ValueError('Board 2609 E preimage is not the observed all-zero sector')
    built_f = (a24.OUT / f'{a24.STEM}-f000-ffff.bin').read_bytes()
    if source_f != built_f or sha(source_f) != '43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a':
        raise ValueError('Live F does not match alpha24 before E install')
    built_e = (a24.OUT / f'{a24.STEM}-e000-efff.bin').read_bytes()
    if new[:0x800] != old[:0x800] or new[0x800:0xF00] != built_e[0x800:0xF00] \
            or new[0xF00:] != old[0xF00:]:
        raise ValueError('Staged E does not preserve the board margins or match alpha24 S/R')

    stage = args.out / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    a24.include_bytes(stage / 'e-old-image.inc', old)
    a24.include_bytes(stage / 'e-new-image.inc', new)
    worker = json.loads((a24.OUT / 'build.json').read_text())['worker']
    (stage / 'e-worker-addresses.inc').write_text(''.join(
        f'{name:24} EQU     ${worker[name]:04X}\n'
        for name in ('V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')

    name = 'str8n-v2-alpha24-board2609-e-install-2000'
    old_out = a24.OUT
    try:
        a24.OUT = args.out
        memory, symbols = a24.assemble(name, 0x2000, shutil.which('wdc02as'),
                                       shutil.which('wdcln'),
                                       source_file=a24.SOURCE / 'str8n-v2-e-repair-2000.asm',
                                       include_dirs=(stage,))
    finally:
        a24.OUT = old_out
    if symbols['START'] != 0x2000 or symbols['E_END'] >= 0x6900:
        raise ValueError('RAM updater layout changed')
    if bytes(memory[a] for a in range(symbols['E_OLD'], symbols['E_OLD'] + 4096)) != old:
        raise ValueError('Embedded old E differs from board preimage')
    if bytes(memory[a] for a in range(symbols['E_NEW'], symbols['E_NEW'] + 4096)) != new:
        raise ValueError('Embedded new E differs from staged image')
    lines = [a24.record('0', 0, b'STR8-N 2.0a24 board 2609 E install')]
    lines.extend(a24.record('1', address, bytes(memory[a] for a in range(
        address, min(address + 32, symbols['E_END']))))
        for address in range(0x2000, symbols['E_END'], 32))
    lines.append(a24.record('9', 0x2000))
    path = args.out / f'{name}.s19'
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a24.read_s19(path)
    if parsed != memory or entry != 0x2000:
        raise ValueError('RAM updater S19 did not round-trip exactly')
    report = {'board': '2609 W65C816SXB', 'old_e_sha256': sha(old),
              'new_e_sha256': sha(new), 'source_f_sha256': sha(source_f),
              'updater_s19_sha256': sha(path.read_bytes()), 'updater_s19': str(path),
              'board_installed': False}
    (args.out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
