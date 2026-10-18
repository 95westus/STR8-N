"""Plan-bound physical mixed-monitor and retained-memory qualification."""
import json,re,sys,time,hashlib,argparse,binascii
from pathlib import Path
from beta4_migration import Link
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from migrate_v2 import ROOT,read
parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('capture','capture_power','accept_power','verify','wear'));parser.add_argument('--root',required=True,type=Path)
ARGS=parser.parse_args();PLAN=read(ARGS.root/'upgrade/plan.json');BOARD=PLAN['board'];BASE=ARGS.root.resolve().parent;BUILD=ROOT/PLAN['target_build']
assert ARGS.root.resolve().name==BOARD and PLAN['active_fallback']=='A' and PLAN['updated_slot']=='B'
FALLBACK_VERSION=PLAN['source']['version'];FALLBACK_GENERATION=PLAN['source_generation']
SOURCE=BASE/BOARD/'prior-verified/b3.bin';raw=SOURCE.read_bytes()
zones=[raw[i:i+32] for i in range(0x1C20,0x2000,32)];zones=[r for r in zones if r[:4]==b'TZ\1\0' and r[31]==0 and binascii.crc_hqx(r[:28],65535)==int.from_bytes(r[28:30],'little')]
minutes=int.from_bytes(max(zones,key=lambda r:int.from_bytes(r[4:8],'little'))[8:10],'little',signed=True) if zones else 0
EXPECTED_OFFSET=('('+('-' if minutes<0 else '+')+f'{abs(minutes)//60:02d}:{abs(minutes)%60:02d}'+')').encode()
names=[raw[i:i+32] for i in range(0x1C20,0x2000,32)];names=[r for r in names if r[:4]==b'BN\1\0' and r[31]==0 and binascii.crc_hqx(r[:28],65535)==int.from_bytes(r[28:30],'little')]
latest=max(names,key=lambda r:int.from_bytes(r[4:8],'little')) if names else None
EXPECTED_NAME=b'Board: '+(latest[9:9+latest[8]] if latest and latest[8] else b'unnamed')

from qualify_v2_spi_install import load_image
import qualify_v2_beta24_power as power
import run_beta23_soak as smoke
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
PORT=next(p.device for p in comports() if p.serial_number==SERIALS[BOARD])

PROMPT=b'\r\nB3> ';MENU=b'Enter default [3s]: ';ROOT_BOARD=BASE/BOARD

def capture(power_on=False):
    out=ROOT_BOARD/'physical-reset';out.mkdir(exist_ok=True)
    with serial_lease('beta25-reset-capture'),(out/'serial.jsonl').open('x') as log:
        l=None
        try:
            print('ARMED: receive-only requested-board power-on capture; waiting for its FTDI identity for 15 minutes',flush=True)
            deadline=time.monotonic()+900;data=b''
            while time.monotonic()<deadline:
                port=next((p.device for p in comports() if p.serial_number==SERIALS[BOARD]),None)
                if port is None:time.sleep(.25);continue
                l=Link(port,log);data=l.until(PROMPT,max(1,deadline-time.monotonic()));break
            assert data,'No requested-board boot captured before timeout'
            (out/'boot.txt').write_bytes(data)
            assert b'STR8-N 2.0b25' in data and f'gen {FALLBACK_GENERATION:08X} VALID'.encode() in data and b'gen 00000025 VALID' in data,data
            p=ROOT_BOARD/'upgrade/install/reset-pending.json';r=read(p);r.update(physical_reset_pending=False,physical_reset_verified=True)
            r['physical_power_cycle_tested']=power_on;p.write_text(json.dumps(r,indent=2)+'\n');print('PASS '+BOARD+' physical boot: fallback A and beta25 B valid; beta25 default',flush=True)
        finally:
            if l:l.serial.close()

