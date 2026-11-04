"""Owner-approved permanent MON A g8: one A erase, no F/C/D erase or retry."""
import argparse
import json
import re
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as opaque

t = p.t
MARK = t.ROOT / 'output/qualification/device-operations/2609.json'
SCOPE = t.ROOT / 'output/qualification/2609-MON-A-g8-scope-20261030-r1'
PLAN = SCOPE / 'install-and-keep/plan.json'
PLAN_SHA = 'f75cb157c40deea697e0e7d42b2e712251a2e9e3e8d27a9a779a348d8f8d6363'
CASE = t.ROOT / 'output/qualification/2609-MON-A-g8-install-20261030-r1'
SERVICE = b'RAM SERVICE BASE1> '


def mark(**fields):
    current = json.loads(MARK.read_text())
    current.update(fields)
    t.save(MARK, current)


def admitted_plan():
    assert t.sha(PLAN.read_bytes()) == PLAN_SHA
    plan = json.loads(PLAN.read_text())
    assert plan['mode'] == 'install-and-keep' and plan['total_sector_erases'] == 1
    assert plan['F_writes'] == plan['C_D_erases'] == 0
    return plan


def leave_service(s):
    assert s.context == SERVICE
    s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC


def restore(s, reader, ram, zp, report):
    if s.context == opaque.PROMPT:
        s.link.send(b'Q\r'); s.link.until(t.REC, seconds=15); s.context = t.REC
    if s.context != SERVICE:
        s.rec(); s.service(reader)
    report.update(s.client.restore_owner(ram, zp))
    s.context = t.REC; s.monitor()
    assert s.owner() == (ram, zp), 'Native owner restoration verification differs'
    s.rec()
    report.update(owner_RAM_restored=True, owner_ZP_restored=True)


def features(s, report):
    face = s.command('A', (t.MON,))
    assert b'g00000008 / MON A' in face and b'CPU $16' in face
    for text in ('V', '?', 'M1', 'W', 'APPS', 'TIME'):
        out = s.command(text)
        if text == 'V': assert b'g00000008 / MON A' in out
        if text == 'TIME': assert re.search(rb'20\d\d-\d\d-\d\d', out)
    s.modify(0x3000, b'\x3c\xc3\x5a\xa5')
    assert s.dump(0x3000, 0x3003) == b'\x3c\xc3\x5a\xa5'
    for address in ('C000', 'D000', 'F000'):
        out = s.command('!M ' + address + ' FF')
        assert b'REFUSED' in out
    clock = s.command('CLOCK', (t.CLOCK,))
    assert b'CLOCK BASE1 / PR05' in clock
    s.command('R')
    s.command('Q', (t.MON,))
    back = s.command('V')
    assert b'g00000008 / MON A' in back and b'CPU $16' in back
    work = s.command('MAINT LOAD', (t.WB,))
    assert b'WORKBENCH WB2 g00000005' in work
    s.mount()
    table = s.command('T P'); assert b'P:slot/kind#seq' in table
    batch = s.command('BATCH T;T')
    assert b'BATCH done' in batch and b'BATCH stopped' not in batch
    bad = s.command('BATCH T;;T'); assert b'BATCH done' not in bad
    assert b'NFATEST' not in table
    s.link.send(b'S P AUTO 3000 3003 NFATEST\r')
    preview = s.until((b'type YES> ',))
    assert b'Target PROGRAM' in preview
    cancel = s.command('NO', (t.WB,)); assert b'Canceled; no record written' in cancel
    s.command('Q', (t.MON,))
    back = s.command('V')
    assert b'g00000008 / MON A' in back and b'CPU $16' in back
    s.rec()
    report['checks'] += ['MON-A-g8-CPU16-Dump-Modify', 'F-C-D-force-refused',
        'M1-W-APPS-TIME', 'CLOCK-read-Q-to-A',
        'board-MAINT-reload-PROGRAM-Table-BATCH-AUTO-NO-Q-to-A']


