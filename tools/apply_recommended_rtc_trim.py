"""Apply explicitly authorized October 11 trims; establish read-only baselines."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_prompt_sync import establish_b3
from rtc_boards import SERIALS
ROOT=Path(__file__).resolve().parents[1]
old=ROOT/'output/qualification/rtc-zero-trim-campaign-2026-10-09-231026Z/baseline-index.json'
index=json.loads(old.read_text());steps={'2205':-17,'2512':-12,'2604':-12,'2609':-14}
out=ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('rtc-trim-validation-%Y-%m-%d-%H%M%SZ');out.mkdir()
def execute(script,*args):
    r=subprocess.run([sys.executable,str(ROOT/'tools'/script),*map(str,args)],capture_output=True,text=True,cwd=ROOT)
    (out/(script+'.log')).write_text(r.stdout+r.stderr)
    assert r.returncode==0,r.stderr[-1500:]
execute('capture_rtc_drift_status.py','--root',out/'preflight','--baseline-index',old)
ports={p.serial_number:p.device for p in comports()};records=[]
for board in sorted(steps):
    b=next(b for b in index['boards'] if b['board']==board);dest=out/board;dest.mkdir()
    transcript=[]
    with (dest/'trim-serial.jsonl').open('w') as log:
        link=Link(ports[SERIALS[board]],log)
        try:
            establish_b3(link)
            def command(text,prompt=b'CLOCK> '):
                reply=link.command(text,prompt);transcript.append('SEND: '+text+'\n'+reply.decode('ascii',errors='replace'))
                (dest/'trim-transcript.txt').write_text('\n'.join(transcript));return reply
            command('R CLOCK')
            before=command('STATUS');assert b'Running: yes' in before
            assert b'Trim 0 steps; coarse OFF; OSCTRIM $00' in command('TRIM')
            assert b['eui'].encode() in command('EUI')
            warning=command(f'TRIM {steps[board]}',b'Type YES to confirm: ')
            assert b'Type YES to confirm:' in warning
            reply=command('YES')
            assert f'Trim {steps[board]} steps; coarse OFF; OSCTRIM ${abs(steps[board]):02X}'.encode() in reply
            after=command('STATUS');assert b'Running: yes' in after
            command('TRIM');command('Q',b'\r\nB3> ')
        finally:link.serial.close()
    records.append(dict(board=board,trim_steps=steps[board],applied=True,clock_set=False))
    (out/'applied-trims.json').write_text(json.dumps(records,indent=2)+'\n')
new=dict(index);new['boards']=[];new.update(campaign='Post-trim residual validation; UTC unchanged',clock_set=False,trim_applied=True)
for board in sorted(steps):
    b=dict(next(b for b in index['boards'] if b['board']==board));b['trim_steps']=steps[board]
    path=out/board/'baseline'
    execute('rtc_utc_baseline.py','--board',board,'--port',ports[SERIALS[board]],'--server','132.163.96.6','--out',path)
    report=path/'report.json';r=json.loads(report.read_text());assert r['passed'] and not r.get('clock_set_attempted',False)
    assert all(x['raw'][8]==abs(steps[board]) and x['raw'][7]==b['control_register'] for x in r['readings'] if x['status']==0)
    for key in ('sync','baseline'):
        b[key+'_report']=str(report);b[key+'_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
    b['baseline_reference_utc']=r['baseline_reference_utc'];b['rtc_minus_reference_interval_s']=r['rtc_minus_reference_interval_s'];new['boards'].append(b)
newindex=out/'baseline-index.json';newindex.write_text(json.dumps(new,indent=2)+'\n')
execute('capture_rtc_drift_status.py','--root',out/'final','--baseline-index',newindex)
pointer=dict(baseline_index=str(newindex),baseline_index_sha256=hashlib.sha256(newindex.read_bytes()).hexdigest(),boards=sorted(steps),excluded_boards=[],scheduled_end_local=None)
(ROOT/'output/qualification/active-rtc-campaign.json').write_text(json.dumps(pointer,indent=2)+'\n')
print('PASS trims and new baselines:',out,flush=True)
execute('analyze_rtc_drift.py','--baseline-index',newindex)
print((out/'analyze_rtc_drift.py.log').read_text(),flush=True)
