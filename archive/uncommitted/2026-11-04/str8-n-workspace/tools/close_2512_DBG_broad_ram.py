"""Seal RAM-only DBG acceptance; does not authorize a journal rotation."""
import json
from pathlib import Path
import rtc_drift_campaign as c
from serial_test_coordination import serial_lease
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';REPO=ROOT/'release/str8nf-v0.2.0';TRIAL=Q/'2512-DBG-broad-RAM-20261102-r1';BASE=Q/'2512-DBG-broad-baseline-RAM-20261102-r1';BUILD=ROOT/'BUILD/dbg-base1-g2-r1';OUT=Q/'2512-DBG-broad-RAM-closeout-20261102-r1'
def run():
 r=c.read(TRIAL/'report.json');b=c.read(BASE/'report.json');assert r['passed'] and len(r['checks'])==17 and b['passed'] and sum(v['defect'] for v in b['findings'])==4
 assert all(r[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'))
 for bank in range(4):assert (TRIAL/f'B{bank}-before.bin').read_bytes()==(TRIAL/f'B{bank}-after.bin').read_bytes()
 f=c.read(REPO/'F_FREEZE.json');assert c.sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==f['sha256'] and all(c.sha(REPO/n)==h for n,h in f['sources'].items())
 z=ROOT/'BUILD/unified-g10-candidate3-20261101-r3/STR8N-MON-g00000010-candidate3.zip';assert c.sha(z)=='6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789'
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 updated=False
 try:
  with serial_lease('2512-DBG-broad-RAM-host-closeout',timeout=1):
   mp=Q/'device-operations/2512.json';m=c.read(mp)
   if m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m['physical_reset_pending'] and not any(v for k,v in m.items() if k.endswith('_worker_active')):
    m.update(DBG_broad_RAM_qualified=True,DBG_g2_flash_installed=False,last_DBG_broad_RAM_closeout=str(OUT/'completion.json'));c.save(mp,m);updated=True
 except TimeoutError:pass
 # Another authorized2512 task may acquire the lease immediately after this
 # trial released it. Do not replace its owner-state or admission markers.
 result=dict(board='2512',passed=True,qualification='DBG g2 broader real-CPU RAM acceptance; this trial did not change installed g1',checks=r['checks'],baseline_findings=b['findings'],F_writes=0,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,other_boards_accessed=[],all_flash_images_settings_history_unchanged=True,owner_RAM_ZP_full_cache_restored=True,BRK_HOLD_hooks_restored=True,RTC_priority_honored=True,shared_marker_updated=updated,shared_marker_update_deferred=not updated,final_prompt_at_test_completion='REC>',COM4_released_by_this_trial=True,build_manifest_sha256=c.sha(BUILD/'manifest.json'),report_sha256=c.sha(TRIAL/'report.json'),baseline_report_sha256=c.sha(BASE/'report.json'),F_sha256=f['sha256'],Candidate3_ZIP_unchanged=True,remaining=['fresh installation review after concurrent2512 work','reviewed installation of g2','2609/816 developer qualification','later extracted developer kit'],execution_contract='IRQ-masked65C02 RAM0200-3FFF; bounded step-over admits six nonblocking public calls; free-running user code is not sandboxed')
 c.save(OUT/'completion.json',result);print('PASS2512 broader DBG RAM gate; four defects fixed in candidate,17 groups pass; no flashing; owner/hooks restored; shared marker updated='+str(updated))
if __name__=='__main__':run()
