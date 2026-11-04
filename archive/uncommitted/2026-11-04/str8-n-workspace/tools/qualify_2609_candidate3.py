"""Approved Candidate3 816 runtime checks; RAM only, exact owner restoration."""
import json,re,sys,time
from pathlib import Path
import install_2609_candidate3 as ins
t=ins.t;d=ins.d;Q=ins.Q;KIT=ins.KIT
OUT=Q/'2609-candidate3-runtime-20261102-r1'
sys.path.insert(0,str(KIT/'foundation/tools'))
from console_core import Session as Console,s19_image
READY=b'SEND S19 (S0/S1/S9); Ctrl-C cancels\r\n'

def run():
 ins.approved();assert json.loads((Q/'2609-candidate3-installed-20261102-r2/report.json').read_text())['passed']
 ins.ins.window(180);OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 reader=(KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 mp=Q/'device-operations/2609.json';s=None;borrowed=False;ram=zp=None
 r=dict(board='2609',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,owner_RAM_restored=False,owner_ZP_restored=False)
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):
  face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
 def mon():
  if s.context is None:s.link.send(b'\x03\r');s.until((t.REC,t.MON,t.WB,d.FT,t.CLOCK,ins.BM,ins.SRAM,ins.WORK),seconds=15)
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context in (t.WB,d.FT,t.CLOCK,ins.BM,ins.SRAM,ins.WORK):cmd('Q',(t.MON,))
  if s.context==t.REC:cmd('B',(t.MON,))
  assert s.context==t.MON
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
 def check(n):r['checks'].append(n);save();print('PASS2609 '+n,flush=True)
 def transfer(cancel):
  mon();ready=cmd('S19',(READY,));s.context=None
  class Port:
   @property
   def in_waiting(self):return s.link.serial.in_waiting
   def write(self,data):s.link.send(data);return len(data)
   def read(self,n):return s.link.read(n)
   def close(self):raise AssertionError('Outer owner closes port')
  events=[];core=Console(lambda *e:events.append(e));core.attach(Port());core.receive(ready)
  path,body,digest=s19_image(KIT/'examples/KEY-S19-3500.s19');core.start_s19(path,body,digest)
  if cancel:core.cancel()
  deadline=time.monotonic()+25
  while core.busy and time.monotonic()<deadline:core.tick();time.sleep(.002)
  assert not core.busy and core.prompt=='mon'
  result=[e[1] for e in events if e[0]=='transfer'][-1]
  assert result['cancelled']==cancel and result['board_accepted']==(not cancel)
  t.save(OUT/('S19-cancel.json' if cancel else 'S19-normal.json'),result);s.context=t.MON
 save()
 with t.serial_lease('2609-candidate3-816-runtime',timeout=30):
  ins.ins.window(180);marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
    face=cmd('VERSION');assert b'CPU: 65C816 emulation' in face and b'Board: 2609' in face and b'STR8-N MON B  gen 00000010' in face
    assert re.search(rb'trim \$0E ctrl \$80',cmd('TIME'))
    prefix=s.dump(0x200,0x1ff+len(reader));zp=s.dump(0,0xdf);(OUT/'owner-zp.bin').write_bytes(zp)
    mark(candidate3_runtime_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
    ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
    assert t.sha(ram)==marker['current_owner_RAM_sha256'] and t.sha(zp)==marker['current_owner_ZP_sha256']
    check('816-emulation-g10-B-native-TIME-trim-and-fresh-owner')
    mon();face=cmd('MAINT LOAD',(t.WB,));assert b'g0000000E' in face;cmd('Q',(t.MON,))
    face=cmd('APPS');assert b'CLOCK' in face and b'MAINT' in face and b'FLASH' in face
    cmd('R CLOCK',(t.CLOCK,));cmd('STATUS');cmd('HISTORY');cmd('Q',(t.MON,))
    cmd('R MAINT',(ins.BM,));face=cmd('?');assert b'Compare' in face or b'compare' in face;cmd('T');cmd('Q',(t.MON,))
    check('installed-APPS-CLOCK-detail-history-and-BANK-MAINT')
    for app,prompt in (('SRAM',ins.SRAM),('WORK',ins.WORK)):
     cmd('R '+app,(prompt,));cmd('?');cmd('T' if app=='SRAM' else '?');cmd('Q',(t.MON,))
     face=cmd('BATCH R '+app+';'+('T' if app=='SRAM' else '?')+';Q;D 1000',(t.MON,))
     assert b'BATCH done' in face and b'1000' in face and b'REFUSED' not in face
    check('installed-storage-and-WORK-returning-BATCH')
    transfer(True);transfer(False);assert s.dump(0x3500,0x3503)==b'KEYS';check('extracted-console-S19-Ctrl-C-and-independent-load-readback')
    rec();face=cmd('L',(b'SEND BIN\r\n',));s.context=None;s.link.send(b'\x03');s.until((t.REC,),seconds=15)
    body=(KIT/'examples/NFCOPY-3000.bin').read_bytes();assert body==bytes.fromhex('A950206D7E4C677E')
    s.load(body,t.sha(body),t.MON);assert s.dump(0x200,0x207)==body;check('SEND-BIN-Ctrl-C-and-normal-RAM-BIN-public-HOLD')
    body=bytes.fromhex('A9168DFF184C677E')
    for off in range(0,len(body),8):cmd('M '+f'{0x2000+off:04X} '+' '.join(f'{v:02X}' for v in body[off:off+8]))
    cmd('G 2000',(t.MON,));assert s.dump(0x18ff,0x18ff)==b'\x16';check('RAM-G-marker-and-public-HOLD-return')
    rec();s.service(reader);assert s.client.flash(3)==(ins.SCOPE/'B3-expected.bin').read_bytes();r['B3_images_settings_history_F_exact']=True
   except BaseException as e:r['error']=repr(e);save();raise
   finally:
    try:
     if borrowed:
      rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    finally:
     if s:s.link.close();r['port_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(candidate3_runtime_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_candidate3_runtime=str(OUT/'report.json'))
     save()
 r['passed']=bool(len(r['checks'])==6 and r.get('B3_images_settings_history_F_exact') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2609 Candidate3 816 runtime; owner RAM/ZP restored; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
