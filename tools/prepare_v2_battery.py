"""Prepare a backup-bound battery update offline; never opens a serial port.

Only accepts the exact map-assets shared baseline. Keeps both installed monitor
slots, F, board-specific settings/identity tail, MAINT and saved programs intact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import beta4_migration as m

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'BUILD/v2-battery'
BASE = ROOT/'BUILD/v2-map-assets'
sha = lambda data: hashlib.sha256(data).hexdigest()
read = lambda path: json.loads(path.read_text())


def audit():
    meta = read(BUILD/'build.json')
    report = read(BUILD/'battery-test-results.json')
    assert meta['battery_age'] and meta['version'] == '2.0b25'
    assert report['passed'] and report['artifacts'] == meta['artifacts']
    for name in ('clock-summary', 'compact-boot', 'version'):
        regression = read(BUILD/(name+'-test-results.json'))
        assert regression['passed'] and regression['artifacts'] == meta['artifacts'], name
        if 'clock_sha256' in regression:
            assert regression['clock_sha256'] == meta['clock_sha256'], name
        if 'version_asset_sha256' in regression:
            assert regression['version_asset_sha256'] == meta['version_asset_sha256'], name
    for name, digest in meta['artifacts'].items():
        assert sha((BUILD/name).read_bytes()) == digest, name
    for folder, field in [('battery', 'battery_asset_sha256'), ('boot-status', 'status_asset_sha256')]:
        assert sha((BUILD/folder/'asset.bin').read_bytes()) == meta[field]
    assert sha((BUILD/'clock/storage.bin').read_bytes()) == meta['clock_storage_sha256']
    assert report['clock_sha256'] == meta['clock_sha256']
    assert report['battery_asset_sha256'] == meta['battery_asset_sha256']
    if meta.get('flash_wear_warnings'):
        wear = read(BUILD/'flash-wear-test-results.json')
        assert wear['passed'] and wear['artifacts'] == meta['artifacts']
        assert wear['battery_asset_sha256'] == meta['battery_asset_sha256']
        assert wear['thresholds'] == meta['flash_wear_thresholds']
    return meta


def plan(banks):
    assert len(banks) == 4 and all(len(b) == 32768 for b in banks)
    final = [bytearray(b) for b in banks]
    # Reject unknown contents instead of reclaiming/erasing somebody's data.
    ranges = [(3, 0x6000, 'str8n-v2-recovery-e000-efff.bin'),
              (2, 0x4800, 'boot-status/asset.bin'),
              (1, 0x3000, 'clock/storage.bin')]
    assert banks[3][0x7000:] == (BASE/'str8n-v2-recovery-f000-ffff.bin').read_bytes()
    for bank, offset, name in ranges:
        before, after = (BASE/name).read_bytes(), (BUILD/name).read_bytes()
        assert len(before) == len(after)
        assert banks[bank][offset:offset+len(before)] == before, ('Unregistered source', name)
        final[bank][offset:offset+len(after)] = after
    asset = (BUILD/'battery/asset.bin').read_bytes()
    assert banks[2][0x5200:0x5200+len(asset)] == b'\xff'*len(asset), 'Battery helper allocation occupied'
    final[2][0x5200:0x5200+len(asset)] = asset
    # Helper first, loader before its new caller, CLOCK continuation before header.
    order = [(3, 12), (2, 13), (3, 14), (2, 12), (1, 13), (1, 12), (1, 11)]
    j = m.journal(banks[3])
    assert j, 'Valid configuration/wear journal required'
    cfg = bytearray(j[8:24])
    assert cfg[14:] == m.config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i], 'little') for i in range(32)]
    seq = int.from_bytes(j[4:8], 'little')
    assert seq < 0xFFFFFFFF
    for bank, sector in order:
        i = bank*8+sector-8
        assert counts[i] < 0xFFFFFF
        counts[i] += 1
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, seq+1)+b'\xff'*(4096-128)
    allowed = {(bank, (sector-8)*4096) for bank, sector in order}
    for bank in range(4):
        for offset in range(0, 32768, 4096):
            if (bank, offset) not in allowed:
                assert final[bank][offset:offset+4096] == banks[bank][offset:offset+4096]
    return final, order


def prepare(backup, output):
    meta = audit()
    manifest = read(backup/'manifest.json')
    assert manifest['repeat_verified']
    banks = [(backup/f'b{i}.bin').read_bytes() for i in range(4)]
    for i, data in enumerate(banks):
        assert data == (backup/f'b{i}-repeat.bin').read_bytes()
        assert sha(data) == manifest['banks'][i]['sha256']
    final, order = plan(banks)
    mf = read(BUILD/'migrator/manifest.json')
    # This baseline uses SR commit $3F with per-step bank+1 and address tables;
    # monitor-style mixed commit values are unnecessary (no slots are changed).
    assert mf['commit_addresses'] == mf['symbols']['MIG_COMMIT_ADDRS']
    assert len(order) <= mf['max_sectors']
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']], cells[mf['commit_after']] = len(order), 0
    expected = [bytearray(b) for b in banks]
    transfers = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytearray(final[bank][offset:offset+4096])
        commit = (bank, sector) == (1, 11)
        if commit:
            data[3] = 0xFF
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        cells.update(dict(enumerate(row, mf['table']+9*i)))
        cells[mf['banks']+i], cells[mf['commits']+i] = bank, 2 if commit else 0
        addresses = (0xB003).to_bytes(2,'little')+b'\0\0' if commit else bytes(4)
        cells.update(dict(enumerate(addresses, mf['commit_addresses']+4*i)))
        expected[bank][offset:offset+4096] = data
        if commit:
            expected[1][0x3003] = 0x3F
        transfers.append(data)
    assert expected == final
    # Create only after every validation succeeds; existing plans are preserved.
    output.mkdir(parents=True, exist_ok=False)
    installer = m.s19(cells, entry)
    (output/'installer.s19').write_bytes(installer)
    info = dict(board=manifest['board'], version=meta['version'], clock_version=meta['clock_version'],
        prior_directory=str(backup.resolve()), steps=[dict(bank=b,sector=s) for b,s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        storage_update=True, commit_records=[dict(bank=1,address=0xB000)],
        monitor_slots_unchanged=True, immutable_recovery_unchanged=True,
        board_access=False, boards_flashed=False, hardware_tested=False)
    (output/'plan.json').write_text(json.dumps(info,indent=2)+'\n')
    for i, data in enumerate(transfers):
        (output/f'transfer-{i:02d}.bin').write_bytes(data)
    for i, data in enumerate(final):
        (output/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED offline battery update:', manifest['board'], len(order), 'sectors; model rehearsal required')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    prepare(args.backup, args.out)
