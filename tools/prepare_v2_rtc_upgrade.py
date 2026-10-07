"""Prepare a pinned multi-bank RTC upgrade from a complete repeated backup."""
import argparse
import hashlib
import json
from pathlib import Path

import beta4_migration as migration
import build_v2_rtc_kernel as kernel

ROOT = Path(__file__).resolve().parents[1]
KNOWN_A26_2512_F = '53f1ef4974c104007be03b4dbeedb1f6c3c6fe7a5c4038c30efb80c0f8a3ea69'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plan(banks, board):
    out = kernel.OUT
    report = json.loads((out / 'build.json').read_text())
    if board == '2512' and sha(banks[3][0x7000:]) == KNOWN_A26_2512_F:
        name, config, counts, sequence = 'known 2512 alpha26; unavailable EEPROM settings', migration.default_config(), [0]*32, 0
    else:
        name, config, counts, sequence = migration.source_settings(banks[3], 'str8n')
        known = migration.maintenance_storage(ROOT / 'BUILD/v2-beta4/kit')
        if banks[3][:8192] != known:
            raise ValueError('B3:8/9 does not match the known MAINT record; preserve unexpected contents')
    if banks[1][:8192] != bytes([255])*8192:
        raise ValueError('B1:8/9 is not erased; do not overwrite existing records')
    config = bytearray(config)
    old = migration.journal(banks[3])
    if old and old[15:16] == b'P':
        # Configuration is at record offset 8; retain an accepted A/B preference.
        page = old[16]
        generation = int.from_bytes(old[17:21], 'little')
        offset = (page << 8) - 0x8000
        if page in (0xA0, 0xB0) and migration.slot_valid(banks[3][offset:offset+4096], page):
            if int.from_bytes(banks[3][offset+8:offset+12], 'little') == generation:
                config[7:13] = b'P' + bytes([page]) + kernel.GENERATION.to_bytes(4, 'little')
    config[14:] = migration.config_sum(config)
    # Any enabled legacy autostart into newly reserved service RAM is incompatible.
    address = int.from_bytes(config[3:5], 'little')
    if config[1] and config[6] == 0 and 0x6500 <= address < 0x6700:
        raise ValueError('Autostart overlaps service RAM; resolve configuration before upgrading')
    maint = (out / 'str8n-maint-1.6-b1-8000-9fff.bin').read_bytes()
    pending = bytearray(maint)
    pending[3] = 255
    desired = {(1, 0x80): bytes(pending[:4096]), (1, 0x90): bytes(pending[4096:]),
        (3, 0x80): (out / 'str8n-rtc-component-8000-8fff.bin').read_bytes(),
        (3, 0x90): bytes([255])*4096,
        (3, 0xA0): (out / 'str8n-v2-recovery-slot-a0.bin').read_bytes(),
        (3, 0xB0): (out / 'str8n-v2-recovery-slot-b0.bin').read_bytes(),
        (3, 0xE0): (out / 'str8n-v2-recovery-e000-efff.bin').read_bytes(),
        (3, 0xF0): (out / 'str8n-v2-recovery-f000-ffff.bin').read_bytes()}
    order = [(3, 0xD0)] if banks[3][0x5000:0x6000] != bytes([255])*4096 else []
    order += [(3, 0xC0), (1, 0x80), (1, 0x90)]
    order += [item for item in ((3,0x90),(3,0x80),(3,0xA0),(3,0xB0),(3,0xE0),(3,0xF0))
              if banks[item[0]][(item[1]<<8)-0x8000:(item[1]<<8)-0x7000] != desired[item]]
    if sequence == 0xFFFFFFFF:
        raise ValueError('Journal sequence exhausted')
    after = list(counts)
    for bank, page in order:
        i = bank*8 + (page >> 4) - 8
        if after[i] == 0xFFFFFF:
            raise ValueError('Erase count exhausted')
        after[i] += 1
    desired[(3,0xD0)] = bytes([255])*4096
    desired[(3,0xC0)] = migration.metadata(bytes(config), after, sequence+1) + bytes([255])*(4096-128)
    expected = [bytearray(b) for b in banks]
    rows, transfers = [], []
    commit_after = order.index((1,0x90)) + 1
    for bank, page in order:
        data = desired[(bank,page)]
        assert len(data) == 4096
        rows.append(bytes([page]) + migration.fnv(expected[bank]).to_bytes(4,'little') + migration.fnv(data).to_bytes(4,'little'))
        expected[bank][(page<<8)-0x8000:(page<<8)-0x7000] = data
        transfers.append(data)
        if len(rows) == commit_after:
            expected[1][3] = 0x3F
    template = out / 'migrator'
    manifest = json.loads((template / 'manifest.json').read_text())
    s19 = template / 'rtc-migrator-2000.s19'
    if sha(s19.read_bytes()) != manifest['sha256']:
        raise ValueError('Installer template hash mismatch')
    cells, entry = migration.read_s19(s19)
    assert len(order) <= 10 and entry == 0x2000
    cells[manifest['count']] = len(order)
    cells[manifest['commit_after']] = commit_after
    for i, (bank, page) in enumerate(order):
        cells[manifest['banks'] + i] = bank
    for a, value in enumerate(b''.join(rows), manifest['table']):
        assert a in cells
        cells[a] = value
    info = dict(board=board, version=kernel.VERSION, generation=kernel.GENERATION,
        source_firmware=name, steps=[dict(bank=b,sector=p>>4) for b,p in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in expected],
        config=bytes(config).hex(), counts_before=counts, counts_after=after,
        maintenance_bank=1, maintenance_commit_after=commit_after,
        fixed_f_changed=banks[3][0x7000:] != expected[3][0x7000:],
        journals_preaccount_planned_attempts=True)
    return info, migration.s19(cells, entry), transfers, [bytes(b) for b in expected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--board', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.backup / 'manifest.json').read_text())
    assert manifest['repeat_verified'] and manifest['board'] == args.board
    banks = [(args.backup / f'b{b}.bin').read_bytes() for b in range(4)]
    assert [sha(b) for b in banks] == [v['sha256'] for v in manifest['banks']]
    for b in range(4):
        assert (args.backup / f'b{b}-repeat.bin').read_bytes() == banks[b]
    info, installer, transfers, expected = plan(banks, args.board)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'installer.s19').write_bytes(installer)
    info['installer_sha256'] = sha(installer)
    (args.out / 'plan.json').write_text(json.dumps(info, indent=2) + '\n')
    for i, data in enumerate(transfers):
        (args.out / f'transfer-{i:02d}.bin').write_bytes(data)
    for b, data in enumerate(expected):
        (args.out / f'expected-b{b}.bin').write_bytes(data)
    print(args.board, info['source_firmware'], info['steps'], 'F changed:', info['fixed_f_changed'])


if __name__ == '__main__':
    main()
