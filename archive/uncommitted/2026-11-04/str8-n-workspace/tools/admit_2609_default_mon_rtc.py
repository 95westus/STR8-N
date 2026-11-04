"""Admit the new MON/REC-aware host reader without changing RTC history."""
import hashlib
import json
import rtc_mon_ui1_gc_auto2609 as g

c=g.c;b=g.b
ROOT=c.ROOT
BASE=ROOT/'output/qualification/2609-default-MON-B-20261031-r1'


def run():
    boot=c.read(BASE/'report.json');assert boot['passed']
    before=c.read(c.STATE)
    baseline=json.dumps(before['baselines'],sort_keys=True)
    interval=before['interval_hours']
    points=__import__('pathlib').Path(before['root'])/'points.json'
    events=points.with_name('events.json')
    prior_hashes=(c.sha(points),c.sha(events))
    folder=BASE/'RTC-prompt-qualification-r2'
    r=g.collect('2609',folder,qualification=True)
    item=dict(board='2609',report=str(folder/'report.json'),sha256=c.sha(folder/'report.json'))
    point=g.audit_board(item,before)
    assert r['original_prompt']=='B3>' and r['monitor_slot']=='B'
    # The known latched outage is evidence, not a failed wire-protocol test.
    # Never clear it or reset the baseline to admit a new host prompt path.
    audit=dict(passed=True,point=point,profile=g.PROFILE,driver_sha256=c.sha(g.__file__),
        PF_latched=point['PF_latched'],PF_ACK=False,continuity_claimed=False,
        baseline_changed=False,cadence_changed=False)
    c.save(folder/'admission-audit.json',audit)
    with b.serial_lease('drift',timeout=30):
        state=c.read(c.STATE)
        assert json.dumps(state['baselines'],sort_keys=True)==baseline
        assert state['interval_hours']==interval
        assert (c.sha(points),c.sha(events))==prior_hashes
        c.save(folder/'campaign-state-before.json',state)
        profile=state['base1_profiles']['2609']
        profile.update(profile=g.PROFILE,qualified=True,auto_prompt=True,
            qualification='Native gC TIME from MON B; original prompt retained. PF latch preserved, no continuity claim.',
            qualification_report=str(folder/'report.json'),qualification_report_sha256=item['sha256'],
            qualification_audit=str(folder/'admission-audit.json'),qualification_audit_sha256=c.sha(folder/'admission-audit.json'))
        state['dependencies']['tools/rtc_mon_ui1_gc_auto2609.py']=c.sha(g.__file__)
        path=c.Q/'device-operations/2609.json';marker=c.read(path)
        marker.update(rtc_prompt_adapter_worker_active=False,current_sampling_profile=g.PROFILE,
            last_default_MON_RTC_admission=str(folder/'registration.json'))
        assert marker['final_prompt']=='B3>'
        for key,value in state['board_admission']['2609'].items():assert marker.get(key)==value
        c.save(c.STATE,state);c.save(path,marker)
        assert json.dumps(c.read(c.STATE)['baselines'],sort_keys=True)==baseline
        assert (c.sha(points),c.sha(events))==prior_hashes
    c.save(folder/'registration.json',dict(passed=True,board='2609',profile=g.PROFILE,
        baseline_unchanged=True,interval_hours=interval,prior_points_sha256=prior_hashes[0],
        prior_events_sha256=prior_hashes[1],PF_latch_retained=point['PF_latched'],
        PF_ACK=False,RAM_uploaded=False,port_released=True,final_prompt='B3>'))
    print('PASS 2609 MON-prompt TIME/NIST reader admitted; baseline/history/cadence retained',flush=True)


if __name__=='__main__':run()
