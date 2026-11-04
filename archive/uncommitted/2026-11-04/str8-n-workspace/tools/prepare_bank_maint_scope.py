"""Compose a bounded two-board BANK MAINT review. No port access or builds."""
import binascii
import json
import re
import sys
from pathlib import Path
import install_2512_native_utilities as d

t = d.t
sys.path.insert(0, str(t.REPO / 'tools'))
from native_journal_room import require_zero_erase_room

OUT = t.ROOT / 'output/qualification/BANK-MAINT-scope-20261031-r1'
TRIALS = {'2512': '2512-BANK-MAINT-RAM-20261031-r2',
          '2609': '2609-BANK-MAINT-RAM-20261031-r1'}
CAPTURES = {'2512': '2512-BANK-MAINT-target-20261031-r2',
            '2609': '2609-BANK-MAINT-target-20261031-r1'}


def pinned(folder, name):
    manifest = json.loads((folder / 'manifest.json').read_text())
    body = (folder / name).read_bytes()
    assert t.sha(body) == manifest['artifacts'][name]['sha256']
    return body


def run():
    freeze = json.loads((t.REPO / 'F_FREEZE.json').read_text())
    frozen = (t.REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert t.sha(frozen) == freeze['sha256']
    for name, digest in freeze['sources'].items():
        assert t.sha((t.REPO / name).read_bytes()) == digest
    # This adapter skips the frozen self-edit/BRK guard only, while SEI and
    # its own destination guard are already in force. No erase/account/verify
    # instruction is skipped. Bind the exact bytes, rather than assuming +13.
    worker_inc = (t.REPO / 'src/core/worker-image.inc').read_text()
    worker = bytes(int(x, 16) for x in re.findall(r'\$([0-9A-Fa-f]{2})(?![0-9A-Fa-f])', worker_inc))
    assert len(worker) >= 0x100
    assert worker[0xA5:0xB2] == bytes.fromhex('A5 F5 F0 06 A9 03 85 F6 38 60 78 00 FC')
    assert worker[0xB2:0xB4] == bytes.fromhex('A9 01')
    nb = t.ROOT / 'BUILD/native-apps-g1-maint-r1'
    sb = t.ROOT / 'BUILD/services-gB-maint-r1'
    maint = pinned(nb, 'BANK-MAINT-g00000001-flash.bin')
    rtc = pinned(nb, 'RTC-BASE1-B3-8000.bin')
    services = pinned(sb, 'STR8N-SERVICES-g0000000B-E.bin')
    bundle = pinned(sb, 'STR8N-SERVICES-g0000000B-B2-8000.bin')
    assert len(maint) == 12288 and binascii.crc_hqx(maint, 65535) == 0
    OUT.mkdir(exist_ok=False)
    (OUT / '.gitignore').write_text('*\n')
    result = dict(status='REVIEW_READY_NOT_APPROVED_NOT_INSTALLED', F_writes=0,
                  F_sha256=freeze['sha256'], power_cuts=0, excluded_boards=['2205', '2604'],
                  published_download_changes=0, firmware_builds_during_review=0,
                  worker_mutate_preamble_sha256=t.sha(worker[0xA5:0xB2]),
                  worker_mutate_body_address='78B2', boards={})
    for board, trial_name in TRIALS.items():
        trial = t.ROOT / 'output/qualification' / trial_name
        proof = json.loads((trial / 'report.json').read_text())
        assert proof['passed'] and proof['owner_RAM_restored'] and proof['owner_ZP_restored']
        capture = t.ROOT / 'output/qualification' / CAPTURES[board]
        cp = json.loads((capture / 'report.json').read_text())
        assert cp['passed'] and cp['port_released']
        before = {n: (trial / f'B{n}-before.bin').read_bytes() for n in (1, 2, 3)}
        sector9 = (capture / 'B0-9000-before.bin').read_bytes()
        assert t.sha(sector9) == cp['sha256'] and before[3][-4096:] == frozen
        marker = json.loads((t.ROOT / f'output/qualification/device-operations/{board}.json').read_text())
        for n, body in before.items():
            assert t.sha(body) == marker['current_physical_bank_sha256'][f'B{n}']
        after = {n: bytearray(body) for n, body in before.items()}
        after[1][:12288] = maint
        after[2][:12288] = bundle
        # STATUS lives outside the module/provider seals, inside bundle padding.
        for a, b in ((0x40, 0x100), (0x240, 0x300), (0x2C00, 0x3000)):
            after[2][a:b] = before[2][a:b]
        after[3][:4096] = rtc
        after[3][0x6000:0x7000] = services
        assert after[1][12288:] == before[1][12288:]
        assert after[2][8192:] == before[2][8192:], 'PROGRAM/CLOCK/FLASH/STATUS must stay exact'
        assert after[3][4096:0x6000] == before[3][4096:0x6000]
        assert after[3][0x7000:] == frozen
        for a, b in ((0x300, 0x1F00), (0x1F00, 0x2C00)):
            assert binascii.crc_hqx(after[2][a:b], 65535) == 0
        folder = OUT / board
        folder.mkdir()
        targets = []
        order = [(1, 0x80), (1, 0x90), (1, 0xA0), (2, 0x80), (2, 0x90), (3, 0xE0), (3, 0x80)]
        for bank, page in order:
            off = (page - 0x80) * 256
            old = before[bank][off:off + 4096]
            new = after[bank][off:off + 4096]
            assert old != new and len(new) == 4096
            name = f'B{bank}-{page:02X}00.bin'
            (folder / name).write_bytes(new)
            targets.append(dict(bank=bank, page=page, address=f'{page:02X}00', file=name,
                                before_sha256=t.sha(old), sha256=t.sha(new)))
        journal = t.classify_journal(before[3])
        assert journal['default'] == 'B'
        fixture_erases = 1 if cp['blank'] else 2
        assert fixture_erases == (1 if board == '2512' else 2)
        operations = len(targets) + fixture_erases
        room = require_zero_erase_room(before[3], operations)
        counts = journal['counts'].copy()
        for bank, page in order:
            counts[bank * 8 + (page - 0x80) // 16] += 1
        counts[1] += fixture_erases
        empty_metadata = [f'{off + 0x8000:04X}' for off in range(0x1C00, 0x2000, 32)
                          if before[3][off:off + 32] == b'\xff' * 32]
        assert len(empty_metadata) >= 2
        for n, body in before.items():
            (folder / f'B{n}-before.bin').write_bytes(body)
            (folder / f'B{n}-image-target.bin').write_bytes(after[n])
        (folder / 'B0-9000-before.bin').write_bytes(sector9)
        info = dict(board=board, targets=targets, image_erases=7,
                    fixture_sector='B0:9', fixture_erases=fixture_erases,
                    fixture_before_sha256=t.sha(sector9), fixture_blank=cp['blank'],
                    total_erases=operations, C_D_erases=0, F_writes=0,
                    counts_before=journal['counts'], counts_after=counts,
                    journal_room=room, sequence_before=journal['sequence'],
                    sequence_after=journal['sequence'] + operations,
                    records_before=journal['valid_records'], records_after=journal['valid_records'] + operations,
                    all_old_journal_records_retained_on_chip=True,
                    reserved_append_pages=room['ordinary_blank_pages'][:operations],
                    boot_policy=dict(default='B', generation='0000000C', enabled_mask=journal['enabled_mask'],
                                     entries=journal['entries'], unknown_mask=journal['unknown_mask']),
                    naming_appends=2, naming_slots=empty_metadata[:2],
                    final_board_name=board, local_offset='-05:00',
                    B1_replaced_record='HELLO0200' if board == '2512' else 'UCHESS',
                    B1_replaced_extent='B1:8000-AFFF; exact old 12KB archived on host',
                    B1_retained_extent='B1:B000-FFFF, including legacy CLOCK',
                    before_bank_sha256={f'B{n}': t.sha(b) for n, b in before.items()},
                    target_bank_sha256={f'B{n}': t.sha(b) for n, b in after.items()},
                    RAM_trial=str(trial / 'report.json'), target_capture=str(capture / 'report.json'),
                    positive_tests=['cold R MAINT/BM and Q', 'copy/compare RAM and flash',
                        '4KB read/patch/fill/CRC/write/verify', 'journaled erase and exact B0:9 restoration',
                        'NAME CLEAR then original name (two confirmed append-only BN rows)',
                        'TABLE/T and BOOT inspect', 'read-only BATCH through BM and back',
                        'CLOCK/FLASH/PROGRAM/APPS routes and STATUS retained',
                        'fresh owner RAM/ZP restoration and readback'],
                    no_writes=['B0 except exact B0:9 fixture', 'B1:B-F', 'B2:A-F', 'B3:9 except two BN rows',
                               'MON A/B', 'F', 'SRAM data/WORKSPACE', 'RTC time/trim/offset/PF/history'],
                    qualification_limits=['Legacy X flash/PROGRAM named transfer is not ported; use existing S/T/R workflow',
                                          'NAME changes the board name; no new per-sector naming format',
                                          'Old SR01 catalogue rows are not a promise of legacy execution ABI compatibility'])
        t.save(folder / 'plan.json', info)
        result['boards'][board] = info
    result['image_erases_total'] = 14
    result['fixture_erases_total'] = 3
    result['total_erases'] = 17
    result['naming_appends_total'] = 4
    t.save(OUT / 'review.json', result)
    print(json.dumps({b: {k: p[k] for k in ('total_erases', 'reserved_append_pages', 'sequence_after',
                           'records_after', 'naming_slots', 'counts_after')} for b, p in result['boards'].items()}, indent=2))


if __name__ == '__main__':
    run()
