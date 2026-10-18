"""Check both published rc1 slots/apps, preserve RTC controls and restore RAM."""
import argparse,hashlib,json,re,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from atomic_json import publish
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-2604-2609-hardware-2026-10-18-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--board',required=True,choices=['2604','2609']);p.add_argument('--reset-confirmation',required=True,type=Path);a=p.parse_args();board=a.board
    confirmation=read(a.reset_confirmation);assert confirmation['user_confirmed_physical_reset'] and board in confirmation['boards']
    assert read(RUN/'observer-and-slot-switch-model.json')['passed']
    installed=read(RUN/(board+'-install/report.json'));assert installed['passed'] and installed['transaction_device_verified'] and installed['physical_reset_pending']
    prep=read(RUN/'preparation.json');kit=Path(prep['package'])/'migration';sys.path.insert(0,str(kit));import migrate;import legacy_transport as wire
    migrate.verify_kit(kit);assert sha((kit/'kit-manifest.json').read_bytes())==prep['kit_manifest_sha256']
    active=read(Q/'active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert not state['soak_active'] and not state['RTC_sampling_active'] and set(active['powered_off_boards'])=={'2205','2512'}
    marker=Q/'device-operations'/f'{board}.json';assert read(marker)['state']=='rc1-reset-required'
    archive=Path(installed['RAM_archive']);assert sha(archive.read_bytes())==installed['RAM_archive_sha256']
    from serial.tools.list_ports import comports
    matches=[p for p in comports() if p.serial_number==SERIALS[board]];assert len(matches)==1 and matches[0].device==installed['port']
    out=RUN/(board+'-checks');out.mkdir(exist_ok=False);report=dict(board=board,version='2.0rc1',generation=49,passed=False,slots={},published_zip_sha256=prep['published_zip_sha256'],host_memory_readbacks=False,clock_set=False,trim_changed=False,RTC_sampling_resumed=False,soak_resumed=False,EPROM_SRAM_written=False,checks=[],started_utc=datetime.now(timezone.utc).isoformat())
    def save():publish(out/'report.json',report)
    save()
    preferred='A' if installed['original_preferred_page']==0xa0 else 'B';order=[preferred,'B' if preferred=='A' else 'A']
    with serial_lease('owner-rc1-check-'+board,timeout=60,priority=True):
        publish(marker,dict(board=board,state='rc1-checking',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True))
        with (out/'serial.jsonl').open('x') as log:
            link=wire.Link(matches[0].device,log)
            def command(text,prompt=b'\r\nB3> ',timeout=45):link.send(text.encode()+b'\r');return link.until(prompt,timeout)
            def version(slot,stem):
                link.send(b'VERSION\r');text=link.until(('Board: '+board).encode())+link.until(b'\r\nB3> ');(out/(stem+'-version.txt')).write_bytes(text)
                assert b'2.0rc1' in text and b'00000031' in text and ('Running: MONITOR '+slot).encode() in text and (b'65C816' if board=='2609' else b'65C02') in text,text
                return text
            def load(path):
                command('L',b'S19')
                for row in path.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
                text=link.until(b'\r\nB3> ',90);assert b'Entry 2000' in text and not any(v in text for v in (b'Bad',b'Protected',b'Wrap',b'Error')),text
            def mode(stem):
                folder=ROOT/'tmp/rc1mode1';pin=read(folder/'report.json');assert pin['passed'] and sha((folder/'mode.s19').read_bytes())==pin['s19_sha256'];load(folder/'mode.s19');text=command('G 2000');(out/(stem+'-mode.txt')).write_bytes(text)
                rows=re.findall(rb'(?:[0-9A-F]{2} ){13}[0-9A-F]{2}',text);assert len(rows)==1,text;raw=bytes.fromhex(rows[0].decode())
                cpu=0x16 if board=='2609' else 2;assert raw[0]==cpu and raw[2:6]==bytes(4) and raw[6]&0x0c==4 and raw[7:11]==bytes.fromhex('01170401') and raw[11]==cpu and raw[12]&1 and not raw[12]&8 and raw[13]==0xa5
                if board=='2609':assert raw[1]==1,'816 runtime was not E=1 before the probe'
                return dict(cpu='65C816 E=1' if board=='2609' else '65C02',zero_DBR_PBR_direct_page=True,IRQ_disabled=True,decimal_clear=True,native_mode_entered=False,result=raw.hex())
            def clock(stem):
                text=command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.11' in text;text+=command('STATUS',b'CLOCK> ');text+=command('Q');(out/(stem+'-clock.txt')).write_bytes(text)
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode());before=bytes.fromhex(installed['rtc_before_raw']);assert raw[7:9]==before[7:9] and raw[0]&0x80==before[0]&0x80 and raw[3]&8==before[3]&8,'RTC control/trim/oscillator/backup changed'
                return dict(control=raw[7],trim_register=raw[8],oscillator_start_unchanged=True,backup_enable_unchanged=True,raw=raw.hex())
            try:
                establish_b3(link)
                for index,slot in enumerate(order):
                    if index:
                        text=command('P '+slot);assert ('Preferred '+slot+' 00000031').encode() in text,text
                        text=command('J3',timeout=60);assert b'2.0rc1' in text
                        establish_b3(link)
                    version(slot,slot);slot_result=dict(version_identity=True,cpu_before=mode(slot+'-before'))
                    apps=command('APPS');(out/(slot+'-apps.txt')).write_bytes(apps);assert b'ASM' in apps
                    table=command('T 1');(out/(slot+'-table.txt')).write_bytes(table);assert b'UCHESS' in table and b'CLOCK' in table
                    link.send(b'R 1 UCHESS\r');game=link.until(b'Microchess Copyright',30);time.sleep(.3);link.send(b'Q');game+=link.until(b'\r\nB3> ',30);(out/(slot+'-uchess.txt')).write_bytes(game);assert b'Peter Jennings' in game
                    text=command('ASM',b'ASM> ');assert b'ASM 0.5' in text
                    for cmd in ('NEW','10 ORG $0200',"20 LDA #'R'",'30 JSR $7E6D','40 JMP $7E67','ASM','S19'):
                        answer=command(cmd,b'ASM> ');text+=answer
                        if cmd=='ASM':assert b'OK 8 bytes' in answer
                    text+=command('QUIT');text+=command('G 0200');(out/(slot+'-asm.txt')).write_bytes(text);assert b'R\r\nB3> ' in text
                    batch=command('BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q',b'BATCH done',90)+link.until(b'\r\nB3> ');assert b'BATCH stopped' not in batch
                    batch+=command('BATCH R CLOCK;STATUS;Q',b'BATCH done',90)+link.until(b'\r\nB3> ');assert b'CLOCK 1.11' in batch and b'BATCH stopped' not in batch;(out/(slot+'-batch.txt')).write_bytes(batch)
                    slot_result.update(UCHESS_table_game_copyright_HOLD=True,ASM_05_assembly_S19_RAM_execution=True,MAINT_SRAM_WORK_EDU_BATCH=True,CLOCK_111_BATCH=True,RTC=clock(slot),cpu_after=mode(slot+'-after'),passed=True);report['slots'][slot]=slot_result;save();print('PASS',board,'MON',slot,'rc1/app/ASM/UCHESS/BATCH/CPU/unchanged RTC controls',flush=True)
                if order[-1]!=preferred:
                    text=command('P '+preferred);assert ('Preferred '+preferred+' 00000031').encode() in text;command('J3',timeout=60);establish_b3(link)
                version(preferred,'final');report['final_RTC']=clock('final');report['final_CPU']=mode('final');report['final_preferred_monitor']=preferred
                command('L',b'S19')
                for row in archive.read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
                result=link.until(b'\r\nB3> ',90);assert b'Entry 0200' in result and not any(t in result for t in (b'Bad',b'Protected',b'Wrap',b'Error'));(out/'RAM-restore-loader.txt').write_bytes(result)
                report.update(passed=True,both_monitor_slots_passed=True,all_supported_apps_checked=True,application_RAM_archive_loaded=True,RAM_loader_acknowledged=True,host_RAM_restoration_verified=False,ports_released=True,physical_reset_pending=False,finished_utc=datetime.now(timezone.utc).isoformat());save()
                clear=dict(needed=False,loader_acknowledged=True,host_verified=False,archive=str(archive),archive_sha256=installed['RAM_archive_sha256']);publish(out/'restore-needed.json',clear);publish(RUN/(board+'-install/restore-needed.json'),clear)
                publish(marker,dict(board=board,state='rc1-both-slots-and-apps-passed',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True,soak_owner_stopped=True,firmware='2.0rc1 generation49',preferred_monitor=preferred))
                print('PASS',board,'both slots/apps, original preference restored, RAM archive loader acknowledged; workloads remain stopped',flush=True)
            except BaseException:
                report['failure']=traceback.format_exc();save();publish(marker,dict(board=board,state='inspection-required',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True));raise
            finally:link.serial.close()
if __name__=='__main__':main()
