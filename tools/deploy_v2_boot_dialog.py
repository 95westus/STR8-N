"""Backup-bound 2609 display update, using the tested RAM migrator."""
import argparse
import json
from pathlib import Path

import beta4_migration as m
import update_v2_beta24 as deploy
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = deploy.ROOT
BUILD = ROOT / 'BUILD/v2-boot-dialog'
OLD = ROOT / 'BUILD/v2-beta25'
BOARD = '2609'
read, sha = deploy.read, deploy.sha


def audit():
    meta = read(BUILD/'build.json')
    assert meta['boot_dialog_order'] and meta['power_fail_timezone'] == 'UTC'
    for name, digest in meta['artifacts'].items():
        assert sha((BUILD/name).read_bytes()) == digest, name
    for name in ('boot-dialog', 'compact-boot', 'time-local'):
        receipt = read(BUILD/(name+'-test-results.json'))
        assert receipt['passed'] and receipt['artifacts'] == meta['artifacts']
        for field in ('local_asset_sha256', 'status_asset_sha256'):
            assert receipt[field] == meta[field]
    for field, name in (('local_asset_sha256', 'local-display/asset.bin'),
                        ('status_asset_sha256', 'boot-status/asset.bin')):
        assert sha((BUILD/name).read_bytes()) == meta[field]
    return meta


def prepare(root, prior):
    meta = audit()
    manifest = read(root/prior/'manifest.json')
    assert manifest['repeat_verified'] and manifest['board'] == BOARD
    banks = [(root/prior/f'b{i}.bin').read_bytes() for i in range(4)]
    for i, data in enumerate(banks):
        assert len(data) == 32768 and data == (root/prior/f'b{i}-repeat.bin').read_bytes()
        assert sha(data) == manifest['banks'][i]['sha256']
    final = [bytearray(b) for b in banks]
    for bank, offset, name in ((2, 0x4800, 'boot-status/asset.bin'),
                               (2, 0x6000, 'local-display/asset.bin'),
                               (3, 0, 'str8n-rtc-component-8000-8fff.bin')):
        before, after = (OLD/name).read_bytes(), (BUILD/name).read_bytes()
        assert len(before) == len(after)
        assert banks[bank][offset:offset+len(before)] == before, ('Unexpected installed asset', name)
        final[bank][offset:offset+len(after)] = after
    order = [(3, 12), (2, 12), (2, 13), (2, 14), (3, 8)]
    journal = m.journal(banks[3])
    assert journal
    cfg = bytearray(journal[8:24])
    assert cfg[14:] == m.config_sum(cfg)
    counts = [int.from_bytes(journal[24+3*i:27+3*i], 'little') for i in range(32)]
    before = counts[:]
    for bank, sector in order:
        index = bank*8+sector-8
        assert counts[index] < 0xFFFFFF
        counts[index] += 1
    seq = int.from_bytes(journal[4:8], 'little')
    assert seq < 0xFFFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, seq+1)+b'\xff'*(4096-128)
    assert final[0] == banks[0] and final[1] == banks[1]
    assert final[3][0x1000:0x4000] == banks[3][0x1000:0x4000]
    assert final[3][0x5000:] == banks[3][0x5000:]
    mf = read(BUILD/'migrator/manifest.json')
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']] = len(order)
    cells[mf['commit_after']] = 0
    expected = [bytearray(b) for b in banks]
    payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytes(final[bank][offset:offset+4096])
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        for address, value in enumerate(row, mf['table']+9*i):
            cells[address] = value
        cells[mf['banks']+i] = bank
        cells[mf['commits']+i] = 0
        for address in range(mf['commit_addresses']+4*i, mf['commit_addresses']+4*i+4):
            cells[address] = 0
        expected[bank][offset:offset+4096] = data
        payloads.append(data)
    assert expected == final
    out = root/'upgrade'
    out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry)
    (out/'installer.s19').write_bytes(installer)
    plan = dict(board=BOARD, version=meta['version'], generation=meta['generation'],
        prior_directory=prior, steps=[dict(bank=b, sector=s) for b, s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        storage_update=True, commit_records=[], config=cfg.hex(),
        counts_before=before, counts_after=counts, monitor_slots_unchanged=True,
        recovery_unchanged=True, rtc_administration_unchanged=True)
    (out/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payloads):
        (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for i, data in enumerate(final):
        (out/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED 2609: B2:C/D/E assets, B3:8 banner, B3:C wear journal', flush=True)


def verify(root):
    from serial.tools.list_ports import comports
    plan = read(root/'upgrade/plan.json')
    port = next(p.device for p in comports() if p.serial_number == SERIALS[BOARD])
    with serial_lease('boot-dialog-verify'), (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link = m.Link(port, log)
        try:
            establish_b3(link)
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000, 0x10000, 4096))
                assert sha(data) == plan['expected_hashes'][bank], ('Post-reset mismatch', bank)
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS 2609 complete readback B'+str(bank), flush=True)
            link.command('B3')
            boot = link.command('J3')
            (root/'upgrade/boot.txt').write_bytes(boot)
            assert b'Board: 2609\r\n\r\nRAM ' in boot, boot
            assert boot.index(b'RAM ') < boot.index(b'EDU ON') < boot.index(b'SSRAM:') < boot.index(b'RTCC:')
            assert boot.endswith(b'\r\n\r\nB3> '), boot
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(dict(
                passed=True, board=BOARD, complete_flash_readback=True,
                boot_dialog_verified=True, physical_reset_confirmed_by_operator=True,
                expected_hashes=plan['expected_hashes']), indent=2)+'\n')
            pending_path = root/'upgrade/install/reset-pending.json'
            pending = read(pending_path)
            pending['physical_reset_pending'] = False
            pending_path.write_text(json.dumps(pending, indent=2)+'\n')
            print(boot.decode('ascii'), flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'install', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prior', default='prior-verified-3')
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare(args.root, args.prior)
    elif args.stage == 'install':
        deploy.BUILD, deploy.audit = BUILD, audit
        deploy.install(args.root, BOARD)
    else:
        verify(args.root)
