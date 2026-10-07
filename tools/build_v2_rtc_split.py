"""Measure a flash-code/RAM-gateway RTC candidate. No board access or install.

Reads the accepted phase 1 source without changing it. All mutable symbols are
bound to RAM; the flash image is sealed and entered through its versioned table.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil

import build_v2_config as compiler
from beta4_migration import s19

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-phase2-split'
SOURCE = ROOT / 'tools/v2-rtc'
PROVIDER_BASE = 0x8000
PROVIDER_BANK = 3
TRANSPORT_EXTRA = None
PROVIDER_FORMAT = 1


def crc(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xFFFF
    return value


def main():
    stage = OUT / 'source'
    stage.mkdir(parents=True, exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    for name in ('build.json', 'test-results.json', 'i2c-test-results.json',
                 'provider.bin', 'gateway.bin', 'gateway.s19'):
        (OUT / name).unlink(missing_ok=True)
    api = (SOURCE / 'rtc-api.inc').read_text()
    api = api.replace('; Optional RAM RTC service v1. Caller reserves $3000-$3FFF while installed.',
                      '; Flash RTC provider; mutable state is RAM. Call through the RAM gateway.')
    def rebase(match):
        value = int(match[1], 16)
        if 0x3000 <= value < 0x3040:
            value += PROVIDER_BASE - 0x3000
        elif 0x3F00 <= value <= 0x3F3F:
            value += 0x27C0
        return f'${value:04X}'
    (stage / 'rtc-api.inc').write_text(re.sub(r'\$([0-9A-F]{4})', rebase, api))
    original = (SOURCE / 'rtc-service.asm').read_text()
    begin, end = original.index('\nBUSY DB 0'), original.index('\nSERVICE_END')
    state = original[begin:end] + '''
I_ADDRESS DB 0
I_FLAGS DB 0
I_TX_LEFT DB 0
I_RX_LEFT DB 0
I_ERROR DB 0
I_PTR_LO DB 0
I_REG_PACKET DS 10
'''
    private, cursor = {}, 0x6669
    for line in state.strip().splitlines():
        name, directive, argument = line.split()
        assert directive in ('DB', 'DS')
        assert directive != 'DB' or argument == '0', 'Nonzero private defaults need an initializer'
        private[name] = cursor
        cursor += 1 if directive == 'DB' else int(argument)
    provider_source = original[:begin] + '\n' + ''.join(
        f'{name} EQU ${address:04X}\n' for name, address in private.items()) + original[end:]
    provider_source = provider_source.replace('INCLUDE "rtc-api.inc"',
        'INCLUDE "rtc-api.inc"\n        INCLUDE "i2c-api.inc"')
    provider_source = provider_source.replace('START   DB "RC",1,4', 'START   DB "RC",1,5')
    if PROVIDER_FORMAT!=1:
        provider_source=provider_source.replace('START   DB "RC",1,5',f'START   DB "RC",{PROVIDER_FORMAT},5')
    provider_source = provider_source.replace('        JMP DO_ACK\n',
        '        JMP DO_ACK\n        JMP PUBLIC_I2C\n')
    transport_begin = provider_source.index('\nREAD_REGS\n')
    transport_end = provider_source.index('\nSTART_BUS ', transport_begin)
    provider_source = provider_source[:transport_begin] + '\n        INCLUDE "i2c-transport.inc"\n' + provider_source[transport_end:]
    provider_source = provider_source.replace(
        '; Application must reserve $3000-$3FFF and provide exclusive VIA1 ownership.',
        '; Resident flash extension; private RAM state and exclusive VIA1 ownership.')
    if TRANSPORT_EXTRA:
        provider_source=provider_source.replace('\nSERVICE_END','\n        INCLUDE "eeprom-transfer.inc"\nSERVICE_END')
        from build_bank_maint_v2 import long_branches
        (stage/'eeprom-transfer.inc').write_text(long_branches(Path(TRANSPORT_EXTRA).read_text()).replace('BM_LONG_','EE_LONG_'))
    (stage / 'rtc-provider.asm').write_text(provider_source)
    shutil.copyfile(SOURCE / 'i2c-api.inc', stage / 'i2c-api.inc')
    shutil.copyfile(SOURCE / 'i2c-transport.inc', stage / 'i2c-transport.inc')
    compiler.OUT, compiler.SOURCE = OUT, stage
    cells, provider_symbols = compiler.assemble('rtc-provider', PROVIDER_BASE,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=stage)
    provider = compiler.dense_image(cells, PROVIDER_BASE, provider_symbols['SERVICE_END'])
    provider += crc(provider).to_bytes(2, 'big')
    assert crc(provider) == 0 and PROVIDER_BASE + len(provider) <= 0x9000
    (OUT / 'provider.bin').write_bytes(provider)
    (stage / 'split-defs.inc').write_text(
        f'PROVIDER_SIZE EQU ${len(provider):04X}\nPROVIDER_BASE EQU ${PROVIDER_BASE:04X}\n'
        'PROVIDER_BITS EQU $EE\nPRIVATE_BASE EQU $6669\n'
        f'PRIVATE_SIZE EQU {cursor-0x6669}\n')
    shutil.copyfile(SOURCE / 'rtc-flash-gateway.asm', stage / 'rtc-gateway.asm')
    if PROVIDER_FORMAT!=1:
        path=stage/'rtc-gateway.asm';path.write_text(path.read_text().replace('LDA PROVIDER_BASE+2\n        CMP #1',f'LDA PROVIDER_BASE+2\n        CMP #{PROVIDER_FORMAT}'))
    cells, gateway_symbols = compiler.assemble('rtc-gateway', 0x6500,
        shutil.which('wdc02as'), shutil.which('wdcln'), source=stage)
    gateway_code = compiler.dense_image(cells, 0x6500, gateway_symbols['GATE_END'])
    assert gateway_symbols['GATE_END'] <= 0x6650, 'Gateway overlaps I2C request'
    assert cursor <= 0x66B0
    for address, value in enumerate(bytes.fromhex('AD 00 00 60 8D 00 00 60'), 0x66B0):
        assert address not in cells
        cells[address] = value
    gateway = bytes(cells.get(a, 0) for a in range(0x6500, 0x6700))
    (OUT / 'gateway.bin').write_bytes(gateway)
    (OUT / 'gateway.s19').write_bytes(s19(dict(enumerate(gateway, 0x6500)), 0x6500))
    manifest = dict(provider_bank=PROVIDER_BANK, provider_address=PROVIDER_BASE, provider_bytes=len(provider),
        provider_sha256=hashlib.sha256(provider).hexdigest(), provider_symbols=provider_symbols,
        gateway_code_bytes=len(gateway_code), gateway_reserved_ram_bytes=len(gateway),
        gateway_sha256=hashlib.sha256(gateway).hexdigest(), gateway_symbols=gateway_symbols,
        private_ram_bytes=cursor-0x6669, public_buffer_bytes=64, i2c_request_bytes=12,
        i2c_max_bytes=64, i2c_signature=0x6510, i2c_entry=0x6514,
        ram_buffer_thunk_bytes=8, ram_allocation='6500-66FF',
        required_provider_nmi_vector=0x7E20, requires_ram_nmi_handler_for_cross_bank=True,
        physical_hardware_tested=False, monitor_integrated=False)
    (OUT / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Flash provider {len(provider)} bytes; RAM gateway code {len(gateway_code)} bytes; '
          f'private state {cursor-0x6669} bytes; total RAM reservation {len(gateway)} bytes')


if __name__ == '__main__':
    main()
