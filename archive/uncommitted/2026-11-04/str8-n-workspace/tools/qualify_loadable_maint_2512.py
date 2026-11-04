"""Live REC load and RAM-only checks of full MAINT; no persistent writes."""
import argparse,binascii,json,re
import devtools_2512_session as ds
t=ds.t;Q=ds.Q;BM=b'BM> ';CONFIRM=b'WRITE? TYPE Y> '
OUT=Q/'2512-loadable-full-MAINT-20261102-r1';BUILD=t.ROOT/'BUILD/loadable-maint-full-r2'
def run(out=OUT,resume=None):
 m=json.loads((BUILD/'manifest.json').read_text());body=(BUILD/'MAINT.bin').read_bytes();assert t.sha(body)==m['sha256']
 r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,load='0200',entry='0200',MAINT_sha256=m['sha256'])
 if resume:
  previous=json.loads((resume/'report.json').read_text());assert previous['MAINT_sha256']==m['sha256'] and len(previous['checks'])==4
  assert previous['owner_RAM_restored'] and previous['owner_ZP_restored'] and previous['B3_F_images_settings_history_unchanged']
  r['checks']=previous['checks'];r['accepted_prefix_receipt']=str(resume/'report.json')
 with ds.escrow(out,r,'2512-full-MAINT-REC-RAM-only',window=360,cache_first=0x6b00,cache_end=0x77ff) as x:
  def quit_to_rec():
   x.s.link.send(b'Q\r');x.s.context=None
   chooser=b'A/B/S,Enter default [3s]:'
   x.s.until((chooser,t.REC,t.MON),seconds=15)
   if x.s.context==chooser:x.cmd('S',(t.REC,))
   if x.s.context==t.MON:x.cmd('Q',(t.REC,))
   assert x.s.context==t.REC
  def check(s):r['checks'].append(s);x.save();print('PASS '+s,flush=True)
  def crc():
   text=x.cmd('K',(BM,));match=re.search(rb'CRC16-CCITT-FALSE ([0-9A-F]{4})',text);assert match,text;return int(match[1],16)
  def write(s):
   x.cmd(s,(CONFIRM,));assert x.s.context==CONFIRM
   face=x.cmd('Y',(BM,));assert b'VERIFIED' in face,face
  try:
   x.rec();x.s.load(body,m['sha256'],BM)
   if not resume:
    menu=x.cmd('?',(BM,));assert b'Copy RAM or flash' in menu and b'Buffer CRC16' in menu and b'Q Restart F' in menu
    assert b'REC 0200 r1' in x.cmd('VERSION',(BM,));check('REC raw BIN startup, full menu and local VERSION')
    face=x.cmd('NAME',(BM,));assert b'Board: 2512' in face,face
    x.cmd('NAME TEST',(b'Type YES: ',));x.cmd('NO',(BM,));assert b'Board: 2512' in x.cmd('NAME',(BM,))
    assert b'DEFAULT=B' in x.cmd('BOOT',(BM,));check('NAME query/cancel and BOOT inspection')
    table=x.cmd('TABLE',(BM,));assert b'CLOCK' in table and b'no payload CRC' in table,table
    check('TABLE catalogues installed named flash records')
    x.cmd('N 1000 FF',(BM,));x.cmd('P 0 12 34 56',(BM,));x.cmd('F 10-1F A5',(BM,))
    expected=bytearray(b'\xff'*4096);expected[:3]=b'\x12\x34\x56';expected[0x10:0x20]=b'\xa5'*16;want=binascii.crc_hqx(expected,65535)
    assert crc()==want;assert b'12 34 56' in x.cmd('D 0-1F',(BM,))
    for query in ('M1','M2','M3','VERSION','TABLE 1'):
     text=x.cmd(query,(BM,));assert b'REFUSED' not in text and b'INVALID' not in text,text
     if query=='M3':assert b'SNBT SEQ=' in text and b'??????' not in text,text
     assert crc()==want,query
    check('4K editor patch/fill/display/CRC; maps preserve editor')
   x.cmd('R 3 8000-80FF',(BM,));write('W R 1300');write('C R 1300-13BF R 1340');write('C R 1300-133F R 1500')
   assert b'MATCH' in x.cmd('V R 1300-133F R 1500',(BM,))
   x.cmd('N 1 EF',(BM,));write('W R 1500');assert b'DIFFERENT AT DEST 1500' in x.cmd('V R 1300-133F R 1500',(BM,))
   x.cmd('C R 1300-133F R 1580',(CONFIRM,));x.cmd('NO',(BM,))
   for query in ('E 3 F','E 3 C-D','E 2 8','E 1 8-A','C R 1300-133F 3 F000'):
    text=x.cmd(query,(BM,));assert b'WRITE? TYPE Y' not in text and (b'INVALID / PROTECTED RANGE' in text or b'CANCELED' in text),text
   check('RAM copy/compare/overlap/cancel; F/C/D and installed utilities protected')
   quit_to_rec();check('Q restarts golden Foundation; recovery selected without settings writes')
   x.mon();actual=x.s.dump(0x1300,0x13ff);source=x.s.dump(0x8000,0x80ff)
   want=bytearray(source);want[0x40:]=source[:0xc0];assert actual==want
   assert x.s.dump(0x1500,0x153f)==b'\xef'+source[1:0x40];check('exact RAM destination and overlapping memmove results')
  finally:
   if x.s.context==CONFIRM:x.cmd('NO',(BM,))
   if x.s.context==BM:quit_to_rec()
 r['passed']=len(r['checks'])==7 and r.get('B3_F_images_settings_history_unchanged') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored')
 t.save(out/'report.json',r);assert r['passed'];print('PASS full MAINT; RAM restored; REC>; COM4 released',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=type(OUT),default=OUT);p.add_argument('--resume',type=type(OUT));a=p.parse_args();run(a.out,a.resume)
