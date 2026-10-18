"""Install/check the CPU-qualified narrow UTC update on an authorized rc1 board."""
import argparse,hashlib,json,re,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from atomic_json import publish
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';RUN=Q/'rc1-utc-2609-2604-hardware-2026-10-18-r4';BASE=Q/'rc1-utc-2609-2604-hardware-2026-10-18-r2';read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
def guards():
    active=read(Q/'active-rtc-campaign.json');state=read(Path(active['campaign_state']));assert set(active['powered_off_boards'])=={'2205','2512'} and not state['soak_active'] and not state['RTC_sampling_active'] and not state['automatic_workload_restart_permitted'];return active,state
def run(board):
    guards();prep=read(RUN/'preparation.json');proof=read(RUN/'CPU-report.json');info=read(RUN/board/'build.json');updater=RUN/board/'updater.s19'
    assert proof['passed'] and proof['full_return_paths_tested'] and sha(updater.read_bytes())==proof['source_build_hashes'][board]==info['s19_sha256']
    kit=Path(prep['package'])/'migration';sys.path.insert(0,str(kit));import migrate;import legacy_transport as wire
    migrate.verify_kit(kit);plan=read(BASE/(board+'-utc')/'plan.json');archive=Path(plan['RAM_archive']);assert sha(archive.read_bytes())==plan['RAM_archive_sha256']
    marker=Q/'device-operations'/f'{board}.json';oldmarker=read(marker);assert oldmarker['state']==('inspection-required' if board=='2609' else 'rc1-both-slots-and-apps-passed')
    if board=='2609':assert read(RUN/'owner-reset-2609.json')['user_confirmed_physical_reset']
    from serial.tools.list_ports import comports
    ports=[p for p in comports() if p.serial_number==SERIALS[board]];assert len(ports)==1
    out=RUN/board/'hardware';out.mkdir(exist_ok=False);report=dict(board=board,version='2.0rc1',generation=49,package_revision=2,passed=False,published_zip_sha256=prep['published_zip_sha256'],updater_sha256=info['s19_sha256'],host_memory_readbacks=False,clock_set=False,trim_changed=False,soak_resumed=False,RTC_sampling_resumed=False,last_known_RAM_archive=str(archive),RAM_archive_sha256=sha(archive.read_bytes()),started_utc=datetime.now(timezone.utc).isoformat())
    def save():publish(out/'report.json',report)
    def mark(state):publish(marker,dict(board=board,state=state,run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True,soak_owner_stopped=True))
    save()
    with serial_lease('owner-rc1-UTC-sector-'+board,timeout=60,priority=True):
        guards();assert read(marker)==oldmarker;mark('rc1-utc-sector-checking')
        with (out/'serial.jsonl').open('x') as log:
            link=wire.Link(ports[0].device,log)
            def cmd(s,prompt=b'\r\nB3> ',timeout=60):link.send(s.encode()+b'\r');return link.until(prompt,timeout)
            def load(path,entry):
                cmd('L',b'S19')
                for line in path.read_bytes().splitlines():link.send(line+b'\r\n');time.sleep(.04)
                t=link.until(b'\r\nB3> ',90);assert f'Entry {entry:04X}'.encode() in t and not any(v in t for v in (b'Bad',b'Protected',b'Wrap',b'Error')),t
                return t
            def clock(stem):
                t=cmd('R CLOCK',b'CLOCK> ')+cmd('STATUS',b'CLOCK> ')+cmd('Q');(out/(stem+'-clock.txt')).write_bytes(t)
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode());assert len(raw)>=9;return raw
            def mode(stem):
                folder=ROOT/'tmp/rc1mode1';pin=read(folder/'report.json');assert pin['passed'] and sha((folder/'mode.s19').read_bytes())==pin['s19_sha256'];load(folder/'mode.s19',0x2000);text=cmd('G 2000');(out/(stem+'-mode.txt')).write_bytes(text);rows=re.findall(rb'(?:[0-9A-F]{2} ){13}[0-9A-F]{2}',text);assert len(rows)==1,text;raw=bytes.fromhex(rows[0].decode());cpu=0x16 if board=='2609' else 2
                assert raw[0]==cpu and raw[2:6]==bytes(4) and raw[6]&12==4 and raw[7:11]==bytes.fromhex('01170401') and raw[11]==cpu and raw[12]&1 and not raw[12]&8 and raw[13]==0xa5
                if board=='2609':assert raw[1]==1,'816 was not already in emulation mode'
                return raw.hex()
            def version(stem):
                t=cmd('VERSION');(out/(stem+'-version.txt')).write_bytes(t);assert b'2.0rc1' in t and ('Board: '+board).encode() in t and (b'65C816' if board=='2609' else b'65C02') in t
                for slot in ('A','B'):assert ('MONITOR '+slot+' gen 00000031 VALID').encode() in t
                return t
            try:
                establish_b3(link);version('before');cfg=cmd('C');pref=cmd('P');(out/'config-before.txt').write_bytes(cfg);(out/'preference-before.txt').write_bytes(pref);(out/'wear-before.txt').write_bytes(cmd('W'));before=clock('before');report['RTC_before_raw']=before.hex()
                publish(out/'restore-needed.json',dict(needed=True,archive=str(archive),archive_sha256=report['RAM_archive_sha256'],last_known_archive=True,host_readback_requested=False));report['CPU_before']=mode('before');save()
                load(updater,0x2000);mark('rc1-utc-sector-updating');report['updater_execution_started']=True;save();result=cmd('G 2000',timeout=90);(out/'update-result.txt').write_bytes(result)
                assert b'UTC UPDATE VERIFIED  [power-fail UTC]' in result,result
                report.update(device_sector_verified=True,static_firmware_and_live_worker_pins_passed=True,UTC_label_verified_from_flash=True,dynamic_journals_accounted_by_firmware=True);save()
                version('after');assert cmd('C')==cfg and cmd('P')==pref,'Configuration/preference changed'
                (out/'wear-after.txt').write_bytes(cmd('W'));apps=cmd('APPS');table=cmd('T 1');(out/'apps.txt').write_bytes(apps);(out/'table.txt').write_bytes(table);assert b'ASM' in apps and b'UCHESS' in table and b'CLOCK' in table
                (out/'time-query.txt').write_bytes(cmd('TIME'));after=clock('after');assert after[7:9]==before[7:9] and after[0]&0x80==before[0]&0x80 and after[3]&8==before[3]&8,'RTC control/trim/oscillator/backup changed'
                report['RTC_after_raw']=after.hex();report['CPU_after']=mode('after');restored=load(archive,0x0200);(out/'RAM-restore-loader.txt').write_bytes(restored)
                clear=dict(needed=False,loader_acknowledged=True,host_verified=False,archive=str(archive),archive_sha256=report['RAM_archive_sha256'],last_known_archive=True);publish(out/'restore-needed.json',clear)
                if board=='2609':
                    for pending in (BASE/'2609-install/restore-needed.json',Q/'rc1-utc-2609-2604-hardware-2026-10-18-r3/2609/hardware/restore-needed.json'):
                        if pending.exists():
                            previous=read(pending);assert previous['archive_sha256']==report['RAM_archive_sha256']
                            publish(pending,dict(clear,recovered_by=str(out),prior_attempt_evidence_retained=True))
                report.update(passed=True,config_and_preference_unchanged=True,both_monitor_slots_valid=True,apps_discovered=True,RAM_loader_acknowledged=True,host_RAM_restoration_verified=False,ports_released=True,physical_reset_pending=False,finished_utc=datetime.now(timezone.utc).isoformat());save()
                publish(marker,dict(board=board,state='rc1-utc-label-passed',run=str(out),block_snapshot=True,RTC_sampling_owner_stopped=True,soak_owner_stopped=True,firmware='2.0rc1 generation49 package revision2',preferred_monitor=('A' if b'Preferred A' in pref else 'B')))
                print('PASS',board,'[power-fail UTC] verified in flash; MON A/B valid, settings/RTC unchanged, RAM archive loader acknowledged; no RESET required',flush=True)
            except BaseException:
                report['failure']=traceback.format_exc();save();mark('inspection-required');raise
            finally:link.serial.close()
