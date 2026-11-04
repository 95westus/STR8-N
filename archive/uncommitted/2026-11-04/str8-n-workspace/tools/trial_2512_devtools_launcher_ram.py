"""Run actual AP decoder/entry adapters in RAM before any flash installation."""
import binascii,json
from devtools_2512_session import escrow,t,Q,AP,DP
from time_prep_ram_packets import Code
BUILD=t.ROOT/'BUILD/devtools-AP02-g1-r2';OUT=Q/'2512-devtools-launcher-RAM-20261102-r1'

def packet(name):
 raw=(BUILD/(name+'-expanded.bin')).read_bytes();sy=json.loads((BUILD/(name+'-adapter-symbols.json')).read_text())
 import sys
 sys.path.insert(0,str(t.REPO/'tools'));from storage_compact import compact
 packed=compact(raw);assert 0x203+len(packed)<0x1f00
 a=bytearray(0x2100);a[:3]=bytes.fromhex('4C001F');a[3:3+len(packed)]=packed
 decoder=(t.ROOT/'BUILD/named-edu-g3-r8/COMPACT-DECODE-6800.bin').read_bytes();a[0x1e00:0x1e00+len(decoder)]=decoder
 adapter=(BUILD/(name+'-adapter.bin')).read_bytes();a[0x2000:0x2000+len(adapter)]=adapter
 c=Code(0x1f00);c.emit(0x78,0xd8,0xa2,0);c.label('kernel')
 for source,dest in ((0x2000,0x6800),(0x2100,0x6900)):c.absolute(0xbd,source);c.absolute(0x9d,dest)
 c.emit(0xe8);c.branch(0xd0,'kernel');c.emit(0xa2,0);c.label('adapter');c.absolute(0xbd,0x2200);c.absolute(0x9d,0x6740);c.emit(0xe8,0xe0,len(adapter));c.branch(0x90,'adapter')
 end=0x4000+len(raw);crc=binascii.crc_hqx(raw,65535);srcend=0x203+len(packed)
 values={0xe0:3,0xe1:2,0xe2:0,0xe3:0x40,0x6708:3,0x6709:end&255,0x670a:end>>8,0x670b:0,0x670c:0x40,0x670d:crc&255,0x670e:crc>>8,0x670f:srcend&255,0x6710:srcend>>8}
 for addr,value in values.items():c.emit(0xa9,value);c.absolute(0x8d,addr)
 c.absolute(0x20,0x6740)
 if name=='ASM':c.absolute(0x20,sy['DT_PROVIDER']);c.branch(0xb0,'enter');c.absolute(0x4c,0x7e67)
 else:
  c.emit(0xa9,0);c.absolute(0x8d,0x707a);c.emit(0xa9,0x18);c.absolute(0x8d,0x707b);c.absolute(0x9c,0x6b00)
 c.label('enter');c.absolute(0x4c,sy['DT_ENTER']);code=c.done();assert len(code)<=256
 a[0x1d00:0x1d00+len(code)]=code
 if name=='DBG':a[0x1600:0x160a]=bytes.fromhex('A9118D00194C677EEAEA')
 return bytes(a)

def run():
 r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0)
 with escrow(OUT,r,'2512-devtools-AP-launcher-RAM',window=240) as x:
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  def asm():
   x.rec();body=packet('ASM');x.s.load(body,t.sha(body),AP);x.cmd('?')
  asm();check('accepted-decoder-ASM-entry-provider-CRC-and-help')
  for line in ('10 ORG $0200','20 LDA #$42','30 STA $1900','40 JMP $7E67','50 END'):x.cmd(line)
  assert b'OK 8 bytes' in x.cmd('ASM');assert b'A9 42' in x.cmd('DUMP');x.cmd('QUIT',(t.MON,));x.cmd('G 0200',(t.MON,));assert x.s.dump(0x1900,0x1900)==b'\x42';check('ASM-output-runs-and-returns')
  x.rec();body=packet('DBG');x.s.load(body,t.sha(body),DP);assert b'PC=1800' in x.cmd('R');assert b'PC=1802' in x.cmd('S');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x1800,0x1800)==b'\xa9' and x.s.dump(0x1900,0x1900)==b'\x11';check('DBG-initial-stop-step-HOLD-restores-hooks-and-first-byte')
  asm();assert b'Source storage: 81' in x.cmd('SAVE FLASH NOTEST');x.cmd('QUIT',(t.MON,));check('ASM-reloads-PROGRAM-after-debugger-cache-use')
 r['passed']=bool(len(r['checks'])==4 and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 launch adapters in RAM; owner restored; REC>; COM4 free',flush=True)
if __name__=='__main__':run()
