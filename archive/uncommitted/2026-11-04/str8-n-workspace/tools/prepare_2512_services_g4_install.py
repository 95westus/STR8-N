"""Prepare exact 2512 tools/C-rotation postimages from a fresh RAM trial.

No serial imports, board access, flash operations, builds or CPU simulation.
The existing native journal forecast calculates the reviewed byte changes.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'migration-host')]
from journal_rotation_plan import reserve
from native_journal_room import inspect as journal_room
from nf_migrate import classify_journal, valid_snapshot

sha = lambda body: hashlib.sha256(body).hexdigest()
save = lambda path, data: path.write_text(json.dumps(data, indent=2) + '\n')


def prepare(capture, out):
    capture, out = capture.resolve(), out.resolve()
    assert out.is_relative_to(ROOT / 'output/qualification') and not out.exists()
    report = json.loads((capture / 'report.json').read_text())
    assert report['passed'] and report['board'] == '2512' and report['CPU'] == '65C02'
    assert report['all_flash_banks_unchanged'] and report['all_131072_SRAM_bytes_unchanged']
    assert report['owner_RAM_restored'] and report['COM4_released']
    banks = [(capture / f'before-pass1-B{n}.bin').read_bytes() for n in range(4)]
    for n, body in enumerate(banks):
        assert body == (capture / f'before-pass2-B{n}.bin').read_bytes()
        assert body == (capture / f'after-pass1-B{n}.bin').read_bytes()
        assert body == (capture / f'after-pass2-B{n}.bin').read_bytes()
    before = classify_journal(banks[3])
    room = journal_room(banks[3])
    assert before['sequence'] == 1028 and before['valid_records'] == 31
    assert room['latest_page'] == 'DE00' and room['ordinary_blank_pages'] == []
    assert not room['peer_blank'] and room['reserved_intent_page'] == 'DF00'
    source = REPO / 'monitors/candidates/services-g00000004'
    manifest = json.loads((source / 'manifest.json').read_text())
    def artifact(variant):
        name, item = next((n, i) for n, i in manifest['artifacts'].items() if i['variant'] == variant)
        body = (source / name).read_bytes()
        assert len(body) == item['bytes'] and sha(body) == item['sha256']
        return body
    bundle, dispatcher = artifact('B2 bundle'), artifact('E')
    assert len(bundle) == 12288 and len(dispatcher) == 4096
    assert sha(banks[3][-4096:]) == manifest['F_sha256']
    targets = [(2, 0x8000, bundle[:4096]), (2, 0x9000, bundle[4096:8192]),
               (2, 0xa000, bundle[8192:]), (3, 0xe000, dispatcher)]
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    expected = list(banks)
    steps = []
    for bank, address, target in targets:
        label = f'B{bank}-{address:04X}'
        original = banks[bank][address - 0x8000:address - 0x7000]
        assert target != original, 'Do not reserve an erase for an identical image'
        index = bank * 8 + address // 4096 - 8
        before_hashes = list(map(sha, expected))
        expected[3], journal = reserve(expected[3], index)
        changed = bytearray(expected[bank])
        changed[address - 0x8000:address - 0x7000] = target
        expected[bank] = bytes(changed)
        (out / f'{label}-original.bin').write_bytes(original)
        (out / f'{label}-target.bin').write_bytes(target)
        for n, body in enumerate(expected):
            (out / f'{label}-expected-B{n}.bin').write_bytes(body)
        steps.append(dict(target=f'B{bank}:{address:04X}', bank=bank, page=address >> 8,
                          counter_index=index, original_sha256=sha(original), target_sha256=sha(target),
                          journal=journal, before_bank_sha256=before_hashes,
                          after_bank_sha256=list(map(sha, expected))))
    final = classify_journal(expected[3])
    assert final['sequence'] == 1033 and final['valid_records'] == 20
    assert final['default'] == before['default'] == 'B'
    for key in ('enabled_mask', 'entries', 'unknown_mask'):
        assert final[key] == before[key]
    assert final['counts'][28:32] == [53, 33, 28, 24]
    assert final['counts'][16:19] == [596, 265, 13]
    assert final['counts'][26:28] == [41, 48]
    assert expected[0] == banks[0] and expected[1] == banks[1]
    assert expected[2][0x3000:] == banks[2][0x3000:]
    assert expected[3][:0x4000] == banks[3][:0x4000]
    assert expected[3][0x5000:0x5f00] == banks[3][0x5000:0x5f00]
    assert expected[3][0x7000:] == banks[3][0x7000:]
    old_row, new_row = banks[3][0x5e00:0x5f00], expected[3][0x4300:0x4400]
    permitted = set(range(8, 12)) | {30, 31, 252, 253} | set(range(64, 160))
    assert all(old_row[i] == new_row[i] for i in range(256) if i not in permitted)
    old_c, old_d = banks[3][0x4000:0x5000], banks[3][0x5000:0x6000]
    assert sum(valid_snapshot(old_c[i:i + 256]) for i in range(0, 4096, 256)) == 16
    (out / 'original-C-4096.bin').write_bytes(old_c)
    (out / 'original-D-4096.bin').write_bytes(old_d)
    for n, body in enumerate(expected):
        (out / f'final-expected-B{n}.bin').write_bytes(body)
    plan = dict(schema=1, status='PREPARED_NOT_AUTHORIZED', board='2512', port='COM4',
                usb_serial='A10MQFLCA', CPU='65C02', source_capture=str(capture),
                source_report_sha256=sha((capture / 'report.json').read_bytes()),
                source_manifest=str(source / 'manifest.json'), source_bank_sha256=list(map(sha, banks)),
                expected_bank_sha256=list(map(sha, expected)), steps=steps,
                component_erases=4, journal_C_erases=1, total_sector_erases=5,
                journal_appends=5, F_writes=0, D_erases=0, A_B_image_writes=0,
                saved_default='B', saved_monitor_generation='00000008',
                original_C_records_archived_on_host=16, original_D_records_retained_on_chip=15,
                original_C_sha256=sha(old_c), original_D_sha256=sha(old_d),
                latest_boot_wear_policy_preserved=True, all_old_rows_retained_on_chip=False,
                final_journal=final, SRAM_sha256=report['SRAM_sha256'], SRAM_data_writes=0,
                WORKSPACE_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0,
                firmware_builds=0, other_board_access=False, F_sha256=manifest['F_sha256'],
                owner_RAM_ZP_restore_required=True, original_context_restore='MON B / B3>',
                installed_checks=['native-M1-M2-M3-W-APPS', 'MAINT-LOAD-cold-and-valid-old-cache',
                                  'WB5-PROGRAM-query-Table-BATCH-AUTO-NO', 'CLOCK-refresh-return',
                                  'all-bank-postimages-boot-wear-RAM-ZP-preservation'],
                physical_RESET_after_install='Separate receiver prompt after approved writes; no power cut',
                original_images_archived=True, existing_downloads_changed=False)
    save(out / 'plan.json', plan)
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    prepare(a.capture, a.out)
