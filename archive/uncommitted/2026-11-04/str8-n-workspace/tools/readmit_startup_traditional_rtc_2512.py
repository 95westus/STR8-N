"""Approved2512 g10 RTC admission; keep prior readers, points and baselines."""
import json,time
from datetime import datetime
from pathlib import Path
import install_startup_traditional_2512 as ins
import rtc_drift_campaign as c
from serial_test_coordination import drift_pending
t=ins.t;Q=ins.Q;SCOPE=ins.SCOPE;OUT=Q/'2512-startup-traditional-RTC-readmission-20261101-r1'

def await_drift():
    # Let a due scheduled run finish before changing its host routing. This
    # also avoids handing a newly registered generation to an older campaign
    # process that was imported before it acquired the fleet lease.
    while True:
        last=c.read(Q/'rtc-hourly-controller-last.json');due=last.get('next_due')
        overdue=bool(due and datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()<=time.time())
        if not drift_pending() and not overdue:return
        time.sleep(1)

def run():
    p=ins.approved();reset=Q/'2512-startup-traditional-reset-20261101-r2/report.json';assert c.read(reset)['passed']
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());folder=SCOPE/'RTC-candidates'
    await_drift()
    with t.serial_lease('2512-g10-RTC-host-registration',timeout=60):
        assert c.sha(t.ROOT/'tools/rtc_drift_campaign.py')==p['RTC']['original_campaign_sha256']
        assert all(c.sha(t.ROOT/'tools'/n)==h for n,h in p['RTC']['original_readers_sha256'].items())
        for n in ('rtc_led_collect_g10.py','rtc_mon_ui1_g10_trim.py','rtc_led_dispatch_g10.py','rtc_led_mode_g10.py'):
            src=folder/n;dst=t.ROOT/'tools'/n;assert c.sha(src)==p['RTC']['files'][n] and not dst.exists();dst.write_bytes(src.read_bytes())
        candidate=folder/'rtc_drift_campaign.candidate.py';assert c.sha(candidate)==p['RTC']['files'][candidate.name]
        (OUT/'rtc_drift_campaign-before.py').write_bytes((t.ROOT/'tools/rtc_drift_campaign.py').read_bytes())
        tmp=t.ROOT/'tools/rtc_drift_campaign.gf-pending';tmp.write_bytes(candidate.read_bytes());tmp.replace(t.ROOT/'tools/rtc_drift_campaign.py')
        state=c.read(c.STATE);c.save(OUT/'campaign-before.json',state);assert state['board_admission']['2512']['monitor_generation']=='0000000F'
        state['board_admission']['2512']['monitor_generation']='00000010'
        for n in ('rtc_led_collect_g10.py','rtc_mon_ui1_g10_trim.py','rtc_led_dispatch_g10.py','rtc_led_mode_g10.py'):state['dependencies']['tools/'+n]=c.sha(t.ROOT/'tools'/n)
        c.save(c.STATE,state)
    import rtc_mon_ui1_g10_trim as native
    import rtc_led_collect_g10 as led
    r=dict(board='2512',passed=False,RTC_SET=0,trim_writes=0,PF_ACK=0,flash_writes=0,qualified=[])
    def save():c.save(OUT/'report.json',r)
    save();await_drift();n=native.collect('2512',OUT/'native-TIME');assert n['passed']
    ni=dict(board='2512',report=str(OUT/'native-TIME/report.json'),sha256=c.sha(OUT/'native-TIME/report.json'),capture_profile=native.PROFILE)
    np=native.audit_board(ni,c.read(c.STATE));r['qualified'].append('nine strict native TIME/NIST readings');save()
    await_drift();l=led.collect('2512',OUT/'LED-seconds');assert l['passed']
    li=dict(board='2512',report=str(OUT/'LED-seconds/report.json'),sha256=c.sha(OUT/'LED-seconds/report.json'),capture_profile=led.PROFILE,RAM_restored=True)
    lp=led.audit_board(li,c.read(c.STATE));assert np['trim']==lp['trim']==-12 and np['control']==lp['control']==0x80
    r['qualified'].append('unchanged794-byte LED sampler;62 seconds;RAM/LED restored');save();await_drift()
    with t.serial_lease('2512-g10-RTC-final-admission',timeout=60):
        state=c.read(c.STATE);before=c.read(OUT/'campaign-before.json');assert state['baselines']==before['baselines'] and state['segment_boundaries']==before['segment_boundaries']
        c.save(OUT/'native-audit.json',dict(passed=True,item=ni,point=np));old_profile=state['base1_profile'].copy();profile=old_profile.copy()
        profile.update(qualified=True,profile=native.PROFILE,qualification_report=ni['report'],qualification_report_sha256=ni['sha256'],qualification_audit=str(OUT/'native-audit.json'),qualification_audit_sha256=c.sha(OUT/'native-audit.json'),qualification='Installed MON g10 Traditional presentation; strict nine TIME/NIST samples, unchanged TIME/control/trim and guarded SRAM provider')
        state['base1_profile']=profile;state.setdefault('firmware_profile_events',[]).append(dict(board='2512',UTC=c.NOW(),reason='Approved three-sector g10 Traditional presentation; native TIME and unchanged LED sampler qualified; no clock/trim/PF write or baseline reset',report=str(OUT/'report.json'),old_profile=old_profile))
        state.setdefault('CPU_reset_events',[]).append(dict(board='2512',recorded_UTC=c.NOW(),reason='Captured g10 Traditional/default-B acceptance, saved EDU ON and SRAM capacity without PREP',report=str(reset),power_cycle=False));c.save(c.STATE,state)
        c.save(Q/'rtc-led-g10-2512.json',dict(qualified=True,board='2512',monitor_generation='00000010',driver_sha256=c.sha(led.__file__),qualification=li))
        mp=Q/'device-operations/2512.json';m=c.read(mp);assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
        m.update(block_snapshot=False,startup_qualification_pending=False,startup_RTC_admission_pending=False,
            status_admission_hold_reason=None,last_startup_RTC_readmission=str(OUT/'report.json'));c.save(mp,m)
    r.update(passed=True,native_qualification=ni,LED_qualification=li,trim_steps=-12,control=0x80,baselines_unchanged=True,owner_RAM_LEDs_restored=True);save();print('PASS2512 g10 native TIME and LED RTC admitted; baselines and old instruments retained',flush=True)

if __name__=='__main__':run()
