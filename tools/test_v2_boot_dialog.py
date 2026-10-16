"""Execute reordered beta25 boot paths in the instruction model only."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-boot-dialog')
import json
from test_v2_status import fresh, boot, layout, snapshot, OUT
from test_v2_board_name import record
from test_v2_local_time import record as offset_record
from test_v2_journal import event
from test_v2_storage import cmd


def main():
    checks = []
    invalid = layout()
    invalid[60] ^= 1
    cases = (
        ('uninitialized-pf', None, None, {}, b'Allocation uninitialized', True),
        ('allocated', layout(), None, {}, b'PROGRAM payload', False),
        ('repair', bytes(64), layout(2), {}, b'Layout needs repair', False),
        ('invalid', invalid, None, {}, b'Layout invalid', False),
        ('absent', None, None, dict(present=False), b'Unavailable', False),
    )
    for name, primary, secondary, options, status, pf in cases:
        cpu, m = fresh(primary=primary, secondary=secondary, **options)
        m.banks[3][0x1C20:0x1C40] = record(b'2609')
        m.banks[3][0x1C40:0x1C60] = offset_record(-300)
        if pf:
            m.bus.rtc_regs[3] |= 16
            m.bus.rtc_regs[0x18:0x20] = event(5)
        before = snapshot(m)
        scratch = bytes(m.ram[0x200:0x6500])
        boot(cpu)
        out = bytes(m.tx)
        assert b'ABI 65C02 | 816E | 816N-VEC\r\n\r\nBoard: 2609\r\n\r\nRAM $0200-$64FF\r\nEDU ON\r\nSSRAM: ' in out, out
        assert status in out
        assert out.index(b'SSRAM:') < out.index(b'RTCC: Thu')
        assert b'14:53:15 (-05:00)\r\n\r\nB3> ' in out, out
        assert bytes(m.ram[0x200:0x6500]) == scratch
        after = snapshot(m)
        assert after[0] == before[0] and after[3] == before[3]
        if pf:
            assert b'\r\n\r\n [power-fail UTC]\r\nPower down: 10-07 05:05' in out
            assert b'RTCC: PF logged, ACK\r\n\r\nRTCC:' in out
            assert not m.bus.rtc_regs[3] & 16
        else:
            assert after == before
        (OUT / (name+'-boot.txt')).write_bytes(out)
        checks.append(name)
        print('PASS', name, flush=True)
    for off in (False, True):
        cpu, m = fresh(off=off)
        before = snapshot(m)
        boot(cpu)
        out = bytes(m.tx)
        assert b'Board:' not in out
        assert snapshot(m) == before
        if off:
            assert b'RAM $0200-$66FF\r\nEDU OFF' in out
            assert b'SSRAM:' not in out and b'RTCC:' not in out
            assert not m.bus.accesses and not m.spi.frames
        m.tx.clear()
        cpu.pc = 0x7E67
        boot(cpu)
        assert b'RAM $' not in m.tx and b'Board:' not in m.tx
    checks.append('unnamed, EDU OFF device-free, quiet monitor return')
    cpu, m = fresh()
    m.banks[3][0x1C20:0x1C40] = record(b'2609')
    m.bus.rtc_regs[3] |= 16
    m.bus.rtc_regs[0x18:0x20] = event(5)
    m.bus.ee[:128] = bytes(range(128))
    before = snapshot(m)
    boot(cpu)
    assert b'RTCC: PF log failed.\r\n\r\nRTCC:' in m.tx
    assert snapshot(m) == before
    checks.append('failed journal retains power-fail evidence')
    meta = json.loads((OUT/'build.json').read_text())
    report = dict(passed=True, checks=checks, artifacts=meta['artifacts'],
                  status_asset_sha256=meta['status_asset_sha256'],
                  local_asset_sha256=meta['local_asset_sha256'],
                  board_access=False, boards_flashed=False)
    (OUT/'boot-dialog-test-results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
