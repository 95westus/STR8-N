"""Post-interrupt integrity checks; preserve clocks, EEPROM, identities and flash."""
import argparse,json,hashlib,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from qualify_v2_rtc_board import load
from install_v2_rtc_upgrade import SERIALS
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--board',required=True);p.add_argument('--port',required=True);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    prior=json.loads((a.root/'report.json').read_text());assert prior['passed']
    nmi=json.loads((a.root/'nmi-check/report.json').read_text());assert nmi['passed'] and nmi['pointers_restored']
    if a.board=='2609':assert json.loads((a.root/'native-check/report.json').read_text())['passed']
    out=a.root/'final-check';out.mkdir(exist_ok=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ')
            if b'CLOCK>' in initial or b'BM>' in initial:link.command('Q')
            link.command('B3')
            report=dict(passed=False,board=a.board,flash_changed=False,clock_set=False,trim_changed=False,powerfail_acknowledged=False)
            if a.board=='2609':
                load(link,ROOT/'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19');data=link.command('G 2400');(out/'cpu-state.txt').write_bytes(data)
                state=link.dump(0x2500,0x2507);assert state[0]==1 and state[2:6]==bytes(4);report['returned_816_emulation_state']=list(state)
            link.command('R CLOCK',b'CLOCK> ');status=link.command('STATUS',b'CLOCK> ');(out/'clock-status.txt').write_bytes(status)
            eui=link.command('EUI',b'CLOCK> ');(out/'clock-eui.txt').write_bytes(eui)
            history=link.command('HISTORY',b'CLOCK> ');(out/'clock-history.txt').write_bytes(history);link.command('Q')
            if a.board!='2512':
                earlier=(a.root/'clock-status-before.txt').read_bytes()
                def calendar(d):return datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',d)[1].decode(),'%Y-%m-%d %H:%M:%S')
                def settings(d):return bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',d)[1].decode())[7:9]
                assert calendar(status)>calendar(earlier) and settings(status)==settings(earlier)
                assert all(x in status for x in (b'Running: yes',b'Backup enabled: yes',b'Power-fail latched: no'))
                report.update(clock_advanced=True,control_trim_unchanged=True)
            else:assert b'RTCC: EUI unavailable' in eui
            ee=[]
            for i in range(2):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000')
                data=link.dump(0x2400,0x2494);(out/f'eeprom-{i}.bin').write_bytes(data);ee.append(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            assert ee[0]==ee[1]
            if a.board!='2512':
                assert ee[0][0x90]==0 and ee[0][:137]==(a.root/'eeprom-before.bin').read_bytes()[:137]
                identity=':'.join(f'{v:02X}' for v in ee[0][0x83:0x89]).encode()
                assert b'RTCC: EUI '+identity+b'\r\n' in eui and b'Remembered EUI: '+identity in eui
                report['eeprom_factory_identity_unchanged']=True
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                assert data==(a.root/f'before-b{bank}.bin').read_bytes();(out/f'b{bank}.bin').write_bytes(data);hashes.append(sha(data))
            link.command('B3');assert hashes==prior['initial_hashes']
            report.update(passed=True,final_hashes=hashes,nmi_passed=True,native_brk_nmi_passed=a.board=='2609')
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            prior.update(manual_nmi_pending=False,physical_nmi_passed=True,native_brk_nmi_passed=a.board=='2609',final_post_interrupt_check_passed=True)
            (a.root/'report.json').write_text(json.dumps(prior,indent=2)+'\n')
            print('PASS',a.board,'post-NMI flash/EEPROM/identity/settings preservation; monitor ready')
        finally:link.serial.close()
if __name__=='__main__':main()
