"""No-write physical saved-B boot closeout for the approved 2512 tools install."""
import argparse
import json
from pathlib import Path

import qualify_services_g4_2512_ram as t

INSTALL = t.ROOT / 'output/qualification/2512-services-g4-installed-20261030-r1'
PLAN = t.ROOT / 'output/qualification/2512-services-g4-install-scope-20261030-r1'


def run(folder):
    folder = folder.resolve()
    assert folder.is_relative_to(t.ROOT / 'output/qualification') and not folder.exists()
    installed = json.loads((INSTALL / 'report.json').read_text())
    plan = json.loads((PLAN / 'plan.json').read_text())
    assert installed['passed'] and installed['owner_RAM_restored'] and installed['COM4_released']
    assert installed['component_requests'] == 4 and installed['total_sector_erases'] == 5
    assert installed['all_postimages_double_verified'] and installed['all_131072_SRAM_bytes_unchanged']
    ram, zp = (INSTALL / 'owner-ram.bin').read_bytes(), (INSTALL / 'owner-zp.bin').read_bytes()
    assert t.sha(ram) == installed['owner_RAM_sha256'] and t.sha(zp) == installed['owner_ZP_sha256']
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader) == t.live.READBACK_SHA256
    folder.mkdir(parents=True)
    (folder / '.gitignore').write_text('*\n')
    (folder / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    report = dict(board='2512', CPU='65C02', passed=False, started_utc=t.utc(),
        phase='prepared', flash_writes=0, journal_writes=0, boot_setting_writes=0,
        SRAM_data_writes=0, WORKSPACE_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0,
        power_cuts=0, chooser_keys_sent=0, owner_RAM_restored=False)
    s = None
    borrowed = False

    def checkpoint(): t.save(folder / 'report.json', report)
    def mark(**fields):
        marker = json.loads(t.MARK.read_text()); marker.update(fields); t.save(t.MARK, marker)

    checkpoint()
    try:
        with t.serial_lease('2512-services-g4-physical-default-B-closeout', timeout=30):
            marker = json.loads(t.MARK.read_text())
            assert marker['feature_install_boot_pending'] and marker['application_ram_restored']
            assert not marker['application_RAM_restore_pending']
            assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)] == plan['expected_bank_sha256']
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    s = t.Session(folder, log)
                    mark(services_g4_boot_worker_active=True, block_snapshot=True, physical_reset_pending=True)
                    report['phase'] = 'READY_FOR_PHYSICAL_RESET_NO_CHOOSER_KEY'; checkpoint()
                    print('READY: press only 2512 physical RESET, keep USB connected, and let saved B countdown finish. Receiver sends no chooser key.', flush=True)
                    head = s.until((t.transport.CHOICES,), seconds=600)
                    (folder / 'physical-foundation-startup.txt').write_bytes(head)
                    assert t.transport.IDENTITY in head
                    banner = s.until((t.MON,), seconds=30)
                    (folder / 'physical-default-B.txt').write_bytes(banner)
                    assert b'g00000008 / MON B' in banner and b'CPU $02' in banner
                    borrowed = True
                    mark(physical_reset_pending=False, application_RAM_restore_pending=True)
                    assert s.owner() == (ram, zp), 'Physical default startup changed owner RAM/ZP'
                    report['physical_saved_B_boot_owner_unchanged'] = True
                    print('PASS physical saved B/g8 boot and owner RAM/ZP preservation', flush=True)
                    for line in ('V', 'M1', 'W', 'APPS', 'TIME'):
                        out = s.command(line)
                        assert b'Services absent/invalid' not in out
                    s.rec(); s.service(reader)
                    for n in range(4):
                        body = s.client.flash(n)
                        (folder / f'physical-after-B{n}.bin').write_bytes(body)
                        assert body == (PLAN / f'final-expected-B{n}.bin').read_bytes()
                    report['all_installed_postimages_unchanged_after_RESET'] = True
                finally:
                    try:
                        if borrowed:
                            if s.context != b'RAM SERVICE BASE1> ': s.rec(); s.service(reader)
                            restored = s.client.restore_owner(ram, zp)
                            report.update({k:v for k,v in restored.items() if k not in ('owner_RAM_restored', 'owner_ZP_restored')})
                            s.context = t.REC
                            s.monitor()
                            assert s.owner() == (ram, zp)
                            report.update(owner_RAM_restored=True, owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close(); report['COM4_released'] = True
                            report['final_context'] = s.context.decode() if s.context else None
                        mark(services_g4_boot_worker_active=False,
                             application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                             application_ram_restored=report['owner_RAM_restored'] if borrowed else True,
                             block_snapshot=True, last_services_g4_boot=str(folder / 'report.json'))
                        checkpoint()
        assert report['physical_saved_B_boot_owner_unchanged'] and report['all_installed_postimages_unchanged_after_RESET']
        assert report['owner_RAM_restored'] and report['COM4_released']
        report.update(passed=True, phase='PHYSICAL_DEFAULT_BOOT_AND_PRESERVATION_PASSED', finished_utc=t.utc())
        checkpoint()
        final = dict(installed, physical_boot_verified=True, physical_boot_report_sha256=t.sha((folder / 'report.json').read_bytes()),
            phase='INSTALLED_AND_PHYSICAL_DEFAULT_BOOT_PASSED', finished_utc=t.utc(),
            physical_saved_B_boot_owner_unchanged=True, original_context_restored='MON B / B3>',
            physical_boot_flash_writes=0, final_context='B3>', COM4_released=True)
        t.save(INSTALL / 'final-receipt.json', final)
        mark(feature_install_boot_pending=False, firmware_verification_pending=False,
             physical_reset_pending=False, application_RAM_restore_pending=False, application_ram_restored=True,
             state='MON-g8-services-g4-WB5-in-flash-original-WB3-cache-restored', final_prompt='B3>',
             workbench_RAM_generation_at_closeout='00000003', workbench_current_flash_reload='MAINT LOAD',
             last_services_g4_preservation_receipt=str(INSTALL / 'final-receipt.json'),
             block_snapshot=False, physical_boot_status='MON B generation 00000008 saved-default physical RESET passed')
        print(json.dumps(final, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=t.utc()); checkpoint(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    run(parser.parse_args().folder)
