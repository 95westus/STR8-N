"""Buffered LED-update admission and borrowed-RAM preservation tests."""
from pathlib import Path
import board_flash_led_2512 as h


def main():
    checks = 0; marker = h.io.read(h.io.MARKER)
    h.guard(marker,Path('unused')); checks += 1
    for key in ('block_snapshot','application_RAM_restore_pending','one_shot_collection_active',
                'recovery_worker_active','physical_reset_pending','owner_application_running',
                'boot_settings_restore_pending','opaque_sector_restore_pending'):
        try: h.guard(dict(marker,**{key:True}),Path('unused'))
        except AssertionError: pass
        else: raise AssertionError('Unsafe source admitted: '+key)
        checks += 1
    old = (h.OLD_BUILD/'payload/bank-monitor-8000-ram.bin').read_bytes()
    previous = bytes([0xa5])*0x6300
    snapshot = bytearray(bytes([0x5a])*0x6300); snapshot[:len(old)] = old
    expected = previous[:0xd00]+bytes(snapshot[0xd00:])
    restored,scope = h.owner_snapshot(bytes(snapshot),previous)
    assert restored == expected and 'fresh-tail' in scope; checks += 1
    snapshot[0x1e00:0x1e04] = b'\x00\x03\xff\x42'
    restored,_ = h.owner_snapshot(bytes(snapshot),previous)
    assert restored[0x1e00:0x1e04] == b'\x00\x03\xff\x42'; checks += 1
    already = previous[:0xd00]+bytes(snapshot[0xd00:])
    assert h.owner_snapshot(already,previous)[0] == already; checks += 1
    bad = bytearray(snapshot); bad[0] ^= 1
    try: h.owner_snapshot(bytes(bad),previous)
    except AssertionError: pass
    else: raise AssertionError('Unknown owner RAM prefix overwritten')
    checks += 1
    h.io.save(h.HERE/'flash-led-host-tests.json',dict(passed=True,hardware=False,serial_access=False,
        checks=checks,helper_sha256=h.io.sha(Path(h.__file__).read_bytes()),
        checker_sha256=h.io.sha(Path(__file__).read_bytes())))
    print('PASS',checks,'LED-update host/preservation checks')


if __name__ == '__main__': main()
