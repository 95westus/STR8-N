"""Buffered scope/admission checks for the owner-authorized keep-installed run."""
from pathlib import Path
from unittest.mock import patch
import board_flash_keep_2512 as live
from test_board_bank_monitor_2512 import Peer


def main():
    marker = live.io.read(live.io.MARKER); live.guard(marker,Path('unused')); checks = 1
    for key in ('block_snapshot','application_RAM_restore_pending','opaque_sector_restore_pending',
                'one_shot_collection_active','physical_reset_pending','owner_application_running',
                'recovery_worker_active','pf_ack_worker_active','boot_settings_restore_pending'):
        try: live.guard(dict(marker,**{key:True}),Path('unused'))
        except AssertionError: pass
        else: raise AssertionError('Unsafe marker accepted: '+key)
        checks += 1
    body = (live.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    peer = Peer(body)
    with patch.object(live.prior.time,'sleep'):
        assert live.write_image(peer,body,b'\xff'*4096)['passed']
    assert peer.sent[0][6:8] == b'\0\x80' and b''.join(peer.sent[1:]) == body
    checks += 1
    for bad in (b'\0'*4096,body[:-1]):
        peer = Peer(body)
        try: live.write_image(peer,bad,b'\xff'*4096)
        except AssertionError: pass
        else: raise AssertionError('Different image accepted')
        assert not peer.sent
        checks += 1
    peer = Peer(body,reply=b'REFUSED: preimage CRC\r\n')
    with patch.object(live.prior.time,'sleep'):
        try: live.write_image(peer,body,b'\xff'*4096)
        except AssertionError: pass
        else: raise AssertionError('Failed programming accepted')
    checks += 1
    live.io.save(live.HERE/'flash-keep-host-tests.json',dict(passed=True,hardware=False,serial_access=False,
        checks=checks,helper_sha256=live.io.sha(Path(live.__file__).read_bytes()),
        checker_sha256=live.io.sha(Path(__file__).read_bytes())))
    print('PASS',checks,'keep-installed host checks')


if __name__ == '__main__': main()
