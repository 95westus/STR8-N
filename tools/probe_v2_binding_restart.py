"""Observe post-installer restart without issuing reset or flash commands."""
import argparse,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    results=[]
    for board,port in (('2512','COM4'),('2205','COM3'),('2609','COM8')):
        assert next(x for x in comports() if x.device.upper()==port).serial_number==SERIALS[board]
        root=a.root/board;out=root/'restart-probe';out.mkdir(exist_ok=False)
        with (out/'serial.jsonl').open('x') as log:
            link=Link(port,log)
            try:
                received=bytearray();end=time.monotonic()+.3
                while time.monotonic()<end:received.extend(link.read(max(1,link.serial.in_waiting)))
                link.send(b'\r')
                try:
                    data=link.until(b'> ',5);received.extend(data)
                    if b'CLOCK>' in data or b'BM>' in data:received.extend(link.command('Q'))
                    ready=b'B3>' in received or b'CLOCK>' in data or b'BM>' in data
                except TimeoutError:ready=False
                (out/'received.txt').write_bytes(received)
                report=dict(board=board,ready=ready,reset_issued=False,flash_written=False)
                (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');results.append(report)
                print(board,'monitor ready' if ready else 'no prompt; may still be halted in installer')
            finally:link.serial.close()
    (a.root/'restart-probe.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
