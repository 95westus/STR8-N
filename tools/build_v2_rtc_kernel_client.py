"""Build the application-level client for integrated RTC/I2C qualification."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as link

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-kernel/client'


def main():
    (OUT / 'asm').mkdir(parents=True, exist_ok=True)
    link.OUT = OUT
    link.SOURCE = ROOT / 'tools/v2-rtc'
    memory, symbols = link.assemble('kernel-client', 0x2000, shutil.which('wdc02as'),
        shutil.which('wdcln'), source=link.SOURCE)
    assert symbols['CLIENT_END'] <= 0x2400
    body = link.dense_image(memory, 0x2000, symbols['CLIENT_END'])
    lines = (OUT / 'asm/kernel-client.s19').read_text().splitlines()
    lines = [line for line in lines if not line.startswith('S9')]
    lines.append(link.record('9', 0x2000, b''))
    (OUT / 'kernel-client.s19').write_text('\n'.join(lines)+'\n', encoding='ascii')
    (OUT / 'manifest.json').write_text(json.dumps(dict(entry=0x2000,bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),symbols=symbols),indent=2)+'\n')
    print('Kernel fixture', len(body), 'bytes; default READ does not set time')


if __name__ == '__main__':
    main()
