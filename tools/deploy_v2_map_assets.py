"""Install MAINT 2.1 firmware-asset map labels on board 2609 only."""
import argparse
import json
import beta4_migration as m
import update_v2_beta24 as deploy
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = deploy.ROOT
BUILD = ROOT/'BUILD/v2-map-assets'
BASE = ROOT/'BUILD/v2-version'
BOARD = '2609'
read, sha = deploy.read, deploy.sha


def audit():
    meta = read(BUILD/'build.json')
    mm = read(BUILD/'maint/manifest.json')
    assert meta['map_firmware_assets'] and mm['version'] == '2.1'
    for n, h in meta['artifacts'].items():
        assert sha((BUILD/n).read_bytes()) == h, n
    assert sha((BUILD/'maint/board-name.bin').read_bytes()) == mm['program_sha256']
    assert sha((BUILD/meta['maintenance_storage_file']).read_bytes()) == mm['storage_sha256']
    r = read(BUILD/'map-assets-test-results.json')
    assert r['passed'] and r['artifacts'] == meta['artifacts']
    assert r['maintenance_sha256'] == mm['program_sha256'] and r['storage_sha256'] == mm['storage_sha256']
    for n in ('clock/clock.bin', 'version/asset.bin', 'boot-status/asset.bin', 'local-display/asset.bin',
              'str8n-v2-recovery-e000-efff.bin', 'str8n-v2-recovery-f000-ffff.bin',
              'str8n-v2-recovery-slot-a0.bin', 'str8n-v2-recovery-slot-b0.bin'):
        assert (BUILD/n).read_bytes() == (BASE/n).read_bytes(), n
    return meta


def prepare(root):
    meta = audit()
    p = read(root/'prior-verified-2/manifest.json')
    assert p['board'] == BOARD and p['repeat_verified']
    banks = [(root/f'prior-verified-2/b{i}.bin').read_bytes() for i in range(4)]
    for i, b in enumerate(banks):
        assert len(b) == 32768 and b == (root/f'prior-verified-2/b{i}-repeat.bin').read_bytes()
        assert sha(b) == p['banks'][i]['sha256']
    oldmeta = read(BASE/'build.json')
    assert banks[1][:12288] == (BASE/oldmeta['maintenance_storage_file']).read_bytes()
    final = [bytearray(b) for b in banks]
    final[1][:12288] = (BUILD/meta['maintenance_storage_file']).read_bytes()
    order = [(3, 12), (1, 10), (1, 9), (1, 8)]
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
    assert final[0] == banks[0] and final[2] == banks[2]
    assert final[1][0x3000:] == banks[1][0x3000:]
    assert final[3][:0x4000] == banks[3][:0x4000] and final[3][0x5000:] == banks[3][0x5000:]
    mf = read(BUILD/'migrator/manifest.json')
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']], cells[mf['commit_after']] = len(order), 0
    expected = [bytearray(b) for b in banks]
    payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytearray(final[bank][offset:offset+4096])
        commit = (bank, sector) == (1, 8)
        if commit:
            data[3] = 0xFF
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        for a, v in enumerate(row, mf['table']+9*i):
            cells[a] = v
        cells[mf['banks']+i], cells[mf['commits']+i] = bank, 2 if commit else 0
        for slot in range(2):
            a = 0x8003 if commit and slot == 0 else 0
            cells[mf['commit_addresses']+4*i+2*slot] = a&255
            cells[mf['commit_addresses']+4*i+2*slot+1] = a>>8
        expected[bank][offset:offset+4096] = data
        if commit:
            expected[1][3] = 0x3F
        payloads.append(bytes(data))
    assert expected == final
    out = root/'upgrade'
    out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry)
    (out/'installer.s19').write_bytes(installer)
    plan = dict(board=BOARD, version=meta['version'], maintenance_version='2.1',
        prior_directory='prior-verified-2', steps=[dict(bank=b, sector=s) for b, s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        config=cfg.hex(), counts_before=before, counts_after=counts,
        storage_update=True, commit_records=[dict(bank=1, address=0x8000)],
        boot_clock_version_unchanged=True)
    (out/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payloads):
        (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for i, data in enumerate(final):
        (out/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED 2609 only: B1:8/9/A MAINT; B3:C wear; header commit last', flush=True)


def verify(root):
    from serial.tools.list_ports import comports
    info = read(root/'upgrade/plan.json')
    port = next(p.device for p in comports() if p.serial_number == SERIALS[BOARD])
    with serial_lease('map-assets-verify'), (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link = m.Link(port, log)
        try:
            establish_b3(link)
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000, 0x10000, 4096))
                assert sha(data) == info['expected_hashes'][bank], ('Readback mismatch', bank)
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS 2609 full readback B'+str(bank), flush=True)
            link.command('B3')
            for view in (1, 2, 3):
                text = link.command('M'+str(view))
                if view == 1:
                    assert b'B2 .  .  S  S  +  F  F  .' in text, text
                    assert b'F firmware assets' in text
                    print(text.decode('ascii'), flush=True)
                else:
                    assert b'Firmware status formatter C800-D1FF reserved' in text
                    assert b'Local/board E000-E6FF; VERSION E800-EFFF reserved' in text
                (root/f'upgrade/map-M{view}.txt').write_bytes(text)
            text = link.command('VERSION')
            assert b'Running: MONITOR B, gen 00000025' in text
            (root/'upgrade/version.txt').write_bytes(text)
            report = dict(passed=True, board=BOARD, maintenance_version='2.1',
                complete_flash_readback=True, all_map_views_verified=True,
                version_verified=True, physical_reset_confirmed_by_operator=True,
                expected_hashes=info['expected_hashes'])
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(report, indent=2)+'\n')
            p = root/'upgrade/install/reset-pending.json'
            pending = read(p)
            pending['physical_reset_pending'] = False
            p.write_text(json.dumps(pending, indent=2)+'\n')
        finally:
            link.serial.close()


if __name__ == '__main__':
    from pathlib import Path
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
