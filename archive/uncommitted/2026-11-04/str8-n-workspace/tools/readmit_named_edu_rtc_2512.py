"""Qualify versioned2512 gE readers; preserve old instruments and baselines."""
import json,sys
from pathlib import Path
import install_named_edu_2512 as ins
import rtc_drift_campaign as c

t=ins.t;Q=ins.Q;SCOPE=ins.SCOPE
OUT=Q/'2512-named-EDU-RTC-readmission-20261101-r1'

def run():
    p=ins.approved();ins.window(180)
    positive=Q/'2512-named-transfer-positive-20261101-r1/report.json';assert c.read(positive)['passed']
    resumed=OUT.exists()
    if resumed:
        assert not c.read(OUT/'report.json')['passed'] and not (OUT/'native-TIME-r2').exists()
        assert c.read(OUT/'native-TIME/report.json')['error'].startswith("AssertionError('No fresh")
        assert (OUT/'native-TIME/TIME-5.txt').read_bytes()==b'TIME\r\nRTCC error $04\r\nRTCC: --\r\nB3> '
        (OUT/'report-first-attempt.json').write_bytes((OUT/'report.json').read_bytes())
        (OUT/'driver-resume-as-executed.py').write_bytes(Path(__file__).read_bytes())
    else:
        OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    files=SCOPE/'RTC-candidates'
    if not resumed:
      with t.serial_lease('2512-gE-RTC-host-admission',timeout=30):
        assert c.sha(t.ROOT/'tools/rtc_drift_campaign.py')==p['RTC']['original_campaign_sha256']
        for n in ('rtc_led_collect_ge.py','rtc_mon_ui1_ge_trim.py','rtc_led_dispatch.py','rtc_led_mode_ge.py'):
            src=files/n;dst=t.ROOT/'tools'/n;assert c.sha(src)==p['RTC']['files'][n]
            assert not dst.exists();dst.write_bytes(src.read_bytes())
        campaign=files/'rtc_drift_campaign.candidate.py';assert c.sha(campaign)==p['RTC']['files'][campaign.name]
        (OUT/'rtc_drift_campaign-before.py').write_bytes((t.ROOT/'tools/rtc_drift_campaign.py').read_bytes())
        (t.ROOT/'tools/rtc_drift_campaign.py').write_bytes(campaign.read_bytes())
        state=c.read(c.STATE);c.save(OUT/'campaign-before.json',state)
        assert state['board_admission']['2512']['monitor_generation']=='0000000D'
        state['board_admission']['2512']['monitor_generation']='0000000E'
        for n in ('rtc_led_collect_ge.py','rtc_mon_ui1_ge_trim.py','rtc_led_dispatch.py','rtc_led_mode_ge.py'):
            state['dependencies']['tools/'+n]=c.sha(t.ROOT/'tools'/n)
        c.save(c.STATE,state)
    import rtc_mon_ui1_ge_trim as native
    import rtc_led_collect_ge as led
    r=dict(board='2512',passed=False,RTC_SET=0,trim_writes=0,PF_ACK=0,flash_writes=0,qualified=[])
    def save():c.save(OUT/'report.json',r)
    save()
    native_folder=OUT/('native-TIME-r2' if resumed else 'native-TIME')
    n=native.collect('2512',native_folder);assert n['passed']
    ni=dict(board='2512',report=str(native_folder/'report.json'),sha256=c.sha(native_folder/'report.json'),capture_profile=native.PROFILE)
    state=c.read(c.STATE);np=native.audit_board(ni,state);r['qualified'].append('nine native TIME/NIST fresh trim/control samples');save()
    l=led.collect('2512',OUT/'LED-seconds');assert l['passed']
    li=dict(board='2512',report=str(OUT/'LED-seconds/report.json'),sha256=c.sha(OUT/'LED-seconds/report.json'),capture_profile=led.PROFILE,RAM_restored=True)
    lp=led.audit_board(li,c.read(c.STATE));r['qualified'].append('unchanged794-byte LED agent;62 seconds;RAM/LED restored');save()
    assert np['trim']==lp['trim']==-12 and np['control']==lp['control']
    with t.serial_lease('2512-gE-RTC-host-admission-finalize',timeout=30):
        state=c.read(c.STATE)
        before=c.read(OUT/'campaign-before.json')
        assert state['baselines']==before['baselines'] and state['segment_boundaries']==before['segment_boundaries']
        old_profile=state['base1_profile'].copy();profile=old_profile.copy()
        profile.update(qualified=True,profile=native.PROFILE,qualification_report=ni['report'],qualification_report_sha256=ni['sha256'],qualification_audit=str(OUT/'native-audit.json'),qualification='Installed MON gE: nine TIME/NIST samples with fresh trim/control; preserved RTC settings')
        c.save(OUT/'native-audit.json',dict(passed=True,item=ni,point=np));profile['qualification_audit_sha256']=c.sha(OUT/'native-audit.json')
        state['base1_profile']=profile
        state.setdefault('firmware_profile_events',[]).append(dict(board='2512',UTC=c.NOW(),reason='MON gE/named-copy installation;native TIME and unchanged LED sampler requalified; no clock/trim/PF write or baseline reset',report=str(OUT/'report.json'),old_profile=old_profile))
        c.save(c.STATE,state)
        c.save(Q/'rtc-led-ge-2512.json',dict(qualified=True,board='2512',monitor_generation='0000000E',driver_sha256=c.sha(led.__file__),qualification=li))
        mp=Q/'device-operations/2512.json';m=c.read(mp);m.update(named_edu_RTC_admission_pending=False,status_admission_hold_reason=None,last_named_EDU_RTC_readmission=str(OUT/'report.json'));c.save(mp,m)
    r.update(passed=True,native_qualification=ni,LED_qualification=li,trim_steps=np['trim'],control=np['control'],owner_RAM_and_LEDs_restored=True,baselines_unchanged=True)
    save();print('PASS2512 gE RTC readmission; previous instruments/history/baselines retained',flush=True)

if __name__=='__main__':run()
