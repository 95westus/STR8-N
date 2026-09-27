"""Prepare an E-sector S19 for an exact alpha21 Bank-3 readback.

This is a host-only staging tool. It never accesses a board or installs flash.
"""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path

from build_v2_a22 import OUT, STEM, record

ALPHA21_F_HASHES = {
    '3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49': 'frozen-rc1',
    '0ddaa218bc49817aca4d44f4793140c901ac2963333fd8fa190bfcf01db7f4d5': 'source-built-a21',
}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('bank3_readback', type=Path,
                        help='exact 8192-byte E-F or 32768-byte full Bank-3 readback')
    parser.add_argument('--out', type=Path, default=OUT / 'upgrade-prep')
    args = parser.parse_args()
    bank = args.bank3_readback.read_bytes()
    if len(bank) == 0x8000:
        old_e, old_f = bank[0x6000:0x7000], bank[0x7000:0x8000]
    elif len(bank) == 0x2000:
        old_e, old_f = bank[:0x1000], bank[0x1000:0x2000]
    else:
        raise SystemExit('Expected a complete 8192-byte E-F or 32768-byte Bank-3 readback')
    old_f_hash = sha256(old_f).hexdigest()
    if old_f_hash not in ALPHA21_F_HASHES:
        raise SystemExit('Bank-3 F is not an exact supported alpha21 image')
    if ALPHA21_F_HASHES[old_f_hash] == 'source-built-a21':
        source_image = OUT.parent.joinpath('v2-alpha21/str8n-v2-alpha21-e000-ffff.bin')
        if not source_image.exists() or old_f != source_image.read_bytes()[0x1000:]:
            raise SystemExit('Source-built alpha21 F must match a fresh local build')
    if old_e[0x800:0xF00] != b'\xff' * 0x700:
        raise SystemExit('E800-EEFF is occupied; refusing to replace it')
    candidate = (OUT / f'{STEM}-e000-ffff.bin').read_bytes()
    if len(candidate) != 8192 or candidate[:0x800] != b'\xff' * 0x800:
        raise SystemExit('Invalid a22 candidate image')
    if candidate[0xF00:0x1000] != b'\xff' * 0x100:
        raise SystemExit('Candidate attempts to change the configuration page')
    staged = bytearray(old_e)
    staged[0x800:0xF00] = candidate[0x800:0xF00]
    if staged[:0x800] != old_e[:0x800] or staged[0xF00:] != old_e[0xF00:]:
        raise SystemExit('Preservation check failed')
    args.out.mkdir(parents=True, exist_ok=True)
    e_bin = args.out / f'{STEM}-bank3-e-preserved.bin'
    e_s19 = args.out / f'{STEM}-bank3-e-preserved.s19'
    e_bin.write_bytes(staged)
    lines = [record('0', 0, b'STR8-N 2.0a22 B3 E')]
    lines.extend(record('1', addr, staged[addr-0xE000:addr-0xE000+32])
                 for addr in range(0xE000, 0xF000, 32))
    lines.append(record('9', 0xF004))
    e_s19.write_text('\n'.join(lines) + '\n', encoding='ascii')
    manifest = {
        'source_bank3_sha256': sha256(bank).hexdigest(),
        'source_f_sha256': sha256(old_f).hexdigest(),
        'source_f_variant': ALPHA21_F_HASHES[old_f_hash],
        'source_e_sha256': sha256(old_e).hexdigest(),
        'staged_e_sha256': sha256(staged).hexdigest(),
        'candidate_f_sha256': sha256(candidate[0x1000:]).hexdigest(),
        'staged_e_s19_sha256': sha256(e_s19.read_bytes()).hexdigest(),
        'board_install_qualified': False,
    }
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Staged E: {e_s19}')
    print('Host preflight passed; no board writes performed')


if __name__ == '__main__':
    main()
