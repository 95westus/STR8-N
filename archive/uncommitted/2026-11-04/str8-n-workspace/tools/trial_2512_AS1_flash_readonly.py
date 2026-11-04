"""SF/1 RAM-first overlay, guards and allocation cancellation; zero SST writes."""
import binascii,json,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,CONF,ins
from time_prep_ram_packets import Code
BUILD=t.ROOT/'BUILD/asm-flash-source-g2-r4';OUT=Q/'2512-AS1-FLASH-readonly-RAM-20261102-r2'
PROMPT=b'; type YES> '

def packet(corrupt=False):
 body=bytearray((BUILD/'ASM-RAM.bin').read_bytes());sf=bytearray((BUILD/'FLASH-SOURCE-7000.bin').read_bytes())
 if corrupt:sf[-1]^=1
 # Sole transport substitution: provider source RAM3000 replaces ROMD800.
 pattern=bytes.fromhex('A9D885E1A97085E3');assert body.count(pattern)==1
 body=body.replace(pattern,bytes.fromhex('A93085E1A97085E3'));body[0x2e00:0x3600]=sf
 return bytes(body)

def bounds_packet():
 body=bytearray(packet());ns=json.loads((BUILD/'source-symbols.json').read_text());sf=json.loads((BUILD/'flash-provider-symbols.json').read_text())
 header=bytearray(32);header[:4]=b'SF\x01\xff';header[4:6]=(0x1809).to_bytes(2,'little');header[6]=2;header[8:13]=b'BOUND';header[24:26]=binascii.crc_hqx(header[:24],65535).to_bytes(2,'little');header[3]=0x3f;body[0x1c40:0x1c60]=header
 c=Code(0x1f00);c.emit(0x78,0xd8,0xa2,0);c.label('copy')
 for page in range(8):c.absolute(0xbd,0x3000+page*256);c.absolute(0x9d,0x7000+page*256)
 c.emit(0xe8);c.branch(0xd0,'copy');c.emit(0xa9,1);c.absolute(0x8d,0x6512);c.emit(0xa9,0x18);c.absolute(0x8d,0x6513);c.absolute(0x20,ns['NS_VALIDATE']);c.emit(0x08,0x68);c.absolute(0x8d,0x1e00)
 c.emit(0xa2,31);c.label('header');c.absolute(0xbd,0x1e40);c.absolute(0x9d,0x6540);c.emit(0xca);c.branch(0x10,'header');c.emit(0xa9,0x90);c.absolute(0x8d,0x6560);c.absolute(0x20,sf['NF_VALIDATE_HEADER']);c.emit(0x08,0x68);c.absolute(0x8d,0x1e01);c.absolute(0x4c,0x7e67)
 code=c.done();assert len(code)<=256;body[:3]=bytes.fromhex('4C001F');body[0x1d00:0x1d00+len(code)]=code;return bytes(body)

def run():
 assert json.loads((Q/'2512-AS1-FLASH-post-fault-audit-20261102-r1/report.json').read_text())['passed']
 print('2512 SF/1 RAM-only scan/cancel waiting for RTC window',flush=True)
 while True:
  try:ins.window(300);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,checks=[],flash_writes=0,flash_erases=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,borrowed_provider_cache='6B00-77FF')
 with escrow(OUT,r,'2512-AS1-FLASH-readonly-RAM',window=300,cache_first=0x6b00,cache_end=0x77ff) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  old={b:x.s.client.flash(b) for b in (0,3)}
  for b,v in old.items():assert t.sha(v)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(v)
  x.mon();worker=x.s.dump(0x7800,0x7be7);(OUT/'worker-before.bin').write_bytes(worker)
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  def enter(corrupt=False):x.rec();b=packet(corrupt);x.s.load(b,t.sha(b),AP)
  def lines():
   for line in ('10 ORG $0200','20 LDA #$42','30 STA $1900','40 JMP $7E67','50 END'):x.cmd(line)
  enter(True);lines();assert b'Source storage: 81' in x.cmd('SAVE FLASH SFTRY');x.cmd('QUIT',(t.MON,));assert x.s.dump(0x7800,0x7be7)==worker
  check('CRC-invalid-private-provider-refused-before-allocation')
  x.rec();b=bounds_packet();x.s.load(b,t.sha(b),t.MON);flags=x.s.dump(0x1e00,0x1e01);assert all(v&1 for v in flags) and x.s.dump(0x2000,0x2007)==bytes(8);assert x.s.dump(0x7800,0x7be7)==worker;check('AS1-and-SF1-source-size-bounds-refused-before-source-copy')
  enter();lines();before=x.cmd('LIST');face=x.cmd('SAVE FLASH SFTRY',(PROMPT,));assert b'Append source B0:9000 sectors 01' in face;assert b'Source storage: 54' in x.cmd('NO',(AP,));assert x.cmd('LIST')==before;check('exact-B0-9000-allocation-and-NO-cancels-with-source-intact')
  face=x.cmd('LOAD FLASH MISSING',(CONF,));assert b'Load cancelled' in x.cmd('NO',(AP,));assert x.cmd('LIST')==before;check('dirty-FLASH-load-NO-preserves-source')
  x.cmd('LOAD FLASH MISSING',(CONF,));assert b'Source storage: 42' in x.cmd('YES',(AP,));assert x.cmd('LIST')==before;check('valid-FLASH-provider-scan-missing-name-refused')
  x.cmd('LOAD SRAM MISSING',(CONF,));assert b'Source storage: 42' in x.cmd('YES',(AP,));assert x.cmd('LIST')==before;check('FLASH-to-PROGRAM-overlay-reload-and-read-only-lookup')
  x.cmd('SAVE FLASH SFTRY',(PROMPT,));assert b'Source storage: 54' in x.cmd('NO',(AP,));assert b'OK 8 bytes' in x.cmd('ASM');x.cmd('QUIT',(t.MON,));check('PROGRAM-to-FLASH-reload-and-unchanged-assembly')
  x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
  for b in (0,3):v=x.s.client.flash(b);assert v==old[b];(OUT/f'B{b}-after.bin').write_bytes(v)
  check('entire-B0-B3-flash-journal-settings-and-F-exact')
 r['passed']=bool(len(r['checks'])==8 and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 SF/1 read-only RAM gates; no writes; owner/full provider restored; COM4 free',flush=True)
if __name__=='__main__':run()
