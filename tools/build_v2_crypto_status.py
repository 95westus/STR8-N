"""Build an offline 65C02 crypto status engine; no board access or integration."""
import hashlib
import json
import shutil
from pathlib import Path

import build_v2_config as compiler
from build_bank_maint_v2 import long_branches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-crypto-status-offline'
SOURCE = ROOT / 'tools/v2-rtc/crypto-status.asm'


def crc(data):
    """CryptoAuthentication CRC, independent of the project's flash CRC."""
    value = 0
    for byte in data:
        for bit in range(8):
            mix = ((byte >> bit) & 1) ^ (value >> 15)
            value = (value << 1) & 0xffff
            if mix:
                value ^= 0x8005
    return value.to_bytes(2, 'little')


def commands():
    # Word addressing in configuration zone: offsets 0, 8, 12 and 84.
    # Word 21 contains LockValue [86] and LockConfig [87].
    for opcode, word in ((0x30, 0), (0x02, 0), (0x02, 2), (0x02, 3), (0x02, 21)):
        body = bytes((7, opcode, 0, word, 0))
        yield b'\x03' + body + crc(body)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('build.json', 'test-results.json', 'crypto-status.bin'):
        (OUT / name).unlink(missing_ok=True)
    stage = OUT / 'source'
    stage.mkdir(exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    (stage / 'crypto-status.asm').write_text(long_branches(SOURCE.read_text()), encoding='ascii')
    (stage / 'crypto-commands.inc').write_text('COMMANDS\n' + ''.join(
        '        DB ' + ','.join(f'${v:02X}' for v in cmd) + '\n'
        for cmd in commands()), encoding='ascii')
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise SystemExit('WDC02AS and WDCLN must be on PATH')
    compiler.OUT, compiler.SOURCE = OUT, stage
    cells, symbols = compiler.assemble('crypto-status', 0x2000, assembler, linker, source=stage)
    end = symbols['APP_END']
    assert symbols['START'] == 0x2000 and end < 0x3000
    image = bytes(cells.get(a, 0) for a in range(0x2000, end))
    (OUT / 'crypto-status.bin').write_bytes(image)
    manifest = dict(format=1, entry=0x2000, end=end, size=len(image),
                    sha256=hashlib.sha256(image).hexdigest(),
                    source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    hardware_tested=False, hardware_adapter=False,
                    resident_integration=False, symbols=symbols,
                    commands=[c.hex() for c in commands()])
    (OUT / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Offline crypto status engine: {len(image)} bytes; hardware adapter unavailable')


if __name__ == '__main__':
    main()
