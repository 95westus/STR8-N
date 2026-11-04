"""Append on-demand or periodic native MON TIME samples to a host JSONL log.

One serial owner, foreground only. No BIN, flash/SRAM/RTC-data write or reset.
The board's unzoned time and the host's UTC collection times remain separate.
"""
import argparse
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import re
import time

PROMPT=re.compile(rb'(?:^|\r\n)(B[0-3]> )$')
RTC=re.compile(r'^RTCC: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(.*)$',re.M)

def utc_now():return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def sample(exchange,*,source=None):
    """exchange sends TIME only from an already observed idle native prompt."""
    started=utc_now();reply=exchange(b'TIME\r');received=utc_now()
    raw=reply.decode('ascii',errors='replace').replace('\r','')
    match=RTC.search(raw);board_time=None
    if match:
        try:board_time=datetime.fromisoformat(match[1]).isoformat()
        except ValueError:pass
    flags=re.search(r' flags \$([0-9A-F]{2})',match[2]) if match else None
    return dict(schema=1,source=source,host_request_utc=started,host_received_utc=received,
                board_time=board_time,board_zone=None,status='sample' if board_time else 'unavailable',
                board_flags_hex=flags[1] if flags else None,raw_reply=raw,
                note='Board zone and clock/battery accuracy are not certified; host times are collection times.')

def collect(exchange,output,*,count=1,interval=0,source=None,emit=None):
    """count0 runs until interrupted; missed deadlines never cause a burst."""
    if count<0 or not math.isfinite(interval) or interval<0 or (count!=1 and interval<=0):
        raise ValueError('Use count1 for on-demand, or a positive interval with count0/positive count')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    done=0;due=time.monotonic()
    with output.open('a',encoding='utf-8',newline='\n') as stream:
        while count==0 or done<count:
            delay=due-time.monotonic()
            if delay>0:time.sleep(delay)
            row=sample(exchange,source=source)
            stream.write(json.dumps(row,ensure_ascii=True)+'\n');stream.flush();os.fsync(stream.fileno())
            done+=1
            if emit:emit(row)
            if interval:
                due+=interval;now=time.monotonic()
                if due<now:due+=(math.floor((now-due)/interval)+1)*interval
    return done

class SerialMonitor:
    """Requires the user's explicit idle-monitor assertion; never enters REC/L."""
    def __init__(self,port,baud=115200,expected_serial=None):
        self.device=port;self.baud=baud;self.expected_serial=expected_serial;self.port=None;self.prompt=None
    def __enter__(self):
        import serial
        from serial.tools import list_ports
        if self.expected_serial:
            found=[p for p in list_ports.comports() if p.device.upper()==self.device.upper()]
            if len(found)!=1 or found[0].serial_number!=self.expected_serial:
                raise ValueError('Selected port does not match the expected USB serial number')
        port=serial.Serial(port=None,baudrate=self.baud,timeout=.05,write_timeout=5)
        port.dtr=False;port.rts=False;port.rtscts=False;port.port=self.device
        self.port=port
        try:
            port.open();port.write(b'\x03');self._reply(15)
        except BaseException:
            port.close();raise
        return self
    def __exit__(self,*_):
        if self.port:self.port.close()
    def _reply(self,timeout):
        data=bytearray();deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            data.extend(self.port.read(max(1,min(4096,self.port.in_waiting))))
            match=PROMPT.search(data)
            if match:self.prompt=match[1];return bytes(data)
            if data.endswith(b'REC> ') or data.endswith(b'SEND BIN\r\n'):
                self.prompt=None;raise RuntimeError('Native MON Bx> required; no TIME command sent to recovery/loader')
            if len(data)>65536:break
        self.prompt=None;raise TimeoutError('Native monitor prompt lost; collection stopped without retry')
    def exchange(self,command):
        if command!=b'TIME\r' or not self.prompt:raise ValueError('Only TIME from an observed native prompt is allowed')
        self.prompt=None
        if self.port.write(command)!=len(command):raise IOError('Short serial write; collection stopped')
        return self._reply(20)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True);parser.add_argument('--baud',type=int,default=115200)
    parser.add_argument('--expect-serial');parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--idle-monitor',action='store_true',help='Confirm the selected board is idle at native Bx>; disconnect its terminal first')
    parser.add_argument('--interval',type=float,default=0,help='Seconds between sample starts; collector must remain running')
    parser.add_argument('--count',type=int,help='Default1 on-demand, or repeat until Ctrl-C when interval is positive')
    args=parser.parse_args();count=args.count if args.count is not None else (0 if args.interval else 1)
    if not args.idle_monitor:parser.error('--idle-monitor is required; this tool does not stop an application or enter the monitor')
    if count<0 or not math.isfinite(args.interval) or args.interval<0 or (count!=1 and args.interval<=0):
        parser.error('Periodic collection needs a finite positive --interval; --count must be0 or positive')
    try:
        with SerialMonitor(args.port,args.baud,args.expect_serial) as monitor:
            collect(monitor.exchange,args.output,count=count,interval=args.interval,source=args.port,
                    emit=lambda r:print(r['host_received_utc'],r['board_time'] or r['status'],flush=True))
    except KeyboardInterrupt:print('Collection stopped; serial port released.')
    except (OSError,ValueError,RuntimeError,TimeoutError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
