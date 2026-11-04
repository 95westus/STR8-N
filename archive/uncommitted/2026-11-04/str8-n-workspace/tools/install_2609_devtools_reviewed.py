"""Owner-approved2609 five-image/one-D-rotation install and installed checks."""
import binascii,json,re,sys,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,ins,d
from serial_test_coordination import drift_pending
import nf_opaque as opaque
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
SCOPE=Q/'2609-devtools-flash-scope-20261102-r2'
OUT=Q/'2609-devtools-installed-20261102-r1'
START=b'DBG RAM start 0200-3FFF; Q MON> '
OWNER='Approve the reviewed six-erase 2609 ASM/DBG installation and installed checks. Keep F golden, preserve settings/history and owner RAM as reviewed, yield to RTC collection, and leave the other boards alone.'

def run():
 p=json.loads((SCOPE/'plan.json').read_text());v=json.loads((SCOPE/'review-verification.json').read_text())
 assert v['passed'] and v['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())
 assert p['status']=='REVIEW_READY_NOT_EXECUTED' and p['total_erases']==6 and p['image_erases']==5 and p['journal_erases']==1 and p['journal_appends']==6 and p['F_writes']==p['MON_writes']==0
 assert p['owner_layout_selection']=='Host-backup WDC; use qualified layout' and p['AP02_header_CPU']==0x16
 assert t.sha((SCOPE/p['WDC_backup']['file']).read_bytes())==p['WDC_backup']['sha256']
 assert (SCOPE/p['journal_backup']['file']).read_bytes()==(SCOPE/'B3-original.bin').read_bytes()[0x4000:0x6000]
 assert t.sha((Q/'2609-devtools-g2-emulation-RAM-20261102-r1/report.json').read_bytes())==p['inputs']['RAM_report_sha256']
 f=json.loads((t.REPO/'F_FREEZE.json').read_text());assert all(t.sha((t.REPO/name).read_bytes())==h for name,h in f['sources'].items())
 for name,offset in (('ASM',0x2000),('DBG',0x4000)):
  body=(SCOPE/'B0-target.bin').read_bytes()[offset:offset+8192];used=int.from_bytes(body[8:10],'little')
  assert body[15]==0x16 and binascii.crc_hqx(body[:28],65535)==int.from_bytes(body[28:30],'little') and binascii.crc_hqx(body[32:used],65535)==int.from_bytes(body[30:32],'little') and t.sha(body)==p['AP02_envelopes'][name]['target_sha256']
 print('2609 approved six-erase ASM/DBG install waiting for RTC window480s',flush=True)
 while True:
  try:ins.window(480);break
  except AssertionError:time.sleep(1)
 r=dict(board='2609',CPU='65C816 emulation',passed=False,checks=[],completed=[],erase_requests=0,image_erase_requests=0,journal_erase_requests=0,journal_appends=0,F_writes=0,MON_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0,automatic_retries=0,persistent_source_write_tests=False)
 with escrow(OUT,r,'2609-approved-six-erase-ASM-DBG-install',window=480,cache_first=0x6b00,cache_end=0x77ff,board='2609') as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'escrow-as-executed.py').write_bytes((t.ROOT/'tools/devtools_2512_session.py').read_bytes())
  t.save(OUT/'approval.json',dict(approved=True,owner_statement=OWNER,approved_at=t.utc(),plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()),review_document_sha256=t.sha((SCOPE/'review-document.md').read_bytes())))
  def check(name):r['checks'].append(name);x.save();print('PASS2609 '+name,flush=True)
  def boundary():
   if drift_pending():raise InterruptedError('RTC priority at safe boundary; no extra writes')
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,body in old.items():assert t.sha(body)==p['before_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(body)
  assert old[0]==(SCOPE/p['WDC_backup']['file']).read_bytes() and t.sha(old[3][0x7000:])==f['sha256']
  check('fresh-four-bank-target-preimages-WDC-archive-history-and-golden-F')
  state=old[3];reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
  try:
   boundary();x.rec();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();x.s.load(writer,t.sha(writer),opaque.PROMPT)
   with (OUT/'opaque-wire.jsonl').open('x') as wirelog:
    wire=opaque.Wire(x.s.link.serial,timeout=90,trace=wirelog,progress=lambda msg:print(msg,flush=True))
    for target,wanted in zip(p['targets'],p['operations']):
     boundary();bank,page=target['bank'],target['page'];assert (bank,page) in ((0,0xa0),(0,0xb0),(0,0xc0),(0,0xd0),(3,0xe0))
     before=wire.read_sector(bank,page);assert t.sha(before)==target['before_sha256']
     body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
     state,op=reserve(state,bank*8+(page-0x80)//16);assert op==wanted
     if bank==3:tmp=bytearray(state);at=(page-0x80)*256;tmp[at:at+4096]=body;state=bytes(tmp)
     x.expected_b3_sha256=t.sha(state)
     r['image_erase_requests']+=1;r['journal_erase_requests']+=len(op['journal_sector_erases']);r['erase_requests']=r['image_erase_requests']+r['journal_erase_requests'];assert r['erase_requests']<=6;x.save()
     x.s.context=None;assert not wire.replace_sector(bank,page,before,body);x.s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
     r['journal_appends']+=len(op['journal_appends']);r['completed'].append(target['address']);check('installed-'+target['address'])
   assert state==(SCOPE/'B3-target.bin').read_bytes() and r['erase_requests']==6 and r['journal_appends']==6
   def banks(suffix):
    x.rec();x.s.service(reader)
    for b in range(4):
     body=x.s.client.flash(b);(OUT/f'B{b}-{suffix}.bin').write_bytes(body);assert t.sha(body)==p['after_bank_sha256'][f'B{b}']
   banks('installed');r['NVM_verified']=True
   marker=json.loads(x.mp.read_text());counts=marker['current_tracked_erase_counts'].copy()
   for i,n in enumerate(p['after_journal']['counts']):counts[f'B{i//8}:{8+i%8:X}']=n
   for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['after_journal']['counts'][i]
   x.mark(current_physical_bank_sha256=p['after_bank_sha256'],current_journal_sequence=1095,current_journal_valid_records=17,current_valid_journal_records=17,current_wear_counts=p['after_journal']['counts'],current_tracked_erase_counts=counts,ASM_DBG_flash_installed=True,ASM_DBG_installed_qualified=False,ASM_source_generation='00000002',DBG_generation='00000002',DEVTOOLS_install_inspection_pending=False,DEVTOOLS_installed_qualification_pending=True,last_ASM_DBG_flash_install=str(OUT/'report.json'),WDC_B0_complete_on_chip=False,WDC_B0_host_backup=str(SCOPE/p['WDC_backup']['file']))
   check('all-four-banks-planned-D-rotation-root-all11-retained-rows-and-F-exact')
   x.mon();face=x.cmd('APPS');assert b'ASM B0:A000' in face and b'DBG B0:C000' in face
   x.cmd('APP ASM',(AP,));assert b'SAVE' in x.cmd('?');x.cmd('QUIT',(t.MON,))
   x.cmd('R DBG',(START,));x.cmd('Q',(t.MON,));x.cmd('APP DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
   check('CPU16-APPS-APP-ASM-R-DBG-APP-DBG-and-start-cancellation')
   boundary();x.cmd('R ASM',(AP,))
   for line in ('10 BASE EQU $0200','20 ORG BASE','30 start: LDA #$23','40 JSR $7E6D','50 JMP $7E67','60 END'):x.cmd(line)
   assert b'OK 8 bytes' in x.cmd('ASM');assert b'0200 BASE' in x.cmd('SYMS');assert b'0200 A9 23' in x.cmd('LST') and b'0200: A9 23' in x.cmd('DUMP') and b'S1' in x.cmd('S19')
   x.cmd('QUIT',(t.MON,));assert x.s.dump(0x200,0x207)==bytes.fromhex('A923206D7E4C677E');assert b'#' in x.cmd('G 0200',(t.MON,));assert x.hooks()==x.oldhooks
   check('installed-R-ASM-EQU-labels-list-export-physical-output-run-and-HOLD')
   def poke(a,body):
    for off in range(0,len(body),8):x.cmd(f'M {a+off:04X} '+body[off:off+8].hex(' ').upper())
   def start(program=bytes.fromhex('4C677E'),extra=None):
    boundary();x.mon();poke(0x1800,program)
    for a,body in (extra or {}).items():poke(a,body)
    x.cmd('R DBG',(START,));assert b'PC=1800' in x.cmd('1800',(DP,))
   def regs(face=None):
    face=x.cmd('R') if face is None else face;m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face
    return dict(zip(('PC','A','X','Y','P','S'),(int(v,16) for v in m.groups())))
   def err(line):face=x.cmd(line);assert b'?\r\n' in face,(line,face)
   def logical(a,end=None):
    face=x.cmd(f'D {a:04X}'+(f' {end:04X}' if end is not None else ''));return bytes(int(v,16) for _,v in re.findall(rb'([0-9A-F]{4}): ([0-9A-F]{2})',face))
   def leave():x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
   start(bytes.fromhex('A911A2222000118D0019EA4C677E'),{0x1100:bytes.fromhex('1A60')})
   assert regs(x.cmd('S'))['PC']==0x1802 and regs(x.cmd('S'))['PC']==0x1804
   face=x.cmd('N');assert regs(face)['PC']==0x1807 and regs(face)['A']==0x12
   x.cmd('B 180A');assert regs(x.cmd('C',(DP,)))['PC']==0x180a and logical(0x1900)==b'\x12'
   x.cmd('BC');assert regs(x.cmd('S'))['PC']==0x180b;x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x180a,0x180a)==b'\xea'
   check('installed-DBG-real-BRK-S-N-JSR-RTS-breakpoint-BC-and-HOLD')
   start();wanted=logical(0x10)[0]^255;x.cmd(f'M 0010 {wanted:02X}');x.cmd('M 2000 EA');x.cmd('B 2000');leave();assert x.s.dump(0x10,0x10)==bytes((wanted,)) and x.s.dump(0x2000,0x2000)==b'\xea'
   start(bytes.fromhex('A96D8510A95A85D04C677E'),{0x2000:b'\xea'});x.cmd('B 2000');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0xd0,0xd0)==b'\x5a' and x.s.dump(0x10,0x10)==b'\x6d' and x.s.dump(0x2000,0x2000)==b'\xea'
   check('installed-X-stopped-ZP-and-HOLD-live-ZP-full-unpatch-cleanup')
   start(bytes.fromhex('2000404C677E'));x.cmd('R SP F0');x.cmd('M 01EF AA BB');before=regs()
   for cmd in ('S','N'):err(cmd);assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB')
   for n,op in enumerate((0x07,0x0f,0x87,0x8f,0xc2,0xe2,0xfb)):
    a=0x3000+4*n;x.cmd(f'M {a:04X} {op:02X} 10 00 EA');x.cmd(f'R PC {a:04X}');assert b'.BYTE' in x.cmd(f'U {a:04X} 1');before=regs();err('S');err('N');assert regs()==before
   leave();check('installed-atomic-call-stack-and-reassigned-mode-opcode-refusals')
   start(bytes.fromhex('A923206D7E4C677E'));x.cmd('S');face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x1805;x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks
   callback=bytes.fromhex('A95A8D0270A96B8D0370A97C8D047060')
   start(bytes.fromhex('00804C677E'),{0x2100:callback,0x2200:bytes.fromhex('C0002100')});rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'])==(1,16,4)
   x.cmd('M 1800 00 81');x.cmd('R PC 1800');x.cmd('R A 00');x.cmd('R X 22');rr=regs(x.cmd('S'));assert rr['A']==0 and rr['P']&1
   x.cmd('M 1800 00 C0');x.cmd('R PC 1800');rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'],rr['PC'])==(0x5a,0x6b,0x7c,0x1802);leave()
   check('installed-public-N-built-in-service-and-real-user-callback')
   boundary();x.cmd('R ASM',(AP,));assert b'Source storage: 42' in x.cmd('LOAD FLASH NFG2ZZ9');assert b'Source storage: 42' in x.cmd('LOAD SRAM NFG2ZZ9');x.cmd('QUIT',(t.MON,));assert x.hooks()==x.oldhooks
   check('installed-SF-provider-read-only-scan-and-PROGRAM-overlay-reload')
   boundary();face=x.cmd('R CLOCK',(t.CLOCK,));assert b'CLOCK' in face;x.cmd('Q',(t.MON,))
   x.cmd('R MAINT',(b'BM> ',));assert b'EDITOR BUFFER' in x.cmd('?');x.cmd('Q',(t.MON,))
   x.cmd('R FLASH',(d.FT,));x.cmd('?',(d.FT,));x.cmd('Q',(t.MON,))
   x.cmd('MAINT LOAD',(t.WB,));assert b'SSRAM PROGRAM:' in x.cmd('SRAM');x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
   check('existing-CLOCK-BANK-MAINT-FLASH-and-SRAM-workbench-launches')
   banks('after');check('final-all-bank-predicted-images-settings-root-F-and-no-extra-writes')
   r['functional_checks_passed']=True
  finally:
   if r['erase_requests'] and not r.get('NVM_verified'):
    x.original['block_snapshot']=True;x.mark(DEVTOOLS_install_inspection_pending=True)
 r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and r.get('planned_B3_verified') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('port_released') and r['erase_requests']==6 and r['journal_appends']==6)
 t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2609 installed ASM/DBG; six erases/six appends, F/settings and owner/cache/hooks preserved; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
