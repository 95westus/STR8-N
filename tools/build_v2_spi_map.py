"""Build an unflashed MAINT 1.9 SPI playground map against beta22.

Reuse the status formatter's read-only layout validation, including secondary
recovery and exact completed-count checks. Never initialize or probe SRAM.
"""
import json
import re
import shutil
from pathlib import Path

import build_v2_storage_maint as maint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-spi-map'


def map_source():
    source = (ROOT / 'tools/v2-spi/boot-status.asm').read_text()
    code = source[source.index('ALLOCATION:\n'):source.index('PRINT:  JMP STATUS_PRINT')]
    # State checks precede any access to service RAM reclaimed by EDU OFF.
    first = code.index('        LDX #3\nSM_HEADER:')
    code = '''ALLOCATION:
        LDA $7D27
        CMP #2
        BEQ OFF
        LDX #3
DESCRIPTOR:
        LDA $7D04,X
        CPX #3
        BEQ FLAGS
        CMP DESCRIPTOR_MAGIC,X
        BNE ABSENT
        BRA DESCRIPTOR_NEXT
FLAGS:  AND #12
        CMP #12
        BNE ABSENT
DESCRIPTOR_NEXT:
        DEX
        BPL DESCRIPTOR
        LDA $7D08
        BNE ABSENT
        LDA $7D09
        CMP #$65
        BNE ABSENT
''' + code[first:]
    code = code.replace('        BNE UNAVAILABLE\n        DEX\n        BPL SM_HEADER',
                        '        BNE ABSENT\n        DEX\n        BPL SM_HEADER')
    code = code.replace('        BPL SM_HEADER\n', '''        BPL SM_HEADER
        LDX #<ON_TEXT
        LDY #>ON_TEXT
        JSR PRINT
''', 1)
    code = code.replace('        LDX #<PROGRAM_TEXT\n', '''        LDX UNIT
        LDA RANGE_LO,X
        LDY RANGE_HI,X
        TAX
        JSR PRINT
        LDX #<PROGRAM_TEXT
''', 1)
    code += '''OFF:    LDX #<OFF_TEXT
        LDY #>OFF_TEXT
        JMP PRINT
ABSENT: LDX #<ABSENT_TEXT
        LDY #>ABSENT_TEXT
        JMP PRINT
'''
    data = source[source.index('SM_MAGIC DB'):source.index('APP_END:\n')]
    start = data.index('RAM_TEXT DB')
    end = data.index('PROGRAM_TEXT DB')
    data = data[:start] + data[end:]
    data = data.replace('SSRAM: WORKSPACE ', 'SPI playground capacity: ')
    data = data.replace('SSRAM:', 'SPI SRAM:')
    data = data.replace('Allocation uninitialized', 'Allocation uninitialized; playground split unknown')
    data = data.replace('Unavailable', 'Unavailable (hardware/read refused)')
    data += '''DESCRIPTOR_MAGIC DB "SV",1,0
ON_TEXT DB "SPI SRAM: ON; 00000-1FFFF (128 KiB external, not CPU mapped)",13,10,0
OFF_TEXT DB "SPI SRAM: OFF (EDU OFF); playground unavailable",13,10,0
ABSENT_TEXT DB "SPI SRAM: services absent/incompatible; playground unavailable",13,10,0
R16 DB "SPI programs 00800-03FFF; playground 04000-1FFDF",13,10,0
R32 DB "SPI programs 00800-07FFF; playground 08000-1FFDF",13,10,0
R48 DB "SPI programs 00800-0BFFF; playground 0C000-1FFDF",13,10,0
R64 DB "SPI programs 00800-0FFFF; playground 10000-1FFDF",13,10,0
RANGE_LO DB <R16,<R32,<R48,<R64
RANGE_HI DB >R16,>R32,>R48,>R64
'''
    # Namespace all private formatter labels; MAINT owns its own print routine.
    labels = re.findall(r'^([A-Z][A-Z0-9_]*)(?::|\s+(?:DB|DS)\b)', code + data, re.M)
    replacements = {name: 'SPI_MAP_' + name for name in labels}
    replacements.update(PRINT='PRINT', BUF='$6400', R='$6650', J_CRC='$7D38',
                        AP_CRC_INIT='SPI_MAP_CRC_INIT', AP_CRC_BYTE='SPI_MAP_CRC_BYTE')
    parts = re.split(r'("[^"\n]*")', code + data)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r'\b[A-Z][A-Z0-9_]*\b',
                             lambda m: replacements.get(m[0], m[0]), parts[index])
    return ''.join(parts)


def main():
    installed = ROOT / 'BUILD/v2-spi-startup'
    shutil.copytree(installed, OUT, dirs_exist_ok=True)
    maint.OUT = OUT
    maint.SPI_MAP = True
    maint.main()
    meta = json.loads((OUT / 'build.json').read_text())
    meta['spi_playground_map'] = True
    meta['boards_flashed'] = False
    (OUT / 'build.json').write_text(json.dumps(meta, indent=2) + '\n')


if __name__ == '__main__':
    main()
