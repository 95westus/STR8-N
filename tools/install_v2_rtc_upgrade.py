"""Execute an already modeled, backup-bound RTC upgrade on its exact board.

Writes only the modeled sectors after complete source readback and RAM installer
verification. No automatic retry or reset; the installer halts awaiting RESET.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from serial.tools.list_ports import comports
from beta4_migration import Link, read_s19, fnv
from qualify_v2_rtc_board import load

ROOT = Path(__file__).resolve().parents[1]
SERIALS = {'2512': 'A10MQFLCA', '2205': 'A10MPUPNA', '2609': 'A10MPQXCA'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--board', required=True, choices=tuple(SERIALS))
    parser.add_argument('--port', required=True)
    parser.add_argument('--build',type=Path,default=ROOT/'BUILD/v2-rtc-kernel')
    parser.add_argument('--check-only',action='store_true',help='Verify receipts and payloads without opening a board port')
    args = parser.parse_args()
    info = json.loads((args.root / 'upgrade/plan.json').read_text())
    check = json.loads((args.root / 'upgrade/model-check.json').read_text())
    kernel = json.loads((args.build/'kernel-test-results.json').read_text())
    assert kernel['passed'] and check['passed'] and info['board'] == args.board
    assert check.get('stale_preimage_refused') and check.get('corrupt_payload_refused')
    assert check['installer_sha256'] == info['installer_sha256']
    assert check['expected_hashes'] == info['expected_hashes']
    installer = args.root / 'upgrade/installer.s19'
    assert hashlib.sha256(installer.read_bytes()).hexdigest() == info['installer_sha256']
    if info.get('storage_update'):
        compact = info.get('compact_boot_update', False)
        candidate_name='compact-boot-candidate-check.json' if compact else ('spi-startup-candidate-check.json' if info.get('spi_startup_update') else ('local-time-candidate-check.json' if info.get('local_time_update') else 'storage-candidate-check.json'))
        candidate=json.loads((args.build/candidate_name).read_text())
        assert candidate['passed'] and candidate['artifacts']==kernel['artifacts']
        if compact or info.get('spi_startup_update'):
            assert hashlib.sha256((args.build/'build.json').read_bytes()).hexdigest()==candidate['build_sha256']==info['build_sha256']
            for name,digest in candidate['model_report_hashes'].items():
                report_path=args.build/name
                assert hashlib.sha256(report_path.read_bytes()).hexdigest()==digest,name
                assert json.loads(report_path.read_text())['passed'],name
        if compact:
            assert info['version']=='2.0b23' and info['generation']==32
            assert hashlib.sha256((args.build/candidate_name).read_bytes()).hexdigest()==info['candidate_audit_sha256']
            for name,digest in candidate['artifacts'].items():
                assert hashlib.sha256((args.build/name).read_bytes()).hexdigest()==digest,name
            for name,key in (('boot-status/asset.bin','status_asset_sha256'),('local-display/asset.bin','local_asset_sha256'),('clock/clock.bin','clock_sha256')):
                assert hashlib.sha256((args.build/name).read_bytes()).hexdigest()==candidate[key],name
            if args.board!='2512':assert json.loads((args.root/'sram-prior/report.json').read_text())['repeat_verified']
        assert set(map(tuple,check['record_commits']))=={(r['bank'],r['address']) for r in info['commit_records']}
        if info.get('local_time_update') and not compact:
            local=json.loads((args.build/'local-time-test-results.json').read_text())
            assert local['passed'] and local['artifacts']==kernel['artifacts']
            assert local['clock_sha256']==candidate['clock_sha256']==info['clock_sha256']
            assert local['local_asset_sha256']==candidate['local_asset_sha256']
        elif info.get('trim_display_update'):
            display=json.loads((args.build/'trim-display-test-results.json').read_text())
            assert display['passed'] and display['artifacts']==kernel['artifacts']
            assert display['status_asset_sha256']==candidate['status_asset_sha256']
        elif args.board!='2512':assert json.loads((args.root/'sram-prior/report.json').read_text())['repeat_verified']
    cells, entry = read_s19(installer)
    manifest = json.loads((args.build/'migrator/manifest.json').read_text())
    if info.get('banner_update'):
        banner = json.loads((args.build/'banner-test-results.json').read_text())
        assert banner['passed'] and banner['artifacts']==kernel['artifacts']
    if info.get('journal_helper_relocation'):
        for name in ('journal-test-results.json','spi-resident-test-results.json','weekday-test-results.json','quiet-return-test-results.json'):
            report=json.loads((args.build/name).read_text())
            assert report['passed'] and report['artifacts']==kernel['artifacts'],name
    if info.get('journal_update'):
        journal=json.loads((args.build/'journal-test-results.json').read_text())
        assert journal['passed'] and journal['artifacts']==kernel['artifacts']
        clock_build=Path(info.get('clock_build',ROOT/'BUILD/v2-clock-1.2'))
        clock=json.loads((clock_build/'test-results.json').read_text())
        assert clock['passed'] and clock['sha256']==info['clock_sha256']
        if info.get('binding_update'):
            candidate=json.loads((args.build/'candidate-check.json').read_text())
            assert candidate['passed'] and candidate['version']==info['version']
            reports=('trim-test-results.json','binding-clock-test-results.json','time-test-results.json') if info.get('trim_update') else ('binding-test-results.json','binding-clock-test-results.json','time-test-results.json')
            for name in reports:
                report=json.loads((args.build/name).read_text());assert report['passed'] and report['artifacts']==kernel['artifacts']
            if info.get('trim_update'):
                assert candidate['clock_sha256']==info['clock_sha256']
                assert json.loads((args.build/'trim-test-results.json').read_text())['clock_sha256']==info['clock_sha256']
            if info.get('spi_update'):
                spi=json.loads((args.build/'spi-resident-test-results.json').read_text())
                assert spi['passed'] and spi['artifacts']==kernel['artifacts']
    elif info.get('clock_update') and not info.get('local_time_update'):
        powerfail=json.loads((args.build/'powerfail-test-results.json').read_text())
        assert powerfail['passed'] and powerfail['clock_sha256']==info['clock_sha256']
        assert powerfail['kernel_artifacts']==kernel['artifacts']
    payloads = []
    for i, step in enumerate(info['steps']):
        data = (args.root / f'upgrade/transfer-{i:02d}.bin').read_bytes()
        expected = int.from_bytes(bytes(cells[manifest['table']+9*i+5+j] for j in range(4)), 'little')
        assert len(data) == 4096 and fnv(data) == expected
        payloads.append(data)
    if args.check_only:
        print('PASS',args.board,'installer/build/model/payload preflight; no board port opened')
        return
    port = next(p for p in comports() if p.device.upper() == args.port.upper())
    assert port.serial_number == SERIALS[args.board], (port.serial_number, SERIALS[args.board])
    run = args.root / 'upgrade/install'
    run.mkdir(exist_ok=False)
    with (run / 'serial.jsonl').open('x') as log:
        link = Link(args.port, log)
        try:
            stop = time.monotonic() + .3
            while time.monotonic() < stop:
                link.read(max(1, link.serial.in_waiting))
            initial=link.command('', b'> ')
            if b'CLOCK>' in initial or b'BM>' in initial:link.command('Q')
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                actual = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000,0x10000,4096))
                assert hashlib.sha256(actual).hexdigest() == info['prior_hashes'][bank], f'B{bank} changed: no install'
                print('PASS', args.board, 'current B'+str(bank)+' matches verified backup', flush=True)
            link.command('B3')
            load(link, installer)
            result = link.command(f'G {entry:04X}', b'Y then Enter> ')
            (run / 'title.txt').write_bytes(result)
            link.send(b'Y\r')
            for i, (step, data) in enumerate(zip(info['steps'], payloads)):
                token = f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode()
                link.until(token, 90)
                for offset in range(0, 4096, 64):
                    link.send(data[offset:offset+64])
                    time.sleep(.01)
                print('PASS', args.board, 'transfer', i+1, f'B{step["bank"]}:{step["sector"]:X}', flush=True)
            result = link.until(b'MIGRATION VERIFIED; PRESS PHYSICAL RESET', 90)
            (run / 'result.txt').write_bytes(result)
            (run / 'reset-pending.json').write_text(json.dumps(dict(board=args.board,port=args.port,
                device_sectors_verified=True, physical_reset_pending=True, expected_hashes=info['expected_hashes']),indent=2)+'\n')
            print(args.board, 'MIGRATION VERIFIED; PHYSICAL RESET REQUIRED', flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
