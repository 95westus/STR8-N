"""Beta14 RAM/service regression; no reset, flash writes, SET, ACK or WORK calls."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,read_application_s19

ROOT=Path(__file__).resolve().parents[1]
PROBES=ROOT/'BUILD/v2-board-regression'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda t:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode())
calendar=lambda t:datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',t)[1].decode(),'%Y-%m-%d %H:%M:%S')

def image_hash(path):
    cells,_=read_application_s19(path)
    return sha(bytes(cells[a] for a in range(min(cells),max(cells)+1)))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--board',required=True,choices=tuple(SERIALS))
    p.add_argument('--port',required=True)
    a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    probes=json.loads((PROBES/'build.json').read_text())['probes']
    service=json.loads((PROBES/'service-build.json').read_text())
    hashes={name:image_hash(PROBES/(name+'.s19')) for name in ('abi','irq','snapshot','service')}
    for name in ('abi','irq'):assert hashes[name]==probes[name]['sha256']
    assert hashes['service']==service['sha256']
    clock=json.loads((ROOT/'BUILD/v2-clock-1.5/build.json').read_text())
    state_path=ROOT/'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19'
    if a.board=='2609':
        state_meta=json.loads((state_path.parent/'build.json').read_text())
        hashes['816-state']=image_hash(state_path)
        assert hashes['816-state']==state_meta['sha256']
    out=a.root/'regression';out.mkdir(exist_ok=False)
    checks=[]
    report=dict(passed=False,board=a.board,port=a.port,version='2.0b14',checks=checks,
        flash_changed=False,clock_set=False,powerfail_acknowledged=False,trim_changed=False,
        software_reset=False,work_invoked=False,physical_nmi_tested=False,probe_hashes=hashes)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ');(out/'start.txt').write_bytes(first)
            if any(prompt in first for prompt in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0F\0\x65\xff\x64'
            policy=link.dump(0x66AE,0x66AF);assert policy[0]==1
            report['managed_reset_latch_before']=policy.hex()
            def preserved():assert link.dump(0x66AE,0x66AF)==policy,'Managed policy/WORK reset latch changed'
            def cmd(text,prompt=b'\r\nB3> ',name=None):
                data=link.command(text,prompt)
                (out/((name or text.replace(' ','-').replace('?','help').lower())+'.txt')).write_bytes(data)
                return data
            def load(name):
                assert load_image(link,PROBES/(name+'.s19'))==hashes[name]
            def io_snapshot(label):
                load('snapshot');cmd('G 2000',name=label)
                data=link.dump(0x2400,0x2405);(out/(label+'.bin')).write_bytes(data)
                return data
            load('abi');assert b'RAM ABI: PASS' in cmd('G 2000',name='ram-abi');preserved()
            checks.append('Bank-safe RAM ABI, capability and board query')
            pointers=link.dump(0x7E00,0x7E1B);via=io_snapshot('io-before-irq')
            (out/'pointers-before-irq.bin').write_bytes(pointers)
            assert via[0]&0x7F==0,'VIA1 interrupts already enabled; IRQ probe refused'
            load('irq');assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in cmd('G 2000',name='brk-irq')
            after_pointers=link.dump(0x7E00,0x7E1B);assert after_pointers==pointers
            (out/'pointers-after-irq.bin').write_bytes(after_pointers)
            after=io_snapshot('io-after-irq')
            assert after[0]&0x7F==0 and after[1:5]==via[1:5]
            assert (after[5]^via[5])&via[4]==0
            preserved();checks.append('Actual BRK/VIA1 timer IRQ; A/X/Y, stack, RTI, pointers, ACR, timer latches and driven Port A restored')
            report['interrupt_pointers_restored']=True;report['via_state_restored']=True
            if a.board=='2609':
                assert load_image(link,state_path)==hashes['816-state']
                cmd('G 2400',name='cpu-state');state=link.dump(0x2500,0x2507)
                assert state[0]==1 and state[2:6]==bytes(4)
                report['returned_816_emulation_state']=list(state)
                preserved();checks.append('816 E=1, D/DBR/PBR=0')
            load('service');data=cmd('G 200C',name='rtc-all-banks')
            assert b'RTC banks preserved' in data
            assert link.dump(0x2450,0x2453)==bytes([1 if a.board=='2512' else 0])*4
            cmd('G 200F',name='i2c-read');bus=link.dump(0x2458,0x245B)
            assert bus[:3]==(bytes((1,0,0)) if a.board=='2512' else bytes((0,1,9)))
            address=service['symbols']['BUS_DATA'];cmd(f'M {address:04X} 57',name='stage-i2c-eeprom-address')
            cmd('G 200F',name='i2c-eeprom-denied');assert link.dump(0x2458,0x245B)[:3]==bytes((6,0,0))
            cmd(f'M {address:04X} 6F',name='restore-i2c-address');preserved()
            checks.append('RTC read in all caller banks, I2C read and raw EEPROM denial')
            protected=link.dump(0x6500,0x66FF)
            for i,command in enumerate(('M 6500 12','G 6504','I 8000 8FFF','F 8000 00',
                    'I 9000 9FFF','F 9000 00','S 3 9000 6200 6201 GUARD','S 2 A000 6500 6501 GUARD')):
                data=cmd(command,name=f'guard-{i}')
                assert any(x in data for x in (b'Protected',b'Bad range',b'Bad args',b'Invalid',b'SR error')),data
                assert link.dump(0x6500,0x66FF)==protected
            preserved();checks.append('Service RAM edit/execute/SAVE and B3:8/9 flash guards reject before mutation')
            assert b'Done' in cmd('R 2 CLOCK L',name='restore-clock')
            assert sha(link.dump(0x2000,clock['end']-1))==clock['sha256']
            data=cmd('TIME',name='monitor-time')
            assert (b'RTCC: Time unavailable' in data) if a.board=='2512' else (b'UTC 2026-' in data)
            assert b'CLOCK 1.5' in cmd('R CLOCK',b'CLOCK> ',name='clock-start')
            start=time.monotonic();before=cmd('STATUS',b'CLOCK> ',name='clock-status-before')
            cmd('TIME',b'CLOCK> ',name='clock-time');cmd('TRIM',b'CLOCK> ',name='clock-trim')
            help_text=cmd('HELP',b'CLOCK> ',name='clock-help')
            assert b'TRIM [-127..+127]' in help_text and b'COARSE [ON' not in help_text
            history=cmd('HISTORY',b'CLOCK> ',name='clock-history-before')
            identity=cmd('EUI',b'CLOCK> ',name='clock-eui')
            for text in ('TRIM 128','COARSE ON'):
                data=cmd(text,b'CLOCK> ',name='clock-invalid-'+text.split()[0].lower())
                assert b'Invalid command/date' in data and b'Type YES' not in data
            if a.board=='2512':
                assert b'RTCC: EUI unavailable' in identity and b'History unavailable/error' in history
                assert b'Type YES' not in cmd('TRIM 0',b'CLOCK> ',name='clock-trim-absent')
            else:
                assert b', changed' not in identity and b', unbound' not in identity
                for slot in range(1,5):cmd(f'SHOW {slot}',b'CLOCK> ',name=f'clock-show-{slot}')
                cmd('TRIM -20',b'Type YES to confirm: ',name='clock-trim-warning')
                assert b'Canceled' in cmd('NO',b'CLOCK> ',name='clock-trim-canceled')
                cmd('CLEAR ALL',b'Type DELETE ALL: ',name='clock-clear-warning')
                assert b'Canceled' in cmd('NO',b'CLOCK> ',name='clock-clear-canceled')
            after=cmd('STATUS',b'CLOCK> ',name='clock-status-after')
            assert cmd('HISTORY',b'CLOCK> ',name='clock-history-after')==history
            cmd('Q');preserved()
            if a.board!='2512':
                assert all(x in before and x in after for x in (b'Running: yes',b'Backup enabled: yes'))
                assert raw(before)[7:9]==raw(after)[7:9]
                assert bool(raw(before)[3]&0x10)==bool(raw(after)[3]&0x10)
                elapsed=(calendar(after)-calendar(before)).total_seconds()
                assert 0<=elapsed<time.monotonic()-start+3
                report['control_trim_unchanged']=True;report['clock_elapsed_seconds']=elapsed
            checks.append('Byte-exact CLOCK1.5 restore; time/EUI/history reads, malformed requests and canceled trim/CLEAR')
            assert b'BANK MAINT 1.7' in cmd('R MAINT',b'BM> ',name='maint-start')
            cmd('M',b'BM> ',name='maint-map')
            for i,text in enumerate(('E 3 8','E 3 9','C R 6400 6401 R 6500')):
                data=cmd(text,b'BM> ',name=f'maint-guard-{i}')
                assert any(x in data for x in (b'CANCELED',b'INVALID',b'PROTECTED')) and b'Y to confirm' not in data
            cmd('Q');preserved();checks.append('MAINT1.7 return, protected sectors and service RAM destination guards')
            report.update(passed=True,managed_reset_latch_after=link.dump(0x66AE,0x66AF).hex(),workspace_latch_preserved=True)
            print('PASS',a.board,'beta14 automated regression:',len(checks),'checks; live workspace context preserved',flush=True)
        except Exception as e:
            report['error']=repr(e);raise
        finally:
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            link.serial.close()

if __name__=='__main__':main()
