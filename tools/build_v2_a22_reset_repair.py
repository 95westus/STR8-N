"""Build an exact-image a22 F repair updater from a recorded board readback.

The S19 is RAM-loaded. It checks every byte of the old B3:F image before
offering a B2:F backup or an F-sector write. It does not change E.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_a22 as a22


OLD_F_SHA256 = '6c2288de66614e25cd04d75f701fd0d65981354e54a439dcc163fe04b4c29209'
NAME = 'str8n-v2-alpha22-cold-start-repair-2000'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-ef-readback', type=Path, required=True)
    parser.add_argument('--paired-e-repair', action='store_true',
                        help='acknowledge that this F relink also requires the paired E-sector repair')
    args = parser.parse_args()
    old_ef = args.old_ef_readback.read_bytes()
    if len(old_ef) != 8192:
        raise ValueError('Old E/F readback must be exactly 8192 bytes')
    old = old_ef[-4096:]
    old_hash = hashlib.sha256(old).hexdigest()
    if old_hash != OLD_F_SHA256:
        raise ValueError(f'Old B3:F is not the installed a22 image: {old_hash}')
    candidate = (a22.OUT / f'{a22.STEM}-f000-ffff.bin').read_bytes()
    new_e = (a22.OUT / f'{a22.STEM}-e000-efff.bin').read_bytes()
    e_relink_required = old_ef[0x800:0xF00] != new_e[0x800:0xF00]
    if e_relink_required and not args.paired_e_repair:
        raise ValueError('F relink changes E extension calls; build and install the paired E repair, then pass --paired-e-repair')
    if len(candidate) != 4096 or candidate == old:
        raise ValueError('Build the corrected a22 image first')
    if candidate[-4:-2] != b'\x04\xf0':
        raise ValueError('Candidate RESET vector is not F004')
    out = a22.ROOT / 'BUILD/v2-alpha22-reset-fix'
    stage = out / 'asm'
    stage.mkdir(parents=True, exist_ok=True)
    a22.include_bytes(stage / 'str8n-v2-a21-old-top.inc', old)
    candidate_sum = sum(candidate) & 0xFFFF
    candidate_include = stage / 'str8n-v2-current-top-image.inc'
    candidate_include.write_text(
        f'TU_CANDIDATE_SUM        EQU             ${candidate_sum:04X}\n', encoding='ascii')
    with candidate_include.open('a', encoding='ascii') as stream:
        stream.write(''.join(
            '                        DB              ' +
            ','.join(f'${value:02X}' for value in candidate[i:i+16]) + '\n'
            for i in range(0, len(candidate), 16)))
    a22.OUT = out
    memory, sym = a22.assemble(
        NAME, None, shutil.which('wdc02as'), shutil.which('wdcln'),
        source_file=a22.TOP_UPDATE_SOURCE, include_dirs=(stage,), defines=(
            ('STR8_TOP_EMBED', 0), ('STR8_DIRECTORY_REFRESH', 1),
            ('STR8_V2_TOP_IMAGE', 1), ('STR8_IN65_TOP_IMAGE', 0),
            ('STR8_IN65_VERSION_135', 0), ('STR8_IN65_VERSION_133', 0)))
    if sym['TU_CANDIDATE_IMAGE'] != 0x4000 or sym['TU_OLD_IMAGE'] != 0x5000:
        raise ValueError('Updater image layout changed')
    if bytes(memory[a] for a in range(0x4000, 0x5000)) != candidate:
        raise ValueError('Candidate embed differs')
    if bytes(memory[a] for a in range(0x5000, 0x6000)) != old:
        raise ValueError('Old-image embed differs')
    ordered = sorted(memory)
    lines = [a22.record('0', 0, b'STR8-N 2.0a22 F repair')]
    index = 0
    while index < len(ordered):
        address = ordered[index]
        data = bytearray([memory[address]])
        index += 1
        while (index < len(ordered) and len(data) < 32 and
               ordered[index] == address + len(data)):
            data.append(memory[ordered[index]])
            index += 1
        lines.append(a22.record('1', address, data))
    lines.append(a22.record('9', 0x2000))
    path = out / f'{NAME}.s19'
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a22.read_s19(path)
    if parsed != memory or entry != 0x2000:
        raise ValueError('Updater S19 round trip failed')
    report = dict(old_readback=str(args.old_ef_readback), old_f_sha256=old_hash,
                  candidate_f_sha256=hashlib.sha256(candidate).hexdigest(),
                  e_relink_required=e_relink_required,
                  updater_s19_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  updater=str(path))
    (out / 'repair.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
