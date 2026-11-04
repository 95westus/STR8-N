"""2609-only g10 RTC readmission; retain old instruments and all baselines."""
import json,time
from datetime import datetime
from pathlib import Path
import install_2609_candidate3 as ins
import rtc_drift_campaign as c
from serial_test_coordination import drift_pending
t=ins.t;Q=ins.Q
OUT=Q/'2609-candidate3-RTC-readmission-20261102-r1'
RESET=Q/'2609-candidate3-reset-20261102-r1/report.json'
FILES=('rtc_mon_ui1_g10_2609.py','rtc_led_collect_g10_2609.py','rtc_led_dispatch_g10_2609.py','rtc_led_mode_g10_2609.py','rtc_led_collect_g10_2609_r2.py')

def await_drift():
 while True:
  due=c.read(Q/'rtc-hourly-controller-last.json').get('next_due')
  overdue=bool(due and datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()<=time.time())
  if not drift_pending() and not overdue:return
  time.sleep(1)

def run(resume=False):
 global OUT
 first=OUT
 if resume:
  assert c.read(Q/'2609-candidate3-LED-owner-restoration-20261102-r1/report.json')['passed']
  assert c.read(first/'native-TIME/report.json')['passed']
  OUT=Q/'2609-candidate3-RTC-readmission-20261102-r2'
 ins.approved();assert c.read(RESET)['passed']
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 for name in FILES[:2]:assert c.sha(t.ROOT/'tools'/name)==c.sha(ins.SCOPE/'RTC-candidates'/name)
 r=dict(board='2609',passed=False,RTC_SET=0,trim_writes=0,PF_ACK=0,flash_writes=0,qualified=[])
 def save():c.save(OUT/'report.json',r)
 save();await_drift()
 with t.serial_lease('2609-g10-RTC-host-registration',timeout=60):
  source=t.ROOT/'tools/rtc_drift_campaign.py';text=source.read_text(encoding='utf-8');(OUT/'rtc_drift_campaign-before.py').write_bytes(source.read_bytes())
  if resume:
   state=c.read(c.STATE);assert state['board_admission']['2609']['monitor_generation']=='00000010'
   c.save(OUT/'campaign-before.json',c.read(first/'campaign-before.json'))
   for name in FILES:state['dependencies']['tools/'+name]=c.sha(t.ROOT/'tools'/name)
   c.save(c.STATE,state)
   r['prior_attempt']=str(first/'report.json');r['host_audit_correction']='Compare PIA CRA0-5; record read-cleared IRQ flags6/7 separately. Original failed report retained; unchanged sampler binary.';save()
  else:
   register_original(source,text)
 import rtc_mon_ui1_g10_2609 as native
 import rtc_led_collect_g10_2609_r2 as led
 assert led.cra_controls_match(0xB4,0x34) and not led.cra_controls_match(0x34,0x30)
 if resume:
  ni=dict(board='2609',report=str(first/'native-TIME/report.json'),sha256=c.sha(first/'native-TIME/report.json'),capture_profile=native.PROFILE)
 else:
  await_drift();n=native.collect('2609',OUT/'native-TIME');assert n['passed']
  ni=dict(board='2609',report=str(OUT/'native-TIME/report.json'),sha256=c.sha(OUT/'native-TIME/report.json'),capture_profile=native.PROFILE)
 np=native.audit_board(ni,c.read(c.STATE));r['qualified'].append('nine strict native TIME/NIST readings');save();print('PASS2609 native TIME/NIST, fresh trim/control',flush=True)
 await_drift();l=led.collect('2609',OUT/'LED-seconds');assert l['passed']
 li=dict(board='2609',report=str(OUT/'LED-seconds/report.json'),sha256=c.sha(OUT/'LED-seconds/report.json'),capture_profile=led.PROFILE,RAM_restored=True)
 lp=led.audit_board(li,c.read(c.STATE));assert np['trim']==lp['trim']==-14 and np['control']==lp['control']==0x80
 r['qualified'].append('unchanged794-byte62-second LED sampler, RAM/LED and PIA control bits restored; IRQ flags reported separately');save();await_drift()
 with t.serial_lease('2609-g10-RTC-final-admission',timeout=60):
  state=c.read(c.STATE);before=c.read(OUT/'campaign-before.json');assert state['baselines']==before['baselines'] and state['segment_boundaries']==before['segment_boundaries']
  c.save(OUT/'native-audit.json',dict(passed=True,item=ni,point=np));old=state['base1_profiles']['2609'].copy();profile=old.copy()
  profile.update(qualified=True,profile=native.PROFILE,qualification_report=ni['report'],qualification_report_sha256=ni['sha256'],qualification_audit=str(OUT/'native-audit.json'),qualification_audit_sha256=c.sha(OUT/'native-audit.json'),qualification='Installed Candidate3 MON g10 816 emulation; nine native TIME/NIST readings and unchanged62-second LED sampler, trim -14/control80 retained')
  state['base1_profiles']['2609']=profile
  state.setdefault('firmware_profile_events',[]).append(dict(board='2609',UTC=c.NOW(),reason='Approved Candidate3 upgrade; native TIME and unchanged LED sampler qualified; no RTC time/trim/PF write or baseline reset',report=str(OUT/'report.json'),old_profile=old))
  state.setdefault('CPU_reset_events',[]).append(dict(board='2609',recorded_UTC=c.NOW(),reason='Captured Traditional g10 saved-B startup and cold SRAM without PREP',report=str(RESET),power_cycle=False));c.save(c.STATE,state)
  c.save(Q/'rtc-led-g10-2609.json',dict(qualified=True,board='2609',monitor_generation='00000010',driver_sha256=c.sha(led.__file__),qualification=li))
  mp=Q/'device-operations/2609.json';m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
  m.update(RTC_LED_owner_hold=False,RTC_LED_owner_hold_reason=None,RTC_collection_pending_monitor_recovery=False,candidate3_RTC_readmission_pending=False,last_candidate3_RTC_readmission=str(OUT/'report.json'),block_snapshot=False);c.save(mp,m)
 r.update(passed=True,native_qualification=ni,LED_qualification=li,trim_steps=-14,control=0x80,baselines_unchanged=True,owner_RAM_LEDs_restored=True);save()
 print('PASS2609 Candidate3 RTC readmitted; native TIME and LED sampler; baselines unchanged',flush=True)

