"""Install only CLOCK 1.7 on USB-identified board 2609 from exact backups."""
import argparse
import json
from pathlib import Path

import beta4_migration as m
import update_v2_beta24 as deploy
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = deploy.ROOT
BUILD = ROOT/'BUILD/v2-clock-summary'
BASE = ROOT/'BUILD/v2-boot-dialog'
BOARD = '2609'
read, sha = deploy.read, deploy.sha


def audit():
    meta = read(BUILD/'build.json')
    assert meta['clock_summary'] and meta['clock_version'] == '1.7'
    cm = read(BUILD/'clock/build.json')
    assert sha((BUILD/'clock/clock.bin').read_bytes()) == cm['sha256'] == meta['clock_sha256']
    assert sha((BUILD/'clock/storage.bin').read_bytes()) == meta['clock_storage_sha256']
    tests = read(BUILD/'clock-summary-test-results.json')
    assert tests['passed'] and tests['clock_sha256'] == meta['clock_sha256']
    assert tests['clock_storage_sha256'] == meta['clock_storage_sha256']
    for name, digest in meta['artifacts'].items():
        assert sha((BUILD/name).read_bytes()) == digest, name
        assert (BUILD/name).read_bytes() == (BASE/name).read_bytes(), name
    for name in ('boot-status/asset.bin', 'local-display/asset.bin'):
        assert (BUILD/name).read_bytes() == (BASE/name).read_bytes(), name
    return meta


def prepare(root):
    meta = audit()
    prior = 'prior-verified-2'
    manifest = read(root/prior/'manifest.json')
    assert manifest['board'] == BOARD and manifest['repeat_verified']
    banks = [(root/prior/f'b{i}.bin').read_bytes() for i in range(4)]
    for bank, data in enumerate(banks):
        assert len(data) == 32768 and data == (root/prior/f'b{bank}-repeat.bin').read_bytes()
        assert sha(data) == manifest['banks'][bank]['sha256']
    old = (BASE/'clock/clock.bin').read_bytes()
    expected_header = b'SR\x01\x3f\x00\x20'+len(old).to_bytes(2, 'little')+b'CLOCK'.ljust(16, b'\0')
    assert banks[1][0x3000:0x3018] == expected_header
    assert banks[1][0x3018:0x3018+len(old)] == old
    assert banks[1][0x3018+len(old):0x6000] == b'\xff'*(0x6000-0x3018-len(old))
    final = [bytearray(b) for b in banks]
    final[1][0x3000:0x6000] = (BUILD/'clock/storage.bin').read_bytes()
    order = [(3, 12), (1, 13), (1, 12), (1, 11)]
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
    assert final[0] == banks[0] and final[2] == banks[2]
    assert final[1][:0x3000] == banks[1][:0x3000] and final[1][0x6000:] == banks[1][0x6000:]
    assert final[3][:0x4000] == banks[3][:0x4000] and final[3][0x5000:] == banks[3][0x5000:]
    mf = read(BUILD/'migrator/manifest.json')
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']], cells[mf['commit_after']] = len(order), 0
    expected = [bytearray(b) for b in banks]
    payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096
        data = bytearray(final[bank][offset:offset+4096])
        commit = (bank, sector) == (1, 11)
        if commit:
            data[3] = 0xFF
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4, 'little')+m.fnv(data).to_bytes(4, 'little')
        for address, value in enumerate(row, mf['table']+9*i):
            cells[address] = value
        cells[mf['banks']+i], cells[mf['commits']+i] = bank, 2 if commit else 0
        for slot in range(2):
            address = 0xB003 if commit and slot == 0 else 0
            cells[mf['commit_addresses']+4*i+2*slot] = address & 255
            cells[mf['commit_addresses']+4*i+2*slot+1] = address >> 8
        expected[bank][offset:offset+4096] = data
        if commit:
            expected[1][0x3003] = 0x3F
        payloads.append(bytes(data))
    assert expected == final
    out = root/'upgrade'
    out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry)
    (out/'installer.s19').write_bytes(installer)
    plan = dict(board=BOARD, version=meta['version'], clock_version='1.7',
        prior_directory=prior, steps=[dict(bank=b, sector=s) for b, s in order],
        prior_hashes=[sha(b) for b in banks], expected_hashes=[sha(b) for b in final],
        installer_sha256=sha(installer), build_sha256=sha((BUILD/'build.json').read_bytes()),
        storage_update=True, commit_records=[dict(bank=1, address=0xB000)],
        config=cfg.hex(), counts_before=before, counts_after=counts,
        recovery_and_boot_dialog_unchanged=True, no_sram_format=True)
    (out/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for i, data in enumerate(payloads):
        (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for bank, data in enumerate(final):
        (out/f'expected-b{bank}.bin').write_bytes(data)
    print('PREPARED 2609 only: B1:B/C/D CLOCK, B3:C wear; SR commit last', flush=True)


def verify(root):
    from serial.tools.list_ports import comports
    info = read(root/'upgrade/plan.json')
    port = next(p.device for p in comports() if p.serial_number == SERIALS[BOARD])
    with serial_lease('clock-summary-verify'), (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
        link = m.Link(port, log)
        try:
            establish_b3(link)
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000, 0x10000, 4096))
                assert sha(data) == info['expected_hashes'][bank], ('Post-reset mismatch', bank)
                (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(data)
                print('PASS 2609 full readback B'+str(bank), flush=True)
            link.command('B3')
            text = link.command('R CLOCK', b'CLOCK> ')
            assert b'CLOCK 1.7\r\nBoard: 2609' in text, text
            assert b'Local: ' in text and b'UTC:   ' in text and b'Offset: ' in text
            assert b'RTCC: Running | Calendar valid | Backup enabled' in text
            assert b'TIME  STATUS  HISTORY  HELP  Q' in text
            (root/'upgrade/clock-summary.txt').write_bytes(text)
            for command, wanted in (('HELP', b'Read-only queries'), ('TIME', b'UTC:   '),
                                     ('STATUS', b'RTC registers (raw):'), ('HISTORY', b'UTC slot ')):
                result = link.command(command, b'CLOCK> ')
                if command == 'HISTORY':
                    assert wanted in result or b'No saved event' in result, result
                else:
                    assert wanted in result, result
                (root/('upgrade/clock-'+command.lower()+'.txt')).write_bytes(result)
            link.command('Q')
            report = dict(passed=True, board=BOARD, clock_version='1.7',
                complete_flash_readback=True, clock_summary_verified=True,
                physical_reset_confirmed_by_operator=True, expected_hashes=info['expected_hashes'])
            (root/'upgrade/post-reset-report.json').write_text(json.dumps(report, indent=2)+'\n')
            pending_path = root/'upgrade/install/reset-pending.json'
            pending = read(pending_path)
            pending['physical_reset_pending'] = False
            pending_path.write_text(json.dumps(pending, indent=2)+'\n')
            print(text.decode('ascii'), flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'install', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    if args.stage == 'prepare':
        prepare(args.root)
    elif args.stage == 'install':
        deploy.BUILD, deploy.audit = BUILD, audit
        deploy.install(args.root, BOARD)
    else:
        verify(args.root)
