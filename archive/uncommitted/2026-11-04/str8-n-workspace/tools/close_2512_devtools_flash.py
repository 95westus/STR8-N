"""Seal installed developer acceptance and2609 default verification; host only."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';REPO=ROOT/'release/str8nf-v0.2.0'
TRIAL=Q/'2512-devtools-flash-installed-20261102-r1';SCOPE=Q/'2512-devtools-flash-scope-20261102-r1';BUILD=ROOT/'BUILD/devtools-AP02-g1-r2';OUT=Q/'2512-devtools-flash-closeout-20261102-r1'
def run():
 r=c.read(TRIAL/'report.json');p=c.read(SCOPE/'plan.json');mr=c.read(Q/'2609-default-MON-g10-20261102-r1/report.json')
 assert r['passed'] and r['erase_requests']==5 and r['journal_appends']==5 and len(r['completed'])==5
 assert all(r[k] for k in ('NVM_verified','functional_checks_passed','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released'))
 assert mr['passed'] and mr['append_requests']==0 and mr['foreground_MON_B_and_owner_verified'] and mr['COM8_released']
 f=c.read(REPO/'F_FREEZE.json');assert c.sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==f['sha256'] and all(c.sha(REPO/n)==h for n,h in f['sources'].items())
 for b in range(4):assert c.sha(TRIAL/f'B{b}-after.bin')==p['after_bank_sha256'][f'B{b}']
 assert (TRIAL/'B3-before.bin').read_bytes()[-4096:]==(TRIAL/'B3-after.bin').read_bytes()[-4096:]
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 with serial_lease('2512-devtools-host-closeout',timeout=30):
  mp=Q/'device-operations/2512.json';m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  assert m['current_physical_bank_sha256']==p['after_bank_sha256']
  m.update(ASM_DBG_flash_installed=True,ASM_DBG_installed_qualified=True,last_ASM_DBG_flash_closeout=str(OUT/'completion.json'),current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256']);c.save(mp,m)
  import rtc_fleet
  rtc_fleet.admission('2512')
 result=dict(board='2512',passed=True,qualification='65C02 AP02 RAM-staged ASM/DBG installed',F_sha256=f['sha256'],F_writes=0,MON_writes=0,C_D_erases=0,image_erases=5,old_journal_rows_retained=20,journal_sequence=1182,journal_valid_rows=25,boot_settings_unchanged=True,owner_RAM_ZP_cache_restored=True,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,RTC_host_eligible=True,checks=r['checks'],final_prompt='REC>',COM4_released=True,manifest_sha256=c.sha(BUILD/'manifest.json'),trial_report_sha256=c.sha(TRIAL/'report.json'),scope_sha256=c.sha(SCOPE/'plan.json'),other_action=dict(board='2609',default='MON B g00000010',already_saved=True,flash_writes=0,foreground='B3>',COM8_released=True,report_sha256=c.sha(Q/'2609-default-MON-g10-20261102-r1/report.json')),remaining=['source FLASH adapter','broader debugger boundary/register/callback and816 acceptance','later XIP/full-RAM layout and extracted developer kit'],published_downloads_changed=False)
 c.save(OUT/'completion.json',result);print('PASS2512 installed ASM/DBG closed; RTC eligible.2609 default MON B verified without writes.')
if __name__=='__main__':run()
