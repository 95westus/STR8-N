"""Backup-bound beta23 to beta24 deployment for 2604/2609."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import beta4_migration as m
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'BUILD/v2-board-name'
OLD = ROOT / 'BUILD/v2-compact-boot'
sha = lambda data: hashlib.sha256(data).hexdigest()
read = lambda path: json.loads(path.read_text())


def audit():
    meta = read(BUILD/'build.json')
    assert (meta['version'], meta['generation']) == ('2.0b24', 35 if meta.get('startup_fifo_drain') else 34 if meta.get('startup_keys') else 33)
    for name, digest in meta['artifacts'].items():
        assert sha((BUILD/name).read_bytes()) == digest, name
    for name in ('board-name-test-results.json', 'compact-boot-test-results.json',
                 'local-time-test-results.json', 'storage-transfer-test-results.json'):
        report = read(BUILD/name)
        assert report['passed'] and report['artifacts'] == meta['artifacts'], name
        if 'local_asset_sha256' in report:
            assert report['local_asset_sha256']==meta['local_asset_sha256'],name
    if 'STR8N-006' in meta.get('fixes',[]):
        report=read(BUILD/'board-name-power-fail-test-results.json')
        assert report['passed'] and report['local_asset_sha256']==meta['local_asset_sha256']
        assert report['artifacts']==meta['artifacts']
    if meta.get('startup_keys'):
        report=read(BUILD/'startup-keys-test-results.json')
        assert report['passed'] and report['artifacts']==meta['artifacts']
    if meta.get('startup_fifo_drain'):
        report=read(BUILD/'startup-fifo-test-results.json')
        assert report['passed'] and report['artifacts']==meta['artifacts']
    assert sha((BUILD/'boot-status/asset.bin').read_bytes()) == meta['status_asset_sha256']
    assert sha((BUILD/'local-display/asset.bin').read_bytes()) == meta['local_asset_sha256']
    return meta


def prepare(root, board):
    meta = audit()
    prior = read(root/'prior-verified/manifest.json')
    assert prior['repeat_verified'] and prior['board'] == board
    banks = [(root/f'prior-verified/b{i}.bin').read_bytes() for i in range(4)]
    for i, data in enumerate(banks):
        assert len(data) == 32768 and data == (root/f'prior-verified/b{i}-repeat.bin').read_bytes()
        assert sha(data) == prior['banks'][i]['sha256']
    regions = [(3, 0, 'str8n-rtc-component-8000-8fff.bin', 4096),
               (3, 0x1000, 'str8n-journal-9000-9fff.bin', 3072),
               (3, 0x2000, 'str8n-v2-recovery-slot-a0.bin', 4096),
               (3, 0x3000, 'str8n-v2-recovery-slot-b0.bin', 4096),
               (3, 0x6000, 'str8n-v2-recovery-e000-efff.bin', 4096),
               (3, 0x7000, 'str8n-v2-recovery-f000-ffff.bin', 4096),
               (2, 0x4800, 'boot-status/asset.bin', 2560),
               (2, 0x6000, 'local-display/asset.bin', 1536)]
    final = [bytearray(data) for data in banks]
    for bank, offset, name, size in regions:
        assert banks[bank][offset:offset+size] == (OLD/name).read_bytes()[:size], name
        data = (BUILD/name).read_bytes()
        size = len(data) if name == 'local-display/asset.bin' else size
        if name == 'local-display/asset.bin':
            assert size == 1792 and banks[bank][offset+1536:offset+size] == b'\xff'*256
        final[bank][offset:offset+size] = data[:size]
    for page, offset in ((0xA0, 0x2000), (0xB0, 0x3000)):
        assert m.slot_valid(banks[3][offset:offset+4096], page)
        assert int.from_bytes(banks[3][offset+8:offset+12], 'little') == 32
    oldmeta = read(OLD/'build.json')
    oldmaint = (OLD/oldmeta['maintenance_storage_file']).read_bytes()
    assert banks[1][:len(oldmaint)] == oldmaint
    maint = (BUILD/meta['maintenance_storage_file']).read_bytes()
    assert len(maint) == 12288 and banks[1][len(oldmaint):len(maint)] == b'\xff'*(len(maint)-len(oldmaint))
    final[1][:len(maint)] = maint
    assert (BUILD/'clock/clock.bin').read_bytes() == (OLD/'clock/clock.bin').read_bytes()
    order = [(3,12), (1,10), (1,9), (1,8), (2,13), (2,12), (2,14), (3,11), (3,10)]
    journal = m.journal(banks[3]); assert journal
    cfg = bytearray(journal[8:24]); assert cfg[14:] == m.config_sum(cfg)
    if cfg[7] == ord('P'): cfg[9:13] = (33).to_bytes(4,'little')
    cfg[14:] = m.config_sum(cfg)
    counts = [int.from_bytes(journal[24+3*i:27+3*i], 'little') for i in range(32)]
    before = counts[:]
    for bank, sector in order:
        idx = bank*8+sector-8; assert counts[idx] < 0xFFFFFF; counts[idx] += 1
    seq = int.from_bytes(journal[4:8], 'little'); assert seq < 0xFFFFFFFF
    final[3][0x4000:0x5000] = m.metadata(cfg, counts, seq+1)+b'\xff'*(4096-128)
    assert final[0] == banks[0] and final[1][0x3000:] == banks[1][0x3000:]
    assert final[3][:0x2000] == banks[3][:0x2000] and final[3][0x5000:] == banks[3][0x5000:]
    assert final[2][:0x4800] == banks[2][:0x4800]
    assert final[2][0x5200:0x6000] == banks[2][0x5200:0x6000] and final[2][0x6700:] == banks[2][0x6700:]
    mf = read(BUILD/'migrator/manifest.json')
    cells, entry = m.read_s19(BUILD/'migrator/rtc-migrator-2000.s19')
    cells[mf['count']] = len(order); cells[mf['commit_after']] = 0
    stage = [bytearray(data) for data in final]; stage[1][3] = 255
    expected = [bytearray(data) for data in banks]; payloads = []
    for i, (bank, sector) in enumerate(order):
        offset = (sector-8)*4096; data = bytes(stage[bank][offset:offset+4096])
        row = bytes((sector<<4,))+m.fnv(expected[bank]).to_bytes(4,'little')+m.fnv(data).to_bytes(4,'little')
        for pos, value in enumerate(row, mf['table']+9*i): cells[pos] = value
        cells[mf['banks']+i] = bank
        commit = (bank,sector) == (1,8); cells[mf['commits']+i] = 2 if commit else 0
        for slot in range(2):
            address = 0x8003 if commit and slot == 0 else 0
            cells[mf['commit_addresses']+4*i+2*slot] = address & 255
            cells[mf['commit_addresses']+4*i+2*slot+1] = address >> 8
        expected[bank][offset:offset+4096] = data
        if commit: expected[1][3] = 63
        payloads.append(data)
    assert expected == final
    out = root/'upgrade'; out.mkdir(exist_ok=False)
    installer = m.s19(cells, entry); (out/'installer.s19').write_bytes(installer)
    plan = dict(board=board, version='2.0b24', generation=33, source_generation=32, prior_directory='prior-verified',
                steps=[dict(bank=b,sector=s) for b,s in order], prior_hashes=[sha(b) for b in banks],
                expected_hashes=[sha(b) for b in final], installer_sha256=sha(installer),
                build_sha256=sha((BUILD/'build.json').read_bytes()), config=cfg.hex(),
                counts_before=before, counts_after=counts, storage_update=True,
                commit_records=[dict(bank=1,address=0x8000)], no_sram_format=True)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for i,data in enumerate(payloads): (out/f'transfer-{i:02d}.bin').write_bytes(data)
    for i,data in enumerate(final): (out/f'expected-b{i}.bin').write_bytes(data)
    print('PREPARED', board, 'nine sectors; recovery, records and settings preserved', flush=True)


def install(root, board):
    from serial.tools.list_ports import comports
    from qualify_v2_rtc_board import load
    audit()
    info = read(root/'upgrade/plan.json'); check = read(root/'upgrade/model-check.json')
    assert info['board'] == board and check['passed']
    assert check['stale_preimage_refused'] and check['corrupt_payload_refused']
    assert check['expected_hashes'] == info['expected_hashes']
    assert check['installer_sha256'] == info['installer_sha256']
    assert check['record_commits'] == [[r['bank'],r['address']] for r in info['commit_records']]
    assert sha((BUILD/'build.json').read_bytes()) == info['build_sha256']
    path = root/'upgrade/installer.s19'; assert sha(path.read_bytes()) == info['installer_sha256']
    mf = read(BUILD/'migrator/manifest.json'); cells,entry = m.read_s19(path)
    payloads = [(root/f'upgrade/transfer-{i:02d}.bin').read_bytes() for i in range(len(info['steps']))]
    for i,data in enumerate(payloads):
        assert len(data) == 4096 and m.fnv(data) == int.from_bytes(bytes(cells[mf['table']+9*i+5+j] for j in range(4)),'little')
    port = next(p.device for p in comports() if p.serial_number == SERIALS[board])
    with serial_lease('firmware-update'):
        out = root/'upgrade/install'; out.mkdir(exist_ok=False)
        with (out/'serial.jsonl').open('x') as log:
            link = m.Link(port,log)
            try:
                establish_b3(link)
                for bank in range(4):
                    prompt = f'\r\nB{bank}> '.encode(); link.command(f'B{bank}',prompt)
                    actual = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                    assert sha(actual) == info['prior_hashes'][bank], 'Stale backup; no install'
                    print('PASS',board,'fresh preimage B'+str(bank),flush=True)
                link.command('B3'); load(link,path)
                (out/'title.txt').write_bytes(link.command(f'G {entry:04X}',b'Y then Enter> '))
                link.send(b'Y\r')
                for i,(step,data) in enumerate(zip(info['steps'],payloads)):
                    link.until(f'SEND 4096 BYTES FOR B{step["bank"]}:{step["sector"]:X}\r\n'.encode(),90)
                    for offset in range(0,4096,64):
                        link.send(data[offset:offset+64]); time.sleep(.01)
                    print('TRANSFER',board,f'B{step["bank"]}:{step["sector"]:X}',flush=True)
                (out/'result.txt').write_bytes(link.until(info.get('completion_token','MIGRATION VERIFIED; PRESS PHYSICAL RESET').encode(),90))
                if info.get('returns_to_monitor'):
                    startup=link.until(b'\r\nB3> ',90)
                    assert ('STR8-N '+info['version']).encode() in startup,startup
                    (out/'return-boot.txt').write_bytes(startup)
                (out/'reset-pending.json').write_text(json.dumps(dict(board=board,port=port,version=info['version'],
                    device_sectors_verified=True,physical_reset_pending=info.get('physical_reset_required',True),software_reset_pending=bool(info.get('returns_to_monitor')),expected_hashes=info['expected_hashes']),indent=2)+'\n')
                print('PASS',board,info['version'],'migration verified; '+('J3 restart ready' if info.get('returns_to_monitor') else 'physical RESET required'),flush=True)
            finally: link.serial.close()


def verify(root, board):
    from serial.tools.list_ports import comports
    info = read(root/'upgrade/plan.json')
    pending = read(root/'upgrade/install/reset-pending.json')
    assert pending['device_sectors_verified'] and info['board'] == board
    port = next(p.device for p in comports() if p.serial_number == SERIALS[board])
    with serial_lease('firmware-update'):
        with (root/'upgrade/post-reset-serial.jsonl').open('a') as log:
            link = m.Link(port,log)
            try:
                # Receive-only while the RAM installer awaits physical RESET.
                boot = link.until(b'\r\nB3> ',180)
                assert b'STR8-N 2.0b24' in boot, boot
                (root/'upgrade/boot.txt').write_bytes(boot)
                establish_b3(link)
                for bank in range(4):
                    prompt = f'\r\nB{bank}> '.encode(); link.command(f'B{bank}',prompt)
                    actual = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                    assert sha(actual) == info['expected_hashes'][bank], f'Post-reset B{bank} mismatch'
                    (root/f'upgrade/post-reset-b{bank}.bin').write_bytes(actual)
                    print('PASS',board,'post-reset B'+str(bank),flush=True)
                link.command('B3')
                transcript = link.command('R MAINT',b'BM> ')
                assert b'2.0' in transcript, transcript
                transcript += link.command('NAME',b'BM> ')
                transcript += link.command('Q')
                (root/'upgrade/maint.txt').write_bytes(transcript)
                report = dict(passed=True,board=board,version='2.0b24',generation=33,
                              complete_flash_readback=True,maintenance_version='2.0',
                              physical_reset_verified=True,expected_hashes=info['expected_hashes'])
                (root/'upgrade/post-reset-report.json').write_text(json.dumps(report,indent=2)+'\n')
                pending['physical_reset_pending'] = False
                (root/'upgrade/install/reset-pending.json').write_text(json.dumps(pending,indent=2)+'\n')
                print('PASS',board,'beta24 boot, complete flash readback and MAINT 2.0 NAME query',flush=True)
            finally: link.serial.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--board',required=True,choices=('2604','2609'))
    p.add_argument('--stage',required=True,choices=('prepare','install','verify'))
    a = p.parse_args()
    dict(prepare=prepare,install=install,verify=verify)[a.stage](a.root,a.board)
