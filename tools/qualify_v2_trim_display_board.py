"""After operator RESET, verify every flash byte and read-only TIME correction."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True)
    a=p.parse_args();assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/'installed-check';out.mkdir(exist_ok=False);plan=json.loads((a.root/'upgrade/plan.json').read_text())
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ');(out/'startup.txt').write_bytes(initial)
            if any(t in initial for t in (b'CLOCK>',b'EDU>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                assert data==(a.root/f'upgrade/expected-b{bank}.bin').read_bytes()
                digest=hashlib.sha256(data).hexdigest();assert digest==plan['expected_hashes'][bank]
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(digest)
            link.command('B3');output=link.command('TIME');(out/'time.txt').write_bytes(output)
            if a.board=='2512':assert b'RTCC: unavailable' in output and b'Trim' not in output
            else:
                assert b'RTCC: UTC ' in output and b'RTCC: Trim 0 steps: 0.00 ppm, 0.000 s/day correction' in output
                link.command('R CLOCK',b'CLOCK> ')
                status=link.command('STATUS',b'CLOCK> ');(out/'clock-status.txt').write_bytes(status)
                assert b'Running: yes' in status and b'OSCTRIM $00' in status and b'coarse OFF' in status
                identity=link.command('EUI',b'CLOCK> ');(out/'eui.txt').write_bytes(identity)
                assert b', changed' not in identity and b', unbound' not in identity
                link.command('Q')
            if plan.get('quiet_monitor_return'):
                mapped=link.command('M1');(out/'m1.txt').write_bytes(mapped)
                assert b'B3:8-F protected.' in mapped and b'STR8-N ' not in mapped and b'RTCC:' not in mapped
            if plan.get('weekday_display') and a.board!='2512':
                import re
                assert re.search(rb'RTCC: UTC (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{4}-\d{2}-\d{2}',output)
            (out/'report.json').write_text(json.dumps(dict(passed=True,board=a.board,version=plan['version'],
                final_hashes=hashes,clock_set=False,trim_changed=False,all_saved_records_preserved=True),indent=2)+'\n')
            print('PASS',a.board,'exact four-bank image and read-only trim display')
        finally:link.serial.close()

if __name__=='__main__':main()
