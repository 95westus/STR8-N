"""Qualify/admit one installed gC native TIME reader without resetting history."""
import argparse,json
from pathlib import Path
import rtc_mon_ui1_gc as g
c=g.c;b=g.b
ROOT=c.ROOT;BASE=ROOT/'output/qualification/STATUS-install-20261031-r1'
def run(board):
    g.inputs(board)
    folder=BASE/board/'RTC-continuity'
    before=c.read(c.STATE);saved_baselines=json.dumps(before['baselines'],sort_keys=True)
    r=g.collect(board,folder)
    item=dict(board=board,report=str(folder/'report.json'),sha256=c.sha(folder/'report.json'))
    point=g.audit_board(item,before)
    assert not point['PF_latched'],'PF latched; do not acknowledge or register silently'
    audit=dict(passed=True,board=board,point=point,profile=g.PROFILE,
               driver_sha256=c.sha(g.__file__),baseline_reset=False,cadence_changed=False)
    c.save(folder/'admission-audit.json',audit)
    with b.serial_lease('drift',timeout=30):
        state=c.read(c.STATE)
        assert json.dumps(state['baselines'],sort_keys=True)==saved_baselines
        points=Path(state['root'])/'points.json';events=Path(state['root'])/'events.json'
        hashes=(c.sha(points),c.sha(events));interval=state['interval_hours']
        c.save(folder/'campaign-state-before.json',state)
        profile=state['base1_profile'] if board=='2512' else state['base1_profiles'][board]
        profile.update(qualified=True,profile=g.PROFILE,native_status_gc=True,
            qualification='Installed gC native TIME exact trace/NIST passed; original baseline/history/cadence retained',
            qualification_report=str(folder/'report.json'),qualification_report_sha256=item['sha256'],
            qualification_audit=str(folder/'admission-audit.json'),qualification_audit_sha256=c.sha(folder/'admission-audit.json'))
        state['dependencies']['tools/rtc_mon_ui1_gc.py']=c.sha(g.__file__)
        marker=c.read(c.Q/f'device-operations/{board}.json')
        state['board_admission'][board]={key:marker.get(key) for key in state['board_admission'][board]}
        c.save(c.STATE,state)
        after=c.read(c.STATE)
        assert json.dumps(after['baselines'],sort_keys=True)==saved_baselines and after['interval_hours']==interval
        assert (c.sha(points),c.sha(events))==hashes
    c.save(folder/'registration.json',dict(passed=True,board=board,profile=g.PROFILE,
        previous_points_sha256=hashes[0],previous_events_sha256=hashes[1],baseline_unchanged=True,
        interval_hours=interval,clock_SET=0,PF_ACK=0,RAM_uploaded=False,ports_released=True))
    print('PASS',board,'gC native TIME/NIST admitted; baseline/history/cadence unchanged',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True);a=p.parse_args();run(a.board)
