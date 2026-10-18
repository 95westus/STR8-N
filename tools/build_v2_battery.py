"""Unflashed beta25 battery-age candidate, based on the current shared assets.

No serial imports or board access. Reuse the PJ6 tail and qualified byte writer;
boot loads a sealed helper into staging after the status formatter tail-returns.
"""
import hashlib
import json
import shutil
from pathlib import Path

from beta4_migration import crc, s19
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches
import build_v2_clock as clock

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'BUILD/v2-map-assets'
OUT = ROOT/'BUILD/v2-battery'
sha = lambda data: hashlib.sha256(data).hexdigest()


def writer():
    text = (ROOT/'tools/v2-rtc/clock-offset.inc').read_text()
    text = text[text.index('OFFSET_SAVE:\n'):text.index('OFFSET_WORD DB')]
    text = text.replace('OFFSET_', 'BT_').replace('TZ_READ', 'BT_READ')
    text = text.replace('BT_HEADER', 'BT_RECORD_HEADER')
    for old, new in [('TZ_FREE', 'BT_FREE'), ('TZ_SEQ', 'BT_SEQ'), ('TZ_MAGIC', 'BT_MAGIC')]:
        text = text.replace(old, new)
    first = text.index('        LDA BT_PENDING\n')
    last = text.index('        LDA #<BT_RECORD_BYTES\n', first)
    text = text[:first]+'''        LDX #6
BT_PAYLOAD_COPY:
        LDA BT_PENDING,X
        STA BT_RECORD_BYTES+8,X
        DEX
        BPL BT_PAYLOAD_COPY
'''+text[last:]
    first = text.index('        LDA TZ_OFFSET\n')
    last = text.index('        SEC\n        RTS\n', first)
    text = text[:first]+'''        LDA BT_FOUND
        BEQ BT_REFUSE
        LDX #6
BT_READBACK:
        LDA BT_PAYLOAD,X
        CMP BT_PENDING,X
        BNE BT_REFUSE
        DEX
        BPL BT_READBACK
'''+text[last:]
    return text+'''BT_JOURNAL_MAGIC DB "PJ",6,1
BT_BANK DB 0
BT_LED DB 0
BT_INDEX DB 0
BT_ERROR DB 0
BT_RECORD_BYTES DS 32
BT_ZP DS 32
'''


def sealed(body, size):
    assert len(body) <= size-2, (len(body), size)
    result = body+b'\xff'*(size-2-len(body))
    result += crc(result).to_bytes(2, 'big')
    assert crc(result) == 0
    return result


