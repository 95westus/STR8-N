"""Receive-only four-board startup capture with USB reconnect support."""
import argparse,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--seconds',type=int,default=300);a=p.parse_args()
    assert 1<=a.seconds<=600
    out=a.root/'power-return';out.mkdir(exist_ok=False)
    logs={b:(out/(b+'-serial.jsonl')).open('x') for b in SERIALS};links={};buffers={b:bytearray() for b in SERIALS};events=[]
    end=time.monotonic()+a.seconds
    print('Receive-only power-return capture ready on all four boards; TX=0; backup batteries stay installed',flush=True)
    try:
        while time.monotonic()<end:
            ports={p.serial_number:p.device for p in comports()}
            for b,identity in SERIALS.items():
                if b not in links and identity in ports:
                    try:links[b]=Link(ports[identity],logs[b]);events.append(dict(board=b,event='opened',port=ports[identity],unix=time.time()))
                    except Exception as e:events.append(dict(board=b,event='open-error',error=repr(e),unix=time.time()))
                if b in links:
                    try:
                        if links[b].serial.in_waiting:
                            buffers[b].extend(links[b].read(links[b].serial.in_waiting));(out/(b+'-boot.txt')).write_bytes(buffers[b])
                    except Exception as e:
                        events.append(dict(board=b,event='disconnected',error=repr(e),unix=time.time()))
                        try:links[b].serial.close()
                        except Exception:pass
                        del links[b]
            if all(b'STR8-N 2.0b23' in data and b'B3> ' in data for data in buffers.values()):break
            time.sleep(.05)
        report=dict(boards={b:dict(beta23_banner=b'STR8-N 2.0b23' in data,monitor_ready=b'B3> ' in data,tx_bytes=0) for b,data in buffers.items()},events=events)
        report['passed']=all(r['beta23_banner'] and r['monitor_ready'] for r in report['boards'].values())
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    finally:
        for link in links.values():link.serial.close()
        for log in logs.values():log.close()

if __name__=='__main__':main()