def install():
    plan = admitted_plan()
    image = (SCOPE / 'candidate-MON-A-PR05-g8-4096.bin').read_bytes()
    old = (SCOPE / 'original-MON-A-PR04-4096.bin').read_bytes()
    assert t.sha(image) == plan['candidate_MON_A']['sha256'] and t.sha(old) == plan['old_MON_A']['sha256']
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer = (t.REPO / 'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    fw = json.loads((t.REPO / 'firmware/minimal-manifest.json').read_text())
    writer_sha = fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    assert t.sha(reader) == t.live.READBACK_SHA256 and t.sha(writer) == writer_sha
    CASE.mkdir(exist_ok=False); (CASE / '.gitignore').write_text('*\n')
    (CASE / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    t.save(CASE / 'approval.json', dict(owner_answer='Install and keep A g8 (recommended)',
        plan_sha256=PLAN_SHA, scope='one B3:A erase and D300 wear append; keep A g8', recorded_utc=t.utc()))
    report = dict(board='2609', CPU='65C816 emulation', passed=False, started_utc=t.utc(),
        plan_sha256=PLAN_SHA, erase_requests=0, erases_completed=0, F_writes=0,
        C_D_erases=0, B_E_or_tool_writes=0, boot_setting_writes=0, SRAM_data_writes=0,
        WORKSPACE_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0,
        firmware_builds=0, CPU_simulations=0, owner_RAM_restored=False,
        owner_ZP_restored=False, checks=[], phase='prepared')
    def checkpoint(): t.save(CASE / 'install-receipt.json', report)
    s = None; borrowed = False; marker = None; ram = zp = None
    checkpoint()
    try:
        with t.serial_lease('2609-approved-permanent-MON-A-g8', timeout=30):
            import rtc_monb8_2609 as qualified
            admission = qualified.inputs(); marker = admission[0]
            assert not marker['block_snapshot'] and admission[-1] == plan['source_bank_sha256']
            t.save(CASE / 'marker-before.json', marker); t.save(CASE / 'escrow-authority.json', admission[2])
            with (CASE / 'serial.jsonl').open('x') as log:
                try:
                    s = p.Session(CASE, log, '2609')
                    s.link.send(b'\r'); s.until((t.REC,), seconds=12); s.monitor()
                    assert b'CPU $16' in s.command('V')
                    ram, zp = s.owner(); assert s.owner() == (ram, zp)
                    assert (ram, zp) == (admission[3]['owner-ram.bin'], admission[3]['owner-zp.bin'])
                    opaque.durable_file(CASE / 'owner-ram.bin', ram)
                    opaque.durable_file(CASE / 'owner-zp.bin', zp)
                    report.update(RAM_sha256=t.sha(ram), ZP_sha256=t.sha(zp), fresh_native_double_escrow=True)
                    print('PASS fresh native owner RAM/ZP double escrow', flush=True)
                    borrowed = True
                    mark(MON_A_g8_worker_active=True, application_RAM_restore_pending=True, block_snapshot=True)
                    s.rec(); t.transport.recovery_usb(s.link); s.service(reader)
                    assert s.client.read(b'M', 0x6500) == reader + ram[len(reader):]
                    assert s.client.read(b'Z', 0xe0) == zp
                    s.read_banks('before', plan['source_bank_sha256'])
                    assert (CASE / 'before-pass1-B3.bin').read_bytes()[0x2000:0x3000] == old
                    opaque.durable_file(CASE / 'archived-original-A-PR04-4096.bin', old)
                    from native_journal_room import require_zero_erase_room
                    require_zero_erase_room((CASE / 'before-pass1-B3.bin').read_bytes(), 1)
                    print('PASS four-bank double backup, old A archive, journal capacity', flush=True)
                    leave_service(s); t.transport.recovery_usb(s.link)
                    s.load(writer, writer_sha, opaque.PROMPT)
                    wire = opaque.Wire(s.link.serial, timeout=60, trace=log, progress=lambda v: print(v, flush=True))
                    assert wire.read_sector(3, 0xa0) == old
                    report.update(phase='single-A-replacement-request', erase_requests=1); checkpoint()
                    mark(firmware_verification_pending=True)
                    s.context = None
                    assert not wire.replace_sector(3, 0xa0, old, image)
                    s.context = opaque.PROMPT; assert wire.read_sector(3, 0xa0) == image
                    wire.send(b'Q\r'); wire.text_until(t.REC); s.context = t.REC
                    s.service(reader)
                    s.read_banks('installed', plan['final_bank_sha256'])
                    before = (CASE / 'before-pass1-B3.bin').read_bytes()
                    after = (CASE / 'installed-pass1-B3.bin').read_bytes()
                    for offset in range(0x4000, 0x6000, 256):
                        if before[offset:offset+4] == b'SNBT': assert after[offset:offset+256] == before[offset:offset+256]
                    journal = t.classify_journal(after)
                    assert journal['sequence'] == 1034 and journal['valid_records'] == 20 and journal['counts'][26] == 52
                    assert journal['default'] == 'S' and journal['enabled_mask'] == 0
                    report.update(erases_completed=1, all_19_old_records_retained=True,
                        final_bank_sha256=plan['final_bank_sha256'], sequence_after=1034,
                        valid_records_after=20, A_count_after=52, counts_after=dict(C=78,D=48,E=45,F=31))
                    checkpoint()
                    print('PASS MON A and complete bank/journal postimages', flush=True)
                    leave_service(s); features(s, report)
                    print('PASS MON A tools, guard checks and returns', flush=True)
                    s.service(reader); s.read_banks('final', plan['final_bank_sha256'])
                    report['all_banks_expected'] = True
                finally:
                    try:
                        if borrowed: restore(s, reader, ram, zp, report)
                    finally:
                        if s is not None:
                            s.link.close(); report['COM8_released'] = True
                            report['final_context'] = s.context.decode() if s.context else None
                        if marker is not None:
                            restored = report['owner_RAM_restored'] if borrowed else True
                            mark(MON_A_g8_worker_active=False, application_RAM_restore_pending=not restored,
                                application_ram_restored=restored,
                                block_snapshot=True if report['erase_requests'] or not restored else marker['block_snapshot'],
                                last_MON_A_g8_install=str(CASE / 'install-receipt.json'))
                        checkpoint()
        assert report['erases_completed'] == 1 and report['owner_RAM_restored'] and report['all_banks_expected']
        report.update(passed=True, phase='INSTALLED_TOOLS_PASSED_PHYSICAL_BOOT_PENDING', finished_utc=t.utc())
        checkpoint()
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'), plan['final_bank_sha256'])),
            current_journal_sequence=1034, current_journal_valid_records=20,
            current_full_flash_sha256=t.sha(b''.join((CASE / f'final-pass1-B{n}.bin').read_bytes() for n in range(4))),
            MON_A_generation='00000008', MON_A_g8_boot_pending=True, MON_A_g8_RTC_admission_pending=True,
            firmware_verification_pending=True, final_prompt='REC>')
        print('PASS one erase complete; owner RAM/ZP restored; COM8 released; physical A boot pending', flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=t.utc()); checkpoint(); raise


def resume():
    """Finish host checks after the banner-only assertion; never load a writer."""
    plan=admitted_plan(); previous=json.loads((CASE/'install-receipt.json').read_text())
    assert not previous['passed'] and previous['erases_completed']==previous['erase_requests']==1
    assert previous['owner_RAM_restored'] and previous['owner_ZP_restored'] and previous['COM8_released']
    assert previous['sequence_after']==1034 and previous['valid_records_after']==20
    for n in range(4):
        for repeat in (1,2): assert t.sha((CASE/f'installed-pass{repeat}-B{n}.bin').read_bytes())==plan['final_bank_sha256'][n]
    folder=CASE/'host-check-resume';folder.mkdir(exist_ok=False)
    (folder/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    t.save(folder/'previous-install-receipt.json',previous)
    report=dict(previous,passed=False,checks=[],phase='READ_ONLY_HOST_CHECK_RESUME',resume_started_utc=t.utc(),
        owner_RAM_restored=False,owner_ZP_restored=False,COM8_released=False)
    report.pop('error',None)
    ram=(CASE/'owner-ram.bin').read_bytes();zp=(CASE/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader)==t.live.READBACK_SHA256
    def checkpoint():t.save(folder/'report.json',report)
    s=None;borrowed=False
    checkpoint()
    try:
        with t.serial_lease('2609-MON-A-g8-no-erase-host-check-resume',timeout=30):
            marker=json.loads(MARK.read_text())
            assert marker['block_snapshot'] and not marker['application_RAM_restore_pending']
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=p.Session(folder,log,'2609');s.link.send(b'\r');s.until((t.REC,),seconds=12);s.monitor()
                    assert s.owner()==(ram,zp)
                    borrowed=True;mark(MON_A_g8_worker_active=True,application_RAM_restore_pending=True)
                    s.rec();s.service(reader);s.read_banks('before',plan['final_bank_sha256'])
                    leave_service(s);features(s,report)
                    print('PASS MON A tools and explicit V after both Q returns',flush=True)
                    s.service(reader);s.read_banks('final',plan['final_bank_sha256'])
                    for n in range(4):
                        for repeat in (1,2):
                            (CASE/f'final-pass{repeat}-B{n}.bin').write_bytes((folder/f'final-pass{repeat}-B{n}.bin').read_bytes())
                    report['all_banks_expected']=True
                finally:
                    try:
                        if borrowed:restore(s,reader,ram,zp,report)
                    finally:
                        if s is not None:
                            s.link.close();report['COM8_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        restored=report['owner_RAM_restored'] if borrowed else True
                        mark(MON_A_g8_worker_active=False,application_RAM_restore_pending=not restored,
                            application_ram_restored=restored,block_snapshot=True)
                        checkpoint()
        assert report['all_banks_expected'] and report['owner_RAM_restored']
        report.update(passed=True,phase='INSTALLED_TOOLS_PASSED_PHYSICAL_BOOT_PENDING',finished_utc=t.utc(),
            host_check_resume=str(folder/'report.json'),host_banner_assertion_corrected=True,
            additional_erase_requests_on_resume=0)
        checkpoint();t.save(CASE/'install-receipt.json',report)
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),plan['final_bank_sha256'])),
            current_journal_sequence=1034,current_journal_valid_records=20,
            current_full_flash_sha256=t.sha(b''.join((CASE/f'final-pass1-B{n}.bin').read_bytes() for n in range(4))),
            MON_A_generation='00000008',MON_A_g8_boot_pending=True,MON_A_g8_RTC_admission_pending=True,
            firmware_verification_pending=True,final_prompt='REC>')
        print('PASS installed A qualified with zero additional erases; owner RAM restored; physical boot pending',flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());checkpoint();raise


