"""Build exact-image RAM updaters for the paired a22 autostart-dot revision."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_a22 as a22


OLD_F_SHA256 = 'b1cdbc62db9429571a356b566931b6fdefb3c7fa991a4370a60226df380c6880'
OLD_E_CODE_SHA256 = '7ec7c082f304b8afddf32ede92ed9a2f500532d2c389a011928a9714cf1b1aba'
NEW_F_SHA256 = '1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439'
NEW_E_CODE_SHA256 = 'fcb0a253fa802c5e44ce48bba22c4b004a49b6dfe8b6563a9d8891ea75875401'
OUT = a22.ROOT / 'BUILD/v2-alpha22-dot-update'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_s19(path, memory, entry, dense_end=None):
    ordered = sorted(memory)
    if dense_end is not None and ordered != list(range(entry, dense_end)):
        raise ValueError('Updater RAM image is not dense')
    lines = [a22.record('0', 0, b'STR8-N 2.0a22 dot update')]
    index = 0
    while index < len(ordered):
        address = ordered[index]
        data = bytearray([memory[address]])
        index += 1
        while (index < len(ordered) and len(data) < 32
               and ordered[index] == address + len(data)):
            data.append(memory[ordered[index]])
            index += 1
        lines.append(a22.record('1', address, data))
    lines.append(a22.record('9', entry))
    path.write_text('\n'.join(lines) + '\n', encoding='ascii')
    parsed, parsed_entry = a22.read_s19(path)
    if parsed != memory or parsed_entry != entry:
        raise ValueError('Updater S19 round trip failed')
    return sha(path.read_bytes())


def build_e(old_e, new_e, worker):
    stage = OUT / 'e'
    stage.mkdir(parents=True, exist_ok=True)
    a22.include_bytes(stage / 'e-old-image.inc', old_e)
    a22.include_bytes(stage / 'e-new-image.inc', new_e)
    (stage / 'e-worker-addresses.inc').write_text(
        ''.join(f'{name:24} EQU     ${worker[name]:04X}\n'
                for name in ('V2W_SNAPSHOT', 'V2W_MUTATE')), encoding='ascii')
    name = 'str8n-v2-alpha22-dot-e-update-2000'
    memory, sym = a22.assemble(
        name, 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'),
        source_file=a22.SOURCE / 'str8n-v2-e-repair-2000.asm',
        include_dirs=(stage,))
    if sym['START'] != 0x2000 or sym['E_END'] >= 0x6900:
        raise ValueError('E updater layout changed')
    if bytes(memory[a] for a in range(sym['E_NEW'], sym['E_NEW'] + 4096)) != new_e:
        raise ValueError('Embedded new E differs')
    if bytes(memory[a] for a in range(sym['E_OLD'], sym['E_OLD'] + 4096)) != old_e:
        raise ValueError('Embedded old E differs')
    path = OUT / (name + '.s19')
    return path, write_s19(path, memory, 0x2000, sym['E_END'])


def build_f(old_f, new_f):
    stage = OUT / 'f'
    stage.mkdir(parents=True, exist_ok=True)
    a22.include_bytes(stage / 'str8n-v2-a21-old-top.inc', old_f)
    candidate_include = stage / 'str8n-v2-current-top-image.inc'
    candidate_include.write_text(
        f'TU_CANDIDATE_SUM        EQU             ${sum(new_f) & 0xFFFF:04X}\n',
        encoding='ascii')
    with candidate_include.open('a', encoding='ascii') as stream:
        stream.write(''.join(
            '                        DB              '
            + ','.join(f'${value:02X}' for value in new_f[i:i+16]) + '\n'
            for i in range(0, len(new_f), 16)))
    name = 'str8n-v2-alpha22-dot-f-update-2000'
    memory, sym = a22.assemble(
        name, None, shutil.which('wdc02as'), shutil.which('wdcln'),
        source_file=a22.TOP_UPDATE_SOURCE, include_dirs=(stage,), defines=(
            ('STR8_TOP_EMBED', 0), ('STR8_DIRECTORY_REFRESH', 1),
            ('STR8_V2_TOP_IMAGE', 1), ('STR8_IN65_TOP_IMAGE', 0),
            ('STR8_IN65_VERSION_135', 0), ('STR8_IN65_VERSION_133', 0)))
    if sym['TU_CANDIDATE_IMAGE'] != 0x4000 or sym['TU_OLD_IMAGE'] != 0x5000:
        raise ValueError('F updater layout changed')
    if bytes(memory[a] for a in range(0x4000, 0x5000)) != new_f:
        raise ValueError('Embedded new F differs')
    if bytes(memory[a] for a in range(0x5000, 0x6000)) != old_f:
        raise ValueError('Embedded old F differs')
    path = OUT / (name + '.s19')
    return path, write_s19(path, memory, 0x2000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-ef-readback', type=Path, required=True)
    args = parser.parse_args()
    live = args.live_ef_readback.read_bytes()
    if len(live) != 8192:
        raise ValueError('Live E/F readback must be exactly 8192 bytes')
    old_e, old_f = live[:4096], live[4096:]
    if sha(old_f) != OLD_F_SHA256 or sha(old_e[0x800:0xF00]) != OLD_E_CODE_SHA256:
        raise ValueError('Live E/F is not the exact installed paired revision')
    new_f = (a22.OUT / f'{a22.STEM}-f000-ffff.bin').read_bytes()
    built_e = (a22.OUT / f'{a22.STEM}-e000-efff.bin').read_bytes()
    if len(new_f) != 4096 or len(built_e) != 4096:
        raise ValueError('Built E/F sector length mismatch')
    if sha(new_f) != NEW_F_SHA256 or sha(built_e[0x800:0xF00]) != NEW_E_CODE_SHA256:
        raise ValueError('Built E/F is not the tested dot revision')
    if new_f[-4:-2] != b'\x04\xf0':
        raise ValueError('Candidate RESET vector is not F004')
    new_e = old_e[:0x800] + built_e[0x800:0xF00] + old_e[0xF00:]
    if new_e == old_e or new_f == old_f:
        raise ValueError('One of the paired sectors has no change')
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    (OUT / 'old-e.bin').write_bytes(old_e)
    (OUT / 'candidate-e.bin').write_bytes(new_e)
    (OUT / 'old-f.bin').write_bytes(old_f)
    (OUT / 'candidate-f.bin').write_bytes(new_f)
    worker = json.loads((a22.OUT / 'build.json').read_text())['worker']
    original_out = a22.OUT
    try:
        a22.OUT = OUT
        e_path, e_s19_sha = build_e(old_e, new_e, worker)
        f_path, f_s19_sha = build_f(old_f, new_f)
    finally:
        a22.OUT = original_out
    report = dict(live_readback=str(args.live_ef_readback),
                  live_ef_sha256=sha(live), old_e_sha256=sha(old_e),
                  old_f_sha256=sha(old_f), candidate_e_sha256=sha(new_e),
                  candidate_f_sha256=sha(new_f),
                  e_changed_bytes=sum(a != b for a, b in zip(old_e, new_e)),
                  f_changed_bytes=sum(a != b for a, b in zip(old_f, new_f)),
                  e_updater=str(e_path), e_s19_sha256=e_s19_sha,
                  f_updater=str(f_path), f_s19_sha256=f_s19_sha)
    (OUT / 'update.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
