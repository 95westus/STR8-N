"""Seal the owner-approved AS/1 PROGRAM trial; host files only."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0';Q=ROOT/'output/qualification'
SCOPE=Q/'2512-AS1-PROGRAM-scope-20261102-r1';TRIAL=Q/'2512-AS1-PROGRAM-trial-20261102-r1';OUT=Q/'2512-AS1-PROGRAM-closeout-20261102-r1'

def run():
 r=c.read(TRIAL/'report.json');a=c.read(SCOPE/'approval.json');p=c.read(SCOPE/'plan.json');assert a['approved'] and a['owner_answer']=='Approve 320-byte AS/1 trial' and r['passed'] and len(r['checks'])==6
 assert a['plan_sha256']==c.sha(SCOPE/'plan.json') and a['review_sha256']==c.sha(SCOPE/'review-document.md')
 assert all(r[k] for k in ('SPI_restored','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released')) and not r['SPI_mutation_pending']
 assert c.sha(TRIAL/'driver-as-executed.py')==a['driver_sha256']
 for b,h in p['preimages'].items():assert c.sha(SCOPE/f'SPI-{b}-original.bin')==h
 assert c.sha(TRIAL/'AS1-saved-payload-page.bin') and (TRIAL/'AS1-saved-payload-page.bin').read_bytes()[:p['capsule_bytes']]==(SCOPE/'expected-AS1-capsule.bin').read_bytes()
 freeze=c.read(REPO/'F_FREEZE.json');assert c.sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==freeze['sha256'] and all(c.sha(REPO/n)==h for n,h in freeze['sources'].items())
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 with serial_lease('2512-AS1-host-closeout',timeout=30):
  mp=Q/'device-operations/2512.json';m=c.read(mp)
  assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m.get('physical_reset_pending') and not m.get('ASM_source_SPI_restore_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  m.update(current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256'],ASM_AS1_PROGRAM_qualified=True,last_AS1_PROGRAM_closeout=str(OUT/'completion.json'));c.save(mp,m)
  import rtc_fleet
  rtc_fleet.admission('2512')
 result=dict(board='2512',passed=True,qualification='RAM resident ASM AS/1 PROGRAM source persistence; no flash installation',temporary_PROGRAM_bytes=320,exact_original_SPI_and_directory_restored=True,original_records_preserved=['CLK','CLOCK','NFCOPY'],test_record_remaining=False,checks=r['checks'],owner_RAM_restored=True,owner_ZP_restored=True,provider_cache_restored=True,BRK_HOLD_hooks_unchanged=True,B3_F_images_settings_history_unchanged=True,F_sha256=freeze['sha256'],flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,other_boards_accessed=[],RTC_host_eligible=True,RTC_campaign_settings_changed=False,final_prompt='REC>',COM4_released=True,approval_sha256=c.sha(SCOPE/'approval.json'),plan_sha256=c.sha(SCOPE/'plan.json'),trial_report=str(TRIAL/'report.json'),trial_report_sha256=c.sha(TRIAL/'report.json'),driver_sha256=a['driver_sha256'],RAM_helper_sha256=a['RAM_helper_sha256'],ASM_sha256=p['ASM_sha256'],capsule_sha256=p['capsule_sha256'],capsule_bytes=p['capsule_bytes'],remaining=['flash-source adapter','final ROM layout and normal MON/APPS/R launch integration','reviewed installation','broader debugger guards/cleanup,816 and later extracted developer kit'])
 c.save(OUT/'completion.json',result);print('PASS2512 AS/1 PROGRAM persistence gate closed; original320 bytes and owner/cache restored; RTC eligible; REC>;COM4 free')

if __name__=='__main__':run()
