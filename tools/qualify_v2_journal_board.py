"""Archive and qualify the EEPROM journal without setting RTC time."""
import argparse, binascii, hashlib, json, re, time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load

ROOT=Path(__file__).resolve().parents[1]

def records(data):
    result=[]
    for i in range(4):
        r=data[i*32:(i+1)*32]
        if (r[:8]==b'PF\x01'+bytes((i+1,))+b'JR\x20\xa5'
                and r[31]==0xa5 and binascii.crc_hqx(r[:28],0xffff)==int.from_bytes(r[28:30],'little')):
            result.append(dict(slot=i+1,sequence=int.from_bytes(r[8:12],'little'),outage=r[12:20].hex(),capture=r[20:28].hex(),clearance=r[30]))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True)
    p.add_argument('--stage',default='journal-check');p.add_argument('--initialize',action='store_true');p.add_argument('--flash-check',action='store_true')
    a=p.parse_args();assert not a.initialize or a.board=='2205'
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/a.stage;out.mkdir(exist_ok=False)
    report=dict(board=a.board,stage=a.stage,clock_set=False,trim_written=False,initialized=a.initialize)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            start=link.command('',b'> ')
            if b'CLOCK>' in start:link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'CLOCK> ',name=None):
                output=link.command(text,prompt);(out/((name or text.replace(' ','-').lower())+'.txt')).write_bytes(output)
                return output
            def inventory(name):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000')
                data=link.dump(0x2400,0x2494);(out/(name+'.bin')).write_bytes(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
                if a.board=='2512':assert data[0x90] in (1,2,3)
                else:
                    assert data[0x90]==0
                    prior=(a.root/'eeprom-prior/status-factory.bin').read_bytes()
                    assert data[0x80:0x89]==prior
                return data
            before=inventory('eeprom-before')
            for i,slot in enumerate(('A','B')):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());output=link.until(b'\r\nB3> ')
                (out/f'slot-{slot}.txt').write_bytes(output);assert b'STR8-N 2.0b8 B3' in output
                assert (b'RTC unavailable' in output) if a.board=='2512' else (b'UTC 2026-' in output)
            assert link.dump(0x7D19,0x7D20)==b'PJ\x01\x01\x04\x90\x00\x6B'
            output=cmd('R CLOCK',name='clock-start');assert b'CLOCK 1.2' in output
            started=time.monotonic();status=cmd('STATUS',name='status-before')
            history=cmd('HISTORY',name='history-before')
            if a.board=='2512':
                assert b'History unavailable/error' in history
                cmd('SHOW 1');cmd('CLEAR 1');cmd('ACK');cmd('Q',b'\r\nB3> ')
            else:
                assert b'Running: yes' in status and b'Calendar valid: yes' in status
                if a.initialize:
                    assert b'error 90' in history
                    cmd('CLEAR ALL',b'Type DELETE ALL: ',name='initialize-warning')
                    output=cmd('DELETE ALL',name='initialize-result');assert b'History cleared' in output
                    history=cmd('HISTORY',name='history-initialized');assert b'No saved event' in history
                    output=cmd('ACK',b'Type YES to confirm: ',name='ack-warning')
                    assert b'UTC time keeps running unchanged.' in output
                    output=cmd('YES',name='ack-result');assert b'latch verified clear' in output
                output=cmd('HISTORY',name='history-after');assert b'seq ' in output and b'latch cleared' in output
                slot=int(re.search(rb'Slot ([1-4]) seq ',output)[1])
                cmd(f'SHOW {slot}',name='show-event')
                cmd(f'CLEAR {slot}',b'Type YES: ',name='clear-warning')
                output=cmd('NO',name='clear-cancel');assert b'Canceled' in output
                cmd('CLEAR ALL',b'Type DELETE ALL: ',name='clear-all-warning')
                output=cmd('NO',name='clear-all-cancel');assert b'Canceled' in output
                output=cmd('ACK',name='ack-no-event');assert b'nothing cleared' in output
                output=cmd('STATUS',name='status-after');assert b'Power-fail latched: no' in output and b'Running: yes' in output
                def calendar(text):
                    match=re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',text)
                    return datetime.strptime(match[1].decode(),'%Y-%m-%d %H:%M:%S')
                first,last=calendar(status),calendar(output)
                assert 0<=(last-first).total_seconds()<time.monotonic()-started+3
                report.update(calendar_before=first.isoformat(),calendar_after=last.isoformat(),utc_advancement_verified=True)
                cmd('Q',b'\r\nB3> ')
            after=inventory('eeprom-after');again=inventory('eeprom-repeat');assert after==again
            if a.board!='2512':
                assert after[0x80:0x89]==before[0x80:0x89]
                report['records']=records(after[:128]);assert report['records'] and all(r['clearance']==0 for r in report['records'])
                if not a.initialize:assert after[:128]==before[:128]
            if a.flash_check:
                plan=json.loads((a.root/'upgrade/plan.json').read_text());hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    image=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    digest=hashlib.sha256(image).hexdigest();assert digest==plan['expected_hashes'][bank]
                    (out/f'final-b{bank}.bin').write_bytes(image);hashes.append(digest)
                link.command('B3');report['final_hashes']=hashes
            report.update(passed=True,factory_status_unchanged=True,eeprom_sha256=hashlib.sha256(after[:128]).hexdigest())
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            pending=a.root/'upgrade/install/reset-pending.json'
            r=json.loads(pending.read_text());r.update(physical_reset_pending=False,physical_reset_confirmed_by_user=True);pending.write_text(json.dumps(r,indent=2)+'\n')
            print('PASS',a.board,a.stage,report.get('records',[]))
        finally:link.serial.close()

if __name__=='__main__':main()
