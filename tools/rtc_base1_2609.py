"""2609 BASE1 RTC qualification/collection using the frozen RAM reader binary.

No native-mode or ACIA claim. Only FT245 / 65C816 emulation, exact BASE1 F,
and the independently captured, subsequently restored owner RAM authority.
"""
import argparse
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'output/qualification'
sys.path.insert(0, str(ROOT / 'tools'))
import rtc_drift_campaign as campaign

read, sha = campaign.read, campaign.sha
PROFILE = 'BASE1-RTC-RAM1-2609'
TRIAL = Q / '2609-rc1-zip-migration-20261028-r1'
RECEIPT = TRIAL / 'live/final-receipt.json'
RECEIPT_SHA = '4a719e12724ddf6f05c23a1db6ee44da4bc0f1ad79ac10963e8cd68be95a1bfa'
CAPTURE_SHA = '4a3449833e70daf27115d9d68dd88af84f47c44a16026eab8d7c4f03ea506417'
DRIVER_SHA = 'fea08bf9f2d8cd98b76fb31e2ebf56271a329601c3af1532c69b3d9834eab92e'
AUDIT_SHA = '45dc570f0672231fde7548fbb30c3cc70026e969bfba52cac7f0a7e992be2b9b'


def adapted(name, expected):
    path = ROOT / 'tools' / name
    assert sha(path) == expected, 'Frozen BASE1 source changed'
    source = path.read_text(encoding='utf-8')
    # Only board/USB/port/report routing changes. BUILD remains the original
    # byte-identical, CPU/I2C-tested reader, not an untested rebuilt image.
    source = source.replace("'2512'", "'2609'")
    source = source.replace('device-operations/2512.json', 'device-operations/2609.json')
    source = source.replace('A10MQFLCA', 'A10MPQXCA').replace("'COM4'", "'COM8'")
    source = source.replace('2512:', '2609:').replace('PASS 2512 BASE1', 'PASS 2609 BASE1')
    source = source.replace("'BASE1-RTC-RAM1'", repr(PROFILE))
    source = source.replace("ROOT/'tools/rtc_base1_collect.py'", 'Path(__file__)')
    module = types.ModuleType('_2609_' + path.stem)
    module.__file__ = str(Path(__file__).resolve())
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module, source


driver, DRIVER_SOURCE = adapted('rtc_base1_collect.py', DRIVER_SHA)
auditor, AUDIT_SOURCE = adapted('rtc_base1_audit.py', AUDIT_SHA)


