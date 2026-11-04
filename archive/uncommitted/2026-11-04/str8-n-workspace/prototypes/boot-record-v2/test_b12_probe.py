"""Buffered qualification of b12 deployment probes; no hardware or serial."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import board_b12_2512 as board
from build_b12 import HELP

BUILD=board.ROOT/'BUILD/pr04-b12-no-readback-r4'
def main():
    rows=[]
    def passed(case):rows.append(dict(case=case,passed=True))
    for fault in (None,'premature-RX','cancel-refused'):
        class Peer:
            pending=bytearray()
            def __init__(self):self.sent=[]
            def command(self,text,prompt):assert text=='L';return b'L\r\nSEND HEADER+BIN\r\n'
            def read(self,count):return b'REFUSED' if fault=='premature-RX' else b''
            def send(self,data):self.sent.append(data)
            def until(self,prompt):return b'REFUSED\r\nREC> ' if fault=='cancel-refused' else b'REC> '
        tick=[0.0]
        def clock():tick[0]+=.25;return tick[0]
        peer=Peer()
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            with patch.object(board.time,'monotonic',side_effect=clock),patch.object(board,'b12_help_probe'):
                try:board.b12_wait_probe(peer,Path(folder))
                except ValueError:assert fault is not None and not (Path(folder)/'b12-idle-cancel.json').exists()
                else:assert fault is None and peer.sent==[b'\x03']
        passed('idle-cancel-'+str(fault))
    for fault in (None,'?','R','D','V','d','v'):
        class Peer:
            def command(self,key,prompt):
                if key==fault:return b'REFUSED: timeout\r\nREC> '
                if key=='?':return b'?\r\n'+HELP+b'REC> '
                if key=='R':return b'R\r\nREFUSED: no valid RAM image\r\nREC> '
                return key.encode()+b'\r\nREFUSED: command\r\nREC> '
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            try:board.b12_help_probe(Peer(),Path(folder))
            except ValueError:assert fault is not None and not (Path(folder)/'b12-help-fresh.json').exists()
            else:assert fault is None and board.r.read(Path(folder)/'b12-help-fresh.json')['removed_D_V_refused']
        passed('help-R-removed-DV-'+str(fault))
    body=bytes(range(256))*9+b'\x03\r\n\xff'
    for fault in (None,'premature-RX','bad-reply','refused'):
        class Peer:
            pending=bytearray()
            def __init__(self):self.sent=[]
            def command(self,key,prompt):assert key=='L';return b'SEND HEADER+BIN\r\n'
            def send(self,data):self.sent.append(data)
            def read(self,count):return b'timeout' if fault=='premature-RX' else b''
            def until(self,prompt):return b'REC> ' if fault=='bad-reply' else (b'REFUSED LOADED; R runs\r\nREC> ' if fault=='refused' else b'LOADED; R runs\r\nREC> ')
        peer=Peer();tick=[0.0]
        def clock():tick[0]+=.25;return tick[0]
        with patch.object(board.time,'monotonic',side_effect=clock),patch.object(board.time,'sleep'):
            try:board.rlp_load(peer,body)
            except ValueError:assert fault is not None
            else:assert fault is None and b''.join(peer.sent)==board.rlp_header(body)+body and peer.b12_binary_wait_seconds>=3
        if fault=='premature-RX':assert not peer.sent
        passed('RLP1-load-no-recovery-readback-'+str(fault))
    body=(BUILD/'payload/ram-installer-offline.bin').read_bytes()
    symbols=board.r.read(BUILD/'symbols.json')['core/ram-installer'];sector=bytes(range(256))*16
    runtime=board.b12_runtime_image(body,sector,symbols)
    for fault in (None,'wrong','short','scratch-header','scratch-CRC'):
        class Peer:
            def dump(self,first,last):
                assert (first,last)==(0x2000,0x1fff+len(body))
                if fault is None:return runtime
                if fault=='wrong':return b'X'+runtime[1:]
                if fault=='short':return runtime[:-1]
                changed=bytearray(runtime)
                changed[symbols['OI_HEADER' if fault=='scratch-header' else 'OI_CRC']-0x2000]^=1
                return bytes(changed)
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            try:board.b12_mon_readback(Peer(),Path(folder),body,sector,symbols)
            except ValueError:assert fault is not None and not (Path(folder)/'b12-tool-RAM-readback.json').exists()
            else:assert fault is None and board.r.read(Path(folder)/'b12-tool-RAM-readback.json')['sha256']==board.r.sha(runtime)
        passed('independent-MON-readback-'+str(fault))
    assert 'serial' not in __import__('sys').modules
    board.save(BUILD/'b12-probe-host-tests.json',dict(passed=True,hardware=False,serial_access=False,checks=len(rows),cases=rows,
        adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),checker_sha256=board.r.sha(Path(__file__).read_bytes())))
    print('PASS b12 buffered deployment probe cases',len(rows),flush=True)

if __name__=='__main__':main()
