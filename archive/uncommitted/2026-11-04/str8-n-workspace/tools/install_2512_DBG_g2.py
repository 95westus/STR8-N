"""Owner-approved two-erase DBG g2 installation and installed checks; F golden."""
import json,re,sys,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,ins
from serial_test_coordination import drift_pending
import nf_opaque as opaque
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve

BUILD=t.ROOT/'BUILD/dbg-base1-g2-r1'
SCOPE=Q/'2512-DBG-g2-install-scope-20261102-r1'
OUT=Q/'2512-DBG-g2-installed-20261102-r1'
START=b'DBG RAM start 0200-3FFF; Q MON> '
OWNER='Approve the reviewed two-erase DBG installation on 2512 and run the installed checks. Keep F golden, preserve settings/history and owner RAM, yield to RTC collection, and leave the other boards alone.'

def run():
 p=json.loads((SCOPE/'plan.json').read_text());v=json.loads((SCOPE/'review-verification.json').read_text())
 assert v['passed'] and v['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())
 assert p['total_erases']==2 and p['journal_erases']==p['F_writes']==0
 assert t.sha((BUILD/'manifest.json').read_bytes())==p['manifest_sha256']
 assert t.sha((Q/'2512-DBG-broad-RAM-20261102-r1/report.json').read_bytes())==p['RAM_report_sha256']
 f=json.loads((t.REPO/'F_FREEZE.json').read_text())
 assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
 assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
 print('2512 approved two-erase DBG g2 install waiting for RTC window',flush=True)
 while True:
  try:ins.window(480);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,journal_appends=0,C_D_erases=0,F_writes=0,MON_writes=0,ASM_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,automatic_retries=0)
 with escrow(OUT,r,'2512-approved-DBG-g2-two-sector-install',window=480,cache_first=0x6b00,cache_end=0x77ff) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  t.save(OUT/'approval.json',dict(approved=True,owner_statement=OWNER,plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()),review_document_sha256=t.sha((SCOPE/'review-document.md').read_bytes())))
  def check(name):r['checks'].append(name);x.save();print('PASS2512 '+name,flush=True)
  assert not x.original['block_snapshot'] and not x.original.get('utility_retirement_pending') and not x.original.get('legacy_reclaim_pending')
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,body in old.items():
   assert t.sha(body)==p['before_bank_sha256'][f'B{b}'],f'B{b} changed; reviewed scope invalid'
   (OUT/f'B{b}-before.bin').write_bytes(body)
  image=(BUILD/'DBG-FLASH.bin').read_bytes()
  assert t.sha(image)==json.loads((BUILD/'manifest.json').read_text())['artifacts']['DBG-FLASH.bin']['sha256']
  assert old[0][0x5800:0x6000]==image[0x1800:] and t.sha(old[3][0x7000:])==f['sha256']
  check('fresh-scope-preimages-all-banks-SF-provider-and-golden-F')
  if drift_pending():raise InterruptedError('RTC requested before first write; no writes')
  state=old[3];x.rec();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();x.s.load(writer,t.sha(writer),opaque.PROMPT)
  wire=opaque.Wire(x.s.link.serial,timeout=90,trace=x.s.log if hasattr(x.s,'log') else None,progress=lambda msg:print(msg,flush=True))
  for target,wanted_op in zip(p['targets'],p['operations']):
   assert not drift_pending(),'RTC requested; stop at completed sector boundary'
   bank,page=target['bank'],target['page'];assert bank==0 and page in (0xc0,0xd0)
   before=wire.read_sector(bank,page);assert t.sha(before)==target['before_sha256']
   body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
   state,op=reserve(state,(page-0x80)//16);assert op==wanted_op and not op['journal_sector_erases']
   x.expected_b3_sha256=t.sha(state);r['erase_requests']+=1;x.save();x.s.context=None
   assert not wire.replace_sector(bank,page,before,body)
   x.s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
   r['journal_appends']+=1;r['completed'].append(f'B0:{page>>4:X}');check('installed-'+r['completed'][-1])
  assert state==(SCOPE/'B3-target.bin').read_bytes()
  def verify_banks(suffix):
   x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
   for b in range(4):
    body=x.s.client.flash(b);(OUT/f'B{b}-{suffix}.bin').write_bytes(body)
    assert t.sha(body)==p['after_bank_sha256'][f'B{b}'],f'B{b} readback differs'
  verify_banks('installed')
  r['NVM_verified']=True
  marker=json.loads(x.mp.read_text());counts=marker['current_tracked_erase_counts'].copy()
  for i,n in enumerate(p['new_journal']['counts']):counts[f'B{i//8}:{8+i%8:X}']=n
  for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['new_journal']['counts'][i]
  x.mark(current_physical_bank_sha256=p['after_bank_sha256'],current_journal_sequence=1201,current_journal_valid_records=28,current_valid_journal_records=28,current_wear_counts=p['new_journal']['counts'],current_tracked_erase_counts=counts,DBG_generation='00000002',DBG_g2_installed=True,DBG_g2_installed_qualified=False,last_DBG_g2_install=str(OUT/'report.json'))
  check('all-four-banks-predicted-journal-all26-old-rows-and-SF-provider-exact')
  def rtc():
   if drift_pending():raise InterruptedError('RTC priority at safe functional-check boundary')
  def poke(addr,data):
   for off in range(0,len(data),8):x.cmd(f'M {addr+off:04X} '+data[off:off+8].hex(' ').upper())
  def start(program=bytes.fromhex('4C677E'),extra=None):
   rtc();x.mon();poke(0x1800,program)
   for addr,data in (extra or {}).items():poke(addr,data)
   x.cmd('R DBG',(START,));face=x.cmd('1800',(DP,));assert b'PC=1800' in face
  def leave():x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
  def regs(face=None):
   face=x.cmd('R') if face is None else face
   m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face
   return dict(zip(('PC','A','X','Y','P','S'),(int(n,16) for n in m.groups())))
  def logical(a,end=None):
   face=x.cmd(f'D {a:04X}'+(f' {end:04X}' if end is not None else ''))
   return bytes(int(n,16) for _,n in re.findall(rb'([0-9A-F]{4}): ([0-9A-F]{2})',face))
  def err(cmd):face=x.cmd(cmd);assert b'?\r\n' in face,(cmd,face)
  x.mon();face=x.cmd('APPS');assert b'ASM B0:A000' in face and b'DBG B0:C000' in face
  x.cmd('R DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
  x.cmd('APP DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
  check('APPS-R-and-APP-DBG-installed-launch-and-start-cancellation')
  start();wanted=logical(0x10)[0]^255;x.cmd(f'M 0010 {wanted:02X}');leave();assert x.s.dump(0x10,0x10)==bytes((wanted,))
  check('installed-X-publishes-stopped-logical-ZP')
  start(bytes.fromhex('A96D8510A95A85D04C677E'),{0x2000:b'\xea'});x.cmd('B 2000');x.cmd('C',(t.MON,))
  assert x.hooks()==x.oldhooks and x.s.dump(0x10,0x10)==b'\x6d' and x.s.dump(0xd0,0xd0)==b'\x5a' and x.s.dump(0x2000,0x2000)==b'\xea'
  check('installed-HOLD-preserves-live-ZP-and-unpatches')
  start(bytes.fromhex('EAEA4C677E'))
  x.cmd('B 1801');err('BC 1801 EXTRA');assert b'1801\r\n' in x.cmd('B');x.cmd('BC');assert b'1801\r\n' not in x.cmd('B')
  x.cmd('B 1801');assert regs(x.cmd('S'))['PC']==0x1801;x.cmd('BC *');assert regs(x.cmd('S'))['PC']==0x1802
  x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x1800,0x1801)==b'\xea\xea'
  check('installed-BC-bare-star-trailing-guard-and-duplicate-step-unpatch')
  start(bytes.fromhex('2000404C677E'));x.cmd('R SP F0');x.cmd('M 01EF AA BB');before=regs()
  for cmd in ('S','N'):err(cmd);assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB')
  for addr in ('4000','7000','7FC0'):err('D '+addr);err('M '+addr+' 00')
  x.cmd('M 1900 6C C0 7F');x.cmd('R PC 1900');before=regs();err('S');assert regs()==before;leave()
  check('installed-atomic-JSR-stack-and-I-O-indirect-memory-guards')
  start(bytes.fromhex('A923206D7E4C677E'))
  assert regs(x.cmd('S'))['PC']==0x1802;err('S');face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x1805
  x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks
  check('installed-public-PUTC-N-step-over-and-HOLD-return')
  callback=bytes.fromhex('A95A8D0270A96B8D0370A97C8D047060')
  start(bytes.fromhex('00804C677E'),{0x2100:callback,0x2200:bytes.fromhex('C0002100')})
  rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'])==(1,16,4)
  x.cmd('M 1800 00 81');x.cmd('R PC 1800');x.cmd('R A 00');x.cmd('R X 22');rr=regs(x.cmd('S'));assert rr['A']==0 and rr['P']&1
  x.cmd('M 1800 00 C0');x.cmd('R PC 1800');rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'],rr['PC'])==(0x5a,0x6b,0x7c,0x1802)
  assert b'C0 2100' in x.cmd('F');leave();check('installed-built-in-query-registration-and-real-user-callback')
  rtc();x.cmd('R ASM',(AP,));face=x.cmd('?');assert b'SAVE' in face and b'FLASH' in face
  x.cmd('QUIT',(t.MON,));assert x.hooks()==x.oldhooks;check('unchanged-ASM-and-SF-provider-admission-after-DBG')
  verify_banks('after');check('final-four-bank-and-journal-readback-exact-no-extra-writes')
  r['functional_checks_passed']=True
 r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and r.get('planned_B3_verified') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('port_released'))
 t.save(OUT/'report.json',r);assert r['passed']
 with t.serial_lease('2512-DBG-g2-host-only-closeout',timeout=30):
  marker=json.loads((Q/'device-operations/2512.json').read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
  marker.update(DBG_g2_installed_qualified=True,last_DBG_g2_install=str(OUT/'report.json'),ASM_DBG_qualification='2512 65C02 installed DBG g2 and AS/1 PROGRAM/SF/1 FLASH source accepted; 816 developer path pending')
  t.save(Q/'device-operations/2512.json',marker)
 print('PASS2512 installed DBG g2; two erases/two appends; all26 old rows/F/settings preserved; owner/cache restored; REC>; COM4 free',flush=True)

if __name__=='__main__':run()
