"""Owner-reset source/final boot checks without host flash/RAM dumps."""
import argparse,json,hashlib,sys,time
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';PLANS=Q/'bf1-empty-bank-tests-2026-10-18-r1'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install',type=Path,required=True);p.add_argument('--mode',choices=('stock','bf1-source','beta4','bf1-final'),required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    installed=read(a.install/'report.json');board=installed['board'];assert board in ('2604','2609') and installed['passed'] and installed['transaction_device_verified']
    marker=Q/'device-operations'/f'{board}.json';guard=read(marker);assert guard['state']=='empty-bank-reset-required' and Path(guard['run']).resolve()==a.install.resolve()
    prep=read(PLANS/'preparation.json');kit=Path(prep['kit']);sys.path.insert(0,str(kit));import legacy_transport as wire
    ports=[p for p in comports() if p.serial_number==SERIALS[board]];assert len(ports)==1 and ports[0].device==installed['port']
    assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board=board,passed=False,mode=a.mode,install_report_sha256=sha(a.install/'report.json'),expected_hashes=installed['expected_hashes'],host_memory_readbacks=False,clock_trim_changes=False)
    publish(a.out/'report.json',report)
    with (a.out/'serial.jsonl').open('x') as log:
        link=wire.Link(ports[0].device,log,stock=a.mode=='stock')
        try:
            if a.mode=='stock':
                assert board=='2609'
                publish(marker,dict(board=board,state='empty-bank-stock-debugger-armed',run=str(a.install.resolve()),block_snapshot=True))
                print('ARMED 2609 read-only original WDC debugger; press RESET within four minutes',flush=True)
                identity=link.stock_info_after_reset(seconds=240);assert identity[:4]==b'SXB6'
                report.update(stock_identity=identity.hex(),empty_B0_B1_B2_device_verified_before_RESET=True)
            else:
                establish_b3(link)
                if a.mode=='beta4':text=link.command('P')
                else:
                    link.send(b'VERSION\r')
                    text=link.until(('Board: '+board).encode())+link.until(b'\r\nB3> ')
                (a.out/'version.txt').write_bytes(text)
                if a.mode=='beta4':assert b'Preferred A 0000000D' in text
                else:assert b'2.0bf1' in text and ('Board: '+board).encode() in text
                if a.mode=='bf1-final':
                    text=link.command('T 1');(a.out/'stored-apps.txt').write_bytes(text);assert b'UCHESS' in text
                    link.send(b'R 1 UCHESS\r');game=link.until(b'Microchess Copyright',30)
                    time.sleep(.2);link.send(b'Q');game+=link.until(b'\r\nB3> ',30);(a.out/'uchess.txt').write_bytes(game)
                    establish_b3(link)
                    link.send(b'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q\r')
                    text=link.until(b'BATCH done',60)+link.until(b'\r\nB3> ')
                    (a.out/'native-batch.txt').write_bytes(text)
                    # Observe only. Do not sync or change a source-affected RTC.
                    text=link.command('R CLOCK',b'CLOCK> ');text+=link.command('STATUS',b'CLOCK> ');text+=link.command('Q');(a.out/'clock-status.txt').write_bytes(text)
                    report.update(UCHESS_discovered_executed_and_returned=True,native_app_Batch_passed=True,RTC_status_observed_without_setters=True)
                    archive=(Q/'bf1-powered-soak-2604-2026-10-17-r1' if board=='2604' else Q/'2609-windows-migration-backup-2026-10-18-r1')/'restore-application-ram.s19'
                    link.send(b'L\r');time.sleep(.2)
                    for row in archive.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
                    result=link.until(b'\r\nB3> ',60);assert b'Entry 0200' in result and not any(v in result for v in (b'Bad',b'Protected',b'Wrap',b'Error'))
                    report.update(application_RAM_archive_written=True,loader_acknowledged=True,host_RAM_restoration_verified=False)
            report.update(passed=True,boot_identity_verified=True,finished_utc=datetime.now(timezone.utc).isoformat());publish(a.out/'report.json',report)
        finally:link.serial.close()
    publish(marker,dict(board=board,state=('empty-bank-stock-debugger-connected' if a.mode=='stock' else 'empty-bank-final-bf1-tested' if a.mode=='bf1-final' else 'empty-bank-source-boot-checked'),
        run=str(a.out.resolve()),stock_probe=str(a.out.resolve()) if a.mode=='stock' else None,block_snapshot=True,RTC_sampling_owner_stopped=True))
    print('PASS',board,a.mode,'boot/checks; no host memory readbacks',flush=True)

if __name__=='__main__':main()
