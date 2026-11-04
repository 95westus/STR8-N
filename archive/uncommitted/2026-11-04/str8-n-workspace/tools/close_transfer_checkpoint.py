"""Audit existing transfer receipts without importing drivers or opening ports."""
import binascii
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
Q = ROOT / 'output/qualification'
SCOPE = Q / 'TRANSFER-scope-20261101-r2'
sha = lambda data: hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run():
    approval = read(SCOPE / 'approval.json')
    assert approval['approved']
    assert sha((SCOPE / 'review.json').read_bytes()) == approval['review_sha256']
    for board, digest in approval['plan_sha256'].items():
        assert sha((SCOPE / board / 'plan.json').read_bytes()) == digest
    freeze = read(REPO / 'F_FREEZE.json')
    f = (REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f) == 4096 and sha(f) == freeze['sha256']
    for name, digest in freeze['sources'].items():
        assert sha((REPO / name).read_bytes()) == digest, name

    install = Q / '2512-transfer-installed-20261101-r3'
    trial = Q / '2512-transfer-PROGRAM-positive-20261101-r1'
    ir, tr = read(install / 'report.json'), read(trial / 'report.json')
    plan = read(SCOPE / '2512/plan.json')
    for folder, report in ((install, ir), (trial, tr)):
        assert report['passed'] and report['owner_RAM_restored'] and report['owner_ZP_restored']
        assert report['port_released'] and report['F_writes'] == report['power_cuts'] == report['resets'] == 0
        assert sha((folder / 'owner-ram.bin').read_bytes()) == report['RAM_sha256']
        assert sha((folder / 'owner-zp.bin').read_bytes()) == report['ZP_sha256']
    assert ir['completed'] == [target['address'] for target in plan['targets']]
    assert ir['image_erases_requested'] == 4 and plan['journal_erases'] == 0
    assert ir['final_journal']['sequence'] == plan['sequence_after'] == 1120
    assert ir['final_journal']['counts'] == plan['counts_after']
    assert ir['final_journal']['valid_records'] == plan['records_after'] == 27
    assert (install / 'SPI-metadata-before.bin').read_bytes() == (install / 'SPI-metadata-after.bin').read_bytes()
    for target in plan['targets']:
        name = f"B{target['bank']}-{target['page']:02X}-after.bin"
        assert sha((install / name).read_bytes()) == target['sha256']
    old3 = (install / 'B3-before.bin').read_bytes()
    new3 = (install / 'B3-after.bin').read_bytes()
    assert sha(old3) == plan['before_bank_sha256']['B3']
    assert sha(new3) == plan['target_bank_sha256']['B3']
    assert old3[-4096:] == new3[-4096:] == f
    old_rows = 0
    for offset in range(0x4000, 0x6000, 256):
        page = old3[offset:offset+256]
        if page != b'\xff' * 256:
            assert page == new3[offset:offset+256]
            old_rows += 1
    assert old_rows == plan['old_rows_retained'] == 23
    assert tr['B3_unchanged'] and (trial / 'B3-before.bin').read_bytes() == new3
    assert tr['SPI_restored'] and not tr['SPI_restore_pending']
    assert tr['temporary_SPI_bytes'] == 8256 and len(tr['checks']) == 7
    assert all(tr[key] == 0 for key in ('flash_writes', 'journal_writes', 'WORKSPACE_writes', 'RTC_SET', 'trim_writes', 'PF_ACK'))
    payload = (trial / 'SPI-payload-after.bin').read_bytes()
    row = (trial / 'SPI-record-after.bin').read_bytes()
    assert len(payload) == 8192 and payload == (trial / 'owner-ram.bin').read_bytes()[0x4500:]
    assert row[:4] == b'SP\x01\0' and row[63] == 0xA5
    assert binascii.crc_hqx(row[:62], 65535) == 0
    assert int.from_bytes(row[12:14], 'little') == binascii.crc_hqx(payload, 65535)

    # Independently recheck the final CRC-framed SPI reads, including cleanup.
    rx = b''.join(bytes.fromhex(v['hex']) for line in (trial / 'serial.jsonl').read_text().splitlines()
                  if (v := json.loads(line))['direction'] == 'RX')
    last = {}
    for text in re.findall(rb'D([0-9A-F]{138})\r?\n', rx):
        frame = bytes.fromhex(text.decode())
        assert binascii.crc_hqx(frame[:-2], 65535) == int.from_bytes(frame[-2:], 'big')
        last[int.from_bytes(frame[:3], 'big')] = frame[3:-2]
    allowed = [0x140] + list(range(0x9800, 0xB800, 64))
    assert b''.join(last[a] for a in allowed) == (trial / 'SPI-test-window-before.bin').read_bytes()
    assert b''.join(last[a] for a in range(0, 0x240, 64)) == (trial / 'SPI-primary-directory-before.bin').read_bytes()
    assert last[0x10000] == (trial / 'SPI-WORK-header-before.bin').read_bytes()
    holds = read(Q / 'rtc-hourly-schedule.json')['owner_blocked_boards']
    assert '2609' in holds

    out = Q / 'TRANSFER-checkpoint-20261101-r1'
    out.mkdir(exist_ok=False)
    (out / '.gitignore').write_text('*\n')
    report = dict(
        checkpoint_passed=True, both_boards_closed=False,
        hardware_access=False, F_sha256=sha(f), frozen_sources_unchanged=True,
        image_erases_consumed=4, journal_appends=4, journal_erases=0, F_writes=0,
        board_2512=dict(installed=True, integrated_S19=True, large_PROGRAM_Store_Restore=True,
            sequence=1120, old_journal_rows_retained=23, journal_rows=27,
            counts_C_D_E_F=plan['counts_after'][28:32], exact_SPI_restore_bytes=8256,
            final_SPI_readback_reaudited=True, owner_RAM_ZP_restored=True,
            B1_B2_evidence=ir['B1_B2_evidence']),
        board_2609=dict(installed=False, owner_held=True, remaining_approved_image_erases=4,
            requires_new_owner_recovery_instruction=True, hold=holds['2609']),
        evidence={str(folder.relative_to(ROOT)): sha((folder / 'report.json').read_bytes())
                  for folder in (install, trial)},
        published_downloads_changed=False,
        open=['2609 recovery and deferred installation', 'Dense flash S19 intake',
              'Large flash STORE', 'Live factory restoration', 'Extracted full-environment kit'])
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS 2512 transfer checkpoint: exact scope/history/F/8256-byte cleanup; 2609 remains owner-held')


if __name__ == '__main__':
    run()
