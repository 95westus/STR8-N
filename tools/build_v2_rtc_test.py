"""Build the RAM-only EDU RTC probe; no board access or flash writes."""
import hashlib
import json
import shutil
from pathlib import Path
import build_v2_a24 as base

OUT = base.ROOT / 'BUILD/v2-rtc-test'
SOURCE = base.ROOT / 'tools/v2-rtc-test'
NAME = 'str8n-v2-rtc-test-2000'

def main():
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise SystemExit('WDC02AS and WDCLN must be on PATH')
    base.OUT = OUT
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    for filename in ('build.json', 'test-results.json', NAME + '.bin', NAME + '.s19'):
        (OUT / filename).unlink(missing_ok=True)
    memory, symbols = base.assemble(NAME, 0x2000, assembler, linker, source=SOURCE)
    image = base.dense_image(memory, 0x2000, symbols['PROBE_END'])
    assert symbols['START'] == 0x2000 and symbols['PROBE_END'] < 0x7000
    (OUT / (NAME + '.bin')).write_bytes(image)
    shutil.copyfile(OUT / 'asm' / (NAME + '.s19'), OUT / (NAME + '.s19'))
    (OUT / 'build.json').write_text(json.dumps({
        'entry': 0x2000, 'end': symbols['PROBE_END'], 'size': len(image),
        'sha256': hashlib.sha256(image).hexdigest(), 'symbols': symbols,
        'physical_hardware_tested': False,
    }, indent=2) + '\n')
    print(f'RTC probe: {len(image)} bytes at $2000; {OUT}')

if __name__ == '__main__':
    main()
