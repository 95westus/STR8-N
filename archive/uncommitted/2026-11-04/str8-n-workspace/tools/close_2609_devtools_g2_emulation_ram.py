"""Host-only closeout of 2609 RAM emulation qualification; no port opened."""
import json
from pathlib import Path
from devtools_2512_session import t,Q
OUT=Q/'2609-devtools-g2-emulation-RAM-20261102-r1'
BUILD=t.ROOT/'BUILD/devtools-g2-candidate2-20261102-r2'

def run():
 r=json.loads((OUT/'report.json').read_text());assert r['passed'] and len(r['checks'])==13 and len(r['transfers'])==8
 assert all(r[k] for k in ('functional_checks_passed','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'))
 assert all(r[k]==0 for k in ('flash_writes','journal_writes','SPI_writes','WORKSPACE_writes','RTC_writes','resets','power_cuts','firmware_builds'))
 assert len(r['ambiguous_opcodes'])==32 and len(r['unsupported_opcodes'])==17
 want=dict(E=1,M=1,X=1,DBR=0,D=0,PBR=0)
 assert all(r['context_before'][k]==r['context_after'][k]==v for k,v in want.items())
 marker=json.loads((OUT/'marker-before.json').read_text());hashes={}
 for b in range(4):
  before=(OUT/f'B{b}-before.bin').read_bytes();after=(OUT/f'B{b}-after.bin').read_bytes();assert before==after
  hashes[f'B{b}']=t.sha(after);assert hashes[f'B{b}']==marker['current_physical_bank_sha256'][f'B{b}']
 assert t.sha((OUT/'owner-ram.bin').read_bytes())==r['RAM_sha256'] and t.sha((OUT/'owner-zp.bin').read_bytes())==r['ZP_sha256']
 z=BUILD/'STR8N-DEVTOOLS-g2-candidate2.zip';assert t.sha(z.read_bytes())==r['ZIP_sha256']
 kit=Path(r['kit_path']);mf=json.loads((kit/'KIT-MANIFEST.json').read_text())
 for item in r['transfers']:
  p=Path(item['path']);assert p.is_relative_to(kit) and item['host_complete']
  info=mf['files'][p.relative_to(kit).as_posix()];assert item['sha256']==info['sha256'] and item['sent']==info['bytes']
 receipt=dict(schema=1,passed=True,board='2609',CPU='65C816 emulation',accepted_at=t.utc(),ZIP_sha256=r['ZIP_sha256'],scope='RAM-extracted ASM65C02 common subset and DBGg2 emulation paths; no flash installation/persistent source writes',checks=r['checks'],CPU_context=want,ambiguous_opcode_refusals=32,additional_unsupported_opcode_refusals=17,transfers=8,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0,owner_RAM_ZP_cache_hooks_restored=True,F_golden=True,all_images_settings_history_unchanged=True,final_prompt='REC>',COM8_released=True,other_boards_accessed=[],AP02_installation_tested=False,persistent_source_storage_tested=False,native_816_in_scope=False,physical_GUI_keys_repeated=False)
 with t.serial_lease('2609-devtools-emulation-host-closeout',timeout=30):
  mp=Q/'device-operations/2609.json';m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and m['current_physical_bank_sha256']==hashes
  m.update(DEVTOOLS_g2_816E_RAM_qualified=True,DEVTOOLS_g2_RAM_accepted_ZIP_sha256=r['ZIP_sha256'],last_DEVTOOLS_g2_816E_RAM_acceptance=str(OUT/'report.json'));t.save(mp,m)
 t.save(OUT/'completion.json',dict(**receipt,report_sha256=t.sha((OUT/'report.json').read_bytes()),all_four_bank_sha256=hashes))
 t.save(BUILD/'ACCEPTANCE-2609-RAM.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':run()
