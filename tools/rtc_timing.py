"""UTC bounds and MCP79411 fine-trim calculation for STR8-N UTIL RTC."""
import csv
from datetime import datetime, timezone
import math
import socket
import statistics
import struct
import time

NTP_EPOCH = 2208988800
PPM_PER_STEP = 2_000_000 / (32768 * 60)
COLUMNS = ('segment', 'device', 'server', 'reference_unix', 'offset_low_s', 'offset_high_s',
           'control_hex', 'trim_hex', 'outage_hex')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ntp_bounds(server):
    """Return a UTC-minus-monotonic interval, using a four-timestamp exchange."""
    request = bytearray(48)
    request[0] = 0x23
    stamp = time.time() + NTP_EPOCH
    second = int(stamp)
    struct.pack_into('!II', request, 40, second & 0xffffffff, int((stamp-second)*2**32))
    family, kind, protocol, _, address = socket.getaddrinfo(server, 123, type=socket.SOCK_DGRAM)[0]
    with socket.socket(family, kind, protocol) as sock:
        sock.settimeout(5)
        sock.connect(address)
        start = time.perf_counter()
        sock.send(request)
        response = sock.recv(512)
        end = time.perf_counter()
    require(len(response)>=48 and response[0]>>6!=3 and response[0]&7==4 and
            1<=response[1]<=15 and response[24:32]==request[40:48] and
            any(response[32:40]) and any(response[40:48]), 'Invalid or unsynchronized NTP reply')
    def stamp_at(offset):
        s, frac = struct.unpack_from('!II', response, offset)
        era = round((second-s)/2**32)
        return s+era*2**32+frac/2**32-NTP_EPOCH
    received, sent = stamp_at(32), stamp_at(40)
    require(0<=sent-received<=end-start<=0.5, 'NTP exchange exceeded timing budget')
    delay = max(0, struct.unpack_from('!i', response, 4)[0]/65536)
    dispersion = struct.unpack_from('!I', response, 8)[0]/65536
    margin = delay/2 + dispersion + .002
    return sent-end-margin, received-start+margin


class Reference:
    def __init__(self, server):
        self.server = server
        windows = []
        for i in range(3):
            if i:
                time.sleep(4)
            windows.append(ntp_bounds(server))
        self.low = max(x[0] for x in windows)
        self.high = min(x[1] for x in windows)
        self.start = time.perf_counter()
        require(0<=self.high-self.low<=.2, 'NTP intervals disagree or uncertainty exceeds 100 ms')

    def now(self):
        return time.perf_counter()+(self.low+self.high)/2

    def uncertainty(self):
        age = time.perf_counter()-self.start
        require(age<180, 'UTC reference expired')
        return (self.high-self.low)/2+age*.00005

    def check(self):
        low, high = ntp_bounds(self.server)
        u = self.uncertainty()
        mid = (self.low+self.high)/2
        require(max(low,mid-u)<=min(high,mid+u), 'UTC reference shifted during operation')


def decode_rtc(raw):
    require(len(raw)==17 and raw[0]&0x80 and raw[3]&0x30==0x20,
            'RTC stopped or power-fail evidence is latched')
    require(not raw[2]&0x40, 'RTC calendar must be in 24-hour mode')
    def bcd(v):
        require(v>>4<=9 and v&15<=9, 'Invalid RTC BCD')
        return 10*(v>>4)+(v&15)
    return datetime(2000+bcd(raw[6]),bcd(raw[5]&31),bcd(raw[4]&63),
                    bcd(raw[2]&63),bcd(raw[1]&127),bcd(raw[0]&127),
                    tzinfo=timezone.utc).timestamp()


def trim_steps(value):
    return (value&0x7f)*(1 if value&0x80 else -1)


def series_key(row):
    return tuple(row[key] for key in ('segment','device','server','control_hex','trim_hex','outage_hex'))


def samples(path):
    with path.open(encoding='utf-8',newline='') as handle:
        reader=csv.DictReader(handle)
        require(tuple(reader.fieldnames or ())==COLUMNS, 'Unknown RTC CSV schema')
        rows=list(reader)
    require(0<len(rows)<=1000, 'Use a series with one to 1,000 samples')
    require(all(None not in row and None not in row.values() for row in rows), 'Malformed RTC CSV')
    for row in rows:
        t,lo,hi=(float(row[k]) for k in ('reference_unix','offset_low_s','offset_high_s'))
        require(all(math.isfinite(v) for v in (t,lo,hi)) and 0<=hi-lo<=.5,
                'Sample is missing or has more than 500 ms of uncertainty width')
        for field, length in (('control_hex',1),('trim_hex',1),('outage_hex',8)):
            require(len(bytes.fromhex(row[field]))==length, 'Invalid register evidence in CSV')
    require(all(series_key(row)==series_key(rows[0]) for row in rows),
            'CSV mixes devices, references, trim, control or power-fail records')
    times=[float(row['reference_unix']) for row in rows]
    require(all(b>a for a,b in zip(times,times[1:])), 'Samples must be strictly chronological')
    return rows


def calculate(rows):
    require(len(rows)>=3, 'At least three samples are required')
    first=rows[0]
    require(not int(first['control_hex'],16)&4, 'Fine trim requires coarse mode OFF')
    start=float(first['reference_unix'])
    t=[float(row['reference_unix'])-start for row in rows]
    require(t[-1]>=12*3600, 'Collect at least 12 hours in one uninterrupted segment')
    lower=[float(row['offset_low_s']) for row in rows]
    upper=[float(row['offset_high_s']) for row in rows]
    lo,hi=-math.inf,math.inf
    for i in range(len(t)-1):
        for j in range(i+1,len(t)):
            span=t[j]-t[i]
            lo=max(lo,(lower[j]-upper[i])/span)
            hi=min(hi,(upper[j]-lower[i])/span)
    require(lo<=hi, 'No constant drift fits these bounds. Start a fresh series after discontinuities.')
    middle=[(a+b)/2 for a,b in zip(lower,upper)]
    mean=statistics.mean(t)
    slope=sum((x-mean)*y for x,y in zip(t,middle))/sum((x-mean)**2 for x in t)
    ppm=min(hi,max(lo,slope))*1e6
    lo*=1e6
    hi*=1e6
    current=trim_steps(int(first['trim_hex'],16))
    bottom,top=current-hi/PPM_PER_STEP,current-lo/PPM_PER_STEP
    candidate=math.floor((bottom+top)/2+.5)
    stable=-127<=candidate<=127 and candidate-.5<bottom<=top<candidate+.5
    return dict(device=first['device'],reference=first['server'],samples=len(rows),
                span_hours=t[-1]/3600,drift_ppm=ppm,drift_bounds_ppm=[lo,hi],
                current_trim=current,trim_range=[bottom,top],
                proposed_trim=candidate if stable else None,
                last_reference_unix=start+t[-1],ppm_per_step=PPM_PER_STEP)

