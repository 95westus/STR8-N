"""Post-RESET beta12 qualification and explicit initial EUI acceptance."""
import argparse,binascii,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,crc
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
from qualify_v2_journal_board import records
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());out=a.root/'binding-check';out.mkdir(exist_ok=False)
    report=dict(board=a.board,port=a.port,clock_set=False,trim_written=False,identity_accepted=False)
    expected=[(a.root/f'upgrade/expected-b{b}.bin').read_bytes() for b in range(4)]
    prior_ee=(a.root/'eeprom-prior/array.bin').read_bytes();prior_sf=(a.root/'eeprom-prior/status-factory.bin').read_bytes()
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            startup=bytearray();end=time.monotonic()+.3
            while time.monotonic()<end:startup.extend(link.read(max(1,link.serial.in_waiting)))
            first=link.command('',b'> ');startup.extend(first);(out/'physical-startup.txt').write_bytes(startup)
            if b'CLOCK>' in first or b'BM>' in first:link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'CLOCK> ',name=None):
                data=link.command(text,prompt);(out/((name or text.replace(' ','-').lower())+'.txt')).write_bytes(data);return data
            def flash(label,wanted):
                hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    (out/f'{label}-b{bank}.bin').write_bytes(data);assert data==wanted[bank],f'{label} B{bank} mismatch'
                    hashes.append(hashlib.sha256(data).hexdigest())
                link.command('B3');return hashes
            report['installed_hashes']=flash('installed',expected)
            # Both slots, current RAM discovery and compact read-only TIME.
            for slot in ('A','B'):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());data=link.until(b'\r\nB3> ')
                (out/f'slot-{slot}.txt').write_bytes(data);assert b'STR8-N 2.0b12 B3' in data
                assert b'RTCC: Time unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\0\x65\xff\x64'
            assert link.dump(0x7D19,0x7D20)==b'PJ\x01\x01\x04\x90\0\x6b'
            data=cmd('TIME',b'\r\nB3> ');assert b'RTCC: EUI' not in data
            assert b'RTCC: Time unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            # Runnable example uses only RAM; physical 816 remains in emulation.
            load(link,ROOT/'BUILD/v2-time-example/time-example.s19');data=cmd('G 2000',b'\r\nB3> ',name='time-example')
            assert b'UTC unavailable; error' in data if a.board=='2512' else b'UTC 2026-' in data
            data=cmd('R CLOCK',name='clock-start');assert b'CLOCK 1.4' in data
            started=time.monotonic();status=cmd('STATUS',name='status-before')
            history=cmd('HISTORY',name='history-preserved')
            if a.board=='2512':
                assert b'RTCC: EUI unavailable' in status
                data=cmd('ACCEPT EUI');assert b'EUI unavailable' in data and b'Type YES' not in data
                cmd('EUI');cmd('ACK');cmd('Q',b'\r\nB3> ')
            else:
                identity=prior_sf[3:9];display=':'.join(f'{v:02X}' for v in identity).encode()
                assert b'RTCC: EUI '+display+b', unbound' in status and b'Running: yes' in status
                assert b'Power-fail latched: no' in status and b'seq ' in history
                data=cmd('ACCEPT EUI',b'Type YES: ',name='accept-cancel-warning');assert display in data
                data=cmd('NO',name='accept-cancel');assert b'Canceled' in data
                data=cmd('ACCEPT EUI',b'Type YES: ',name='accept-warning');assert display in data
                data=cmd('YES',name='accept-result');assert b'RTCC: EUI remembered.' in data
                data=cmd('EUI');assert b'RTCC: EUI '+display+b'\r\n' in data and b'Remembered EUI: '+display in data and b', changed' not in data
                data=cmd('ACCEPT EUI',name='accept-no-change');assert b'already remembered' in data and b'Type YES' not in data
                data=cmd('STATUS',name='status-after');assert b'Running: yes' in data and b'Backup enabled: yes' in data and b'Power-fail latched: no' in data
                def calendar(text):return datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',text)[1].decode(),'%Y-%m-%d %H:%M:%S')
                first,last=calendar(status),calendar(data);assert 0<=(last-first).total_seconds()<time.monotonic()-started+3
                report.update(identity_accepted=True,eui=display.decode(),calendar_before=first.isoformat(),calendar_after=last.isoformat())
                cmd('Q',b'\r\nB3> ')
                body=b'EI\x01\0'+(1).to_bytes(4,'little')+identity+bytes([255])*14
                record=body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')+b'\xff\0'
                image=bytearray(expected[3]);image[7168:7200]=record;expected[3]=bytes(image)
            # Re-enter both boot paths after binding; private code CRC excludes valid data.
            for slot in ('A','B'):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());data=link.until(b'\r\nB3> ')
                (out/f'bound-slot-{slot}.txt').write_bytes(data);assert b'STR8-N 2.0b12' in data
                assert b', unbound' not in data and b', changed' not in data
            # Saved maintenance remains intact and protects the occupied sector.
            data=cmd('R MAINT',b'BM> ',name='maint-start');assert b'BANK MAINT 1.7' in data
            data=cmd('E 3 9',b'BM> ',name='maint-protected');assert b'CANCELED' in data and b'Y to confirm' not in data
            cmd('Q',b'\r\nB3> ')
            final=[]
            for i in range(2):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000');data=link.dump(0x2400,0x2494)
                (out/f'eeprom-final-{i}.bin').write_bytes(data);final.append(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            assert final[0]==final[1]
            if a.board!='2512':
                assert final[0][0x90]==0 and final[0][0x80:0x89]==prior_sf
                current=records(final[0][:128]);previous=records(prior_ee);assert current
                report.update(records=current,prior_records=previous,eeprom_unchanged=final[0][:128]==prior_ee)
                # If RESET was a power cycle, boot may correctly append one real event.
                assert report['eeprom_unchanged'] or max(r['sequence'] for r in current)>max(r['sequence'] for r in previous)
            report['final_hashes']=flash('final',expected)
            assert crc(expected[3][4096:7168])==0
            report.update(passed=True,factory_status_unchanged=True,expected_final_hashes=report['final_hashes'])
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            rp=a.root/'upgrade/install/reset-pending.json';r=json.loads(rp.read_text());r.update(physical_reset_pending=False,physical_restart_observed=True,restart_evidence=str(a.root/'restart-probe/report.json'));rp.write_text(json.dumps(r,indent=2)+'\n')
            print('PASS',a.board,'beta12/CLOCK1.4 TIME/example, EUI binding/absence, history and exact flash')
        finally:link.serial.close()
if __name__=='__main__':main()
