"""Build commented opaque FLASH page variants offline; never opens a device."""
import argparse
import binascii
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from str8build.assemble import Assembly
from str8build.formats import save, sha


def long_branches(source):
    inverse = dict(BEQ='BNE', BNE='BEQ', BCS='BCC', BCC='BCS', BMI='BPL',
                   BPL='BMI', BVS='BVC', BVC='BVS')
    rows, n = [], 0
    for line in source.splitlines():
        m = re.fullmatch(r'\s*(BEQ|BNE|BCS|BCC|BMI|BPL|BVS|BVC|BRA)\s+(\w+)\s*', line)
        if not m:
            rows.append(line)
        elif m[1] == 'BRA':
            rows.append('        JMP ' + m[2])
        else:
            n += 1
            skip = 'BM_LONG_' + str(n)
            rows += ['        ' + inverse[m[1]] + ' ' + skip,
                     '        JMP ' + m[2], skip + ':']
    return '\n'.join(rows) + '\n'


def crc(data):
    return binascii.crc_hqx(data, 0xffff)


def build(out, source):
    assert not out.exists(), 'Use a fresh output directory'
    report = json.loads((source / 'prototype-report.json').read_text())
    assert report['banner'] == '2.0proto b15' and report['journal_duplicate_guard']
    f = (source / 'payload/f-offline-component.bin').read_bytes()
    assert sha(f) == '1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8'
    engine = (source / 's/core/prototype-engine.inc').read_text()
    assert 'JSR JE_CHECK_DUPLICATES' in engine
    out.mkdir(parents=True)
    shutil.copytree(source / 's', out / 's')
    shutil.copytree(source / 'payload', out / 'payload')
    a = object.__new__(Assembly)
    a.out, a.assembler, a.linker = out, shutil.which('wdc02as'), shutil.which('wdcln')
    assert a.assembler and a.linker
    a.compiled, a.symbols = [], json.loads((source / 'symbols.json').read_text())
    core = out / 's/core'
    original = (HERE / 'installer.inc').read_text()
    slices = {'apply': original[original.index('OI_APPLY:'):original.index('OI_FRAME_BAD:')],
              'target': original[original.index('OI_TARGET:'):original.index('; Raw receive')],
              'crc': original[original.index('OI_PRINT:'):original.index('OI_SIGNATURE:')]}
    for name, value in slices.items():
        (core / f'bank-monitor-{name}.inc').write_text(value)
    variants = []
    # Alternative placements of the same application, not two images to combine.
    for origin in (0x8000, 0x9000):
        name = f'bank-monitor-{origin:04x}'
        layout = core / 'bank-monitor-layout.inc'
        # One short page at 8; alternate 9-A placement demonstrates a span.
        allocation = 4096 if origin == 0x8000 else 8192
        layout.write_text(f'BM_HOME_FIRST EQU ${origin >> 8:02X}\n'
                          f'BM_HOME_AFTER EQU ${(origin + allocation) >> 8:02X}\n'
                          f'BM_F_CRC_LO EQU ${crc(f) & 255:02X}\n'
                          f'BM_F_CRC_HI EQU ${crc(f) >> 8:02X}\n')
        (core / (name + '.asm')).write_text(long_branches((HERE / 'bank-monitor.asm').read_text()))
        body, sy = a.link('core', name, 0x200, 'BM_END')
        assert sy['BM_END'] <= 0x2000, 'Keep M editable RAM wholly above this tool'
        body = bytearray(body)
        code_crc = crc(body[:sy['BM_CODE_END'] - 0x200])
        offset = sy['BM_CODE_CRC'] - 0x200
        body[offset:offset + 2] = code_crc.to_bytes(2, 'little')
        pages = (len(body) + 255) // 256
        layout.write_text(layout.read_text() + f'BM_COPY_PAGES EQU {pages}\n'
                          f'BM_HOME_ADDRESS EQU ${sy["BM_HOME"]:04X}\n')
        entry_name = name + '-entry'
        (core / (entry_name + '.asm')).write_text((HERE / 'bank-monitor-entry.asm').read_text())
        entry, _ = a.link('core', entry_name, origin, 'BM_ROM_END')
        assert len(entry) <= 128
        image = (entry.ljust(128, b'\xff') + bytes(body).ljust(pages * 256, b'\xff')).ljust(allocation, b'\xff')
        assert len(image) == allocation
        a.emit(name + '.bin', image)
        a.emit(name + '-ram.bin', body)
        # Freeze each variant's layout alongside the generated source.
        (core / (name + '-layout.inc')).write_bytes(layout.read_bytes())
        (core / (name + '.asm')).write_text((core / (name + '.asm')).read_text().replace(
            '"bank-monitor-layout.inc"', f'"{name}-layout.inc"'))
        (core / (entry_name + '.asm')).write_text((core / (entry_name + '.asm')).read_text().replace(
            '"bank-monitor-layout.inc"', f'"{name}-layout.inc"'))
        variants.append(dict(name=name, entry=origin, image_bytes=len(image), ram_bytes=len(body),
                             ram_end=sy['BM_END'], copy_end=0x200 + pages * 256,
                             sha256=sha(image), ram_sha256=sha(body), code_crc16=code_crc,
                             own_sectors=list(range(origin >> 12, (origin + allocation) >> 12))))
    save(out / 'symbols.json', a.symbols)
    save(out / 'prototype-report.json', report)
    result = dict(hardware=False, serial_access=False, installed=False,
                  source_build=str(source), f_sha256=sha(f), f_crc16=crc(f),
                  source_hashes={p.name: sha(p.read_bytes()) for p in
                                 (Path(__file__), HERE / 'bank-monitor.asm', HERE / 'bank-monitor-entry.asm')},
                  unchanged_engine_sha256=sha(engine.encode()),
                  unchanged_oip_slices={k: sha(v.encode()) for k, v in slices.items()},
                  variants=variants, compiled=a.compiled,
                  implemented=['B0..B3 data bank', 'D 16-byte dump', 'M 1-8 RAM bytes',
                               'F 1-8 flash bytes by sector preservation', 'I 4K erase',
                               'YES confirmation', 'Q validate MON B/A or REC',
                               'code and b15 F CRC admission', 'durable wear reservation'],
                  planned=['named application directory', 'FLASH/IO/FILE/PROGRAM launcher',
                           'whole-image upload from this page', 'hardware qualification'])
    save(out / 'bank-monitor-build.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'BUILD/pr04-b15-cancel-r3')
    p.add_argument('--out', type=Path, required=True)
    x = p.parse_args()
    print(json.dumps(build(x.out.resolve(), x.source.resolve()), indent=2))
