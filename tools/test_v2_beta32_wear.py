"""Execute worst-sector flash-wear warnings; no physical board access."""
import os
os.environ['STR8_RTC_BUILD']='BUILD/v2-beta32-candidate'
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
    values=[0,9,10,99,100,255,256,999,1000,9999,10000,49999,50000,65535,65536,79999,80000,100000,9999999,10000000,0xFFFFFF]
    for value in values:
        wanted=b'FLASH: wear check HIGH: >=80,000' if value>=80000 else b'FLASH: wear check WARNING: >=50,000' if value>=50000 else None
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
                assert f'Sector B{index//8}:{8+index%8:X}, max {value} tracked erases.'.encode() in text,text
                assert b'Prior/direct wear unknown' in text
                if value < 80000:
                    assert b'HIGH' not in text
            else:
                assert b'FLASH: wear check OK' in text and b'prior/direct wear unknown' in text.lower() and b'HIGH' not in text and b'WARNING' not in text,(value,text)
            selected=index if value else 0
            assert f'Sector B{selected//8}:{8+selected%8:X}, max {value} tracked erases.'.encode() in text,text
            assert int.from_bytes(m.ram[S['WEAR_MAX']:S['WEAR_MAX']+3],'little')==value
    checks.append('105 linked boundary/sector cases: exact decimal peak, bank/sector, zero, 50k/80k and 24-bit limits; original count, app and devices preserved')
    print('PASS', checks[-1], flush=True)

    counts=[0]*32;counts[3]=counts[25]=4321;journal(counts);start=len(m.tx)
    invoke(cpu,S['WEAR_SHOW']);assert b'Sector B0:B, max 4321 tracked erases.' in m.tx[start:]
    checks.append('equal maxima choose the lowest bank/sector; all-zero history chooses B0:8')
    print('PASS',checks[-1],flush=True)
    import random
    rng=random.Random(32)
    for value in [0,1,0xFFFFFF]+[rng.randrange(0x1000000) for _ in range(128)]:
        m.ram[S['WEAR_MAX']:S['WEAR_MAX']+3]=value.to_bytes(3,'little');start=len(m.tx);before=snapshot(m)
        invoke(cpu,S['WEAR_DECIMAL'])
        assert bytes(m.tx[start:])==str(value).encode(),(value,bytes(m.tx[start:]))
        assert int.from_bytes(m.ram[S['WEAR_MAX']:S['WEAR_MAX']+3],'little')==value and snapshot(m)==before
    checks.append('131 direct decimal-format cases, deterministic 24-bit samples; no leading zeroes and original maximum retained')
    print('PASS',checks[-1],flush=True)

    # One hot sector dominates regardless of the chip average.
    counts = [49999]*32
    counts[14] = 80000
    journal(counts)
    start = len(m.tx)
    invoke(cpu, S['WEAR_SHOW'])
    text = bytes(m.tx[start:])
    assert b'HIGH' in text and b'Sector B1:E, max 80000 tracked erases.' in text
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
    assert b'FLASH: wear check UNKNOWN' in m.tx[start:] and b', max ' not in m.tx[start:] and b'Sector B' not in m.tx[start:] and snapshot(m) == before
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
        assert b'FLASH: wear check HIGH' in m.tx and b'Sector B0:B, max 80000 tracked erases.' in m.tx
        assert snapshot(m) == before and not m.events
        if off:
            assert bytes(m.ram[0x6500:0x6700]) == reclaimed
            assert not m.bus.accesses and not m.spi.frames and b'Battery' not in m.tx
        # Normal monitor returns stay quiet; W is the existing detailed view.
        m.tx.clear()
        cpu.pc = 0x7E67
        boot(cpu)
        assert b'FLASH: wear check' not in m.tx
        text = cmd(cpu, m, b'W\r')
        assert b'B0:B 013880' in text and snapshot(m) == before
    checks.append('actual ON/OFF boot warnings, device-free OFF, quiet return, unchanged W counts; no extra wear writes')
    print('PASS', checks[-1], flush=True)
    # A low count must now be visible on real ON and OFF boot paths.
    for off in (False,True):
        cpu,m=fresh(off=off);before=snapshot(m);app=bytes(m.ram[0x200:0x6700 if off else 0x6500]);boot(cpu)
        text=bytes(m.tx);assert text.count(b'FLASH: wear check OK')==1,text[-1000:]
        assert b'prior/direct wear unknown' in text.lower()
        assert snapshot(m)==before and not m.events
        assert bytes(m.ram[0x200:0x6700 if off else 0x6500])==app
        if off:assert not m.bus.accesses and not m.spi.frames and b'Battery' not in text
        (OUT/('wear-boot-off.txt' if off else 'wear-boot-on.txt')).write_bytes(text)
    checks.append('visible OK exactly once on normal ON/OFF boot, retained application RAM and devices unchanged')
    print('PASS',checks[-1],flush=True)
    from test_v2_spi_resident import k
    from test_v2_sram_store import console
    cpu,m=fresh();m.banks=[bytearray((OUT/f'candidate/b{i}.bin').read_bytes()) for i in range(4)];m.spi.banks=m.banks;m.fast=True
    k.model.run(cpu,lambda:cpu.pc==META['boot']['BOOT_STARTUP_DOTS'],30000000);boot(cpu)
    assert m.ram[0x7D30]==0xB0 and b'2.0b32' in m.tx
    before=snapshot(m);start=len(m.tx)
    text=console(cpu,m,b'BATCH MAINT;Q;TIME\r',limit=100000000)
    assert b'BANK MAINT 2.4' in text and b'BATCH done' in text and b'FLASH:' not in text and text.endswith(b'B3> '),text[-1000:]
    assert snapshot(m)==before and not m.events
    checks.append('beta32 B reference boot; bare alias/BATCH intact, no repeated wear line on ordinary return or TIME')
    print('PASS',checks[-1],flush=True)
    (OUT/'beta32-wear-test-results.json').write_text(json.dumps(dict(passed=True,
        checks=checks, build_sha256=__import__('hashlib').sha256((OUT/'build.json').read_bytes()).hexdigest(), artifacts=META['artifacts'], battery_asset_sha256=META['battery_asset_sha256'],
        thresholds=META['flash_wear_thresholds'], board_access=False, boards_flashed=False),indent=2)+'\n')


if __name__ == '__main__':
    main()
