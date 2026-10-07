"""Build optional RAM RTC service and its application client; no board access."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as compiler
from beta4_migration import s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-phase1'
SOURCE = ROOT / 'tools/v2-rtc'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    compiler.OUT = OUT
    compiler.SOURCE = SOURCE
    manifest = dict(format=1, allocation='3000-3FFF', hardware_tested=False, images={})
    for name, address in [('rtc-service', 0x3000), ('rtc-client', 0x2000)]:
        cells, symbols = compiler.assemble(name, address, shutil.which('wdc02as'),
                                           shutil.which('wdcln'), source=SOURCE)
        end = max(cells) + 1
        if name == 'rtc-service':
            assert end <= 0x3F00, 'Service overlaps public buffers'
            # Initialize all owned RAM, including capture-valid flag and gaps.
            cells = {a: cells.get(a, 0) for a in range(0x3000, 0x4000)}
        else:
            assert end <= 0x3000, 'Client overlaps service'
        body = bytes(cells[a] for a in range(address, max(cells) + 1))
        (OUT / f'{name}.bin').write_bytes(body)
        (OUT / f'{name}.s19').write_bytes(s19(cells, address))
        manifest['images'][name] = dict(entry=address, code_end=end,
            size=len(body), sha256=hashlib.sha256(body).hexdigest(), symbols=symbols)
    (OUT / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Built optional RTC service at $3000 and client at $2000')


if __name__ == '__main__':
    main()
