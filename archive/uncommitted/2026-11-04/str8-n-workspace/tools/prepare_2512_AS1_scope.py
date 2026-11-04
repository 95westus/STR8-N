"""Fresh read-only PROGRAM allocation/escrow for an AS/1 positive-write review."""
import binascii,json,time
from pathlib import Path
import devtools_2512_session as ds
from serial_test_coordination import drift_pending
t=ds.t;Q=ds.Q;OUT=Q/'2512-AS1-PROGRAM-scope-20261102-r1'
NAME='AS1TRY'
LINES=['ORG $0200','LDA #$42','STA $1800','JMP $7E67','END']

def allocation(meta):
 h=meta[:64];assert len(meta)==0x240 and h[:2]==b'SS' and h[2] in (1,2) and h[3:5]==b'\x08\x08' and h[62:]==b'\0\xa5' and binascii.crc_hqx(h[:62],65535)==0
 pages=int.from_bytes(h[5:7],'little');assert pages in (64,128,192,256)
 used=set(range(8));free=[];records=[]
 for slot in range(8):
  row=meta[(slot+1)*64:(slot+2)*64]
  if row[63]!=0xa5:free.append(slot);continue
  assert row[:4]==b'SP\x01\0' and row[62]==0 and row[32:60]==bytes(28) and binascii.crc_hqx(row[:62],65535)==0
  name=row[16:32].split(b'\0')[0].decode();assert name!=NAME
  length=int.from_bytes(row[6:8],'little');seq=int.from_bytes(row[10:12],'little');kind=row[15];assert seq and kind in (1,2)
  if kind==1:
   extent=set(range(row[14],row[14]+(length+255)//256));assert extent and min(extent)>=8 and max(extent)<pages and not used&extent;used|=extent
  else:assert length==0 and row[14]==0
  records.append(dict(slot=slot,name=name,sequence=seq,kind=kind))
 assert free and max([r['sequence'] for r in records],default=0)<65535
 page=next(p for p in range(8,pages) if p not in used)
 return dict(format=f'SS{h[2]}',pages=pages,slot=max(free),page=page,next_sequence=max([r['sequence'] for r in records],default=0)+1,records=records)

def run():
 print('Preparing2512 AS/1 scope; waiting for RTC window',flush=True)
 while True:
  try:ds.ins.window(150);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,preparation_only=True,flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
 with ds.escrow(OUT,r,'2512-AS1-PROGRAM-readonly-scope',window=150) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'escrow-driver-as-executed.py').write_bytes(Path(ds.__file__).read_bytes())
  x.wb();x.cmd('TABLE P');meta=b''.join(x.raw(a) for a in range(0,0x240,64));(OUT/'PROGRAM-directory.bin').write_bytes(meta)
  a=allocation(meta);slot_address=(a['slot']+1)*64;payload_address=a['page']*256
  original={slot_address:meta[slot_address:slot_address+64]}
  for off in range(0,256,64):
   assert not drift_pending(),'RTC priority before any mutation';original[payload_address+off]=x.raw(payload_address+off)
  for address,body in original.items():(OUT/f'SPI-{address:05X}-original.bin').write_bytes(body)
  source=b''.join((10*n).to_bytes(2,'little')+bytes((len(line),0))+line.encode() for n,line in enumerate(LINES,1))
  capsule=b'AS\x01\x08'+len(source).to_bytes(2,'little')+binascii.crc_hqx(source,65535).to_bytes(2,'little')+source;assert len(capsule)<=256
  (OUT/'expected-AS1-capsule.bin').write_bytes(capsule)
  plan=dict(board='2512',name=NAME,allocation=a,directory_address=f'{slot_address:05X}',payload_start=f'{payload_address:05X}',payload_end=f'{payload_address+255:05X}',temporary_PROGRAM_bytes=320,write_blocks=[f'{v:05X}' for v in original],preimages={f'{k:05X}':t.sha(v) for k,v in original.items()},directory_sha256=t.sha(meta),lines=LINES,source_bytes=len(source),capsule_bytes=len(capsule),capsule_sha256=t.sha(capsule),ASM_manifest=str(t.ROOT/'BUILD/asm-base1-g1-r6/manifest.json'),ASM_sha256='b05b71cf95019fb860bce175302d24a39664676d54bb1ee8b21c742f556fe12b',F_writes=0,flash_erases=0,journal_appends=0,WORKSPACE_writes=0,RTC_writes=0,resets=0,power_cuts=0,other_boards=[],restore_all_320_bytes=True,checks=['SAVE SRAM AS1TRY; exact AS/1 and directory/payload CRC','NEW/LOAD SRAM AS1TRY; LIST/ASM and8 expected output bytes','dirty-source LOAD NO preserves edits','temporary one-byte payload CRC fault refused before source copy, then repair','restore exact original directory slot and256-byte payload page, preserving all other records','restore owner RAM/ZP/cache and verify F/settings/history'])
  t.save(OUT/'plan.json',plan);r['allocation']=a;r['plan_sha256']=t.sha((OUT/'plan.json').read_bytes());x.save()
 r['passed']=bool(r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['provider_cache_restored'] and r['B3_F_images_settings_history_unchanged']);t.save(OUT/'report.json',r);assert r['passed']
 p=json.loads((OUT/'plan.json').read_text())
 text=f'''#2512 AS/1 PROGRAM source persistence: write-scope review

Preparation only, November2,2026. No persistent writes have occurred.

Only2512/COM4; yield to RTC collection. Temporarily use free directory slot{a['slot']}
at SPI ${slot_address:05X}-${slot_address+63:05X} and free payload page
${payload_address:05X}-${payload_address+255:05X}:320 bytes total. Fresh directory
and all320 bytes are archived alongside this plan. Refuse changed preimages,
occupied allocations or an existing AS1TRY; do not choose a different target.

Use the accepted ASM RAM packet, admitted SP/g3 provider, source name AS1TRY,
and the five commented/test program lines in plan.json. Test real source SAVE,
NEW/LOAD, exact AS/1 and payload CRC, reassembly and dirty-load cancellation.
Temporarily flip one payload byte, verify CRC refusal before source copy, then
repair it. Restore every original test byte and read it back; no record remains.

Zero flash erases/programs, journal/metadata appends, F writes, WORKSPACE or RTC
setting/time/trim/PF-ACK writes; no reset/power cut or other-board access. Preserve
all existing records, settings/history and fresh owner RAM0200-66FF/ZP00-DF;
restore borrowed cache7000-74FF and leave original BRK/HOLD hooks unchanged.
Finish at REC>,COM4 released and RTC eligible. Published files stay unchanged.

This review does not authorize writes. The earlier RAM-only allowance explicitly
excluded PROGRAM mutations. Only after owner approval, prepare the bounded
five-block restoration helper and executable trial. Any candidate correction
must stay inside these exact byte/operation limits; no new flash scope is implied.
'''
 (OUT/'review-document.md').write_text(text,encoding='utf-8');print(f'REVIEW2512 slot{a["slot"]}, SPI{slot_address:05X}, payload{payload_address:05X}-{payload_address+255:05X};320 bytes; no writes; owner restored;COM4 free',flush=True)

if __name__=='__main__':run()
