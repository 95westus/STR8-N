"""Arm a hash-verified RAM NMI probe; operator presses physical NMI once."""
import argparse
import json
import time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from qualify_v2_spi_install import load_image

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--board', choices=tuple(SERIALS), required=True)
    p.add_argument('--port', required=True)
    p.add_argument('--native', action='store_true')
    a = p.parse_args(); assert not a.native or a.board=='2609'
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    assert json.loads((a.root/'reset-notice-check/report.json').read_text())['passed']
    kind = 'native' if a.native else 'nmi'
    probes = ROOT/'BUILD/v2-board-regression'
    meta = json.loads((probes/'build.json').read_text())['probes'][kind]
    out = a.root/(kind+'-check'); out.mkdir(exist_ok=False)
    report = dict(passed=False, board=a.board, kind=kind, probe_sha256=meta['sha256'], flash_changed=False)
    with (out/'serial.jsonl').open('x') as log:
        link = Link(a.port, log)
        try:
            time.sleep(.3); link.command('', b'> '); link.command('B3')
            pointers = link.dump(0x7E00,0x7E1B)
            assert load_image(link,probes/(kind+'.s19'))==meta['sha256']
            link.send(b'G 2000\r')
            armed = link.until(b'PRESS NMI\r\n',45)
            (out/'armed.txt').write_bytes(armed)
            print('ARMED',a.board,kind,'physical NMI probe; press NMI once now',flush=True)
            result = link.until(b'\r\nB3> ',180)
            (out/'result.txt').write_bytes(result)
            expected = b'V2 816N BRK/NMI / A-X-Y / FRAME / RTI: PASS' if a.native else b'V2 NMI / A-X-Y / STACK / RTI: PASS'
            assert expected in result, result
            assert link.dump(0x7E00,0x7E1B)==pointers
            report.update(passed=True, interrupt_vectors_restored=True, physical_nmi_tested=True)
        except Exception as e:
            report['error']=repr(e); raise
        finally:
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n'); link.serial.close()
    print('PASS',a.board,kind,'physical NMI and restored interrupt vectors',flush=True)


if __name__=='__main__': main()