def close():
    active,state=guards();boards={};prior=read(Q/'rc1-hardware-current.json')
    for b in ('2609','2604'):
        p=RUN/b/'hardware/report.json';r=read(p);assert r['passed'] and r['device_sector_verified'] and r['UTC_label_verified_from_flash'] and r['RAM_loader_acknowledged'] and not r['physical_reset_pending'];assert not read(RUN/b/'hardware/restore-needed.json')['needed']
        def counts(name):
            text=(RUN/b/'hardware'/name).read_bytes();rows=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',text);assert len(rows)==32
            return {(int(bank),int(sector,16)):int(value,16) for bank,sector,value in rows}
        before=counts('wear-before.txt');after=counts('wear-after.txt');expected=dict(before);expected[3,8]+=1;assert after==expected,'Unexpected erase-attempt counter change'
        boards[b]=dict(report=str(p),sha256=sha(p.read_bytes()),version='2.0rc1',generation=49,package_revision=2,UTC_label_hardware_verified=True,both_monitor_slots_valid=True,clocks_trims_settings_unchanged=True,saved_RAM_loader_acknowledged=True,host_RAM_readback_verified=False)
        boards[b].update(exactly_one_B3_8_erase_accounted=True,B3_8_count_before=before[3,8],B3_8_count_after=after[3,8],all_other_31_erase_counts_unchanged=True)
        state.setdefault('firmware_current',{})[b]='2.0rc1 generation49 package revision2; power-fail UTC label hardware verified; idle'
    result=dict(passed=True,version='2.0rc1',generation=49,package_revision=2,boards=boards,prior_both_slot_and_all_app_hardware_checkpoint=prior,only_banner_sector_firmware_changed=True,published_zip_sha256=read(RUN/'preparation.json')['published_zip_sha256'],clocks_and_trims_unchanged=True,soaks_and_RTC_sampling_stopped=True,powered_off_boards=['2205','2512'],deferred=['RTC qualification','native 816 applications/tests','ACIA','crypto'],finished_utc=datetime.now(timezone.utc).isoformat())
    publish(RUN/'hardware-checkpoint.json',result);ptr=dict(receipt=str(RUN/'hardware-checkpoint.json'),sha256=sha((RUN/'hardware-checkpoint.json').read_bytes()));publish(Q/'rc1-hardware-current.json',ptr)
    state['rc1_hardware_checkpoint']=ptr['receipt'];state['rc1_hardware_checkpoint_sha256']=ptr['sha256'];publish(Path(active['campaign_state']),state)
    print('PASS both boards now rc1 revision2; soaks/RTC sampling remain stopped',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['install','close']);p.add_argument('--board',choices=['2609','2604']);a=p.parse_args()
    if a.operation=='close':close()
    else:assert a.board;run(a.board)