def main():
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for p in OUT.glob('*test-results.json'):
        p.unlink()
    (OUT/'qualification-summary.json').unlink(missing_ok=True)
    meta = json.loads((BASE/'build.json').read_text())
    assert meta['version'] == '2.0b25'
    core = (ROOT/'tools/v2-rtc/battery-core.inc').read_text()+writer()
    byte = meta['worker']['V2W_BYTE']
    # CLOCK retains its existing three-sector allocation and all prior commands.
    source = OUT/'clock/input'
    text = (BASE/'clock/input/clock-summary.asm').read_text()
    text = text.replace('        JSR OFFSET_TRY\n', '        JSR BT_TRY\n        JSR OFFSET_TRY\n', 1)
    text = text.replace('UI_IDENTITY:\n        JSR EUI_SHOW\n',
                        'UI_IDENTITY:\n        JSR EUI_SHOW\n        JSR BT_PROCESS\n', 1)
    # Shorten help to fit battery administration without taking another sector.
    first, last = text.index('HELP_TEXT DB '), text.index('\nUTC_TEXT DB')
    text = text[:first]+'''HELP_TEXT DB "TIME/R STATUS/S EUI HISTORY SHOW n",13,10
        DB "SET yyyy-mm-dd hh:mm:ss UTC; OFFSET +/-HH:MM; TRIM -127..+127",13,10
        DB "ACK; ACCEPT EUI; CLEAR n/ALL; HELP/?; Q/QUIT",13,10
        DB "BATTERY [REPLACED | yyyy-mm-dd | LIMITS ww rr]",13,10
        DB "Limits: 01..99 30-day months, ww < rr. Changes confirmed.",13,10,0
'''+text[last:]
    extra = f'BT_FLASH_BYTE EQU ${byte:04X}\n'+core+(ROOT/'tools/v2-rtc/clock-battery.inc').read_text()
    text = text.replace('APP_END:\n', extra+'\nAPP_END:\n', 1)
    text = text.replace('TITLE DB "CLOCK 1.7"', 'TITLE DB "CLOCK 1.8"', 1)
    (source/'clock-battery.asm').write_text(text)
    clock.OUT, clock.SOURCE = OUT/'clock', source
    clock.SOURCE_NAME, clock.VERSION, clock.MAX_END = 'clock-battery.asm', '1.8', 0x5000
    clock.main()
    cm = json.loads((OUT/'clock/build.json').read_text())
    body = (OUT/'clock/clock.bin').read_bytes()
    record = b'SR\x01\x3f\x00\x20'+len(body).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+body
    assert len(record) <= 12288, len(record)
    (OUT/'clock/storage.bin').write_bytes(record+b'\xff'*(12288-len(record)))

    # The unused tail of the already reserved B2:D status sector holds the helper.
    stage = OUT/'battery/source'
    stage.mkdir(parents=True, exist_ok=True)
    local = (ROOT/'tools/v2-rtc/local-time.inc').read_text()
    checksum = local[local.index('TZ_CRC:\n'):local.index('TZ_ABS:\n')]
    text = f'''        MODULE BATTERY
        XDEF START
        XDEF APP_END
TZ_PTR EQU $D6
BT_FLASH_BYTE EQU ${byte:04X}
        CODE
START:  DB "BS",1,3
        JMP BT_ENTRY
BT_ENTRY:
        JSR WEAR_SHOW
        LDA $7D27
        CMP #2
        BEQ BT_ENTRY_DONE
        JSR $7E7F
        JSR BT_PROCESS
BT_ENTRY_DONE:
        SEC
        RTS
PRINT:  STX $D0
        STY $D1
        LDY #0
BT_PRINT_LOOP:
        LDA ($D0),Y
        BEQ BT_PRINT_DONE
        JSR $7E6D
        INY
        BNE BT_PRINT_LOOP
        INC $D1
        BRA BT_PRINT_LOOP
BT_PRINT_DONE:
        RTS
TZ_SUM DS 2
'''+checksum+core+(ROOT/'tools/v2-rtc/flash-wear.inc').read_text()+'\nAPP_END:\n        ENDMOD\n'
    (stage/'battery.asm').write_text(long_branches(text).replace('BM_LONG_', 'BAT_LONG_'))
    body, bs, _ = assemble(stage, 'battery', 0x6E00, 'APP_END', 0x6E07)
    # Stop before the resident flash worker at $7800.
    asset = sealed(body, 2560)
    (OUT/'battery/asset.bin').write_bytes(asset)

    # Tail-return from status is essential: loading battery replaces 6E00 staging.
    stage = OUT/'storage-status/source'
    text = (stage/'storage-status.asm').read_text()
    marker = 'RETURN: SEC\n        RTS\n'
    assert text.count(marker) == 1
    text = text.replace(marker, '''RETURN:
        LDA #6
        JMP $EF09
''', 1)
    # Save 12 bytes for the tail route by shortening this existing diagnostic.
    text = text.replace('"Allocation uninitialized"', '"Uninitialized"')
    (stage/'storage-status.asm').write_text(text)
    body, ss, _ = assemble(stage, 'storage-status', 0x6E00, 'APP_END', 0x6E07)
    status = sealed(body, 2560)
    (OUT/'boot-status/asset.bin').write_bytes(status)

    stage = OUT/'loader/source'
    text = (BASE/'loader/source/version-loader.asm').read_text()
    marker = '''        CMP #5
        BNE RANGE_READY
        LDX #$E8
        LDY #$76
'''
    assert marker in text
    text = text.replace(marker, '''        CMP #5
        BCC RANGE_READY
        LDX #$E8
        LDY #$76
        CMP #5
        BEQ RANGE_READY
        LDX #$D2
        LDY #$78
''', 1)
    # Shared failure routine already emits a diagnostic and returns to monitor.
    first, last = text.index('BAD:    '), text.index('TIME_WORD DB')
    text = text[:first]+'BAD:    JMP STORAGE_ASSET_FAIL\n'+text[last:]
    text = text.replace('ERROR_TEXT DB 13,10,"Status error",13,10,0\n', '')
    (stage/'version-loader.asm').write_text(text)
    loader, ls, _ = assemble(stage, 'version-loader', 0xEF00, 'AUX_END', 0xEF0C)
    assert len(loader) <= 254, len(loader)
    image = bytearray((BASE/'str8n-v2-recovery-e000-efff.bin').read_bytes())
    image[0xF00:0xFFE] = loader+b'\xff'*(254-len(loader))
    image[-2:] = crc(image[:-2]).to_bytes(2,'big')
    assert crc(image) == 0 and crc(image[:0x800]) == 0
    stem = 'str8n-v2-recovery-e000-efff'
    (OUT/(stem+'.bin')).write_bytes(image)
    (OUT/(stem+'.s19')).write_bytes(s19(dict(enumerate(image,0xE000)),0xF004))
    meta.update(battery_age=True, battery_default_months=[12,24], battery_month_days=30,
        flash_wear_warnings=True, flash_wear_thresholds=[50000,80000],
        battery_symbols=bs, battery_code_bytes=bs['APP_END']-0x6E00,
        battery_asset_address=0xD200, battery_asset_bytes=len(asset), battery_asset_sha256=sha(asset),
        clock_version='1.8', clock_sha256=cm['sha256'], clock_storage_sha256=sha((OUT/'clock/storage.bin').read_bytes()),
        status_symbols=ss, status_code_bytes=ss['APP_END']-0x6E00, status_asset_sha256=sha(status),
        version_loader_symbols=ls, version_loader_bytes=len(loader),
        hardware_tested=False, board_access=False, boards_flashed=False)
    meta['artifacts'] = {n:sha((OUT/n).read_bytes()) for n in meta['artifacts']}
    (OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('UNFLASHED beta25 BATTERY: CLOCK',cm['bytes'],'boot helper',bs['APP_END']-0x6E00,
          'status',ss['APP_END']-0x6E00,'loader',len(loader),'bytes; F/A/B unchanged')


if __name__ == '__main__':
    main()
