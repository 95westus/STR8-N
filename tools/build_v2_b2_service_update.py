"""Exact command-catalog -> SERVICE.REGISTER E updater, guarded by F and B.

Install and verify the zero-filled B manager backing with I first. This RAM
updater then checks exact old E, unchanged F, and all B bytes, before/after
confirmation. No device I/O. Uses existing b2 staging and monitor scratch.
"""
import argparse
import json
from pathlib import Path
import build_v2_b2_board_update as update
import build_v2_b2 as firmware
from v2_b2_config import valid_boot_pocket, decode_header, decode_locator

OLD_E_SHA = '50d85e12c6219357e0b71c72af81e09605c62f3b66a4363833080459759fac14'
OLD_F_SHA = 'e4fd452810074ba27bc772cb05a29546027ca4b647bc7b7211ee06427d6866ad'


def plan(source, phase, backup=None, unused=None):
    source = update.source_ef(source)
    e, f = source[:4096], source[4096:]
    if phase != 'e' or update.sha(e) != OLD_E_SHA:
        raise ValueError('Expected the exact installed command-catalog E image')
    if update.sha(update.normalized(f)) != OLD_F_SHA:
        raise ValueError('Unknown F core')
    if not valid_boot_pocket(f[update.POCKET]):
        raise ValueError('Invalid boot/config pocket')
    if backup is None or update.backup_f(backup) != f:
        raise ValueError('Exact host F backup required')
    candidate = (firmware.OUT / f'{firmware.STEM}-e000-ffff.bin').read_bytes()
    if len(candidate) != 8192 or update.normalized(candidate[4096:]) != update.normalized(f):
        raise ValueError('Candidate would require a core update')
    binding = firmware.crc16(f[:0xFD0]+f[0xFE0:])
    if candidate[:4] != b'EM\x01\x01' or int.from_bytes(candidate[4:6], 'little') != binding:
        raise ValueError('Candidate E/F binding mismatch')
    return e, candidate[:4096], f, 0xE0


def build(readback, out):
    if len(readback) != 32768 or readback[0x3000:0x4000] != b'\xff'*4096:
        raise ValueError('Need a full initial B3 readback with an erased B sector')
    locator = decode_locator(readback[0x7FD0:0x7FE0])
    if locator is None or locator == (3, 11):
        raise ValueError('A valid configuration sector outside B3:B is required')
    bank, sector = locator
    if bank != 3:
        raise ValueError('This exact board plan expects configuration in resident B3')
    offset = (sector-8)*4096
    policy = decode_header(readback[offset:offset+16], bank, sector)
    if policy[3] & 0x08:
        raise ValueError('B3:B must be excluded from RTS storage')
    backing = (firmware.OUT / f'{firmware.STEM}-b000-bfff.bin').read_bytes()
    receipt = json.loads((firmware.OUT / 'service-registration-tests.json').read_text())
    candidate = (firmware.OUT / f'{firmware.STEM}-e000-ffff.bin').read_bytes()
    if update.sha(backing) != receipt['manager_storage_sha256'] or update.sha(candidate) != receipt['ef_sha256']:
        raise ValueError('Candidate service qualification receipt does not match')
    result = update.build(readback, out, 'e', readback[-4096:], planner=plan,
        staging=0x6100, scratch_base=0xE0, flash_backup_guard=False,
        secondary_guard=backing)
    path = Path(out) / 'manifest.json'
    metadata = json.loads(path.read_text())
    metadata.update(baseline_sha256=OLD_F_SHA, source_e_sha256=OLD_E_SHA,
                    backup_location='host', source_version='b2-command-catalog',
                    target_version='b2-service-register', backing_install_first=True)
    path.write_text(json.dumps(metadata, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readback', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(build(args.readback.read_bytes(), args.out)[0])


if __name__ == '__main__':
    main()
