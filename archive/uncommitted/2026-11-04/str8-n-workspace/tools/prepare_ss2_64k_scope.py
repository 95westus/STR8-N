"""Host-only SS2/64K scope from archived metadata; no serial or build calls."""
import binascii,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'output/qualification';REPO=ROOT/'release/str8nf-v0.2.0'
OUT=Q/'SS2-64K-three-board-scope-20261102-r1'
SHA=lambda v:hashlib.sha256(v).hexdigest()
CASES={
 '2512':('COM4','A10MQFLCA','2512-candidate4-physical-keys-20261102-r2/SPI-metadata-after.bin','SS1',0x10000),
 '2604':('COM5','A10MQGVHA','2604-REC-utility-cleanup-verified-20261102-r3/SPI-metadata-after.bin','SS2',0x4000),
 '2609':('COM8','A10MPQXCA','2609-REC-utility-cleanup-installed-20261102-r1/SPI-metadata-before.bin','SS1',0x10000)}

def save(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def seal(packet):
 v=bytearray(packet);v[60:62]=binascii.crc_hqx(v[:60],65535).to_bytes(2,'big');v[62]=0;v[63]=0xa5
 assert binascii.crc_hqx(v[:62],65535)==0
 return bytes(v)
def ranges(addresses):
 result=[]
 for n in sorted(addresses):
  if result and n==result[-1][1]+1:result[-1][1]=n
  else:result.append([n,n])
 return [dict(start=f'{a:05X}',end=f'{b:05X}',bytes=b-a+1) for a,b in result]

def run():
 import sys
 sys.path.insert(0,str(REPO/'tools'));from program_format import inspect
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 freeze=json.loads((REPO/'F_FREEZE.json').read_text());assert SHA((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
 for n,h in freeze['sources'].items():assert SHA((REPO/n).read_bytes())==h
 plan=dict(status='PREPARED_FROM_ARCHIVES_NOT_LIVE_ADMITTED_NOT_APPROVED',prepared_local_date='2026-11-02',hardware_access=False,firmware_builds=0,CPU_simulations=0,flash_writes=0,flash_erases=0,journal_appends=0,RTC_setting_writes=0,physical_resets=0,power_cuts=0,excluded_boards=['2205'],F_sha256=freeze['sha256'],target=dict(format='SS2',PROGRAM_boundary='10000',PROGRAM_payload_bytes=63488,WORKSPACE_payload_start='10000',WORKSPACE_payload_end='1FFDF',WORKSPACE_payload_bytes=65504),boards={})
 source=REPO/'monitors/native/sram-work-classic.inc';plan['reviewed_source_sha256']=SHA(source.read_bytes())
 actual=(ROOT/'BUILD/storage-installed-auto-r2/SRAM-WORK-g4-flash.bin').read_bytes();plan['installed_storage_image_sha256']=SHA(actual)
 for b,(port,usb,rel,fmt,boundary) in CASES.items():
  out=OUT/b;out.mkdir();path=Q/rel;old=path.read_bytes();assert len(old)==2048
  layout=inspect(old+bytes(0x20000-len(old)));assert layout['format']==fmt and int(layout['boundary'],16)==boundary and not layout['records']
  marker=json.loads((Q/f'device-operations/{b}.json').read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
  # This scope admits only an allocation-free SS2 session; a claim requires
  # separate relocation/release review, even if its bytes would remain intact.
  claims=[dict(slot=i,packet=old[0x300+32*i:0x320+32*i].hex()) for i in range(4) if old[0x31f+32*i]==0xa5]
  assert fmt=='SS1' or not claims
  new=bytearray(old);header=bytearray(old[:64]);allowed=set(range(64))|set(range(0x240,0x280))
  if fmt=='SS1':
   header[2]=2;header[8:12]=(1).to_bytes(4,'little')
   session=bytearray(64);session[:3]=b'WS\x01';session[4:8]=(1).to_bytes(4,'little');session[8:12]=(1).to_bytes(4,'little');new[0x280:0x2c0]=seal(session)
   new[0x2ff]=0
   for i in range(4):new[0x31f+32*i]=0
   allowed|=set(range(0x280,0x2c0))|{0x2ff}|{0x31f+32*i for i in range(4)}
   action='Native WORK U upgrade (UPGRADE! confirmation); retain64K boundary'
   generation=1;epoch=1;revision=1
  else:
   # Recorded2604 has one authoritative WS packet at280, rev1/epoch1.
   session=bytearray(old[0x280:0x2c0]);assert session[:3]==b'WS\x01' and session[63]==0xa5 and binascii.crc_hqx(session[:62],65535)==0
   assert old[0x2ff]!=0xa5
   revision=int.from_bytes(session[4:8],'little')+1;epoch=int.from_bytes(session[8:12],'little')+1;assert revision<2**32 and epoch<2**32
   session[4:8]=revision.to_bytes(4,'little');session[8:12]=epoch.to_bytes(4,'little');session[12:14]=bytes(2);new[0x2c0:0x300]=seal(session)
   header[5:7]=(256).to_bytes(2,'little');generation=layout['generation']+1;header[8:12]=generation.to_bytes(4,'little')
   allowed|=set(range(0x2c0,0x300))
   action='Native WORK P64 resize (RESIZE!! confirmation); fresh instance advances WS epoch once'
  new[:64]=new[0x240:0x280]=seal(header)
  changed={i for i,(a,z) in enumerate(zip(old,new)) if a!=z};assert changed<=allowed
  assert old[0x40:0x240]==new[0x40:0x240] and old[0x380:]==new[0x380:]
  post=inspect(bytes(new)+bytes(0x20000-len(new)));assert post['format']=='SS2' and post['boundary']=='10000' and not post['records']
  (out/'SPI-metadata-original.bin').write_bytes(old);(out/'SPI-metadata-expected.bin').write_bytes(new);save(out/'marker-reference.json',marker)
  item=dict(board=b,port=port,usb_serial=usb,archived_metadata_source=str(path),original_metadata_sha256=SHA(old),expected_metadata_sha256=SHA(new),original_format=fmt,original_PROGRAM_boundary=f'{boundary:05X}',PROGRAM_records=0,managed_claim_packets=claims if fmt=='SS2' else 'not defined by SS1',action=action,expected_layout_generation=generation,expected_session_revision=revision,expected_session_epoch=epoch,permitted_SPI_write_ranges=ranges(allowed),distinct_SPI_addresses_permitted=len(allowed),expected_changed_metadata_bytes=len(changed),preserved_PROGRAM_directory='00040-0023F',preserved_payload='00800-1FFFF byte-for-byte',preserved_other_metadata='all bytes outside permitted ranges',full_131072_byte_capture_available_for_this_scope=False,fresh_full_capture_required=True,reference_flash_bank_sha256=marker['current_physical_bank_sha256'],F_writes=0,journal_writes=0)
  if b=='2604':item['reclassified_without_copy_or_zero']=dict(start='04000',end='0FFFF',bytes=49152,meaning='old unclaimed WORKSPACE becomes PROGRAM allocation space; original bytes retained but may be used by later STORE operations')
  save(out/'plan.json',item);plan['boards'][b]=item
 plan['total_distinct_SPI_addresses_permitted']=sum(v['distinct_SPI_addresses_permitted'] for v in plan['boards'].values());assert plan['total_distinct_SPI_addresses_permitted']==586
 plan['execution_order']=['2512','2609','2604'];plan['execution_preconditions']=[
 'RTC lease/window first; one board only per window; verify exact USB identity and idle/recovery prompt',
 'Fresh owner RAM0200-66FF, ZP00-DF, cache6B00-77FF and BRK/HOLD escrow; retain matching runtime state',
 'Fresh full131072-byte SPI capture before any mutating WORK call; archive durably/untracked on host; validate PROGRAM and SS2 sessions/claims without writing',
 'Fresh first2048 bytes must equal scope original; any drift or allocation conflict stops and requires refreshed scope',
 'All active PROGRAM records must be preserved; this scope requires the recorded empty directories. No record deletion, relocation, format or reclaim',
 '2604 must have no committed WORK claims before entering a new epoch; native epoch rollover must not be used to hide/release a preexisting claim',
 'Check all four flash banks unchanged, including F, boot/wear journal and board metadata; verify installed B1:B-D storage image hash',
 'Use existing native manager operation only; no direct byte-patching layout, no FORMAT, REPAIR, extra resize, test STORE/CLAIM, payload writes or persistent EDU save',
 'Before mutating metadata ensure enough time for command verification and owner restoration; on RTC request do not begin next board/operation; finish verified command/cleanup and yield',
 'No automatic retry after failure; preserve pre/post evidence and use only reviewed original metadata bytes for bounded rollback after validating data unchanged']
 plan['acceptance']=[
 'SS2 primary/peer headers valid and identical; boundary10000; expected generation and WS revision/epoch',
 'Full SPI after-image equals fresh full before-image with exactly the predicted metadata delta; every byte00800-1FFFF and PROGRAM directory unchanged',
 'Any claimed WORK extent or unexpected metadata change stops; no forced release or hidden allocation movement',
 'TABLE P and WORK ? query only; no additional mutating WORK call and no temporary payload fixture',
 'All four flash banks exact; boot settings, cumulative wear/history, board identity/offset/EDU and RTC time/trim/power-fail data unchanged',
 'Owner RAM/ZP/cache/hooks restored/read back; provider/runtime state valid; REC> and each port released; RTC collection may resume']
 save(OUT/'plan.json',plan)
 text='''SS2 / 64K PROGRAM + 64K WORKSPACE - THREE-BOARD WRITE SCOPE
Prepared November 2, 2026. REVIEW ONLY; NO LIVE ADMISSION OR WRITES PERFORMED.

Targets:2512/COM4,2609/COM8,2604/COM5. Never open2205/COM3.
Use existing installed SRAM/WORK g4. No firmware build or simulation.
Zero flash erases/programs, zero Foundation F/MON changes, zero C/D boot/wear
journal appends, zero RTC-setting/history/EEPROM writes, zero physical resets
or power cuts. Published downloads and the candidate4 ZIP remain unchanged.

DATA POLICY
Keep the entire SPI payload $00800-$1FFFF byte-for-byte and PROGRAM directory
$00040-$0023F exact. Only the management-cell ranges below may change. The
archived metadata shows all eight PROGRAM slots uncommitted on each board.
2604 has no committed WORK claims; SS1 has no managed WORK allocation scheme.
This is evidence from archives, not a current live admission. Preserve any
newer record or claim by stopping and preparing a refreshed scope.

2512 and2609: SS1/64K -> SS2/64K using native U (UPGRADE!).
Allowed SPI addresses on EACH (197 distinct addresses, not a count of bus writes):
  $00000-$0003F primary layout; $00240-$0027F backup layout;
  $00280-$002BF initial WS session; $002FF old WS peer commit marker;
  $0031F/$0033F/$0035F/$0037F claim commit markers.
Expected layout generation1; WS revision1/epoch1. Existing unused management
cells are initialized; their original raw bytes are retained in the host archive.
Neither payload nor the 64K boundary moves. No bulk format/zero operation.

2604: SS2/16K -> SS2/64K using native P 64 (RESIZE!!).
Allowed SPI addresses (192 distinct): $00000-$0003F, $00240-$0027F,
and $002C0-$002FF. Expected layout generation2->3, WS revision1->2 and
epoch1->2 on the fresh manager's first mutating call. Original WS A and all
four claim packets stay exact. Refuse any preexisting committed WORK claim
BEFORE epoch rollover; do not let lazy epoch initialization hide allocations.

2604 RECLASSIFICATION: $04000-$0FFFF (49,152 bytes) becomes PROGRAM allocation
space instead of WORKSPACE. No bytes are copied, cleared or rewritten there.
Raw unclaimed data in that range is retained and archived, but later STORE
may allocate over it. If it is still needed as WORKSPACE, stop and review a
relocation first. There is no generic way to identify arbitrary raw data's owner.

Final on all: SS2; PROGRAM boundary $10000, payload $00800-$0FFFF =63,488 bytes;
WORK payload $10000-$1FFDF =65,504 bytes. The final32 SPI bytes are outside the
managed WORK payload and remain exact. Total maximum address allowance586,
all in management cells. No temporary STORE/CLAIM/WORK payload tests included.

FRESH ADMISSION AND PRESERVATION
Before execution: acquire shared serial lease and RTC window; check USB/board
identity, idle markers and matching native component bytes. Capture all4 banks,
complete128KiB SPI and owner RAM/ZP/cache/hooks. Archive durably and untracked.
Require metadata identical to the pinned per-board original and empty PROGRAM;
validate session CRCs and WORK claims BEFORE any mutating API call. The full
SPI capture is still pending and is mandatory before approval is exercised.
Inspect2604's reclassified region; do not infer erased/free from arbitrary bytes.
No positive operation is included by merely reading WORK capacity or TABLE.

Execute one board at a time:2512,2609,2604. Yield to RTC before each admission
and unstarted mutation. Reserve enough collection margin for command plus
verification/restoration; once begun, finish that small verified metadata
transaction and cleanup before releasing the port. No whole-fleet port hold.
No deliberate RESET or USB power interruption. No automatic failure retry.

AFTER EACH BOARD
Read all128KiB SPI: require exactly the forecast metadata changes and exact
PROGRAM directory/all payload/other metadata retention. Query TABLE P and
WORK capacity without starting another mutation. Read all4 banks: require
exact F, images, boot policy, wear/history and board metadata. Restore and
independently verify owner RAM0200-66FF, ZP00-DF, cache6B00-77FF, BRK/HOLD
hooks and valid runtime/provider state. Finish REC>, port released.
Do not change RTC time/trim/power-fail flags/history, saved EDU or LED agent.

RECOVERY BOUNDARY
On unexpected command result stop and retain evidence; no retry, format,
repair or forced claim release. If only allowed metadata changed and payload
is exact, rollback may restore exactly the archived allowed metadata cells,
then verify all128KiB and owner RAM. A changed payload or unavailable prompt
requires a new recovery review; do not guess or touch F. Rollback retains the
old SS1/SS2 format, not a falsely reported successful conversion.

APPROVAL BOUNDARY
This prepares a three-board metadata-only standardization, not permission to
run it. An approval must cover SS1 management initialization on2512/2609,
2604's48KiB logical reclassification and single session-epoch advance, the
bounded original-metadata rollback, and fresh RAM escrow/verification. Any
new allocation or differing metadata requires a refreshed review.
'''
 (OUT/'review-document.txt').write_text(text)
 save(OUT/'review.json',dict(approved=False,status=plan['status'],plan_sha256=SHA((OUT/'plan.json').read_bytes()),review_document_sha256=SHA((OUT/'review-document.txt').read_bytes()),SPI_address_allowance=586,flash_writes=0,hardware_access=False,execution_ready=False,reason='Scope prepared; approval and fresh live SPI admission still required'))
 print('Prepared SS2/64K review:2512/2609 upgrade,2604 resize;586 management addresses maximum; zero hardware/build/flash activity.')

if __name__=='__main__':run()
