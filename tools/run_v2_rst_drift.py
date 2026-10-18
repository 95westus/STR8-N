"""Fresh post-trim read-only NTP baseline, then hourly leased snapshots."""
import argparse,ctypes,datetime,json,os,sys,time,traceback
from pathlib import Path
import rtc_utc_baseline as rtc
import upgrade_v2_fleet as fleet
from serial_test_coordination import serial_lease
from run_v2_rst_soak import BOARDS,END,END_LOCAL,save,active_boards

def capture(root,baseline=False):
    now=datetime.datetime.now(datetime.timezone.utc);stamp=now.strftime('%Y%m%d-%H%M%SZ')
    out=root/'drift'/('baseline' if baseline else 'snapshot-'+stamp);out.mkdir(parents=True,exist_ok=False)
    results=[]
    with serial_lease('drift',timeout=600):
        for board in active_boards(root):
            try:
                assert time.time()<END-30,'Sampling deadline reached'
                pending=[p for p in (root/board).glob('*/restore-state.json') if json.loads(p.read_text()).get('needs_restore')]
                assert not pending,'Scratch recovery pending; do not disturb board'
                sys.argv=['rtc_utc_baseline','--board',board,'--port',fleet.port(board),'--out',str(out/board)]
                if not baseline:sys.argv+=['--baseline',str(root/'drift/baseline'/board/'report.json')]
                rtc.main();r=json.loads((out/board/'report.json').read_text());assert r['passed'] and not r['trim_changed']
                result=dict(board=board,passed=True,rtc_minus_ntp_interval_s=r['rtc_minus_reference_interval_s'],
                    reference_utc=r['baseline_reference_utc'],reference_uncertainty_s=r['reference_uncertainty_s'],
                    clock_set=False,trim_changed=False)
                for key in ('elapsed_seconds','drift_seconds_interval','drift_ppm_interval','drift_seconds_per_day_interval'):
                    if key in r:result[key]=r[key]
                results.append(result)
            except Exception:
                results.append(dict(board=board,passed=False,error=traceback.format_exc()));traceback.print_exc()
    report=dict(passed=all(r['passed'] for r in results),baseline=baseline,boards=results,started_utc=now.isoformat(),
        finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),finished_unix=time.time(),
        reference='live time.nist.gov NTP; installed calibrated trims retained; no clock SET')
    save(out/'index.json',report)
    if baseline:assert report['passed'],'New baseline incomplete; do not start soak'
    return out,report

def run(root):
    original=json.loads((root/'drift/baseline/index.json').read_text());assert original['passed']
    anchor=original['finished_unix']
    completed=[(p,json.loads(p.read_text())) for p in (root/'drift').glob('snapshot-*/index.json')]
    slots=[int((datetime.datetime.fromisoformat(r['started_utc']).timestamp()-anchor)//3600) for _,r in completed]
    previous=max(slots,default=0)
    number=max(previous+1,int((time.time()-anchor)//3600))
    status=dict(state='running',pid=os.getpid(),baseline=str(root/'drift/baseline/index.json'),snapshots=len(completed),end_local=END_LOCAL,
        active_boards=list(active_boards(root)),missed_scheduled_slots=list(range(previous+1,number)))
    assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        while True:
            due=anchor+number*3600
            if due>=END-180:break
            status.update(next_due_utc=datetime.datetime.fromtimestamp(due,datetime.timezone.utc).isoformat(),updated=time.time())
            save(root/'drift/status.json',status)
            while time.time()<due and not (root/'STOP').exists():time.sleep(min(5,due-time.time()))
            if (root/'STOP').exists():break
            folder,result=capture(root);status.update(snapshots=status['snapshots']+1,scheduled_slot=number,last_snapshot=str(folder),last_passed=result['passed'],updated=time.time())
            save(root/'drift/status.json',status);print('HOURLY SNAPSHOT',number,result['passed'],str(folder),flush=True);number+=1
        while time.time()<END and not (root/'STOP').exists():time.sleep(min(5,END-time.time()))
        status.update(state='completed',ports_released=True,updated=time.time());save(root/'drift/status.json',status)
    except Exception:
        status.update(state='stopped-on-failure',error=traceback.format_exc(),updated=time.time());save(root/'drift/status.json',status);raise
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('baseline','run'));p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    if a.stage=='baseline':capture(a.root.resolve(),True)
    else:run(a.root.resolve())
