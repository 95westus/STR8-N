"""Buffered raw protocol, timing refusals and independent MON readback."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import board_b14_2512 as board
from build_b14 import HELP
BUILD=board.ROOT/'BUILD/pr04-b14-raw-r4'

def main():
    rows=[]
    def passed(case):rows.append(dict(case=case,passed=True))
    for fault in [None,'premature','refused','early-run','late-run']:
        class Peer:
            def __init__(self):self.pending=bytearray();self.sent=[];self.reads=0
            def command(self,key,prompt):assert key=='L' and prompt==b'SEND BIN\r\n';return prompt
            def read(self,count):self.reads+=1;return b'bad' if fault=='premature' else b''
            def send(self,data):self.sent.append(data)
            def until(self,prompt,seconds):
                clock[0]+=1 if fault=='early-run' else 5 if fault=='late-run' else 3
                return b'REFUSED\r\nREC> ' if fault=='refused' else board.OI_PROMPT
        clock=[0.0]
        def mono():clock[0]+=.01;return clock[0]
        body=bytes(range(256))*4;peer=Peer()
        with patch.object(board.time,'monotonic',side_effect=mono),patch.object(board.time,'sleep'):
            try:board.raw_load_auto_run(peer,body)
            except ValueError:assert fault is not None
            else:
                assert fault is None and b''.join(peer.sent)==body and peer.b14_raw_receipt['initial_no_data_wait_seconds']>=5
                assert not peer.b14_raw_receipt['R_command_sent'] and peer.b14_raw_receipt['header_bytes']==0
        if fault=='premature':assert not peer.sent
        passed('raw-no-header-no-R-'+str(fault))
    for fault in [None,'help','R','r','D','d','V','v']:
        class Peer:
            def command(self,key,prompt):
                if key==fault or fault=='help' and key=='?':return b'wrong REC> '
                return b'?\r\n'+HELP+b'REC> ' if key=='?' else key.encode()+b'\r\nREFUSED: command\r\nREC> '
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            try:board.b14_help_probe(Peer(),Path(folder))
            except ValueError:assert fault is not None
            else:assert fault is None
        passed('help-removed-command-'+str(fault))
    body=(BUILD/'payload/ram-installer-offline.bin').read_bytes();sy=board.r.read(BUILD/'symbols.json')['core/ram-installer']
    sector=bytes(range(256))*16;expected=board.b14_runtime_image(body,sector,sy)
    for fault in [None,'code','short','scratch']:
        class Peer:
            def dump(self,a,b):
                assert (a,b)==(0x200,0x1ff+len(body))
                if fault=='short':return expected[:-1]
                v=bytearray(expected)
                if fault:v[0 if fault=='code' else sy['OI_HEADER']-0x200]^=1
                return bytes(v)
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            try:board.b14_mon_readback(Peer(),Path(folder),body,sector,sy)
            except ValueError:assert fault is not None
            else:assert fault is None
        passed('MON-exact-0200-readback-'+str(fault))
    assert 'serial' not in __import__('sys').modules
    board.save(BUILD/'b14-probe-host-tests.json',dict(passed=True,hardware=False,serial_access=False,checks=len(rows),cases=rows,
        adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),checker_sha256=board.r.sha(Path(__file__).read_bytes())))
    print('PASS b14 buffered probes',len(rows),flush=True)

if __name__=='__main__':main()
