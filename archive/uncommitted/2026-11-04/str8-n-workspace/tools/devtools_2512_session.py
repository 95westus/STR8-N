"""Bounded2512 devtool RAM escrow; no nonvolatile operation is implicit."""
import json,re
from contextlib import contextmanager
import install_named_edu_2512 as ins
t=ins.t;d=ins.d;Q=ins.Q
AP=b'ASM> ';DP=b'DBG> ';CONF=b'Discard unsaved edits? Type YES: '

class Session:
 def __init__(self,out,report,board='2512'):
  assert board in ('2512','2609')
  self.out=out;self.r=report;self.s=None;self.borrowed=False;self.ram=self.zp=self.high=None;self.cache_first=0x7000;self.mp=Q/f'device-operations/{board}.json'
 def save(self):t.save(self.out/'report.json',self.r)
 def mark(self,**kw):m=json.loads(self.mp.read_text());m.update(kw);t.save(self.mp,m)
 def cmd(self,line,tokens=None):
  face=self.s.command(line,tokens);(self.out/f'{self.s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(face);return face
 def mon(self):
  s=self.s
  import nf_opaque
  if s.context in (b'B0> ',b'B1> ',b'B2> '):self.cmd('B3',(t.MON,))
  if s.context==nf_opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
  if s.context is None:raise AssertionError('Unknown execution state; no blind RAM reload')
  if s.context==CONF:self.cmd('NO',(AP,))
  if s.context==AP:self.cmd('QUIT',(t.MON,))
  if s.context==DP:self.cmd('X',(t.MON,))
  if s.context==b'DBG RAM start 0200-3FFF; Q MON> ':self.cmd('Q',(t.MON,))
  if s.context in (t.CLOCK,d.FT,b'BM> ',b'STORAGE> ',b'SRAM> ',b'WORK> '):self.cmd('Q',(t.MON,))
  if s.context==t.PB:s.link.send(b'Q');s.until((t.MON,),seconds=15)
  if s.context==t.WB:self.cmd('Q',(t.MON,))
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context==t.REC:self.cmd('B',(t.MON,))
  assert s.context==t.MON
 def rec(self):
  s=self.s
  import nf_opaque
  if s.context==nf_opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:self.mon();self.cmd('Q',(t.REC,))
 def hooks(self):return self.s.dump(0x7e02,0x7e03)+self.s.dump(0x7e67,0x7e69)
 def restore_high(self):
  self.mon();s=self.s
  for off in range(0,len(self.high),8):self.cmd(f'M {0x2000+off:04X} '+self.high[off:off+8].hex(' ').upper())
  code=bytearray(bytes.fromhex('78D8A200'));loop=0x3004
  for page in range(len(self.high)//256):code+=bytes((0xbd,0,(0x2000+256*page)>>8,0x9d,0,(self.cache_first+256*page)>>8))
  code+=bytes((0xe8,0xd0,(loop-(0x3000+len(code)+3))&255));code+=bytes.fromhex('A92F85E0AD307D85E16CE000')
  for off in range(0,len(code),8):self.cmd(f'M {0x3000+off:04X} '+code[off:off+8].hex(' ').upper())
  self.cmd('G 3000',(t.MON,));assert s.dump(self.cache_first,self.cache_first+len(self.high)-1)==self.high;self.r['provider_cache_restored']=True
 def wb(self):
  self.mon();self.cmd('MAINT LOAD',(t.WB,));face=self.cmd('SRAM');assert b'SSRAM PROGRAM:' in face,face
 def raw(self,address):
  assert self.s.context==t.WB and address%64==0 and 0<=address<=0x1ffc0
  face=self.cmd(f'SRAM READ {address>>16:X} {address&65535:04X}');m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){63}[0-9A-F]{2})',face);assert m,face
  return bytes.fromhex(m[1].decode())

@contextmanager
def escrow(out,report,kind,window=180,cache_first=0x7000,cache_end=0x74ff,lease_timeout=30,board='2512'):
 assert cache_first%256==0 and cache_end%256==255 and 0x6b00<=cache_first<=cache_end<=0x77ff
 ins.window(window);out.mkdir();(out/'.gitignore').write_text('*\n');x=Session(out,report,board);x.cache_first=cache_first;x.save()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 with t.serial_lease(kind,timeout=lease_timeout):
  ins.window(window)
  ins.window(window);x.original=json.loads(x.mp.read_text());m=x.original
  assert m['board']==board and m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  t.save(out/'marker-before.json',m)
  with (out/'serial.jsonl').open('x') as log:
   try:
    s=x.s=d.Session(out,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);x.mon()
    cpu=b'CPU: 65C02' if board=='2512' else b'CPU: 65C816 emulation'
    face=x.cmd('VERSION');assert b'STR8-N MON B  gen 00000010' in face and cpu in face
    prefix=s.dump(0x200,0x1ff+len(reader));x.zp=s.dump(0,0xdf);x.high=s.dump(cache_first,cache_end);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
    for name,body in [('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)]:(out/name).write_bytes(body)
    x.mark(ASM_source_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);x.borrowed=True
    x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;x.ram=prefix+memory[len(reader):];(out/'owner-ram.bin').write_bytes(x.ram)
    assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3']
    yield x
   except BaseException as e:report['error']=repr(e);x.save();raise
   finally:
    try:
     if x.borrowed:
      x.mon();assert x.hooks()==x.oldhooks;x.restore_high();x.rec();s=x.s;s.service(reader)
      try:
       wanted=getattr(x,'expected_b3_sha256',m['current_physical_bank_sha256']['B3'])
       assert t.sha(s.client.flash(3))==wanted
       report['B3_F_images_settings_history_unchanged' if wanted==m['current_physical_bank_sha256']['B3'] else 'planned_B3_verified']=True
      finally:
       report.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
    finally:
     if x.s:x.s.link.close();report['port_released']=True
     if x.borrowed:
      restored=report.get('owner_RAM_restored') and report.get('owner_ZP_restored')
      x.mark(ASM_source_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=bool(restored),block_snapshot=m['block_snapshot'] if restored and not report.get('SPI_mutation_pending') else True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_ASM_source_operation=str(out/'report.json'))
     x.save()
