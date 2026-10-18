"""Verify paced-probe WDC source and restore original application RAM without executing it."""
import argparse,json,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
from beta4_migration import Link
from bf1_2512_stock_ram_restore import restore
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--identity',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    stage=read(a.stage/'report.json');identity=read(a.identity/'report.json');assert stage['passed'] and identity['passed'] and identity['board']=='2512' and identity['identity_hex']=='535842322c010000c8000000'
    plan=Path(stage['plan']);assert sha(plan)==stage['plan_sha256'];info=read(plan);original=Path(stage['fresh_backup'])/'application-ram-original.bin'
    assert read(a.stage/'restore-needed.json')['sha256']==sha(original)
    marker=Q/'device-operations/2512.json';operation=read(marker);assert operation['block_snapshot']
    assert operation['state']=='inspection-required' or (operation['state']=='legacy-reset-required' and operation['phase']=='wdcmonv2-restore-historical-source')
    ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1;assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board='2512',passed=False,source_stage_report_sha256=sha(a.stage/'report.json'),identity_report_sha256=sha(a.identity/'report.json'),started_utc=datetime.now(timezone.utc).isoformat(),persistent_writes=False,execution_requested=False,clocks_trims_unchanged=True,transport='115200, DTR=0, RTS=1, CTS gating off; purge stale host queue once')
    def save():publish(a.out/'report.json',report)
    save()
    with (a.out/'serial.jsonl').open('x') as log:
      link=Link(ports[0],log,stock=False);link.serial.rts=True;link.serial.reset_output_buffer();link.serial.reset_input_buffer()
      try:
        link.protocol(12);actual=link.exact(12);assert actual.hex()==identity['identity_hex']
        for n in range(2):
            data=link.stock_read(0x8000,32768);(a.out/f'b3-{n}.bin').write_bytes(data);assert sha(a.out/f'b3-{n}.bin')==info['expected_sha256'][3];print('PASS exact WDC B3',n,flush=True)
        receipt=restore(link,original.read_bytes());publish(a.out/'RAM-restoration.json',receipt)
        report.update(passed=True,application_ram_restored=True,expected_b3_sha256=info['expected_sha256'][3],finished_utc=datetime.now(timezone.utc).isoformat());save()
        publish(a.stage/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(original),receipt=str((a.out/'RAM-restoration.json').resolve())))
        publish(marker,dict(board='2512',state='historical-wdc-verified',run=str(a.out.resolve()),transaction=str(a.stage.resolve()),block_snapshot=True,application_ram_restored=True,reason='Stock monitor active; normal RTC collector incompatible'));print('PASS WDC source and full original RAM restored without EXEC',flush=True)
      except BaseException:report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:link.serial.cancel_write();link.serial.reset_output_buffer();link.serial.close()
if __name__=='__main__':main()
