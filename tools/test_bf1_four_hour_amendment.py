"""Offline receipt-gate regression for the owner's shortened existing soak."""
import argparse,json,tempfile
from pathlib import Path
from datetime import datetime,timezone
import check_bf1_acceptance as c
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();checks=[]
    with tempfile.TemporaryDirectory(dir=c.ROOT/'tmp') as temp:
        root=Path(temp);run=root/'run';run.mkdir();(root/'tools').mkdir();real=c.ROOT;c.ROOT=root
        for name in ('run_bf1_2609_soak.py','bf1_2609_readonly.py','soak_led_patterns.py'):(root/'tools'/name).write_bytes((real/'tools'/name).read_bytes())
        baseline=root/'baseline';baseline.write_bytes(b'original immutable baseline');hardware=root/'hardware';hardware.write_text('{}');original=run/'application-ram-original.bin';original.write_bytes(bytes(25344));Path(str(run)+'.stderr.log').write_text('')
        groups=['unit'+str(i) for i in range(34)];start=100000.;iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        mode=dict(emulation_mode_before_probe=True,dbr=0,pbr=0,direct_page=0,entry_decimal_clear=True,entry_irq_disabled=True)
        for n in range(34):
            d=run/f'{n:06d}-{groups[n]}';d.mkdir();(d/'report.json').write_text(json.dumps(dict(passed=True,cpu_mode_before=mode,cpu_mode_after=mode,finished=start+(n+1)*14410/34)))
        state=dict(board='2609',state='stopped-by-request',pid=1,baseline_index=str(baseline),baseline_sha256=c.sha(baseline),runner_sha256=c.sha(root/'tools/run_bf1_2609_soak.py'),adapter_sha256=c.sha(root/'tools/bf1_2609_readonly.py'),led_patterns_sha256=c.sha(root/'tools/soak_led_patterns.py'),hardware_report=str(hardware),hardware_report_sha256=c.sha(hardware),passed_units=34,groups=groups,started_utc=iso(start),duration_started_utc=iso(start),finished_utc=iso(start+14410),application_ram_restored=True)
        receipt=dict(owner_authorized=True,board='2609',worker_pid=1,total_hours=4,deadline_unix=start+14400,requested_utc=iso(start+14400))
        restore=dict(needed=False,verified=True,sha256=c.sha(original));rule=dict(run=str(run),minimum_monitored_hours=4,minimum_complete_cycles=1,owner_duration_amendment=True,safe_stop_receipt='four-hour-stop-request.json')
        def check(name,change=None,expect='passed'):
            s=dict(state);r=dict(receipt);z=dict(restore);rr=dict(rule)
            if change:change(s,r,z,rr)
            for path,data in [('status.json',s),('four-hour-stop-request.json',r),('restore-needed.json',z)]:(run/path).write_text(json.dumps(data))
            try:result=c.audit_soak('2609',rr,start+14500)['status']
            except AssertionError:result='refused'
            assert result==expect,(name,result);checks.append(dict(name=name,passed=True,outcome=result))
        check('Authorized four-hour safe boundary and restoration')
        check('No matching policy amendment',lambda s,r,z,rr:rr.update(owner_duration_amendment=False),'refused')
        check('Unapproved receipt',lambda s,r,z,rr:r.update(owner_authorized=False),'refused')
        check('Wrong worker receipt',lambda s,r,z,rr:r.update(worker_pid=2),'refused')
        check('Early STOP receipt',lambda s,r,z,rr:r.update(requested_utc=iso(start+14399)),'refused')
        check('Wrong total deadline',lambda s,r,z,rr:r.update(deadline_unix=start+14000),'refused')
        check('Pending RAM restoration',lambda s,r,z,rr:z.update(needed=True),'refused')
        check('Failed RAM verification',lambda s,r,z,rr:z.update(verified=False),'refused')
        c.ROOT=real
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks),indent=2)+'\n');print('PASS',len(checks),'four-hour amendment receipt checks')
if __name__=='__main__':main()
