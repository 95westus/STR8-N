"""Qualify/register the two gD native TIME readers, retaining campaign history."""
import json
from pathlib import Path
import rtc_mon_ui1_gd_trim as g

c=g.c;b=g.b
OUT=c.Q/'MON-trim-RTC-admission-20261031-r1'


def run():
    started=c.NOW()
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    initial=c.read(c.STATE)
    snapshot=json.dumps(initial['baselines'],sort_keys=True)
    interval=initial['interval_hours'];items=[];points={}
    for board in ('2512','2609'):
        installation=c.read(c.Q/f'{board}-MON-trim-installed-20261031-r1/report.json')
        assert installation['passed'] and installation['owner_RAM_restored'] and installation['owner_ZP_restored']
        folder=OUT/board;r=g.collect(board,folder)
        item=dict(board=board,report=str(folder/'report.json'),sha256=c.sha(folder/'report.json'),
                  offset=r['rtc_minus_reference_interval_s'],trim=r['trim_steps'],
                  RAM_restored=r['application_ram_restored'],capture_profile=g.PROFILE)
        point=g.audit_board(item,initial)
        assert point['trim_verified'] and point['control_verified']
        items.append(item);points[board]=point
        print('PASS '+board+' live NTP/TIME trim '+str(point['trim'])+' control '+f"{point['control']:02X}",flush=True)
    summary=dict(passed=True,started_utc=started,finished_utc=c.NOW(),boards=items,
                 failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
    c.save(OUT/'summary.json',summary)
    with b.serial_lease('drift',timeout=30):
        state=c.read(c.STATE)
        assert json.dumps(state['baselines'],sort_keys=True)==snapshot and state['interval_hours']==interval
        c.save(OUT/'campaign-state-before.json',state)
        pp=Path(state['root'])/'points.json';ep=Path(state['root'])/'events.json'
        previous=c.read(pp);old_points=json.loads(json.dumps(previous));events_sha=c.sha(ep)
        for point in points.values():
            assert not any(p['board']==point['board'] and p['time']==point['time'] for p in previous)
            previous.append(point)
        c.save(pp,previous)
        assert c.read(pp)[:len(old_points)]==old_points and c.sha(ep)==events_sha
        for board in ('2512','2609'):
            marker=c.read(c.Q/f'device-operations/{board}.json')
            profile=state['base1_profile'] if board=='2512' else state['base1_profiles'][board]
            profile.update(qualified=True,profile=g.PROFILE,native_time_trim=True,
                qualification='Installed gD: nine native TIME/NIST samples include fresh control/trim; exact trace audited',
                qualification_report=items[0 if board=='2512' else 1]['report'],
                qualification_report_sha256=items[0 if board=='2512' else 1]['sha256'])
            state['board_admission'][board]={key:marker.get(key) for key in state['board_admission'][board]}
            marker.update(current_sampling_profile=g.PROFILE,RTC_UI1_readmission_pending=False,
                          last_RTC_native_trim_admission=str(OUT/board/'report.json'))
            c.save(c.Q/f'device-operations/{board}.json',marker)
        state['dependencies']['tools/rtc_mon_ui1_gd_trim.py']=c.sha(g.__file__)
        issues=[x for x in state.get('last_issues',[]) if x.get('board') not in points]
        issues += [dict(board=p['board'],error='Native TIME reports PF latched; no ACK sent') for p in points.values() if p['PF_latched']]
        state.update(last_attempt_utc=c.NOW(),last_summary=str(OUT/'summary.json'),last_issues=issues,last_new_PF_events=[])
        c.save(c.STATE,state)
        assert c.sha(ep)==events_sha and json.dumps(c.read(c.STATE)['baselines'],sort_keys=True)==snapshot
        c.save(OUT/'campaign-audit.json',dict(passed=not issues,issues=issues,new_PF_events=[],summary_sha256=c.sha(OUT/'summary.json')))
        rows=c.report(state)
        receipt=dict(passed=True,profile=g.PROFILE,boards=points,old_points_preserved=len(old_points),
                     events_sha256=events_sha,baseline_unchanged=True,interval_hours=interval,
                     RTC_SET=0,trim_writes=0,F_writes=0,RAM_uploaded=False,ports_released=True,
                     recommendations={board:rows[board]['recommendation'] for board in points})
        c.save(OUT/'final-receipt.json',receipt)
    print('PASS both gD live-trim readers registered; baseline/history/cadence retained',flush=True)


if __name__=='__main__':run()