def register_original(source,text):
  old="from rtc_led_dispatch_g10 import audit_board as led_audit";assert text.count(old)==1;text=text.replace(old,"from rtc_led_dispatch_g10_2609 import audit_board as led_audit")
  old="from rtc_led_mode_g10 import enabled as led_enabled, campaign as led_campaign";assert text.count(old)==1;text=text.replace(old,"from rtc_led_mode_g10_2609 import enabled as led_enabled, campaign as led_campaign")
  old="            if selected_profile.get('profile')=='MON-UI1-G10-TIME-TRIM':"
  new="            if selected_profile.get('profile')=='MON-UI1-G10-2609-TIME-TRIM':\n                from rtc_mon_ui1_g10_2609 import collect as g10_2609_collect,PROFILE as base1_capture_profile\n                base1_collect=lambda folder:g10_2609_collect(base1_board,folder)\n            elif selected_profile.get('profile')=='MON-UI1-G10-TIME-TRIM':"
  assert text.count(old)==1;text=text.replace(old,new)
  old="            if item.get('capture_profile')=='MON-UI1-G10-TIME-TRIM':"
  new="            if item.get('capture_profile')=='MON-UI1-G10-2609-TIME-TRIM':\n                from rtc_mon_ui1_g10_2609 import audit_board as native_audit\n                p=native_audit(item,state)\n                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))\n            elif item.get('capture_profile')=='MON-UI1-G10-TIME-TRIM':"
  assert text.count(old)==1;text=text.replace(old,new);compile(text,str(source),'exec')
  state=c.read(c.STATE);c.save(OUT/'campaign-before.json',state)
  assert state['board_admission']['2609']['monitor_generation']=='0000000D'
  source.write_text(text,encoding='utf-8');state['board_admission']['2609']['monitor_generation']='00000010'
  for name in FILES:state['dependencies']['tools/'+name]=c.sha(t.ROOT/'tools'/name)
  if 'tools/rtc_drift_campaign.py' in state['dependencies']:state['dependencies']['tools/rtc_drift_campaign.py']=c.sha(source)
  c.save(c.STATE,state)
if __name__=='__main__':
 import sys
 run('--resume-pia-audit' in sys.argv)
