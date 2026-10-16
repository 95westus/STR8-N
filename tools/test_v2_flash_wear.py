"""Execute worst-sector flash-wear warnings; no physical board access."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-battery')
import json

from beta4_migration import metadata
from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_local_time import invoke
from test_v2_storage import cmd

META = json.loads((OUT/'build.json').read_text())
S = META['battery_symbols']


def main():
    cpu, m = fresh(off=True)
    boot(cpu)
    assert not m.bus.accesses and not m.spi.frames
    cfg = bytes(m.ram[0x7D80:0x7D90])
    app = bytes(m.ram[0x200:0x6700])
    checks = []

    def journal(counts, seq=1):
        m.banks[3][0x4000:0x6000] = metadata(cfg, counts, seq)+b'\xff'*(8192-128)

    # Includes exact thresholds, carry boundaries, large 24-bit values and B0.
    for value, wanted in [(0, None), (49999, None), (50000, b'Flash wear: >=50,000'),
                          (65535, b'Flash wear: >=50,000'), (65536, b'Flash wear: >=50,000'),
                          (79999, b'Flash wear: >=50,000'), (80000, b'Flash wear HIGH: >=80,000'),
                          (100000, b'Flash wear HIGH: >=80,000'), (0xFFFFFF, b'Flash wear HIGH: >=80,000')]:
        for index in (0, 7, 24, 28, 31):
            counts = [0]*32
            counts[index] = value
            journal(counts)
            before = snapshot(m)
            start = len(m.tx)
            # A different bank is visible on entry; the helper must restore it.
            m[0x7FEC] = (m.ram[0x7FEC]&0x11)|0xCC
            pcr = m.ram[0x7FEC]
            invoke(cpu, S['WEAR_SHOW'])
            text = bytes(m.tx[start:])
            assert m.ram[0x7FEC] == pcr
            assert snapshot(m) == before and bytes(m.ram[0x200:0x6700]) == app
            assert not m.events and not m.bus.accesses and not m.spi.frames
            if wanted:
                assert wanted in text, (value, index, text)
                assert f'Sector B{index//8}:{8+index%8:X}.'.encode() in text, text
                assert b'Prior/direct wear unknown' in text
                if value < 80000:
                    assert b'HIGH' not in text
            else:
                assert not text, (value, text)
    checks.append('45 linked boundary/sector cases: 50k/80k, 16/24-bit carries, B0 and journal sectors; bank/app/device/flash preserved')
    print('PASS', checks[-1], flush=True)

    # One hot sector dominates regardless of the chip average.
    counts = [49999]*32
    counts[14] = 80000
    journal(counts)
    start = len(m.tx)
    invoke(cpu, S['WEAR_SHOW'])
    text = bytes(m.tx[start:])
    assert b'HIGH' in text and b'Sector B1:E.' in text
    # A newer uncommitted/corrupt record cannot mask an older warning.
    older = metadata(cfg, counts, 1)
    for kind in ('uncommitted', 'crc'):
        bad = bytearray(metadata(cfg, [0]*32, 2))
        bad[127 if kind == 'uncommitted' else 120] ^= 1
        m.banks[3][0x4000:0x6000] = older+bad+b'\xff'*(8192-256)
        start = len(m.tx)
        invoke(cpu, S['WEAR_SHOW'])
        assert b'HIGH' in m.tx[start:]
    # With no valid journal, show uncertainty, never a fabricated zero.
    m.banks[3][0x4000:0x6000] = b'\xff'*8192
    before = snapshot(m)
    start = len(m.tx)
    invoke(cpu, S['WEAR_SHOW'])
    assert b'Flash wear history unavailable' in m.tx[start:] and snapshot(m) == before
    checks.append('worst-sector selection; valid committed journal required; invalid history is unavailable')
    print('PASS', checks[-1], flush=True)

    # Actual cold boot must show wear even with EDU OFF, without touching RAM.
    for off in (False, True):
        cpu, m = fresh(off=off)
        cfg = bytes(m.banks[3][0x4008:0x4018])
        counts = [0]*32
        counts[3] = 80000
        m.banks[3][0x4000:0x6000] = metadata(cfg, counts, 1)+b'\xff'*(8192-128)
        before = snapshot(m)
        reclaimed = bytes(m.ram[0x6500:0x6700])
        boot(cpu)
        assert b'Flash wear HIGH' in m.tx and b'Sector B0:B.' in m.tx
        assert snapshot(m) == before and not m.events
        if off:
            assert bytes(m.ram[0x6500:0x6700]) == reclaimed
            assert not m.bus.accesses and not m.spi.frames and b'Battery' not in m.tx
        # Normal monitor returns stay quiet; W is the existing detailed view.
        m.tx.clear()
        cpu.pc = 0x7E67
        boot(cpu)
        assert b'Flash wear' not in m.tx
        text = cmd(cpu, m, b'W\r')
        assert b'B0:B 013880' in text and snapshot(m) == before
    checks.append('actual ON/OFF boot warnings, device-free OFF, quiet return, unchanged W counts; no extra wear writes')
    print('PASS', checks[-1], flush=True)
    (OUT/'flash-wear-test-results.json').write_text(json.dumps(dict(passed=True,
        checks=checks, artifacts=META['artifacts'], battery_asset_sha256=META['battery_asset_sha256'],
        thresholds=META['flash_wear_thresholds'], board_access=False, boards_flashed=False),indent=2)+'\n')


if __name__ == '__main__':
    main()
