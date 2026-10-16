"""Build the RAM crypto status display against the qualified adapter image."""
import hashlib
import json
import shutil

import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
from build_v2_crypto_adapter import ROOT, OUT as ADAPTER

OUT = ROOT / 'BUILD/v2-crypto-display'
SOURCE = ROOT / 'tools/v2-rtc/crypto-display.asm'


def main():
    meta = json.loads((ADAPTER / 'build.json').read_text())
    test = json.loads((ADAPTER / 'test-results.json').read_text())
    assert test['passed'] and test['sha256'] == meta['sha256']
    image = (ADAPTER / 'crypto-adapter.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == meta['sha256']
    stage = OUT / 'source'
    stage.mkdir(parents=True, exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    for name in ('build.json', 'test-results.json'):
        (OUT / name).unlink(missing_ok=True)
    names = ('START', 'RESULT', 'VALID', 'REVISION', 'SERIAL', 'LOCKS',
             'FIELD_ERRORS', 'CLEANUP_ERROR', 'CA_ADDRESS')
    (stage / 'crypto-symbols.inc').write_text(''.join(
        f'{n} EQU ${meta["symbols"][n]:04X}\n' for n in names), encoding='ascii')
    (stage / 'crypto-display.asm').write_text(long_branches(SOURCE.read_text()), encoding='ascii')
    compiler.OUT, compiler.SOURCE = OUT, stage
    cells, symbols = compiler.assemble('crypto-display', 0x2800,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=stage)
    assert symbols['CLIENT_START'] == 0x2800 and symbols['CLIENT_END'] < 0x3000
    client = bytes(cells.get(a, 0) for a in range(0x2800, symbols['CLIENT_END']))
    (OUT / 'client.bin').write_bytes(client)
    package = bytearray(symbols['CLIENT_END'] - 0x2000)
    package[:len(image)] = image
    package[0x800:] = client
    (OUT / 'crypto-display.bin').write_bytes(package)
    (OUT / 'crypto-display.s19').write_bytes(s19(dict(enumerate(package, 0x2000)), 0x2800))
    result = dict(entry=0x2800, first=0x2000, end=symbols['CLIENT_END'],
        client_bytes=len(client), total_staged_bytes=len(package),
        sha256=hashlib.sha256(package).hexdigest(), adapter_sha256=meta['sha256'],
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), symbols=symbols,
        hardware_installed=False)
    (OUT / 'build.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'RAM display: {len(client)} client bytes; G 2800; disabled until target configured')


if __name__ == '__main__':
    main()
