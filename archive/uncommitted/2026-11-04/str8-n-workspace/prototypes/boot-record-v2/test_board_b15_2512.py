"""Buffered b15 host admission and token/framing checks; no serial access."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import board_b15_2512 as h


def main():
    checks=0;marker=h.io.read(h.MARKER)
    for key in ('block_snapshot','application_RAM_restore_pending','owner_application_running',
                'installer_worker_active','physical_reset_pending','one_shot_collection_active'):
        bad=dict(marker,**{key:True})
        try:h.guard(bad,Path('unused'))
        except AssertionError:pass
        else:raise AssertionError('Unsafe source admitted: '+key)
        checks+=1
    class Peer:
        def __init__(self):self.requested=[]
        def until(self,token,seconds):self.requested.append((token,seconds));return token
    peer=Peer();wrapped=h.RestartLink(peer)
    assert wrapped.until(h.OLD_DONE,90)==h.DONE and peer.requested==[(h.DONE,90)];checks+=1
    assert wrapped.until(b'OTHER',15)==b'OTHER' and peer.requested[-1]==(b'OTHER',15);checks+=1
    class CancelPeer:
        pending=bytearray()
        def __init__(self,bad=False):self.sent=[];self.bad=bad
        def send(self,data):self.sent.append(data)
        def until(self,token,seconds=45):
            if token==b'SEND BIN\r\n':return b'L\r\nSEND BIN\r\n'
            assert token==h.io.REC and self.sent[-1]==b'\x03'
            return ((b'STR8-N' if self.bad else b'')+b'\r\nRecovery L A/B 0-3 C1/2/3 ?\r\nREC> ')
    with tempfile.TemporaryDirectory(dir=h.ROOT/'tmp',prefix='b15-host-') as name:
        folder=Path(name).resolve();assert folder.parent==(h.ROOT/'tmp').resolve()
        peer=CancelPeer();h.cancel_ready(peer,folder,'cancel')
        assert peer.sent==[b'L\r',b'\x03'] and h.io.read(folder/'cancel.json')['passed'];checks+=1
        peer=CancelPeer(bad=True)
        try:h.cancel_ready(peer,folder,'bad')
        except AssertionError:pass
        else:raise AssertionError('Unexpected boot accepted as cancellation')
        checks+=1
    result=dict(passed=True,checks=checks,hardware=False,serial_access=False,failures=0,
        helper_sha256=h.io.sha(Path(h.__file__).read_bytes()),checker_sha256=h.io.sha(Path(__file__).read_bytes()))
    h.io.save(h.HERE/'b15-host-tests.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
