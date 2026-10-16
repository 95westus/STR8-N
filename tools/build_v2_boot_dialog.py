"""Build a separate beta25 boot-dialog candidate; no ports or flashing."""
import hashlib
import json
import shutil
from pathlib import Path

from beta4_migration import crc, s19
from build_v2_spi_resident import assemble

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'BUILD/v2-beta25'
OUT = ROOT / 'BUILD/v2-boot-dialog'
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    shutil.copytree(BASE, OUT, dirs_exist_ok=True)
    for path in OUT.glob('*test-results.json'):
        path.unlink()
    (OUT / 'qualification-summary.json').unlink(missing_ok=True)
    meta = json.loads((BASE / 'build.json').read_text())
    path = OUT / 'local-display/source/local-display.asm'
    text = path.read_text()
    first = text.index('LOCAL_ENTRY:')
    last = text.index('PRINT:  JMP TZ_PRINT', first)
    text = text[:first] + '''LOCAL_ENTRY:
        STA KIND
        CMP #3
        BNE LOCAL_TIME
        JSR $7E7F
        JSR BN_READ
        LDA BN_LENGTH
        BEQ BN_LOCAL_DONE
        JSR $7E7F
        JMP BN_SHOW
LOCAL_TIME:
        LDA $7D27
        CMP #2
        BEQ BN_LOCAL_DONE
        LDA KIND
        CMP #1
        BNE LOCAL_BOOT_DISPLAY
        JSR TRIM_DISPLAY
LOCAL_BOOT_DISPLAY:
        JSR TZ_SHOW_LOCAL
        LDA KIND
        BNE BN_LOCAL_DONE
        JMP $7E7F
BN_LOCAL_DONE:
        RTS
''' + text[last:]
    path.write_text(text)
    body, local, _ = assemble(path.parent, 'local-display', 0x6700, 'APP_END', 0x6707)
    assert len(body) <= 1790
    asset = body + b'\xff' * (1790-len(body))
    asset += crc(asset).to_bytes(2, 'big')
    (OUT / 'local-display/asset.bin').write_bytes(asset)
    meta.update(local_symbols=local, local_code_bytes=len(body), local_asset_sha256=sha(asset))

    path = OUT / 'storage-status/source/storage-status.asm'
    text = path.read_text()
    first = text.index('DISPLAY:')
    pending = text[text.index('        LDA KIND\n', first):text.index('NO_PENDING:', first)]
    last = text.index('MODE_TEXT:', first)
    text = text[:first] + '''DISPLAY:
        STA KIND
        CMP #3
        BCC STORAGE_DISPLAY
        JMP STORAGE
STORAGE_DISPLAY:
        CMP #2
        BNE STATUS_DISPLAY
        JMP TIME_ONLY
STATUS_DISPLAY:
        TAX
        BNE STATUS_RAM
        LDA #3
        STA KIND
        JSR LOCAL_DISPLAY
        STZ KIND
STATUS_RAM:
        LDX #<RAM_TEXT
        LDY #>RAM_TEXT
        JSR PRINT
        LDA $7D0B
        JSR $7E7C
        LDA $7D0A
        JSR $7E7C
        JSR $7E7F
        LDX #<EDU_TEXT
        LDY #>EDU_TEXT
        JSR PRINT
        LDA $7D27
        CMP #2
        JSR MODE_TEXT
''' + pending + '''NO_PENDING:
        LDA $7D27
        CMP #2
        BEQ RETURN
        JSR ALLOCATION
        JSR CLOCK
        LDA KIND
        BEQ RETURN
        LDA $7D2A
        BEQ EUI_ABSENT
        LDA $6BEE
        PHA
        JSR SHOW_EUI
        PLA
        STA $6BEE
        BRA RETURN
EUI_ABSENT:
        LDX #<EUI_UNAVAILABLE
        LDY #>EUI_UNAVAILABLE
        JSR PRINT
RETURN: SEC
        RTS
TIME_ONLY:
        LDA $7D2A
        BEQ TIME_UNAVAILABLE
        JSR $6504
        BCC TIME_UNAVAILABLE
        JSR LOCAL_DISPLAY
        SEC
        RTS
TIME_UNAVAILABLE:
        LDX #<CLOCK_UNAVAILABLE
        LDY #>CLOCK_UNAVAILABLE
        JSR PRINT
        SEC
        RTS
CLOCK:  LDA $7D2A
        BEQ TIME_UNAVAILABLE
        LDA $7D25
        PHA
        LDA KIND
        BEQ CLOCK_BOOT
        LDA #1
        STA $7D25
CLOCK_BOOT:
        JSR $6504
        BCC CLOCK_NO_EVENT
        LDA $66C1
        AND #8
        BRA CLOCK_EVENT_READY
CLOCK_NO_EVENT:
        LDA #0
CLOCK_EVENT_READY:
        PHA
        BEQ CLOCK_CALL
        JSR $7E7F
CLOCK_CALL:
        JSR $8907
        PLA
        BEQ CLOCK_FORMAT
        JSR $7E7F
CLOCK_FORMAT:
        JSR LOCAL_DISPLAY
        PLA
        STA $7D25
        RTS
''' + text[last:]
    text = text.replace('RAM_TEXT DB 13,10,13,10,', 'RAM_TEXT DB 13,10,', 1)
    # Share the allocation prefix to make room for conditional event spacing.
    text = text.replace('"SSRAM: ', '"')
    text = text.replace('ALLOCATION:\n', 'ALLOCATION:\n        JSR SRAM_PREFIX\n', 1)
    text = text.replace('        LDX #<WORK_TEXT\n', '        JSR SRAM_PREFIX\n        LDX #<WORK_TEXT\n', 1)
    text = text.replace('APP_END:', '''SRAM_PREFIX:
        LDX #<SRAM_TEXT
        LDY #>SRAM_TEXT
        JMP PRINT
SRAM_TEXT DB "SSRAM: ",0
APP_END:''', 1)
    path.write_text(text)
    body, status, _ = assemble(path.parent, 'storage-status', 0x6E00, 'APP_END', 0x6E07)
    assert len(body) <= 2558, len(body)
    asset = body + b'\xff' * (2558-len(body))
    asset += crc(asset).to_bytes(2, 'big')
    (OUT / 'boot-status/asset.bin').write_bytes(asset)
    meta.update(status_symbols=status, status_code_bytes=len(body), status_asset_sha256=sha(asset))

    # Keep all SPI helper addresses fixed: the four added UTC-label bytes
    # replace four bytes in the failure message, before the helper code.
    stage = OUT / 'banner/source'
    shutil.copytree(BASE / 'resident-banner/source', stage, dirs_exist_ok=True)
    for name in ('kernel-rtc-api.inc', 'journal-eq.inc', 'outage-format.inc'):
        shutil.copyfile(BASE / 'resident-banner/source' / name, stage / name)
    path = stage / 'rtc-banner.asm'
    text = path.read_text().replace('" [power-fail]"', '" [power-fail UTC]"')
    text = text.replace('"RTCC: PF logging failed."', '"RTCC: PF log failed."')
    path.write_text(text)
    body, banner, _ = assemble(stage, 'rtc-banner', 0x8900, 'BANNER_END', 0x890D)
    prior = json.loads((BASE / 'banner/build.json').read_text())
    assert len(body) == prior['bytes']
    for name, address in prior['symbols'].items():
        if name.startswith(('SP_', 'SPI_')):
            assert banner[name] == address, name
    sector = bytearray((BASE / 'str8n-rtc-component-8000-8fff.bin').read_bytes())
    sector[0x900:0x900+len(body)] = body
    sector[-2:] = crc(sector[:-2]).to_bytes(2, 'big')
    assert crc(sector) == 0
    (OUT / 'str8n-rtc-component-8000-8fff.bin').write_bytes(sector)
    (OUT / 'str8n-rtc-component-8000-8fff.s19').write_bytes(
        s19(dict(enumerate(sector, 0x8000)), 0x8000))
    (OUT / 'banner/build.json').write_text(json.dumps(dict(bytes=len(body), sha256=sha(body), symbols=banner), indent=2)+'\n')
    meta.update(boot_dialog_order=True, power_fail_timezone='UTC', hardware_tested=False,
                board_access=False, boards_flashed=False)
    for name in meta['artifacts']:
        meta['artifacts'][name] = sha((OUT / name).read_bytes())
        if name != 'str8n-rtc-component-8000-8fff.bin':
            assert (OUT / name).read_bytes() == (BASE / name).read_bytes(), name
    (OUT / 'build.json').write_text(json.dumps(meta, indent=2)+'\n')
    print('UNFLASHED boot-dialog candidate:', meta['local_code_bytes'], 'local;', meta['status_code_bytes'], 'status bytes')


if __name__ == '__main__':
    main()
