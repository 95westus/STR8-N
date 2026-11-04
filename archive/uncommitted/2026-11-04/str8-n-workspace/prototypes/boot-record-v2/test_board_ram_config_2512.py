"""Buffered transport checks; imports no serial adapter or board session."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import board_ram_config_2512 as h


class Peer:
    def __init__(self, ready=b'L\r\nSEND BIN\r\n', prompt=h.CFG):
        self.ready, self.prompt, self.sent = ready, prompt, []
    def command(self, text, prompt):
        assert text == 'L' and prompt == b'SEND BIN\r\n'
        return self.ready
    def send(self, data): self.sent.append(data)
    def until(self, prompt, seconds):
        assert prompt == h.CFG and seconds == 30
        return self.prompt


def main():
    checks = 0
    with patch.object(h.time,'sleep',lambda _:None):
        body = bytes(range(256))*11
        peer = Peer(); h.raw_load(peer,body,h.CFG)
        assert b''.join(peer.sent) == body and max(map(len,peer.sent)) <= 64
        checks += 1
        for body in (b'', b'X'*0x6301):
            peer = Peer()
            try: h.raw_load(peer,body,h.CFG)
            except AssertionError: pass
            else: raise AssertionError('Invalid raw length accepted')
            assert not peer.sent; checks += 1
        peer = Peer(ready=b'REFUSED\r\nREC> ')
        try: h.raw_load(peer,b'valid',h.CFG)
        except AssertionError: pass
        else: raise AssertionError('Wrong ready accepted')
        assert not peer.sent; checks += 1
        peer = Peer(prompt=b'REC> ')
        try: h.raw_load(peer,b'valid',h.CFG)
        except AssertionError: pass
        else: raise AssertionError('Wrong launch accepted')
        checks += 1
    marker = h.read(h.MARKER)
    for key in ('block_snapshot','application_RAM_restore_pending','owner_application_running',
                'recovery_worker_active','physical_reset_pending','one_shot_collection_active'):
        bad = dict(marker,**{key:True})
        try: h.guard(bad,Path('unused'))
        except AssertionError: pass
        else: raise AssertionError('Unsafe marker admitted: '+key)
        checks += 1
    with tempfile.TemporaryDirectory(dir=h.ROOT/'tmp',prefix='config-host-') as td:
        folder = Path(td).resolve(); assert folder.parent == (h.ROOT/'tmp').resolve()
        h.save(folder/'proof.json',{'passed':True})
        assert h.read(folder/'proof.json') == {'passed':True}
        checks += 1
    class SyncPeer:
        def __init__(self,reply): self.reply=reply;self.sent=False;self.delivered=False
        def read(self,count):
            if self.sent and not self.delivered:
                self.delivered=True;return self.reply
            h.time.sleep(.01);return b''
        def send(self,data): assert data==b'\r';self.sent=True
        def command(self,text,prompt):
            assert text=='B' and prompt==h.MON
            return b'B\r\nSTR8-N 2.0proto b14 B3 65C02'+h.MON
    for reply in (h.MON,b'\r\n'+h.MON,b'\r\nREFUSED: command\r\nREC> '):
        assert h.sync_mon(SyncPeer(reply)).endswith(h.MON)
        checks += 1
    result = dict(passed=True,hardware=False,serial_access=False,checks=checks,failures=0,
        helper_sha256=h.sha(Path(h.__file__).read_bytes()),checker_sha256=h.sha(Path(__file__).read_bytes()))
    h.save(h.HERE/'ram-config-host-tests.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
