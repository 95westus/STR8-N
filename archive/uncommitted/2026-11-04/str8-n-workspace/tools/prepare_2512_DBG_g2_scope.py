"""Prepare native DBG-only install scope; no write/erase operation is issued."""
import json,sys
from pathlib import Path
from devtools_2512_session import t,Q
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
BUILD=t.ROOT/'BUILD/dbg-base1-g2-r1';RAM=Q/'2512-DBG-broad-RAM-20261102-r1';PREF=Q/'2512-DBG-g2-fresh-preflight-20261102-r1';OUT=Q/'2512-DBG-g2-install-scope-20261102-r1'
def run():
 r=json.loads((RAM/'report.json').read_text());assert r['passed'] and len(r['checks'])==17 and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['provider_cache_restored'] and r['port_released']
 fresh=json.loads((PREF/'report.json').read_text());assert fresh['passed'] and fresh['owner_RAM_restored'] and fresh['owner_ZP_restored'] and fresh['provider_cache_restored']
 m=json.loads((Q/'device-operations/2512.json').read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m['physical_reset_pending'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
 old={b:(PREF/f'B{b}-original.bin').read_bytes() for b in range(4)};assert all(t.sha(v)==m['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
 image=(BUILD/'DBG-FLASH.bin').read_bytes();mf=json.loads((BUILD/'manifest.json').read_text());assert t.sha(image)==mf['artifacts']['DBG-FLASH.bin']['sha256'] and old[0][0x5800:0x6000]==image[0x1800:]
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());targets=[];ops=[];state=old[3];new0=bytearray(old[0])
 for n,page in enumerate((0xc0,0xd0)):
  at=(page-0x80)*256;body=image[n*4096:(n+1)*4096];name=f'B0-{page:02X}-target.bin';(OUT/name).write_bytes(body);(OUT/f'B0-{page:02X}-original.bin').write_bytes(old[0][at:at+4096]);new0[at:at+4096]=body;state,op=reserve(state,(page-0x80)//16);ops.append(op);targets.append(dict(bank=0,page=page,file=name,sha256=t.sha(body),before_sha256=t.sha(old[0][at:at+4096])))
 surviving=[];archived=[]
 for at in range(0x4000,0x6000,256):
  row=old[3][at:at+256]
  if valid_snapshot(row):
   (surviving if row==state[at:at+256] else archived).append(dict(address=f'{at+0x8000:04X}',sequence=int.from_bytes(row[8:12],'little'),sha256=t.sha(row)))
 before=t.classify_journal(old[3]);after=t.classify_journal(state)
 journal_erases=sum(len(op['journal_sector_erases']) for op in ops)
 assert before['sequence']==1199 and before['valid_records']==26 and not archived and len(surviving)==26 and journal_erases==0
 assert after['sequence']==1201 and after['valid_records']==28 and before['counts'][28:]==after['counts'][28:]
 assert new0[:0x4000]==old[0][:0x4000] and new0[0x6000:]==old[0][0x6000:] and new0[0x5800:0x6000]==old[0][0x5800:0x6000]
 assert state[:0x4000]==old[3][:0x4000] and state[0x6000:]==old[3][0x6000:]
 for b,body in old.items():(OUT/f'B{b}-original.bin').write_bytes(body)
 (OUT/'B0-target.bin').write_bytes(new0);(OUT/'B3-target.bin').write_bytes(state)
 p=dict(board='2512',status='REVIEW_READY_NOT_EXECUTED',request='Review flash scope only; no installation authorized by this review',image_erases=2,journal_erases=journal_erases,total_erases=2+journal_erases,targets=targets,operations=ops,F_writes=0,MON_writes=0,ASM_writes=0,E_writes=0,SF_provider_changed=False,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,other_boards=[],old_journal=before,new_journal=after,all_old_rows_archived_on_host=before['valid_records'],old_rows_retained_on_chip=surviving,old_rows_replaced_on_chip=archived,before_bank_sha256=m['current_physical_bank_sha256'],after_bank_sha256={**m['current_physical_bank_sha256'],'B0':t.sha(new0),'B3':t.sha(state)},manifest_sha256=t.sha((BUILD/'manifest.json').read_bytes()),RAM_report_sha256=t.sha((RAM/'report.json').read_bytes()),fresh_preflight_report_sha256=t.sha((PREF/'report.json').read_bytes()),fresh_preflight_path=str(PREF),owner_cache='6B00-77FF',preserve=['golden F','MON A/B g10 and saved B generation','ASM/SF1 provider exact','boot policy and board metadata','all unrelated images and reclaimed sectors','all SPI data','RTC time/trim/PF and collection','owner RAM/ZP/cache'])
 t.save(OUT/'plan.json',p)
 text=f'''# 2512 DBG g2 installation: fresh flash-scope review

The broader17-group real-CPU RAM suite passed; this is preparation only.
No flashing is required to keep using the RAM candidate. Installed DBG still
has the recorded g1 cleanup/boundary defects until this update is installed.

The other2512 retirement/reclamation operations have closed. Their completed
rotation changed journal room, so the earlier three-erase estimate is obsolete.
Fresh read-only capture verifies sequence1199 and26 valid C/D records.

Installation now needs only TWO erases, B0:C and B0:D. Two wear reservations
append {ops[0]['journal_appends'][0]['page']}/1200 and
{ops[1]['journal_appends'][0]['page']}/1201. All26 old records remain exact on
chip and are also archived on the host. No C/D erase or history replacement.
Final journal:28 valid records, sequence1201.
Counters: B0:C {before['counts'][4]}->{after['counts'][4]},
B0:D {before['counts'][5]}->{after['counts'][5]}; B3:C/D/E/F remain
{ '/'.join(str(v) for v in before['counts'][28:]) }.

Preserve Foundation F, MON A/B g10/default B, ASM and its exact D800-DFFF SF/1
provider, E, all other images, settings, all SPI data, RTC time/trim/PF and
fresh owner RAM/ZP/full provider cache. No reset, power cut, other-board access
or published-download change. RTC keeps priority; finish REC>, COM4 released.

Fresh owner RAM/ZP/full cache were restored and verified after the capture.
COM4 is released. No flash, SPI-data, metadata or RTC-setting writes were
performed to prepare this review; no resets or power cuts were used.

Only this review was requested. Installation has NOT been run. Before any
future execution, re-admit exact current bank hashes, target preimages and
journal room under the shared RTC-priority serial lease. Refuse changed
preimages or an unexpected rotation instead of expanding this scope.

Post-install acceptance should exercise installed R DBG startup/cancellation,
X/HOLD ZP and patch cleanup, BC, invalid-call guards, representative callback
and public-N behavior, plus unchanged ASM/source-provider admission. Then
independently read back all banks/journal and restore owner RAM/ZP/cache.
'''
 (OUT/'review-document.md').write_text(text,encoding='utf-8');print(text)
if __name__=='__main__':run()
