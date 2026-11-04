"""Buffered 2512 FLASH host scope/framing tests; no serial or device access."""
from pathlib import Path
from unittest.mock import patch
import board_bank_monitor_2512 as live


class Peer:
    def __init__(self, body, corrupt=False, reply=b'OK: verified sector\r\n'):
        self.pending = bytearray()
        self.body, self.corrupt, self.reply = body, corrupt, reply
        self.sent = []
    def command(self, text, token):
        assert text == 'I' and token == live.HEADER
        return b'I\r\n'+live.HEADER
    def send(self, body):
        self.sent.append(body)
    def until(self, token, seconds=45):
        if token in (live.READ,live.PAYLOAD): return token
        assert token == live.OI
        return ((b'\r\nOK: read\r\n' if self.sent[0][5] == 0 else self.reply)+token)
    def exact(self, n):
        assert n == 4098
        return self.body+(live.io.crc(self.body) ^ int(self.corrupt)).to_bytes(2,'little')


def main():
    checks = 0
    marker = live.io.read(live.io.MARKER)
    live.guard(marker,Path('unused')); checks += 1
    for key in ('block_snapshot','application_RAM_restore_pending','opaque_sector_restore_pending',
                'one_shot_collection_active','physical_reset_pending','owner_application_running',
                'recovery_worker_active','pf_ack_worker_active','boot_settings_restore_pending'):
        bad = dict(marker,**{key:True})
        try: live.guard(bad,Path('unused'))
        except AssertionError: pass
        else: raise AssertionError('Unsafe board state accepted: '+key)
        checks += 1
    body = bytes(range(256))*16
    for sector in (0x80,0x90):
        peer = Peer(body)
        data = live.opaque_read(peer,sector,body)
        assert data[:4096] == body and peer.sent == [live.protocol.frame_header(0,sector)]
        checks += 1
        peer = Peer(body)
        with patch.object(live.time,'sleep'):
            result = live.opaque_write(peer,sector,body,b'\xff'*4096)
        assert result['passed'] and peer.sent[0] == live.protocol.frame_header(0,sector,body,live.io.crc(b'\xff'*4096))
        assert b''.join(peer.sent[1:]) == body and len(peer.sent[1:]) == 64
        checks += 1
    peer = Peer(body,corrupt=True)
    try: live.opaque_read(peer,0x80,body)
    except AssertionError: pass
    else: raise AssertionError('Bad binary CRC accepted')
    checks += 1
    peer = Peer(body,reply=b'REFUSED: preimage CRC\r\n')
    with patch.object(live.time,'sleep'):
        try: live.opaque_write(peer,0x80,body,b'\xff'*4096)
        except AssertionError: pass
        else: raise AssertionError('Refused programming treated as success')
    checks += 1
    for sector in (0,0x81,0xa0,0xf0):
        try: live.opaque_write(Peer(body),sector,body,body)
        except AssertionError: pass
        else: raise AssertionError('Host target outside owner scope accepted')
        checks += 1
    live.io.save(live.HERE/'bank-monitor-host-tests.json',dict(passed=True,hardware=False,
        serial_access=False,checks=checks,helper_sha256=live.io.sha(Path(live.__file__).read_bytes()),
        checker_sha256=live.io.sha(Path(__file__).read_bytes())))
    print('PASS',checks,'buffered host scope/framing checks')


if __name__ == '__main__': main()
