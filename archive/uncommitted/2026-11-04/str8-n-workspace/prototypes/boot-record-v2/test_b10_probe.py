"""Buffered tests of the live wait/cancel probe; no serial import or device."""
from pathlib import Path
import tempfile
from unittest.mock import patch
import board_b10_2512 as board


def main():
    rows=[]
    for fault in (None,'premature-RX','cancel-refused'):
        class Peer:
            pending=bytearray()
            sent=[]
            def command(self,text,prompt):assert text=='L';return b'L\r\nSEND HEADER+BIN\r\n'
            def read(self,count):return b'REFUSED: timeout' if fault=='premature-RX' else b''
            def send(self,data):self.sent.append(data)
            def until(self,prompt):return b'REFUSED\r\nREC> ' if fault=='cancel-refused' else b'REC> '
        tick=[0.0]
        def clock():tick[0]+=.25;return tick[0]
        peer=Peer()
        with tempfile.TemporaryDirectory(prefix='b10-probe-',dir=board.ROOT/'tmp') as folder:
            with patch.object(board.time,'monotonic',side_effect=clock):
                try:board.b10_wait_probe(peer,Path(folder))
                except ValueError:
                    assert fault is not None
                    assert not (Path(folder)/'b10-idle-cancel.json').exists()
                    if fault=='premature-RX':assert not peer.sent
                else:
                    assert fault is None and peer.sent==[b'\x03']
                    assert board.r.read(Path(folder)/'b10-idle-cancel.json')['initial_idle_seconds']>=12
        rows.append(dict(case=fault or 'idle12-Ctrl-C-return',passed=True))
    assert 'serial' not in __import__('sys').modules
    board.save(board.ROOT/'BUILD/pr04-b10-wait/b10-probe-host-tests.json',dict(passed=True,
        hardware=False,serial_access=False,checks=len(rows),cases=rows,
        adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
        checker_sha256=board.r.sha(Path(__file__).read_bytes())))
    print('PASS b10 live-probe buffered groups',len(rows),flush=True)


if __name__=='__main__':main()
