"""Backup-bound beta26 installation on 2609; keep active beta25 as fallback."""
import argparse
import json
from pathlib import Path
import beta4_migration as m
import prepare_v2_battery as battery
import update_v2_beta24 as deploy

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'BUILD/v2-beta26'
PARENT = ROOT/'BUILD/v2-battery'
BOARD = '2609'
read, sha = deploy.read, deploy.sha


def build_audit():
    battery.audit()
    meta = read(BUILD/'build.json')
    assert (meta['version'], meta['generation']) == ('2.0b26', 38)
    assert meta['battery_parent_build_sha256'] == sha((PARENT/'build.json').read_bytes())
    for name, digest in meta['artifacts'].items():
        assert sha((BUILD/name).read_bytes()) == digest, name
    for name in ('str8n-v2-recovery-f000-ffff.bin',
                 'clock/storage.bin', 'battery/asset.bin',
                 'local-display/asset.bin', 'version/asset.bin'):
        assert (BUILD/name).read_bytes() == (PARENT/name).read_bytes(), name
    assert meta['storage_reserved_end'] == 0xE000 and meta['version_service_kind'] == 7
    assert sha((BUILD/'boot-status/asset.bin').read_bytes()) == meta['status_asset_sha256']
    return meta


def prepare(root):
    meta = build_audit()
    manifest = read(root/'prior-verified/manifest.json')
    state = read(root/'initial-state.json')
    assert manifest['board'] == BOARD and manifest['repeat_verified']
    assert (state['active_page'], state['inactive_page']) == (0xB0, 0xA0)
    banks = [(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i, data in enumerate(banks):
        assert data == (root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert sha(data) == manifest['banks'][i]['sha256']
    assert banks[3][0x3000:0x4000] == (ROOT/'BUILD/v2-beta25/str8n-v2-recovery-slot-b0.bin').read_bytes()
    original_build = battery.BUILD
    try:
        battery.BUILD = BUILD
        final, order = battery.plan(banks)
    finally:
        battery.BUILD = original_build
    final[3][0x2000:0x3000] = (BUILD/'str8n-v2-recovery-slot-a0.bin').read_bytes()
    order.append((3, 10))
    j = m.journal(banks[3])
    assert j
    cfg = bytearray(j[8:24])
    assert cfg[14:] == m.config_sum(cfg)
    cfg[7:13] = b'P\xA0'+(38).to_bytes(4, 'little')
    cfg[14:] = m.config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i], 'little') for i in range(32)]
    before = counts[:]
    for bank, sector in order:
        i = bank*8+sector-8
        assert counts[i] < 0xFFFFFF
        counts[i] += 1
    sequence = int.from_bytes(j[4:8], 'little')
    assert sequence < 0xFFFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, sequence+1)+b'\xff'*(4096-128)
    assert final[0] == banks[0]
    assert final[3][0x3000:0x4000] == banks[3][0x3000:0x4000]
    assert final[3][:0x2000] == banks[3][:0x2000]  # All identity/name/offset records.
    assert final[3][0x7000:] == banks[3][0x7000:]  # Fixed F unchanged.
    mf = read(BUILD/'migrator/manifest.json')
    assert mf['mixed_commit_values'] and len(order) <= mf['max_sectors']
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']], cells[mf['commit_after']] = len(order), 0
    expected = [bytearray(b) for b in banks]
    payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytearray(final[bank][offset:offset+4096])
        addresses = [0xB003] if (bank, sector) == (1, 11) else [0xA01F] if (bank, sector) == (3, 10) else []
        for address in addresses:
            data[address-0x8000-offset] = 0xFF
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        cells.update(dict(enumerate(row, mf['table']+9*i)))
        cells[mf['banks']+i] = bank
        cells[mf['commits']+i] = bank+1 if addresses else 0
        raw = b''.join(a.to_bytes(2, 'little') for a in addresses).ljust(4,b'\0')
        cells.update(dict(enumerate(raw, mf['commit_addresses']+4*i)))
        expected[bank][offset:offset+4096] = data
        for address in addresses:
            expected[bank][address-0x8000] = 0 if bank == 3 else 0x3F
        payloads.append(data)
    assert expected == final
    output = root/'upgrade'
    output.mkdir(exist_ok=False)
    installer = m.s19(cells, entry)
    (output/'installer.s19').write_bytes(installer)
    plan = dict(board=BOARD, version=meta['version'], generation=38,
        source=read(root/'source.json'),
        target_build=str(BUILD.relative_to(ROOT)), prior_directory='prior-verified',
        steps=[dict(bank=b, sector=s) for b,s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        template_manifest_sha256=sha((BUILD/'migrator/manifest.json').read_bytes()),
        config=cfg.hex(), counts_before=before, counts_after=counts,
        storage_update=True, commit_records=[dict(bank=1,address=0xB000)],
        monitor_commit=dict(bank=3,address=0xA01F,value=0),
        fallback_page=0xB0, fallback_version='2.0b25', fallback_sha256=sha(banks[3][0x3000:0x4000]),
        immutable_recovery_unchanged=True, physical_reset_required=True)
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payloads):
        (output/f'transfer-{i:02d}.bin').write_bytes(data)
    for i, data in enumerate(final):
        (output/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED beta26 A / retained beta25 B:',len(order),'sectors; both CLOCK and monitor commits withheld until verification')


def audit(root):
    meta = build_audit()
    plan = read(root/'upgrade/plan.json')
    assert plan['board'] == BOARD and plan['version'] == '2.0b26'
    assert sha((BUILD/'build.json').read_bytes()) == plan['build_sha256']
    assert sha((BUILD/'migrator/manifest.json').read_bytes()) == plan['template_manifest_sha256']
    model = read(root/'upgrade/model-check.json')
    assert model['passed'] and model['monitor_commit_verified_last'] and model['fallback_unchanged']
    mixed = read(root/'upgrade/beta26-test-results.json')
    assert mixed['passed'] and mixed['expected_hashes'] == plan['expected_hashes']
    assert mixed['artifacts'] == meta['artifacts']
    assert read(root/'retained/sram-prior/report.json')['repeat_verified']
    assert read(root/'retained/devices-before/report.json')['passed']
    return meta


def install(root):
    deploy.BUILD = BUILD
    deploy.audit = lambda: audit(root)
    deploy.install(root, BOARD)


def verify(root):
    from serial.tools.list_ports import comports
    from rtc_boards import SERIALS
    from rtc_prompt_sync import establish_b3
    from serial_test_coordination import serial_lease
    audit(root)
    plan = read(root/'upgrade/plan.json')
    pending_path = root/'upgrade/install/reset-pending.json'
    pending = read(pending_path)
    assert pending['device_sectors_verified']
    port = next(p.device for p in comports() if p.serial_number == SERIALS[BOARD])
    with serial_lease('beta26-reset-verify'), (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link = m.Link(port, log)
        try:
            print('ARMED: press physical RESET on 2609; receiving beta26 startup',flush=True)
            startup = link.until(b'\r\nB3> ',180)
            assert b'STR8-N 2.0b26' in startup and b'Battery age unknown' in startup, startup
            (root/'upgrade/boot.txt').write_bytes(startup)
            assert link.dump(0x7D30,0x7D30) == b'\xA0'
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}',prompt)
                actual = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(actual) == plan['expected_hashes'][bank], ('Post-reset mismatch',bank)
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(actual)
                print('PASS beta26 complete readback B'+str(bank),flush=True)
            link.command('B3')
            version = link.command('VERSION')
            assert b'STR8-N 2.0b26' in version and b'Running: MONITOR A, gen 00000026' in version,version
            assert b'MONITOR B gen 00000025 VALID' in version
            (root/'upgrade/version.txt').write_bytes(version)
            time = link.command('TIME')
            assert b'(-05:00)' in time
            (root/'upgrade/time.txt').write_bytes(time)
            clock = link.command('R CLOCK',b'CLOCK> ')
            assert b'CLOCK 1.8' in clock and b'Battery age unknown' in clock
            clock += link.command('BATTERY',b'CLOCK> ')
            assert b'Battery age unknown' in clock
            clock += link.command('STATUS',b'CLOCK> ')
            assert b'Running: yes' in clock and b'Backup enabled: yes' in clock
            assert b'80 0E ' in clock  # Preserve calibrated control and trim.
            clock += link.command('Q')
            (root/'upgrade/clock.txt').write_bytes(clock)
            wear = link.command('W')
            (root/'upgrade/wear.txt').write_bytes(wear)
            assert b'B3:A' in wear
            pending.update(physical_reset_pending=False, physical_reset_verified=True)
            pending_path.write_text(json.dumps(pending,indent=2)+'\n')
            report = dict(passed=True, board=BOARD, version='2.0b26', generation=38,
                physical_reset_verified=True, complete_flash_readback=True,
                expected_hashes=plan['expected_hashes'], active_slot='A', fallback_version='2.0b25',
                fallback_slot='B', version_time_clock_battery_wear_passed=True)
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS 2609 beta26 A, beta25 B fallback, VERSION/TIME/CLOCK/BATTERY/W and exact full flash',flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'audit', 'install', 'verify'))
    p.add_argument('--root', required=True, type=Path)
    args = p.parse_args()
    {'prepare':prepare, 'audit':audit, 'install':install, 'verify':verify}[args.stage](args.root.resolve())
