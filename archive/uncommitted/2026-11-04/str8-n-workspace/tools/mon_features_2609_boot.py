"""Physical MON B boot and read/cancel-only acceptance; no flash writer."""
import argparse
import json
import re
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import mon_features_2609_ram as trial
from installer.common import save

utc=lambda:datetime.now(timezone.utc).isoformat()
INSTALL=ROOT/'output/qualification/2609-mon-feature-install-20261030-r1'


def run(folder):
    installed=json.loads((INSTALL/'install-receipt.json').read_text())
    assert installed['passed'] and installed['erase_requests']==5
    assert installed['all_banks_expected'] and installed['owner_RAM_restored']
    assert installed['F_writes']==installed['C_D_erases']==0
    ram=(INSTALL/'owner-ram.bin').read_bytes();zp=(INSTALL/'owner-zp.bin').read_bytes()
    reader=(trial.KIT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert trial.sha(reader)==trial.live.READBACK_SHA256
    folder=folder.resolve();folder.mkdir(parents=True,exist_ok=False)
    report=dict(board='2609',CPU='65C816 emulation',passed=False,phase='prepared',
                flash_writes=0,journal_writes=0,boot_setting_writes=0,
                SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
                owner_RAM_restored=False,checks=[],started_utc=utc())
    link=None;context=None;client=None;borrowed=False;number=0
    def checkpoint():save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(trial.MARK.read_text());m.update(fields);save(trial.MARK,m)
    def until(token,seconds=35):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            found=link.pending.find(token)
            if found>=0:
                n=found+len(token);out=bytes(link.pending[:n]);del link.pending[:n];return out
            link.pending.extend(link.read(max(1,link.serial.in_waiting)))
        raise TimeoutError(repr(token)+': '+repr(bytes(link.pending[-180:])))
    def evidence(label,data):
        nonlocal number
        number+=1;(folder/f'{number:03d}-{label}.txt').write_bytes(data);return data
    def command(text,prompt=None):
        link.send(text.encode()+b'\r')
        return evidence('command',until(prompt or context))
    def dump(first,last):
        cells={}
        for base in range(first,last+1,512):
            finish=min(base+511,last)
            data=command(f'D {base:04X} {finish:04X}',trial.MON)
            for line in data.decode('ascii').splitlines():
                m=re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
                if m:cells.update((int(m[1],16)+i,b) for i,b in enumerate(bytes.fromhex(m[2])))
        assert all(a in cells for a in range(first,last+1))
        return bytes(cells[a] for a in range(first,last+1))
    def readback():
        nonlocal client,context,borrowed
        assert context==trial.REC
        trial.recovery.PROMPT=b'RAM SERVICE BASE1> '
        client=trial.recovery.RecoveryClient(trial.live.LoggedRecoveryStream(link),timeout=60)
        context=None;borrowed=True;client.load(reader,trial.live.READBACK_SHA256,REC_observed=True)
        context=trial.recovery.PROMPT
    checkpoint()
    try:
      with trial.serial_lease('2609-MON-B-physical-acceptance',timeout=30):
       with (folder/'serial.jsonl').open('x',encoding='utf-8') as log:
        try:
            link=trial.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
            mark(feature_boot_worker_active=True,block_snapshot=True)
            report['phase']='READY_FOR_OWNER_PHYSICAL_RESET';checkpoint()
            print('READY: press only2609 physical RESET; keep USB connected. Receiver selects B; no flash writes.',flush=True)
            face=evidence('physical-startup',until(trial.transport.CHOICES,seconds=180))
            assert trial.transport.IDENTITY in face
            link.send(b'B')
            banner=evidence('MON-B-boot',until(trial.MON,seconds=20));context=trial.MON
            assert b'g00000008' in banner and b'CPU $16' in banner
            assert re.search(rb'g00000008 / (?:MON )?B\r\n',banner)
            report['physical_MON_B_boot']=True;borrowed=True
            mark(application_RAM_restore_pending=True)
            assert dump(0x200,0x66ff)==ram and dump(0,0xdf)==zp
            report['ROM_startup_owner_RAM_ZP_unchanged']=True
            for text in ('V','?','M1','W','APPS','TIME'):
                output=command(text)
                if text=='TIME':assert re.search(rb'20\d\d-\d\d-\d\d',output)
            report['checks'].append('physical-B-boot-owner-preservation-identity-map-wear-TIME-APPS')
            checkpoint()
            link.send(b'CLOCK\r');context=None
            clock=evidence('CLOCK',until(b'CLOCK> '));context=b'CLOCK> '
            assert b'CLOCK BASE1 / PR05' in clock
            command('R');command('Q',trial.MON);context=trial.MON
            link.send(b'MAINT LOAD\r');context=None
            tools=evidence('MAINT-LOAD',until(trial.WB));context=trial.WB
            assert b'WORKBENCH WB2 g00000005' in tools
            command('EDU ON');sram=command('SRAM')
            if b'SSRAM error $01' in sram:
                prep=command('SRAM PREP');assert b'Disabled CB flags acknowledged' in prep
                sram=command('SRAM')
            assert b'SSRAM PROGRAM:' in sram
            table=command('T P');assert b'P:slot/kind#seq' in table
            batch=command('BATCH T;T');assert b'BATCH done' in batch and b'BATCH stopped' not in batch
            bad=command('BATCH T;;T');assert b'BATCH done' not in bad
            name='NF30TEST';assert name.encode() not in table
            command('R P '+name+' L')
            link.send(('S P AUTO 3000 3007 '+name+'\r').encode())
            preview=evidence('AUTO-preview',until(b'type YES> '))
            assert b'Target PROGRAM' in preview
            canceled=command('NO');assert b'Canceled; no record written' in canceled
            command('Q',trial.MON);context=trial.MON
            report['checks'].append('board-loaded-CLOCK-MAINT-g5-PROGRAM-BATCH-AUTO-NO-Q')
            report['PROGRAM_AUTO_canceled_without_write']=True;checkpoint()
            command('Q',trial.REC);context=trial.REC
            readback()
            for bank in range(4):
                body=client.flash(bank);(folder/f'final-B{bank}.bin').write_bytes(body)
                assert body==(INSTALL/f'after-B{bank}.bin').read_bytes()
            report['all_banks_expected']=True
        finally:
          try:
            if borrowed:
                if context==b'CLOCK> ':
                    command('Q',trial.MON);context=trial.MON
                if context==trial.WB:
                    command('Q',trial.MON);context=trial.MON
                if context==trial.MON:
                    command('Q',trial.REC);context=trial.REC
                if context==trial.REC:readback()
                if context==b'RAM SERVICE BASE1> ':
                    report.update(client.restore_owner(ram,zp));report['owner_RAM_restored']=True;context=trial.REC
                else:raise RuntimeError('No admitted restoration prompt; preserve power')
          finally:
            if link is not None:link.close();report['COM8_released']=True
            mark(feature_boot_worker_active=False,application_RAM_restore_pending=borrowed and not report['owner_RAM_restored'],
                 application_ram_restored=report['owner_RAM_restored'] if borrowed else True,
                 block_snapshot=True,last_MON_feature_boot=str(folder/'report.json'))
            report['final_context']=context.decode() if context else None;checkpoint()
      assert report['physical_MON_B_boot'] and report['all_banks_expected'] and report['owner_RAM_restored']
      report.update(passed=True,phase='BOOT_AND_FEATURES_VERIFIED_RTC_ADMISSION_PENDING',finished_utc=utc())
      checkpoint()
      final=dict(installed,physical_boot_and_features=report,passed=True,
          original_owner_RAM_ZP_restored_and_verified=True,final_context='REC>',
          final_receipt_utc=utc(),boot_report=str(folder/'report.json'))
      save(INSTALL/'final-receipt.json',final)
      mark(feature_install_boot_pending=False,firmware_verification_pending=False,
           monitor_generation='00000008',last_preservation_report=str(INSTALL/'final-receipt.json'),
           state='BASE1-MON-B-g8-tools-g5-accepted',final_prompt='REC>',block_snapshot=True)
      print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
      report.update(error=repr(error),finished_utc=utc());checkpoint();raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    run(p.parse_args().folder)
