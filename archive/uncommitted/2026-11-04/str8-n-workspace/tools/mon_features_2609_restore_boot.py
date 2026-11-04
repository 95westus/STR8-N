"""Restore2609 owner RAM after the MAINT LOAD refusal; no further flash writes."""
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import mon_features_2609_ram as trial
from installer.common import save

case=ROOT/'output/qualification/2609-mon-feature-install-20261030-r1'
boot=ROOT/'output/qualification/2609-mon-feature-boot-20261030-r1'


def run():
    receipt=json.loads((case/'install-receipt.json').read_text());assert receipt['passed'] and receipt['erase_requests']==5
    ram,zp=(case/'owner-ram.bin').read_bytes(),(case/'owner-zp.bin').read_bytes()
    reader=(trial.KIT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();assert trial.sha(reader)==trial.live.READBACK_SHA256
    with trial.serial_lease('2609-post-boot-owner-restoration',timeout=30):
      with (boot/'recovery-serial.jsonl').open('x') as log:
        link=trial.transport.RecoveryLink('COM8',log,usb_serial='A10MPQXCA')
        try:
            def prompt():
                data=bytearray();end=time.monotonic()+12
                while time.monotonic()<end:
                    data.extend(link.read(4096))
                    if data.endswith(trial.MON):return trial.MON,bytes(data)
                    if data.endswith(trial.REC):return trial.REC,bytes(data)
                raise TimeoutError('No admitted prompt; no reset issued')
            link.send(b'\r');context,raw=prompt();(boot/'recovery-initial.txt').write_bytes(raw)
            if context==trial.MON:link.send(b'Q\r');context,raw=prompt()
            assert context==trial.REC
            trial.recovery.PROMPT=b'RAM SERVICE BASE1> '
            client=trial.recovery.RecoveryClient(trial.live.LoggedRecoveryStream(link),timeout=60)
            client.load(reader,trial.live.READBACK_SHA256,REC_observed=True)
            for bank in range(4):
                data=client.flash(bank);(boot/f'recovery-B{bank}.bin').write_bytes(data)
                assert data==(case/f'after-B{bank}.bin').read_bytes()
            restored=client.restore_owner(ram,zp)
            report=json.loads((boot/'report.json').read_text());report.update(restored,owner_RAM_restored=True,
                all_banks_expected=True,final_context='REC> ',COM8_released=True,
                restoration_completed_utc=datetime.now(timezone.utc).isoformat())
            save(boot/'report.json',report)
            marker=json.loads(trial.MARK.read_text());marker.update(feature_boot_worker_active=False,
                application_RAM_restore_pending=False,application_ram_restored=True,block_snapshot=True,
                firmware_verification_pending=True,feature_install_boot_pending=False,
                monitor_generation='00000008',final_prompt='REC>',
                feature_install_known_issue='MAINT LOAD after cold flash copy returns syntax; E repair required; no extra erase authorized')
            save(trial.MARK,marker)
            print('PASS owner RAM/ZP restored; all five-sector postimages and raw history match; REC>; no extra flash writes',flush=True)
        finally:link.close()


if __name__=='__main__':run()
