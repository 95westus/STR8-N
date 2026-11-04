"""Combine the frozen b14 MON kit and OIP1 installer, offline only.

No F/MON rebuild, device access, or WDC migration. One shared JE writer.
"""
import argparse
import binascii
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from build import long_branches
from build_mon_absent import data_rows
from str8build.assemble import Assembly
from str8build.formats import save, sha


def replace_once(body, old, new):
    assert body.count(old) == 1, ('Unexpected source shape', old)
    return body.replace(old, new, 1)


def build(out, source):
    assert not out.exists(), 'Fresh output required'
    out.mkdir(parents=True)
    for name in ('s', 'payload'):
        shutil.copytree(source / name, out / name)
    for name in ('prototype-report.json', 'mon-absent-build.json'):
        shutil.copy2(source / name, out / name)
    a = object.__new__(Assembly)
    a.out, a.assembler, a.linker = out, shutil.which('wdc02as'), shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled = []
    a.symbols = json.loads((source / 'symbols.json').read_text())
    core = out / 's/core'
    mon = (HERE / 'mon-absent-tool.inc').read_text()
    init, rest = mon.split('        JSR J_CRC_INIT\n', 1)
    check, rest = ('        JSR J_CRC_INIT\n' + rest).split('        LDX #<MA_MENU\n', 1)
    ops = rest[rest.index('MA_DESTROY:\n'):rest.index('MA_MENU: DB')]
    # Keep the old fixed-target operations byte-for-byte at source level.
    # Normalize only the known mutable OIP1 bytes before checking the whole app.
    init = replace_once(init, '        LDA #1\n        STA DC_BINARY\n', '        STZ DC_BINARY\n')
    verify = '''CK_VERIFY:
        LDX #0
        LDA #0
CK_CLEAR_STATE:
        STA OI_HEADER,X
        INX
        CPX #OI_STATE_END-OI_HEADER
        BNE CK_CLEAR_STATE
''' + check + '        RTS\n'
    oi = (HERE / 'installer.inc').read_text()
    oi = 'OI_PTR EQU V2_PTR\nOI_STAGE EQU $6800\nOI_PORT_CAPTURE:\n' + oi[oi.index('        LDA DC_LAST\n'):]
    oi = replace_once(oi, 'OI_PAGES: DB 0\n', 'OI_PAGES: DB 0\nOI_STATE_END:\n')
    f_image = (source / 'payload/f-offline-component.bin').read_bytes()
    fsum = binascii.crc_hqx(f_image, 65535)
    prefix = '''        MODULE RECOVERY_KIT
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
'''
    body = f'F_SUM_LO EQU ${fsum & 255:02X}\nF_SUM_HI EQU ${fsum >> 8:02X}\n'
    body += init + '        JSR CK_VERIFY\n        JMP CK_MENU\n' + verify
    body += (HERE / 'recovery-kit-menu.inc').read_text() + '\n' + ops
    body += 'MA_OK: DB 13,10,"MON KIT DONE",13,10,0\nMA_ERROR: DB 13,10,"MON KIT REFUSED/FAILED",13,10,0\n'
    body += oi + '\n        INCLUDE "prototype-engine.inc"\n'
    slots = []
    for name, page in (('A', 'a0'), ('B', 'b0')):
        slot = (source / f'payload/monitor-{page}-offline-component.bin').read_bytes()
        assert len(slot) == 4096
        slots.append(slot)
        body += f'MA_IMAGE_{name}:\n' + data_rows(slot)
    body += 'MA_SUM: DB 0,0\nINSTALLER_END:\nCK_END:\n'
    (core / 'recovery-kit.asm').write_text(long_branches(prefix + body + '        ENDMOD\n        END\n'))
    data, sy = a.link('core', 'recovery-kit', 0x200, 'CK_END')
    assert sy['CK_END'] <= 0x6500 and sy['MA_SUM'] == sy['CK_END'] - 2
    data = data[:-2] + binascii.crc_hqx(data[:-2], 65535).to_bytes(2, 'little')
    a.emit('recovery-kit.bin', data)
    save(out / 'symbols.json', a.symbols)
    unchanged = {}
    for name in ('f-offline-component.bin', 'monitor-a0-offline-component.bin', 'monitor-b0-offline-component.bin'):
        assert (out / 'payload' / name).read_bytes() == (source / 'payload' / name).read_bytes()
        unchanged[name] = sha((out / 'payload' / name).read_bytes())
    report = dict(passed=True, hardware=False, serial_access=False, source_build=str(source),
                  app_bytes=len(data), load_address='0200', end_exclusive=f'{sy["CK_END"]:04X}',
                  remaining_application_bytes=0x6500-sy['CK_END'],
                  shared_writer_bytes=sy['JE_END']-sy['JE_ENTER'], shared_writer_copies=1,
                  embedded_MON_bytes=sum(map(len, slots)), app_sha256=sha(data),
                  separate_tool_bytes=(source/'payload/mon-kit.bin').stat().st_size+(source/'payload/ram-installer-offline.bin').stat().st_size,
                  unchanged_firmware=unchanged,
                  mutable_self_check_exclusion='OI_HEADER through OI_PAGES reset to canonical zeros before every I/T/confirmed-X',
                  commands=['?', 'T', 'I', 'X (ERASE confirmation)', 'Q'],
                  sources={p.name:sha(p.read_bytes()) for p in (Path(__file__), HERE/'recovery-kit-menu.inc', HERE/'mon-absent-tool.inc', HERE/'installer.inc')},
                  compiled=a.compiled,
                  limitations=['F-dependent b14 RAM app, not a WDCMONv2 bootstrap', 'No physical hardware qualification'])
    save(out / 'recovery-kit-build.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source', type=Path, default=ROOT/'BUILD/pr04-b14-mon-absent-r5')
    x = p.parse_args()
    print(json.dumps(build(x.out.resolve(), x.source.resolve()), indent=2))
