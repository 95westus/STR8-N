"""Owner-requested2609 saved default and foreground MON; F remains golden."""
import json,time
from pathlib import Path
import install_2609_candidate3 as ins
from native_journal_room import valid_snapshot
from prepare_boot_clock_scope_2512 import append_policy
t=ins.t;d=ins.d;Q=ins.Q;OUT=Q/'2609-default-MON-g10-20261102-r1'
CONFIG=b'RAM CONFIG ? B C I W Q> '

def run():
 print('2609 default-MON check waiting for RTC window',flush=True)
 while True:
  try:ins.ins.window(180);break
  except AssertionError:time.sleep(1)
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();config=(ins.KIT/'foundation/firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes();mp=Q/'device-operations/2609.json'
 r=dict(board='2609',passed=False,selected='B',generation='00000010',append_requests=0,flash_erases=0,F_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
 s=None;borrowed=False;ram=zp=None;after=None
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def mon():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context==t.REC:s.command('B',(t.MON,))
  assert s.context==t.MON
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context==t.MON:s.command('Q',(t.REC,))
  assert s.context==t.REC
 save()
 with t.serial_lease('2609-owner-default-MON-g10',timeout=30):
  ins.ins.window(180);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.REC,t.MON),seconds=15);mon();face=s.command('VERSION');assert b'STR8-N MON B  gen 00000010' in face and b'CPU: 65C816 emulation' in face
    prefix=s.dump(0x200,0x1ff+len(reader));zp=s.dump(0,0xdf);(OUT/'owner-zp.bin').write_bytes(zp)
    mark(default_boot_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
    old=s.client.flash(3);assert t.sha(old)==m['current_physical_bank_sha256']['B3'];(OUT/'B3-before.bin').write_bytes(old)
    assert int.from_bytes(old[0x3008:0x300c],'little')==16
    latest=max((old[i:i+256] for i in range(0x4000,0x6000,256) if valid_snapshot(old[i:i+256])),key=lambda v:int.from_bytes(v[8:12],'little'))
    r['already_default_B_g10']=latest[7]==ord('B') and latest[18:22]==(16).to_bytes(4,'little');after=old
    if not r['already_default_B_g10']:
     changes={7:ord('B'),**{18+i:v for i,v in enumerate((16).to_bytes(4,'little'))}}
     expected,operation=append_policy(old,changes,'C B default MON B g10');assert not operation['journal_sector_erases'] and len(operation['journal_appends'])==1,'Default change requires an unreviewed rotation; do not write'
     t.save(OUT/'zero-erase-append-review.json',operation);rec();s.load(config,t.sha(config),CONFIG);r['append_requests']=1;save();face=s.command('C B');assert b'OK' in face and b'REFUSED' not in face
     s.command('Q',(t.MON,));rec();s.service(reader);after=s.client.flash(3);assert after==expected
    r['journal']=t.classify_journal(after);assert r['journal']['default']=='B';(OUT/'B3-after.bin').write_bytes(after)
    r['saved_default_verified']=True
   except BaseException as e:r['error']=repr(e);save();raise
   finally:
    try:
     if borrowed:
      rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
      if r.get('saved_default_verified'):
       face=s.command('B',(t.MON,));assert b'STR8-N MON B  gen 00000010' in face
       assert s.owner()==(ram,zp);r['foreground_MON_B_and_owner_verified']=True;r['final_prompt']='B3>'
    finally:
     if s:s.link.close();r['COM8_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];fields=dict(default_boot_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=m['block_snapshot'] if restored else True,final_prompt=r.get('final_prompt','REC>'),last_default_MON_g10=str(OUT/'report.json'))
      if r.get('saved_default_verified'):
       hs=m['current_physical_bank_sha256'].copy();hs['B3']=t.sha(after);fields.update(current_physical_bank_sha256=hs,saved_default='B',saved_default_generation='00000010',default_monitor_generation='00000010',current_journal_sequence=r['journal']['sequence'],current_journal_valid_records=r['journal']['valid_records'],current_valid_journal_records=r['journal']['valid_records'],current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
      mark(**fields)
     save()
 r['passed']=bool(r.get('saved_default_verified') and r.get('foreground_MON_B_and_owner_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2609 saved default B/g10 verified; MON B running; owner restored; COM8 free; appends='+str(r['append_requests']),flush=True)

if __name__=='__main__':run()
