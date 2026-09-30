"""Build an exact-image F updater from the installed optimized a22 to a23."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_a23 as a23

OLD_F_SHA256 = '23278c32717d8cd1a26b13d7eddc79019050f2ba21f37729e9566a2e021758cd'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live_ef', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    old_ef = args.live_ef.read_bytes()
    candidate = (a23.OUT / f'{a23.STEM}-e000-ffff.bin').read_bytes()
    if len(old_ef) != 8192 or len(candidate) != 8192:
        raise ValueError('E/F image must be 8192 bytes')
    old_e, old_f = old_ef[:4096], old_ef[4096:]
    new_f = candidate[4096:]
    if sha(old_f) != OLD_F_SHA256:
        raise ValueError('Installed optimized a22 F mismatch')
    if old_e[0x800:0xF00] != candidate[0x800:0xF00]:
        raise ValueError('E extension code changed; F-only update is unsafe')
    if old_f == new_f or new_f[-4:-2] != b'\x04\xf0':
        raise ValueError('Invalid candidate F')
    out = args.out.resolve()
    (out / 'asm').mkdir(parents=True, exist_ok=True)
    (out / 'old-f.bin').write_bytes(old_f)
    (out / 'candidate-f.bin').write_bytes(new_f)
    a23.include_bytes(out / 'asm/str8n-v2-a22-old-top.inc', old_f)
    with (out / 'asm/str8n-v2-current-top-image.inc').open('w', encoding='ascii') as stream:
        stream.write(f'TU_CANDIDATE_SUM        EQU             ${sum(new_f) & 0xFFFF:04X}\n')
        for i in range(0, len(new_f), 16):
            stream.write('                        DB              ' +
                         ','.join(f'${v:02X}' for v in new_f[i:i+16]) + '\n')
    old_out = a23.OUT
    try:
        a23.OUT = out
        name = 'str8n-v2-alpha23-f-update-2000'
        memory, sym = a23.assemble(name, None, shutil.which('wdc02as'),
                                   shutil.which('wdcln'),
                                   source_file=a23.TOP_UPDATE_SOURCE,
                                   include_dirs=(out / 'asm',), defines=(
                                       ('STR8_TOP_EMBED', 0), ('STR8_DIRECTORY_REFRESH', 1),
                                       ('STR8_V2_TOP_IMAGE', 1), ('STR8_IN65_TOP_IMAGE', 0),
                                       ('STR8_IN65_VERSION_135', 0), ('STR8_IN65_VERSION_133', 0)))
    finally:
        a23.OUT = old_out
    if sym['TU_CANDIDATE_IMAGE'] != 0x4000 or sym['TU_OLD_IMAGE'] != 0x5000:
        raise ValueError('Updater image layout moved')
    if bytes(memory[a] for a in range(0x4000, 0x5000)) != new_f:
        raise ValueError('Embedded candidate F mismatch')
    if bytes(memory[a] for a in range(0x5000, 0x6000)) != old_f:
        raise ValueError('Embedded old F mismatch')
    ordered = sorted(memory)
    lines = [a23.record('0', 0, b'STR8-N 2.0a23 F update')]
    start = 0
    while start < len(ordered):
        address = ordered[start]
        run = bytearray([memory[address]])
        start += 1
        while start < len(ordered) and len(run) < 32 and ordered[start] == address + len(run):
            run.append(memory[ordered[start]])
            start += 1
        lines.append(a23.record('1', address, run))
    lines.append(a23.record('9', 0x2000))
    s19 = out / f'{name}.s19'
    s19.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, entry = a23.read_s19(s19)
    if parsed != memory or entry != 0x2000:
        raise ValueError('Updater S19 round trip failed')
    report = {'old_f_sha256': sha(old_f), 'candidate_f_sha256': sha(new_f),
              'live_e_sha256': sha(old_e), 'e_code_unchanged': True,
              'updater': str(s19), 'updater_sha256': sha(s19.read_bytes()),
              'changed_f_bytes': sum(a != b for a, b in zip(old_f, new_f))}
    (out / 'update.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
