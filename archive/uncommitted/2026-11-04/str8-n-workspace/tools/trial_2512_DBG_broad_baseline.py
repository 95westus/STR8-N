"""Safe baseline DBG cases; record cleanup defects without unsafe I/O stepping."""
import json,re,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,DP,ins
BUILD=t.ROOT/'BUILD/dbg-base1-g1-r5';OUT=Q/'2512-DBG-broad-baseline-RAM-20261102-r1'
def run():
 print('2512 DBG baseline waiting for RTC window',flush=True)
 while True:
  try:ins.window(360);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,checks=[],findings=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0)
 body=(BUILD/'DBG-BASE1-RAM.bin').read_bytes();assert t.sha(body)=='f55b7edddbf5ed783734e6247aa073d367dffdbe3ad3fc54f465c482a4306e12'
 with escrow(OUT,r,'2512-DBG-broad-safe-baseline',window=360,cache_first=0x6b00,cache_end=0x77ff) as x:
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  def enter(program=b'\x4c\x67\x7e',extra=None):
   b=bytearray(body);b[0xe00:0xe02]=b'\0\0';b[0xe02:0xe02+len(program)]=program
   for address,data in (extra or {}).items():b[address-0x200:address-0x200+len(data)]=data
   x.rec();x.s.load(bytes(b),t.sha(b),DP)
  def logical(a,end=None):
   face=x.cmd(f'D {a:04X}'+(f' {end:04X}' if end is not None else ''));rows=re.findall(rb'([0-9A-F]{4}): ([0-9A-F]{2})',face);return bytes(int(v,16) for _,v in rows)
  def leave():x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
  enter();old=logical(0x10)[0];wanted=old^255;x.cmd(f'M 0010 {wanted:02X}');assert logical(0x10)==bytes((wanted,));leave();actual=x.s.dump(0x10,0x10)[0];r['findings'].append(dict(case='X preserves logical user ZP edits',expected=wanted,actual=actual,defect=actual!=wanted));check('safe-X-ZP-cleanup-observation')
  enter(bytes.fromhex('A96D8510A95A85D04C677E'),{0x2000:b'\xea'});x.cmd('B 2000');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x2000,0x2000)==b'\xea';actual=x.s.dump(0xd0,0xd0)[0];r['findings'].append(dict(case='program HOLD preserves live user D0',expected=0x5a,actual=actual,defect=actual!=0x5a));assert x.s.dump(0x10,0x10)==b'\x6d';check('safe-HOLD-ZP-and-patch-cleanup-observation')
  enter(extra={0x2000:b'\xea'});x.cmd('B 2000');face=x.cmd('BC');listing=x.cmd('B');r['findings'].append(dict(case='BC without arguments clears all',defect=b'2000\r\n' in listing,response=face.decode()));x.cmd('BC *');leave();check('BC-and-explicit-clear-all-observation')
  enter(extra={0x1200:bytes.fromhex('200040')});x.cmd('R PC 1200');x.cmd('R SP FF');x.cmd('M 01FE AA BB');before=logical(0x1fe,0x1ff);face=x.cmd('S');after=logical(0x1fe,0x1ff);assert b'?\r\n' in face;r['findings'].append(dict(case='rejected JSR leaves logical stack unchanged',before=before.hex(),after=after.hex(),defect=before!=after));leave();check('out-of-RAM-JSR-refusal-and-stack-observation')
  enter(bytes.fromhex('4C0020'),{0x2000:b'\xea'*8+bytes.fromhex('4C677E')})
  for a in range(0x2000,0x2008):x.cmd(f'B {a:04X}')
  assert b'?\r\n' in x.cmd('B 2008')
  for a in range(0x2000,0x2008):assert f'PC={a:04X}'.encode() in x.cmd('C',(DP,))
  x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x2000,0x2007)==b'\xea'*8;check('all-eight-breakpoints-hit-and-original-bytes-restored')
  assert sum(v['defect'] for v in r['findings'])==4
 r['passed']=bool(len(r['checks'])==5 and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed'];print('PASS2512 safe baseline; four reproducible findings; owner/cache/hooks restored; COM4 free',flush=True)
if __name__=='__main__':run()
