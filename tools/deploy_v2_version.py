"""Backup-bound VERSION install and physical A/B verification on 2609 only."""
import argparse
import json
from pathlib import Path
import beta4_migration as m
import update_v2_beta24 as deploy
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = deploy.ROOT
BUILD = ROOT/'BUILD/v2-version'
BASE = ROOT/'BUILD/v2-clock-summary'
BOARD = '2609'
read, sha = deploy.read, deploy.sha


def audit():
    meta = read(BUILD/'build.json')
    assert meta['version_command']
    for n, h in meta['artifacts'].items():
        assert sha((BUILD/n).read_bytes()) == h, n
    assert sha((BUILD/'version/asset.bin').read_bytes()) == meta['version_asset_sha256']
    for name in ('version', 'boot-dialog', 'clock-summary'):
        r = read(BUILD/(name+'-test-results.json'))
        assert r['passed'] and r['artifacts'] == meta['artifacts'], name
    assert read(BUILD/'version-test-results.json')['version_asset_sha256'] == meta['version_asset_sha256']
    for n in ('clock/clock.bin', 'boot-status/asset.bin', 'local-display/asset.bin',
              'str8n-v2-recovery-f000-ffff.bin', 'str8n-v2-recovery-slot-a0.bin', 'str8n-v2-recovery-slot-b0.bin'):
        assert (BUILD/n).read_bytes() == (BASE/n).read_bytes(), n
    return meta


def prepare(root):
    meta = audit()
    p = read(root/'prior-verified/manifest.json')
    assert p['board'] == BOARD and p['repeat_verified']
    banks = [(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i, b in enumerate(banks):
        assert len(b) == 32768 and b == (root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert sha(b) == p['banks'][i]['sha256']
    assert banks[3][0x6000:0x7000] == (BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    assert banks[2][0x6000:0x6700] == (BASE/'local-display/asset.bin').read_bytes()
    assert banks[2][0x6800:0x7000] == b'\xff'*2048, 'Reserved VERSION allocation is occupied'
    final = [bytearray(b) for b in banks]
    final[2][0x6800:0x7000] = (BUILD/'version/asset.bin').read_bytes()
    final[3][0x6000:0x7000] = (BUILD/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    order = [(3, 12), (2, 14), (3, 14)]
    j = m.journal(banks[3])
    assert j
    cfg = bytearray(j[8:24])
    assert cfg[14:] == m.config_sum(cfg)
    counts = [int.from_bytes(j[24+3*i:27+3*i], 'little') for i in range(32)]
    before = counts[:]
    for bank, sector in order:
        i = bank*8+sector-8
        assert counts[i] < 0xFFFFFF
        counts[i] += 1
    seq = int.from_bytes(j[4:8], 'little')
    assert seq < 0xFFFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, seq+1)+b'\xff'*(4096-128)
    assert final[0] == banks[0] and final[1] == banks[1]
    assert final[2][:0x6800] == banks[2][:0x6800] and final[2][0x7000:] == banks[2][0x7000:]
    assert final[3][:0x4000] == banks[3][:0x4000] and final[3][0x7000:] == banks[3][0x7000:]
    mf = read(BUILD/'migrator/manifest.json')
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']], cells[mf['commit_after']] = len(order), 0
    expected = [bytearray(b) for b in banks]
    payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytes(final[bank][offset:offset+4096])
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        for a, v in enumerate(row, mf['table']+9*i):
            cells[a] = v
        cells[mf['banks']+i], cells[mf['commits']+i] = bank, 0
        for a in range(mf['commit_addresses']+4*i, mf['commit_addresses']+4*i+4):
            cells[a] = 0
        expected[bank][offset:offset+4096] = data
        payloads.append(data)
    assert expected == final
    out = root/'upgrade'
    out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry)
    (out/'installer.s19').write_bytes(installer)
    plan = dict(board=BOARD, version=meta['version'], generation=meta['generation'],
        prior_directory='prior-verified', steps=[dict(bank=b, sector=s) for b, s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        config=cfg.hex(), counts_before=before, counts_after=counts,
        storage_update=True, commit_records=[], monitor_slots_unchanged=True,
        immutable_recovery_unchanged=True, clock_unchanged=True)
    (out/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payloads):
        (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for bank, data in enumerate(final):
        (out/f'expected-b{bank}.bin').write_bytes(data)
    print('PREPARED 2609 only: B3:C wear, B2:E VERSION asset, B3:E shared loader', flush=True)


def verify(root):
    from serial.tools.list_ports import comports
    info = read(root/'upgrade/plan.json')
    port = next(p.device for p in comports() if p.serial_number == SERIALS[BOARD])
    with serial_lease('version-verify'), (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link = m.Link(port, log)
        try:
            establish_b3(link)
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000, 0x10000, 4096))
                assert sha(data) == info['expected_hashes'][bank], ('Readback mismatch', bank)
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS 2609 complete readback B'+str(bank), flush=True)
            link.command('B3')
            def version(label, firmware, running):
                text = link.command('VERSION')
                assert firmware in text and running in text, text
                assert b'Board: 2609' in text and b'MONITOR A gen 00000023 VALID' in text
                assert b'MONITOR B gen 00000025 VALID default' in text, text
                (root/('upgrade/version-'+label+'.txt')).write_bytes(text)
                print(text.decode('ascii'), flush=True)
            version('B', b'STR8-N 2.0b25 B3 65C816', b'Running: MONITOR B, gen 00000025')
            startup = link.command('J3', b'Enter default [3s]: ')
            link.send(b'A')
            startup += link.until(b'\r\nB3> ')
            (root/'upgrade/manual-A-boot.txt').write_bytes(startup)
            version('A', b'STR8-N 2.0b24 B3 65C816', b'Running: MONITOR A, gen 00000023')
            (root/'upgrade/default-B-boot.txt').write_bytes(link.command('J3'))
            version('B-restored', b'STR8-N 2.0b25 B3 65C816', b'Running: MONITOR B, gen 00000025')
            text = link.command('TIME')
            assert b'(-05:00)' in text, text
            (root/'upgrade/time.txt').write_bytes(text)
            text = link.command('R CLOCK', b'CLOCK> ')
            assert b'CLOCK 1.7' in text and b'Board: 2609' in text
            (root/'upgrade/clock.txt').write_bytes(text)
            link.command('Q')
            report = dict(passed=True, board=BOARD, complete_flash_readback=True,
                version_A_and_B_verified=True, running_distinct_from_default=True,
                physical_reset_confirmed_by_operator=True, clock_and_time_verified=True,
                expected_hashes=info['expected_hashes'])
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(report, indent=2)+'\n')
            p = root/'upgrade/install/reset-pending.json'
            pending = read(p)
            pending['physical_reset_pending'] = False
            p.write_text(json.dumps(pending, indent=2)+'\n')
        finally:
            link.serial.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'install', 'verify'))
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    if a.stage == 'prepare':
        prepare(a.root)
    elif a.stage == 'install':
        deploy.BUILD, deploy.audit = BUILD, audit
        deploy.install(a.root, BOARD)
    else:
        verify(a.root)
