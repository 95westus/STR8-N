"""Build the 816-only entry-state fixture separately from frozen RTC images."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as compiler
from beta4_migration import s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-phase1/816-probe'
SOURCE = ROOT / 'tools/v2-rtc'


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    # Failed builds must not leave an earlier runnable fixture at these paths.
    for name in ('rtc-816-state.bin', 'rtc-816-state.s19', 'build.json'):
        (OUT / name).unlink(missing_ok=True)
    compiler.OUT = OUT
    compiler.SOURCE = SOURCE
    cells, symbols = compiler.assemble('rtc-816-state', 0x2400,
        shutil.which('wdc816as'), shutil.which('wdcln'), source=SOURCE)
    assert min(cells) == 0x2400 and max(cells) < 0x2500
    body = compiler.dense_image(cells, 0x2400, max(cells) + 1)
    # MODULE/CODE can reset the WDC assembler's width declarations. A native
    # assembler's 16-bit immediate would execute as BRK in this 8-bit fixture.
    # Inspect the exact linked instruction sequence before making it runnable.
    expected = bytes.fromhex(
        '08 78 E2 30 D8 8B A9 00 48 AB 68 8D 02 25 4B 68 8D 03 25 '
        '0B 68 8D 04 25 68 8D 05 25 68 8D 01 25 18 FB A9 00 69 00 '
        '8D 00 25 38 FB 3B 8D 06 25 EB 8D 07 25 A9 00 EB A9 00 '
        '5B 5C 67 7E 00')
    assert body == expected, '816 fixture encoding mismatch: do not execute'
    (OUT / 'rtc-816-state.bin').write_bytes(body)
    (OUT / 'rtc-816-state.s19').write_bytes(s19(cells, 0x2400))
    (OUT / 'build.json').write_text(json.dumps(dict(entry=0x2400, size=len(body),
        sha256=hashlib.sha256(body).hexdigest(), symbols=symbols), indent=2) + '\n')
    print('Built 816-only G entry-state fixture at $2400; no board access')


if __name__ == '__main__':
    main()
