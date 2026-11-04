"""Seal approved2609 Candidate3 evidence and final full owner-RAM restoration."""
import json
from pathlib import Path
import install_2609_candidate3 as ins
import rtc_drift_campaign as c
t=ins.t;d=ins.d;Q=ins.Q
OUT=Q/'2609-candidate3-closeout-20261102-r1'
RUNTIME=Q/'2609-candidate3-runtime-20261102-r1'
RTC=Q/'2609-candidate3-RTC-readmission-20261102-r2'

def run():
 p=ins.approved()
 receipts={k:Q/(v+'/report.json') for k,v in dict(installation='2609-candidate3-installed-20261102-r2',runtime='2609-candidate3-runtime-20261102-r1',reset='2609-candidate3-reset-20261102-r1',RTC='2609-candidate3-RTC-readmission-20261102-r2').items()}
 rs={k:c.read(v) for k,v in receipts.items()};assert all(r['passed'] for r in rs.values())
 assert rs['installation']['image_erase_requests']==15 and rs['installation']['native_journal_erases']==['B3:C'] and rs['installation']['journal_appends']==17
 assert rs['reset']['physical_resets']==1 and rs['RTC']['trim_steps']==-14 and rs['RTC']['control']==0x80
 package=t.ROOT/'BUILD/unified-g10-candidate3-20261101-r3/STR8N-MON-g00000010-candidate3.zip'
 assert c.sha(package)=='6b1b3220cf5c05be0b49bf98c055f1df82e3870531512e2d3f94f3363b4bc789'
 state=c.read(c.STATE);old=c.read(RTC/'campaign-before.json')
 assert state['baselines']==old['baselines'] and state['segment_boundaries']==old['segment_boundaries']
 assert state['base1_profile']==old['base1_profile']
 for board in ('2205','2512','2604'):assert state['board_admission'][board]==old['board_admission'][board]
 import rtc_led_mode_g10_2609 as mode
 assert mode.ready(state) and mode.previous.ready(state)
 ins.ins.window(120);OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 ram=(RUNTIME/'owner-ram.bin').read_bytes();zp=(RUNTIME/'owner-zp.bin').read_bytes();reader=(ins.KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 mp=Q/'device-operations/2609.json';s=None;borrowed=False
 r=dict(board='2609',passed=False,image_erases=15,journal_erases=1,total_erases=16,journal_appends=17,physical_resets=1,power_cuts=0,F_writes=0,extra_flash_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,SPI_writes=0,owner_RAM_restored=False,owner_ZP_restored=False,receipts={k:dict(path=str(v),sha256=c.sha(v)) for k,v in receipts.items()})
 def save():c.save(OUT/'completion.json',r)
 def mark(**kw):m=c.read(mp);m.update(kw);c.save(mp,m)
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context==t.MON:s.command('Q',(t.REC,))
  assert s.context==t.REC
 save()
 with t.serial_lease('2609-candidate3-final-owner-verification',timeout=30):
  ins.ins.window(120);m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending']
  assert not m['physical_reset_pending'] and not m['RTC_LED_owner_hold'] and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  assert m['current_journal_sequence']==1089 and m['current_valid_journal_records']==27
  assert [m['current_tracked_erase_counts'][n] for n in 'CDEF']==[80,49,49,31]
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.REC,t.MON),seconds=15)
    if s.context==t.REC:s.command('B',(t.MON,))
    prefix=s.dump(0x200,0x1ff+len(reader));livezp=s.dump(0,0xdf)
    mark(candidate3_closeout_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);live=s.client.read(b'M',0x6500);assert live[:len(reader)]==reader
    before=prefix+live[len(reader):]
    r.update(post_RTC_RAM_matches_original=before==ram,post_RTC_ZP_matches_original=livezp==zp,post_RTC_RAM_different_bytes=sum(a!=b for a,b in zip(before,ram)),post_RTC_ZP_different_bytes=sum(a!=b for a,b in zip(livezp,zp)))
   finally:
    try:
     if borrowed:rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    finally:
     if s:s.link.close();r['port_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(candidate3_closeout_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=not restored,final_prompt='REC>',last_candidate3_closeout=str(OUT/'completion.json'))
     save()
 r.update(passed=bool(r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']),sequence=1089,valid_journal_records=27,final_C_D_E_F_counts=[80,49,49,31],default='B',default_generation='00000010',bank_enables=0,entries=['8000']*4,RTC_readmitted=True,trim_steps=-14,control=0x80,package_sha256=c.sha(package),published_downloads_unchanged=True,other_boards_accessed=[],firmware_builds=0,CPU_simulations=0)
 save();assert r['passed'];print('PASS2609 Candidate3 closed:16 erases/17 appends/1 reset; F golden; owner restored; RTC readmitted; REC>;COM8 free',flush=True)

if __name__=='__main__':run()
