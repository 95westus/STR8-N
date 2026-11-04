"""Close already-complete three-board SS2 operations; host reads only."""
import json
import standardize_ss2_64k as s

t=s.t;Q=s.Q

def run():
 plan=s.approved();result=dict(passed=False,date_local='2026-11-02',scope_plan_sha256=t.sha((s.SCOPE/'plan.json').read_bytes()),format='SS2',PROGRAM_boundary='10000',PROGRAM_payload_bytes=63488,WORKSPACE_payload_bytes=65504,flash_writes=0,journal_appends=0,RTC_setting_writes=0,physical_resets=0,power_cuts=0,firmware_builds=0,other_boards_accessed=[],boards={})
 for board in plan['execution_order']:
  out=Q/f'{board}-SS2-64K-standardized-20261102-r1';r=json.loads((out/'report.json').read_text());p=plan['boards'][board]
  assert r['passed'] and not r['SPI_change_pending'] and r['metadata_operation_started'] and r['whole_SPI_matches_exact_plan'] and r['all_four_banks_exact']
  for flag in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','port_released'):assert r[flag]
  for k in ('flash_writes','journal_appends','RTC_SET','trim_writes','PF_ACK','physical_resets','power_cuts','firmware_builds','CPU_simulations','automatic_retries'):assert r[k]==0
  before=(out/'SPI-before.bin').read_bytes();after=(out/'SPI-after.bin').read_bytes();assert len(before)==len(after)==131072
  assert before[:2048]==(s.SCOPE/board/'SPI-metadata-original.bin').read_bytes()
  assert after==(s.SCOPE/board/'SPI-metadata-expected.bin').read_bytes()+before[2048:]
  assert before[0x40:0x240]==after[0x40:0x240] and before[0x800:]==after[0x800:]
  for bank in range(4):assert (out/f'B{bank}-before.bin').read_bytes()==(out/f'B{bank}-after.bin').read_bytes()
  m=json.loads((Q/f'device-operations/{board}.json').read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m['SS2_SPI_restore_pending'] and m['SPI_format']=='SS2'
  item=dict(passed=True,format='SS2',PROGRAM_boundary='10000',layout_generation=p['expected_layout_generation'],session_revision=p['expected_session_revision'],session_epoch=p['expected_session_epoch'],original_SPI_sha256=t.sha(before),final_SPI_sha256=t.sha(after),PROGRAM_directory_and_all_payload_exact=True,all_flash_banks_exact=True,owner_RAM_ZP_cache_hooks_restored=True,final_prompt='REC>',port_released=True,report=str(out/'report.json'),archive=str(t.ROOT/f'local-archives/SS2-64K-standardization-20261102/{board}'))
  if r.get('readonly_continuation'):
   item.update(readonly_continuation=r['readonly_continuation'],initial_verification_error=r['initial_verification_error'],native_operation_replayed=r['native_operation_replayed'])
  result['boards'][board]=item
 result['passed']=True;t.save(Q/'SS2-64K-standardization-complete-20261102.json',result)
 print('PASS2512/2609/2604 SS2/64K; all payload/directories/flash exact; owner restored; all ports released')

if __name__=='__main__':run()
