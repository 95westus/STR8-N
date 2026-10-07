"""Read-only RTC/EEPROM archive before flash; never SET or ACK."""
import argparse,json,time,hashlib
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True);p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/'eeprom-prior';out.mkdir(exist_ok=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            start=link.command('',b'> ')
            if b'CLOCK>' in start or b'BM>' in start:link.command('Q')
            link.command('B3');link.command('R CLOCK',b'CLOCK> ')
            status=link.command('STATUS',b'CLOCK> ');(a.root/'prior/rtc-prior.txt').write_bytes(status)
            history=link.command('HISTORY',b'CLOCK> ');(a.root/'prior/history-prior.txt').write_bytes(history)
            link.command('Q')
            images=[]
            for i in range(2):
                load(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000')
                data=link.dump(0x2400,0x2494);(out/f'inventory-{i}.bin').write_bytes(data);images.append(data)
                assert data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            assert images[0]==images[1];data=images[0]
            if a.board=='2512':assert data[0x90] in (1,2,3)
            else:
                assert data[0x90]==0 and b'Running: yes' in status and b'Calendar valid: yes' in status
                prior=(ROOT/f'output/qualification/rtc-journal-2026-10-07/{a.board}/eeprom-prior/status-factory.bin').read_bytes()
                assert data[0x80:0x89]==prior
            (out/'array.bin').write_bytes(data[:128]);(out/'status-factory.bin').write_bytes(data[0x80:0x89])
            (out/'report.json').write_text(json.dumps(dict(board=a.board,port=a.port,passed=True,written=False,status=data[0x90],eeprom_sha256=hashlib.sha256(data[:128]).hexdigest(),factory_hex=data[0x81:0x89].hex()),indent=2)+'\n')
            print('PASS',a.board,'read-only RTC/EEPROM archive; independent reads matched')
        finally:link.serial.close()
if __name__=='__main__':main()
