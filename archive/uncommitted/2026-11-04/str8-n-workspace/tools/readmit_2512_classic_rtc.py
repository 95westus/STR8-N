"""Re-admit only changed 2512 MON gB TIME; retain baseline/history/cadence."""
import json,hashlib
from pathlib import Path
import rtc_mon_ui1_gb_2512 as n
c=n.c;ROOT=c.ROOT;BASE=ROOT/'output/qualification/2512-classic-workflow-20261030-r1';OUT=BASE/'RTC-continuity'
assert c.read(BASE/'installation/report.json')['passed']
state=c.read(c.STATE);before=dict(baselines=state['baselines'],interval_hours=state['interval_hours'],active=state['active']);points_path=Path(state['root'])/'points.json';points=c.read(points_path);old_points=list(points)
r=n.collect(OUT/'2512');item=dict(report=str(OUT/'2512/report.json'),sha256=c.sha(OUT/'2512/report.json'));point=n.audit_board(item,state)
assert not any(x['board']==point['board'] and x['time']==point['time'] for x in points);points.append(point);c.save(points_path,points)
assert c.read(points_path)[:-1]==old_points
m=c.read(n.MARK);state['board_admission']['2512']={k:m.get(k) for k in state['board_admission']['2512']}
state['base1_profile'].update(native_ui1_gb=True,profile=n.PROFILE,qualification_report=item['report'],qualification_report_sha256=item['sha256'],qualification='MON gB native TIME exact trace/NIST passed; existing baseline, trim, schedule and points retained')
state['dependencies']['tools/rtc_mon_ui1_gb_2512.py']=c.sha(ROOT/'tools/rtc_mon_ui1_gb_2512.py')
assert dict(baselines=state['baselines'],interval_hours=state['interval_hours'],active=state['active'])==before
c.save(c.STATE,state)
c.save(OUT/'audit.json',dict(passed=True,one_new_2512_point=True,prior_points_unchanged=True,baseline_unchanged=True,cadence_unchanged=True,RTC_SET=False,trim_written=False,PF_ACK=False,other_boards_accessed=False,report=item['report'],sha256=item['sha256']))
m.update(RTC_UI1_readmission_passed=True,RTC_UI1_readmission_pending=False,RTC_UI1_readmission=item['report']);c.save(n.MARK,m)
print('PASS 2512 RTC/NTP continuity; prior points/baseline/cadence retained; no other board access',flush=True)
