"""Owner-authorized preserving rc1 installation using the downloaded ZIP engine."""
import argparse,hashlib,json,re,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
from atomic_json import publish
from rtc_prompt_sync import establish_b3
from rtc_boards import SERIALS
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-2604-2609-hardware-2026-10-18-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--board',required=True,choices=['2604','2609']);a=ap.parse_args();board=a.board
    prep=read(RUN/'preparation.json');assert prep['passed'] and read(RUN/'owner-authorization.json')['owner_authorized'];package=Path(prep['package']);kit=package/'migration';sys.path.insert(0,str(kit));import migrate;import legacy_transport as wire;import install_transport as engine
    migrate.verify_kit(kit);assert sha((kit/'kit-manifest.json').read_bytes())==prep['kit_manifest_sha256']
    folder=RUN/(board+'-published-rc1');plan=read(folder/'plan.json');assert sha((folder/'plan.json').read_bytes())==prep['plans'][folder.name]
    check=next(c for c in read(RUN/'CPU-report.json')['checks'] if c['name']==folder.name);assert check['passed'] and check['plan_sha256']==prep['plans'][folder.name] and check['installer_sha256']==plan['installer_sha256']
    active=read(Q/'active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert not state['soak_active'] and not state['RTC_sampling_active'] and set(active['powered_off_boards'])=={'2205','2512'}
    marker=Q/'device-operations'/f'{board}.json';assert read(marker)['state']=='empty-bank-final-bf1-tested'
    archive=Q/('bf1-powered-soak-2604-2026-10-17-r1' if board=='2604' else '2609-windows-migration-backup-2026-10-18-r1')/'restore-application-ram.s19';assert archive.is_file()
    out=RUN/(board+'-install');out.mkdir(exist_ok=False)
    from serial.tools.list_ports import comports
    matches=[p for p in comports() if p.serial_number==SERIALS[board]];assert len(matches)==1;port=matches[0].device
    report=dict(board=board,version='2.0rc1',generation=49,passed=False,port=port,usb_serial=SERIALS[board],published_zip_sha256=prep['published_zip_sha256'],plan_sha256=sha((folder/'plan.json').read_bytes()),source_hashes=plan['source_sha256'],expected_hashes=plan['expected_sha256'],original_preferred_page=plan['original_preferred_page'],packaged_engine_sha256=sha((kit/'install_transport.py').read_bytes()),transfers_completed=0,host_memory_readbacks=False,device_full_source_preflight=True,clock_set=False,trim_changed=False,EEPROM_SRAM_written=False,RAM_archive=str(archive),RAM_archive_sha256=sha(archive.read_bytes()),physical_reset_pending=False,started_utc=datetime.now(timezone.utc).isoformat())
    def save():publish(out/'report.json',report)
    save()
    with serial_lease('owner-published-rc1-'+board,timeout=60,priority=True):
        assert read(marker)['state']=='empty-bank-final-bf1-tested';publish(marker,dict(board=board,state='rc1-installing',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True))
        with (out/'serial.jsonl').open('x') as log:
            link=wire.Link(port,log)
            try:
                establish_b3(link);link.send(b'VERSION\r');text=link.until(('Board: '+board).encode())+link.until(b'\r\nB3> ');(out/'version-before.txt').write_bytes(text)
                assert b'2.0bf1' in text and ('Board: '+board).encode() in text and (b'65C816' if board=='2609' else b'65C02') in text,text
                (out/'preference-before.txt').write_bytes(link.command('P'))
                clock=link.command('R CLOCK',b'CLOCK> ')+link.command('STATUS',b'CLOCK> ');clock+=link.command('Q');(out/'clock-before.txt').write_bytes(clock)
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',clock)[1].decode());assert len(raw)>=9;report['rtc_before_raw']=raw.hex();report['rtc_control_before']=raw[7];report['rtc_trim_before']=raw[8];save()
                publish(out/'restore-needed.json',dict(needed=True,archive=str(archive),archive_sha256=report['RAM_archive_sha256'],last_known_archive=True,host_readback_requested=False))
                def progress(n,op):report['transfers_completed']=n;save();print('TRANSFER',board,n,op['bank'],hex(op['address']),flush=True)
                report['installer_execution_may_have_started']=True;save();result=engine.execute(link,folder,stock=False,host_readback=False,progress=progress)
                report.update(result,passed=True,device_target_verified=True,ports_released=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
                publish(marker,dict(board=board,state='rc1-reset-required',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True))
                print('PASS',board,'published rc1 MON A/B installed; four verified transfers; PHYSICAL RESET REQUIRED',flush=True)
            except BaseException:
                report['failure']=traceback.format_exc();report['inspection_required']=True;save();publish(marker,dict(board=board,state='inspection-required',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True));raise
            finally:link.serial.close()
if __name__=='__main__':main()
