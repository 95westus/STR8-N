"""Buffered live help/R/V probe acceptance and three refusal conditions."""
import tempfile
from pathlib import Path
import board_b11_2512 as board
from build_b11 import HELP

def main():
    rows=[]
    for fault in (None,'?','R','V'):
        class Peer:
            def command(self,key,prompt):
                if key==fault:return b'REFUSED: timeout\r\nREC> '
                return (HELP if key=='?' else b'REFUSED: no valid RAM image\r\n')+b'REC> '
        with tempfile.TemporaryDirectory(prefix='b11-help-probe-',dir=board.ROOT/'tmp') as folder:
            try:board.b11_help_probe(Peer(),Path(folder))
            except ValueError:assert fault is not None and not (Path(folder)/'b11-help-fresh.json').exists()
            else:assert fault is None and board.r.read(Path(folder)/'b11-help-fresh.json')['R_V_no_valid_RAM_image']
        rows.append(dict(case=fault or 'help-and-precise-RV',passed=True))
    assert 'serial' not in __import__('sys').modules
    board.save(board.ROOT/'BUILD/pr04-b11-help-r7/b11-help-probe-host-tests.json',dict(passed=True,hardware=False,serial_access=False,
        checks=len(rows),cases=rows,adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),checker_sha256=board.r.sha(Path(__file__).read_bytes())))
    print('PASS live help probe buffered checks',len(rows),flush=True)

if __name__=='__main__':main()
