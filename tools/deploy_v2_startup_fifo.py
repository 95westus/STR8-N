"""2609-only generation 35 drain deployment and retained reference."""
import json,sys,shutil,time
import deploy_v2_startup_keys as d
from rtc_prompt_sync import establish_b3

ROOT=d.ROOT;BUILD=ROOT/'BUILD/v2-startup-fifo';BASE=ROOT/'output/qualification/startup-fifo-2026-10-14'
d.BUILD=BUILD;d.OLD=ROOT/'BUILD/v2-startup-keys';d.BASE=BASE;d.BOARDS=('2609',);d.deploy.BUILD=BUILD

def baseline():
    root=BASE/'2609';root.mkdir(parents=True,exist_ok=True)
    with d.serial_lease('startup-fifo-baseline'),(root/'stale-baseline-calibration.jsonl').open('a') as log:
        l=d.m.Link(d.port('2609'),log)
        try:
            establish_b3(l)
            for delay in (.2,.3,.4):
                l.send(b'J3\r');text=l.until(b'J3\r\n');time.sleep(delay);l.send(b'B')
                text+=l.until(b'\r\nB3> ');(root/f'stale-baseline-{delay}.txt').write_bytes(text)
                if b'Enter default [3s]: ' not in text and text.split(b'STR8-N')[0].count(b'.')==0:
                    assert l.dump(0x7D30,0x7D30)==b'\xB0'
                    (root/'stale-baseline-report.json').write_text(json.dumps(dict(passed=True,delay_seconds=delay,queued_key='B',startup_dots=0),indent=2)+'\n')
                    print('PASS old generation 34 accepts queued B before the first dot; injection delay',delay,flush=True)
                    break
            else:raise AssertionError('Could not establish pre-window FIFO injection; no hardware drain claim')
        finally:l.serial.close()

def reference():
    campaign=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
    with d.serial_lease('startup-fifo-reference'):
        root=BASE/'2609'/'retained';prior=root/'sram-prior';prior.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(ROOT/'output/qualification/startup-keys-2026-10-14/2609/corrected-retest/retained/sram-final/array-0.bin',prior/'array-0.bin')
        d.power.call(d.power.array,['--root',str(root),'--board','2609','--port',d.port('2609'),'--stage','final'])
        shutil.move(root/'sram-final',root/'sram-reference')
        d.power.call(d.power.devices,['--root',str(root),'--board','2609','--port',d.port('2609'),'--stage','before','--baseline-index',campaign['baseline_index']])

if __name__=='__main__':
    stage=sys.argv[1]
    if stage=='baseline':baseline()
    elif stage=='backups':d.backups()
    elif stage=='reference':reference()
    elif stage=='prepare':d.prepare('2609')
    elif stage=='install':d.deploy.install(BASE/'2609','2609')
    else:raise ValueError(stage)
