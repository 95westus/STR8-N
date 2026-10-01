"""Build board-2512 exact-preimage RAM installers for alpha21 to alpha25 E/F."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import build_v2_a24 as old
import build_v2_a25 as new

EXPECTED_EF = '9717a340dbb3c9540db880fec8d9fd6717f64873aadbb0a899281c0e9f688df9'
OUT_DEFAULT = new.ROOT / 'BUILD/board/a25-2512'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def make_updater(name, source, previous, candidate, required, worker, out):
    stage = out / name / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    old.include_bytes(stage / 'e-old-image.inc', previous)
    old.include_bytes(stage / 'e-new-image.inc', candidate)
    if required is not None:
        old.include_bytes(stage / 'e-required-image.inc', required)
    (stage / 'e-worker-addresses.inc').write_text(''.join(
        f'{symbol:24} EQU     ${worker[symbol]:04X}\n'
        for symbol in ('V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')
    previous_out = old.OUT
    try:
        old.OUT = out / name
        memory, symbols = old.assemble(name, 0x2000, shutil.which('wdc02as'),
                                       shutil.which('wdcln'), source_file=source,
                                       include_dirs=(stage,))
    finally:
        old.OUT = previous_out
    if symbols['START'] != 0x2000 or symbols['E_END'] >= 0x6900:
        raise ValueError(f'{name}: RAM layout changed')
    for label, image in (('E_OLD', previous), ('E_NEW', candidate),
                         ('E_REQUIRED', required)):
        if image is None:
            continue
        if bytes(memory[a] for a in range(symbols[label], symbols[label]+4096)) != image:
            raise ValueError(f'{name}: {label} does not match input')
    lines = [old.record('0', 0, f'STR8-N 2.0a25 {name}'.encode())]
    lines.extend(old.record('1', address, bytes(memory[a] for a in range(
        address, min(address+32, symbols['E_END']))))
        for address in range(0x2000, symbols['E_END'], 32))
    lines.append(old.record('9', 0x2000))
    path = out / f'{name}.s19'
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = old.read_s19(path)
    if parsed != memory or entry != 0x2000:
        raise ValueError(f'{name}: S19 round-trip failed')
    return path, symbols

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first_readback', type=Path)
    parser.add_argument('second_readback', type=Path)
    parser.add_argument('--out', type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    first = args.first_readback.read_bytes()
    second = args.second_readback.read_bytes()
    if len(first) != 8192 or first != second or sha(first) != EXPECTED_EF:
        raise ValueError('Board E/F readbacks do not match the pinned board-2512 preimage')
    old_e, old_f = first[:4096], first[4096:]
    if old_e != bytes(4096):
        raise ValueError('B3:E is not the expected all-zero sector')
    frozen = new.ROOT / 'output/qualification/v2-alpha21-2026-09-24/candidate'
    frozen_image = (frozen / 'str8n-v2-alpha21-e000-ffff.bin').read_bytes()
    if len(frozen_image) != 8192 or old_f != frozen_image[4096:]:
        raise ValueError('B3:F does not match the frozen alpha21 image')
    candidate = (new.OUT / f'{new.STEM}-e000-ffff.bin').read_bytes()
    if len(candidate) != 8192:
        raise ValueError('Build alpha25 before preparing guarded update')
    new_e, new_f = candidate[:4096], candidate[4096:]
    if old_f[0xFE0:] != new_f[0xFE0:]:
        raise ValueError('Hardware vectors or configuration bytes changed')
    if new_e[:4] != b'RT\x01\x00' or new_e[0x800:0x805] != b'SR\x01\x01\x18':
        raise ValueError('Alpha25 E descriptors changed')
    args.out.mkdir(parents=True, exist_ok=True)
    worker = json.loads((frozen / 'build.json').read_text())['worker']
    new_worker = json.loads((new.OUT / 'build.json').read_text())['worker']
    for symbol in ('V2W_SNAPSHOT', 'V2W_MUTATE'):
        if worker[symbol] != new_worker[symbol]:
            raise ValueError(f'Flash worker address drift: {symbol}')
    e_path, e_symbols = make_updater(
        'str8n-v2-alpha25-board2512-e-install-2000',
        new.SOURCE / 'str8n-v2-e-repair-2000.asm', old_e, new_e, None,
        worker, args.out)
    f_path, f_symbols = make_updater(
        'str8n-v2-alpha25-board2512-f-install-2000',
        new.SOURCE / 'str8n-v2-f-update-2000.asm', old_f, new_f, new_e,
        worker, args.out)
    for name, image in (('old-e.bin', old_e), ('old-f.bin', old_f),
                        ('new-e.bin', new_e), ('new-f.bin', new_f)):
        (args.out / name).write_bytes(image)
    report = {
        'board': 'W65C02SXB COM4, board 2512',
        'source_ef_sha256': sha(first), 'old_e_sha256': sha(old_e),
        'old_f_sha256': sha(old_f), 'new_e_sha256': sha(new_e),
        'new_f_sha256': sha(new_f),
        'e_updater': str(e_path), 'e_updater_sha256': sha(e_path.read_bytes()),
        'e_updater_end': e_symbols['E_END'],
        'f_updater': str(f_path), 'f_updater_sha256': sha(f_path.read_bytes()),
        'f_updater_end': f_symbols['E_END'],
        'board_installed_by_builder': False,
    }
    (args.out / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
