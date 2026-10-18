"""Arm read-only stock debugger before owner RESET; verify source and restore RAM without EXEC."""
import argparse,json,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link
from bf1_2512_stock_ram_restore import restore
from rtc_boards import SERIALS
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';sha=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--retry-after-owner-reset',action='store_true');a=ap.parse_args()
    stage=read(a.stage/'report.json');assert stage['passed'] and stage['physical_reset_pending'] and stage['phase']=='wdcmonv2-stage-source'
    plan=Path(stage['plan']);assert sha(plan.read_bytes())==stage['plan_sha256'];info=read(plan);marker=Q/'device-operations/2512.json'
    if a.retry_after_owner_reset:
        previous=Path(read(marker)['run'])/'report.json';failed=read(previous)
        assert read(marker)['state']=='inspection-required' and not failed['passed'] and not failed['execution_requested'] and 'SerialTimeoutException: Write timeout' in failed['failure']
        assert failed['stage_report_sha256']==sha((a.stage/'report.json').read_bytes())
    else:assert read(marker)['state']=='reset-required-historical-wdc'
    ports=[p for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1;assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board='2512',passed=False,stage_report_sha256=sha((a.stage/'report.json').read_bytes()),started_utc=datetime.now(timezone.utc).isoformat(),persistent_writes=False,execution_requested=False,clock_set=False,trim_changed=False)
    publish(a.out/'report.json',report)
    with (a.out/'serial.jsonl').open('x') as log:
        # The existing read-only WDC binary probe uses no CTS gating. On this
        # FT245 route CTS can block host sync before RESET; retain that failed
        # receipt and use the established no-flow identity-probe transport.
        link=Link(ports[0].device,log,stock=False)
        report.update(rtscts=False,rts=False,cts_at_open=link.serial.cts,transport_source_sha256=sha(Path(__file__).read_bytes()));publish(a.out/'report.json',report)
        try:
            print('ARMED stock debugger; owner physical RESET on 2512 only within 300 seconds',flush=True)
            identity=link.stock_info_after_reset(seconds=300);(a.out/'stock-identity.bin').write_bytes(identity);assert identity[:4]==b'SXB2'
            for n in range(2):
                b3=link.stock_read(0x8000,32768);(a.out/f'b3-{n}.bin').write_bytes(b3);assert sha(b3)==info['expected_sha256'][3],'Historical B3 differs; no migration execution permitted'
            original=Path(stage['fresh_backup'])/'application-ram-original.bin';receipt=restore(link,original.read_bytes());publish(a.out/'RAM-restoration.json',receipt)
            publish(a.stage/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(original.read_bytes()),receipt=str((a.out/'RAM-restoration.json').resolve())))
            report.update(passed=True,source_boot_identity=identity.hex(),expected_b3_sha256=info['expected_sha256'][3],application_ram_restored=True,finished_utc=datetime.now(timezone.utc).isoformat());publish(a.out/'report.json',report)
            publish(marker,dict(board='2512',state='historical-wdc-verified',run=str(a.out.resolve()),block_snapshot=True,reason='Stock debugger active; normal RTC collector incompatible',application_ram_restored=True));print('PASS physical WDC identity, double B3 read and full application RAM restoration; port released',flush=True)
        except BaseException:
            report['failure']=traceback.format_exc();publish(a.out/'report.json',report);publish(marker,dict(board='2512',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:link.serial.close()
if __name__=='__main__':main()
