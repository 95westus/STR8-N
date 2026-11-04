"""2205 b35-to-Foundation planning from its permanent SPECIAL capture."""
import binascii,json,sys
from pathlib import Path
from capture_2205_special_permanent import ARCHIVE,F_HASH
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path[:0]=[str(REPO/'tools'),str(REPO/'migration-host')]
from installer.engine import runtime as engine
from installer.engine.legacy_transport import config_sum,read_s19
from nf_migrate import snapshot,valid_snapshot,classify_journal
from journal_rotation_plan import reserve
from prepare_boot_clock_scope_2512 import append_policy
from inventory_boards_readonly import durable

OUT=ROOT/'output/qualification/2205-foundation-rollout-scope-20261102-r1'
KIT=ROOT/'BUILD/unified-g10-candidate4-2512-acceptance-20261102-r1/STR8N-UNIFIED-MON-g00000010-ASMDBG-g2-candidate4'
sha=engine.sha
def seal(row):
 r=bytearray(row);r[30:32]=binascii.crc_hqx(r[:30],65535).to_bytes(2,'little');r[252:254]=binascii.crc_hqx(r[:252],65535).to_bytes(2,'little');assert valid_snapshot(r);return bytes(r)

def run():
 report=json.loads((ARCHIVE/'live-board/report.json').read_text());assert report['passed'] and report['owner_RAM_unchanged'] and report['provider_cache_unchanged']
 banks=[(ARCHIVE/f'live-board/b{i}.bin').read_bytes() for i in range(4)]
 for i,b in enumerate(banks):assert b==(ARCHIVE/f'live-board/b{i}-repeat.bin').read_bytes() and sha(b)==report['bank_sha256'][f'B{i}']
 assert sha(banks[3][-4096:])==F_HASH
 seq,offset,row,valid=engine.clean_journal(banks);cfg=row[8:24];assert cfg[14:]==config_sum(cfg) and cfg[0]==1 and cfg[1]==0 and cfg[8]==0xb0 and int.from_bytes(cfg[9:13],'little')==0x2f
 counts=[max(int.from_bytes(r[24+3*i:27+3*i],'little') for _,_,r in valid) for i in range(32)]
 metadata=[]
 for o in range(0x1c00,0x2000,32):
  r=banks[3][o:o+32]
  if r==b'\xff'*32:continue
  assert r[:4] in (b'TZ\1\0',b'BN\1\0',b'BA\1\0',b'EI\1\0',b'ED\1\0') and r[30:]==b'\xff\0' and binascii.crc_hqx(r[:28],65535)==int.from_bytes(r[28:30],'little')
  metadata.append(dict(address=f'{o+0x8000:04X}',kind=r[:2].decode(),sequence=int.from_bytes(r[4:8],'little'),raw=r.hex()))
 freeze=json.loads((REPO/'F_FREEZE.json').read_text());f=(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();assert sha(f)==freeze['sha256'] and all(sha((REPO/n).read_bytes())==h for n,h in freeze['sources'].items())
 catalog=json.loads((KIT/'NATIVE-COMPONENTS.json').read_text());assert len(catalog['targets'])==20 and len(catalog['retirement_targets'])==9
 retained=offset&0x7000;peer=retained^0x1000;assert retained in (0x4000,0x5000)
 free=next(a for a in range(retained,retained+0xf80,128) if banks[3][a:a+256]==b'\xff'*256)
 reserved=counts.copy()
 for o in (peer,0x7000,retained):reserved[24+o//4096]+=1
 reservation=engine.record(cfg,reserved,seq+1);base=list(map(bytearray,banks));base[3][free:free+128]=reservation
 conversion=[]
 for off,n in ((peer,seq+2),(0x7000,None),(retained,seq+3)):
  if n is None:body=f;commit=None
  else:
   root=bytearray(snapshot(reserved,n));root[18:22]=(16).to_bytes(4,'little');root[32:48]=cfg;body=seal(root)+b'\xff'*3840;commit=off+0x8000+255
  conversion.append(dict(bank=3,address=f'{off+0x8000:04X}',commit_address=commit,before_sha256=sha(base[3][off:off+4096]),sha256=sha(body),body=body));base[3][off:off+4096]=body
 assert classify_journal(base[3])['default']=='S'
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 durable(OUT/'legacy-reservation-128.bin',reservation)
 for i,b in enumerate(banks):durable(OUT/f'B{i}-original.bin',b)
 for i,op in enumerate(conversion):op['file']=f'conversion-{i}-B3-{op["address"]}.bin';durable(OUT/op['file'],op.pop('body'))
 shared=dict(board='2205',port='COM3',USB_serial='A10MPUPNA',permanent_archive=str(ARCHIVE),source_F_sha256=F_HASH,target_F_sha256=freeze['sha256'],legacy_sequence=seq,legacy_config_hex=cfg.hex(),legacy_counts=counts,legacy_records=len(valid),legacy_reservation_address=f'{free+0x8000:04X}',legacy_reservation_sequence=seq+1,conversion=conversion,converted_bank_sha256={f'B{i}':sha(v) for i,v in enumerate(base)},converted_journal=classify_journal(base[3]),metadata_records=metadata,F_replacements=1,F_rebuilt=False,RTC_setting_writes=0,SPI_writes=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,physical_resets=3,runtime_policy='Archive legacy cache/vectors; initialize matching Foundation runtime. Preserve original owner RAM0200-66FF/ZP00-DF.',boot_policy='Retain B default, bind new MONg10; S only during conversion/install. Disabled legacy app config remains archived/imported.',admission_pending=['Full SPI companion and exact legacy owner restoration','Unchanged-board physical reset into legacy B3 and bounded S19/G/HOLD route','Fresh full-bank/owner/RTC-priority admission before writes'])
 # Compose the existing qualified conversion engine; only source/target tables
 # and the WC reservation change. There is no assembly or CPU simulation.
 state=list(map(bytearray,banks));ops=[];data=[]
 for bank,address,body,commit,kind in [(3,free+0x8000,reservation,free+0x8000+127,'legacy-WC-reservation')]+[(3,int(x['address'],16),(OUT/x['file']).read_bytes(),x['commit_address'],'conversion-sector') for x in conversion]:
  before=engine.hashes(state);off=address-0x8000;state[bank][off:off+len(body)]=body;ops.append(dict(kind=kind,bank=bank,address=address,commit_address=commit,source_sha256=before,after_sha256=engine.hashes(state),data_sha256=sha(body)));data.append(body)
 tx=dict(source_sha256=engine.hashes(banks),expected_sha256=engine.hashes(state),operations=ops,reservation_offset=free,counts_before=counts,reserved_counts=reserved,sequence_before=seq,sequence_after=seq+3,model_only=True,installation_permitted=False)
 info=engine.compose(ROOT/'tools/installer/engine/template',OUT/'conversion-engine-review',banks,tx,data,list(map(bytes,state)))
 original,entry=read_s19(ROOT/'tools/installer/engine/template/integrated-template.s19');composed,newentry=read_s19(OUT/'conversion-engine-review/installer-model-only.s19');mf=json.loads((ROOT/'tools/installer/engine/template/manifest.json').read_text())
 allowed={mf['count'],mf['commit_after']}|set(range(0x3500,0x3516))|set(range(0x3600,0x3700))
 for key,n in [('banks',24),('commits',24),('commit_addresses',96),('commit_values',24),('table',216)]:allowed.update(range(mf[key],mf[key]+n))
 assert entry==newentry==0x2000 and set(original)==set(composed) and {a for a in original if original[a]!=composed[a]}<=allowed
 durable(OUT/'conversion-engine-review/static-review.json',(json.dumps(dict(passed=True,unchanged_executable_bytes=True,board_access=False,firmware_builds=0,CPU_simulations=0,installer_sha256=info['installer_sha256'],converted_journal=classify_journal(base[3])),indent=2)+'\n').encode())
 options={}
 for variant,retire in (('core',False),('compact',True)):
  out=OUT/variant;out.mkdir();(out/'targets').mkdir();state=list(map(bytearray,base));targets=[];operations=[];same=[]
  items=list(catalog['targets'])+(catalog['retirement_targets'] if retire else [])
  # Install MON A/B first, then the common tools; default remains S throughout.
  items.sort(key=lambda x:(0 if x['bank']==3 and x['address'] in ('A000','B000') else 1,x['bank'],int(x['address'],16)))
  for item in items:
   b,a=item['bank'],int(item['address'],16);record=item['variants']['65c02'] if 'variants' in item else item;body=(KIT/record['file']).read_bytes();assert sha(body)==record['sha256']
   if item.get('preserve_RTC_metadata'):assert b==3 and a==0x9000 and len(body)==3072;body+=banks[3][0x1c00:0x2000]
   assert len(body)==4096 and not(b==3 and a in (0xc000,0xd000,0xf000))
   off=a-0x8000;before=bytes(state[b][off:off+4096])
   if before==body:same.append(f'B{b}:{a:04X}');continue
   journal,op=reserve(bytes(state[3]),b*8+off//4096);state[3]=bytearray(journal);operations.append(op);state[b][off:off+4096]=body
   name=f'targets/B{b}-{a:04X}.bin';durable(out/name,body);targets.append(dict(bank=b,address=f'{a:04X}',label=item['role'],file=name,before_sha256=sha(before),sha256=sha(body),retirement=item in catalog['retirement_targets']))
  state[3],binding=append_policy(bytes(state[3]),{7:ord('B'),**{18+i:v for i,v in enumerate((16).to_bytes(4,'little'))}},'CONFIG C B; bind replacement MONg10');operations.append(binding)
  final=classify_journal(state[3]);assert final['kind']=='valid-snbt' and final['default']=='B' and final['counts'][31]==counts[31]+1
  rotations=[z for op in operations for z in op['journal_sector_erases']]
  for i,v in enumerate(state):durable(out/f'B{i}-expected.bin',bytes(v))
  p={**shared,'variant':variant,'status':'REVIEW_READY_NO_HARDWARE_WRITES','targets':targets,'native_operations':operations,'native_journal_rotations':rotations,'image_erases':len(targets),'total_erases':3+len(targets)+len(rotations),'native_appends':sum(len(op['journal_appends']) for op in operations),'journal_after':final,'expected_bank_sha256':{f'B{i}':sha(v) for i,v in enumerate(state)},'retirement_erases':sum(x['retirement'] for x in targets),'identical_skipped':same,'scope_choice_required_for_retirement':retire}
  durable(out/'plan.json',(json.dumps(p,indent=2)+'\n').encode());options[variant]=dict(total_erases=p['total_erases'],image_erases=len(targets),retirement_erases=p['retirement_erases'],journal_rotations=rotations,native_appends=p['native_appends'],final_C_D_E_F=final['counts'][28:],final_sequence=final['sequence'])
 text=f'''2205 b35 SPECIAL -> Foundation/MON/ASM/DBG WRITE REVIEW
The permanent special original is {ARCHIVE}.
All4 flash banks match independent native repeats; RAM/ZP/cache/vectors unchanged.
Source F {F_HASH}; target F {freeze['sha256']} (exact frozen4096 bytes).

Existing firmware is2.0b35, A g28/B g2F, default B. Legacy WC sequence{seq}
has{len(valid)} valid128-byte rows. Every original row and image remains in the
permanent host archive. Import the maximum tracked count for each of32 sectors;
prior/direct wear remains unknown. Rebuilding C/D replaces legacy rows on chip.

CONVERSION (common): append WC seq{seq+1} at B3:{free+0x8000:04X} to reserve
three erases, then replace B3:{peer+0x8000:04X}, F, B3:{retained+0x8000:04X}.
Each new journal commits last, default S. The unchanged RAM engine verifies
full-bank source guards and each transferred payload. One frozen F replacement;
F stays golden thereafter. Physical RESET to B3/recovery follows conversion.

OPTIONS
Core: {options['core']['total_erases']} total erases, {options['core']['image_erases']} required component replacements,
{len(options['core']['journal_rotations'])} native C/D rotation(s), {options['core']['native_appends']} native appends.
Keep non-overlapping old sectors on chip as unqualified legacy data.
Compact: {options['compact']['total_erases']} total erases, including {options['compact']['retirement_erases']} explicit retirements
of leftover WDC/old-app sectors, plus {len(options['compact']['journal_rotations'])} native rotation(s).
Retire B0:8/9/E/F, B1:8/9/E/F, B2:E only after that optional scope is chosen.
This yields the same clean compact profile as2512/2604/2609, with REC-loaded
MAINT/FLASH and36KiB in erased sectors. Those original images remain archived.

Both use the exact20 active Candidate4 CPU02 components: MON A/B g10,
ASM/DBG g2, CLOCK, WB/PROGRAM, SRAM/WORK, STATUS and shared services.
All original B3:9C00-9FFF metadata is retained: board2205, offset-06:00,
battery/EUI history. RTC trim-17/control80 and all external RTC/EEPROM data
stay unchanged. Keep every SPI PROGRAM/WORKSPACE byte and its existing split;
no format, resize, reclaim, record deletion, clock SET/TRIM/ACK or power cut.

Restore default B bound to g10 after image verification. Original disabled
legacy application config remains verbatim in SNBT32-47; no opaque bank is
implicitly enabled. All erase counts include conversion and native rotations.

Fresh admission requires: completed full128KiB SPI companion and owner restore;
verified unchanged-board physical B3 reset path; matching four-bank hashes,
idle COM3 USB A10MPUPNA and RTC-priority window; fresh RAM/ZP escrow. Preserve
owner0200-66FF/00-DF. Archive the old provider cache/vectors and initialize the
matching Foundation runtime; do not copy rc1/b35 runtime vectors over BASE1.
Three physical resets are budgeted: unchanged-board path proof, conversion,
and final default-B acceptance. Receivers are armed before requesting presses.

After programming, independently verify all4 banks, boot policy, counters and
metadata. Test A/B startup, VERSION/TIME trim, CLOCK queries, APPS/TABLE,
EDU/SRAM/WORK queries, RAM BATCH/loaders, ASM assemble/run/HOLD and DBG step/
continue/cleanup. MAINT/FLASH remain host-loaded REC BINs. No positive persistent
source-write fixture is included. Verify full SPI unchanged and owner RAM/ZP
restored, then register a2205-only RTC profile retaining campaign baselines,
calibration/history and all other boards' routing. Published files unchanged.

This is review/data preparation only. No flash command has run. Existing owner
instruction authorizes Foundation/MON/ASM/DBG and journal reconstruction as
needed; optional retirement is a separate concrete choice. No simulation or
firmware rebuild occurred. Refuse changed preimages and automatic retries.
'''
 durable(OUT/'review-document.txt',text.encode());durable(OUT/'options.json',(json.dumps(options,indent=2)+'\n').encode())
 print(json.dumps(options,indent=2))

if __name__=='__main__':run()
