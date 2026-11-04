"""Review the owner's authorized five-sector ASM/DBG installation; no ports."""
import json,sys
from pathlib import Path
from devtools_2512_session import t,Q
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot
BUILD=t.ROOT/'BUILD/devtools-AP02-g1-r2';PRE=Q/'2512-devtools-flash-preflight-20261102-r1';RAM=Q/'2512-devtools-launcher-RAM-20261102-r1';OUT=Q/'2512-devtools-flash-scope-20261102-r1'
def run():
 rr=json.loads((RAM/'report.json').read_text());assert rr['passed'] and rr['owner_RAM_restored'] and rr['owner_ZP_restored'] and rr['provider_cache_restored']
 m=json.loads((Q/'device-operations/2512.json').read_text());assert m['application_ram_restored'] and not m['block_snapshot'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
 old={b:(PRE/f'B{b}-original.bin').read_bytes() for b in range(4)};assert all(t.sha(v)==m['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
 mf=json.loads((BUILD/'manifest.json').read_text());images={b:bytearray(v) for b,v in old.items()};targets=[];ops=[];state=old[3]
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 for bank,page,file,offset in ((0,0xa0,'ASM-FLASH.bin',0),(0,0xb0,'ASM-FLASH.bin',4096),(0,0xc0,'DBG-FLASH.bin',0),(0,0xd0,'DBG-FLASH.bin',4096),(3,0xe0,'SERVICES-E.bin',0)):
  body=(BUILD/file).read_bytes()[offset:offset+4096];assert len(body)==4096
  at=(page-0x80)*256;before=old[bank][at:at+4096]
  if bank==0:assert before==bytes(4096),'Do not replace a newly occupied owner target'
  state,op=reserve(state,bank*8+(page-0x80)//16);assert not op['journal_sector_erases'];ops.append(op)
  if bank==3:a=bytearray(state);a[at:at+4096]=body;state=bytes(a)
  else:images[bank][at:at+4096]=body
  n=f'B{bank}-{page:02X}-target.bin';(OUT/n).write_bytes(body);(OUT/f'B{bank}-{page:02X}-original.bin').write_bytes(before)
  targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=n,sha256=t.sha(body),before_sha256=t.sha(before)))
 images[3]=bytearray(state)
 for i in range(0x4000,0x6000,256):
  if valid_snapshot(old[3][i:i+256]):assert old[3][i:i+256]==state[i:i+256]
 assert state[-4096:]==old[3][-4096:] and state[0x2000:0x4000]==old[3][0x2000:0x4000] and images[0][:0x2000]==old[0][:0x2000] and images[0][0x6000:]==old[0][0x6000:]
 for b in (0,3):(OUT/f'B{b}-original.bin').write_bytes(old[b]);(OUT/f'B{b}-target.bin').write_bytes(images[b])
 p=dict(board='2512',authorization='continue, approve flash 2512, make 2609 boot the default monitor',status='REVIEWED_OWNER_AUTHORIZED_INSTALL',total_erases=5,C_D_erases=0,F_writes=0,targets=targets,operations=ops,before_bank_sha256=m['current_physical_bank_sha256'],after_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},before_journal=t.classify_journal(old[3]),after_journal=t.classify_journal(state),manifest_sha256=t.sha((BUILD/'manifest.json').read_bytes()),RAM_report_sha256=t.sha((RAM/'report.json').read_bytes()),SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,other_boards=[],preserved=['F; MON A/B g10 and saved B binding','all20 old journal rows on chip; all counts carried forward','B0:8 FLASH, B0:9 blank, B0:E/F and all B1/B2 images','board settings, RTC time/trim/PF, all SPI data','fresh owner RAM/ZP/cache and BRK/HOLD hooks'],limits=['RAM staged tools; ASM output0200-1FFF, DBG targets0200-3FFF','AS/1 PROGRAM supported; FLASH source adapter remains refused81','2512 65C02 qualification only; no new2609 developer qualification'])
 assert p['after_journal']['sequence']==1182 and p['after_journal']['valid_records']==25
 t.save(OUT/'plan.json',p)
 text=f'''# 2512 ASM/DBG installation review

Owner authorization: “{p['authorization']}”. This implements the authorized
2512 tools installation and does not expand Foundation.

Five erases: B0:A/B for ASM, B0:C/D for DBG, B3:E for the R aliases.
B0:A–D are verified all-zero sectors, not valid stored images; their exact
preimages are archived. B0:8/9/E/F, B1, B2, MON A/B and F are retained exactly.

Five append-only wear reservations: {', '.join(v['journal_appends'][0]['page'] for v in ops)},
sequence1178–1182. All20 existing C/D records remain exact on chip.
No C/D erase, boot/settings change, F write, SPI-data write, RTC-setting write,
reset, power cut, or other-board access is included.

Installed checks: APPS, APP ASM, R ASM and R DBG; edit/assemble/list/dump/run;
DBG start cancellation, initial stop, step/next/breakpoint, D/M/registers,
normal HOLD and X cleanup; PROGRAM cache reload. The RAM adapter gate passed
before this review. Final flash is independently read back, then owner
RAM0200–66FF, ZP00–DF and cache7000–74FF are restored. RTC has serial priority.

This is RAM-staged development tooling, not the later full-RAM XIP layout.
ASM source SAVE/LOAD PROGRAM passed separately. Source FLASH remains refused81;
no flash-source persistence or 816 developer acceptance is claimed here.
Published downloads and F remain unchanged.
'''
 (OUT/'review-document.md').write_text(text)
 t.save(OUT/'approval.json',dict(approved=True,owner_statement=p['authorization'],interpretation='Explicit latest installation authorization; bounded to verified zero B0 sectors plus necessary E dispatcher; no retention conflict or journal rotation',plan_sha256=t.sha((OUT/'plan.json').read_bytes()),review_document_sha256=t.sha((OUT/'review-document.md').read_bytes())))
 print(text)
if __name__=='__main__':run()
