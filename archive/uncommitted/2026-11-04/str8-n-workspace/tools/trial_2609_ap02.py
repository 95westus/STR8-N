"""Approved AP/02 install/launch/exact WDC restore: two B0:9 erases only."""
import argparse
import json
import re
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as opaque
t=p.t
SCOPE=t.ROOT/'output/qualification/2609-AP02-scope-20261030-r1'
APP=b'APP> '; B0=b'B0> '
MARK=t.ROOT/'output/qualification/device-operations/2609.json'


class Session(p.Session):
    def monitor(self):
        if self.context==APP:
            self.link.send(b'Q'); self.until((t.MON,))
        if self.context==B0: self.command('B3',(t.MON,))
        super().monitor()


def run(approval,folder):
    approval=approval.resolve(); folder=folder.resolve()
    plan=json.loads((SCOPE/'plan.json').read_text()); auth=json.loads(approval.read_text())
    assert auth['owner_answer']=='Approve two-erase B0:9 trial' and auth['board']=='2609'
    assert auth['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())=='01b1753b72c20069f85f89db7226b489d8a97dd603115d2a13b42f8700fb50e8'
    assert auth['driver_sha256']==t.sha(Path(__file__).read_bytes())
    assert plan['total_sector_erases']==2 and plan['C_D_erases']==plan['F_writes']==0
    cap=Path(plan['source_capture']); fresh=json.loads((cap/'report.json').read_text())
    assert fresh['passed'] and fresh['owner_RAM_restored'] and fresh['COM8_released']
    assert t.sha((cap/'report.json').read_bytes())==plan['source_report_sha256']
    original=(SCOPE/'original-sector.bin').read_bytes(); assert t.sha(original)==plan['original_sector_sha256']
    images={n:(SCOPE/f'fixture-{n}.bin').read_bytes() for n in ('unsealed','header-only','valid')}
    assert {n:t.sha(b) for n,b in images.items()}==plan['fixture_SHA256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    fw=json.loads((t.REPO/'firmware/minimal-manifest.json').read_text())
    installer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    installer_sha=fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    assert t.sha(reader)==t.live.READBACK_SHA256 and t.sha(installer)==installer_sha
    assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    folder.mkdir(parents=True); (folder/'.gitignore').write_text('*\n')
    (folder/Path(__file__).name).write_bytes(Path(__file__).read_bytes()); t.save(folder/'approval.json',auth)
    report=dict(board='2609',CPU='65C816 emulation',passed=False,started_utc=t.utc(),checks=[],
        erase_requests=0,erases_completed=0,flash_restore_pending=False,owner_RAM_restored=False,
        F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,SRAM_data_writes=0,WORKSPACE_writes=0,
        RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,firmware_builds=0,
        plan_sha256=auth['plan_sha256'],baseline_journal_sequence=1031)
    s=None; borrowed=False; marker=None; ram=zp=None
    def save(): t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(MARK.read_text());m.update(fields);t.save(MARK,m)
    def check(label):
        report['checks'].append(label);save();print('PASS '+label,flush=True)
    def leave_service():
        assert s.context==b'RAM SERVICE BASE1> '
        s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
    def verify(stage,label,double=False):
        if s.context!=b'RAM SERVICE BASE1> ': s.rec();s.service(reader)
        for repeat in range(1,3 if double else 2):
            for n in range(4):
                actual=s.client.flash(n)
                (folder/f'{label}-pass{repeat}-B{n}.bin').write_bytes(actual)
                assert actual==(SCOPE/f'{stage}-expected-B{n}.bin').read_bytes(),'Unexpected postimage; no further mutation'
    def replace(before,after,stage):
        assert report['erase_requests']<2 and s.context==t.REC
        t.transport.recovery_usb(s.link);s.load(installer,installer_sha,opaque.PROMPT)
        wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda line:print(line,flush=True))
        actual=wire.read_sector(0,0x90);assert actual==before
        opaque.durable_file(folder/f'pre-erase-{report["erase_requests"]+1}.bin',actual)
        report['erase_requests']+=1;save();s.context=None
        assert not wire.replace_sector(0,0x90,before,after)
        s.context=opaque.PROMPT;assert wire.read_sector(0,0x90)==after
        wire.send(b'Q\r');wire.text_until(t.REC);s.context=t.REC
        s.service(reader);verify(stage,stage);report['erases_completed']+=1;save()
    def refuse(label):
        leave_service();s.monitor()
        assert b'APPDEMO' not in s.command('APPS')
        assert b'REFUSED' in s.command('APP APPDEMO')
        check(label)
    def seal(address,data,stage):
        s.monitor();s.command('B0',(B0,))
        s.command(f'!M {address:04X} '+data.hex(' ').upper(),(B0,))
        s.command('B3',(t.MON,));s.rec();s.service(reader);verify(stage,stage)
        report.setdefault('checksum_cells',[]).extend(f'{address+i:04X}' for i in range(len(data)))
        save()
    def restore_flash():
        if s.context==opaque.PROMPT:
            s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        if s.context==b'RAM SERVICE BASE1> ': leave_service()
        elif s.context!=t.REC: s.rec()
        s.service(reader)
        b0=s.client.flash(0);b3=s.client.flash(3)
        for n in (1,2):assert t.sha(s.client.flash(n))==plan['source_bank_sha256'][n]
        assert b0[:0x1000]==(cap/'before-pass1-B0.bin').read_bytes()[:0x1000]
        assert b0[0x2000:]==(cap/'before-pass1-B0.bin').read_bytes()[0x2000:]
        assert b3==(SCOPE/'journal-after-install-B3.bin').read_bytes()
        current=b0[0x1000:0x2000]
        # Restoration owns this exact admitted sector even after a partial
        # fixture/checksum step. Other B0 bytes and the reserved journal must
        # still match before spending the one remaining restoration erase.
        leave_service();replace(current,original,'restored')
        verify('restored','final',double=True)
        report.update(flash_restore_pending=False,original_WDC_bank_restored=True,
            all_expected_final_banks=True,all_17_original_journal_records_retained=True,
            sequence_after=1033,valid_records_after=19,journal_appends=2,
            B0_9_count_after=4,counts_after=dict(C=78,D=48,E=45,F=31),
            final_bank_sha256=plan['expected_final_bank_sha256'])
        mark(AP02_flash_restore_pending=False);check('exact-WDC-bank-and-all-journal-postimages-restored')
    save()
    try:
        with t.serial_lease('2609-approved-AP02-two-erase-trial',timeout=180):
            import rtc_monb8_2609 as qualified
            admission=qualified.inputs();marker=admission[0]
            assert admission[-1]==plan['source_bank_sha256']
            t.save(folder/'marker-before.json',marker)
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=Session(folder,log,'2609');s.link.send(b'\r');s.until((t.REC,),seconds=12);s.monitor()
                    assert b'CPU $16' in s.command('V')
                    ram,zp=s.owner();assert s.owner()==(ram,zp)
                    assert (ram,zp)==(admission[3]['owner-ram.bin'],admission[3]['owner-zp.bin'])
                    opaque.durable_file(folder/'owner-ram.bin',ram);opaque.durable_file(folder/'owner-zp.bin',zp)
                    report.update(RAM_sha256=t.sha(ram),ZP_sha256=t.sha(zp))
                    assert b'APPDEMO' not in s.command('APPS')
                    check('fresh-owner-double-escrow-and-name-admission')
                    borrowed=True;mark(AP02_trial_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    s.rec();t.transport.recovery_usb(s.link);s.service(reader)
                    assert s.client.read(b'M',0x6500)==reader+ram[len(reader):]
                    assert s.client.read(b'Z',0xe0)==zp
                    s.read_banks('before',plan['source_bank_sha256'])
                    opaque.durable_file(folder/'archived-original-WDC-B0-32768.bin',(cap/'before-pass1-B0.bin').read_bytes())
                    opaque.durable_file(folder/'archived-original-sector.bin',original)
                    leave_service();report['flash_restore_pending']=True;mark(AP02_flash_restore_pending=True);save()
                    replace(original,images['unsealed'],'unsealed');refuse('unsealed-header-refused-before-execution')
                    seal(0x901c,images['valid'][28:30],'header-only');refuse('unsealed-payload-refused-before-execution')
                    seal(0x901e,images['valid'][30:32],'valid')
                    result=s.client.restore_owner(ram,zp);s.context=t.REC;s.monitor()
                    listed=s.command('APPS');assert b'APPDEMO B0:9000' in listed
                    out=s.command('APP APPDEMO',(APP,t.MON));assert s.context==APP and b'APPDEMO / BASE1 PR05' in out
                    s.link.send(b'?');out=s.until((APP,));assert b'APPDEMO / BASE1 PR05' in out
                    (folder/'app-help.txt').write_bytes(out)
                    s.link.send(b'Q');out=s.until((t.MON,));assert b'g00000008 / MON B' in out and b'CPU $16' in out
                    (folder/'app-Q-public-HOLD.txt').write_bytes(out)
                    assert s.owner()==(ram,zp)
                    report['APP_run_owner_RAM_ZP_unchanged']=True
                    check('flash-APP-launch-help-bare-Q-public-HOLD-owner-preservation')
                finally:
                    try:
                        try:
                            if report['flash_restore_pending']:
                                if report['erase_requests']:
                                    restore_flash()
                                else:
                                    if s.context==opaque.PROMPT:
                                        s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
                                    if s.context!=b'RAM SERVICE BASE1> ':s.rec();s.service(reader)
                                    for n in range(4):assert t.sha(s.client.flash(n))==plan['source_bank_sha256'][n]
                                    report['flash_restore_pending']=False
                                    mark(AP02_flash_restore_pending=False)
                        finally:
                            if borrowed:
                                if s.context!=b'RAM SERVICE BASE1> ':s.rec();s.service(reader)
                                result=s.client.restore_owner(ram,zp)
                                report.update({k:v for k,v in result.items() if k not in ('owner_RAM_restored','owner_ZP_restored')})
                                s.context=t.REC;s.monitor();assert s.owner()==(ram,zp);s.rec()
                                report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close();report['COM8_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            good=report['owner_RAM_restored'] and not report['flash_restore_pending']
                            mark(AP02_trial_worker_active=False,application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                                application_ram_restored=report['owner_RAM_restored'] if borrowed else True,
                                AP02_flash_restore_pending=report['flash_restore_pending'],block_snapshot=True if report['erase_requests'] or not good else marker['block_snapshot'],
                                last_AP02_flash_trial=str(folder/'report.json'))
                        save()
        assert report['original_WDC_bank_restored'] and report['APP_run_owner_RAM_ZP_unchanged'] and report['owner_RAM_restored']
        assert report['erase_requests']==report['erases_completed']==2
        report.update(passed=True,phase='AP02_FLASH_PASSED_RTC_ADMISSION_PENDING',finished_utc=t.utc());save()
        t.save(folder/'final-receipt.json',report)
        mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),plan['expected_final_bank_sha256'])),
            current_full_flash_sha256=t.sha(b''.join((SCOPE/f'restored-expected-B{n}.bin').read_bytes() for n in range(4))),
            current_journal_sequence=1033,current_journal_valid_records=19,
            AP02_flash_trial_closed=True,AP02_RTC_admission_pending=True,
            last_AP02_flash_preservation_receipt=str(folder/'final-receipt.json'),block_snapshot=True)
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());save();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--approval',type=Path,required=True)
    parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args();run(args.approval,args.folder)
