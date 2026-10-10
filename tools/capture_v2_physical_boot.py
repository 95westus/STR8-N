"""Receive-only physical RESET capture for the three authorized boards."""
import argparse,json,time
from pathlib import Path
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from serial.tools.list_ports import comports

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--seconds',type=int,default=300);p.add_argument('--attempt',default='');p.add_argument('--version',default='2.0b22',choices=('2.0b22','2.0b23'));a=p.parse_args()
    assert 1<=a.seconds<=600
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    out=a.root/('physical-boot'+a.attempt);out.mkdir(exist_ok=False)
    ports={x.serial_number:x.device for x in comports()};links={};logs={};buffers={b:bytearray() for b in SERIALS}
    try:
        for board,serial in SERIALS.items():
            logs[board]=(out/(board+'-serial.jsonl')).open('x');links[board]=Link(ports[serial],logs[board])
        print('Receive-only RESET capture ready: 2512, 2205, 2609; TX=0, DTR=0, RTS=0',flush=True)
        end=time.monotonic()+a.seconds
        while time.monotonic()<end:
            for board,link in links.items():
                if link.serial.in_waiting:
                    buffers[board].extend(link.read(link.serial.in_waiting))
                    (out/(board+'-boot.txt')).write_bytes(buffers[board])
            if all(b'B3> ' in data for data in buffers.values()):break
            time.sleep(.025)
        report={board:dict(port=ports[SERIALS[board]],monitor_ready=b'B3> ' in data,beta22_banner=b'STR8-N 2.0b22' in data,
                          expected_version=a.version,banner_matches=('STR8-N '+a.version).encode() in data,
                          tx_bytes=0,dtr=False,rts=False) for board,data in buffers.items()}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    finally:
        for link in links.values():link.serial.close()
        for log in logs.values():log.close()

if __name__=='__main__':main()
