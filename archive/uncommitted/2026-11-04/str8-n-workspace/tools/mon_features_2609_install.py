"""Approved five-sector2609 MON B install; no rotation, retries or F writes."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mon_features_2609_ram as trial
from installer.common import save
import nf_opaque as opaque

PLAN=ROOT/'output/qualification/2609-mon-feature-install-scope-20261030'
utc=lambda:datetime.now(timezone.utc).isoformat()


def run(folder):
    admission,_=trial.inputs()
    marker,_,meta,bodies,_,_,reader,banks=admission
    plan=json.loads((PLAN/'plan.json').read_text())
    assert plan['sector_erases']==plan['journal_appends']==5
    assert plan['C_D_erases']==plan['F_writes']==0 and banks==plan['source_bank_sha256']
    assert [s['target'] for s in plan['steps']]==['B2:8000','B2:9000','B2:A000','B3:E000','B3:B000']
    fw=json.loads((trial.KIT/'firmware/minimal-manifest.json').read_text())
    oi=(trial.KIT/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    oi_sha=fw['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256']
    assert trial.sha(oi)==oi_sha
    original_ram,original_zp=bodies['owner-ram.bin'],bodies['owner-zp.bin']
    folder=folder.resolve();assert folder.is_relative_to(ROOT/'output/qualification')
    folder.mkdir(parents=True,exist_ok=False);(folder/'.gitignore').write_text('*\n')
    save(folder/'approval.json',dict(owner_answer='Approve five-sector MON B install',
         approved_targets=[s['target'] for s in plan['steps']],sector_erases=5,
         journal_appends=5,C_D_erases=0,F_writes=0,recorded_utc=utc(),
         scope_sha256=trial.sha((PLAN/'plan.json').read_bytes())))
    save(folder/'marker-before.json',marker);save(folder/'escrow-authority.json',meta)
    report=dict(board='2609',CPU='65C816 emulation',passed=False,phase='prepared',
         started_utc=utc(),sectors_completed=[],erase_requests=0,
         F_writes=0,C_D_erases=0,boot_settings_changed=False,SRAM_data_writes=0,
         RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,
         owner_RAM_restored=False,firmware_boot_verified=False)
    context=None;client=None;link=None;borrowed=False;expected=None
    def checkpoint():save(folder/'install-receipt.json',report)
    def mark(**fields):
        current=json.loads(trial.MARK.read_text());current.update(fields);save(trial.MARK,current)
    def service():
        nonlocal context,client,borrowed
        assert context==trial.REC
        trial.recovery.PROMPT=b'RAM SERVICE BASE1> '
        client=trial.recovery.RecoveryClient(trial.live.LoggedRecoveryStream(link),timeout=60)
        context=None;borrowed=True
        client.load(reader,trial.live.READBACK_SHA256,REC_observed=True)
        context=trial.recovery.PROMPT
        return client
    def leave_service():
        nonlocal context
        assert context==b'RAM SERVICE BASE1> '
        client.send(b'Q');client.until(trial.REC);context=trial.REC
    checkpoint()
    try:
      with trial.serial_lease('2609-approved-five-sector-install',timeout=30):
        trial.inputs()
        with (folder/'serial.jsonl').open('x',encoding='utf-8') as log:
          try:
            link=trial.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
            link.send(b'\r');link.until(trial.REC,seconds=12);context=trial.REC
            trial.transport.recovery_usb(link)
            mark(feature_install_worker_active=True,application_RAM_restore_pending=True,
                 block_snapshot=True,firmware_verification_pending=True)
            service()
            first,repeat=client.read(b'M',0x6500),client.read(b'M',0x6500)
            zp,zpr=client.read(b'Z',0xe0),client.read(b'Z',0xe0)
            declared_ram,declared_zp=original_ram,original_zp
            original_ram=declared_ram[:len(reader)]+first[len(reader):];original_zp=zp
            assert first==repeat and zp==zpr==declared_zp and first[:len(reader)]==reader
            assert original_ram==declared_ram
            (folder/'owner-ram.bin').write_bytes(original_ram);(folder/'owner-zp.bin').write_bytes(original_zp)
            expected=[]
            for bank in range(4):
                a,b=client.flash(bank),client.flash(bank)
                assert a==b and trial.sha(a)==banks[bank]
                (folder/f'before-B{bank}.bin').write_bytes(a);expected.append(bytearray(a))
            leave_service()
            for index,step in enumerate(plan['steps']):
                assert report['erase_requests']==index<5
                bank=int(step['target'][1]);address=int(step['target'][3:],16)
                before=(PLAN/f'original-B{bank}-{address:04X}.bin').read_bytes()
                image=(PLAN/f'target-B{bank}-{address:04X}.bin').read_bytes()
                assert trial.sha(before)==step['original_sha256'] and trial.sha(image)==step['target_sha256']
                journal_address=int(step['journal_page'],16)
                assert journal_address==0xca00+index*256
                assert expected[3][journal_address-0x8000:journal_address-0x7f00]==b'\xff'*256
                trial.transport.recovery_usb(link)
                trial.recovery.PROMPT=opaque.PROMPT
                loader=trial.recovery.RecoveryClient(trial.live.LoggedRecoveryStream(link),timeout=60)
                context=None;loader.load(oi,oi_sha,REC_observed=True);context=opaque.PROMPT
                wire=opaque.Wire(link.serial,timeout=60,trace=log,progress=lambda x:print(x,flush=True))
                fresh=wire.read_sector(bank,address>>8)
                assert fresh==before,'Changed preimage: stop before replacement'
                stepdir=folder/f'{index+1:02d}-B{bank}-{address:04X}';stepdir.mkdir()
                opaque.durable_file(stepdir/'original.bin',fresh)
                report.update(phase='sending-replacement',current_target=step['target'])
                report['erase_requests']+=1;checkpoint()
                context=None
                identical=wire.replace_sector(bank,address>>8,fresh,image)
                context=opaque.PROMPT
                assert not identical,'Unexpected no-op: do not manufacture a wear record'
                after=wire.read_sector(bank,address>>8)
                opaque.durable_file(stepdir/'after.bin',after);assert after==image
                wire.send(b'Q\r');wire.text_until(trial.REC);context=trial.REC
                expected[bank][address-0x8000:address-0x7000]=image
                expected[3][journal_address-0x8000:journal_address-0x7f00]=(PLAN/f'journal-{journal_address:04X}.bin').read_bytes()
                service()
                actual3=client.flash(3);(stepdir/'independent-B3.bin').write_bytes(actual3)
                assert actual3==expected[3], 'Unexpected journal/image change: no next erase'
                if bank!=3:assert client.flash(bank)==expected[bank]
                report['sectors_completed'].append(step['target'])
                report.update(phase='sector-and-wear-verified',sequence=step['sequence'])
                checkpoint();print('VERIFIED',step['target'],step['journal_page'],step['sequence'],flush=True)
                leave_service()
            assert report['erase_requests']==5 and len(report['sectors_completed'])==5
            service()
            for bank in range(4):
                data=client.flash(bank);(folder/f'after-B{bank}.bin').write_bytes(data)
                assert data==expected[bank] and trial.sha(data)==plan['expected_bank_sha256'][bank]
            report.update(all_banks_expected=True,all_old_journal_rows_retained=True,
                          final_bank_sha256=plan['expected_bank_sha256'],sequence_after=1029,
                          valid_records_after=16,F_sha256=trial.sha(expected[3][-4096:]),
                          counts_after={'C':78,'D':47,'F':31})
            checkpoint()
          finally:
            try:
                if link is not None and borrowed:
                    if context==opaque.PROMPT:
                        # Only a fully observed text prompt permits this exit.
                        link.send(b'Q\r');link.until(trial.REC,seconds=15);context=trial.REC
                    if context==trial.REC:service()
                    if context==b'RAM SERVICE BASE1> ':
                        report.update(client.restore_owner(original_ram,original_zp))
                        report['owner_RAM_restored']=True;context=trial.REC
                    else:
                        raise RuntimeError('No safe restoration prompt; retain power and inspect before further action')
            finally:
                if link is not None:link.close();report['COM8_released']=True
                restored=report['owner_RAM_restored']
                mark(feature_install_worker_active=False,application_RAM_restore_pending=borrowed and not restored,
                     application_ram_restored=restored if borrowed else marker['application_ram_restored'],
                     block_snapshot=True if report['erase_requests'] or not restored else marker['block_snapshot'],
                     last_MON_feature_install=str(folder/'install-receipt.json'))
                report['final_context']=context.decode() if context else None;checkpoint()
      assert report['all_banks_expected'] and report['owner_RAM_restored'] and report['COM8_released']
      report.update(passed=True,phase='PROGRAMMED_VERIFIED_AWAITING_PHYSICAL_BOOT',finished_utc=utc())
      checkpoint()
      mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),report['final_bank_sha256'])),
           current_journal_sequence=1029,current_journal_valid_records=16,
           current_tracked_erase_counts=report['counts_after'],
           MON_B_generation='00000008',MON_A_generation='8000000F',
           feature_install_boot_pending=True,firmware_verification_pending=True,block_snapshot=True)
      print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
      report.update(error=repr(error),finished_utc=utc());checkpoint();raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    run(parser.parse_args().folder)
