"""Concrete SF/1 positive/installation review, host-only; not a write driver."""
import binascii,json,sys
from pathlib import Path
from devtools_2512_session import t,Q
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
BUILD=t.ROOT/'BUILD/asm-flash-source-g2-r4';RAM=Q/'2512-AS1-FLASH-readonly-RAM-20261102-r2';OUT=Q/'2512-AS1-FLASH-scope-20261102-r1'
LINES=['ORG $0200','LDA #$42','STA $1900','JMP $7E67','END'];NAME='AS2TRY'
def run():
 r=json.loads((RAM/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['provider_cache_restored'] and len(r['checks'])==8
 recovery=Q/'2512-AS1-FLASH-post-fault-audit-20261102-r1/report.json';assert json.loads(recovery.read_text())['passed']
 mp=Q/'device-operations/2512.json';m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['block_snapshot'] and not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
 old={b:(RAM/f'B{b}-after.bin').read_bytes() for b in (0,3)};assert all(t.sha(v)==m['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
 assert old[0][0x1000:0x2000]==b'\xff'*4096
 source=b''.join((n*10).to_bytes(2,'little')+bytes((len(line),0))+line.encode() for n,line in enumerate(LINES,1));cap=b'AS\x01\x08'+len(source).to_bytes(2,'little')+binascii.crc_hqx(source,65535).to_bytes(2,'little')+source
 h=bytearray(32);h[:4]=b'SF\x01\xff';h[4:6]=len(cap).to_bytes(2,'little');h[6]=1;h[8:8+len(NAME)]=NAME.encode();h[24:26]=binascii.crc_hqx(h[:24],65535).to_bytes(2,'little');h[3]=0x3f
 fixture=(h+cap).ljust(4096,b'\xff');assert len(h+cap)==98 and fixture[0x28]==10 and fixture[2]==1
 fault=bytearray(fixture);fault[0x28]=8;fault[2]=0
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'expected-SF1-sector.bin').write_bytes(fixture);(OUT/'expected-AS1-capsule.bin').write_bytes(cap);(OUT/'expected-final-fault-sector.bin').write_bytes(fault)
 images={b:bytearray(v) for b,v in old.items()};state=old[3];targets=[];ops=[]
 for bank,page,file,offset in ((0,0xa0,'ASM-FLASH.bin',0),(0,0xb0,'ASM-FLASH.bin',4096),(0,0xc0,'DBG-FLASH.bin',0),(0,0xd0,'DBG-FLASH.bin',4096),(0,0x90,None,0)):
  at=(page-0x80)*256;before=old[bank][at:at+4096];body=(BUILD/file).read_bytes()[offset:offset+4096] if file else b'\xff'*4096
  state,op=reserve(state,bank*8+(page-0x80)//16);assert not op['journal_sector_erases'];ops.append(op)
  images[bank][at:at+4096]=body;n=f'B{bank}-{page:02X}-target.bin';(OUT/n).write_bytes(body);(OUT/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
  targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=n,sha256=t.sha(body),before_sha256=t.sha(before),kind='fixture cleanup' if not file else 'paired app upgrade',write_preimage_sha256=t.sha(fault) if not file else t.sha(before)))
 images[3]=bytearray(state)
 for i in range(0x4000,0x6000,256):
  if valid_snapshot(old[3][i:i+256]):assert old[3][i:i+256]==state[i:i+256]
 before=t.classify_journal(old[3]);after=t.classify_journal(state);assert before['sequence']==1182 and before['valid_records']==25 and after['sequence']==1187 and after['valid_records']==30 and after['counts'][28:]==before['counts'][28:]==[57,38,38,24]
 for b in (0,3):(OUT/f'B{b}-original.bin').write_bytes(old[b]);(OUT/f'B{b}-target.bin').write_bytes(images[b])
 p=dict(board='2512',status='REVIEWED_WITHIN_STANDING_FLASH_AUTHORIZATION',authorization=['continue, approve flash 2512, make 2609 boot the default monitor','next is? / ASM source SAVE-LOAD FLASH on2512 / continue'],targets=targets,total_erases=5,operations=ops,F_writes=0,MON_writes=0,E_writes=0,C_D_erases=0,source_name=NAME,source_lines=LINES,source_bytes=len(source),capsule_bytes=len(cap),SF1_bytes=len(h+cap),maximum_source_byte_programs=100,source_faults=[dict(address='B0:9028',before='0A',after='08',purpose='AS/1 payload CRC refusal'),dict(address='B0:9002',before='01',after='00',purpose='SF/1 header refusal')],SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,other_boards=[],before_journal=before,after_journal=after,before_bank_sha256=m['current_physical_bank_sha256'],after_bank_sha256={**m['current_physical_bank_sha256'],**{f'B{b}':t.sha(v) for b,v in images.items()}},build_manifest_sha256=t.sha((BUILD/'manifest.json').read_bytes()),RAM_report_sha256=t.sha((RAM/'report.json').read_bytes()),post_fault_audit_sha256=t.sha(recovery.read_bytes()),owner_cache='6B00-77FF',checks=['RAM-source SAVE FLASH with exact YES; byte-for-byte SF/1+AS/1 verification','fresh-session LOAD/LIST/ASM; duplicate and dirty-load cancellation','paired ASM/DBG install; installed R ASM LOAD FLASH and exact8-byte output/run','two bounded1->0 corruption checks refuse before source copy','B0:9 exact FF cleanup and five predicted journal appends','DBG AP/02 startup, cancellation/step/return and all unrelated images unchanged','owner RAM/ZP/full provider restored; RTC host admission retained'])
 t.save(OUT/'plan.json',p)
 text=f'''# 2512 SF/1 source persistence and paired-app upgrade scope

Reviewed under the owner's standing2512 flash approval and subsequent
instruction to continue with source SAVE/LOAD FLASH. The earlier installation
is closed; this is a separate bounded execution plan, not an automatic retry.

Five new erases: B0:A/B/C/D replace the existing paired ASM/DBG apps with the
source-extension build; B0:9 has one final cleanup erase restoring its original
all-FF contents. No new sector allocation: the source provider occupies DBG's
unused D800-DFFF padding, within the existing104KiB selected profile.

Before installation, use only B0:9 for source name {NAME}. Save a58-byte source
inside a66-byte AS/1 capsule and32-byte SF/1 header (98 bytes total). Each SAVE
requires the exact B0:9000 one-sector YES prompt. Verify real RAM and installed
LOAD/LIST/ASM; duplicate/cancel paths; then clear only9028:$0A->$08 and
9002:$01->$00 to prove payload/header refusal before live source is changed.
At most100 byte-program calls; no erase during SAVE, no automatic retry.

Finally clean B0:9 with the one reviewed erase. Five wear reservations:
{', '.join(o['journal_appends'][0]['page'] for o in ops)}, sequences1183-1187.
All25 existing C/D rows remain byte-for-byte on chip; no journal rotation.
B0:9 count26->27; A6->7, B1->2, C1->2, D1->2. C/D/E/F stay57/38/38/24.

Preserve F, MON A/B g10, E dispatcher, saved B generation and every boot/board
setting; all other flash images, all SPI SRAM/WORKSPACE, RTC time/trim/PF data,
fresh owner RAM0200-66FF/ZP00-DF and full provider cache6B00-77FF. No reset,
power cut, SPI data/RTC-setting write, other-board access or published change.
RTC collection retains priority. Finish at REC> with COM4 released.

The first read-only candidate lost X across SELECT. A physical RESET restored
the board. Every flash bank and owner/cache was verified, all131072 SPI bytes
matched the preserved baseline, and native RTC flags28/trim0C/control80 were
intact. The corrected candidate passed the read-only RAM suite before this
review. Execution is bounded to this concrete five-erase scope, with zero
automatic retries and no loss of retained owner images or journal history.
'''
 (OUT/'review-document.md').write_text(text,encoding='utf-8')
 t.save(OUT/'authorization.json',dict(authorized=True,owner_statements=p['authorization'],interpretation='Continuing the requested ASM FLASH increment under persistent2512 flash approval; reviewed project-app upgrades only, blank fixture restored, no history replacement or other-board scope',plan_sha256=t.sha((OUT/'plan.json').read_bytes()),review_sha256=t.sha((OUT/'review-document.md').read_bytes())))
 print(text)
if __name__=='__main__':run()
