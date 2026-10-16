"""Build an isolated offline crypto adapter candidate; never opens a board."""
import hashlib
import json
import shutil

import build_v2_config as compiler
from build_bank_maint_v2 import long_branches
from build_v2_crypto_status import ROOT, SOURCE, commands

OUT = ROOT / 'BUILD/v2-crypto-adapter-offline'
ADAPTER = ROOT / 'tools/v2-rtc/crypto-adapter.inc'
WIRE = ROOT / 'tools/v2-rtc/rtc-service.asm'
EQU = ROOT / 'src/v2-rtc-kernel/service-eq.inc'


def main():
    stage = OUT / 'source'
    stage.mkdir(parents=True, exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    for name in ('build.json', 'test-results.json', 'crypto-adapter.bin',
                 'rtc-fixture.bin', 'gateway-fixture.bin'):
        (OUT / name).unlink(missing_ok=True)
    engine = SOURCE.read_text()
    first = engine.index('; Fail-closed slots.')
    last = engine.index('EXPECT_REV DB', first)
    engine = engine[:first] + '        INCLUDE "crypto-adapter.inc"\n' + engine[last:]
    exports = ('CA_ENABLE', 'CA_ADDRESS', 'CA_MHZ', 'CA_PHASE', 'CA_FAULT_CODE',
               'CA_FAULT_PHASE', 'CA_STOP_ERROR', 'CA_BROKEN', 'CA_DELAY',
               'CA_DELAY_UNITS', 'SCL_RELEASE', 'READ_BYTE', 'WRITE_BYTE', 'STOP_BUS')
    engine = engine.replace('        CODE\n', ''.join(f'        XDEF {n}\n' for n in exports) + '        CODE\n', 1)
    (stage / 'crypto-adapter.asm').write_text(long_branches(engine), encoding='ascii')
    (stage / 'crypto-adapter.inc').write_text(
        long_branches(ADAPTER.read_text()).replace('BM_LONG_', 'CA_LONG_'), encoding='ascii')
    # Reuse the exact common VIA bit primitives without RTC register operations.
    wire = WIRE.read_text()
    low = wire[wire.index('\nINIT '):wire.index('\nREAD_REGS\n', wire.index('\nINIT '))]
    low += wire[wire.index('\nSTART_BUS '):wire.index('\nBUSY DB')]
    (stage / 'crypto-wire.inc').write_text(low, encoding='ascii')
    (stage / 'crypto-service-eq.inc').write_bytes(EQU.read_bytes())
    (stage / 'crypto-commands.inc').write_text('COMMANDS\n' + ''.join(
        '        DB ' + ','.join(f'${v:02X}' for v in cmd) + '\n'
        for cmd in commands()), encoding='ascii')
    compiler.OUT, compiler.SOURCE = OUT, stage
    cells, symbols = compiler.assemble('crypto-adapter', 0x2000,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=stage)
    end = symbols['APP_END']
    assert symbols['START'] == 0x2000 and end < 0x3000
    image = bytes(cells.get(a, 0) for a in range(0x2000, end))
    (OUT / 'crypto-adapter.bin').write_bytes(image)
    sources = (SOURCE, ADAPTER, WIRE, EQU,
               ROOT / 'tools/v2-rtc/rtc-flash-gateway.asm',
               ROOT / 'tools/v2-rtc/rtc-api.inc', ROOT / 'tools/v2-rtc/i2c-api.inc')
    manifest = dict(format=1, entry=0x2000, end=end, size=len(image),
        sha256=hashlib.sha256(image).hexdigest(),
        sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        hardware_tested=False, resident_integration=False, default_enabled=False,
        clocks_mhz=[1, 2, 4, 8], symbols=symbols)
    # Independently linked existing RTC code, used only for coexistence tests.
    compiler.SOURCE = ROOT / 'tools/v2-rtc'
    rtc, _ = compiler.assemble('rtc-service', 0x3000,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=compiler.SOURCE)
    (OUT / 'rtc-fixture.bin').write_bytes(bytes(rtc.get(a, 0)
        for a in range(0x3000, max(rtc) + 1)))
    for name in ('rtc-api.inc', 'i2c-api.inc'):
        shutil.copyfile(ROOT / 'tools/v2-rtc' / name, stage / name)
    (stage / 'split-defs.inc').write_text(
        'PROVIDER_SIZE EQU $1000\nPROVIDER_BASE EQU $8000\n'
        'PROVIDER_BITS EQU $EE\nPRIVATE_BASE EQU $6669\nPRIVATE_SIZE EQU 57\n')
    compiler.SOURCE = stage
    gateway, _ = compiler.assemble('rtc-gateway', 0x6500,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=stage,
        source_file=ROOT / 'tools/v2-rtc/rtc-flash-gateway.asm')
    (OUT / 'gateway-fixture.bin').write_bytes(bytes(gateway.get(a, 0)
        for a in range(0x6500, max(gateway) + 1)))
    manifest['fixtures'] = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                            for name in ('rtc-fixture.bin', 'gateway-fixture.bin')}
    (OUT / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Offline adapter candidate: {len(image)} bytes; disabled by default; no board I/O')


if __name__ == '__main__':
    main()
