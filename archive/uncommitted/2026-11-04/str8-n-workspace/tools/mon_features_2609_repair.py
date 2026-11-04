"""Approved D/E repair plus installed feature checks; F/C and other boards untouched."""
import argparse,json,re,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import mon_features_2609_ram as t
import nf_opaque as opaque
from installer.common import save

INSTALL=ROOT/'output/qualification/2609-mon-feature-install-20261030-r1'
PLAN=ROOT/'output/qualification/2609-maint-reload-g4-scope-20261030'
utc=lambda:datetime.now(timezone.utc).isoformat()


def run(folder):
    p=json.loads((PLAN/'plan.json').read_text());m=json.loads(t.MARK.read_text())
    old=json.loads((INSTALL/'install-receipt.json').read_text())
    fixed=json.loads((ROOT/'output/qualification/2609-maint-reload-ram-g4-20261030-r1/report.json').read_text())
    assert old['passed'] and old['erase_requests']==5 and fixed['passed']
    assert p['additional_erases']==2 and p['F_writes']==p['C_erases']==0
    assert m['application_ram_restored'] and not m['application_RAM_restore_pending']
    assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
    assert [m['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==p['source_bank_sha256']
    ram,zp=(INSTALL/'owner-ram.bin').read_bytes(),(INSTALL/'owner-zp.bin').read_bytes()
    reader=(t.KIT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();assert t.sha(reader)==t.live.READBACK_SHA256
    fm=json.loads((t.KIT/'firmware/minimal-manifest.json').read_text())
    oi=(t.KIT/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();oi_sha=fm['artifacts']['STR8N-F-OPAQUE-RAM.bin']['sha256'];assert t.sha(oi)==oi_sha
    before=(PLAN/'original-E-g3.bin').read_bytes();target=(PLAN/'target-E-g4.bin').read_bytes()
    assert t.sha(before)==p['original_E_sha256'] and t.sha(target)==p['target_E_sha256']
    folder=folder.resolve();folder.mkdir(parents=True,exist_ok=False);(folder/'.gitignore').write_text('*\n')
    save(folder/'approval.json',dict(owner_answer='Approve D/E repair',additional_erases=2,
         plan_sha256=t.sha((PLAN/'plan.json').read_bytes()),recorded_utc=utc()))
    save(folder/'marker-before.json',m)
    report=dict(board='2609',CPU='65C816 emulation',passed=False,phase='prepared',
        started_utc=utc(),F_writes=0,C_erases=0,SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        power_cuts=0,erase_scope_started=False,owner_RAM_restored=False,checks=[])
    link=None;context=None;client=None;borrowed=False;counter=0
    def checkpoint():save(folder/'report.json',report)
    def mark(**fields):
        q=json.loads(t.MARK.read_text());q.update(fields);save(t.MARK,q)
    def wait(tokens,seconds=40):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            choices=[(link.pending.find(x),x) for x in tokens if x in link.pending]
            if choices:
                start,token=min(choices,key=lambda a:a[0]);n=start+len(token)
                data=bytes(link.pending[:n]);del link.pending[:n];return data,token
            link.pending.extend(link.read(max(1,link.serial.in_waiting)))
        raise TimeoutError(repr(bytes(link.pending[-200:])))
    def command(text,tokens=None):
        nonlocal context,counter
        link.send(text.encode()+b'\r');data,context=wait(tokens or (context,))
        counter+=1;(folder/f'{counter:03d}.txt').write_bytes(data);return data
    def service():
        nonlocal context,client,borrowed
        assert context==t.REC;t.recovery.PROMPT=b'RAM SERVICE BASE1> '
        client=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link),timeout=60)
        context=None;borrowed=True;client.load(reader,t.live.READBACK_SHA256,REC_observed=True);context=t.recovery.PROMPT
    def leave():
        nonlocal context
        client.send(b'Q');client.until(t.REC);context=t.REC
    checkpoint()
    try:
      with t.serial_lease('2609-approved-D-E-repair',timeout=30):
       with (folder/'serial.jsonl').open('x') as log:
        try:
            link=t.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
            link.send(b'\r');_,context=wait((t.REC,));t.transport.recovery_usb(link)
            mark(feature_repair_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
            service();a,b=client.read(b'M',0x6500),client.read(b'M',0x6500)
            z,zr=client.read(b'Z',0xe0),client.read(b'Z',0xe0)
            assert a==b and z==zr==zp and a[:len(reader)]==reader and a[len(reader):]==ram[len(reader):]
            for bank in range(4):
                data=client.flash(bank);assert t.sha(data)==p['source_bank_sha256'][bank]
                (folder/f'before-B{bank}.bin').write_bytes(data)
            d=(folder/'before-B3.bin').read_bytes()[0x5000:0x6000]
            assert d==(PLAN/'original-D-4096.bin').read_bytes() and t.sha(d)==p['original_D_sha256']
            opaque.durable_file(folder/'archived-original-D-4096.bin',d)
            report['D_archive_sha256']=t.sha(d);checkpoint();leave()
            t.transport.recovery_usb(link);t.recovery.PROMPT=opaque.PROMPT
            loader=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link),timeout=60)
            context=None;loader.load(oi,oi_sha,REC_observed=True);context=opaque.PROMPT
            wire=opaque.Wire(link.serial,timeout=60,trace=log,progress=lambda x:print(x,flush=True))
            assert wire.read_sector(3,0xe0)==before
            report.update(erase_scope_started=True,phase='D-rotation-and-E-replacement');checkpoint();context=None
            assert not wire.replace_sector(3,0xe0,before,target)
            context=opaque.PROMPT;assert wire.read_sector(3,0xe0)==target
            wire.send(b'Q\r');wire.text_until(t.REC);context=t.REC
            service()
            for bank in range(4):
                data=client.flash(bank);(folder/f'after-B{bank}.bin').write_bytes(data)
                assert t.sha(data)==p['expected_bank_sha256'][bank]
            report.update(additional_erases=2,D_erases=1,E_erases=1,sequence_after=1031,
                valid_records_after=17,counts_after=p['counts_after'],all_expected_postimages=True,
                all_previous_C_records_retained=True,old_D_archived_on_host=True)
            checkpoint()
            client.restore_owner(ram,zp);context=t.REC
            # Enter existing physically qualified MON B; its bytes/F unchanged.
            banner=command('B',(t.MON,));assert b'g00000008 / MON B' in banner and b'CPU $16' in banner
            for text in ('V','M1','W','APPS','TIME'):
                out=command(text)
                if text=='TIME':assert re.search(rb'20\d\d-\d\d-\d\d',out)
            clock=command('CLOCK',(b'CLOCK> ',t.MON));assert context==b'CLOCK> '
            command('R');command('Q',(t.MON,))
            tools=command('MAINT LOAD',(t.WB,t.MON));assert context==t.WB and b'WORKBENCH WB2 g00000005' in tools
            command('EDU ON');sram=command('SRAM')
            if b'SSRAM error $01' in sram:
                assert b'Disabled CB flags acknowledged' in command('SRAM PREP');sram=command('SRAM')
            assert b'SSRAM PROGRAM:' in sram
            table=command('T P');assert b'P:slot/kind#seq' in table
            assert b'BATCH done' in command('BATCH T;T')
            bad=command('BATCH T;;T');assert b'BATCH done' not in bad
            name='NF30TEST';assert name.encode() not in table
            command('R P '+name+' L')
            preview=command('S P AUTO 3000 3007 '+name,(b'type YES> ',t.WB));assert context==b'type YES> '
            assert b'Target PROGRAM' in preview
            cancel=command('NO',(t.WB,));assert b'Canceled; no record written' in cancel
            command('Q',(t.MON,));command('Q',(t.REC,));service()
            for bank in range(4):assert t.sha(client.flash(bank))==p['expected_bank_sha256'][bank]
            report['checks']=['ROM-B-g8-entry','native-map-wear-APPS-TIME','flash-CLOCK-refresh-return',
                'MAINT-LOAD-g4-from-flash','PROGRAM-Table','BATCH-positive-and-separator-refusal',
                'missing-name-Restore','AUTO-preview-NO','Q-to-MON-and-REC','all-banks-postimages']
            report['installed_features_passed']=True
        finally:
          try:
            if borrowed:
                if context==b'CLOCK> ':command('Q',(t.MON,))
                if context==b'type YES> ':command('NO',(t.WB,))
                if context==t.WB:command('Q',(t.MON,))
                if context==t.MON:command('Q',(t.REC,))
                if context==t.REC:service()
                if context==b'RAM SERVICE BASE1> ':
                    report.update(client.restore_owner(ram,zp));report['owner_RAM_restored']=True;context=t.REC
                else:raise RuntimeError('No restoration prompt; keep power and inspect')
          finally:
            if link is not None:link.close();report['COM8_released']=True
            mark(feature_repair_worker_active=False,application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                 application_ram_restored=report['owner_RAM_restored'] if borrowed else True,block_snapshot=True,
                 last_MON_feature_repair=str(folder/'report.json'))
            report['final_context']=context.decode() if context else None;checkpoint()
      assert report['installed_features_passed'] and report['all_expected_postimages'] and report['owner_RAM_restored']
      report.update(passed=True,phase='INSTALLED_FEATURES_PASSED_RTC_ADMISSION_PENDING',finished_utc=utc());checkpoint()
      final=dict(report,final_bank_sha256=p['expected_bank_sha256'],F_sha256=t.sha((folder/'after-B3.bin').read_bytes()[-4096:]),
         original_owner_RAM_ZP_restored_and_verified=True,final_context='REC>',
         initial_five_sector_receipt=str(INSTALL/'install-receipt.json'),initial_five_sector_receipt_sha256=t.sha((INSTALL/'install-receipt.json').read_bytes()),
         total_erases_this_feature_upgrade=7,all_old_journal_rows_retained_on_chip=False,
         original_D_record_preserved_on_host=True,physical_MON_B_boot_previously_verified=True,
         physical_boot_report=str(ROOT/'output/qualification/2609-mon-feature-boot-20261030-r1/report.json'))
      save(folder/'final-receipt.json',final)
      mark(current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'),p['expected_bank_sha256'])),
         current_journal_sequence=1031,current_journal_valid_records=17,current_tracked_erase_counts=p['counts_after'],
         monitor_generation='00000008',MON_B_generation='00000008',service_generation='00000004',
         last_preservation_report=str(folder/'final-receipt.json'),state='BASE1-MON-B-g8-tools-g5-accepted',
         feature_install_boot_pending=False,firmware_verification_pending=False,
         feature_install_known_issue=None,final_prompt='REC>',block_snapshot=True)
      print(json.dumps(final,indent=2),flush=True)
    except BaseException as error:
      report.update(error=repr(error),finished_utc=utc());checkpoint();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    run(p.parse_args().folder)
