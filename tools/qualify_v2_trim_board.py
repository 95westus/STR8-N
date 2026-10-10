"""Qualify beta13/CLOCK1.5 while preserving existing trim, UTC and identity."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
from qualify_v2_journal_board import records
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda t:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode())
calendar=lambda t:datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',t)[1].decode(),'%Y-%m-%d %H:%M:%S')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True);p.add_argument('--stage',default='trim-check');p.add_argument('--allow-new-outage',action='store_true');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());out=a.root/a.stage;out.mkdir(exist_ok=False)
    expected=[(a.root/f'upgrade/expected-b{b}.bin').read_bytes() for b in range(4)]
    prior=(a.root/'prior/rtc-prior.txt').read_bytes();ee_prior=(a.root/'eeprom-prior/array.bin').read_bytes();sf=(a.root/'eeprom-prior/status-factory.bin').read_bytes()
    checks=[];report=dict(board=a.board,port=a.port,clock_set=False,trim_changed=False,identity_accepted=False,powerfail_acknowledged=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ');(out/'physical-startup.txt').write_bytes(first)
            if b'CLOCK>' in first or b'BM>' in first:link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',name=None):
                data=link.command(text,prompt);(out/((name or text.replace(' ','-').replace('?','help').lower())+'.txt')).write_bytes(data);return data
            def flash(label):
                hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    (out/f'{label}-b{bank}.bin').write_bytes(data);assert data==expected[bank],f'{label} B{bank} mismatch'
                    hashes.append(sha(data))
                link.command('B3');return hashes
            report['installed_hashes']=flash('installed')
            for slot in ('A','B','A'):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());data=link.until(b'\r\nB3> ')
                (out/f'slot-{len(checks)}-{slot}.txt').write_bytes(data);assert b'STR8-N 2.0b13' in data
                assert b'RTCC: Time unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
                assert b', unbound' not in data and b', changed' not in data
                assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\0\x65\xff\x64'
                checks.append('slot '+slot)
            if a.board=='2609':
                load(link,ROOT/'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19');cmd('G 2400',name='cpu-state');state=link.dump(0x2500,0x2507)
                assert state[0]==1 and state[2:6]==bytes(4);report['cpu_state']=list(state)
            load(link,ROOT/'BUILD/v2-board-regression/service.s19');cmd('G 200C',name='rtc-all-banks')
            assert link.dump(0x2450,0x2453)==bytes([1 if a.board=='2512' else 0])*4
            cmd('G 200F',name='i2c-read');assert link.dump(0x2458,0x245B)[:3]==(bytes((1,0,0)) if a.board=='2512' else bytes((0,1,9)))
            checks.append('public RTC all caller banks and I2C register read')
            protected=link.dump(0x6500,0x66FF)
            for i,command in enumerate(('M 6500 12','G 6504','I 8000 8FFF','F 8000 00','I 9000 9FFF','F 9000 00')):
                data=cmd(command,name=f'guard-{i}');assert b'Protected' in data and link.dump(0x6500,0x66FF)==protected
            checks.append('service RAM and B3:8/9 guards')
            cm=json.loads((ROOT/'BUILD/v2-clock-1.5/build.json').read_text());cmd('R 2 CLOCK L',name='restore-clock')
            assert sha(link.dump(0x2000,cm['end']-1))==cm['sha256']
            load(link,ROOT/'BUILD/v2-time-example/time-example.s19');data=cmd('G 2000',name='time-example')
            assert b'UTC unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            data=cmd('TIME');assert b'RTCC: Time unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            assert b'CLOCK 1.5' in cmd('R CLOCK',b'CLOCK> ',name='clock-start')
            start=time.monotonic();before=cmd('STATUS',b'CLOCK> ',name='status-before')
            cmd('TRIM',b'CLOCK> ',name='trim-display');help_text=cmd('HELP',b'CLOCK> ');assert b'TRIM [-127..+127]' in help_text and b'COARSE [ON' not in help_text
            data=cmd('TRIM 128',b'CLOCK> ',name='trim-invalid');assert b'Invalid command/date' in data and b'Type YES' not in data
            data=cmd('COARSE ON',b'CLOCK> ',name='coarse-rejected');assert b'Invalid command/date' in data and b'Type YES' not in data
            history=cmd('HISTORY',b'CLOCK> ',name='history-preserved');identity=cmd('EUI',b'CLOCK> ')
            if a.board=='2512':
                assert b'RTCC: EUI unavailable' in identity and b'History unavailable/error' in history
                data=cmd('TRIM 0',b'CLOCK> ',name='trim-absent');assert b'Type YES' not in data
            else:
                eui=':'.join(f'{v:02X}' for v in sf[3:9]).encode()
                assert b'RTCC: EUI '+eui+b'\r\n' in identity and b'Remembered EUI: '+eui in identity
                assert raw(prior)[7:9]==raw(before)[7:9]==b'\x80\0'
                cmd('TRIM -20',b'Type YES to confirm: ',name='trim-cancel-warning');assert b'Canceled' in cmd('NO',b'CLOCK> ',name='trim-canceled')
                # Matching zero is read-only in the qualified private service.
                cmd('TRIM 0',b'Type YES to confirm: ',name='trim-zero-warning');data=cmd('YES',b'CLOCK> ',name='trim-zero-verified')
                assert b'Trim 0 steps; coarse OFF; OSCTRIM $00' in data
                report['matching_zero_confirmed']=True
            if a.board!='2512':time.sleep(1.2)
            after=cmd('STATUS',b'CLOCK> ',name='status-after');cmd('Q')
            if a.board!='2512':
                assert raw(after)[7:9]==raw(prior)[7:9] and b'Power-fail latched: no' in after
                assert b'Running: yes' in before and b'Running: yes' in after
                assert 0<(calendar(after)-calendar(before)).total_seconds()<time.monotonic()-start+3
                report.update(eui=eui.decode(),calendar_before=str(calendar(before)),calendar_after=str(calendar(after)),control_trim=raw(after)[7:9].hex())
            checks.append('CLOCK1.5 restore, read-only TRIM/status, malformed/canceled requests, preserved UTC/trim/EUI/history')
            assert b'BANK MAINT 1.7' in cmd('R MAINT',b'BM> ',name='maint-start')
            for i in (8,9):
                data=cmd(f'E 3 {i}',b'BM> ',name=f'maint-guard-{i}');assert b'CANCELED' in data and b'Y to confirm' not in data
            cmd('Q');checks.append('MAINT return and service protection')
            inventories=[]
            for i in range(2):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');cmd('G 2000',name=f'eeprom-probe-{i}');data=link.dump(0x2400,0x2494)
                (out/f'eeprom-final-{i}.bin').write_bytes(data);inventories.append(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            assert inventories[0]==inventories[1]
            unchanged=inventories[0][:128]==ee_prior;new_events=[]
            if a.board!='2512':
                assert inventories[0][0x80:0x89]==sf
                if not unchanged:
                    assert a.allow_new_outage,'Unexpected EEPROM change'
                    old=records(ee_prior);current=records(inventories[0][:128]);last=max((r['sequence'] for r in old),default=0)
                    new_events=[r for r in current if r['sequence']>last]
                    assert len(new_events)==1 and new_events[0]['sequence']==last+1 and new_events[0]['clearance']==0
                    slot=new_events[0]['slot']-1
                    for i in range(4):
                        if i!=slot:assert inventories[0][i*32:(i+1)*32]==ee_prior[i*32:(i+1)*32]
            report['final_hashes']=flash('final');assert report['final_hashes']==plan['expected_hashes']
            report.update(passed=True,checks=checks,eeprom_unchanged=unchanged,new_outage_records=new_events,boot_powerfail_logged_and_acked=bool(new_events),factory_status_unchanged=a.board!='2512',identity_tail_preserved=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            pending=a.root/'upgrade/install/reset-pending.json';r=json.loads(pending.read_text());r.update(physical_reset_pending=False,physical_restart_observed=True,qualification_stage=a.stage);pending.write_text(json.dumps(r,indent=2)+'\n')
            print('PASS',a.board,'beta13/CLOCK1.5, zero trim retained, UTC/EEPROM/EUI preserved, both slots and exact four-bank readbacks')
        finally:link.serial.close()

if __name__=='__main__':main()
