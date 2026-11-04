"""Execute reviewed owner-authorized ASM/DBG AP/02 install once; F golden."""
import json,time,sys
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,ins
from serial_test_coordination import drift_pending
import nf_opaque as opaque
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
BUILD=t.ROOT/'BUILD/devtools-AP02-g1-r2';SCOPE=Q/'2512-devtools-flash-scope-20261102-r1';OUT=Q/'2512-devtools-flash-installed-20261102-r1';START=b'DBG RAM start 0200-3FFF; Q MON> '

def run():
 a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
 assert a['approved'] and a['owner_statement']=='continue, approve flash 2512, make 2609 boot the default monitor'
 assert t.sha((SCOPE/'plan.json').read_bytes())==a['plan_sha256'] and t.sha((SCOPE/'review-document.md').read_bytes())==a['review_document_sha256'] and t.sha((BUILD/'manifest.json').read_bytes())==p['manifest_sha256']
 assert p['total_erases']==5 and p['F_writes']==p['C_D_erases']==0
 print('2512 reviewed five-sector devtool install waiting for RTC window',flush=True)
 while True:
  try:ins.window(420);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,journal_appends=0,F_writes=0,C_D_erases=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,automatic_retries=0)
 with escrow(OUT,r,'2512-owner-authorized-ASM-DBG-five-sector-install',window=420) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,v in old.items():assert t.sha(v)==p['before_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(v)
  assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();check('fresh-owner-four-banks-settings-history-and-golden-F')
  if drift_pending():raise InterruptedError('RTC requested before first write; no writes')
  state=old[3];x.rec();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();x.s.load(writer,t.sha(writer),opaque.PROMPT)
  wire=opaque.Wire(x.s.link.serial,timeout=90,trace=x.s.log if hasattr(x.s,'log') else None,progress=lambda v:print(v,flush=True))
  for target in p['targets']:
   bank,page=target['bank'],target['page'];at=(page-0x80)*256;before=wire.read_sector(bank,page);assert t.sha(before)==target['before_sha256']
   body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
   state,op=reserve(state,bank*8+(page-0x80)//16);assert not op['journal_sector_erases']
   if bank==3:v=bytearray(state);v[at:at+4096]=body;state=bytes(v)
   x.expected_b3_sha256=t.sha(state);r['erase_requests']+=1;x.save();x.s.context=None
   assert not wire.replace_sector(bank,page,before,body);x.s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
   r['journal_appends']+=1;r['completed'].append(target['address']);check('installed-'+target['address'])
  x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
  for b in range(4):
   v=x.s.client.flash(b);(OUT/f'B{b}-after.bin').write_bytes(v);assert t.sha(v)==p['after_bank_sha256'][f'B{b}']
  r['NVM_verified']=True;x.mark(current_physical_bank_sha256=p['after_bank_sha256'],current_journal_sequence=p['after_journal']['sequence'],current_journal_valid_records=25,current_valid_journal_records=25,current_wear_counts=p['after_journal']['counts'])
  marker=json.loads(x.mp.read_text());counts=marker['current_tracked_erase_counts'].copy()
  for i,v in enumerate(p['after_journal']['counts']):counts[f'B{i//8}:{8+i%8:X}']=v
  for n,i in zip('ABCDEF',range(26,32)):counts[n]=p['after_journal']['counts'][i]
  x.mark(current_tracked_erase_counts=counts);check('all-images-predicted-journal-and-all20-old-rows-verified')
  try:
   x.mon();face=x.cmd('APPS');assert b'ASM B0:A000' in face and b'DBG B0:C000' in face;check('APPS-discovers-both-CRC-admitted-AP02-images')
   x.cmd('R ASM',(AP,));assert b'ORG' in x.cmd('?')
   for line in ('10 ORG $0200','20 LDA #$42','30 STA $1900','40 JMP $7E67','50 END'):x.cmd(line)
   assert b'OK 8 bytes' in x.cmd('ASM');assert b'A9 42' in x.cmd('LST');assert b'A9 42' in x.cmd('DUMP');x.cmd('QUIT',(t.MON,));x.cmd('G 0200',(t.MON,));assert x.s.dump(0x1900,0x1900)==b'\x42';check('R-ASM-edit-assemble-list-dump-run-and-HOLD')
   x.cmd('APP ASM',(AP,));x.cmd('QUIT',(t.MON,));check('APP-ASM-launch')
   x.cmd('R DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks;check('DBG-start-cancellation-leaves-public-hooks-intact')
   fixture=bytes.fromhex('A911A2222011188D0019EA4C677EEAEAEA1A60')
   assert fixture[0x11:]==bytes.fromhex('1A60')
   for off in range(0,len(fixture),8):x.cmd(f'M {0x1800+off:04X} '+fixture[off:off+8].hex(' ').upper())
   x.cmd('R DBG',(START,));face=x.cmd('1800',(DP,));assert b'PC=1800' in face
   assert b'PC=1802' in x.cmd('S') and b'PC=1804' in x.cmd('S');face=x.cmd('N');assert b'PC=1807' in face and b'A=12' in face
   x.cmd('B 180A');assert b'PC=180A' in x.cmd('C',(DP,));assert b'1900: 12' in x.cmd('D 1900');x.cmd('M 1900 55');assert b'1900: 55' in x.cmd('D 1900');assert b'A=66' in x.cmd('R A 66');x.cmd('BC');assert b'PC=180B' in x.cmd('S');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks;check('R-DBG-initial-stop-S-N-breakpoint-registers-D-M-and-HOLD-cleanup')
   x.cmd('APP DBG',(START,));x.cmd('1800',(DP,));x.cmd('B 180A');x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x180a,0x180a)==b'\xea';check('APP-DBG-X-restores-hooks-and-breakpoint-byte')
   x.cmd('R ASM',(AP,));assert b'Source storage: 81' in x.cmd('SAVE FLASH NOTEST');x.cmd('QUIT',(t.MON,));check('ASM-PROGRAM-provider-reloads-after-DBG')
   x.cmd('MAINT LOAD',(t.WB,));assert b'SSRAM PROGRAM:' in x.cmd('SRAM');x.cmd('Q',(t.MON,));check('existing-tools-reload-after-devtools')
   r['functional_checks_passed']=True
  finally:
   if x.s.context==START:x.cmd('Q',(t.MON,))
  x.mark(ASM_DBG_flash_installed=bool(r.get('functional_checks_passed')),last_ASM_DBG_flash_install=str(OUT/'report.json'),ASM_DBG_flash_layout='B0:A/B ASM; B0:C/D DBG; B3:E R aliases',ASM_DBG_qualification='2512 65C02 RAM-staged AP02; PROGRAM persistence qualified separately; FLASH source remains refused81')
 r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and r.get('planned_B3_verified') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 ASM/DBG installed; F/MON/settings/history preserved; owner/cache restored; REC>; COM4 free',flush=True)
if __name__=='__main__':run()
