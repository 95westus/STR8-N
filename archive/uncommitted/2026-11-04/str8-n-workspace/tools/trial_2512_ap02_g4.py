"""Guarded one-erase AP/02 trial: program blank B0:9, test, erase to restore."""
import argparse
import json
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as opaque
from native_journal_room import require_zero_erase_room

t=p.t
SCOPE=t.ROOT/'output/qualification/2512-AP02-g4-scope-20261030-r1'
PLAN_SHA='0d1570f0b19651271b612c2eb63f67a68ae91d43680aaf1e92d2e40440b21d20'
APP=b'APP> '; B0=b'B0> '; SERVICE=b'RAM SERVICE BASE1> '


class Session(p.Session):
    def monitor(self):
        if self.context==APP:self.link.send(b'Q');self.until((t.MON,))
        if self.context==B0:self.command('B3',(t.MON,))
        super().monitor()


def run(approval,folder):
    assert t.sha((SCOPE/'plan.json').read_bytes())==PLAN_SHA
    plan=json.loads((SCOPE/'plan.json').read_text());auth=json.loads(approval.read_text())
    assert auth['owner_answer']=='Approve one-erase 2512 AP/02 trial'
    assert auth['board']=='2512' and auth['plan_sha256']==PLAN_SHA
    assert auth['sector_erases']==1 and auth['target']=='B0:9000-9FFF'
    assert auth['driver_sha256']==t.sha(Path(__file__).read_bytes())
    assert plan['total_sector_erases']==1 and plan['F_writes']==plan['C_D_erases']==0
    original=(SCOPE/'original-sector.bin').read_bytes();assert original==b'\xff'*4096
    images={name:(SCOPE/f'fixture-{name}.bin').read_bytes() for name in ['unsealed','header-only','valid']}
    assert {n:t.sha(v) for n,v in images.items()}==plan['fixture_sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    fw=json.loads((t.REPO/'firmware/minimal-manifest.json').read_text())
    writer_sha=fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    assert t.sha(reader)==t.live.READBACK_SHA256 and t.sha(writer)==writer_sha
    folder=folder.resolve();assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    folder.mkdir();(folder/'.gitignore').write_text('*\n')
    opaque.durable_file(folder/'trial-driver.py',Path(__file__).read_bytes())
    t.save(folder/'approval.json',auth)
    report=dict(board='2512',CPU='65C02',passed=False,started_utc=t.utc(),plan_sha256=PLAN_SHA,
        phase='prepared',checks=[],program_commands=0,checksum_cells=[],erase_requests=0,erases_completed=0,
        flash_restore_pending=False,owner_RAM_restored=False,owner_ZP_restored=False,F_writes=0,C_D_erases=0,
        MON_A_B_E_or_tool_writes=0,boot_setting_writes=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,firmware_builds=0,CPU_simulations=0)
    s=None;marker=None;borrowed=False;ram=zp=None
    def checkpoint():t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
    def check(label):
        report['checks'].append(label);checkpoint();print('PASS '+label,flush=True)
    def rec():
        if s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:
            s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    def verify(stage,label,double=False):
        if s.context!=SERVICE:rec();s.service(reader)
        expected=plan['source_bank_sha256'] if stage=='source' else plan['stage_bank_sha256'][stage]
        for repeat in range(1,3 if double else 2):
            for bank in range(4):
                body=s.client.flash(bank);opaque.durable_file(folder/f'{label}-pass{repeat}-B{bank}.bin',body)
                assert t.sha(body)==expected[bank],'Unexpected bank; stop before any further trial mutation'
    def program(address,body):
        assert 0x9000<=address and address+len(body)<=0x9078 and 1<=len(body)<=8
        assert s.context==B0
        assert report['program_commands']<17
        report['program_commands']+=1;checkpoint()
        out=s.command(f'!M {address:04X} '+body.hex(' ').upper())
        assert b'REFUSED' not in out
    def refuse(label):
        rec();s.monitor()
        assert b'APPDEMO' not in s.command('APPS')
        assert b'REFUSED' in s.command('APP APPDEMO')
        check(label)
    def seal(address,body,stage):
        rec();s.monitor();s.command('B0',(B0,));program(address,body)
        report['checksum_cells'] += [f'{address+i:04X}' for i in range(len(body))]
        s.command('B3',(t.MON,));s.rec();s.service(reader);verify(stage,stage)
    def restore_flash():
        rec();s.service(reader)
        actual=[s.client.flash(bank) for bank in range(4)]
        assert all(t.sha(actual[n])==plan['source_bank_sha256'][n] for n in (1,2,3))
        assert actual[0][:0x1000]+actual[0][0x2000:]==(folder/'before-pass1-B0.bin').read_bytes()[:0x1000]+(folder/'before-pass1-B0.bin').read_bytes()[0x2000:]
        before=actual[0][0x1000:0x2000]
        if before==original:
            # Admission/program-transfer failure before any effective bit write:
            # preserve zero-erasure outcome; do not manufacture a wear record.
            report['flash_restore_pending']=False;mark(AP02_g4_flash_restore_pending=False)
            raise RuntimeError('Target already original; no erase requested; trial is incomplete')
        assert report['erase_requests']==0
        opaque.durable_file(folder/'pre-restore-sector.bin',before)
        rec();t.transport.recovery_usb(s.link);s.load(writer,writer_sha,opaque.PROMPT)
        wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda line:print(line,flush=True))
        assert wire.read_sector(0,0x90)==before
        report.update(erase_requests=1,phase='single-restoration-erase-request');checkpoint();s.context=None
        assert not wire.replace_sector(0,0x90,before,original)
        s.context=opaque.PROMPT;assert wire.read_sector(0,0x90)==original
        rec();s.service(reader);verify('restored','final',double=True)
        final=t.classify_journal((folder/'final-pass1-B3.bin').read_bytes())
        assert final==plan['final_journal']
        report.update(erases_completed=1,flash_restore_pending=False,all_expected_final_banks=True,
            original_B0_restored=True,all_28_original_journal_records_retained=True,
            final_bank_sha256=plan['stage_bank_sha256']['restored'],sequence_after=1042,valid_records_after=29,
            B0_9_count_after=15,counts_C_D_E_F_unchanged=[53,33,28,24])
        mark(AP02_g4_flash_restore_pending=False);check('exact-original-B0-and-all-bank-journal-restoration')
    checkpoint()
    try:
        with t.serial_lease('2512-approved-AP02-g4-one-erase-trial',timeout=30):
            marker=json.loads(t.MARK.read_text())
            assert marker['final_prompt']=='B3>' and marker['application_ram_restored']
            assert not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==plan['source_bank_sha256']
            t.save(folder/'marker-before.json',marker)
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=Session(folder,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                    face=s.command('V');assert b'g00000008 / MON B' in face and b'CPU $02' in face
                    ram,zp=s.owner();assert s.owner()==(ram,zp)
                    opaque.durable_file(folder/'owner-ram.bin',ram);opaque.durable_file(folder/'owner-zp.bin',zp)
                    report.update(RAM_sha256=t.sha(ram),ZP_sha256=t.sha(zp),fresh_native_owner_double_escrow=True)
                    assert b'APPDEMO' not in s.command('APPS')
                    borrowed=True;mark(AP02_g4_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    s.rec();t.transport.recovery_usb(s.link);s.service(reader)
                    assert s.client.read(b'M',0x6500)==reader+ram[len(reader):] and s.client.read(b'Z',0xe0)==zp
                    verify('source','before',double=True)
                    assert (folder/'before-pass1-B0.bin').read_bytes()[0x1000:0x2000]==original
                    require_zero_erase_room((folder/'before-pass1-B3.bin').read_bytes(),1)
                    opaque.durable_file(folder/'archived-original-B0-32768.bin',(folder/'before-pass1-B0.bin').read_bytes())
                    check('fresh-owner-double-escrow-bank-backups-and-still-erased-target')
                    rec();s.monitor();s.command('B0',(B0,))
                    report.update(flash_restore_pending=True,phase='program-blank-target-without-erase');checkpoint()
                    mark(AP02_g4_flash_restore_pending=True)
                    for offset in range(0,120,8):program(0x9000+offset,images['unsealed'][offset:offset+8])
                    s.command('B3',(t.MON,));s.rec();s.service(reader);verify('unsealed','unsealed')
                    refuse('unsealed-header-CRC-refused-before-execution')
                    seal(0x901c,images['valid'][28:30],'header-only');refuse('unsealed-payload-CRC-refused-before-execution')
                    seal(0x901e,images['valid'][30:32],'valid')
                    s.client.restore_owner(ram,zp);s.context=t.REC;s.monitor()
                    assert b'APPDEMO B0:9000' in s.command('APPS')
                    out=s.command('APP APPDEMO',(APP,t.MON));assert s.context==APP and b'APPDEMO / BASE1 PR05' in out
                    s.link.send(b'?');out=s.until((APP,));assert b'APPDEMO / BASE1 PR05' in out
                    (folder/'app-help.txt').write_bytes(out)
                    s.link.send(b'Q');back=s.until((t.MON,))
                    assert b'g00000008 / MON B' in back and b'CPU $02' in back
                    (folder/'app-Q-public-HOLD.txt').write_bytes(back)
                    assert s.owner()==(ram,zp)
                    report['APP_run_owner_RAM_ZP_unchanged']=True
                    check('valid-flash-APP-help-public-HOLD-Q-owner-preservation')
                finally:
                    try:
                        try:
                            if report['flash_restore_pending']:restore_flash()
                        finally:
                            if borrowed:
                                if s.context!=SERVICE:rec();s.service(reader)
                                report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                                assert s.owner()==(ram,zp)
                                report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close();report['COM4_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            restored=report['owner_RAM_restored'] if borrowed else True
                            mark(AP02_g4_worker_active=False,application_RAM_restore_pending=not restored,
                                application_ram_restored=restored,AP02_g4_flash_restore_pending=report['flash_restore_pending'],
                                block_snapshot=True if report['flash_restore_pending'] or not restored else marker['block_snapshot'],
                                last_AP02_g4_trial=str(folder/'report.json'))
                        checkpoint()
        assert report['original_B0_restored'] and report['APP_run_owner_RAM_ZP_unchanged'] and report['owner_RAM_restored']
        assert report['erase_requests']==report['erases_completed']==1
        report.update(passed=True,phase='AP02_G4_PASSED_NATIVE_RTC_CONTINUITY_PENDING',finished_utc=t.utc());checkpoint()
        t.save(folder/'final-receipt.json',report)
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),plan['stage_bank_sha256']['restored'])),
            current_full_flash_sha256=t.sha(b''.join((folder/f'final-pass1-B{n}.bin').read_bytes() for n in range(4))),
            current_journal_sequence=1042,current_journal_valid_records=29,
            current_tracked_erase_counts=dict(marker['current_tracked_erase_counts'],**{'B0:9':15}),
            AP02_g4_trial_closed=True,AP02_g4_RTC_continuity_pending=True,
            last_AP02_g4_preservation_receipt=str(folder/'final-receipt.json'),final_prompt='B3>')
        print('PASS AP/02 current g4 on 2512; one erase, original B0 and owner RAM restored; COM4 released',flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());checkpoint();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--approval',type=Path,required=True)
    parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args();run(args.approval,args.folder)
