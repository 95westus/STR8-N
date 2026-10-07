"""Build MAINT 1.6 with RTC-sector and service-RAM ownership guards."""
import hashlib
import json
from pathlib import Path
import shutil

import build_bank_maint_recovery as base
import build_v2_recovery as fw
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-kernel/maint'
KERNEL_OUT = ROOT/'BUILD/v2-rtc-kernel'
VERSION = '1.6'
JOURNAL = False


def main():
    fw.OUT = KERNEL_OUT
    fw.SOURCE = fw.OUT / 'source'
    base.OUT, base.VERSION = OUT, VERSION
    base.main()
    (OUT / 'manifest.json').unlink(missing_ok=True)
    (OUT / (base.NAME + '.s19')).unlink(missing_ok=True)
    (OUT / 'str8n-bank-maint-1.6-2000.s19').unlink(missing_ok=True)
    (fw.OUT / f'str8n-maint-{VERSION}-b1-8000-9fff.bin').unlink(missing_ok=True)
    path = OUT / (base.NAME + '.asm')
    text = path.read_text()
    # The base builder already expanded branches; insert guards before expansion
    # is repeated, then let the shared linker relax every generated label.
    marker = 'CONFIRM_ALLOWED:        STZ DANGER'
    assert text.count(marker) == 1
    text = text.replace(marker, '''                        LDA DB
                        CMP #3
                        BNE CONFIRM_ALLOWED
                        LDA TO+1
                        AND #$F0
                        CMP #$80
                        BEQ CONFIRM_NO
CONFIRM_ALLOWED:        STZ DANGER''')
    marker = '                        LDA LAST+1\n                        CMP #$67\n                        BCS RANGE_FAIL\n'
    assert text.count(marker) == 1
    text = text.replace(marker, '''                        LDA LAST+1
                        CMP #$67
                        BCS RANGE_FAIL
                        CMP #$65
                        BCC RTC_RAM_CONTINUE
                        BIT SVC_ACTIVE
                        BNE RANGE_FAIL
RTC_RAM_CONTINUE:
''')
    marker = 'MAP_STORE_KIND:        STA MAP_KIND'
    assert marker in text
    text = text.replace(marker, '''                        PHA
                        LDA MAPBANK
                        CMP #3
                        BNE RTC_MAP_OTHER
                        LDA MAPSEC
                        CMP #$80
                        BNE RTC_MAP_OTHER
                        PLA
                        LDA #'I'
                        STA MAP_KIND
                        RTS
RTC_MAP_OTHER:          PLA
MAP_STORE_KIND:        STA MAP_KIND''')
    text = text.replace('MAP_DESCRIPTION:      LDA MAP_KIND', '''MAP_DESCRIPTION:      LDA MAP_KIND
                        CMP #'I'
                        BNE RTC_MAP_DESCRIPTION
                        LDX #<RTC_OWNER_TEXT
                        LDY #>RTC_OWNER_TEXT
                        JMP PRINT
RTC_MAP_DESCRIPTION:   LDA MAP_KIND''')
    # Access annotation for the new reserved sector, independent of its contents.
    marker = 'MAP_ACCESS:           LDX #<MAP_WRITABLE_TEXT'
    start = text.index(marker)
    end = text.index('MAP_RANGE_PREFIX:', start)
    access = text[start:end]
    needle = '                        CMP #$A0\n'
    assert needle in access
    access = access.replace(needle, '                        CMP #$80\n                        BEQ RTC_MAP_PROTECTED\n' + needle)
    access = access.replace('                        LDX #<MAP_PROTECTED_TEXT',
                            'RTC_MAP_PROTECTED:     LDX #<MAP_PROTECTED_TEXT')
    text = text[:start] + access + text[end:]
    text = text.replace('B3:A-F', 'B3:8,A-F')
    text = text.replace('MAP_TITLE:             JSR PRINT', '''MAP_TITLE:             JSR PRINT
                        LDA SVC_ACTIVE
                        BPL RTC_RAM_MAP_DONE
                        LDX #<RTC_RAM_TEXT
                        LDY #>RTC_RAM_TEXT
                        JSR PRINT
RTC_RAM_MAP_DONE:''')
    text = text.replace('S record; + continued;', 'I RTC/I2C; S record; + continued;')
    text = text.replace('TITLE:                  DB',
        'RTC_OWNER_TEXT: DB "RTC/I2C services",0\n'
        'RTC_RAM_TEXT: DB "RAM 0200-64FF program; 6500-66FF services protected",$0D,$0A,0\nTITLE:                  DB')
    text = text.replace('BM_LONG_', 'LEGACY_LONG_')
    if JOURNAL:
        text=text.replace("CMP #$80\n                        BEQ CONFIRM_NO", "CMP #$80\n                        BEQ CONFIRM_NO\n                        CMP #$90\n                        BEQ CONFIRM_NO")
        text=text.replace("CMP #$80\n                        BNE RTC_MAP_OTHER", "CMP #$80\n                        BEQ JOURNAL_MAP_KIND\n                        CMP #$90\n                        BNE RTC_MAP_OTHER\nJOURNAL_MAP_KIND:")
        text=text.replace("CMP #$80\n                        BEQ RTC_MAP_PROTECTED", "CMP #$80\n                        BEQ RTC_MAP_PROTECTED\n                        CMP #$90\n                        BEQ RTC_MAP_PROTECTED")
        text=text.replace('RTC/I2C services','RTC/I2C or journal services').replace('B3:8,A-F','B3:8-F')
    path.write_text(long_branches(text).replace('BM_LONG_', 'RTC_BM_LONG_'))
    link = base.link
    link.OUT, link.SOURCE = OUT, OUT / 'asm'
    memory, symbols = link.assemble(base.NAME, 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'), source_file=path)
    memory, symbols = fw.relax_branches(path, memory, symbols,
        lambda: link.assemble(base.NAME, 0x2000, shutil.which('wdc02as'), shutil.which('wdcln'), source_file=path))
    body = link.dense_image(memory, 0x2000, symbols['BM_END'])
    assert symbols['BM_END'] < 0x4000 and len(body) + 24 <= 8192
    records = [link.record('0', 0, ('STR8-N bank maintenance '+VERSION).encode())]
    records += [link.record('1', a, body[a-0x2000:a-0x2000+32]) for a in range(0x2000, symbols['BM_END'], 32)]
    records += [link.record('9', 0x2000)]
    (OUT / f'str8n-bank-maint-{VERSION}-2000.s19').write_text('\n'.join(records) + '\n')
    header = b'SR\x01\x3F' + (0x2000).to_bytes(2, 'little') + len(body).to_bytes(2, 'little') + b'MAINT'.ljust(16, b'\0')
    storage = header + body + bytes([255]) * (8192 - len(header) - len(body))
    (fw.OUT / f'str8n-maint-{VERSION}-b1-8000-9fff.bin').write_bytes(storage)
    (OUT / 'manifest.json').write_text(json.dumps(dict(version=VERSION, entry=0x2000,
        bytes=len(body), end=symbols['BM_END'], symbols=symbols,
        program_sha256=hashlib.sha256(body).hexdigest(), storage_sha256=hashlib.sha256(storage).hexdigest(),
        hardware_tested=False), indent=2) + '\n')
    print(f'MAINT {VERSION}: {len(body)} bytes; stored B1:8/9; protects optional/system sectors and active service RAM')


if __name__ == '__main__':
    main()
