"""Execute linked PF duration, real journal capture and recent interval UI."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta35-candidate'
import calendar
from datetime import datetime,timedelta
import json
from pathlib import Path
import random
import hashlib

from test_v2_status import fresh,boot
from test_v2_sram_store import console
from test_v2_spi_resident import k
from test_v2_journal import EEPROM

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/os.environ['STR8_RTC_BUILD']
read=lambda p:json.loads(p.read_text())
S=read(OUT/'pf-worker/build.json')['symbols'];C=read(OUT/'clock/build.json')['symbols']
BCD=lambda v:(v//10)*16+v%10


def stamp(d,h12=False):
    hour=BCD(d.hour)
    if h12:hour=0x40|(0x20 if d.hour>=12 else 0)|BCD(d.hour%12 or 12)
    return bytes((BCD(d.minute),hour,BCD(d.day),BCD(d.month)|0x60))


def fixture():
    cpu,mem=fresh();mem.fast=True
    mem.banks=[bytearray((OUT/f'candidate/b{i}.bin').read_bytes()) for i in range(4)];mem.spi.banks=mem.banks
    mem.ram[0x6700:0x6A00]=(OUT/'pf-worker/asset.bin').read_bytes()
    return cpu,mem


def call(cpu,address,limit=20000000):
    cpu.stPushWord(0x1FF);cpu.pc=address
    k.model.run(cpu,lambda:cpu.pc==0x200,limit)
    return bool(cpu.p&cpu.CARRY)


def duration_tests():
    cpu,mem=fixture();rng=random.Random(35);cases=[]
    for y in (2000,2024,2025,2026,2027,2028,2098):
        for month in range(1,13):
            down=datetime(y,month,calendar.monthrange(y,month)[1],23,59)
            cases.extend((down,down+timedelta(minutes=n)) for n in (0,1,61,1441,43231))
    for _ in range(200):
        down=datetime(2023,1,1)+timedelta(minutes=rng.randrange(4*365*1440))
        cases.append((down,down+timedelta(minutes=rng.randrange(364*1440))))
    for i,(down,up) in enumerate(cases):
        mem.ram[0x6000:0x6008]=stamp(down,i%2==0)+stamp(up,i%3==0)
        mem.ram[S['OF_PTR']:S['OF_PTR']+2]=b'\0\x60'
        mem.ram[S['D_YEAR']]=up.year&255;mem.ram[S['D_VALID']]=1
        assert call(cpu,S['D_CALC']), (down,up)
        got=(int.from_bytes(mem.ram[S['D_DAYS']:S['D_DAYS']+2],'little'),mem.ram[S['D_HOUR']],mem.ram[S['D_MIN']])
        n=int((up-down).total_seconds()//60);wanted=(n//1440,n//60%24,n%60)
        assert got==wanted,(down,up,got,wanted)
    invalid=[bytes.fromhex(x) for x in (
        '6A 05 07 70 04 05 07 70','03 25 07 70 04 05 07 70',
        '03 05 31 64 04 05 01 65','03 05 29 62 04 05 01 63',
        '03 05 07 70 02 05 07 70')]
    for pair in invalid:
        mem.ram[0x6000:0x6008]=pair;mem.ram[S['OF_PTR']:S['OF_PTR']+2]=b'\0\x60'
        mem.ram[S['D_YEAR']]=2026&255;mem.ram[S['D_VALID']]=1
        assert not call(cpu,S['D_CALC']),pair.hex()
    mem.ram[S['D_VALID']]=0;assert not call(cpu,S['D_CALC'])
    print('PASS',len(cases),'linked duration cases, leap/month/year rollovers, 12h, malformed/unknown/reversed rejection',flush=True)
    return len(cases)


def clock_time(mem,d):
    mem.bus.rtc_regs[:9]=bytes((0x80|BCD(d.second),BCD(d.minute),BCD(d.hour),0x28|d.isoweekday(),BCD(d.day),BCD(d.month),BCD(d.year%100),0x80,12))


def power_event(cpu,mem,down,up,capture=None):
    context={n:getattr(cpu,n) for n in ('pc','a','x','y','p','sp')}
    clock_time(mem,capture or up);mem.bus.rtc_regs[3]|=0x10
    raw=stamp(down)+stamp(up);mem.bus.rtc_regs[0x18:0x20]=raw
    assert call(cpu,0x6504)
    cpu.x=1;assert call(cpu,0x9004,40000000)
    assert not mem.bus.rtc_regs[3]&0x10
    for n,v in context.items():setattr(cpu,n,v)
    return raw


def integration():
    cpu,mem=fixture();mem.bus=EEPROM();mem.bus.ram=mem.ram
    down=datetime(2026,10,15,23,59);up=datetime(2026,10,16,0,1)
    clock_time(mem,up);mem.bus.rtc_regs[3]|=0x10;mem.bus.rtc_regs[0x18:0x20]=stamp(down)+stamp(up)
    boot(cpu);out=bytes(mem.tx);(OUT/'beta35-boot-pf.txt').write_bytes(out)
    assert b'Outage: ~000d 00:02 (min)' in out and b'PF logged, ACK' in out,out[-1000:]
    assert not mem.bus.rtc_regs[3]&0x10
    eeprom=bytes(mem.bus.ee);writes=len(mem.bus.writes)
    out=console(cpu,mem,b'J3\r',limit=100000000)
    assert b'2.0b35' in out and b'power-fail' not in out and bytes(mem.bus.ee)==eeprom and len(mem.bus.writes)==writes
    # Five more real save/ACK cycles wrap the four-slot ring without schema changes.
    for day in range(17,22):
        power_event(cpu,mem,datetime(2026,10,day,0,1),datetime(2026,10,day,0,3))
    before=(bytes(mem.bus.ee),bytes(mem.bus.rtc_regs),[bytes(b) for b in mem.banks],bytes(mem.spi.devices[0].data))
    body=(OUT/'clock/clock.bin').read_bytes();mem.ram[0x2000:0x2000+len(body)]=body
    out=console(cpu,mem,b'G 2000\rSTATS\r',limit=100000000)
    (OUT/'beta35-stats.txt').write_bytes(out)
    assert b'CLOCK 1.10' in out and out.count(b'UTC slot ')==4,out[-2500:]
    assert out.count(b'Outage: ~000d 00:02 (min)')==4,out[-2500:]
    assert out.count(b'On: ~000d 23:58 (min)')==3,out[-2500:]
    after=(bytes(mem.bus.ee),bytes(mem.bus.rtc_regs),[bytes(b) for b in mem.banks],bytes(mem.spi.devices[0].data))
    assert before==after,'STATS must be read-only'
    # Missing trusted capture year is not replaced with the current RTC year.
    for i in range(4):
        rec=bytearray(mem.bus.ee[i*32:(i+1)*32])
        if rec[:2]==b'PF':
            rec[24]&=0x7F
            from beta4_migration import crc
            rec[28:30]=crc(rec[:28]).to_bytes(2,'little');mem.bus.ee[i*32:(i+1)*32]=rec
    out=console(cpu,mem,b'STATS\r',limit=100000000)
    assert out.count(b'Outage: ~unknown')==4 and out.count(b'On: ~unknown')==3,out[-2500:]
    # A Dec 31 up stamp captured after midnight belongs to the previous year.
    rec=bytearray(32);rec[12:20]=stamp(datetime(2027,12,31,1))+stamp(datetime(2027,12,31,2))
    rec[20:28]=(2028).to_bytes(2,'little')+bytes((1,1,0x80,0,0,0))
    mem.ram[0x6000:0x6020]=rec;mem.ram[C['H_PTR']:C['H_PTR']+2]=b'\0\x60'
    mem.ram[C['S_STATS']]=1;mem.ram[C['S_SEEN']]=0
    call(cpu,C['S_GAP']);assert mem.ram[C['S_YEAR']]==2027&255
    print('PASS boot PF save/rearm, reset dedup, subsequent ring-wrap capture and read-only off/on STATS',flush=True)


if __name__=='__main__':
    n=duration_tests();integration()
    (OUT/'beta35-test-results.json').write_text(json.dumps(dict(passed=True,duration_cases=n,minute_precision=True,
        build_sha256=hashlib.sha256((OUT/'build.json').read_bytes()).hexdigest(),
        eeprom_format_unchanged=True,read_only_stats=True,boot_save_ack_rearm=True),indent=2)+'\n')
