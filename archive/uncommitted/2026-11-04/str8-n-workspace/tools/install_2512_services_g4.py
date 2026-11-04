"""Owner-approved five-erase 2512 tools install; no F writes or retries.

Requires the sealed fresh RAM qualification and exact native C-rotation plan.
Uses existing OPAQUE/READBACK binaries; no assembly or CPU simulation.
"""
import argparse
import binascii
import json
import re
from pathlib import Path

import qualify_services_g4_2512_ram as t
import nf_opaque as opaque

PLAN = t.ROOT / 'output/qualification/2512-services-g4-install-scope-20261030-r1'
CAPTURE = t.ROOT / 'output/qualification/2512-services-g4-RAM-20261030-r2'


def run(folder):
    folder = folder.resolve()
    assert folder.is_relative_to(t.ROOT / 'output/qualification') and not folder.exists()
    p = json.loads((PLAN / 'plan.json').read_text())
    approval = json.loads((PLAN / 'owner-approval.json').read_text())
    assert approval['owner_answer'] == 'Aproved'
    assert t.sha((PLAN / 'plan.json').read_bytes()) == approval['plan_sha256'] == '531d9981d535cd090d83fc12ad9f2a35bae59ee4fffcd05d739321154f67f9df'
    q = json.loads((CAPTURE / 'report.json').read_text())
    assert q['passed'] and q['owner_RAM_restored'] and q['COM4_released']
    assert t.sha((CAPTURE / 'report.json').read_bytes()) == p['source_report_sha256']
    assert p['total_sector_erases'] == p['journal_appends'] == 5
    assert p['F_writes'] == p['D_erases'] == p['A_B_image_writes'] == 0
    assert [s['target'] for s in p['steps']] == ['B2:8000', 'B2:9000', 'B2:A000', 'B3:E000']
    before = [(CAPTURE / f'before-pass1-B{n}.bin').read_bytes() for n in range(4)]
    assert list(map(t.sha, before)) == p['source_bank_sha256']
    for step in p['steps']:
        label = step['target'].replace(':', '-')
        for suffix, field in [('original', 'original_sha256'), ('target', 'target_sha256')]:
            assert t.sha((PLAN / f'{label}-{suffix}.bin').read_bytes()) == step[field]
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    fw = json.loads((t.REPO / 'firmware/minimal-manifest.json').read_text())
    image = (t.REPO / 'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    image_sha = fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    assert t.sha(reader) == t.live.READBACK_SHA256 and t.sha(image) == image_sha
    _, _, _, fixture = t.inputs()
    folder.mkdir(parents=True)
    (folder / '.gitignore').write_text('*\n')
    t.save(folder / 'approval.json', dict(owner_answer='Aproved', recorded_utc=t.utc(),
        context='Approval after five-erase scope and 16-C-record host archive were explained',
        plan_sha256=t.sha((PLAN / 'plan.json').read_bytes()),
        total_sector_erases=5, journal_appends=5, F_writes=0, power_cuts=0,
        original_C_records_archived_on_host=16, original_D_records_retained_on_chip=15))
    report = dict(board='2512', CPU='65C02', passed=False, started_utc=t.utc(),
        phase='prepared', component_requests=0, components_completed=[], checks=[],
        planned_total_erases=5, F_writes=0, D_erases=0, A_B_image_writes=0,
        SRAM_data_writes=0, WORKSPACE_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0,
        power_cuts=0, firmware_builds=0, owner_RAM_restored=False,
        physical_boot_verified=False, plan_sha256=t.sha((PLAN / 'plan.json').read_bytes()))
    s = None
    borrowed = False
    marker = None
    ram = zp = None

    def checkpoint():
        t.save(folder / 'report.json', report)

    def mark(**fields):
        current = json.loads(t.MARK.read_text())
        current.update(fields)
        t.save(t.MARK, current)

    def checked(label):
        report['checks'].append(label)
        checkpoint()
        print('PASS ' + label, flush=True)

    checkpoint()
    try:
        with t.serial_lease('2512-approved-services-g4-five-erase-install', timeout=30):
            marker, _, _, _ = t.inputs()
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)] == p['source_bank_sha256']
            t.save(folder / 'marker-before.json', marker)
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    s = t.Session(folder, log)
                    s.link.send(b'\r')
                    s.until((t.MON,), seconds=15)
                    ident = s.command('V')
                    assert b'g00000008 / MON B' in ident and b'CPU $02' in ident
                    ram, zp = s.owner()
                    assert (ram, zp) == s.owner()
                    old_code = ram[0x4600:0x6200]
                    assert old_code[:8] == b'MW\x02\x1cPR05' and binascii.crc_hqx(old_code, 65535) == 0
                    opaque.durable_file(folder / 'owner-ram.bin', ram)
                    opaque.durable_file(folder / 'owner-zp.bin', zp)
                    report.update(owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp),
                                  native_prehelper_double_escrow=True)
                    checked('fresh-native-owner-RAM-ZP-double-escrow')
                    mark(services_g4_install_worker_active=True, application_RAM_restore_pending=True,
                         block_snapshot=True, firmware_verification_pending=True)
                    borrowed = True
                    s.rec()
                    t.transport.recovery_usb(s.link)
                    s.service(reader)
                    assert s.client.read(b'M', 0x6500) == reader + ram[len(reader):]
                    assert s.client.read(b'Z', 0xe0) == zp
                    s.read_banks('before', p['source_bank_sha256'])
                    for sector, offset in [('C', 0x4000), ('D', 0x5000)]:
                        body = before[3][offset:offset + 4096]
                        assert body == (PLAN / f'original-{sector}-4096.bin').read_bytes()
                        opaque.durable_file(folder / f'archived-original-{sector}-4096.bin', body)
                    report['original_C_archive_sha256'] = p['original_C_sha256']
                    checked('fresh-four-bank-admission-and-durable-C-D-archives')
                    s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC
                    for i, step in enumerate(p['steps']):
                        assert report['component_requests'] == i < 4
                        label = step['target'].replace(':', '-')
                        original = (PLAN / f'{label}-original.bin').read_bytes()
                        target = (PLAN / f'{label}-target.bin').read_bytes()
                        t.transport.recovery_usb(s.link)
                        s.load(image, image_sha, opaque.PROMPT)
                        wire = opaque.Wire(s.link.serial, timeout=60, trace=log,
                                           progress=lambda text: print(text, flush=True))
                        assert wire.read_sector(step['bank'], step['page']) == original
                        report.update(phase='approved-replacement', current_target=step['target'])
                        report['component_requests'] += 1
                        checkpoint()
                        s.context = None
                        assert not wire.replace_sector(step['bank'], step['page'], original, target)
                        s.context = opaque.PROMPT
                        assert wire.read_sector(step['bank'], step['page']) == target
                        wire.send(b'Q\r'); wire.text_until(t.REC); s.context = t.REC
                        s.service(reader)
                        for n in range(4):
                            actual = s.client.flash(n)
                            (folder / f'{i + 1:02d}-{label}-B{n}.bin').write_bytes(actual)
                            assert actual == (PLAN / f'{label}-expected-B{n}.bin').read_bytes(), 'Unexpected postimage; no next erase'
                        report['components_completed'].append(step['target'])
                        checked('independent-postimages-' + label)
                        s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC
                    assert report['component_requests'] == 4
                    report.update(total_sector_erases=5, C_erases=1, journal_appends=5,
                        sequence_after=1033, valid_records_after=20, final_journal=p['final_journal'],
                        final_bank_sha256=p['expected_bank_sha256'], original_C_archived_on_host=True,
                        all_15_original_D_records_retained=True)
                    s.service(reader)
                    s.client.restore_owner(ram, zp); s.context = t.REC
                    s.monitor()
                    report['valid_old_cache_before_forced_load'] = True
                    for line in ('V', 'M1', 'M2', 'M3', 'W', 'APPS', 'TIME'):
                        out = s.command(line)
                        assert b'Services absent/invalid' not in out
                        if line == 'TIME': assert re.search(rb'20\d\d-\d\d-\d\d', out)
                    checked('native-g8-g4-map-wear-APPS-TIME')
                    for label, line in [('valid-old-cache', 'MAINT LOAD'), ('spaced', '  MAINT LOAD  ')]:
                        out = s.command(line, (t.WB, t.MON))
                        assert s.context == t.WB and b'WORKBENCH WB2 g00000005' in out
                        assert b'Load flash WB2/PROGRAM:' in out
                        s.monitor()
                        checked('installed-forced-load-' + label)
                    s.modify(0x4800, b'\0' * 8)
                    out = s.command('MAINT LOAD', (t.WB, t.MON))
                    assert s.context == t.WB and b'WORKBENCH WB2 g00000005' in out
                    assert b'Load flash WB2/PROGRAM:' in out
                    s.monitor()
                    out = s.command('MAINT LOAD X')
                    assert b'Load flash WB2/PROGRAM:' not in out and s.context == t.MON
                    checked('installed-cold-forced-load-and-extra-argument-refusal')
                    for line in ('MAINT', 'FLASH'):
                        out = s.command(line, (t.WB, t.MON))
                        assert s.context == t.WB and b'WORKBENCH WB2 g00000005' in out
                        s.monitor()
                    out = s.command('CLOCK', (t.CLOCK, t.MON))
                    assert s.context == t.CLOCK and re.search(rb'20\d\d-\d\d-\d\d', out)
                    s.command('R'); s.monitor()
                    s.command('MAINT', (t.WB, t.MON)); assert s.context == t.WB
                    s.mount(); s.command('WORK')
                    table = s.command('T P'); assert b'P:slot/kind#seq' in table and b'NF2512G4' not in table
                    assert b'BATCH done' in s.command('BATCH T;T')
                    assert b'BATCH done' not in s.command('BATCH T;;T')
                    s.command('R P NF2512G4 L')
                    out = s.command('S P AUTO 3000 3007 NF2512G4', (b'type YES> ', t.WB))
                    assert s.context == b'type YES> ' and b'Target PROGRAM' in out
                    assert b'Canceled; no record written' in s.command('NO', (t.WB,))
                    checked('installed-CLOCK-MAINT-FLASH-PROGRAM-BATCH-AUTO-NO-return')
                    actual_sram = s.sram(fixture, 'SRAM-final')
                    assert actual_sram == (CAPTURE / 'SRAM-after-131072.bin').read_bytes()
                    report.update(all_131072_SRAM_bytes_unchanged=True, SRAM_sha256=t.sha(actual_sram))
                    s.rec(); s.service(reader)
                    s.read_banks('after', p['expected_bank_sha256'])
                    report['all_postimages_double_verified'] = True
                    checked('complete-SRAM-and-all-flash-postimages-verified')
                finally:
                    try:
                        if borrowed:
                            if s.context == opaque.PROMPT:
                                s.link.send(b'Q\r'); s.link.until(t.REC, seconds=15); s.context = t.REC
                            if s.context == b'type YES> ': s.command('NO', (t.WB,))
                            if s.context != b'RAM SERVICE BASE1> ': s.rec(); s.service(reader)
                            report.update(s.client.restore_owner(ram, zp)); s.context = t.REC
                            s.monitor()
                            assert s.owner() == (ram, zp)
                            report.update(owner_RAM_restored=True, owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close(); report['COM4_released'] = True
                            report['final_context'] = s.context.decode() if s.context else None
                        if marker is not None:
                            mark(services_g4_install_worker_active=False,
                                 application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                                 application_ram_restored=report['owner_RAM_restored'] if borrowed else True,
                                 block_snapshot=True if report['component_requests'] or not report['owner_RAM_restored'] else marker['block_snapshot'],
                                 last_services_g4_install=str(folder / 'report.json'))
                        checkpoint()
        assert report['all_postimages_double_verified'] and report['owner_RAM_restored']
        report.update(passed=True, phase='INSTALLED_PASSED_PHYSICAL_DEFAULT_BOOT_PENDING', finished_utc=t.utc())
        checkpoint()
        counts = dict(marker['current_tracked_erase_counts'])
        counts.update(C=53, D=33, F=24, **{'B2:8':596, 'B2:9':265, 'B2:A':13, 'B3:E':28})
        mark(current_physical_bank_sha256=dict(zip(('B0', 'B1', 'B2', 'B3'), p['expected_bank_sha256'])),
             current_full_flash_sha256=t.sha(b''.join((PLAN / f'final-expected-B{n}.bin').read_bytes() for n in range(4))),
             current_journal_sequence=1033, current_journal_valid_records=20,
             current_tracked_erase_counts=counts, service_generation='00000004',
             workbench_flash_generation='00000005', feature_install_boot_pending=True,
             firmware_verification_pending=True, block_snapshot=True,
             state='MON-g8-services-g4-WB5-installed-physical-check-pending', final_prompt='B3>')
        print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=t.utc()); checkpoint(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    run(parser.parse_args().folder)
