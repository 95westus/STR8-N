"""Build CLOCK 1.7 summary on the installed boot-dialog baseline; no ports."""
import json
import shutil
from pathlib import Path

import build_v2_clock as clock

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'BUILD/v2-boot-dialog'
OUT = ROOT/'BUILD/v2-clock-summary'


def main():
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for path in OUT.glob('*test-results.json'):
        path.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    source = OUT/'clock/input'
    text = (BASE/'clock/input/clock-offset.asm').read_text()
    before = '        JSR READ_CLOCK\n        JSR EUI_SHOW\n        JSR OFFSET_SHOW\n        JMP HELP'
    assert text.count(before) == 1
    text = text.replace(before, '        JMP UI_SUMMARY', 1)
    first, last = text.index('READ_CLOCK:\n'), text.index('STATUS_COMMAND:\n')
    text = text[:first]+'''READ_CLOCK:
        JSR RTC_READ
        BCC UI_READ_ERROR
        JSR COPY_TIME
        JSR TZ_SHOW_LOCAL
        JSR NL
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        JSR UI_WEEKDAY
        JSR FORMAT_TIME
        JMP NL
UI_READ_ERROR:
        JMP ERROR
'''+text[last:]
    # CLOCK owns line framing; the shared boot formatter remains unchanged.
    text = text.replace('TZ_RENDER:\n        JSR $7E7F\n', 'TZ_RENDER:\n', 1)
    text = text.replace('TZ_LOCAL_TEXT DB "RTCC: Local ",0', 'TZ_LOCAL_TEXT DB "Local: ",0', 1)
    text = text.replace('UTC_TEXT DB "UTC ",0', 'UTC_TEXT DB "UTC:   ",0', 1)
    text = text.replace('TITLE DB "CLOCK 1.6 - UTC",13,10,0', 'TITLE DB "CLOCK 1.7",13,10,0', 1)
    # Matching identity needs one line. Keep both identities on mismatch.
    text = text.replace('        CMP #2\n        BNE EUI_STATUS_DONE',
        '        CMP #1\n        BEQ UI_EUI_MATCH\n        CMP #2\n        BNE EUI_STATUS_DONE', 1)
    marker = 'EUI_UNBOUND:\n'
    text = text.replace(marker, '''UI_EUI_MATCH:
        LDX #<UI_EUI_MATCH_TEXT
        LDY #>UI_EUI_MATCH_TEXT
        JSR PRINT
        JMP NL
'''+marker, 1)
    text = text.replace('EUI_TEXT DB "RTCC: EUI ",0', 'EUI_TEXT DB "EUI: ",0', 1)
    text = text.replace('EUI_UNAVAILABLE_TEXT DB "RTCC: EUI unavailable",0', 'EUI_UNAVAILABLE_TEXT DB "EUI: unavailable",0', 1)
    text = text.replace('EUI_UNBOUND_TEXT DB ", unbound",0', 'EUI_UNBOUND_TEXT DB " (not remembered)",0', 1)
    text = text.replace('EUI_CHANGED_TEXT DB ", changed",0', 'EUI_CHANGED_TEXT DB " (DIFFERS from remembered)",0', 1)
    first = text.index('HELP_TEXT DB ')
    last = text.index('\nUTC_TEXT DB', first)
    text = text[:first]+'''HELP_TEXT DB "Read-only queries",13,10
        DB "  TIME (R)       Local and UTC time",13,10
        DB "  STATUS (S)     Flags, trim, identity and raw registers",13,10
        DB "  EUI            Current and remembered identity",13,10
        DB "  HISTORY        Saved outages (UTC; slots 1-4)",13,10
        DB "  SHOW n         Details of saved outage n (UTC)",13,10
        DB "  OFFSET         Current fixed UTC offset",13,10
        DB "  TRIM           Current correction",13,10,13,10
        DB "Changes (confirmation required)",13,10
        DB "  SET yyyy-mm-dd hh:mm:ss   Set UTC (2000-2099)",13,10
        DB "  OFFSET +/-HH:MM          Fixed display offset (-12:00 to +14:00)",13,10
        DB "  TRIM -127..+127          Positive faster; negative slower",13,10
        DB "  ACK                     Save and acknowledge latched outage",13,10
        DB "  ACCEPT EUI              Remember current identity",13,10
        DB "  CLEAR n | CLEAR ALL     Delete saved outages",13,10,13,10
        DB "HELP (?)  Q (QUIT)",13,10,0'''+text[last:]
    text = text.replace('H_CAPTURE_TEXT DB "Recorded at (UTC convention): ",0', 'H_CAPTURE_TEXT DB "Recorded at (UTC): ",0')
    text = text.replace('H_SLOT_TEXT DB "Slot ",0', 'H_SLOT_TEXT DB "UTC slot ",0')
    text = text.replace('CAPTURE_NOTE DB "Captured outage (RTC time; no year/seconds):"', 'CAPTURE_NOTE DB "Captured outage (UTC; no year/seconds):"')
    text = text.replace('OUTAGE_TEXT DB "Power-fail down/up (raw, minute precision): "', 'OUTAGE_TEXT DB "Power-fail down/up (raw UTC, minute precision): "')
    extra = (ROOT/'tools/v2-rtc/clock-summary.inc').read_text()
    extra += '\nUI_EUI_MATCH_TEXT DB " (matches remembered)",0\n'
    extra += (ROOT/'tools/v2-rtc/board-name.inc').read_text()
    text = text.replace('APP_END:\n', extra+'\nAPP_END:\n', 1)
    (source/'clock-summary.asm').write_text(text)
    clock.OUT, clock.SOURCE = OUT/'clock', source
    clock.SOURCE_NAME, clock.VERSION, clock.MAX_END = 'clock-summary.asm', '1.7', 0x5000
    clock.main()
    meta = json.loads((OUT/'build.json').read_text())
    cm = json.loads((OUT/'clock/build.json').read_text())
    body = (OUT/'clock/clock.bin').read_bytes()
    record = b'SR\x01\x3f\x00\x20'+len(body).to_bytes(2, 'little')+b'CLOCK'.ljust(16, b'\0')+body
    assert len(record) <= 12288
    record += b'\xff'*(12288-len(record))
    (OUT/'clock/storage.bin').write_bytes(record)
    meta.update(clock_summary=True, clock_version='1.7', clock_sha256=cm['sha256'],
        clock_storage_sha256=clock.hashlib.sha256(record).hexdigest(),
        hardware_tested=False, board_access=False, boards_flashed=False)
    for name, digest in meta['artifacts'].items():
        assert (OUT/name).read_bytes() == (BASE/name).read_bytes(), name
    for name in ('boot-status/asset.bin', 'local-display/asset.bin'):
        assert (OUT/name).read_bytes() == (BASE/name).read_bytes(), name
    (OUT/'build.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('UNFLASHED CLOCK 1.7: summary UI, existing three-sector CLOCK allocation')


if __name__ == '__main__':
    main()
