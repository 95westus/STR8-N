"""Admit standalone REC utilities and capture cleanup preimages; no NVM writes."""
import binascii,json,re
from pathlib import Path
import devtools_2512_session as ds
t=ds.t;Q=ds.Q;BM=b'BM> ';FT=ds.d.FT
OUT=Q/'2609-REC-cleanup-tools-20261102-r1'

def run():
 maint=t.ROOT/'BUILD/loadable-maint-full-r2';mm=json.loads((maint/'manifest.json').read_text());mb=(maint/'MAINT.bin').read_bytes();assert t.sha(mb)==mm['sha256']
 flash=t.ROOT/'firmware/ram-tools/flash-g2';fm=json.loads((flash/'manifest.json').read_text());fb=(flash/'FLASH.bin').read_bytes();assert t.sha(fb)==fm['sha256']
 r=dict(board='2609',passed=False,CPU='65C816 emulation',checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,power_cuts=0,MAINT_sha256=t.sha(mb),FLASH_sha256=t.sha(fb))
 with ds.escrow(OUT,r,'2609-REC-cleanup-utility-RAM-admission',window=360,cache_first=0x6b00,cache_end=0x77ff,board='2609') as x:
  def check(s):r['checks'].append(s);x.save();print('PASS '+s,flush=True)
  def leave(prompt):
   assert x.s.context==prompt
   x.cmd('Q',(t.MON,t.REC));x.mon()
  try:
   for bank in range(4):
    data=x.s.client.flash(bank);assert t.sha(data)==x.original['current_physical_bank_sha256'][f'B{bank}'];(OUT/f'B{bank}-before.bin').write_bytes(data)
   check('fresh four-bank capture matches preserved images/settings/history')
   x.wb();table=x.cmd('TABLE P');assert all(n not in table for n in (b' CLK',b' CLOCK',b' NFCOPY'))
   meta=b''.join(x.raw(a) for a in range(0,0x800,64));(OUT/'SPI-metadata-before.bin').write_bytes(meta)
   assert all(meta[0x40+64*k+63]!=0xa5 for k in range(8));check('PROGRAM already empty; no SPI cleanup writes needed')
   x.rec();x.s.load(mb,t.sha(mb),BM)
   assert b'Copy RAM or flash' in x.cmd('?',(BM,)) and b'REC 0200 r1' in x.cmd('VERSION',(BM,))
   assert b'Board: 2609' in x.cmd('NAME',(BM,));assert b'DEFAULT=B' in x.cmd('BOOT',(BM,));assert b'CLOCK' in x.cmd('TABLE',(BM,))
   x.cmd('N 1000 FF',(BM,));x.cmd('P 0 12 34 56',(BM,));assert b'12 34 56' in x.cmd('D 0-F',(BM,))
   want=binascii.crc_hqx(b'\x12\x34\x56'+b'\xff'*4093,65535)
   for cmd in ('K','M1','K','M3','K'):
    face=x.cmd(cmd,(BM,))
    if cmd=='K':assert f'CRC16-CCITT-FALSE {want:04X}'.encode() in face
   check('816 full REC MAINT menu/TABLE/BOOT/name/maps/4K editor and CRC')
   for cmd in ('W R 1000','C R 1000-100F R 1100'):
    x.cmd(cmd,(b'WRITE? TYPE Y> ',));assert b'VERIFIED' in x.cmd('Y',(BM,))
   assert b'MATCH' in x.cmd('V R 1000-100F R 1100',(BM,))
   for cmd in ('E 3 F','E 3 C-D'):
    face=x.cmd(cmd,(BM,));assert b'WRITE? TYPE Y' not in face and (b'CANCELED' in face or b'PROTECTED' in face)
   leave(BM);check('816 MAINT RAM write/copy/compare, golden-region refusal and Q')
   x.rec();x.s.load(fb,t.sha(fb),FT)
   assert b'FLASH g2' in x.cmd('VERSION',(FT,));assert b'I first last' in x.cmd('?',(FT,))
   x.cmd('BANK 0',(FT,));x.cmd('READ 8000',(FT,));assert b'0000' in x.cmd('VIEW 000',(FT,))
   assert b'REFUSED' in x.cmd('I 9001 9FFF',(FT,));x.cmd('I 9000 9FFF',(b'type YES> ',));assert b'Canceled' in x.cmd('NO',(FT,))
   leave(FT);check('816 REC FLASH version/menu/read/view, erase refusal/cancel and Q')
   x.rec();x.s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
   for bank in range(4):assert t.sha(x.s.client.flash(bank))==x.original['current_physical_bank_sha256'][f'B{bank}']
   check('all four flash banks exact after both RAM utilities')
  finally:
   if x.s.context==b'type YES> ':x.cmd('NO',(FT,))
   if x.s.context==b'WRITE? TYPE Y> ':x.cmd('NO',(BM,))
   if x.s.context in (BM,FT):leave(x.s.context)
 r['passed']=len(r['checks'])==6 and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'))
 t.save(OUT/'report.json',r);assert r['passed'];print('PASS 2609 REC utilities; RAM restored; COM8 released',flush=True)
if __name__=='__main__':run()
