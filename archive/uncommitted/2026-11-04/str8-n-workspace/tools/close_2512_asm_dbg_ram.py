"""Seal first BASE1 ASM/DBG RAM acceptance; host metadata only, no port."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';Q=ROOT/'output/qualification'
FIRST=Q/'2512-ASM-DBG-BASE1-RAM-20261102-r1';PASS=Q/'2512-ASM-DBG-BASE1-RAM-20261102-r3';REC=Q/'2512-ASM-help-recovery-20261102-r1';OUT=Q/'2512-ASM-DBG-BASE1-RAM-closeout-20261102-r1'

def run():
 p=c.read(PASS/'report.json');recovery=c.read(REC/'report.json');assert p['passed'] and recovery['passed'] and len(p['checks'])==7
 assert p['owner_RAM_restored'] and p['owner_ZP_restored'] and p['provider_cache_restored'] and p['B3_F_images_settings_history_unchanged'] and p['port_released']
 for name in ('owner-ram.bin','owner-zp.bin','provider-cache-before.bin','hooks-before.bin'):assert (FIRST/name).read_bytes()==(PASS/name).read_bytes()
 freeze=c.read(REPO/'F_FREEZE.json');assert c.sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==freeze['sha256'] and all(c.sha(REPO/name)==h for name,h in freeze['sources'].items())
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 with serial_lease('2512-ASM-DBG-host-closeout',timeout=30):
  state=c.read(c.STATE);baseline=state['baselines'].copy();segments=state['segment_boundaries'].copy()
  event='2512-ASM-help-recovery-20261102-r1';events=state.setdefault('CPU_reset_events',[])
  assert not any(x.get('event_id')==event for x in events)
  events.append(dict(event_id=event,board='2512',recorded_UTC=c.NOW(),reason='Owner physical RESET to escape first RAM ASM help-printer loop; exact owner/cache/hooks restored; corrected RAM workflow subsequently passed',report=str(REC/'report.json'),report_sha256=c.sha(REC/'report.json'),power_cycle=False))
  assert state['baselines']==baseline and state['segment_boundaries']==segments;c.save(c.STATE,state)
  mp=Q/'device-operations/2512.json';m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  m.update(current_owner_RAM_sha256=p['RAM_sha256'],current_owner_ZP_sha256=p['ZP_sha256'],ASM_DBG_RAM_qualified=True,ASM_DBG_flash_installed=False,last_ASM_DBG_RAM_closeout=str(OUT/'completion.json'));c.save(mp,m)
  import rtc_fleet
  rtc_fleet.admission('2512')
 result=dict(board='2512',passed=True,qualification='Initial BASE1 ASM/DBG RAM workflow only; not installed',checks=p['checks'],F_sha256=freeze['sha256'],F_and_history_unchanged=True,flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,physical_resets_total=1,physical_reset_reason='Operator recovery from first long-help printer loop',first_to_final_owner_RAM_ZP_cache_hooks_identical=True,owner_RAM_restored=True,owner_ZP_restored=True,provider_cache_restored=True,BRK_HOLD_hooks_restored=True,RTC_host_eligible=True,RTC_baselines_segments_unchanged=True,other_boards_accessed=[],final_prompt='REC>',COM4_released=True,runtime_receipt=dict(path=str(PASS/'report.json'),sha256=c.sha(PASS/'report.json')),recovery_receipt=dict(path=str(REC/'report.json'),sha256=c.sha(REC/'report.json')),ASM_sha256=p['ASM_sha256'],DBG_sha256=p['DBG_sha256'],open=['positive AS/1 PROGRAM source persistence and failure fixtures','flash-source adapter','normal MON/APPS/R entry and flash installation','broader debugger boundary/register/breakpoint/callback cases','targeted816 and later extracted developer-kit acceptance'])
 c.save(OUT/'completion.json',result);print('PASS2512 ASM/DBG RAM closeout; original owner/cache/hooks identical across recovery; RTC eligible; no port opened')

if __name__=='__main__':run()
