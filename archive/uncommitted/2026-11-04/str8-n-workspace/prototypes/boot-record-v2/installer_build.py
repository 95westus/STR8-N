"""Offline OIP1 RAM component builder and pure host-side frame helpers.

No serial/device/network access. build.py calls build_installer after generating
the PR03 symbols and shared journal engine. This module never rebuilds F/MON.
"""
import binascii
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HEADER_BYTES = 20
SECTOR_BYTES = 4096
LOAD_ADDRESS = 0x2000
STAGE_ADDRESS = 0x6800


def crc16(data):
    return binascii.crc_hqx(bytes(data), 0xffff)


def target_allowed(bank, sector):
    """sector is the canonical high address byte, e.g. 0x80 or 0xF0."""
    return (0 <= bank <= 3 and sector in range(0x80, 0x100, 0x10)
            and (bank < 3 or sector in (0x80, 0x90, 0xe0)))


def frame_header(bank, sector, payload=None, preimage_crc=0):
    """Create canonical OIP1 read header or write header (payload exactly 4 KiB).

    Caller sends `I` + text terminator, waits for SEND OIP1 HEADER, sends this
    header, then for a write waits for SEND 4096 before sending payload. A read
    waits for READ SECTOR+CRC, then receives 4096 literal bytes + CRC16LE.
    """
    if not target_allowed(bank, sector):
        raise ValueError('Protected or noncanonical target')
    if payload is not None and len(payload) != SECTOR_BYTES:
        raise ValueError('Opaque writes require one complete 4096-byte sector')
    if not 0 <= preimage_crc <= 0xffff:
        raise ValueError('Preimage CRC must be 16 bit')
    if payload is None and preimage_crc:
        raise ValueError('Read requests have zero CRC fields')
    header = (b'OIP1\x01' + bytes([int(payload is not None), bank, sector])
              + SECTOR_BYTES.to_bytes(2, 'little')
              + preimage_crc.to_bytes(2, 'little')
              + (crc16(payload) if payload is not None else 0).to_bytes(2, 'little')
              + bytes(4))
    return header + crc16(header).to_bytes(2, 'little')


def rlp1_header(body, address=LOAD_ADDRESS, entry=LOAD_ADDRESS):
    if not body or address < 0x2000 or address + len(body) > 0x6000:
        raise ValueError('RLP1 tool must fit the escrowed 2000-5FFF range')
    if not address <= entry < address + len(body):
        raise ValueError('Entry must lie inside verified load')
    h = (b'RLP1\x01\x01' + address.to_bytes(2, 'little')
         + len(body).to_bytes(2, 'little') + entry.to_bytes(2, 'little')
         + crc16(body).to_bytes(2, 'little'))
    return h + crc16(h).to_bytes(2, 'little')


def build_installer(a, core, out, long_branches):
    source = '''        MODULE RAM_OPAQUE_INSTALLER
        XDEF INSTALLER_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
''' + (HERE/'installer.inc').read_text() + '''
        INCLUDE "prototype-engine.inc"
INSTALLER_END:
        ENDMOD
        END
'''
    (core/'ram-installer.asm').write_text(
        long_branches(source).replace('P_LONG_', 'OI_LONG_'))
    body, symbols = a.link('core', 'ram-installer', LOAD_ADDRESS, 'INSTALLER_END')
    assert symbols['INSTALLER_START'] == LOAD_ADDRESS
    assert symbols['INSTALLER_END'] <= 0x6000, 'Installer exceeds RLP1 RAM window'
    a.emit('ram-installer-offline.bin', body)
    a.emit('ram-installer-offline.rlp1', rlp1_header(body) + body)
    return dict(start=LOAD_ADDRESS, end=symbols['INSTALLER_END'], bytes=len(body),
                entry=symbols['INSTALLER_START'], staging_start=STAGE_ADDRESS,
                staging_bytes=SECTOR_BYTES, writer_start=symbols['JE_ENTER'],
                writer_bytes=symbols['JE_END'] - symbols['JE_ENTER'],
                protocol='OIP1', header_bytes=HEADER_BYTES,
                writes='Whole 4096-byte sectors only; B0/B1/B2:8-F and B3:8/9/E',
                protected='B3:A/B monitor, C/D journal, F root',
                validation='Header, canonical bank/sector, exact length, receive flags, '
                           'payload CRC and current preimage CRC before reservation/erase',
                wear='JE mode 2 durable conservative attempt reservation before target erase; '
                     'identical sectors do not erase or increment',
                preservation='Only escrowed tool span and reserved 6800-77FF staging; '
                             'JE preserves configuration and counter history; no RTC writes',
                interruptions='Opaque target may be torn. Protected F/MON/journal remain; '
                              'read fresh target CRC before retrying. Lost response can be '
                              'resolved by reading and sending identical sector.',
                framing_failure='Header/payload CRC, receive error, partial transfer timeout '
                                'or blocked binary TX locks the tool in a raw drain loop; '
                                'reset is required and delayed bytes cannot become commands.',
                limitations='CRC detects transfer errors, not authenticity. IRQ disabled; '
                            'external NMI/electrical brownout not hardware-qualified.')


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True,
                        help='Existing isolated PR03 build; adds RAM tool only')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT/'tools'))
    from prepare_monitor_size import offline
    from str8build.assemble import Assembly
    from str8build.formats import save
    from build import long_branches
    offline()
    out = args.build.resolve()
    report = json.loads((out/'prototype-report.json').read_text())
    if not report.get('dual_console'):
        raise ValueError('OIP1 requires the PR03 dual-console RAM worker')
    if not report.get('journal_duplicate_guard'):
        raise ValueError('Rebuild with --opaque-installer: OIP1 requires the guarded journal writer')
    a = object.__new__(Assembly)
    a.out = out
    a.assembler = shutil.which('wdc02as')
    a.linker = shutil.which('wdcln')
    assert a.assembler and a.linker
    a.symbols = json.loads((out/'symbols.json').read_text())
    a.compiled = []
    report['installer'] = build_installer(a, out/'s/core', out, long_branches)
    report['compiled'] += a.compiled
    save(out/'symbols.json', a.symbols)
    save(out/'prototype-report.json', report)
    print(json.dumps(report['installer'], indent=2))


if __name__ == '__main__':
    main()
