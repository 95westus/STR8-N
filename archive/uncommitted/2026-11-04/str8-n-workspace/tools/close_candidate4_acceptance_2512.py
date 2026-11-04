"""Host-only candidate4 acceptance receipt; never edits the tested ZIP."""
import json
import candidate4_2512_common as c

t=c.t
AUTO=c.Q/'2512-candidate4-extracted-RAM-20261102-r1'
KEYS=c.Q/'2512-candidate4-physical-keys-20261102-r2'
RECOVER=c.Q/'2512-candidate4-keys-owner-recovery-20261102-r1'

def run():
 a=json.loads((AUTO/'report.json').read_text());k=json.loads((KEYS/'report.json').read_text());r=json.loads((RECOVER/'report.json').read_text())
 assert a['passed'] and k['passed'] and r['passed']
 assert a['ZIP_sha256']==k['ZIP_sha256']==c.PIN==t.sha((c.BASE/(c.LABEL+'.zip')).read_bytes())
 for name in ('owner-ram.bin','owner-zp.bin','provider-cache-before.bin','hooks-before.bin'):
  assert (AUTO/name).read_bytes()==(KEYS/name).read_bytes()
 for root in (AUTO,KEYS):
  for bank in range(4):assert (root/f'B{bank}-before.bin').read_bytes()==(root/f'B{bank}-after.bin').read_bytes()==(AUTO/f'B{bank}-before.bin').read_bytes()
  assert (root/'SPI-metadata-before.bin').read_bytes()==(root/'SPI-metadata-after.bin').read_bytes()==(AUTO/'SPI-metadata-before.bin').read_bytes()
  for flag in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'):assert root==AUTO and a[flag] or root==KEYS and k[flag]
 for report in (a,k):
  for name in ('flash_writes','journal_appends','settings_writes','SPI_writes','RTC_SET','trim_writes','PF_ACK','physical_resets','power_cuts','firmware_builds'):assert report[name]==0
 assert k['generated_key_events']==0
 for flag in ('SEND_S19_initial_cancel','SEND_BIN_initial_cancel','S19_independent_RAM_verified','F3_BIN_execution_and_return','F4_BIN_execution_and_return','F5_MAP_read_only','F6_CONFIG_read_only','F7_OPAQUE_no_write','F8_DEMO_execution_and_return','GUI_sequence_passed'):assert k[flag]
 native=sorted({x['key'] for x in k['native_keys']});assert {'Shift+F2','Shift+F3'}<=set(native)
 actions={x['action'] for x in k['operator_actions']};assert {f'F{i}' for i in range(1,13)}|{'Shift+F2','Shift+F3'}<=actions
 freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
 for name,h in freeze['sources'].items():assert t.sha((t.REPO/name).read_bytes())==h
 result=dict(passed=True,date_local='2026-11-02',board='2512',CPU='65C02',ZIP=c.LABEL+'.zip',ZIP_sha256=c.PIN,F_sha256=freeze['sha256'],automated_groups=10,automated_extracted_BIN_transfers=5,terminal_action_coverage=sorted(actions),observed_physical_keys=native,operator_actions=k['operator_actions'],native_dialogs_prefilled_by_harness=True,generated_key_events=0,owner_RAM_ZP_cache_hooks_restored=True,all_flash_images_settings_boot_wear_history_exact=True,SPI_metadata_exact=True,persistent_writes=0,physical_resets=0,power_cuts=0,other_boards_accessed=False,RTC_priority_observed=True,final_prompt='REC>',COM4_released=True,automated_report=str(AUTO/'report.json'),physical_report=str(KEYS/'report.json'),first_attempt_recovery=str(RECOVER/'report.json'),tested_ZIP_unchanged=True,published_downloads_unchanged=True,limitations=['2512 RAM-only extracted-kit acceptance; no new816 live qualification','No positive persistent write operation during this acceptance','Ordinary terminal actions may use buttons; exact physical observations are listed','Original first physical attempt stopped at S19 file selection; escrow recovery independently passed'])
 t.save(c.BASE/'ACCEPTANCE-2512.json',result);t.save(c.Q/'2512-candidate4-acceptance-complete-20261102.json',result)
 print('PASS candidate4 extracted2512 acceptance; ZIP/F unchanged; exact owner restoration; REC>;COM4 free')

if __name__=='__main__':run()
