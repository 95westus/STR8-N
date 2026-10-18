"""2609-only physical mixed-monitor and retained-memory qualification."""
import json,re,sys,time,hashlib
from beta4_migration import Link
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from deploy_v2_beta25 import ROOT,BASE,BUILD,BOARD,read
from qualify_v2_spi_install import load_image
import qualify_v2_beta24_power as power
import run_beta23_soak as smoke
from serial.tools.list_ports import comports
from rtc_boards import SERIALS

PROMPT=b'\r\nB3> ';MENU=b'Enter default [3s]: ';ROOT_BOARD=BASE/BOARD

def capture():
    assert next(p for p in comports() if p.device=='COM8').serial_number==SERIALS[BOARD]
    out=ROOT_BOARD/'physical-reset';out.mkdir(exist_ok=False)
    with serial_lease('beta25-reset-capture'),(out/'serial.jsonl').open('x') as log:
        l=Link('COM8',log)
        try:
            print('ARMED: receive-only physical RESET capture on 2609 for 15 minutes',flush=True)
            data=l.until(PROMPT,900);(out/'boot.txt').write_bytes(data)
            assert b'STR8-N 2.0b25' in data and b'gen 00000023 VALID' in data and b'gen 00000025 VALID' in data,data
            p=ROOT_BOARD/'upgrade/install/reset-pending.json';r=read(p);r.update(physical_reset_pending=False,physical_reset_verified=True)
            p.write_text(json.dumps(r,indent=2)+'\n');print('PASS 2609 physical RESET: beta24 A and beta25 B valid; beta25 default',flush=True)
        finally:l.serial.close()

def verify():
    assert next(p for p in comports() if p.device=='COM8').serial_number==SERIALS[BOARD]
    assert read(ROOT_BOARD/'upgrade/install/reset-pending.json')['physical_reset_verified']
    out=ROOT_BOARD/'retest';out.mkdir(exist_ok=False);checks=[];cases=[]
    with serial_lease('beta25-hardware-retest'),(out/'serial.jsonl').open('x') as log:
        l=Link('COM8',log)
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
                version=b'2.0b24' if slot=='A' else b'2.0b25';assert b'STR8-N '+version in text,text
                i=len(cases);(out/f'boot-{i:02d}.txt').write_bytes(text)
                cases.append(dict(key_hex=key.hex() if key else None,choice=choice,recovery=recovery,slot=slot,version=version.decode(),passed=True))
            for key in (b'A',b'a',b'B',b'b'):reboot(key)
            for key,slot in ((b'\x1b','A'),(b'x','B'),(b'\r','A')):reboot(key,slot)
            reboot(b'\x1b',recovery=True);reboot()
            checks.append('fresh A/a beta24 and B/b beta25; ESC/other key retains menu; F recovery A; no-key defaults to beta25')
            for key in (b'A',b'B',b'\x1b'):
                l.send(b'J3\r'+key);text=l.until(PROMPT)
                assert text.split(b'MONITOR ')[0].count(b'.')==160 and MENU in text;active('B')
                (out/('stale-'+key.hex()+'.txt')).write_bytes(text)
            checks.append('queued A/B/ESC discarded before input window; 160 dots and beta25 default retained')
            for slot in ('A','B'):
                reboot(slot.encode());smoke.guards(l);results=[]
                text=l.command('APPS');assert b'\xff' not in text and b' installed' not in text
                text=l.command('TIME');lines=[v for v in text.split(b'\r\n') if v and v not in (b'TIME',b'B3> ')]
                assert len(lines)==1 and re.fullmatch(rb'[A-Z][a-z]{2} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d \(-05:00\)',lines[0]),text
                (out/f'time-{slot}.txt').write_bytes(text)
                old=l.dump(0x3E20,0x3E22)
                try:l.write_ram(0x3E20,b'\x01\x03\0')
                finally:l.write_ram(0x3E20,old)
                for group in ('monitor','clock','edu','sram','work','maint'):results.append(dict(group=group,replies=smoke.commands(l,group)))
                active(slot);(out/f'commands-{slot}.json').write_text(json.dumps(results,indent=2)+'\n')
                transcript=l.command('R MAINT',b'BM> ')+l.command('NAME',b'BM> ')+l.command('Q')
                assert b'2609' in transcript
            checks.append('both versions: local-only TIME, APPS, RAM edit, CLOCK, EDU, SRAM, WORK, MAINT and retained name; HOLD retains selected slot')
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
            checks.append('complete four-bank readback matches plan; MON A byte-exact beta24, MON B beta25; B0/B1 and unrelated flash unchanged')
        finally:l.serial.close()
    campaign=read(ROOT/'output/qualification/active-rtc-campaign.json');retained=ROOT_BOARD/'retained'
    with serial_lease('beta25-retained-final'):
        power.call(power.array,['--root',str(retained),'--board',BOARD,'--port','COM8','--stage','final'])
        power.call(power.devices,['--root',str(retained),'--board',BOARD,'--port','COM8','--stage','after','--baseline-index',campaign['baseline_index']])
    checks.append('full 128 KiB SRAM, EEPROM/history/EUI, RTC control/trim and board name preserved; no time set or SRAM format')
    report=dict(passed=True,board=BOARD,version='2.0b25',generation=37,fallback_version='2.0b24',fallback_generation=35,
        updated_slot='B',fallback_slot='A',checks=checks,key_cases=cases,final_flash_hashes=hashes,
        physical_reset_verified=True,physical_power_cycle_tested=False,physical_nmi_tested=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS 2609 beta25 B / untouched beta24 A, hardware regressions, exact flash and retained memory',flush=True)

def wear():
    assert next(p for p in comports() if p.device=='COM8').serial_number==SERIALS[BOARD]
    out=ROOT_BOARD/'retest';plan=read(ROOT_BOARD/'upgrade/plan.json')
    with serial_lease('beta25-wear-query'),(out/'wear-serial.jsonl').open('x') as log:
        l=Link('COM8',log)
        try:
            establish_b3(l);assert l.dump(0x7D30,0x7D30)==b'\xB0'
            reply=l.command('W');(out/'wear.txt').write_bytes(reply)
            rows=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',reply);assert len(rows)==32,reply
            counts=[None]*32
            for bank,sector,value in rows:counts[int(bank)*8+int(sector,16)-8]=int(value,16)
            assert counts==plan['counts_after']
            reply=l.command('TIME');(out/'time-after-wear.txt').write_bytes(reply)
            lines=[v for v in reply.split(b'\r\n') if v and v not in (b'TIME',b'B3> ')]
            assert len(lines)==1 and b'(-05:00)' in lines[0] and b'UTC ' not in reply
        finally:l.serial.close()
    p=out/'report.json';r=read(p);r['fixed_f_wear_report_verified']=True
    r['checks'].append('fixed-F W prints all 32 exact planned counts; subsequent local-only TIME reloads correctly; beta25 B remains selected')
    p.write_text(json.dumps(r,indent=2)+'\n');print('PASS 2609 fixed-F wear report, planned counts and subsequent TIME',flush=True)

if __name__=='__main__':dict(capture=capture,verify=verify,wear=wear)[sys.argv[1]]()
