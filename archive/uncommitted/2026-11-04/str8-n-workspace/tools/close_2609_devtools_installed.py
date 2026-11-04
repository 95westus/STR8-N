"""Host-only closeout of approved six-erase2609 developer installation."""
import binascii,json
from devtools_2512_session import t,Q
OUT=Q/'2609-devtools-installed-20261102-r1'
SCOPE=Q/'2609-devtools-flash-scope-20261102-r2'

def run():
 r=json.loads((OUT/'report.json').read_text());p=json.loads((SCOPE/'plan.json').read_text());approval=json.loads((OUT/'approval.json').read_text())
 assert r['passed'] and len(r['checks'])==16 and r['completed']==[v['address'] for v in p['targets']]
 assert approval['approved'] and approval['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes()) and approval['review_document_sha256']==t.sha((SCOPE/'review-document.md').read_bytes())
 assert r['erase_requests']==6 and r['image_erase_requests']==5 and r['journal_erase_requests']==1 and r['journal_appends']==6
 assert all(r[k]==0 for k in ('F_writes','MON_writes','SPI_writes','WORKSPACE_writes','RTC_writes','resets','power_cuts','firmware_builds','automatic_retries'))
 assert all(r[k] for k in ('NVM_verified','functional_checks_passed','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released'))
 old={b:(OUT/f'B{b}-before.bin').read_bytes() for b in range(4)};new={b:(OUT/f'B{b}-after.bin').read_bytes() for b in range(4)}
 for b in range(4):assert t.sha(old[b])==p['before_bank_sha256'][f'B{b}'] and t.sha(new[b])==p['after_bank_sha256'][f'B{b}']
 assert old[1]==new[1] and old[2]==new[2] and old[0][:0x2000]==new[0][:0x2000] and old[0][0x6000:]==new[0][0x6000:]
 assert old[3][:0x4000]==new[3][:0x4000] and old[3][0x7000:]==new[3][0x7000:]
 assert old[0]==(SCOPE/p['WDC_backup']['file']).read_bytes() and old[3][0x4000:0x6000]==(SCOPE/p['journal_backup']['file']).read_bytes()
 for row in p['old_rows_retained_on_chip']:
  at=int(row['address'],16)-0x8000;assert old[3][at:at+256]==new[3][at:at+256] and t.sha(new[3][at:at+256])==row['sha256']
 assert len(p['old_rows_retained_on_chip'])==11 and len(p['old_rows_replaced_on_chip'])==16
 for label,at in (('ASM',0x2000),('DBG',0x4000)):
  image=new[0][at:at+8192];assert image[15]==0x16 and t.sha(image)==p['AP02_envelopes'][label]['target_sha256'] and binascii.crc_hqx(image[:28],65535)==int.from_bytes(image[28:30],'little')
 assert binascii.crc_hqx(new[0][0x5800:0x6000],65535)==0
 assert t.sha((OUT/'owner-ram.bin').read_bytes())==r['RAM_sha256'] and t.sha((OUT/'owner-zp.bin').read_bytes())==r['ZP_sha256']
 journal=t.classify_journal(new[3]);assert journal==p['after_journal'] and journal['sequence']==1095 and journal['valid_records']==17 and journal['counts'][28:]==[80,50,50,31]
 with t.serial_lease('2609-devtools-installed-host-closeout',timeout=30):
  mp=Q/'device-operations/2609.json';m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and m['current_physical_bank_sha256']==p['after_bank_sha256']
  m.update(ASM_DBG_installed_qualified=True,DEVTOOLS_g2_816E_installed_qualified=True,DEVTOOLS_g2_readonly_source_backends_qualified=True,DEVTOOLS_installed_qualification_pending=False,last_DEVTOOLS_g2_installed_closeout=str(OUT/'completion.json'),ASM_DBG_flash_layout='B0:A/B ASM sourceg2; B0:C/D DBGg2/SF1; B3:E R aliases; AP02 CPU16',ASM_DBG_qualification='2609 816 emulation installed execution accepted; source-provider read-only lookup passed; positive source persistence separate',current_image_evidence='Reviewed five-image installation plus one native D rotation; F/MON/B1/B2/metadata preserved; original WDC host-archived')
  t.save(mp,m)
 receipt=dict(passed=True,board='2609',CPU='65C816 emulation',closed_at=t.utc(),checks=len(r['checks']),report_sha256=t.sha((OUT/'report.json').read_bytes()),plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()),image_erases=5,journal_erases=1,total_erases=6,journal_appends=6,old_journal_rows_archived=27,old_rows_retained_on_chip=11,old_D_rows_replaced_on_chip=16,final_valid_records=17,final_sequence=1095,final_C_D_E_F_counts=[80,50,50,31],F_golden=True,MON_Boot_settings_metadata_preserved=True,owner_RAM_ZP_cache_hooks_restored=True,WDC_original_host_backup=p['WDC_backup'],WDC_on_chip_complete=False,AP02_CPU='16',persistent_source_write_tests=False,FLASH_source_free_sectors=0,resets=0,power_cuts=0,SPI_writes=0,RTC_writes=0,firmware_builds=0,other_boards_accessed=[],final_prompt='REC>',COM8_released=True)
 t.save(OUT/'completion.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':run()
