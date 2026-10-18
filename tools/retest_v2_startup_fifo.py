"""2609-only FIFO-drain comparison and complete generation 35 retest."""
import json,time,sys
import deploy_v2_startup_fifo as d
import retest_v2_startup_keys as t
from rtc_prompt_sync import establish_b3

t.BASE=d.BASE;t.REPAIR_BASE=d.BASE;t.BUILD=d.BUILD;t.BOARDS=('2609',)
t.GENERATION=35;t.RETEST_NAME='retest';t.CAPTURE_STEM='physical-reset'

def fifo():
    root=d.BASE/'2609';baseline=json.loads((root/'stale-baseline-report.json').read_text())
    assert baseline['passed'];results=[]
    with d.d.serial_lease('startup-fifo-hardware'),(root/'fifo-hardware.jsonl').open('x') as log:
        l=t.Link(d.d.port('2609'),log)
        try:
            establish_b3(l)
            for key in (b'A',b'B',b'\x1b',b'\r'):
                l.send(b'J3\r');text=l.until(b'J3\r\n');time.sleep(baseline['delay_seconds']);l.send(key)
                text+=l.until(t.PROMPT);(root/('stale-'+key.hex()+'.txt')).write_bytes(text)
                assert text.split(b'MONITOR ')[0].count(b'.')==160 and t.MENU in text,text
                assert l.dump(0x7D30,0x7D30)==b'\xA0'
                results.append(dict(key_hex=key.hex(),discarded=True,startup_dots=160,passed=True))
                print('PASS queued',key.hex(),'discarded before input window; all 160 dots retained',flush=True)
        finally:l.serial.close()
    (root/'fifo-hardware-report.json').write_text(json.dumps(dict(passed=True,board='2609',generation=35,
        baseline=baseline,cases=results,continuous_input_bound_tested_in_model=True),indent=2)+'\n')

if __name__=='__main__':
    if sys.argv[1]=='capture':t.capture()
    elif sys.argv[1]=='fifo':fifo()
    elif sys.argv[1]=='verify':t.verify()
    else:raise ValueError(sys.argv[1])
