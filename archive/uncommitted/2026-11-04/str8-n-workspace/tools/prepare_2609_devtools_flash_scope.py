"""Prepare host-reviewed2609 ASM/DBG targets; no serial or flashing code."""
import binascii,json,os,sys
from pathlib import Path
from devtools_2512_session import t,Q
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
PRE=Q/'2609-devtools-flash-preflight-20261102-r1'
RAM=Q/'2609-devtools-g2-emulation-RAM-20261102-r1'
OUT=Q/'2609-devtools-flash-scope-20261102-r2'
KIT=t.ROOT/'BUILD/devtools-g2-candidate2-20261102-r2/STR8N-DEVTOOLS-g2-candidate2'
E=t.ROOT/'BUILD/devtools-AP02-g1-r2'
BASE=t.ROOT/'BUILD/storage-installed-auto-r2'

def run():
 fresh=json.loads((PRE/'report.json').read_text());ram=json.loads((RAM/'report.json').read_text())
 assert fresh['passed'] and ram['passed'] and len(ram['checks'])==13
 for r in (fresh,ram):assert all(r[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
 marker=json.loads((Q/'device-operations/2609.json').read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
 old={b:(PRE/f'B{b}-original.bin').read_bytes() for b in range(4)}
 assert all(t.sha(body)==marker['current_physical_bank_sha256'][f'B{b}'] for b,body in old.items())
 mf=json.loads((KIT/'KIT-MANIFEST.json').read_text());em=json.loads((E/'manifest.json').read_text())
 asm=(KIT/'payload/ASM-FLASH.bin').read_bytes();dbg=(KIT/'payload/DBG-FLASH.bin').read_bytes();extension=(E/'SERVICES-E.bin').read_bytes()
 original_apps={'ASM':asm,'DBG':dbg}
 for name,body in (('ASM-FLASH.bin',asm),('DBG-FLASH.bin',dbg)):
  assert t.sha(body)==mf['files']['payload/'+name]['sha256'] and len(body)==8192
  used=int.from_bytes(body[8:10],'little');assert body[:8]==b'AP\x02\x20PR05' and binascii.crc_hqx(body[:28],65535)==int.from_bytes(body[28:30],'little') and binascii.crc_hqx(body[32:used],65535)==int.from_bytes(body[30:32],'little')
 assert asm[15]==dbg[15]==2
 def for_816(body):
  image=bytearray(body);image[15]=0x16;image[28:30]=binascii.crc_hqx(image[:28],65535).to_bytes(2,'little')
  assert image[32:]==body[32:] and all(a==b or i in (15,28,29) for i,(a,b) in enumerate(zip(image,body)))
  assert binascii.crc_hqx(image[:28],65535)==int.from_bytes(image[28:30],'little')
  return bytes(image)
 asm=for_816(asm);dbg=for_816(dbg)
 assert dbg[0x1800:]==(KIT/'payload/FLASH-SOURCE-7000.bin').read_bytes()
 assert t.sha(extension)==em['artifacts']['services']['sha256'] and binascii.crc_hqx(extension,65535)==0
 accepted_E=Q/'2512-devtools-flash-installed-20261102-r1';assert json.loads((accepted_E/'report.json').read_text())['passed'] and (accepted_E/'B3-after.bin').read_bytes()[0x6000:0x7000]==extension
 # This is the alias-only dispatcher above the exact current full profile.
 assert old[1]==(BASE/'B1-candidate.bin').read_bytes()
 assert old[3][0x6000:0x7000]==(BASE/'SERVICES-E.bin').read_bytes()
 base2=(BASE/'B2-candidate.bin').read_bytes();assert old[2][:0x2c00]==base2[:0x2c00] and old[2][0x3000:]==base2[0x3000:]
 includes=['service-load-image.inc','service-transfer.inc','service-flash-transfer.inc','service-map.inc','batch-interface.inc','service-interface.inc','service-foundation.inc','str8n-v2-public.inc','workbench-interface.inc']
 for name in includes:assert (E/'services-inputs'/name).read_text()==(BASE/'E'/name).read_text()
 freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha(old[3][-4096:])==freeze['sha256']
 assert all(t.sha((t.REPO/name).read_bytes())==h for name,h in freeze['sources'].items())
 assert old[0][:4]==b'WDC\0' and old[0][0x2000:0x3000]!=bytes(4096) and old[0][0x3000:0x6000]==bytes(12288)
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 def durable(name,body):
  p=OUT/name
  with p.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
  assert p.read_bytes()==body;return dict(file=name,bytes=len(body),sha256=t.sha(body),host_readback_verified=True)
 archive={f'B{b}':durable(f'B{b}-original.bin',body) for b,body in old.items()}
 wdc=durable('B0-WDC-original.bin',old[0]);journal=durable('journal-CD-original.bin',old[3][0x4000:0x6000])
 targets=[];ops=[];state=old[3];new0=bytearray(old[0])
 for bank,page,body,label in [(0,0xa0,asm[:4096],'ASM first'),(0,0xb0,asm[4096:],'ASM second'),(0,0xc0,dbg[:4096],'DBG first'),(0,0xd0,dbg[4096:],'DBG second/SF1'),(3,0xe0,extension,'R aliases/dispatcher')]:
  at=(page-0x80)*256;before=old[bank][at:at+4096]
  n=f'B{bank}-{page:02X}-target.bin';durable(n,body);durable(f'B{bank}-{page:02X}-original.bin',before)
  state,op=reserve(state,bank*8+(page-0x80)//16);ops.append(op)
  if bank==3:v=bytearray(state);v[at:at+4096]=body;state=bytes(v)
  else:new0[at:at+4096]=body
  targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',label=label,file=n,sha256=t.sha(body),before_sha256=t.sha(before),before_all_zero=before==bytes(4096)))
 retained=[];replaced=[]
 for at in range(0x4000,0x6000,256):
  row=old[3][at:at+256]
  if valid_snapshot(row):(retained if row==state[at:at+256] else replaced).append(dict(address=f'{at+0x8000:04X}',sequence=int.from_bytes(row[8:12],'little'),sha256=t.sha(row)))
 before=t.classify_journal(old[3]);after=t.classify_journal(state)
 assert before['sequence']==1089 and before['valid_records']==27 and after['sequence']==1095 and after['valid_records']==17
 assert len(retained)==11 and len(replaced)==16 and all(v['address'].startswith('D') for v in replaced)
 assert sum(len(op['journal_sector_erases']) for op in ops)==1 and ops[-1]['journal_sector_erases']==['B3:D']
 assert before['default']==after['default']=='B' and before['enabled_mask']==after['enabled_mask']==0 and before['entries']==after['entries']==[8]*4
 assert after['counts'][28:]==[80,50,50,31] and after['counts'][2:6]==[3]*4
 assert state[:0x4000]==old[3][:0x4000] and state[0x7000:]==old[3][0x7000:]
 assert new0[:0x2000]==old[0][:0x2000] and new0[0x6000:]==old[0][0x6000:]
 # The root may change sequence/CRCs/counts only; no hidden boot-policy edit.
 root_before=old[3][0x4a00:0x4b00];root_after=state[0x5000:0x5100]
 allowed=set(range(8,12))|{30,31,252,253}
 for i in (2,3,4,5,29,30):allowed.update(range(0x40+3*i,0x43+3*i))
 assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(root_before,root_after)))
 durable('B0-target.bin',new0);durable('B3-target.bin',state)
 p=dict(board='2609',status='REVIEW_READY_NOT_EXECUTED',flash_install_authorized=False,owner_layout_selection='Host-backup WDC; use qualified layout',image_erases=5,journal_erases=1,total_erases=6,journal_appends=6,targets=targets,operations=ops,before_journal=before,after_journal=after,old_rows_archived_on_host=27,old_rows_retained_on_chip=retained,old_rows_replaced_on_chip=replaced,original_bank_archives=archive,WDC_backup=wdc,WDC_fallback_qualified_after_install=False,WDC_image_complete_after_install=False,journal_backup=journal,before_bank_sha256=marker['current_physical_bank_sha256'],after_bank_sha256={**marker['current_physical_bank_sha256'],'B0':t.sha(new0),'B3':t.sha(state)},F_writes=0,MON_writes=0,RTC_metadata_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,automatic_retries=0,rollback_erases_included=0,other_boards=[],persistent_source_tests_included=False,FLASH_source_free_sectors_after_install=0,PROGRAM_source_capacity_not_yet_qualified_on_2609=True,dependency_source_includes_unchanged=includes,B1_dependency_exact=True,B2_dependencies_exact_except_STATUS=True,E_previously_installed_tested_on_2512=True,ASM_DBG_core_816_RAM_qualified=True,AP02_installed_816_acceptance_pending=True,AP02_header_CPU=0x16,AP02_header_source_CPU=2,AP02_header_changed_offsets=[15,28,29],AP02_executable_bodies_unchanged=True,firmware_builds=0,inputs=dict(kit_manifest_sha256=t.sha((KIT/'KIT-MANIFEST.json').read_bytes()),E_manifest_sha256=t.sha((E/'manifest.json').read_bytes()),RAM_report_sha256=t.sha((RAM/'report.json').read_bytes()),fresh_report_sha256=t.sha((PRE/'report.json').read_bytes())),qualification_limits='65C02 cross-assembler/common8bit subset on816 emulation; native excluded; no persistent source fixture')
 p['AP02_envelopes']={name:dict(source_sha256=t.sha(original_apps[name]),target_sha256=t.sha(body),executable_body_sha256=t.sha(body[32:]),CPU_before=2,CPU_after=0x16) for name,body in [('ASM',asm),('DBG',dbg)]}
 t.save(OUT/'plan.json',p)
 pages=[row['page']+'/'+str(row['sequence']) for op in ops for row in op['journal_appends']]
 text=f'''# 2609 ASM/DBG: exact flash-scope review

REVIEW READY, NOT EXECUTED. Preparing this scope is not authorization to flash.
Owner layout choice: “Host-backup WDC; use qualified layout”. A verified full
32KiB original B0 WDC bank is archived as B0-WDC-original.bin, SHA-256
{wdc['sha256']}. B0:A contains WDC code and will be replaced. B0:B-D are zero
filler, with exact preimages archived too. WDC is retained on the host, not
as a qualified bootable on-chip fallback after installation. Its signature
or vectors may remain; restore the original bank before relying on WDC.

Six erases total: B0:A/B ASM, B0:C/D DBG/SF1, B3:E R aliases, and one native
B3:D journal rotation. No C erase, F/MON write, boot-setting change, metadata,
SPI-data, RTC-setting write, reset, power cut, retry or rollback is included.

Six journal appends: {', '.join(pages)}. Archive all27 old records on the host.
Keep11 old C records exact on chip; replace16 old D records during rotation.
Final17 valid rows/seq1095; counters B0:A-D2->3 each and C/D/E/F80/50/50/31.
CF00 is the reserved erase intent, not an ordinary free slot. Intent reserves
the E target and D erase counts before D is erased and D000 committed.
Saved B/g10, disabled bank mask00, entries8000 and all other settings remain.

Preserve B0:8/9/E/F, all B1/B2, B3:8/9/A/B/F byte-for-byte. Keep the current
full CLOCK/FLASH/MAINT/SRAM/WORK profile; no utility retirement/reclamation is
included. E reuses the existing loader/interfaces and adds qualified R ASM/
R DBG aliases. Its dependencies match this profile, except the separately
qualified STATUS display extent. F is frozen. Existing legacy B1:E/F stays.

Reuse exact candidate2 executable bodies; no new firmware build. Change only
AP/02 byte15 CPU02->16 and header CRC bytes28/29, because the scanner compares
this field with the hardware CPU query. Payload CRC and all executable/body
bytes stay exact. DBG retains the exact D800-DFFF private SF/1 provider.
Core816 emulation RAM acceptance passed; the AP/02 wrappers/R routing were
installed-tested on2512 and need their actual installed2609 acceptance.
No native16-bit claim is made. Unconverted CPU02 headers must not be installed.

Source persistence writes are excluded. There is no erased SF/1 source
sector in B0:8-D after this layout: vendor8/9 and appsA-D occupy the arena.
No extra B0:9 erase is implied. Positive PROGRAM/FLASH source tests require
another admitted fixture/scope; the installation does not claim those gates.

Before any future installation, yield to RTC, acquire the shared COM8 lease,
capture fresh owner RAM0200-66FF/ZP00-DF/cache6B00-77FF and hooks, and re-admit
all bank hashes/target preimages/journal room. Stop on any mismatch instead
of expanding this six-erase allowance. Host archives must remain verified.

Installed acceptance: APPS/APP/R aliases, assemble/list/export/readback/run,
DBG start cancellation, real BRK/S/N/C/breakpoints/X/HOLD/CPU refusal checks;
read-only source-provider/PROGRAM reload, current native-tool launch checks,
four-bank readback, all11 retained rows and exact planned root/metadata/F.
Restore/read back owner RAM/ZP/full cache and hooks; finish REC>, release
COM8, leave RTC eligible. No other boards or published files are touched.

The fresh capture for this review restored owner RAM/ZP/full cache and
released COM8 at REC>. No flash or persistent-data writes were performed.
Approval of the six erases and on-chip D-history replacement remains pending.
'''
 (OUT/'review-document.md').write_text(text,encoding='utf-8');print(text)

if __name__=='__main__':run()
