"""Build a RAM updater for the exact old B3:E extension after an F relink."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_a22 as a22


OLD_E_SHA256 = '72ee62abb21795c62a6d680bdb577946f83f264ca1ce8e561827b8d9278f07b1'
F_SHA256 = 'b1cdbc62db9429571a356b566931b6fdefb3c7fa991a4370a60226df380c6880'
NAME = 'str8n-v2-alpha22-e-repair-2000'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-ef-readback', type=Path, required=True)
    args = parser.parse_args()
    live = args.live_ef_readback.read_bytes()
    if len(live) != 8192:
        raise ValueError('Live B3:E/F readback must be exactly 8192 bytes')
    old, live_f = live[:4096], live[4096:]
    old_hash = hashlib.sha256(old).hexdigest()
    f_hash = hashlib.sha256(live_f).hexdigest()
    if old_hash != OLD_E_SHA256 or f_hash != F_SHA256:
        raise ValueError(f'Live E/F identity mismatch: E={old_hash} F={f_hash}')
    built = (a22.OUT / f'{a22.STEM}-e000-efff.bin').read_bytes()
    candidate = bytearray(old)
    candidate[0x800:0xF00] = built[0x800:0xF00]
    if candidate == old:
        raise ValueError('Old and new E sectors are identical')
    if candidate[:0x800] != old[:0x800] or candidate[0xF00:] != old[0xF00:]:
        raise ValueError('E repair would change data outside extension')
    out = a22.ROOT / 'BUILD/v2-alpha22-e-repair'
    stage = out / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    a22.include_bytes(stage / 'e-old-image.inc', old)
    a22.include_bytes(stage / 'e-new-image.inc', candidate)
    (out / 'old-e.bin').write_bytes(old)
    (out / 'candidate-e.bin').write_bytes(candidate)
    report = json.loads((a22.OUT / 'build.json').read_text())
    worker = report['worker']
    (stage / 'e-worker-addresses.inc').write_text(
        ''.join(f'{name:24} EQU     ${worker[name]:04X}\n'
                for name in ('V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')
    a22.OUT = out
    memory, sym = a22.assemble(
        NAME, 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'),
        source_file=a22.SOURCE / 'str8n-v2-e-repair-2000.asm',
        include_dirs=(stage,))
    if sym['START'] != 0x2000 or sym['E_END'] >= 0x6900:
        raise ValueError('RAM repair layout changed')
    if bytes(memory[a] for a in range(sym['E_NEW'], sym['E_NEW']+4096)) != candidate:
        raise ValueError('Candidate E embed differs')
    if bytes(memory[a] for a in range(sym['E_OLD'], sym['E_OLD']+4096)) != old:
        raise ValueError('Old E embed differs')
    ordered = sorted(memory)
    if ordered != list(range(0x2000, sym['E_END'])):
        raise ValueError('Updater RAM image is not dense')
    lines = [a22.record('0', 0, b'STR8-N 2.0a22 E repair')]
    lines.extend(a22.record('1', address,
                            bytes(memory[a] for a in range(address, min(address+32, sym['E_END']))))
                 for address in range(0x2000, sym['E_END'], 32))
    lines.append(a22.record('9', 0x2000))
    final = out / f'{NAME}.s19'
    final.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a22.read_s19(final)
    if parsed != memory or entry != 0x2000:
        raise ValueError('Updater S19 round trip failed')
    result = dict(live_readback=str(args.live_ef_readback), old_e_sha256=old_hash,
                  live_f_sha256=f_hash,
                  candidate_e_sha256=hashlib.sha256(candidate).hexdigest(),
                  changed_bytes=sum(a != b for a, b in zip(old, candidate)),
                  updater_s19_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
                  updater=str(final))
    (out / 'repair.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
