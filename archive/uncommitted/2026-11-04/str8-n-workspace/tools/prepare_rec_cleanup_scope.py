"""Prepare review-only 2604/2609 normalization to 2512; never opens a port."""
import json,sys
from pathlib import Path
import devtools_2512_session as ds
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
from status_extents import assert_preserved
t=ds.t;Q=ds.Q;ROOT=t.ROOT
OUT=Q/'2604-2609-REC-cleanup-scope-20261102-r3'
COMMON=((1,0x80),(1,0x90),(1,0xa0),(2,0xe0),(2,0xf0),(3,0xe0))
LEGACY={'2604':((1,0xe0),(1,0xf0)),'2609':((0,0x80),(0,0x90),(0,0xe0),(0,0xf0),(1,0xe0),(1,0xf0))}
SOURCES={'2604':Q/'2604-foundation-profile-installed-20261102-r1','2609':Q/'2609-devtools-installed-20261102-r1'}
def before(board):
 folder=SOURCES[board];suffix='installed' if board=='2604' else 'after'
 return {b:(folder/f'B{b}-{suffix}.bin').read_bytes() for b in range(4)}
def build():
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 (OUT/'scope-builder.py').write_bytes(Path(__file__).read_bytes())
 reference={b:(Q/('2512-DBG-g2-installed-20261102-r1' if b in (0,3) else '2512-legacy-reclaimed-20261102-r1')/f'B{b}-after.bin').read_bytes() for b in range(4)}
 rm=json.loads((Q/'device-operations/2512.json').read_text());assert {f'B{b}':t.sha(v) for b,v in reference.items()}==rm['current_physical_bank_sha256']
 proof=json.loads((ROOT/'BUILD/loadable-maint-full-r2/qualification.json').read_text());assert proof['passed']
 plan=dict(status='REVIEW_ONLY_NOT_APPROVED_NO_FLASHING',owner_request='Clean up2604/2609 to match2512; MAINT/FLASH REC BINs; preserve settings/history/RAM; keep F golden; review new scope first',F_writes=0,MON_writes=0,SPI_writes=0,RTC_setting_writes=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,boards={})
 for board in ('2604','2609'):
  out=OUT/board;out.mkdir();old=before(board);marker=json.loads((Q/f'device-operations/{board}.json').read_text())
  # A read-only RAM admission may own the board during host-only preparation.
  # Busy/restore flags must be clear before execution; no port is opened here.
  assert {f'B{b}':t.sha(v) for b,v in old.items()}==marker['current_physical_bank_sha256']
  assert old[3][-4096:]==reference[3][-4096:]
  for b,v in old.items():(out/f'B{b}-original.bin').write_bytes(v)
  (out/'device-marker-before.json').write_text(json.dumps(marker,indent=2)+'\n')
  rows=[]
  for offset in range(0x4000,0x6000,256):
   row=old[3][offset:offset+256]
   if valid_snapshot(row):
    file=f'original-row-{offset+0x8000:04X}.bin';(out/file).write_bytes(row)
    rows.append(dict(address=f'{offset+0x8000:04X}',sequence=int.from_bytes(row[8:12],'little'),sha256=t.sha(row),file=file))
  state=old[3];after={b:bytearray(v) for b,v in old.items()};targets=[];operations=[]
  for b,page in COMMON+LEGACY[board]:
   offset=(page-0x80)*256;new=reference[b][offset:offset+4096] if (b,page) in COMMON else b'\xff'*4096
   prior=old[b][offset:offset+4096];assert prior!=new
   state,op=reserve(state,b*8+(page-0x80)//16);operations.append(op)
   after[b][offset:offset+4096]=new
   if b==3:
    buf=bytearray(state);buf[offset:offset+4096]=new;state=bytes(buf)
   file=f'B{b}-{page:02X}-target.bin';(out/file).write_bytes(new)
   targets.append(dict(bank=b,page=page,address=f'B{b}:{page:02X}00',file=file,before_sha256=t.sha(prior),sha256=t.sha(new),purpose='Remove resident utility; retain shared services' if (b,page) in COMMON else 'Remove obsolete legacy image/remnant'))
  after[3]=bytearray(state);j0=t.classify_journal(old[3]);j1=t.classify_journal(state)
  for key in ('default','enabled_mask','entries','unknown_mask'):assert j0[key]==j1[key]
  latest=lambda data:max((data[o:o+256] for o in range(0x4000,0x6000,256) if valid_snapshot(data[o:o+256])),key=lambda r:int.from_bytes(r[8:12],'little'))
  assert latest(old[3])[:8]==latest(state)[:8] and latest(old[3])[12:30]==latest(state)[12:30]
  assert after[3][:0x4000]==old[3][:0x4000] and after[3][0x7000:]==old[3][0x7000:]
  assert after[1][0x3000:0x6000]==old[1][0x3000:0x6000]
  assert after[2][:0x6000]==old[2][:0x6000];assert_preserved(old[2],bytes(after[2]))
  assert after[0][0x2000:0x6000]==old[0][0x2000:0x6000]
  replaced=[r for r in rows if state[int(r['address'],16)-0x8000:int(r['address'],16)-0x8000+256]!=(out/r['file']).read_bytes()]
  for b,v in after.items():(out/f'B{b}-target.bin').write_bytes(v)
  rotations=[s for op in operations for s in op['journal_sector_erases']]
  data=dict(board=board,source_archive=str(SOURCES[board]),targets=targets,operations=operations,image_erases=len(targets),journal_rotation_erases=rotations,total_erases=len(targets)+len(rotations),journal_appends=sum(len(op['journal_appends']) for op in operations),old_journal_rows=rows,replaced_on_chip_old_rows=replaced,journal_before=j0,journal_after=j1,before_bank_sha256={f'B{b}':t.sha(v) for b,v in old.items()},after_bank_sha256={f'B{b}':t.sha(v) for b,v in after.items()},post_cleanup_erased_sectors=[f'B{b}:{i+8:X}' for b,v in after.items() for i in range(8) if v[i*4096:(i+1)*4096]==b'\xff'*4096],SPI_policy='Preserve existing layout and bytes; PROGRAM already empty',qualification_before_write=['Fresh device identity, owner-RAM/ZP/cache/hooks escrow and all-bank hashes must match','RTC priority/serial lease and sufficient collection window','Standalone REC MAINT/FLASH must cover the board CPU path'],qualification_after_write=['All four banks match planned images; exact F/MON and settings/metadata retention','APPS/TABLE/CLOCK/STORE services available; MAINT/FLASH remain host-loaded REC BINs','PROGRAM/WORK geometry and bytes unchanged; owner RAM/ZP/cache/hooks restored; port released'])
  (out/'plan.json').write_text(json.dumps(data,indent=2)+'\n');plan['boards'][board]=data
 plan['total_erases']=sum(z['total_erases'] for z in plan['boards'].values());plan['total_appends']=sum(z['journal_appends'] for z in plan['boards'].values());assert plan['total_erases']==21 and plan['total_appends']==21
 (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 lines=['2604 / 2609 REC utility cleanup - WRITE SCOPE REVIEW','Status: REVIEW ONLY. No erase or programming command is authorized by this file.','',
 'Make the utility profile match 2512. Keep MAINT.bin and FLASH.bin on the host, loaded through REC> at $0200. No firmware build, Foundation F write, MON A/B write, SPI format change, RTC setting change or power cut.',
 '', 'Targets on BOTH boards: B1:8/9/A, B2:E/F, B3:E. Remove resident MAINT/FLASH and retain shared transfer workers, STATUS and the native dispatcher. Also erase obsolete B1:E/F on both. On 2609 also erase obsolete B0:8/9/E/F (including the remaining, already host-backed WDC fragments). Retain current ASM/DBG at B0:A-D.',
 '', 'B3 scope: E is replaced on both; D rotates only on 2604. C and F are never erased; F and MON A/B bytes remain exact. Boot choices, generation bindings, enabled banks/entries and all wear counts carry forward, with the 21 reviewed tracked erase increments.', '']
 for board,z in plan['boards'].items():
  j0=z['journal_before'];j1=z['journal_after'];counts=j1['counts']
  lines.extend([f"{board}: {z['image_erases']} image erases + {len(z['journal_rotation_erases'])} journal erase = {z['total_erases']}; {z['journal_appends']} journal appends; sequence {j0['sequence']} -> {j1['sequence']}.",f"Archive all {len(z['old_journal_rows'])} old valid journal rows. {len(z['replaced_on_chip_old_rows'])} old rows replaced on chip; {len(z['old_journal_rows'])-len(z['replaced_on_chip_old_rows'])} remain byte-for-byte. Final C/D/E/F tracked counts: {counts[28]}/{counts[29]}/{counts[30]}/{counts[31]}.",f"After cleanup: {len(z['post_cleanup_erased_sectors'])} erased sectors ({len(z['post_cleanup_erased_sectors'])*4} KiB). PROGRAM is already empty; no SPI deletion/format/resize planned.",''])
 lines.extend(['HISTORY DECISION: 2604 has only four ordinary append pages left. The reviewed native D rotation replaces 16 old D records on chip. All 26 original rows and the complete preimages are archived on the host; the latest boot policy and cumulative wear values survive in newer records. 2609 needs no C/D erase and retains all 17 old rows on chip.', '', 'Preserve owner RAM $0200-$66FF, ZP $00-$DF, full provider cache $6B00-$77FF and BRK/HOLD hooks through a fresh escrow and independent readback. Preserve board name, local offset, EDU policy, RTC time/trim/power-fail history and SPI data. Keep each board\'s own PROGRAM/WORKSPACE geometry. 2512, 2205 and published downloads remain untouched.', '', 'Before execution, recapture/admit all four banks against before_bank_sha256; refuse any drift or busy marker. Archive preimages/history permanently and untracked. At each sector, reserve wear durably before erase/program; no automatic retry. Yield to RTC between board sessions and before any unstarted transaction. Final checks compare all four banks with the planned result and restore/read back owner RAM. No physical reset is requested; utility Q may restart Foundation through its existing public entry.', '', 'Approval requested for 21 erases total: 2604 nine (including D history rotation), 2609 twelve. No write driver is run by this preparation step.'])
 (OUT/'review-document.txt').write_text('\n'.join(lines)+'\n')
 (OUT/'review.json').write_text(json.dumps(dict(approved=False,plan_sha256=t.sha((OUT/'plan.json').read_bytes()),review_document_sha256=t.sha((OUT/'review-document.txt').read_bytes()),total_erases=21,total_appends=21,F_writes=0),indent=2)+'\n')
 print('Prepared review:2604 nine erases;2609 twelve;21 total; zero F/MON/SPI/RTC writes. No hardware accessed.')
if __name__=='__main__':build()
