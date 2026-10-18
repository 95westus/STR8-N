"""Execute CLOCK 1.7 layout, warning, query and confirmation paths."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-clock-summary')
import json
from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_local_time import launch, record
from test_v2_board_name import record as board_record
from test_v2_journal import event
from test_v2_storage import cmd


def main():
    checks = []
    meta = json.loads((OUT/'build.json').read_text())
    cm = json.loads((OUT/'clock/build.json').read_text())
    cpu, m = fresh()
    m.banks[3][0x1C20:0x1C40] = board_record(b'2609')
    m.banks[3][0x1C40:0x1C60] = record(-300)
    boot(cpu)
    before = snapshot(m)
    text = launch(cpu, m)
    wanted = b'''CLOCK 1.7
Board: 2609

Local: Thu 2026-10-08 14:53:15 (-05:00)
UTC:   Thu 2026-10-08 19:53:15
Offset: -05:00 fixed (manual DST)

RTCC: Running | Calendar valid | Backup enabled
Power-fail: None latched
EUI: 54:10:EC:B6:64:AF (matches remembered)

TIME  STATUS  HISTORY  HELP  Q
CLOCK> '''.replace(b'\n', b'\r\n')
    if meta.get('battery_age'):
        wanted = wanted.replace(b'CLOCK 1.7', b'CLOCK 1.8').replace(
            b'(matches remembered)\r\n\r\n',
            b'(matches remembered)\r\nBattery age unknown. Back up SSRAM; use CLOCK BATTERY.\r\n\r\n')
    assert wanted in text, text
    assert b'Remembered EUI:' not in text and b'confirmation' not in text
    assert snapshot(m) == before and not m.events
    (OUT/'clock-summary-preview.txt').write_bytes(text)
    checks.append('exact compact named summary; current/remembered EUI deduplicated; read-only')
    for command, wanted in ((b'TIME', b'UTC:   Thu 2026-10-08 19:53:15'),
            (b'STATUS', b'RTC registers (raw):'), (b'HISTORY', b'No saved event'),
            (b'HELP', b'SET yyyy-mm-dd hh:mm:ss'), (b'?', b'TRIM -127..+127'),
            (b'OFFSET', b'-05:00'), (b'TRIM', b'Trim'), (b'EUI', b'(matches remembered)')):
        text = cmd(cpu, m, command+b'\r')
        assert wanted in text, (command, text)
        assert snapshot(m) == before and not m.events
        if command == b'HELP':
            (OUT/'clock-help-preview.txt').write_bytes(text)
    checks.append('TIME/STATUS/HISTORY/HELP/?/OFFSET/TRIM/EUI remain read-only')
    # Every administration command still requires its original exact confirmation.
    for command in (b'SET 2026-10-09 01:02:03', b'OFFSET +05:30', b'TRIM -17',
                    b'CLEAR 1', b'CLEAR ALL'):
        text = cmd(cpu, m, command+b'\rNO\r')
        assert snapshot(m) == before and not m.events, (command, text)
    invalid = cmd(cpu, m, b'SET 2026-02-29 00:00:00\r')
    assert b'Invalid command/date' in invalid and snapshot(m) == before
    checks.append('SET/OFFSET/TRIM/CLEAR nonconfirmation and invalid date cannot write')
    # Identity differences show both values and never accept automatically.
    m.bus.ee[0xF2] ^= 1
    before = snapshot(m)
    text = cmd(cpu, m, b'EUI\r')
    assert b'(DIFFERS from remembered)' in text and b'Remembered EUI: 54:10:EC:B6:64:AF' in text
    text = cmd(cpu, m, b'ACCEPT EUI\rNO\r')
    assert b'Remember this EUI' in text and snapshot(m) == before
    checks.append('changed EUI explicitly shows both identities; acceptance still confirmed')
    m.bus.ee[0xF2] ^= 1
    # Set latch after boot so the opening screen must display it without ACK.
    cmd(cpu, m, b'Q\r')
    m.bus.rtc_regs[3] |= 0x10
    m.bus.rtc_regs[0x18:0x20] = event(5)
    before = snapshot(m)
    text = launch(cpu, m)
    assert b'Power-fail: LATCHED (UTC)\r\nPower down: 10-07 05:05' in text, text
    assert b'Power up:   10-07 05:06' in text
    assert snapshot(m) == before
    text = cmd(cpu, m, b'ACK\rNO\r')
    assert b'Type YES to confirm' in text and snapshot(m) == before
    checks.append('latched outage uses UTC, stays latched on launch and canceled ACK')
    # Confirmed settings continue to work after relinking the display routines.
    m.bus.rtc_regs[3] &= ~0x10
    rtc = bytes(m.bus.rtc_regs)
    text = cmd(cpu, m, b'OFFSET +05:45\rYES\r')
    assert b'+05:45' in text and bytes(m.bus.rtc_regs) == rtc
    text = cmd(cpu, m, b'TRIM -17\rYES\r')
    assert m.bus.rtc_regs[8] == 17, text
    checks.append('confirmed OFFSET and TRIM still update only requested settings')
    cmd(cpu, m, b'Q\r')
    m.bus.rtc_regs[0] &= ~0x80
    m.bus.rtc_regs[3] &= ~0x20
    before = snapshot(m)
    text = launch(cpu, m)
    assert b'STOPPED' in text and b'Local: ' not in text and b'UTC:   20' not in text
    assert snapshot(m) == before
    checks.append('stopped clock warns and suppresses stale timestamps')
    cpu, m = fresh(off=True)
    boot(cpu)
    before = snapshot(m)
    access = len(m.bus.accesses)
    text = launch(cpu, m)
    assert b'Services unavailable' in text and b'CLOCK> ' in text
    assert len(m.bus.accesses) == access and snapshot(m) == before
    checks.append('EDU OFF stays device-free with usable prompt')
    # Program allocation and boot assets are unchanged outside CLOCK.
    assert len((OUT/'clock/storage.bin').read_bytes()) == 12288
    report = dict(passed=True, checks=checks, clock_sha256=cm['sha256'],
        clock_storage_sha256=meta['clock_storage_sha256'], artifacts=meta['artifacts'],
        board_access=False, boards_flashed=False)
    (OUT/'clock-summary-test-results.json').write_text(json.dumps(report, indent=2)+'\n')
    for check in checks:
        print('PASS', check, flush=True)


if __name__ == '__main__':
    main()
