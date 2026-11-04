"""Host-only closeout for the extracted candidate2 RAM trial; no serial open."""
import json
from devtools_2512_session import t,Q
OUT=Q/'2512-devtools-g2-extracted-RAM-20261102-r2'
BUILD=t.ROOT/'BUILD/devtools-g2-candidate2-20261102-r2'
OLD=t.ROOT/'BUILD/devtools-g2-candidate1-20261102-r1'

def run():
 r=json.loads((OUT/'report.json').read_text());assert r['passed'] and len(r['checks'])==7 and len(r['transfers'])==3
 assert all(r[k] for k in ('functional_checks_passed','owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released','B3_F_images_settings_history_unchanged'))
 assert all(r[k]==0 for k in ('flash_writes','journal_writes','SPI_writes','WORKSPACE_writes','RTC_writes','resets','power_cuts','firmware_builds'))
 kit=BUILD/'STR8N-DEVTOOLS-g2-candidate2';mf=json.loads((kit/'KIT-MANIFEST.json').read_text());mf1=json.loads((OLD/'STR8N-DEVTOOLS-g2-candidate1/KIT-MANIFEST.json').read_text())
 assert all(info==mf1['files'][name] for name,info in mf['files'].items() if name.startswith(('payload/','terminal/')))
 hashes={}
 for b in range(4):
  before=(OUT/f'B{b}-before.bin').read_bytes();after=(OUT/f'B{b}-after.bin').read_bytes();assert before==after
  assert before==(Q/'2512-devtools-g2-extracted-RAM-20261102-r1'/f'B{b}-before.bin').read_bytes()
  hashes[f'B{b}']=t.sha(after)
 assert t.sha((OUT/'owner-ram.bin').read_bytes())==r['RAM_sha256'] and t.sha((OUT/'owner-zp.bin').read_bytes())==r['ZP_sha256']
 zipfile=BUILD/'STR8N-DEVTOOLS-g2-candidate2.zip';assert t.sha(zipfile.read_bytes())==r['ZIP_sha256']
 for item in r['transfers']:
  path=item['path'];assert path.startswith(r['kit_path']) and item['host_complete'] and item['sent']>0
  name='payload/'+path.replace('\\','/').split('/')[-1];assert item['sha256']==mf['files'][name]['sha256'] and item['sent']==mf['files'][name]['bytes']
 prior=json.loads((Q/'2512-devtools-g2-extracted-RAM-20261102-r1/report.json').read_text())
 assert not prior['passed'] and all(prior[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
 receipt=dict(schema=1,passed=True,board='2512',CPU='65C02',accepted_at=t.utc(),ZIP_sha256=r['ZIP_sha256'],scope='extracted RAM binaries, console transfer backend, example, installed launch and preservation',checks=r['checks'],transfers=3,console='0.1.2',flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0,owner_RAM_ZP_cache_hooks_restored=True,final_prompt='REC>',COM4_released=True,firmware_and_terminal_unchanged_from_candidate1=True,correction='Example/manual now use ORG0200 matching the assembler output staging buffer; candidate1 trial stopped before running misplaced code and restored owner memory.',physical_GUI_keys_repeated=False,persistent_source_storage_repeated=False,emulation_816_accepted=False,native_816_in_scope=False,source_only_rebuild_accepted=False)
 with t.serial_lease('2512-extracted-devtools-host-closeout',timeout=30):
  mp=Q/'device-operations/2512.json';m=json.loads(mp.read_text())
  assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and m['current_physical_bank_sha256']==hashes
  m.update(DEVTOOLS_g2_extracted_RAM_qualified=True,DEVTOOLS_g2_accepted_ZIP_sha256=r['ZIP_sha256'],last_DEVTOOLS_g2_extracted_acceptance=str(OUT/'report.json'));t.save(mp,m)
 t.save(OUT/'completion.json',dict(**receipt,report_sha256=t.sha((OUT/'report.json').read_bytes()),all_four_bank_sha256=hashes))
 t.save(BUILD/'ACCEPTANCE-2512.json',receipt)
 print(json.dumps(receipt,indent=2))

if __name__=='__main__':run()
