"""Build the separate RAM-only UTC baseline client; no firmware changes."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as compiler
from beta4_migration import s19, read_s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-kernel/utc-client'


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    compiler.OUT = OUT
    source = ROOT / 'tools/v2-rtc'
    compiler.SOURCE = source
    cells, symbols = compiler.assemble('rtc-sync-client', 0x2000,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=source)
    body = compiler.dense_image(cells, 0x2000, symbols['CLIENT_END'])
    assert len(body) < 256
    (OUT / 'rtc-sync-client.s19').write_bytes(s19(cells, 0x2000))
    read_s19(OUT / 'rtc-sync-client.s19')
    (OUT / 'build.json').write_text(json.dumps(dict(entry=0x2000, bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(), symbols=symbols), indent=2)+'\n')
    print('Built RAM UTC client:', len(body), 'bytes; explicit SET at G2003 only')
    cells,symbols = compiler.assemble('rtc-sample-client',0x2000,
        shutil.which('wdc02as'),shutil.which('wdcln'),source=source)
    body = compiler.dense_image(cells,0x2000,symbols['CLIENT_END'])
    assert len(body)<256
    (OUT/'rtc-sample-client.s19').write_bytes(s19(cells,0x2000))
    read_s19(OUT/'rtc-sample-client.s19')
    (OUT/'sample-build.json').write_text(json.dumps(dict(entry=0x2000,bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),snapshot_address=0x2440,symbols=symbols),indent=2)+'\n')
    print('Built snapshot UTC client:',len(body),'bytes; result at $2440 survives banner READ')


if __name__ == '__main__':
    main()