def inputs():
    marker = driver.read(driver.MARK)
    assert marker['board'] == '2609'
    assert marker['state'] == 'BASE1-extracted-rc1-upgrade-accepted'
    assert marker['firmware'] == 'STR8N-F 0.3.0 g00000001 BASE1 PR05'
    assert marker['current_F_sha256'] == driver.F_SHA
    assert marker['current_firmware_profile'] == 'BASE1' and marker['monitor_generation'] is None
    assert marker['application_ram_restored'] and marker['final_prompt'] == 'REC>'
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('application_RAM_restore_pending', 'upper_RAM_restore_pending', 'physical_reset_pending', 'owner_application_running', 'one_shot_collection_active'))
    assert sha(RECEIPT) == RECEIPT_SHA and Path(marker['last_preservation_report']).resolve() == RECEIPT.resolve()
    r = driver.read(RECEIPT)
    assert r['passed'] and r['board'] == '2609' and r['CPU'] == '65C816 emulation'
    assert r['original_owner_RAM_ZP_restored_and_verified'] and r['COM8_released'] and r['final_context'] == 'REC>'
    assert r['F_sha256'] == driver.F_SHA
    banks = [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
    assert banks == r['final_bank_sha256']
    assert marker['current_tracked_erase_counts'] == r['counts_after']
    assert marker['current_journal_sequence'] == r['sequence_after']
    assert marker['default_boot'] == 'S' and marker['enabled_banks'] == 0
    capture = TRIAL / 'fresh-capture-r2'
    assert sha(capture/'result.json') == CAPTURE_SHA
    meta = driver.read(capture/'result.json')
    assert meta['passed'] and meta['original_pre_helper_escrow'] and meta['USB_serial'] == 'A10MPQXCA'
    bodies = {name: (capture/name).read_bytes() for name in ('owner-ram.bin', 'owner-ram-repeat.bin', 'owner-zp.bin', 'owner-zp-repeat.bin')}
    for stem, size, key in (('owner-ram', 0x6500, 'RAM_sha256'), ('owner-zp', 0xe0, 'ZP_sha256')):
        body = bodies[stem+'.bin']
        assert len(body) == size and body == bodies[stem+'-repeat.bin']
        assert driver.digest(body) == meta[key] == r[key]
    proof = driver.read(driver.BUILD/'proof.json')
    state = driver.read(campaign.STATE)
    for name in ('tools/rtc_base1_collect.py', 'tools/rtc_base1_audit.py', 'tools/build_rtc_base1.py', 'BUILD/rtc-base1-2512-20261029/proof.json', 'BUILD/rtc-base1-2512-20261029/2512-RTC-BASE1-RAM.bin', 'BUILD/rtc-base1-2512-20261029/sampler.bin'):
        assert sha(ROOT/name) == state['dependencies'][name]
    image = (driver.BUILD/'2512-RTC-BASE1-RAM.bin').read_bytes()
    reader = (driver.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert proof['passed'] and len(image) == 1733 and driver.digest(image) == proof['sha256']
    assert len(reader) == 3078 and driver.digest(reader) == driver.live.READBACK_SHA256 == r['product_file_sha256']['firmware/payload/STR8N-F-READBACK-RAM.bin']
    assert sha(driver.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin') == driver.F_SHA
    assert sha(driver.REPO/'src/core/boot-symbols.inc') == proof['source_sha256']['s\\core\\boot-symbols.inc']
    meta = dict(meta, capture=str(capture), capture_sha256=CAPTURE_SHA, restored_by_receipt=str(RECEIPT), receipt_sha256=RECEIPT_SHA,
                prefix_authority='Independent pre-helper resident MON capture, restored and verified by immutable upgrade receipt; not a fresh pre-upload prefix read.')
    return marker, RECEIPT, meta, bodies, proof, image, reader, banks


driver.inputs = inputs


def collect(folder):
    # This rechecks inputs again under the shared serial lease before any USB.
    result = driver.collect(folder)
    folder = Path(folder)
    (folder/'adapted-driver.py').write_text(DRIVER_SOURCE, encoding='utf-8')
    (folder/'adapted-audit.py').write_text(AUDIT_SOURCE, encoding='utf-8')
    return result


def audit_board(item, state):
    point = auditor.audit_board(item, state)
    assert item['board'] == point['board'] == '2609'
    r = driver.read(item['report'])
    assert r['usb_serial'] == 'A10MPQXCA' and r['port'] == 'COM8'
    assert r['initial_qualified_receipt_sha256'] == RECEIPT_SHA
    folder = Path(item['report']).parent
    marker = driver.read(folder/'marker-before.json')
    # Complete B3 equality includes all journal/config/wear sectors; all B0
    # bytes are compared by the inherited audit, not just an image header.
    assert marker['current_journal_sequence'] == 1024
    assert marker['current_tracked_erase_counts'] == {'C': 78, 'D': 47, 'F': 31}
    assert (folder/'owner-ram-before.bin').read_bytes() == (TRIAL/'fresh-capture-r2/owner-ram.bin').read_bytes()
    assert (folder/'owner-zp-before.bin').read_bytes() == (TRIAL/'fresh-capture-r2/owner-zp.bin').read_bytes()
    return point


def accept(path):
    path = Path(path).resolve()
    # Serialize campaign-state acceptance with other scheduled/manual work.
    with driver.serial_lease('drift', timeout=30):
        state = driver.read(campaign.STATE)
        r = driver.read(path)
        item = dict(board='2609', report=str(path), sha256=sha(path), offset=r['rtc_minus_reference_interval_s'], trim=r['trim_steps'], RAM_restored=True, capture_profile=PROFILE)
        point = audit_board(item, state)
        run, root = path.parent.parent, Path(state['root'])
        points, events = driver.read(root/'points.json'), driver.read(root/'events.json')
        assert not state.get('base1_profiles', {}).get('2609', {}).get('qualified'), 'Already accepted; do not reset the powered segment'
        if not any(p['board']=='2609' and p['time']==point['time'] for p in points):
            points.append(point)
        new = []
        for event in point['events']:
            event = dict(event, board='2609')
            if event['up'] >= state['baselines']['2609']['time']-120 and not any(e['board']=='2609' and e['down']==event['down'] and e['up']==event['up'] for e in events):
                events.append(event);new.append(event)
        summary = dict(passed=True, started_utc=r['started_utc'], finished_utc=r['finished_utc'], boards=[item], failures=[], clock_set=False, trim_changed=False, explicit_ACK_sent=False, flash_writer=False, ports_released=True)
        campaign.save(run/'summary.json', summary)
        audit = dict(passed=True, issues=[], new_PF_events=new, summary_sha256=sha(run/'summary.json'),
            exact_serial_read_load_restore_only=True, all_flash_banks_double_verified_unchanged=True,
            RAM_ZP_restoration_verified=True, returned_to_original_REC=True,
            qualification='Live 2609 FT245 / 65C816 emulation; unchanged qualified BASE1 RAM binary; native and ACIA unqualified')
        campaign.save(run/'campaign-audit.json', audit)
        marker = driver.read(driver.MARK)
        marker.update(RTC_sampling_owner_stopped=False, block_snapshot=False,
            snapshot_block_reason='BASE1 read-only RTC sampler qualified; restore owner RAM/ZP and REC after every collection',
            last_BASE1_RTC_qualification=str(path), last_BASE1_RTC_qualification_sha256=sha(path))
        campaign.save(driver.MARK, marker)
        state['board_admission']['2609'] = {k:marker.get(k) for k in state['board_admission']['2609']}
        state.setdefault('base1_profiles', {})['2609'] = dict(board='2609', qualified=True, profile=PROFILE,
            F_sha256=driver.F_SHA, qualification_report=str(path), qualification_report_sha256=sha(path),
            qualification_audit=str(run/'campaign-audit.json'), qualification_audit_sha256=sha(run/'campaign-audit.json'))
        state.setdefault('segment_boundaries', {})['2609'] = dict(time=point['time'], UTC=point['UTC'],
            reason='First qualified 2609 BASE1 RTC reading after firmware upgrade and resets; do not bridge unverified continuity', report=str(path))
        state['dependencies']['tools/rtc_base1_2609.py'] = sha(__file__)
        state.update(last_attempt_utc=campaign.NOW(), last_summary=str(run/'summary.json'), last_issues=[], last_new_PF_events=new)
        campaign.save(root/'points.json', points);campaign.save(root/'events.json', events)
        campaign.save(campaign.STATE, state);campaign.report(state)
        (run/'qualification.md').write_text('# 2609 BASE1 RTC qualification\n\nPASS: nine fresh RTC/NIST observations; exact read/load/restore serial audit; all four flash banks double-read before and after, identical; owner RAM/ZP restored and independently read back; original REC prompt restored; USB released.\n\nTime and trim unchanged. PF latch/history read only. B0, journal/config/wear sectors unchanged. EDU SRAM is never addressed by this helper. FT245 / 65C816 emulation only; ACIA/native mode unqualified. New powered segment starts at this receipt; historical measurements remain.\n\nReceipt: '+str(path)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, accepted=point, new_PF_events=new, qualified_for_scheduled_collection=True), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collect', action='store_true')
    p.add_argument('--out', type=Path)
    p.add_argument('--accept-report', type=Path)
    a = p.parse_args()
    if a.accept_report:
        accept(a.accept_report)
    else:
        inputs()
        if a.collect:
            folder = a.out or Q/('rtc-base1-2609-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))/'2609'
            collect(folder)
        else:
            print('PASS 2609 BASE1 inputs and owner escrow; no board or network port opened')
