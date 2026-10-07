"""Qualify outage banner and CLOCK 1.1; archive before one explicit ACK."""
import argparse,json,hashlib,re,time
from datetime import datetime
from pathlib import Path
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from build_v2_rtc_powerfail import OUT
from build_v2_clock_powerfail import OUT as CLOCK
from serial.tools.list_ports import comports


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);p.add_argument('--ack',action='store_true');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());meta=json.loads((OUT/'build.json').read_text());clock=json.loads((CLOCK/'build.json').read_text())
    out=a.root/'powerfail-check';out.mkdir(exist_ok=False);report=dict(board=a.board,port=a.port,clock_set=False,ack_requested=a.ack,slots=[])
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:link.read(max(1,link.serial.in_waiting))
            link.command('',b'> ');link.command('B3')
            for i,slot in enumerate(('A','B','A')):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());output=link.until(b'\r\nB3> ')
                (out/f'slot-{i}-{slot}.txt').write_bytes(output);assert b'STR8-N 2.0b7 B3' in output
                data=link.dump(0x66C0,0x66FF);(out/f'slot-{i}-{slot}.bin').write_bytes(data)
                if a.board=='2512':assert b'RTC unavailable' in output and data[0]==1 and b'[power-fail]' not in output
                else:
                    assert data[0]==0 and data[1]&7==7 and data[1]&8
                    assert b'[power-fail]' in output and b'Power down: 10-07 05:' in output and b'Power up:   10-07 05:' in output
                assert data[56]==data[58] and (data[57]^data[59])&data[56]==0
                report['slots'].append(dict(slot=slot,status=data[0],flags=data[1]))
            archived=link.dump(0x66C0,0x66FF);(out/'before-ack.bin').write_bytes(archived)
            report['archived_outage']=list(archived[20:28]);report['captured_outage']=list(archived[48:56])
            output=link.command('R CLOCK',b'CLOCK> ');(out/'clock-start.txt').write_bytes(output);assert b'CLOCK 1.1' in output
            output=link.command('STATUS',b'CLOCK> ');(out/'clock-status.txt').write_bytes(output)
            if a.board=='2512':
                output=link.command('ACK',b'CLOCK> ');assert b'RTC error 01' in output and b'Type YES' not in output
            else:
                output=link.command('ACK',b'Type YES to confirm: ');(out/'ack-before-confirm.txt').write_bytes(output)
                assert b'Power down:' in output and b'Record the outage' in output
                # This file and serial log exist and are flushed before authorizing ACK.
                if a.ack:
                    t0=time.monotonic()
                    calendar=re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',output)
                    assert calendar
                    before=datetime.strptime(calendar[1].decode(),'%Y-%m-%d %H:%M:%S')
                    output=link.command('YES',b'CLOCK> ');(out/'ack-result.txt').write_bytes(output)
                    assert b'latch verified clear' in output and b'Power-fail latched: no' in output
                    assert b'Captured outage' in output and b'Power down: 10-07 05:' in output
                    output=link.command('ACK',b'CLOCK> ');assert b'nothing cleared' in output and b'Type YES' not in output
                    (out/'ack-no-event.txt').write_bytes(output)
                    report['ack_elapsed_seconds']=time.monotonic()-t0
                    report['calendar_before_ack']=before.isoformat()
                else:
                    output=link.command('NO',b'CLOCK> ');assert b'Canceled' in output
            output=link.command('Q');(out/'clock-return.txt').write_bytes(output)
            data=link.dump(0x66C0,0x66FF);(out/'after-ack.bin').write_bytes(data)
            if a.board!='2512':
                assert data[0]==0 and data[1]&7==7 and data[1]&0x10
                assert data[18:20]==archived[18:20] and data[28] and data[48:56]==archived[48:56]
                if a.ack:
                    assert not data[1]&8 and b'[power-fail]' not in output and b'Power down:' not in output
                    assert data[20:28]==bytes(8)
                    c=data[2:10];after=datetime(c[0]+256*c[1],c[2],c[3],c[5],c[6],c[7])
                    assert 0<=(after-before).total_seconds()<report['ack_elapsed_seconds']+3
                else:assert data[1]&8
            # Verify original saved bytes without executing mutable app state.
            link.command('R 2 CLOCK L');assert hashlib.sha256(link.dump(0x2000,clock['end']-1)).hexdigest()==clock['sha256']
            output=link.command('R MAINT',b'> ');assert b'BANK MAINT 1.6' in output;link.command('Q')
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                image=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));digest=hashlib.sha256(image).hexdigest()
                assert digest==plan['expected_hashes'][bank];(out/f'final-b{bank}.bin').write_bytes(image);hashes.append(digest)
            link.command('B3');report.update(passed=True,final_hashes=hashes,clock_sha256=clock['sha256'],time_trim_unchanged=True,powerfail_after=bool(data[1]&8),retained_capture=bool(data[28]))
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            rp=a.root/'upgrade/install/reset-pending.json';r=json.loads(rp.read_text());r.update(physical_reset_pending=False,physical_reset_confirmed_by_user=True);rp.write_text(json.dumps(r,indent=2)+'\n')
            print('PASS',a.board,'outage banner, CLOCK 1.1 ACK/absence, retained evidence and exact flash')
        finally:link.serial.close()


if __name__=='__main__':main()
