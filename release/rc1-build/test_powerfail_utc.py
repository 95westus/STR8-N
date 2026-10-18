"""Execute rc1 boot output with/without a latched outage in the offline CPU model.

--model-tools selects the existing qualified beta35 lab model (test_asm,
test_v2_status, test_v2_journal, test_v2_local_time). Never opens serial ports.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-tools', type=Path, required=True)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    os.environ.update(STR8_ASM_CANDIDATE='BUILD/v2-beta35-candidate',
                      STR8_TEST_DEPS=str(a.model_tools.parent/'BUILD/test-deps'))
    sys.path.insert(0, str(a.model_tools))
    import serial
    def forbidden(*args, **kwargs):
        raise RuntimeError('Physical device access forbidden in UTC regression')
    serial.Serial = forbidden
    import beta4_migration
    beta4_migration.Link = forbidden
    import test_asm as asm
    from test_v2_status import boot, layout, snapshot
    from test_v2_local_time import record as offset_record
    from test_v2_journal import event
    image = a.image.read_bytes()
    assert len(image) == 98304
    checks = []
    for slot in ('A', 'B'):
        for case in ('no-event', 'latched-event', 'logging-failure'):
            cpu, m = asm.fixture(primary=layout())
            m.banks = [bytearray(b'\xff'*32768)]+[
                bytearray(image[n:n+32768]) for n in range(0, len(image), 32768)]
            if slot == 'B':
                m.banks[3][0x201f] = 255
            m.banks[3][0x1C40:0x1C60] = offset_record(-300)
            m.spi.banks = m.banks
            m.fast = True
            m.bus.rtc_regs[:9] = bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
            if case != 'no-event':
                m.bus.rtc_regs[3] |= 16
                m.bus.rtc_regs[0x18:0x20] = event(5)
            if case == 'logging-failure':
                m.bus.ee[:128] = bytes(range(128))
            before = snapshot(m)
            calendar = bytes(m.bus.rtc_regs[:9])
            boot(cpu)
            text = bytes(m.tx)
            assert m.ram[0x7d30] == (0xa0 if slot == 'A' else 0xb0)
            assert b'STR8-N 2.0rc1 B3' in text and b'14:53:15 (-05:00)' in text, text
            if case == 'no-event':
                assert b'power-fail' not in text and snapshot(m) == before
            else:
                assert b' [power-fail UTC]\r\nPower down: 10-07 05:05' in text, text
                assert b'Power up:   10-07 05:06' in text, text
                assert text.index(b'[power-fail UTC]') < text.index(b'RTCC: Sun')
                if case == 'latched-event':
                    assert b'RTCC: PF logged, ACK' in text and not m.bus.rtc_regs[3] & 16
                else:
                    assert b'RTCC: PF log failed.' in text and snapshot(m) == before
            # Only the existing PF acknowledgment may differ in the clock registers.
            after_calendar = bytearray(m.bus.rtc_regs[:9])
            after_calendar[3] = (after_calendar[3] & ~16) | (calendar[3] & 16)
            assert bytes(after_calendar) == calendar
            assert not m.events, 'Unexpected modeled flash operation'
            if case == 'no-event':
                for command in ('BATCH R CLOCK;STATUS;Q', 'T 1', 'APPS'):
                    result = asm.command(cpu, command.encode()+b'\r')
                    assert result.endswith(b'B3> '), result
                    if command.startswith('BATCH'):
                        assert b'BATCH done' in result
                    elif command == 'T 1':
                        assert b'UCHESS' in result
                    else:
                        assert b'ASM' in result
                assert snapshot(m) == before
            (a.out/(slot+'-'+case+'.txt')).write_bytes(text)
            checks.append(dict(slot=slot, case=case, passed=True))
            print('PASS MON', slot, case, flush=True)
    report = dict(passed=True, checks=checks, image_sha256=hashlib.sha256(image).hexdigest(),
                  board_access=False, clock_and_trim_unchanged=True,
                  existing_journal_and_ack_behavior_preserved=True)
    (a.out/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
