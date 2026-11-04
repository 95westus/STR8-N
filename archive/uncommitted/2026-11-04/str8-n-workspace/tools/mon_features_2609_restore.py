"""Restore only the pre-HOLD-hook2609 feature trial; never resets or writes flash."""
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import mon_features_2609_ram as trial
from installer.common import save


def run():
    case = ROOT/'output/qualification/2609-mon-features-ram-20261030-r1'
    report = json.loads((case/'report.json').read_text())
    assert report['board'] == '2609' and not report.get('original_HOLD_jump_hex')
    ram, zp = (case/'owner-ram.bin').read_bytes(), (case/'owner-zp.bin').read_bytes()
    assert len(ram) == 0x6500 and len(zp) == 0xe0
    reader = (trial.KIT/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert trial.sha(reader) == trial.live.READBACK_SHA256
    with trial.serial_lease('2609-owner-RAM-restoration', timeout=30):
      with (case/'recovery-serial.jsonl').open('x') as log:
        link = trial.transport.RecoveryLink('COM8', log, usb_serial='A10MPQXCA')
        try:
            # The preceding Q was sent, but the migration-specific error
            # recognizer rejected its stale REFUSED buffer before reading REC.
            link.send(b'\r')
            def prompt():
                data=bytearray();deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    data.extend(link.read(4096))
                    if data.endswith(trial.REC):return trial.REC,bytes(data)
                    if data.endswith(trial.MON):return trial.MON,bytes(data)
                raise TimeoutError('No admitted idle prompt; no reset issued')
            context,raw=prompt();(case/'recovery-initial.txt').write_bytes(raw)
            if context == trial.MON:
                link.send(b'Q\r');context,raw=prompt()
            assert context == trial.REC
            trial.recovery.PROMPT=b'RAM SERVICE BASE1> '
            client=trial.recovery.RecoveryClient(trial.live.LoggedRecoveryStream(link),timeout=60)
            client.load(reader,trial.live.READBACK_SHA256,REC_observed=True)
            for bank in (3,0,1,2):
                data=client.flash(bank)
                (case/f'recovery-b{bank}.bin').write_bytes(data)
                assert data == (case/f'before-1-b{bank}.bin').read_bytes()
            restored=client.restore_owner(ram,zp)
            report.update(restored,owner_RAM_restored=True,all_flash_banks_unchanged=True,
                          final_context='REC> ',port_released=True,
                          recovery_completed_utc=datetime.now(timezone.utc).isoformat(),
                          recovery_note='Expected-refusal host recognizer corrected; HOLD was never patched; no reset or flash write.')
            save(case/'report.json',report)
            marker=json.loads(trial.MARK.read_text());before=json.loads((case/'marker-before.json').read_text())
            marker.update(feature_readiness_worker_active=False,application_RAM_restore_pending=False,
                          application_ram_restored=True,block_snapshot=before['block_snapshot'])
            save(trial.MARK,marker)
            print('PASS: all banks unchanged, owner RAM/ZP restored, REC>, COM8 released',flush=True)
        finally:
            link.close()


if __name__=='__main__':run()