def boot():
    plan = admitted_plan(); installed = json.loads((CASE / 'install-receipt.json').read_text())
    assert installed['passed'] and installed['erases_completed'] == 1
    ram = (CASE / 'owner-ram.bin').read_bytes(); zp = (CASE / 'owner-zp.bin').read_bytes()
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader) == t.live.READBACK_SHA256
    folder = CASE / 'physical-boot'; folder.mkdir(exist_ok=False)
    report = dict(board='2609', CPU='65C816 emulation', passed=False, started_utc=t.utc(),
        flash_writes=0, journal_writes=0, boot_setting_writes=0, power_cuts=0,
        owner_RAM_restored=False, owner_ZP_restored=False, phase='prepared')
    def checkpoint(): t.save(folder / 'report.json', report)
    s = None; borrowed = False
    checkpoint()
    try:
        with t.serial_lease('2609-MON-A-g8-physical-boot', timeout=30):
            marker = json.loads(MARK.read_text())
            assert marker['MON_A_g8_boot_pending'] and not marker['application_RAM_restore_pending']
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)] == plan['final_bank_sha256']
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    s = p.Session(folder, log, '2609')
                    mark(MON_A_g8_worker_active=True, physical_reset_pending=True)
                    report['phase'] = 'READY_FOR_OWNER_RESET'; checkpoint()
                    print('READY: press only 2609 physical RESET, keep USB powered; receiver selects A once.', flush=True)
                    face = s.until((t.transport.CHOICES,), seconds=600)
                    (folder / 'startup.txt').write_bytes(face)
                    assert t.transport.IDENTITY in face
                    s.link.send(b'A'); banner = s.until((t.MON,), seconds=30)
                    (folder / 'MON-A-banner.txt').write_bytes(banner)
                    assert b'g00000008 / MON A' in banner and b'CPU $16' in banner
                    report['physical_MON_A_boot'] = True
                    borrowed = True; mark(application_RAM_restore_pending=True)
                    assert s.owner() == (ram, zp)
                    report['ROM_startup_owner_RAM_ZP_unchanged'] = True
                    s.command('V'); s.command('M1'); s.command('W')
                    s.rec(); s.service(reader); s.read_banks('final', plan['final_bank_sha256'])
                    report['all_banks_expected'] = True
                finally:
                    try:
                        if borrowed: restore(s, reader, ram, zp, report)
                    finally:
                        if s is not None:
                            s.link.close(); report['COM8_released'] = True
                            report['final_context'] = s.context.decode() if s.context else None
                        mark(MON_A_g8_worker_active=False, physical_reset_pending=False,
                            application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                            application_ram_restored=report['owner_RAM_restored'] if borrowed else True,
                            block_snapshot=True)
                        checkpoint()
        assert report['physical_MON_A_boot'] and report['all_banks_expected'] and report['owner_RAM_restored']
        report.update(passed=True, phase='PHYSICAL_BOOT_PASSED_RTC_ADMISSION_PENDING', finished_utc=t.utc()); checkpoint()
        final = dict(installed, phase='MON_A_G8_INSTALLED_AND_PHYSICAL_BOOT_VERIFIED',
            physical_MON_A_boot=True, physical_boot_report=str(folder/'report.json'),
            original_owner_RAM_ZP_restored_and_verified=True, final_receipt_utc=t.utc())
        t.save(CASE / 'final-receipt.json', final)
        mark(MON_A_g8_boot_pending=False, firmware_verification_pending=False,
            MON_A_boot_verified=True, last_MON_A_g8_preservation_receipt=str(CASE/'final-receipt.json'), final_prompt='REC>')
        print('PASS physical A boot and preservation; COM8 released; RTC admission pending', flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=t.utc()); checkpoint(); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('install','resume','boot'))
    args = parser.parse_args()
    {'install':install,'resume':resume,'boot':boot}[args.phase]()
