"""Build an independent, guarded multi-bank RAM installer for RTC beta5."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_beta4_migrator as base
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-kernel/migrator'
VERSION = '2.0b5'
COMMIT_BANK = 1
MULTI_COMMIT = False
COMMIT_ADDRESS = 0x8003


def main():
    base.OUT = OUT
    base.main()
    old = OUT / (base.NAME + '.asm')
    text = old.read_text().replace('BM_LONG_', 'BASE_LONG_')
    assert text.count('MIG_NEXT:               JSR MIG_GUARD') == 1
    text = text.replace('MIG_NEXT:               JSR MIG_GUARD', '''MIG_NEXT:
                        LDX MIG_INDEX
                        LDA MIG_BANKS,X
                        STA V2_SELECTED
                        JSR V2W_SELECT
                        JSR MIG_GUARD''')
    text = text.replace('MIG_GUARD:              STZ V2_PTR', '''MIG_GUARD:
                        LDA V2_SELECTED
                        JSR V2W_SELECT
                        STZ V2_PTR''')
    text = text.replace('FOR B3:', 'FOR B')
    marker = '                        JSR MIG_PRINT\n                        LDA V2_SECTOR'
    assert text.count(marker) == 1
    text = text.replace(marker, '''                        JSR MIG_PRINT
                        LDA V2_SELECTED
                        CLC
                        ADC #'0'
                        JSR V2W_PUTC
                        LDA #':'
                        JSR V2W_PUTC
                        LDA V2_SECTOR''')
    text = text.replace('                        CMP #$09\n', '                        CMP #$0B\n')
    marker = '                        LDA #$03\n                        STA V2_FLASH_PTR'
    assert text.count(marker) == 1
    text = text.replace(marker, f'''                        LDA #{COMMIT_BANK}
                        STA V2_SELECTED
                        JSR V2W_SELECT
                        LDA #$03
                        STA V2_FLASH_PTR''')
    text = text.replace('MIG_TABLE:             INCLUDE', 'MIG_BANKS:             DS 10\nMIG_TABLE:             INCLUDE')
    if MULTI_COMMIT:
        old='''                        LDA MIG_COMMIT_AFTER
                        BEQ MIG_STORAGE_READY
                        CMP MIG_INDEX
                        BNE MIG_STORAGE_READY
                        LDA #'''+str(COMMIT_BANK)+'''
                        STA V2_SELECTED'''
        new='''                        LDX MIG_INDEX
                        LDA MIG_COMMITS-1,X
                        BEQ MIG_STORAGE_READY
                        DEC A
                        STA V2_SELECTED'''
        first=text.index('                        LDA MIG_COMMIT_AFTER\n')
        last=text.index('                        JSR V2W_SELECT\n',first)
        text=text[:first]+new+'\n'+text[last:]
        text=text.replace('MIG_BANKS:             DS 10','MIG_COMMITS:           DS 10\nMIG_BANKS:             DS 10')
    if COMMIT_ADDRESS!=0x8003:
        old='                        LDA #$03\n                        STA V2_FLASH_PTR\n                        LDA #$80\n                        STA V2_FLASH_PTR+1'
        assert text.count(old)==1
        text=text.replace(old,f'                        LDA #${COMMIT_ADDRESS&255:02X}\n                        STA V2_FLASH_PTR\n                        LDA #${COMMIT_ADDRESS>>8:02X}\n                        STA V2_FLASH_PTR+1')
    text = text.replace('STR8-N 2.0b4 + MAINT MIGRATOR; B3:8-F.',
                        f'STR8-N {VERSION} RTC/I2C MIGRATOR; MAINT B1, SYSTEM B3.')
    stage = OUT / 'asm'
    (stage / 'migration-table.inc').write_text(' DB ' + ','.join('$FF' for _ in range(90)) + '\n')
    target = OUT / 'rtc-migrator.asm'
    target.write_text(long_branches(text).replace('BM_LONG_', 'RTC_MIG_LONG_'))
    link = base.link
    link.OUT, link.SOURCE = OUT, stage
    memory, symbols = link.assemble('rtc-migrator', 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'), source_file=target)
    body = link.dense_image(memory, 0x2000, symbols['MIG_END'])
    assert symbols['MIG_END'] <= 0x4000
    lines = [link.record('0', 0, b'RTC kernel multi-bank migration template')]
    lines += [link.record('1', a, body[a-0x2000:a-0x2000+32]) for a in range(0x2000, symbols['MIG_END'], 32)]
    lines += [link.record('9', 0x2000)]
    s19 = OUT / 'rtc-migrator-2000.s19'
    s19.write_text('\n'.join(lines) + '\n')
    (OUT / 'manifest.json').write_text(json.dumps(dict(entry=0x2000, symbols=symbols,
        worker=json.loads((OUT / 'migrator.json').read_text())['worker'],
        count=symbols['MIG_PLAN_COUNT'], commit_after=symbols['MIG_COMMIT_AFTER'], commits=symbols.get('MIG_COMMITS'),
        banks=symbols['MIG_BANKS'], table=symbols['MIG_TABLE'], table_bytes=90,commit_address=COMMIT_ADDRESS,
        sha256=hashlib.sha256(s19.read_bytes()).hexdigest()), indent=2) + '\n')
    print(f'RTC migrator: {len(body)} bytes; B1 record commits after both sectors; F last when required')


if __name__ == '__main__':
    main()
