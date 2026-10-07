"""Arm a RAM-only NMI probe and wait for an operator button press."""
import argparse,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from qualify_v2_rtc_board import load
from install_v2_rtc_upgrade import SERIALS
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--board',required=True);p.add_argument('--port',required=True);p.add_argument('--out',required=True,type=Path);p.add_argument('--native',action='store_true');a=p.parse_args()
    assert not a.native or a.board=='2609'
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    a.out.mkdir(parents=True,exist_ok=False);kind='native' if a.native else 'nmi'
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:link.read(max(1,link.serial.in_waiting))
            start=link.command('',b'> ')
            if b'BM>' in start or b'CLOCK>' in start:link.command('Q')
            link.command('B3');pointers=link.dump(0x7E00,0x7E1B)
            load(link,ROOT/f'BUILD/v2-board-regression/{kind}.s19')
            output=link.command('G 2000',b'PRESS NMI\r\n');(a.out/'armed.txt').write_bytes(output)
            (a.out/'armed.json').write_text(json.dumps(dict(board=a.board,native=a.native,armed=True),indent=2)+'\n')
            print('ARMED',a.board,kind,'PRESS NMI ONCE',flush=True)
            output=link.until(b'\r\nB3> ',150);(a.out/'result.txt').write_bytes(output)
            expected=b'V2 816N BRK/NMI / A-X-Y / FRAME / RTI: PASS' if a.native else b'V2 NMI / A-X-Y / STACK / RTI: PASS'
            passed=expected in output
            assert link.dump(0x7E00,0x7E1B)==pointers
            (a.out/'report.json').write_text(json.dumps(dict(board=a.board,native=a.native,passed=passed,pointers_restored=True,flash_written=False),indent=2)+'\n')
            print('PASS' if passed else 'TIMEOUT/FAIL',a.board,kind,flush=True)
        finally:link.serial.close()
if __name__=='__main__':main()