def verify():
    assert next(p for p in comports() if p.device==PORT).serial_number==SERIALS[BOARD]
    restart=read(ROOT_BOARD/'upgrade/install/reset-pending.json');assert restart['physical_reset_verified']
    out=ROOT_BOARD/'retest';out.mkdir(exist_ok=False);checks=[];cases=[]
    with serial_lease('beta25-hardware-retest'),(out/'serial.jsonl').open('x') as log:
        l=Link(PORT,log)
        try:
            establish_b3(l)
            def active(slot):assert l.dump(0x7D30,0x7D30)==bytes((0xA0 if slot=='A' else 0xB0,))
            def reboot(key=None,choice=None,recovery=False):
                l.send(b'J3\r');text=l.until(b'.')
                if key is not None:
                    l.send(key)
                    if choice or recovery:
                        text+=l.until(MENU);dots=text.count(b'.');assert 0<dots<160
                        if recovery:
                            l.send(b'S');text+=l.until(b'REC> ');assert b'FIXED F RECOVERY' in text
                            l.send(b'A\r');slot='A'
                        else:l.send(choice.encode());slot=choice
                    else:slot=key.decode().upper()
                    text+=l.until(PROMPT);active(slot)
                else:
                    slot='B';text+=l.until(PROMPT);active(slot)
                    assert text.split(b'MONITOR ')[0].count(b'.')==160
                version=FALLBACK_VERSION.encode() if slot=='A' else b'2.0b25';assert b'STR8-N '+version in text,text
                i=len(cases);(out/f'boot-{i:02d}.txt').write_bytes(text)
                cases.append(dict(key_hex=key.hex() if key else None,choice=choice,recovery=recovery,slot=slot,version=version.decode(),passed=True))
            for key in (b'A',b'a',b'B',b'b'):reboot(key)
            for key,slot in ((b'\x1b','A'),(b'x','B'),(b'\r','A')):reboot(key,slot)
            reboot(b'\x1b',recovery=True);reboot()
            checks.append('fresh A/a fallback and B/b beta25; ESC/other key retains menu; F recovery A; no-key defaults to beta25')
            for key in (b'A',b'B',b'\x1b'):
                l.send(b'J3\r'+key);text=l.until(PROMPT)
                assert text.split(b'MONITOR ')[0].count(b'.')==160 and MENU in text;active('B')
                (out/('stale-'+key.hex()+'.txt')).write_bytes(text)
            checks.append('queued A/B/ESC discarded before input window; 160 dots and beta25 default retained')
            for slot in ('A','B'):
                reboot(slot.encode());legacy_b4=slot=='A' and FALLBACK_VERSION=='2.0b4'
                if legacy_b4:assert l.dump(0x7D04,0x7D04)==b'\0'
                else:smoke.guards(l)
                results=[]
                text=l.command('APPS');assert b'\xff' not in text and b' installed' not in text
                text=l.command('TIME');lines=[v for v in text.split(b'\r\n') if v and v not in (b'TIME',b'B3> ')]
                if legacy_b4:assert text==b'TIME\r\nBad hex\r\nB3> ',text
                else:assert len(lines)==1 and EXPECTED_OFFSET in lines[0] and re.fullmatch(rb'[A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d \([+-]\d\d:\d\d\)',lines[0]),text
                (out/f'time-{slot}.txt').write_bytes(text)
                old=l.dump(0x3E20,0x3E22)
                try:l.write_ram(0x3E20,b'\x01\x03\0')
                finally:l.write_ram(0x3E20,old)
                groups=('monitor','maint') if legacy_b4 else ('monitor','clock','edu','sram','work','maint')
                for group in groups:results.append(dict(group=group,replies=smoke.commands(l,group)))
                if legacy_b4:
                    text=l.command('R CLOCK',b'CLOCK> ');assert b'Services unavailable' in text;text+=l.command('Q')
                    (out/'clock-b4-safe-refusal.txt').write_bytes(text)
                active(slot);(out/f'commands-{slot}.json').write_text(json.dumps(results,indent=2)+'\n')
                transcript=l.command('R MAINT',b'BM> ')+l.command('NAME',b'BM> ')+l.command('Q')
                assert EXPECTED_NAME in transcript,transcript
            checks.append('both versions: APPS, RAM edit, MAINT/name and selected-slot HOLD; beta25 local-only TIME and CLOCK/EDU/SRAM/WORK services')
            if FALLBACK_VERSION=='2.0b4':checks.append('retained b4 original capabilities: TIME unsupported and CLOCK services unavailable safely; RTC services run under beta25')
            probes=ROOT/'BUILD/v2-board-regression';pm=read(probes/'build.json')['probes']
            assert load_image(l,probes/'abi.s19')==pm['abi']['sha256']
            assert b'RAM ABI: PASS' in l.command('G 2000')
            pointers=l.dump(0x7E00,0x7E1B);assert load_image(l,probes/'irq.s19')==pm['irq']['sha256']
            assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in l.command('G 2000')
            assert l.dump(0x7E00,0x7E1B)==pointers
            checks.append('actual RAM ABI, BRK/VIA1 IRQ, A/X/Y, stack, RTI and pointer preservation')
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                data=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert data==(ROOT_BOARD/f'upgrade/expected-b{bank}.bin').read_bytes(),bank
                (out/f'final-b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest())
            l.command('B3');active('B')
            checks.append('complete four-bank readback matches plan; MON A byte-exact fallback, MON B beta25; B0, CLOCK and unrelated flash unchanged')
        finally:l.serial.close()
    campaign=read(ROOT/'output/qualification/active-rtc-campaign.json');retained=ROOT_BOARD/'retained'
    with serial_lease('beta25-retained-final'):
        power.call(power.array,['--root',str(retained),'--board',BOARD,'--port',PORT,'--stage','final'])
        if restart.get('physical_power_cycle_tested'):
            fresh=retained/'post-power';fresh.mkdir(exist_ok=False)
            power.call(power.devices,['--root',str(fresh),'--board',BOARD,'--port',PORT,'--stage','before','--baseline-index',campaign['baseline_index']])
            before=retained/'devices-before';after=fresh/'devices-before'
            old=(before/'eeprom-0.bin').read_bytes()[:137];new=(after/'eeprom-0.bin').read_bytes()[:137]
            changed=[i for i in range(4) if old[i*32:i*32+32]!=new[i*32:i*32+32]]
            assert len(changed)==1 and old[128:]==new[128:],'Unexpected EEPROM changes'
            slot=changed[0];previous=power.records(old);current=power.records(new)
            assert current[slot]==max(previous.values(),default=0)+1 and new[slot*32+30]==0
            assert (before/'eui.txt').read_bytes()==(after/'eui.txt').read_bytes()
            assert power.calendar(after/'status.txt')>power.calendar(before/'status.txt')
            checks.append('one CRC-valid, next-sequence outage record acknowledged after physical power cycle; all other EEPROM bytes and EUI preserved')
        else:power.call(power.devices,['--root',str(retained),'--board',BOARD,'--port',PORT,'--stage','after','--baseline-index',campaign['baseline_index']])
    checks.append('full 128 KiB SRAM, RTC control/trim, EUI and board name preserved; no time set or SRAM format')
    report=dict(passed=True,board=BOARD,version='2.0b25',generation=37,fallback_version=FALLBACK_VERSION,fallback_generation=FALLBACK_GENERATION,
        updated_slot='B',fallback_slot='A',checks=checks,key_cases=cases,final_flash_hashes=hashes,
        physical_reset_verified=True,physical_power_cycle_tested=restart.get('physical_power_cycle_tested',False),physical_nmi_tested=False,
        physical_boot_capture_complete=not restart.get('physical_power_cycle_boot_captured_without_initial_header',False))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS '+BOARD+' beta25 B / untouched fallback A, hardware regressions, exact flash and retained memory',flush=True)

def wear():
    assert next(p for p in comports() if p.device==PORT).serial_number==SERIALS[BOARD]
    out=ROOT_BOARD/'retest';plan=read(ROOT_BOARD/'upgrade/plan.json')
    with serial_lease('beta25-wear-query'),(out/'wear-serial.jsonl').open('x') as log:
        l=Link(PORT,log)
        try:
            establish_b3(l);assert l.dump(0x7D30,0x7D30)==b'\xB0'
            reply=l.command('W');(out/'wear.txt').write_bytes(reply)
            rows=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',reply);assert len(rows)==32,reply
            counts=[None]*32
            for bank,sector,value in rows:counts[int(bank)*8+int(sector,16)-8]=int(value,16)
            assert counts==plan['counts_after']
            reply=l.command('TIME');(out/'time-after-wear.txt').write_bytes(reply)
            lines=[v for v in reply.split(b'\r\n') if v and v not in (b'TIME',b'B3> ')]
            assert len(lines)==1 and EXPECTED_OFFSET in lines[0] and b'UTC ' not in reply
        finally:l.serial.close()
    p=out/'report.json';r=read(p);r['fixed_f_wear_report_verified']=True
    r['checks'].append('fixed-F W prints all 32 exact planned counts; subsequent local-only TIME reloads correctly; beta25 B remains selected')
    p.write_text(json.dumps(r,indent=2)+'\n');print('PASS '+BOARD+' fixed-F wear report, planned counts and subsequent TIME',flush=True)

def accept_power():
    out=ROOT_BOARD/'physical-reset';data=(out/'boot.txt').read_bytes()
    assert b'PF logged, ACK' in data and data.endswith(PROMPT) and b'SSRAM: PROGRAM' in data
    assert next(p for p in comports() if p.device==PORT).serial_number==SERIALS[BOARD]
    with serial_lease('beta25-power-boot-confirm'),(out/'confirmation-serial.jsonl').open('x') as log:
        l=Link(PORT,log)
        try:
            establish_b3(l);assert l.dump(0x7D30,0x7D30)==b'\xB0'
            boot=l.command('J3');(out/'software-boot-full.txt').write_bytes(boot)
            assert b'STR8-N 2.0b25' in boot and f'gen {FALLBACK_GENERATION:08X} VALID'.encode() in boot and b'gen 00000025 VALID' in boot,boot
        finally:l.serial.close()
    p=ROOT_BOARD/'upgrade/install/reset-pending.json';r=read(p)
    r.update(physical_reset_pending=False,physical_reset_verified=True,physical_power_cycle_tested=True,
        physical_power_cycle_boot_captured_without_initial_header=True)
    p.write_text(json.dumps(r,indent=2)+'\n');print('PASS physical power-on tail and active beta25 B; full software boot validates fallback A and beta25 B',flush=True)

if __name__=='__main__':dict(capture=capture,capture_power=lambda:capture(True),accept_power=accept_power,verify=verify,wear=wear)[ARGS.stage]()
