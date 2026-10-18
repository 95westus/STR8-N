"""2604-only bf1 preserving soak. STOP yields and restores all application RAM."""
import argparse,ctypes,json,os,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease,drift_pending
from atomic_json import publish
import bf1_2604_readonly as live
old=live.old;base=live.base;ROOT=old.ROOT;sha=base.sha;read=base.read_json;GROUPS=list(old.GROUPS)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--hardware',type=Path,required=True);ap.add_argument('--cycles',type=int,default=0);a=ap.parse_args()
    hardware=read(a.hardware);assert hardware['passed'] and hardware['board']=='2604' and hardware['phase']=='A' and hardware['active_page']==0xa0 and hardware['initial_checks_passed'] and hardware['full_flash_verified'] and hardware['application_ram_restored']
    backup=ROOT/'output/qualification/2604-return-backup-2026-10-17-1724Z';assert read(backup/'report.json')['passed'] and not read(backup/'restore-needed.json')['needed'];sram=(backup/'sram.bin').read_bytes();eeprom=(backup/'eeprom.bin').read_bytes();assert len(sram)==131072 and len(eeprom)==137
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');index=Path(active['baseline_index']);assert sha(index.read_bytes())==active['baseline_index_sha256'] and set(active['powered_off_boards'])=={'2205','2609'};expected=next(b for b in read(index)['boards'] if b['board']=='2604')
    plan=dict(expected_hashes=hardware['expected_hashes']);page=hardware['active_page']
    for image,digest in [(base.CLIENT,base.CLIENT_HASH),(base.EEPROM,base.EEPROM_HASH)]:
        cells,_=base.read_application_s19(image);assert sha(bytes(cells[i] for i in sorted(cells)))==digest
    assert not a.root.exists();a.root.mkdir(parents=True)
    base.REFERENCE=a.root/'legacy-reference';(base.REFERENCE/'retained/devices-after').mkdir(parents=True);(base.REFERENCE/'retained/devices-after/eeprom-0.bin').write_bytes(eeprom)
    # All module state is private to this worker; the 2512 runner and its files
    # remain unchanged. Reuse read-only units with this board's pinned bytes.
    def port():return next(p.device for p in comports() if p.serial_number==SERIALS['2604'])
    state=dict(board='2604',usb_serial=SERIALS['2604'],candidate_id='batchfix-r1',version='2.0bf1',clock_version='1.11',active_page=page,pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),passed_units=0,completed_cycles=0,groups=GROUPS,baseline_index=str(index),baseline_sha256=sha(index.read_bytes()),hardware_report=str(a.hardware.resolve()),hardware_report_sha256=sha(a.hardware.read_bytes()),flash_reference_hashes=plan['expected_hashes'],sram_reference_sha256=sha(sram),eeprom_reference_sha256=sha(eeprom),runner_sha256=sha(Path(__file__).read_bytes()),adapter_sha256=sha(Path(live.__file__).read_bytes()),led_patterns_sha256=sha((ROOT/'tools/soak_led_patterns.py').read_bytes()),clock_set=False,settings_changed=False,flash_sram_eeprom_writes=False,application_ram_borrowed=True,excluded=['settings/time/trim changes','ACK/CLEAR','flash writes/erase','retained device writes/format','reset','ACIA','crypto'])
    for path in [Path(__file__),Path(live.__file__),Path(old.__file__),Path(base.__file__)]: (a.root/('source-'+path.name)).write_bytes(path.read_bytes())
    publish(a.root/'config.json',state);(a.root/'sram-original.bin').write_bytes(sram)
    def status(phase,**kw):state.update(state=phase,updated=time.time(),**kw);publish(a.root/'status.json',state)
    original=None;assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        status('initializing')
        with serial_lease('bf1-soak-2604',timeout=600):
          with (a.root/'startup.jsonl').open('x') as log:
            link=Link(port(),log)
            try:
                establish_b3(link);live.guards(link,page);captured=old.ram(link);assert captured==old.ram(link),'Unstable application RAM'
                assert captured==(backup/'application-ram-original.bin').read_bytes(),'Initial hardware checks did not restore original application RAM'
                (a.root/'application-ram-original.bin').write_bytes(captured);(a.root/'restore-application-ram.s19').write_bytes(s19(dict(enumerate(captured,0x200)),0x200));publish(a.root/'restore-needed.json',dict(needed=True,first=0x200,last=0x64ff,sha256=sha(captured)));original=captured
            finally:link.serial.close()
        while not a.cycles or state['completed_cycles']<a.cycles:
          for group in GROUPS:
            if (a.root/'STOP').exists():status('stopped-by-request');return
            assert sha(index.read_bytes())==state['baseline_sha256']
            while True:
                if (a.root/'STOP').exists():status('stopped-by-request');return
                if drift_pending():status('yielding-to-drift',group=group);time.sleep(2);continue
                try:
                  with serial_lease('bf1-soak-2604',timeout=2):
                    out=a.root/f"{state['passed_units']:06d}-{group}"
                    with (a.root/'serial.jsonl').open('a') as log:
                      link=Link(port(),log)
                      try:
                        out.mkdir();status('running',group=group);establish_b3(link);live.guards(link,page)
                        result=live.workload(link,group,out,plan,sram,state['completed_cycles'],expected);live.guards(link,page);publish(out/'report.json',dict(passed=True,result=result,finished=time.time()))
                      finally:link.serial.close()
                  break
                except TimeoutError as e:
                    if str(e)!='Serial lease unavailable; no board port opened':raise
                    time.sleep(2)
            state['passed_units']+=1;status('running',group=group);print('PASS',state['passed_units'],group,flush=True);time.sleep(.2)
          state['completed_cycles']+=1;status('running',group=None)
          for _ in range(15):
            if (a.root/'STOP').exists():break
            time.sleep(2)
        status('completed',group=None)
    except BaseException:status('stopped-on-failure',error=traceback.format_exc());raise
    finally:
        try:
          if original is not None:
            with serial_lease('bf1-soak-2604',timeout=600):
              with (a.root/'restore.jsonl').open('a') as log:
                link=Link(port(),log)
                try:establish_b3(link);old.restore(link,a.root/'restore-application-ram.s19',original)
                finally:link.serial.close()
            publish(a.root/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(original)));state['application_ram_restored']=True;publish(a.root/'status.json',state)
        finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
if __name__=='__main__':main()
