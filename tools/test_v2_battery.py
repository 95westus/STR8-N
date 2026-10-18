"""Execute beta25 battery calendar, commands, boot and interrupted appends."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-battery')
import binascii
import json
from datetime import date, timedelta

from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_local_time import launch, invoke, record as tz_record
from test_v2_board_name import record as name_record
from test_v2_spi_resident import k
from test_v2_storage import cmd

META = json.loads((OUT/'build.json').read_text())
CM = json.loads((OUT/'clock/build.json').read_text())
S = CM['symbols']
EPOCH = date(2000, 1, 1)


def record(installed, warn=12, replace=24, stage=0, high=None, seq=1):
    r = bytearray(b'\xff'*32)
    r[:4] = b'BA\x01\0'
    r[4:8] = seq.to_bytes(4, 'little')
    n = (installed-EPOCH).days
    h = ((high or installed)-EPOCH).days
    r[8:15] = n.to_bytes(2, 'little')+bytes((warn, replace, stage))+h.to_bytes(2, 'little')
    r[28:30] = binascii.crc_hqx(r[:28], 0xFFFF).to_bytes(2, 'little')
    r[31] = 0
    return r


def clock(cpu, m, command):
    return cmd(cpu, m, command+b'\r')


def set_date(m, d):
    bcd = lambda x: (x//10)*16+x%10
    m.bus.rtc_regs[:7] = bytes((0x80, 0, 0, 0x28+d.isoweekday(), bcd(d.day), bcd(d.month), bcd(d.year-2000)))


def main():
    checks = []
    def passed(label):
        checks.append(label)
        print('PASS', label, flush=True)

    cpu, m = fresh()
    before = snapshot(m)
    app = bytes(m.ram[0x200:0x6500])
    boot(cpu)
    assert b'Battery age unknown' in m.tx, bytes(m.tx)
    assert snapshot(m) == before and bytes(m.ram[0x200:0x6500]) == app
    text = launch(cpu, m)
    assert b'CLOCK 1.8' in text and b'Battery age unknown' in text
    for line in (b'BATTERY', b'BATTERYX', b'BATTERY LIMITS 00 24',
                 b'BATTERY 2026-02-29', b'BATTERY 2027-01-01',
                 b'BATTERY 1999-12-31', b'BATTERY REPLACED\rNO',
                 b'BATTERY REPLACED\rY'):
        clock(cpu, m, line)
        assert snapshot(m) == before, line
    text = clock(cpu, m, b'BATTERY REPLACED\rYES')
    assert b'12/24 months' in text and b'within age policy' in text, text
    assert bytes(m.bus.ee) == before[1] and bytes(m.bus.rtc_regs) == before[2]
    assert bytes(m.spi.devices[0].data) == before[3]
    assert not any(e[0] == 'erase' for e in m.events)
    assert bytes(m.banks[3][:0x1C20]) == before[0][3][:0x1C20]
    saved = snapshot(m)
    clock(cpu, m, b'BATTERY')
    assert snapshot(m) == saved
    passed('unknown age is read-only; strict parser/YES; replacement appends default 12/24 policy and preserves all other data')

    for line in (b'BATTERY LIMITS 00 24', b'BATTERY LIMITS 24 24',
                 b'BATTERY LIMITS 25 24', b'BATTERY LIMITS 01 00',
                 b'BATTERY LIMITS 1 24', b'BATTERY LIMITS 01 24 X',
                 b'BATTERY LIMITS 06 18\rNO'):
        clock(cpu, m, line)
        assert snapshot(m) == saved, line
    text = clock(cpu, m, b'BATTERY LIMITS 06 18\rYES')
    assert b'06/18 months' in text, text
    text = clock(cpu, m, b'BATTERY 2026-10-01\rYES')
    assert b'06/18 months' in text and b'within age policy' in text, text
    passed('threshold validation, confirmation and historical installation date; date changes preserve selected policy')

    # Compare actual assembled Gregorian arithmetic with independent Python dates.
    cases = [date(y, mo, 1) for y in range(2000, 2100) for mo in (1, 2, 3, 12)]
    cases += [date(2000, 2, 29), date(2024, 2, 29), date(2099, 12, 31)]
    for d in cases:
        for name, value in [('BT_YEAR', d.year-2000), ('BT_MONTH', d.month), ('BT_DAY', d.day)]:
            m.ram[S[name]] = value
        invoke(cpu, S['BT_DATE'])
        n = int.from_bytes(m.ram[S['BT_DAYNUM']:S['BT_DAYNUM']+2], 'little')
        assert n == (d-EPOCH).days, (d, n)
    passed('403 linked calendar cases including leap days and 2000/2099 boundaries')

    # Actual boot path latches thresholds; repeated boot does no additional write.
    for elapsed, expected, stage in [(359, b'within age policy', 0), (360, b'Battery reminder', 1),
                                      (719, b'Battery reminder', 1), (720, b'Battery replacement due', 2)]:
        cpu, m = fresh()
        today = date(2026, 10, 8)
        m.banks[3][0x1C20:0x1C40] = record(today-timedelta(days=elapsed))
        before = snapshot(m)
        app = bytes(m.ram[0x200:0x6500])
        boot(cpu)
        assert expected in m.tx, (elapsed, bytes(m.tx))
        assert bytes(m.ram[0x200:0x6500]) == app
        assert bytes(m.bus.ee) == before[1] and bytes(m.bus.rtc_regs) == before[2]
        assert not any(e[0] == 'erase' for e in m.events)
        saved = snapshot(m)
        cpu.pc = 0xF004
        boot(cpu)
        assert snapshot(m) == saved
        launch(cpu, m)
        assert m.ram[S['BT_PAYLOAD']+4] == stage
    passed('boot warning boundaries at 360/720 days; latched append uses worker safely; repeated reset does not write')

    # Persisted warning is a floor even when thresholds are lengthened.
    text = clock(cpu, m, b'BATTERY LIMITS 98 99\rYES')
    assert b'Battery replacement due' in text and b'98/99 months' in text, text
    text = clock(cpu, m, b'BATTERY REPLACED\rYES')
    assert b'within age policy' in text and b'98/99 months' in text, text
    passed('policy changes cannot clear an existing warning; explicit replacement resets it')

    for stopped in (False, True):
        cpu, m = fresh()
        m.banks[3][0x1C20:0x1C40] = record(date(2025, 1, 1), high=date(2026, 10, 9))
        if stopped:
            m.bus.rtc_regs[0] &= ~0x80
            m.bus.rtc_regs[3] &= ~0x20
        boot(cpu)
        assert b'Battery age uncertain' in m.tx, bytes(m.tx)
        saved = snapshot(m)
        cpu.pc = 0xF004
        boot(cpu)
        assert snapshot(m) == saved and b'Battery age uncertain' in m.tx
    passed('backward date/stopped clock latch uncertainty across resets')

    cpu, m = fresh(off=True)
    boot(cpu)
    assert b'Battery' not in m.tx and not m.bus.accesses and not m.spi.frames
    for corrupt in (False, True):
        cpu, m = fresh()
        start = META['battery_asset_address']-0x8000
        if corrupt:
            m.banks[2][start+8] ^= 1
        else:
            m.banks[2][start:start+META['battery_asset_bytes']] = b'\xff'*META['battery_asset_bytes']
        before = snapshot(m)
        boot(cpu)
        assert b'B3> ' in m.tx and snapshot(m) == before
        assert b'within age policy' not in m.tx
    passed('EDU OFF does no device access; corrupt/missing helper cannot execute or block monitor')

    cpu, m = fresh()
    m.banks[3][:4096] = b'\xff'*4096
    boot(cpu)
    assert b'B3> ' in m.tx and b'Battery age unknown' in m.tx
    assert m.ram[0x7D2A] == 0
    passed('missing RTC component never calls an uninstalled clock gateway')

    # Coexisting tail records, full journal, incompatible format, and flash timeout.
    cpu, m = fresh()
    m.banks[3][0x1C20:0x1C40] = record(date(2026, 10, 1))
    m.banks[3][0x1C40:0x1C60] = tz_record(-300)
    m.banks[3][0x1C60:0x1C80] = name_record(b'2609')
    boot(cpu)
    launch(cpu, m)
    before = snapshot(m)
    for p in range(0x1C80, 0x2000, 32):
        m.banks[3][p:p+32] = bytes(32)
    full = snapshot(m)
    text = clock(cpu, m, b'BATTERY REPLACED\rYES')
    assert b'not saved' in text and snapshot(m) == full, text
    m.banks[3][:] = before[0][3]
    m.fault = 'timeout'
    text = clock(cpu, m, b'BATTERY LIMITS 06 18\rYES')
    m.fault = None
    assert b'not saved' in text and not any(e[0] == 'erase' for e in m.events), text
    text = clock(cpu, m, b'BATTERY')
    assert b'12/24 months' in text
    passed('shared EUI/TZ/name records retained; full journal and timeout refuse without erase')

    # Cut each programmed byte of a real replacement append.
    cpu, m = fresh()
    m.banks[3][0x1C20:0x1C40] = record(date(2026, 10, 1))
    boot(cpu)
    launch(cpu, m)
    ram, banks = bytes(m.ram), [bytes(b) for b in m.banks]
    pending = record(date(2026, 10, 8), 6, 18)[8:15]
    def fixture(cut=None):
        c, p = fresh()
        p.ram[:] = ram
        p.banks = [bytearray(b) for b in banks]
        p.spi.banks = p.banks
        p.ram[S['BT_PENDING']:S['BT_PENDING']+7] = pending
        p.cut_after = cut
        return c, p
    cpu, done = fixture()
    invoke(cpu, S['BT_SAVE'])
    assert cpu.p & cpu.CARRY
    writes = len(done.events)
    for cut in range(1, writes+1):
        cpu, partial = fixture(cut)
        try:
            invoke(cpu, S['BT_SAVE'])
        except k.model.PowerCut:
            pass
        partial.cut_after = None
        cpu.sp = 255
        invoke(cpu, S['BT_READ'])
        actual = bytes(partial.ram[S['BT_PAYLOAD']:S['BT_PAYLOAD']+7])
        assert actual == (pending if cut == writes else record(date(2026, 10, 1))[8:15]), (cut, actual)
        assert bytes(partial.banks[3][:0x1C40]) == banks[3][:0x1C40]
    passed(f'all {writes} interrupted appends retain the previous record until verified commit')

    base = OUT.parent/'v2-map-assets'
    for name in ('str8n-v2-recovery-f000-ffff.bin', 'str8n-v2-recovery-slot-a0.bin',
                 'str8n-v2-recovery-slot-b0.bin', 'local-display/asset.bin', 'version/asset.bin'):
        assert (OUT/name).read_bytes() == (base/name).read_bytes(), name
    assert len((OUT/'clock/storage.bin').read_bytes()) == 12288
    # Exercise the offline update planner against an exact shared baseline.
    import prepare_v2_battery as planner
    cpu, m = fresh()
    banks = [bytearray(b) for b in m.banks]
    banks[3][0x6000:0x7000] = (base/'str8n-v2-recovery-e000-efff.bin').read_bytes()
    banks[2][0x4800:0x5200] = (base/'boot-status/asset.bin').read_bytes()
    banks[2][0x5200:0x5C00] = b'\xff'*2560
    banks[1][0x3000:0x6000] = (base/'clock/storage.bin').read_bytes()
    prior = [bytes(b) for b in banks]
    final, order = planner.plan(prior)
    assert len(order) == 7 and final[3][:0x4000] == banks[3][:0x4000]
    assert final[3][0x7000:] == banks[3][0x7000:]
    assert final[1][0x3000:0x6000] == (OUT/'clock/storage.bin').read_bytes()
    for bank, offset in ((2, 0x5200), (3, 0x6001)):
        bad = [bytearray(b) for b in prior]
        bad[bank][offset] ^= 1
        try:
            planner.plan(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('Planner accepted occupied/unknown firmware')
    passed('offline planner preserves both slots/F/settings and refuses occupied helper or unknown shared firmware')
    report = dict(passed=True, checks=checks, clock_sha256=CM['sha256'],
                  battery_asset_sha256=META['battery_asset_sha256'],
                  artifacts=META['artifacts'], board_access=False, boards_flashed=False)
    (OUT/'battery-test-results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
