"""Build an exact-board RAM updater for the F configuration candidate; no board I/O.

Default: migrate alpha24 E settings or preserve current F settings and update F.
--extension: install the matching optional S/R extension on the current core.
Requires the built candidate, and alpha24 build.json for migration worker symbols.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as firmware

ALPHA24_F_SHA = '43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a'
POCKET = slice(0xFD0, 0xFE0)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_config(data):
    if len(data) != 16:
        return False
    a = b = 0
    for value in data[:14]:
        a = (a + value) & 255
        b = (b + a) & 255
    address = int.from_bytes(data[3:5], 'little')
    return (data[0] == 1 and data[1] < 2 and data[2] < 4 and data[5] >= 10
            and data[6] < 2 and data[7:14] == bytes(7)
            and data[14:] == bytes([a, b])
            and (data[6] == 1 or address < 0xE0 or 0x200 <= address < 0x6900
                 or address >= 0x8000))


def plan(source, extension=False):
    if len(source) != 8192:
        raise ValueError('Readback must be exactly 8192 bytes: B3 E followed by F')
    e, f = source[:4096], source[4096:]
    candidate = (firmware.OUT / f'{firmware.STEM}-f000-ffff.bin').read_bytes()
    normalized = f[:0xFD0] + b'\xff' * 16 + f[0xFE0:]
    if normalized == candidate:
        report_path = firmware.OUT / 'build.json'
        settings = f[POCKET]
        origin = 'FFD0'
    elif sha(f) == ALPHA24_F_SHA and not extension:
        report_path = firmware.ROOT / 'BUILD/v2-alpha24/build.json'
        settings = e[0xFF0:]
        origin = 'EFF0'
    else:
        raise ValueError('F firmware is not exact alpha24 or this candidate outside its pocket')
    if extension:
        built = (firmware.OUT / f'{firmware.STEM}-e000-efff.bin').read_bytes()
        new = e[:0x800] + built[0x800:0xF00] + e[0xF00:]
        return e, new, f, 0xE0, report_path, 'unchanged'
    # Explicit host policy: unknown settings are not silently discarded.
    if not valid_config(settings) and settings not in (bytes(16), b'\xff' * 16):
        raise ValueError('Invalid configuration; resolve it before building an updater')
    saved = settings if valid_config(settings) else b'\xff' * 16
    new = candidate[:0xFD0] + saved + candidate[0xFE0:]
    return f, new, e, 0xF0, report_path, origin


def build(source, out, extension=False):
    old, new, guard, sector, report_path, origin = plan(source, extension)
    if old == new:
        raise ValueError('Selected sector already matches the requested image')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    name = 'str8n-config-' + ('e-install' if extension else 'f-update') + '-2000'
    target = out / f'{name}.s19'
    if target.exists():
        raise FileExistsError(target)
    stage = out / 'asm'
    stage.mkdir(exist_ok=True)
    for filename, data in [('e-old-image.inc', old), ('e-new-image.inc', new),
                           ('guard-image.inc', guard)]:
        firmware.include_bytes(stage / filename, data)
    worker = json.loads(report_path.read_text())['worker']
    (stage / 'e-worker-addresses.inc').write_text(''.join(
        f'{key:24} EQU ${worker[key]:04X}\n' for key in ('V2W_SNAPSHOT', 'V2W_MUTATE')))
    text = (firmware.ROOT / 'src/v2a24/str8n-v2-e-repair-2000.asm').read_text()
    # All I/O after mutation is through the initialized RAM ABI of the source core.
    text = text.replace('JSR     $F00D', 'JSR     $7E6D').replace('JSR     $F010', 'JSR     $7E70')
    text = text.replace('LDA     #$E0', f'LDA     #${sector:02X}')
    text = text.replace('                        JSR     V2W_SNAPSHOT\n                        JSR     E_COMPARE_OLD',
                        '                        JSR     E_GUARD\n                        BCC     E_MISMATCH\n'
                        '                        JSR     V2W_SNAPSHOT\n                        JSR     E_COMPARE_OLD', 1)
    text = text.replace('                        JMP     $F007\nE_MISMATCH:',
                        'E_FAILED_WAIT:          JSR     $7E70\n'
                        "                        CMP     #'Y'\n"
                        '                        BNE     E_FAILED_WAIT\n'
                        '                        JMP     E_ROLLBACK\nE_MISMATCH:', 1)
    text = text.replace('"B3:E REPAIR FAILED"', '"WRITE FAILED; Y retries old image"')
    if not extension:
        text = text.replace('B3:E', 'B3:F')
    # Check the other complete sector too: includes the migrating E settings or
    # configured F identity. Refuse changes after the host readback was taken.
    routine = f'''E_GUARD:               LDA     #${0xF0 if extension else 0xE0:02X}
                        STA     V2_SECTOR
                        JSR     V2W_SNAPSHOT
                        LDA     #<E_GUARD_IMAGE
                        STA     E_SRC
                        LDA     #>E_GUARD_IMAGE
                        STA     E_SRC+1
                        JSR     E_COMPARE_IMAGE
                        LDA     #${sector:02X}
                        STA     V2_SECTOR
                        RTS
E_GUARD_IMAGE:          INCLUDE "guard-image.inc"
'''
    text = text.replace('E_NEW:                  INCLUDE', routine + 'E_NEW:                  INCLUDE')
    asm = out / f'{name}-source.asm'
    asm.write_text(text, encoding='ascii')
    previous = firmware.OUT
    try:
        firmware.OUT = out
        memory, symbols = firmware.assemble(name, 0x2000, shutil.which('wdc02as'),
                                            shutil.which('wdcln'), source_file=asm,
                                            include_dirs=(stage,))
    finally:
        firmware.OUT = previous
    end = symbols['E_END']
    if end > 0x6900 or set(memory) != set(range(0x2000, end)):
        raise ValueError('Updater exceeds application RAM or is not dense')
    lines = [firmware.record('0', 0, f'STR8-N {firmware.VERSION} guarded update'.encode())]
    lines.extend(firmware.record('1', address, bytes(memory[a] for a in range(address, min(address+32, end))))
                 for address in range(0x2000, end, 32))
    lines.append(firmware.record('9', 0x2000))
    target.write_text('\n'.join(lines) + '\n', encoding='ascii')
    if firmware.read_s19(target) != (memory, 0x2000):
        raise ValueError('Updater S19 roundtrip failed')
    (out / 'staged-sector.bin').write_bytes(new)
    manifest = dict(version=firmware.VERSION, sector=f'{sector:02X}',
                    source_ef_sha256=sha(source), old_sha256=sha(old),
                    staged_sha256=sha(new), s19_sha256=sha(target.read_bytes()),
                    configuration_source=origin, board_installed=False, symbols=symbols)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return target, new, symbols


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readback', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--extension', action='store_true')
    args = parser.parse_args()
    print(build(args.readback.read_bytes(), args.out, args.extension)[0])
