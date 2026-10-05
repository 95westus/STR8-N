"""Exact 3993-byte b2 -> command-catalog b2 E/F update, with disk backup.

Reuse the qualified RAM updater, with b2 staging at 6100. B2:F's original
beta1 recovery backup is preserved; the source b2 F is backed up on the host.
No device access. Requires the known E and normalized F installed on 2205.
"""
import argparse
import json
from pathlib import Path
import build_v2_b2_board_update as update
import build_v2_b2 as firmware
from v2_b2_config import valid_boot_pocket

OLD_E_SHA = '2aecb0106cceba968665747ae9a9e7da0bc6af6541b2728e78428794f3cac5bb'
OLD_F_SHA = '3ebf70b9d466d0f63f717dc32ec9d4aa095360c6846ebb0c40ffb28c06d5dd12'


def plan(source, phase, backup=None, unused=None):
    metadata = json.loads((firmware.OUT / 'build.json').read_text())
    if metadata.get('manager_storage'):
        raise ValueError('This candidate requires B/E installation; old E/F-only updater is unsupported')
    source = update.source_ef(source)
    e, f = source[:4096], source[4096:]
    if update.sha(update.normalized(f)) != OLD_F_SHA:
        raise ValueError('Unknown source b2 core')
    candidate_e = (firmware.OUT / f'{firmware.STEM}-e000-efff.bin').read_bytes()
    candidate_f = (firmware.OUT / f'{firmware.STEM}-f000-ffff.bin').read_bytes()
    if len(candidate_e) != 4096 or len(candidate_f) != 4096:
        raise ValueError('Candidate must contain two complete sectors')
    binding = firmware.crc16(candidate_f[:0xFD0]+candidate_f[0xFE0:])
    if candidate_e[:4] != b'EM\x01\x01' or int.from_bytes(candidate_e[4:6], 'little') != binding:
        raise ValueError('Candidate E/F binding mismatch')
    if not valid_boot_pocket(f[update.POCKET]):
        raise ValueError('Invalid source boot/config pocket')
    if backup is None or update.backup_f(backup) != f:
        raise ValueError('Exact host F backup required for both phases')
    if phase == 'e':
        if update.sha(e) != OLD_E_SHA:
            raise ValueError('Unknown source b2 E sector')
        return e, candidate_e, f, 0xE0
    if phase != 'f' or e != candidate_e:
        raise ValueError('F update requires the complete matching new E')
    new_f = candidate_f[:0xFD0]+f[update.POCKET]+candidate_f[0xFE0:]
    return f, new_f, e, 0xF0


def build(source, out, phase, backup):
    result = update.build(source, out, phase, backup, planner=plan,
                          staging=0x6100, flash_backup_guard=False, scratch_base=0xE0)
    manifest_path = Path(out) / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest.update(baseline_sha256=OLD_F_SHA, source_version='2.0b2-3993',
                    backup_sha256=update.sha(update.backup_f(backup)),
                    backup_location='host', source_e_sha256=OLD_E_SHA)
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readback', type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    source = update.source_ef(args.readback.read_bytes())
    backup = args.backup.read_bytes()
    e_artifact = build(source, args.out / 'e-update', 'e', backup)
    f_artifact = build(e_artifact[1]+source[4096:], args.out / 'f-update', 'f', backup)
    print(e_artifact[0])
    print(f_artifact[0])


if __name__ == '__main__':
    main()
