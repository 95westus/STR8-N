"""Broader2512 DBG checks on real CPU RAM; no flash/SPI/RTC-setting writes."""
import json,re,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,DP,ins
from time_prep_ram_packets import Code
from serial_test_coordination import drift_pending
BUILD=t.ROOT/'BUILD/dbg-base1-g2-r1';OUT=Q/'2512-DBG-broad-RAM-20261102-r1'

def run():
 print('2512 broader DBG RAM suite waiting for RTC window',flush=True)
 while True:
  try:ins.window(420);break
  except AssertionError:time.sleep(1)
 mf=json.loads((BUILD/'manifest.json').read_text());base=(BUILD/'DBG-RAM.bin').read_bytes();sy=json.loads((BUILD/'symbols.json').read_text());assert t.sha(base)==mf['artifacts']['DBG-RAM.bin']['sha256']
 r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,callbacks_user_slots=16,breakpoint_slots=8)
 with escrow(OUT,r,'2512-DBG-broader-RAM-guards-callbacks',window=420,cache_first=0x6b00,cache_end=0x77ff) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());old={b:x.s.client.flash(b) for b in range(4)}
  for b,v in old.items():assert t.sha(v)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(v)
  def packet(program=bytes.fromhex('4C677E'),extra=None,stub=None):
   b=bytearray(base);b[0xe00:0xe02]=b'\0\0';b[0xe02:0xe02+len(program)]=program
   for a,data in (extra or {}).items():assert 0x200<=a and a+len(data)<=0x4000;b[a-0x200:a-0x200+len(data)]=data
   if stub is not None:b[:3]=bytes.fromhex('4C001F');b[0x1d00:0x1d00+len(stub)]=stub
   return bytes(b)
  def load(program=bytes.fromhex('4C677E'),extra=None):
   if drift_pending():raise InterruptedError('RTC priority between safe cases')
   x.rec();b=packet(program,extra);x.s.load(b,t.sha(b),DP)
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  def regs(face=None):
   face=x.cmd('R') if face is None else face;m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face;return dict(zip(('PC','A','X','Y','P','S'),(int(v,16) for v in m.groups())))
  def err(cmd):face=x.cmd(cmd);assert b'?\r\n' in face,(cmd,face);return face
  def logical(a,end=None):
   face=x.cmd(f'D {a:04X}'+(f' {end:04X}' if end is not None else ''));return bytes(int(v,16) for _,v in re.findall(rb'([0-9A-F]{4}): ([0-9A-F]{2})',face))
  def leave():x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
  # Logical state survives X, while live program ZP survives program HOLD.
  load();oldbyte=logical(0x10)[0];wanted=oldbyte^255;x.cmd(f'M 0010 {wanted:02X}');leave();assert x.s.dump(0x10,0x10)==bytes((wanted,));check('X-restores-stopped-logical-ZP-edits')
  load(bytes.fromhex('A96D8510A95A85D04C677E'),{0x2000:b'\xea'});x.cmd('B 2000');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x10,0x10)==b'\x6d' and x.s.dump(0xd0,0xd0)==b'\x5a' and x.s.dump(0x2000,0x2000)==b'\xea';check('HOLD-keeps-live-user-ZP-before-unpatching')
  load()
  for key,value in [('A','5A'),('X','6B'),('Y','7C'),('P','A5'),('SP','F0')]:x.cmd(f'R {key} {value}')
  got=regs();assert all(got[k]==v for k,v in dict(A=0x5a,X=0x6b,Y=0x7c,P=0xa5,S=0xf0).items())
  for key in ('A','X','Y','P','SP'):err('R '+key+' 100');assert regs()==got
  err('R PC 10000');assert regs()==got;x.cmd('R P 20')
  for cmd in ('C','S','N'):err(cmd)
  x.cmd('R P 24');leave();check('register-edits-width-errors-and-unmasked-context-refusal')
  load(extra={0x3fff:b'\x11'});x.cmd('M 00DF 11');err('M 00DF 22 33');assert logical(0xdf)==b'\x11';x.cmd('M 0010 01 02 03 04 05 06 07 08');err('M 0010 11 12 13 14 15 16 17 18 19');assert logical(0x10,0x17)==bytes(range(1,9));x.cmd('M 01FE AA BB');assert logical(0x1fe,0x1ff)==bytes.fromhex('AABB');err('M 3FFF 22 33');assert logical(0x3fff)==b'\x11'
  for addr in ('4000','7000','7FC0','FFFF'):err('D '+addr);err('M '+addr+' 00')
  leave();check('logical-ZP-stack-eight-byte-and-RAM-I-O-memory-guards')
  load(bytes.fromhex('4C0020'),{0x2000:b'\xea'*8+bytes.fromhex('4C677E')})
  for a in range(0x2000,0x2008):x.cmd(f'B {a:04X}')
  err('B 2008');x.cmd('BC');assert not re.search(rb'200[0-7]\r\n',x.cmd('B'))
  x.cmd('B 2000');err('BC 2000 EXTRA');assert b'2000\r\n' in x.cmd('B');x.cmd('BC *')
  for a in range(0x2000,0x2008):x.cmd(f'B {a:04X}')
  for a in range(0x2000,0x2008):assert regs(x.cmd('C',(DP,)))['PC']==a
  x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x2000,0x2007)==b'\xea'*8;check('eight-real-breakpoint-hits-capacity-BC-and-complete-unpatch')
  load(bytes.fromhex('EAEA4C677E'));x.cmd('B 1003');assert regs(x.cmd('S'))['PC']==0x1003;assert logical(0x1003)==b'\xea';x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x1002,0x1003)==b'\xea\xea';check('duplicate-user-and-step-breakpoint-restores-original-opcode')
  flow={0x1200:bytes.fromhex('D002EAEA80FE'),0x1210:bytes.fromhex('0F1002EAEAEA'),0x1218:bytes.fromhex('8F1002EAEAEA'),0x1220:bytes.fromhex('6C4002'),0x1230:bytes.fromhex('7C4002'),0x1240:bytes.fromhex('208012'),0x1250:b'\x40',0x1260:bytes.fromhex('200040'),0x1280:bytes.fromhex('60EA60'),0x240:bytes.fromhex('80128212'),0x1270:bytes.fromhex('6CFF01'),0x3ffd:bytes.fromhex('208012')}
  load(extra=flow)
  def pcstep(pc,p=None):
   x.cmd(f'R PC {pc:04X}')
   if p is not None:x.cmd(f'R P {p:02X}')
   return regs(x.cmd('S'))
  assert pcstep(0x1200,0x24)['PC']==0x1204 and pcstep(0x1200,0x26)['PC']==0x1202 and pcstep(0x1204,0x24)['PC']==0x1204
  x.cmd('M 0010 00');assert pcstep(0x1210)['PC']==0x1215 and pcstep(0x1218)['PC']==0x121b;x.cmd('M 0010 01');assert pcstep(0x1210)['PC']==0x1213 and pcstep(0x1218)['PC']==0x121d
  assert pcstep(0x1220)['PC']==0x1280;x.cmd('R X 02');assert pcstep(0x1230)['PC']==0x1282;x.cmd('M 01FF 80');x.cmd('M 0200 12');assert pcstep(0x1270)['PC']==0x1280;check('conditional-relative-bit-branch-and-indexed-logical-indirect-flow')
  x.cmd('R SP F0');assert pcstep(0x1240)['PC']==0x1280 and regs()['S']==0xee;assert logical(0x1ef,0x1f0)==bytes.fromhex('4212');assert regs(x.cmd('S'))['PC']==0x1243 and regs()['S']==0xf0
  x.cmd('M 01EF AA BB');x.cmd('R PC 1260');before=regs();err('S');assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB');err('N');assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB')
  x.cmd('R PC 3FFD');before=regs();err('N');assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB')
  x.cmd('R SP F0');x.cmd('M 01F1 24 80 12');assert pcstep(0x1250)['PC']==0x1280 and regs()['S']==0xf3;x.cmd('R SP F0');x.cmd('M 01F1 20 80 12');x.cmd('R PC 1250');before=regs();err('S');assert regs()==before;leave();check('JSR-RTS-RTI-and-atomic-invalid-call-return-stack-guards')
  load(extra={0x1300:bytes.fromhex('58CBDB0328EA'),0x1310:bytes.fromhex('6CC07F'),0x1314:bytes.fromhex('6CFF3F'),0x1318:bytes.fromhex('7CC07F'),0x3fff:b'\xa9'})
  for a in (0x1300,0x1301,0x1302,0x1303,0x1310,0x1314,0x1318,0x3fff,0x4000,0x7fc0,0xffff,1):
   x.cmd(f'R PC {a:04X}');before=regs();err('S');assert regs()==before
  x.cmd('R SP F0');x.cmd('M 01F1 20');x.cmd('R PC 1304');before=regs();err('S');assert regs()==before;x.cmd('M 01F1 24');assert regs(x.cmd('S'))['PC']==0x1305;leave();check('CLI-PLP-WAI-STP-unknown-truncated-and-I-O-indirect-refusal')
  load(extra={0x1400:bytes.fromhex('206D7E4C677E'),0x1410:bytes.fromhex('207C7E4C677E'),0x1420:bytes.fromhex('20887E4C677E'),0x1430:bytes.fromhex('20C07F'),0x1440:bytes.fromhex('20707E')})
  x.cmd('R PC 1400');x.cmd('R A 23');err('S');face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x1403;x.cmd('R PC 1410');x.cmd('R A AB');face=x.cmd('N');assert b'AB' in face and regs(face)['PC']==0x1413;x.cmd('R PC 1420');rr=regs(x.cmd('N'));assert rr['PC']==0x1423 and rr['X']==2
  for a in (0x1430,0x1440):x.cmd(f'R PC {a:04X}');before=regs();err('N');assert regs()==before
  leave();check('N-public-PUTC-HEX-query-and-unsafe-or-blocking-call-refusal')
  # User callbacks run real code, including a nested BRK while outer BUSY=1.
  callback=bytes.fromhex('8D30188E31188C321800808D3318086829018D3418A95A8D0270A96B8D0370A97C8D0470AD057009018D057060')
  load(extra={0x1200:bytes.fromhex('00804C677E'),0x2100:callback,0x2200:bytes.fromhex('C0002100'),0x3fff:b'Z'})
  def invoke(sig,a=None,xx=None,y=None):
   x.cmd(f'M 1200 00 {sig:02X}');x.cmd('R PC 1200')
   for k,v in [('A',a),('X',xx),('Y',y)]:
    if v is not None:x.cmd(f'R {k} {v:02X}')
   face=x.cmd('S');return regs(face),face
  rr,_=invoke(0x80);assert (rr['A'],rr['X'],rr['Y'],rr['P']&1)==(1,16,4,1)
  rr,face=invoke(0x84,255,0x3f,1);assert b'Z' in face and rr['PC']==0x1202;rr,_=invoke(0x84,255,0x3f,2);assert rr['A']==1 and not rr['P']&1;rr,_=invoke(0x84,0xc0,0x7f,1);assert rr['A']==1 and not rr['P']&1
  rr,_=invoke(0x81,0,0x22);assert rr['A']==0 and rr['P']&1;rr,_=invoke(0xc0);assert (rr['A'],rr['X'],rr['Y'])==(0x5a,0x6b,0x7c) and rr['PC']==0x1202;assert logical(0x1830,0x1834)==bytes((0,0x70,0xc0,9,0));assert b'C0 2100' in x.cmd('F');leave();check('built-in-query-trace-bounds-user-callback-register-edits-and-nested-BRK')
  load(extra={0x1200:bytes.fromhex('00814C677E'),0x2100:b'\x60',0x3ffc:bytes.fromhex('C0002100')})
  rr,_=invoke(0x81,0xfc,0x3f);assert rr['A']==0 and rr['P']&1
  for ident in range(0xc1,0xd0):
   x.cmd(f'M 2200 {ident:02X} 00 21 00');rr,_=invoke(0x81,0,0x22);assert rr['A']==0 and rr['P']&1
  x.cmd('M 2200 D0 00 21 00');rr,_=invoke(0x81,0,0x22);assert rr['A']==1 and not rr['P']&1
  for ident in (0,0x80,0xbf,0xff):rr,_=invoke(0x82,ident);assert rr['A']==1 and not rr['P']&1
  rr,_=invoke(0x82,0xc7);assert rr['A']==0 and rr['P']&1;x.cmd('M 2200 C7 00 21 00');rr,_=invoke(0x81,0,0x22);assert rr['A']==0 and rr['P']&1
  rr,_=invoke(0x81,0,0x22);assert rr['A']==1 and not rr['P']&1
  for ptr in (0x3ffd,0x100,0x7fc0):rr,_=invoke(0x81,ptr&255,ptr>>8);assert rr['A']==1 and not rr['P']&1
  listed=x.cmd('F');assert all(f'{ident:02X} 2100'.encode() in listed for ident in range(0xc0,0xd0));leave();check('all16-user-callback-slots-duplicate-capacity-namespace-and-request-bounds')
  # Hostile callback results are rejected before execution or any BP patch.
  badpc=bytes.fromhex('A9C08D0070A97F8D017060');badbp=bytes.fromhex('A9008D4070A9208D4170A9018D4370A9C08D4470A97F8D4570A9018D477060')
  load(extra={0x1010:bytes.fromhex('00C14C677E'),0x1018:bytes.fromhex('00C24C677E'),0x1200:bytes.fromhex('00814C677E'),0x2200:bytes.fromhex('C1002300C2202300'),0x2300:badpc,0x2320:badbp,0x2000:b'\xea'})
  for ptr in (0x2200,0x2204):rr,_=invoke(0x81,ptr&255,ptr>>8);assert rr['A']==0 and rr['P']&1
  x.cmd('R PC 1010');err('C');assert regs()['PC']==0x7fc0;x.cmd('R PC 1018');err('C');assert logical(0x2000)==b'\xea';leave();check('callback-bad-PC-and-complete-BP-preflight-before-mutation')
  load();x.s.link.send(b'\x03');x.s.until((DP,));assert regs()['PC']==0x1002;x.cmd('R A 5X\x085');assert regs()['A']==0x55;err('!'*41);err('X EXTRA');assert x.s.context==DP;leave();check('Ctrl-C-backspace-overlong-input-and-X-argument-guards')
  # Known other owners are refused. The fixture cleanup is preloaded RAM.
  for bad_brk in (True,False):
   clean=Code(0x2500);clean.emit(0xa9,0xa5);clean.absolute(0x8d,0x1e00)
   for addr,value in zip((0x7e02,0x7e03,0x7e67,0x7e68,0x7e69),x.oldhooks):clean.emit(0xa9,value);clean.absolute(0x8d,addr)
   clean.absolute(0x4c,0x7e67);stub=Code(0x1f00);stub.emit(0x78,0xd8)
   if bad_brk:stub.emit(0xa9,0x56);stub.absolute(0x8d,0x7e02)
   else:
    stub.emit(0xa9,0);stub.absolute(0x8d,0x7e68);stub.emit(0xa9,0x25);stub.absolute(0x8d,0x7e69)
   stub.absolute(0x4c,sy['DBG_ENTRY']);x.rec();b=packet(extra={0x2500:clean.done()},stub=stub.done());log_start=(OUT/'serial.jsonl').stat().st_size;x.s.load(b,t.sha(b),t.MON)
   with (OUT/'serial.jsonl').open() as trace:trace.seek(log_start);face=b''.join(bytes.fromhex(v['hex']) for v in map(json.loads,trace) if v.get('direction')=='RX')
   if bad_brk:x.cmd('G 2500',(t.MON,))
   assert x.hooks()==x.oldhooks and x.s.dump(0x1e00,0x1e00)==b'\xa5';assert b'DBG refused:' in face
  check('existing-BRK-and-HOLD-owner-refusal-with-explicit-hook-restoration')
  # Private system-registration API: four slots and descriptor/active guards.
  requests={0x3ffc:bytes((0xa0,0,0x21,0)),0x2200:bytes((0xa1,0,0x21,0)),0x2204:bytes((0xa2,0,0x21,0)),0x2208:bytes((0xa3,0,0x21,0)),0x220c:bytes((0xa4,0,0x21,0)),0x2210:bytes((0xa5,0,0x21,0)),0x2214:bytes((0xa1,0xc0,0x7f,0)),0x2218:bytes((0xa1,0xff,1,0)),0x221c:bytes((0xa1,0,0x21,1)),0x2220:bytes((0xc0,0,0x21,0)),0x2100:b'\x60'}
  calls=[0x3ffc,0x3ffd,0x100,0x2214,0x2218,0x221c,0x2220,0x2200,0x2204,0x2208,0x3ffc,0x220c,0x2210];expect=[True,False,False,False,False,False,False,True,True,True,False,False,False]
  c=Code(0x1f00);c.emit(0x78,0xd8);c.absolute(0x9c,0x7070);c.absolute(0x9c,0x7073)
  for n,ptr in enumerate(calls):
   if n==12:c.emit(0xa9,0xd7);c.absolute(0x8d,0x7070)
   c.emit(0xa9,ptr&255,0xa2,ptr>>8);c.absolute(0x20,sy['DBG_SYSTEM_REGISTER']);c.absolute(0x8d,0x1e00+2*n);c.emit(0x08,0x68,0x29,1);c.absolute(0x8d,0x1e01+2*n)
  c.emit(0xa2,0);c.label('registry');c.absolute(0xbd,0x7400);c.absolute(0x9d,0x1e80);c.emit(0xe8,0xe0,80);c.branch(0x90,'registry');c.absolute(0x9c,0x7070);c.absolute(0x9c,0x7073);c.absolute(0x4c,0x7e67)
  stub=c.done();assert len(stub)<=512
  # This larger fixture spans1F00-20FF; its descriptors and callback start2100.
  x.rec();b=packet(extra=requests);b=bytearray(b);b[:3]=bytes.fromhex('4C001F');b[0x1d00:0x1d00+len(stub)]=stub;x.s.load(bytes(b),t.sha(b),t.MON);status=x.s.dump(0x1e00,0x1e00+2*len(calls)-1)
  assert all(status[2*n]==(0 if ok else 1) and status[2*n+1]==int(ok) for n,ok in enumerate(expect));registry=x.s.dump(0x1e80,0x1ecf);assert registry[::4][:4]==bytes(range(0xa0,0xa4)) and registry[16:]==bytes(64);assert x.hooks()==x.oldhooks;check('private-system-registry-four-slots-and-all-admission-guards')
  x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
  for b in range(4):v=x.s.client.flash(b);assert v==old[b];(OUT/f'B{b}-after.bin').write_bytes(v)
  check('all-four-flash-banks-settings-history-and-golden-F-exact')
 r['passed']=bool(len(r['checks'])==17 and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed'];print('PASS2512 broader DBG RAM suite; full owner/cache/hooks restored; no NVM writes; COM4 free',flush=True)
if __name__=='__main__':run()
