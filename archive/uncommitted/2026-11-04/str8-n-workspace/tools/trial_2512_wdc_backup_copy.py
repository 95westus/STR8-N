"""Approved preserving B0 copy/restore only: four erases; F golden, no C/D erase."""
import argparse
import json
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as opaque

t=p.t
SCOPE=t.ROOT/'output/qualification/2512-WDC-backup-copy-scope-20261030-r1'
PLAN_SHA='0952de2b671bca6bdad4caded9a2fbf6b48d05c30a8eb5d5b3210bd6d0b7803a'
SERVICE=b'RAM SERVICE BASE1> '


def run(folder, *, lease_timeout=60):
    folder=folder.resolve()
    assert t.sha((SCOPE/'plan.json').read_bytes())==PLAN_SHA
    plan=json.loads((SCOPE/'plan.json').read_text())
    assert plan['total_sector_erases']==4 and plan['F_writes']==plan['C_D_erases']==0
    assert plan['target_sectors']==['B0:8','B0:9'] and plan['all_20_original_journal_records_retained']
    assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    fw=json.loads((t.REPO/'firmware/minimal-manifest.json').read_text())
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    writer_sha=fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(writer)==writer_sha and t.sha(reader)==t.live.READBACK_SHA256
    original=(SCOPE/'original-B0-32768.bin').read_bytes()
    vendor=(SCOPE/'wdcmonv2-original-32768.bin').read_bytes()
    assert t.sha(original)==plan['source_bank_sha256'][0] and t.sha(vendor)==plan['vendor_bank_sha256']
    for step in plan['steps']:
        label=step['label']
        assert t.sha((SCOPE/f'{label}-before.bin').read_bytes())==step['original_sector_sha256']
        assert t.sha((SCOPE/f'{label}-target.bin').read_bytes())==step['target_sector_sha256']
        assert [t.sha((SCOPE/f'{label}-expected-B{n}.bin').read_bytes()) for n in range(4)]==step['after_sha256']
        assert step['journal']['journal_sector_erases']==[]
    folder.mkdir(parents=True);(folder/'.gitignore').write_text('*\n')
    opaque.durable_file(folder/'reviewed-plan.json',(SCOPE/'plan.json').read_bytes())
    opaque.durable_file(folder/'trial-driver.py',Path(__file__).read_bytes())
    opaque.durable_file(folder/'original-B0-32768.bin',original)
    opaque.durable_file(folder/'wdcmonv2-host-backup-32768.bin',vendor)
    t.save(folder/'wdcmonv2-host-backup.json',dict(schema=1,board='2512',CPU='65C02',
        sha256=t.sha(vendor),bytes=32768,source=plan['vendor_source'],reset_vector='F818',
        source_kind='preserved-original-vendor-bank',live_WDC_source_capture=False,
        factory_migration_qualified=False,WDC_B0_boot_qualified=False))
    report=dict(schema=1,board='2512',CPU='65C02',port='COM4',usb_serial='A10MQFLCA',passed=False,
        started_utc=t.utc(),plan_sha256=PLAN_SHA,checks=[],erase_requests=0,erases_completed=0,
        completed_steps=[],flash_restore_pending=False,owner_RAM_restored=False,owner_ZP_restored=False,
        F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,firmware_builds=0,CPU_simulations=0,
        writer_sha256=writer_sha,readback_sha256=t.live.READBACK_SHA256,
        new_NFM2_engine_executed=False,full_factory_migration_qualified=False,WDC_B0_boot_qualified=False,
        serial_port_opened=False,owner_RAM_restore_pending=False)
    s=None;marker=None;borrowed=False;ram=zp=None
    def save():t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
    def check(label):
        report['checks'].append(label);save();print('PASS '+label,flush=True)
    def rec():
        if s.context==SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:
            s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        elif s.context!=t.REC:
            s.rec()
        assert s.context==t.REC
    def verify(hashes,label,double=False):
        if s.context!=SERVICE:rec();s.service(reader)
        for repeat in range(1,3 if double else 2):
            for n in range(4):
                actual=s.client.flash(n)
                opaque.durable_file(folder/f'{label}-pass{repeat}-B{n}.bin',actual)
                assert t.sha(actual)==hashes[n],f'Unexpected B{n} postimage; no further flash write'
    save()
    try:
        assert 1 <= lease_timeout <= 600
        print(f'WAIT: shared serial lease, up to {lease_timeout}s; no board port opened',flush=True)
        with t.serial_lease('2512-approved-WDC-backup-copy-four-erases',timeout=lease_timeout):
            marker=json.loads(t.MARK.read_text())
            assert not marker['block_snapshot'] and marker['application_ram_restored']
            assert not marker['application_RAM_restore_pending']
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==plan['source_bank_sha256']
            t.save(folder/'marker-before.json',marker)
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=p.Session(folder,log,'2512');report['serial_port_opened']=True;save()
                    s.link.send(b'\r');s.until((t.MON,),seconds=15)
                    face=s.command('V');assert b'g00000008 / MON B' in face and b'CPU $02' in face
                    ram,zp=s.owner();assert s.owner()==(ram,zp)
                    opaque.durable_file(folder/'owner-ram.bin',ram);opaque.durable_file(folder/'owner-zp.bin',zp)
                    report.update(RAM_sha256=t.sha(ram),ZP_sha256=t.sha(zp),native_owner_double_escrow=True)
                    check('fresh-native-owner-RAM-ZP-double-escrow')
                    borrowed=True;report['owner_RAM_restore_pending']=True;save()
                    mark(WDC_backup_copy_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    rec();t.transport.recovery_usb(s.link);s.service(reader)
                    assert s.client.read(b'M',0x6500)==reader+ram[len(reader):]
                    assert s.client.read(b'Z',0xe0)==zp
                    verify(plan['source_bank_sha256'],'before',double=True)
                    for n in range(4):
                        opaque.durable_file(folder/f'live-original-B{n}-32768.bin',(folder/f'before-pass1-B{n}.bin').read_bytes())
                    check('fresh-all-bank-double-admission-and-durable-originals')
                    for step in plan['steps']:
                        label=step['label'];verify(step['before_sha256'],label+'-pre')
                        rec();t.transport.recovery_usb(s.link);s.load(writer,writer_sha,opaque.PROMPT)
                        wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda line:print(line,flush=True))
                        before=wire.read_sector(0,step['page'])
                        assert t.sha(before)==step['original_sector_sha256']
                        opaque.durable_file(folder/f'{label}-preimage.bin',before)
                        target=(SCOPE/f'{label}-target.bin').read_bytes()
                        assert report['erase_requests']<4
                        report.update(erase_requests=report['erase_requests']+1,flash_restore_pending=True,active_step=label)
                        mark(WDC_backup_copy_flash_restore_pending=True);save();s.context=None
                        assert not wire.replace_sector(0,step['page'],before,target)
                        s.context=opaque.PROMPT
                        assert wire.read_sector(0,step['page'])==target
                        rec();s.service(reader);verify(step['after_sha256'],label)
                        report['erases_completed']+=1;report['completed_steps'].append(label);save()
                        check(label+'-sector-and-all-bank-postimages-verified')
                        if label=='copy-B0-9000':
                            actual=s.client.flash(0);opaque.durable_file(folder/'WDC-copy-B0-32768.bin',actual)
                            assert actual==vendor
                            assert (folder/'wdcmonv2-host-backup-32768.bin').read_bytes()==actual
                            report.update(exact_WDC_bank_copy_verified=True,host_and_B0_backups_agree=True)
                            check('complete-WDC-copy-equals-standalone-host-backup')
                    verify(plan['expected_final_bank_sha256'],'final',double=True)
                    final=t.classify_journal((folder/'final-pass1-B3.bin').read_bytes())
                    assert final==plan['final_journal']
                    report.update(flash_restore_pending=False,original_B0_restored=True,
                        all_20_original_journal_records_retained=True,final_journal=final,
                        final_bank_sha256=plan['expected_final_bank_sha256'])
                    mark(WDC_backup_copy_flash_restore_pending=False)
                    check('original-B0-and-20-original-records-retained-with-four-new-reservations')
                finally:
                    try:
                        if borrowed:
                            rec();s.service(reader)
                            restored=s.client.restore_owner(ram,zp)
                            assert restored['owner_RAM_restored'] and restored['owner_ZP_restored']
                            s.context=t.REC;s.monitor();assert s.owner()==(ram,zp)
                            report.update(owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_restore_pending=False)
                    finally:
                        if s is not None:
                            s.link.close();report['COM4_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            good=report['owner_RAM_restored'] and not report['flash_restore_pending']
                            mark(WDC_backup_copy_worker_active=False,
                                application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                                application_ram_restored=report['owner_RAM_restored'] if borrowed else marker['application_ram_restored'],
                                WDC_backup_copy_flash_restore_pending=report['flash_restore_pending'],
                                block_snapshot=marker['block_snapshot'] if good or not borrowed else True,
                                last_WDC_backup_copy_report=str(folder/'report.json'))
                        save()
        assert report['erases_completed']==report['erase_requests']==4 and report['original_B0_restored']
        assert report['owner_RAM_restored'] and report['host_and_B0_backups_agree']
        report.update(passed=True,phase='SEPARATE_BACKUP_COPY_PASSED_FACTORY_MIGRATION_STILL_OPEN',finished_utc=t.utc());save()
        t.save(folder/'final-receipt.json',report)
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),plan['expected_final_bank_sha256'])),
             current_full_flash_sha256=t.sha(b''.join((SCOPE/f'final-expected-B{n}.bin').read_bytes() for n in range(4))),
             current_journal_sequence=1037,current_journal_valid_records=24,
             current_tracked_erase_counts=dict(marker['current_tracked_erase_counts'],**{'B0:8':8,'B0:9':14}),
             last_WDC_backup_copy_preservation_receipt=str(folder/'final-receipt.json'))
        print('PASS separate WDC backup copy; original B0/RAM restored, F golden, 20 old records retained; COM4 released',flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--execute-approved-backup-copy',action='store_true')
    parser.add_argument('--lease-timeout',type=int,default=60)
    args=parser.parse_args()
    if not args.execute_approved_backup_copy:parser.error('Explicit reviewed backup-copy execution switch required; no port opened')
    run(args.folder,lease_timeout=args.lease_timeout)
