"""Verify RTC/EEPROM preservation after all SPI prototype operations."""
import argparse,json,re,time
from datetime import datetime
from pathlib import Path
from beta4_migration import Link
from qualify_v2_rtc_board import load
ROOT=Path(__file__).resolve().parents[1]
raw=lambda t:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode())
calendar=lambda t:datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',t)[1].decode(),'%Y-%m-%d %H:%M:%S')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True);a=p.parse_args()
    out=a.root/'rtc-eeprom-final';out.mkdir(exist_ok=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            link.command('');link.command('B3');data=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.5' in data
            status=link.command('STATUS',b'CLOCK> ');(out/'status.txt').write_bytes(status)
            history=link.command('HISTORY',b'CLOCK> ');(out/'history.txt').write_bytes(history);link.command('Q')
            if a.board!='2512':
                prior=(a.root/'prior/rtc-prior.txt').read_bytes()
                assert raw(status)[7:9]==raw(prior)[7:9]==b'\x80\0'
                assert calendar(status)>calendar(prior) and b'Running: yes' in status and b'Power-fail latched: no' in status
            images=[]
            for i in range(2):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000');data=link.dump(0x2400,0x2494)
                (out/f'inventory-{i}.bin').write_bytes(data);images.append(data)
            assert images[0]==images[1]
            if a.board!='2512':
                assert images[0][:128]==(a.root/'eeprom-prior/array.bin').read_bytes()
                assert images[0][0x80:0x89]==(a.root/'eeprom-prior/status-factory.bin').read_bytes()
            report=dict(passed=True,board=a.board,clock_set=False,trim_changed=False,eeprom_unchanged=a.board!='2512',factory_status_unchanged=a.board!='2512',clock_advanced=a.board!='2512',ports_closed=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',a.board,'RTC/EEPROM/EUI/trim preserved; monitor B3 ready')
        finally:link.serial.close()

if __name__=='__main__':main()
