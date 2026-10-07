"""On-board beta12 regression: RAM probes, services, guards and exact preservation."""
import argparse,json,hashlib,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s_record
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',required=True);p.add_argument('--port',required=True);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.out;out.mkdir(parents=True,exist_ok=False);checks=[]
    accepted=ROOT/f'output/qualification/rtc-binding-2026-10-07/{a.board}/binding-check'
    expected=[(accepted/f'final-b{b}.bin').read_bytes() for b in range(4)]
    probes=json.loads((ROOT/'BUILD/v2-board-regression/build.json').read_text())['probes']
    kernel=json.loads((ROOT/'BUILD/v2-board-regression/service-build.json').read_text())
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            start=link.command('',b'> ')
            if b'CLOCK>' in start or b'BM>' in start:link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',name=None):
                data=link.command(text,prompt);(out/((name or text.replace(' ','-').replace('?','help').lower())+'.txt')).write_bytes(data);return data
            def flash(label):
                hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    assert data==expected[bank],f'{label} B{bank} changed';(out/f'{label}-b{bank}.bin').write_bytes(data);hashes.append(sha(data))
                link.command('B3');return hashes
            hashes=flash('before')
            def inventory(label):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');cmd('G 2000',name=label+'-probe')
                data=link.dump(0x2400,0x2494);(out/(label+'.bin')).write_bytes(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
                assert data[0x90] in ((1,2,3) if a.board=='2512' else (0,))
                return data
            before_ee=inventory('eeprom-before')
            for slot in ('A','B','A'):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());data=link.until(b'\r\nB3> ')
                (out/f'slot-{len(checks)}-{slot}.txt').write_bytes(data);assert b'STR8-N 2.0b12' in data
                active=link.dump(0x7D30,0x7D30);assert active==bytes((0xA0 if slot=='A' else 0xB0,))
                assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\0\x65\xff\x64'
                checks.append('monitor slot '+slot)
            for command in ('?','C','P','W','T 1','T 2','APPS','M 1','M 2','M 3'):
                cmd(command,name='monitor-'+command.replace(' ','-').replace('?','help'))
            load(link,ROOT/'BUILD/v2-board-regression/abi.s19');data=cmd('G 2000',name='ram-abi');assert b'RAM ABI: PASS' in data
            checks.append('bank-safe RAM ABI, capability and board query')
            # Actual BRK plus hardware VIA1 timer IRQ, with complete restoration.
            def io_snapshot(label):
                load(link,ROOT/'BUILD/v2-board-regression/snapshot.s19');cmd('G 2000',name=label)
                return link.dump(0x2400,0x2405)
            vectors=link.dump(0x7E00,0x7E1B);via=io_snapshot('io-before-irq')
            assert via[0]&0x7F==0,'VIA interrupts active: IRQ probe cannot safely run'
            load(link,ROOT/'BUILD/v2-board-regression/irq.s19');data=cmd('G 2000',name='brk-irq')
            assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in data
            assert link.dump(0x7E00,0x7E1B)==vectors
            after=io_snapshot('io-after-irq');assert after[1:4]==via[1:4] and after[0]&0x7F==0 and after[4]==via[4]
            checks.append('physical BRK/VIA1 timer IRQ; registers, stack, RTI and pointers/latches restored')
            if a.board=='2609':
                load(link,ROOT/'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19');cmd('G 2400',name='cpu-state')
                state=link.dump(0x2500,0x2507);assert state[0]==1 and state[2:6]==bytes(4)
                checks.append('816 emulation entry: E=1, D/DBR/PBR=0')
            # RAM edit/execute and rejection of an unverified S19 record.
            original=link.dump(0x5F00,0x5F07);cmd('M 5F00 11 22 33 44 55 66 77 88')
            assert link.dump(0x5F00,0x5F07)==bytes.fromhex('1122334455667788')
            cmd('M 2000 A9 5A 8D 07 5F 4C 67 7E');cmd('G 2000',name='ram-execute');assert link.dump(0x5F07,0x5F07)==b'\x5a'
            old=link.dump(0x5F00,0x5F00);link.command('L',b'S19')
            record=s_record('1',0x5F00,b'\xaa');bad=record[:-2]+f'{int(record[-2:],16)^1:02X}'
            link.send(bad.encode()+b'\r\n');data=link.until(b'\r\nB3> ');(out/'s19-bad-checksum.txt').write_bytes(data)
            assert b'sum' in data.lower() and link.dump(0x5F00,0x5F00)==old
            cmd('M 5F00 '+' '.join(f'{v:02X}' for v in original));checks.append('RAM edit/execute, atomic bad-S19 rejection and scratch restoration')
            # Program clients and public I2C in each overlay.
            load(link,ROOT/'BUILD/v2-board-regression/service.s19')
            cmd('G 200C',name='rtc-all-banks');assert link.dump(0x2450,0x2453)==bytes([1 if a.board=='2512' else 0])*4
            cmd('G 200F',name='i2c-read');bus=link.dump(0x2458,0x245B)
            assert bus[:3]==(bytes((1,0,0)) if a.board=='2512' else bytes((0,1,9)))
            address=kernel['symbols']['BUS_DATA'];cmd(f'M {address:04X} 57');cmd('G 200F',name='i2c-eeprom-denied')
            assert link.dump(0x2458,0x245B)[:3]==bytes((6,0,0))
            checks.append('RTC caller banks; managed I2C reads and raw EEPROM denial')
            protected=link.dump(0x6500,0x66FF)
            for i,command in enumerate(('M 6500 12','G 6504','I 8000 8FFF','F 8000 00','I 9000 9FFF','F 9000 00','S 3 9000 6200 6201 GUARD','S 2 A000 6500 6501 GUARD')):
                data=cmd(command,name=f'guard-{i}')
                assert any(x in data for x in (b'Protected',b'Bad range',b'Bad args',b'Invalid',b'SR error')),data
                assert link.dump(0x6500,0x66FF)==protected
            checks.append('service-RAM execute/edit/SAVE guards and B3:8/9 flash guards')
            # Saved records restore byte-exactly without executing the loaded program.
            for name,bank,path in (('CLOCK',2,'BUILD/v2-clock-1.4/build.json'),('MAINT',1,'BUILD/v2-rtc-binding/maint/manifest.json')):
                cmd(f'R {bank} {name} L',name='restore-'+name.lower())
                meta=json.loads((ROOT/path).read_text());end=meta['end']
                assert sha(link.dump(0x2000,end-1))==meta.get('sha256',meta.get('program_sha256'))
            data=cmd('R MAINT',b'BM> ',name='maint');assert b'BANK MAINT 1.7' in data
            for i,command in enumerate(('M','E 3 8','E 3 9','C R 6400 6401 R 6500')):
                data=cmd(command,b'BM> ',name=f'maint-{i}')
                if i:assert any(x in data for x in (b'CANCELED',b'INVALID',b'PROTECTED')) and b'Y to confirm' not in data
            cmd('Q');checks.append('CLOCK/MAINT byte-exact RESTORE, maps and service ownership guards')
            load(link,ROOT/'BUILD/v2-time-example/time-example.s19');data=cmd('G 2000',name='time-example')
            assert b'UTC unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            data=cmd('TIME');assert b'RTCC: Time unavailable' in data if a.board=='2512' else b'UTC 2026-' in data
            data=cmd('R CLOCK',b'CLOCK> ',name='clock');assert b'CLOCK 1.4' in data
            before_status=cmd('STATUS',b'CLOCK> ',name='clock-status-before');cmd('HELP',b'CLOCK> ');cmd('TIME',b'CLOCK> ')
            identity=cmd('EUI',b'CLOCK> ');history=cmd('HISTORY',b'CLOCK> ')
            if a.board!='2512':
                sf=before_ee[0x80:0x89];eui=':'.join(f'{v:02X}' for v in sf[3:9]).encode()
                assert b'RTCC: EUI '+eui+b'\r\n' in identity and b'Remembered EUI: '+eui in identity
                data=cmd('ACCEPT EUI',b'CLOCK> ',name='clock-eui-no-change');assert b'already remembered' in data and b'Type YES' not in data
                for i in range(1,5):cmd(f'SHOW {i}',b'CLOCK> ',name=f'journal-show-{i}')
                cmd('CLEAR ALL',b'Type DELETE ALL: ',name='clear-all-warning');assert b'Canceled' in cmd('NO',b'CLOCK> ',name='clear-all-cancel')
                cmd('SET 2026-10-07 01:02:03',b'Type YES to confirm: ',name='set-warning');assert b'Canceled' in cmd('NO',b'CLOCK> ',name='set-cancel')
                data=cmd('SET 2026-02-29 00:00:00',b'CLOCK> ',name='set-invalid');assert b'Invalid command/date' in data and b'Type YES' not in data
            else:
                assert b'EUI unavailable' in identity and b'History unavailable/error' in history
                for command in ('ACK','ACCEPT EUI','SET 2026-10-07 01:02:03'):
                    data=cmd(command,b'CLOCK> ',name='absent-'+command.split()[0].lower());assert b'Type YES' not in data
            after_status=cmd('STATUS',b'CLOCK> ',name='clock-status-after');cmd('Q')
            if a.board!='2512':
                assert b'Running: yes' in before_status and b'Running: yes' in after_status and b'Power-fail latched: no' in after_status
                raw=lambda d:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',d)[1].decode())
                assert raw(before_status)[7:9]==raw(after_status)[7:9]
            checks.append('CLOCK/EUI/history, canceled administration, malformed SET and optional-device behavior')
            after_ee=inventory('eeprom-after');again=inventory('eeprom-repeat');assert after_ee==again
            if a.board!='2512':assert before_ee[:0x89]==after_ee[:0x89]
            final_hashes=flash('after');assert final_hashes==hashes
            report=dict(passed=True,board=a.board,port=a.port,checks=checks,flash_changed=False,clock_set=False,powerfail_acknowledged=False,trim_changed=False,
                eeprom_and_factory_unchanged=a.board!='2512',initial_hashes=hashes,final_hashes=final_hashes,manual_nmi_pending=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',a.board,'on-board automated regression:',len(checks),'checks; flash/EEPROM/time settings preserved')
        finally:link.serial.close()
if __name__=='__main__':main()
