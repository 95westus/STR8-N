"""Verify saved MAINT and sector-9 refusal; never authorize flash operations."""
import argparse, hashlib, json, time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);a=p.parse_args()
    for board,port in (('2512','COM4'),('2205','COM3'),('2609','COM8')):
        assert next(x for x in comports() if x.device.upper()==port).serial_number==SERIALS[board]
        root=a.root/board;out=root/'maintenance-check';out.mkdir(exist_ok=False)
        with (out/'serial.jsonl').open('x') as log:
            link=Link(port,log)
            try:
                end=time.monotonic()+.3
                while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
                output=link.command('',b'> ')
                if b'BM>' in output or b'CLOCK>' in output:link.command('Q')
                link.command('B3')
                output=link.command('R MAINT',b'BM> ');(out/'start.txt').write_bytes(output)
                assert b'STR8-N BANK MAINT 1.7' in output
                output=link.command('E 3 9',b'BM> ');(out/'protected.txt').write_bytes(output)
                assert b'CANCELED' in output and b'Y to confirm' not in output
                link.command('Q')
                sector=link.dump(0x9000,0x9FFF);(out/'journal-sector.bin').write_bytes(sector)
                assert sector==(root/'powercycle-check/final-b3.bin').read_bytes()[4096:8192]
                output=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.2' in output
                output=link.command('HISTORY',b'CLOCK> ');(out/'history-after.txt').write_bytes(output)
                if board=='2512':assert b'History unavailable/error' in output
                else:assert b'seq 00000002' in output and b'seq 00000001' in output
                link.command('Q')
                (out/'report.json').write_text(json.dumps(dict(passed=True,board=board,version='1.7',sector_9_refused=True,flash_write_authorized=False,journal_sha256=hashlib.sha256(sector).hexdigest()),indent=2)+'\n')
                print('PASS',board,'MAINT 1.7, journal-sector protection and CLOCK return')
            finally:link.serial.close()

if __name__=='__main__':main()
