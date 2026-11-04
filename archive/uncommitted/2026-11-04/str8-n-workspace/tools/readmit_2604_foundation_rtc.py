"""2604-only g10 RTC readmission; preserve campaign history and all other routing."""
import json,sys,time
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
from installer.common import save
from inventory_boards_readonly import durable
from install_2604_foundation_profile import Session,t,SCOPE,CONVERSION,MP
from serial_test_coordination import serial_lease,drift_pending

OUT=c.Q/'2604-foundation-RTC-readmission-20261102-r1'
RESET=c.Q/'2604-foundation-default-reset-20261102-r1/report.json'
FILES=('rtc_mon_ui1_g10_2604_trim.py','rtc_led_collect_g10_2604_r2.py','rtc_led_dispatch_g10_2604.py','rtc_led_mode_g10_2604.py')


def await_drift():
    while True:
        due=c.read(c.Q/'rtc-hourly-controller-last.json')['next_due']
        overdue=datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()<=time.time()
        if not drift_pending() and not overdue:return
        time.sleep(1)


def run(resume=False):
    global OUT
    first=OUT
    if resume:
        assert c.read(first/'native-TIME/report.json')['passed']
        assert c.read(first/'LED-seconds/report.json')['passed'] and c.read(first/'LED-seconds/report.json')['port_released']
        OUT=c.Q/'2604-foundation-RTC-readmission-20261102-r2'
    assert c.read(RESET)['passed']
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
    r=dict(board='2604',passed=False,flash_writes=0,journal_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,SPI_writes=0,qualified=[])
    def checkpoint(**kw):r.update(kw);save(OUT/'report.json',r)
    checkpoint();await_drift()
    if not resume:
      with serial_lease('2604-Foundation-RTC-host-profile-registration',timeout=60):
        state=c.read(c.STATE);save(OUT/'campaign-before.json',state)
        # Only new2604 collector modules are copied; existing readers stay exact.
        for name in FILES[:2]:
            destination=ROOT/'tools'/name;assert not destination.exists()
            durable(destination,(SCOPE/'RTC-candidates'/name).read_bytes())
        source=ROOT/'tools/rtc_drift_campaign.py';text=source.read_text(encoding='utf-8')
        durable(OUT/'rtc_drift_campaign-before.py',source.read_bytes())
        old='from rtc_led_dispatch_g10_2609 import audit_board as led_audit'
        assert text.count(old)==1;text=text.replace(old,'from rtc_led_dispatch_g10_2604 import audit_board as led_audit')
        old='from rtc_led_mode_g10_2609 import enabled as led_enabled, campaign as led_campaign'
        assert text.count(old)==1;text=text.replace(old,'from rtc_led_mode_g10_2604 import enabled as led_enabled, campaign as led_campaign')
        old="            if selected_profile.get('profile')=='MON-UI1-G10-2609-TIME-TRIM':"
        new="            if selected_profile.get('profile')=='MON-UI1-G10-2604-TIME-TRIM':\n                from rtc_mon_ui1_g10_2604_trim import collect as g10_2604_collect,PROFILE as base1_capture_profile\n                base1_collect=lambda folder:g10_2604_collect(base1_board,folder)\n            elif selected_profile.get('profile')=='MON-UI1-G10-2609-TIME-TRIM':"
        assert text.count(old)==1;text=text.replace(old,new)
        old="            if item.get('capture_profile')=='MON-UI1-G10-2609-TIME-TRIM':"
        new="            if item.get('capture_profile')=='MON-UI1-G10-2604-TIME-TRIM':\n                from rtc_mon_ui1_g10_2604_trim import audit_board as native_audit\n                p=native_audit(item,state)\n                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))\n            elif item.get('capture_profile')=='MON-UI1-G10-2609-TIME-TRIM':"
        assert text.count(old)==1;text=text.replace(old,new);compile(text,str(source),'exec')
        marker=c.read(MP)
        assert marker['monitor_generation']=='00000010' and marker['firmware']=='STR8N-F 0.3.0 BASE1 PR05'
        state['board_admission']['2604']={k:marker.get(k) for k in state['board_admission']['2604']}
        state.setdefault('base1_profiles',{})['2604']=dict(qualified=False,profile='MON-UI1-G10-2604-TIME-TRIM')
        for name in FILES:state['dependencies']['tools/'+name]=c.sha(ROOT/'tools'/name)
        source.write_text(text,encoding='utf-8');state['dependencies']['tools/rtc_drift_campaign.py']=c.sha(source)
        save(c.Q/'rtc-led-g10-2604.json',dict(qualified=False,board='2604',monitor_generation='00000010'))
        c.save(c.STATE,state)
    if resume:
        durable(OUT/'campaign-before.json',(first/'campaign-before.json').read_bytes())
        r['prior_attempt']=str(first/'report.json')
        r['host_gate_correction']='Compare2604 against its preserved control00; never inherit another board control80. Existing successful samples reused without hardware replay.'
    import rtc_mon_ui1_g10_2604_trim as native
    import rtc_led_collect_g10_2604_r2 as led
    if not resume:
        await_drift();n=native.collect('2604',OUT/'native-TIME');assert n['passed']
    samples=first if resume else OUT
    ni=dict(board='2604',report=str(samples/'native-TIME/report.json'),sha256=c.sha(samples/'native-TIME/report.json'),capture_profile=native.PROFILE)
    np=native.audit_board(ni,c.read(c.STATE));r['qualified'].append('nine strict native TIME/NIST readings');checkpoint()
    print('PASS2604 native TIME/NIST and current trim/control',flush=True)
    if not resume:
        await_drift();l=led.collect('2604',OUT/'LED-seconds');assert l['passed']
    li=dict(board='2604',report=str(samples/'LED-seconds/report.json'),sha256=c.sha(samples/'LED-seconds/report.json'),capture_profile=led.PROFILE,RAM_restored=True)
    lp=led.audit_board(li,c.read(c.STATE))
    original=c.Q/'rtc-drift-3hour-20261028/captures/20261102/batch-210123Z/2604/report.json'
    old=c.read(original);assert old['passed'] and old['board']=='2604' and old['finished_utc']<c.read(SCOPE/'approval.json')['approved_utc']
    durable(OUT/'preconversion-RTC-preservation-reference.json',original.read_bytes())
    assert np['trim']==lp['trim']==old['trim_steps']==-12
    assert np['control']==lp['control']==old['control_register']==0
    r['qualified'].append('unchanged794-byte62-second sampler;RAM/LED/CRA controls restored');checkpoint()
    await_drift()
    with serial_lease('2604-Foundation-final-owner-restoration-and-RTC-admission',timeout=60):
        ram=(CONVERSION/'owner-ram.bin').read_bytes();zp=(CONVERSION/'owner-zp.bin').read_bytes();s=None
        with (OUT/'owner-restoration.jsonl').open('x') as log:
            try:
                s=Session(OUT,log);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15)
                if s.context==t.MON:s.command('Q',(t.REC,))
                reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();s.service(reader)
                assert t.sha(s.client.flash(3))==c.read(SCOPE/'plan.json')['expected_bank_sha256']['B3']
                r.update(s.client.restore_owner(ram,zp));assert r['owner_RAM_restored'] and r['owner_ZP_restored']
            finally:
                if s:s.link.close();r['port_released']=True
        state=c.read(c.STATE);before=c.read(OUT/'campaign-before.json')
        assert state['baselines']==before['baselines'] and state['segment_boundaries']==before['segment_boundaries']
        for board in ('2205','2512','2609'):assert state['board_admission'][board]==before['board_admission'][board]
        save(OUT/'native-audit.json',dict(passed=True,item=ni,point=np))
        state['base1_profiles']['2604']=dict(qualified=True,profile=native.PROFILE,qualification_report=ni['report'],
            qualification_report_sha256=ni['sha256'],qualification_audit=str(OUT/'native-audit.json'),qualification_audit_sha256=c.sha(OUT/'native-audit.json'),
            qualification='2604 Foundation/MONg10; native TIME/NIST and unchanged LED sampler; preserved trim-12/control00, no clock/PF write or baseline reset')
        state.setdefault('firmware_profile_events',[]).append(dict(board='2604',UTC=c.NOW(),reason='Approved27-erase rc1g34->Foundation/MONg10 migration; all originals archived; RTC readmitted unchanged',report=str(OUT/'report.json'),old_admission=before['board_admission']['2604']))
        state.setdefault('CPU_reset_events',[]).append(dict(board='2604',recorded_UTC=c.NOW(),reason='Approved migration recovery and g10 saved-B startup; no power cuts',report=str(RESET),power_cycle=False))
        c.save(c.STATE,state)
        save(c.Q/'rtc-led-g10-2604.json',dict(qualified=True,board='2604',monitor_generation='00000010',driver_sha256=c.sha(led.__file__),qualification=li))
        marker=c.read(MP);marker.update(block_snapshot=False,RTC_LED_owner_hold=False,RTC_LED_owner_hold_reason=None,
            RTC_collection_pending_monitor_recovery=False,foundation_RTC_readmission_pending=False,
            foundation_rollout_qualification_pending=False,foundation_rollout_complete=True,last_foundation_RTC_readmission=str(OUT/'report.json'),final_prompt='REC>')
        c.save(MP,marker)
    checkpoint(passed=True,native_qualification=ni,LED_qualification=li,trim_steps=-12,control=0,
        baselines_unchanged=True,other_boards_admission_unchanged=True,final_prompt='REC>')
    print('PASS2604 RTC readmitted;owner RAM/ZP exact;RTC time/trim/history and other instruments retained',flush=True)


if __name__=='__main__':run('--resume-preserved-control' in sys.argv)
