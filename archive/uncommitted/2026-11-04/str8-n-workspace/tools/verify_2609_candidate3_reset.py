"""Approved single physical RESET; passive COM8 wait yields the fleet lease."""
import json,re,time
from pathlib import Path
import install_2609_candidate3 as ins
t=ins.t;d=ins.d;Q=ins.Q
OUT=Q/'2609-candidate3-reset-20261102-r1'
RUNTIME=Q/'2609-candidate3-runtime-20261102-r1'

def run():
 ins.approved();assert json.loads((RUNTIME/'report.json').read_text())['passed']
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 ram=(RUNTIME/'owner-ram.bin').read_bytes();zp=(RUNTIME/'owner-zp.bin').read_bytes()
 reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 mp=Q/'device-operations/2609.json';s=None;borrowed=False
 r=dict(board='2609',passed=False,phase='arming',physical_resets=0,power_cuts=0,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,owner_RAM_restored=True,owner_ZP_restored=True)
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):
  face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{line}.txt').write_bytes(face);return face
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context==t.MON:cmd('Q',(t.REC,))
  assert s.context==t.REC
 save()
 with (OUT/'serial.jsonl').open('x') as log:
  try:
   with t.serial_lease('2609-candidate3-reset-arming',timeout=30):
    m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m.get('physical_reset_pending')
    assert m['monitor_generation']=='00000010' and m['current_journal_sequence']==1089
    assert m['current_owner_RAM_sha256']==t.sha(ram) and m['current_owner_ZP_sha256']==t.sha(zp)
    mark(physical_reset_pending=True,candidate3_reset_waiting=True)
    s=d.Session(OUT,log,'2609');s.link.serial.reset_input_buffer();s.link.pending.clear()
    r['phase']='waiting-for-physical-reset';save()
   print('ARMED2609 Candidate3 RESET; passive COM8 receiver; fleet lease released',flush=True)
   deadline=time.monotonic()+12*3600
   while time.monotonic()<deadline:
    try:face=s.until((t.MON,),seconds=25)
    except TimeoutError:continue
    if b'STR8-N MON B  gen 00000010' not in face:continue
    (OUT/'full-startup.txt').write_bytes(face);break
   else:raise TimeoutError('No reset captured')
   r['physical_resets']=1;r['phase']='startup-captured';save()
   with t.serial_lease('2609-candidate3-reset-verification',timeout=90):
    mark(candidate3_reset_waiting=False,candidate3_reset_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    borrowed=True;r['owner_RAM_restored']=r['owner_ZP_restored']=False
    try:
     for text in (b'Boot : 6 5 4 3 2 1 0',b'STR8-N F 0.3.0  Foundation',b'Recovery / opaque-image boot',b'STR8-N MON B  gen 00000010',b'Board: 2609',b'EDU ON',b'SSRAM: PROGRAM payload',b'SSRAM: WORKSPACE',b'FLASH:',b'Battery:'):
      assert text in face,(text,face)
     r['saved_B_Traditional_cold_start_and_SSRAM_without_PREP']=True
     version=cmd('VERSION');assert b'CPU: 65C816 emulation' in version and b'BASE1/PR05 ABI 2' in version
     for text in (b'MONITOR A gen 00000010 VALID',b'MONITOR B gen 00000010 VALID default'):assert text in version
     assert re.search(rb'trim \$0E ctrl \$80',cmd('TIME'));r['VERSION_and_native_TIME_trim_preserved']=True
     rec();s.service(reader);assert s.client.flash(3)==(ins.SCOPE/'B3-expected.bin').read_bytes();r['B3_images_metadata_history_F_exact']=True
    finally:
     rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
     restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
     mark(candidate3_reset_worker_active=False,physical_reset_pending=not restored,application_RAM_restore_pending=not restored,application_ram_restored=restored,final_prompt='REC>',last_candidate3_reset=str(OUT/'report.json'))
  except BaseException as e:r['error']=repr(e);save();raise
  finally:
   if s:s.link.close();r['port_released']=True
   mark(candidate3_reset_waiting=False);save()
 r['passed']=bool(r.get('saved_B_Traditional_cold_start_and_SSRAM_without_PREP') and r.get('VERSION_and_native_TIME_trim_preserved') and r.get('B3_images_metadata_history_F_exact') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 mark(candidate3_physical_boot_pending=False)
 print('PASS2609 physical saved-B g10 startup; F/settings/history exact; owner restored; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
