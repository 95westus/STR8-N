"""Owner-amended four-hour total duration; request existing worker's safe STOP only."""
import hashlib,json,time
from pathlib import Path
from datetime import datetime,timezone
from atomic_json import publish
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text())
def main():
    pointer=read(Q/'bf1-acceptance-policy-current.json');policy=Path(pointer['policy'])
    assert hashlib.sha256(policy.read_bytes()).hexdigest()==pointer['sha256']
    rule=read(policy)['soaks']['2609'];assert rule['minimum_monitored_hours']==4 and rule['owner_duration_amendment']
    run=Path(rule['run']);s=read(run/'status.json');start=datetime.fromisoformat(s['duration_started_utc']).timestamp();deadline=start+14400
    receipt=run/'four-hour-stop-request.json'
    while time.time()<deadline:
        s=read(run/'status.json')
        assert s['state'] in ('running','yielding-to-drift'), 'Worker stopped before amended deadline; inspect, never restart'
        time.sleep(min(20,max(.1,deadline-time.time())))
    s=read(run/'status.json');assert s['state'] in ('running','yielding-to-drift')
    assert not (run/'STOP').exists() and not receipt.exists()
    publish(receipt,dict(board='2609',owner_authorized=True,total_hours=4,started_utc=s['duration_started_utc'],deadline_unix=deadline,requested_utc=datetime.now(timezone.utc).isoformat(),policy=str(policy),policy_sha256=pointer['sha256'],worker_pid=s['pid'],mechanism='existing STOP at next safe unit boundary; worker restores RAM'))
    (run/'STOP').write_text('Owner amended total soak duration to four hours. See four-hour-stop-request.json.\n')
    print('Requested safe STOP; completion still requires independent receipt/process/restoration audit',flush=True)
if __name__=='__main__':main()
