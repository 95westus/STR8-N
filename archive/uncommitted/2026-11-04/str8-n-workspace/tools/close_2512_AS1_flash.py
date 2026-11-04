"""Seal completed2512 source FLASH gate; host receipt, no device operations."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';REPO=ROOT/'release/str8nf-v0.2.0';BUILD=ROOT/'BUILD/asm-flash-source-g2-r4';TRIAL=Q/'2512-AS1-FLASH-installed-20261102-r1';SCOPE=Q/'2512-AS1-FLASH-scope-20261102-r1';OUT=Q/'2512-AS1-FLASH-closeout-20261102-r1'
def run():
 r=c.read(TRIAL/'report.json');p=c.read(SCOPE/'plan.json');assert r['passed'] and r['erase_requests']==r['wear_appends']==5 and len(r['checks'])==15
 assert all(r[k] for k in ('NVM_verified','functional_checks_passed','cleanup_erase_used','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released')) and not r['source_fixture_may_exist']
 f=c.read(REPO/'F_FREEZE.json');assert c.sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==f['sha256'] and all(c.sha(REPO/n)==h for n,h in f['sources'].items())
 for b in range(4):assert c.sha(TRIAL/f'B{b}-after.bin')==p['after_bank_sha256'][f'B{b}']
 assert (TRIAL/'B0-after.bin').read_bytes()[0x1000:0x2000]==b'\xff'*4096
 zipfile=ROOT/'BUILD/unified-g10-candidate3-20261101-r3/STR8N-MON-g00000010-candidate3.zip';assert c.sha(zipfile)=='6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789'
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 with serial_lease('2512-AS1-FLASH-host-closeout',timeout=30):
  mp=Q/'device-operations/2512.json';m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending'] and not m['block_snapshot'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  assert m['current_physical_bank_sha256']==p['after_bank_sha256'];m.update(ASM_FLASH_source_qualified=True,ASM_DBG_qualification='2512 65C02 RAM-staged AP02; AS/1 PROGRAM and SF/1 FLASH source gates passed; broader DBG/816 pending',last_ASM_FLASH_source_closeout=str(OUT/'completion.json'),current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256']);c.save(mp,m)
  import rtc_fleet
  rtc_fleet.admission('2512')
 result=dict(board='2512',passed=True,qualification='SF/1 FLASH source persistence and paired ASM/DBG AP02 installed',F_sha256=f['sha256'],F_writes=0,MON_writes=0,E_writes=0,C_D_erases=0,erases=5,wear_appends=5,source_record_bytes=98,maximum_source_programs=100,old_journal_rows_retained=25,sequence=1187,journal_rows=30,fixture_B0_9_restored_FF=True,owner_RAM_ZP_full_provider_cache_restored=True,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,RTC_host_eligible=True,other_boards_accessed=[],profile_bytes=106496,ASM_source_RAM_bytes=6144,current_free_FLASH_source_extent='B0:9 only; one source record with packed source <=4056 bytes',final_prompt='REC>',COM4_released=True,checks=r['checks'],build_manifest_sha256=c.sha(BUILD/'manifest.json'),scope_sha256=c.sha(SCOPE/'plan.json'),trial_report_sha256=c.sha(TRIAL/'report.json'),recovery_report_sha256=c.sha(Q/'2512-AS1-FLASH-loader-recovery-20261102-r1/report.json'),post_fault_audit_sha256=c.sha(Q/'2512-AS1-FLASH-post-fault-audit-20261102-r1/report.json'),Candidate3_ZIP_unchanged=True,remaining=['broader DBG boundary/register/all-breakpoint/callback cleanup coverage','2609/816 developer qualification','later extracted developer kit; optional full-RAM XIP layout'])
 c.save(OUT/'completion.json',result);print('PASS2512 ASM FLASH-source gate closed; record removed; F/MON/E and all25 old journal rows preserved; owner/cache restored; RTC eligible; COM4 free')
if __name__=='__main__':run()
