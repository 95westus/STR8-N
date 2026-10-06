"""Build an isolated named-flash-application candidate; no board access.

Reuses the b3 builder and exact fixed F. Only the two monitor slots and E000-E7FF
change. Legacy S/R/T bytes and EF00-EFFF remain compatible. E000-E7FF is an
explicit new allocation, NOT free space inferred from an erased-byte scan.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sys

import build_v2_recovery as fw

ROOT = fw.ROOT
OUT = ROOT / 'BUILD/v2-beta4'
SOURCE = ROOT / 'src/v2-beta4-launcher'
BASE_SOURCE = ROOT / 'src/v2-beta4'
BASELINE_DIR = ROOT / 'BUILD/v2-beta4-base'
TABLE = 0xe6f0
NAMES = ()
RESERVED = set('BDMGLFICJ?SRTWUP') | {'APPS', *(f'{c}{i}' for c in 'BJ' for i in range(4))}
_BASE_SLOT_IMAGE = fw.slot_image


def slot_image(code, symbols, page, generation, compatibility=None):
    """Publish the extra private callback for every generated candidate slot."""
    data = bytearray(_BASE_SLOT_IMAGE(code, symbols, page, generation, compatibility))
    if 'AP_TRY' in symbols:
        data[70:72] = symbols['V2_M_EDIT'].to_bytes(2, 'little')
        data[18:20] = fw.crc(data[:18] + data[32:]).to_bytes(2, 'little')
    return bytes(data)


def descriptor(name, bank=0, start=0x9000, image=None, entry=0x9010,
               ram=(0, 0), zp=(0xff, 0xff), abi=1):
    if not name.isascii() or not 1 <= len(name) <= 11 or not name.isalpha() or name != name.upper():
        raise ValueError('App name must contain 1..11 uppercase ASCII letters')
    if name in RESERVED:
        raise ValueError('App name collides with a monitor command')
    row = bytearray(32)
    row[:len(name)] = name.encode('ascii')
    row[12:14] = bytes((bank, abi))
    for offset, value in ((14, start), (16, len(image or b'')), (18, entry),
                          (20, ram[0]), (22, ram[1])):
        row[offset:offset+2] = value.to_bytes(2, 'little')
    row[24:26] = bytes(zp)
    row[26:28] = fw.crc(image or b'').to_bytes(2, 'little')
    row[30] = 0x3f if image is not None else 0xff
    row[28:30] = fw.crc(row[:28] + row[30:]).to_bytes(2, 'little')
    if image is not None:
        if not 0 <= bank <= 3 or abi != 1:
            raise ValueError('Unsupported bank or host ABI')
        if not 0x8000 <= start < entry < start + len(image) <= 0xffe0 or entry < start + 16:
            raise ValueError('Image/entry outside executable flash')
        if bank == 3 and start + len(image) > 0xa000:
            raise ValueError('Application overlaps B3 recovery reservations')
        if ram != (0, 0) and not 0x0200 <= ram[0] <= ram[1] <= 0x66ff:
            raise ValueError('Application RAM outside public range')
        if zp != (0xff, 0xff) and not 0 <= zp[0] <= zp[1] <= 0xdf:
            raise ValueError('Application zero page outside public range')
        if image[:4] != b'AP\x01\x01' or image[4:14] != row[16:26]:
            raise ValueError('Image header disagrees with descriptor')
        if fw.crc(image[:14]) != int.from_bytes(image[14:16], 'little'):
            raise ValueError('Image header CRC mismatch')
    return bytes(row)


def seal_extension(data):
    data = bytearray(data)
    if len(data) != 2048:
        raise ValueError('Extension must be exactly E000-E7FF')
    data[-2:] = fw.crc(data[:-2]).to_bytes(2, 'big')
    assert fw.crc(data) == 0
    return bytes(data)


def configure():
    """Select candidate globals before importing model or dependent builders."""
    fw.OUT = OUT
    fw.SOURCE = OUT / 'source'
    fw.VERSION = '2.0b4'
    fw.slot_image = slot_image


def prepare(baseline):
    stage = OUT / 'source'
    stage.mkdir(parents=True, exist_ok=True)
    for p in BASE_SOURCE.iterdir():
        if p.is_file():
            shutil.copyfile(p, stage / p.name)
    help_text=json.loads((SOURCE/'help.json').read_text())
    messages=json.loads((stage/'str8n-v2-text.json').read_text())
    next(m for m in messages if m['name']=='V2_HELP')['text']=help_text['monitor']
    (stage/'str8n-v2-text.json').write_text(json.dumps(messages,indent=2)+'\n')
    tail=help_text['extension'].encode('ascii')
    if len(tail)>255:raise ValueError('Extension help exceeds its bounded printer')
    (stage/'app-help.inc').write_text('AP_HELP_TEXT:\n'+''.join(
        ' DB '+','.join(f'${v:02X}' for v in (tail+b'\0')[i:i+24])+'\n'
        for i in range(0,len(tail)+1,24)))
    monitor = (stage / 'str8n-v2.asm').read_text()
    marker = 'V2_DISPATCH:           LDA     V2_LINE'
    if monitor.count(marker) != 1:
        raise ValueError('b3 dispatcher changed; review the candidate overlay')
    monitor = monitor.replace(marker, 'V2_DISPATCH:           JSR AP_TRY\n'
                             '                        BCS V2_PROMPT\n'
                             '                        LDA     V2_LINE')
    begin = monitor.index('V2_SR_DISPATCH:')
    end = monitor.index('                        INCLUDE "str8n-v2-monitor.inc"', begin)
    legacy_sr = monitor[begin:end]
    begin_map = monitor.index('V2_MAP_REQUEST:')
    end_map = monitor.index('V2_CAPTURE_BANK:', begin_map)
    legacy_map = monitor[begin_map:end_map]
    monitor = monitor[:begin_map] + monitor[end_map:]
    monitor = monitor[:begin] + '                        INCLUDE "app-fixed-symbols.inc"\n' + \
        (SOURCE / 'monitor-hook.inc').read_text() + '\n' + monitor[end:]
    (stage / 'str8n-v2.asm').write_text(monitor)
    legacy = legacy_sr + legacy_map
    for old, new in (('V2_SR_DISPATCH', 'AP_LEGACY_SR'), ('V2_SR_MISSING', 'AP_SR_MISSING'),
                     ('V2_MAP_REQUEST', 'AP_LEGACY_MAP'), ('V2_MAP_EDIT', 'AP_MAP_EDIT')):
        # Keep text-id names intact when replacing code labels.
        legacy = re.sub(r'\b' + old + r'\b', new, legacy)
    legacy = legacy.replace('AP_MAP_EDIT:            JMP V2_M_EDIT', '')
    # Formatting is inherited from b3; assert that no duplicate edit stub remains.
    legacy = re.sub(r'AP_MAP_EDIT:\s+JMP\s+V2_M_EDIT\n', '', legacy)
    (stage / 'app-legacy-dispatch.inc').write_text(legacy)
    boot = baseline['boot']
    fixed = {'AP_CRC_INIT': boot['J_CRC_INIT'], 'AP_CRC_BYTE': boot['J_CRC_BYTE'],
             'AP_SLOT_ROUTE': boot['BOOT_SR_ROUTE']}
    (stage / 'app-fixed-symbols.inc').write_text(''.join(f'{n} EQU ${v:04X}\n' for n, v in fixed.items()))


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation', type=int, default=10)
    parser.add_argument('--apps', type=Path, help='JSON list of installed flash applications; see the launcher guide')
    parser.add_argument('--out', type=Path, default=OUT, help='Isolated build directory')
    args = parser.parse_args()
    OUT = args.out.resolve()
    if not 1 <= args.generation < 0xffffffff:
        parser.error('generation must be 1..4294967294')
    (OUT / 'launcher-test-results.json').unlink(missing_ok=True)
    baseline_dir = BASELINE_DIR
    baseline = json.loads((baseline_dir / 'build.json').read_text())
    prior_f = (baseline_dir / (fw.STEM + '-f000-ffff.bin')).read_bytes()
    prior_sr = (baseline_dir / (fw.STEM + '-e000-efff.bin')).read_bytes()[0x800:0xf00]
    prepare(baseline)
    configure()
    # Use one extra slot-header pointer through the EXISTING F router. No new
    # fixed-F stub is introduced; only candidate slots publish pointer #19.
    saved = sys.argv
    try:
        sys.argv = [saved[0], '--generation', str(args.generation)]
        fw.main()
    finally:
        sys.argv = saved
    generated_f = (OUT / (fw.STEM + '-f000-ffff.bin')).read_bytes()
    if generated_f != prior_f:
        raise ValueError('Candidate changes fixed F; refuse this build')
    report_path = OUT / 'build.json'
    report = json.loads(report_path.read_text())
    report_path.unlink()  # Publish completion only after the launcher and demo pass bounds.
    stage = OUT / 'asm'
    (stage / 'app-text-ids.inc').write_text(''.join(line for line in
        (stage / 'text-ids.inc').read_text().splitlines(True) if not line.startswith('V2_SR_ERROR_TEXT ')))
    # Legacy dispatch includes branches; relax them together with the launcher.
    from build_bank_maint_v2 import long_branches
    (stage / 'app-legacy-dispatch.inc').write_text(long_branches((stage / 'app-legacy-dispatch.inc').read_text()).replace('BM_LONG_', 'AP_LEG_LONG_'))
    launcher = OUT / 'launcher.asm'
    launcher.write_text(long_branches((SOURCE / 'launcher.asm').read_text()).replace('BM_LONG_', 'AP_LONG_'))
    memory, symbols = fw.link.assemble('launcher', 0xe000, shutil.which('wdc02as'),
                                     shutil.which('wdcln'), source_file=launcher)
    memory, symbols = fw.relax_branches(launcher, memory, symbols,
        lambda: fw.link.assemble('launcher', 0xe000, shutil.which('wdc02as'),
                                shutil.which('wdcln'), source_file=launcher))
    code = fw.link.dense_image(memory, 0xe000, symbols['AP_END'])
    if len(code) > 0x6e0:
        raise ValueError('Launcher overlaps map-probe capability descriptor')
    extension = bytearray(b'\xff' * 2048)
    extension[:len(code)] = code
    extension[0x6e0:0x6e8] = b'MP\x01\x08\x11\xe0\x90\x7d'
    extension[TABLE-0xe000:TABLE-0xe000+4] = b'AT\x01\x08'
    entries = json.loads(args.apps.read_text()) if args.apps else []
    if not isinstance(entries, list):
        raise ValueError('--apps must contain a JSON list')
    rows_by_name = {n: descriptor(n) for n in NAMES}
    seen = set()
    for app in entries:
        name = app['name']
        if name in seen:
            raise ValueError('Duplicate application name')
        seen.add(name)
        image_path = Path(app['image'])
        if not image_path.is_absolute():
            image_path = args.apps.resolve().parent / image_path
        image = image_path.read_bytes()
        if len(image) < 17:
            raise ValueError('App image needs a header and executable payload')
        rows_by_name[name] = descriptor(name, bank=app['bank'], start=app['start'], image=image,
            entry=int.from_bytes(image[6:8], 'little'),
            ram=(int.from_bytes(image[8:10], 'little'), int.from_bytes(image[10:12], 'little')),
            zp=tuple(image[12:14]))
    rows = list(rows_by_name.values())
    if len(rows) > 8:
        raise ValueError('At most eight named applications are supported')
    for i in range(8):
        row = rows[i] if i < len(rows) else bytes(32)
        offset = TABLE - 0xe000 + 4 + i * 32
        extension[offset:offset+32] = row
    extension = seal_extension(extension)
    e = bytearray((OUT / (fw.STEM + '-e000-efff.bin')).read_bytes())
    if e[0x800:0xf00] != prior_sr:
        raise ValueError('Legacy S/R/T changed; review compatibility')
    e[:2048] = extension
    fw.emit(fw.STEM + '-e000-efff', 0xe000, e, 0xf004)
    demo_memory, demo_symbols = fw.link.assemble('app-demo', 0x9000, shutil.which('wdc02as'),
        shutil.which('wdcln'), source_file=SOURCE / 'demo.asm')
    demo = bytearray(fw.link.dense_image(demo_memory, 0x9000, demo_symbols['APP_END']))
    demo[4:6] = len(demo).to_bytes(2, 'little')
    demo[14:16] = fw.crc(demo[:14]).to_bytes(2, 'little')
    fw.emit('app-demo-9000', 0x9000, demo, 0x9010)
    demo_sector = demo + b'\xff' * (4096 - len(demo))
    fw.emit('app-demo-9000-sector', 0x9000, demo_sector, 0x9010)
    vectors = bytearray(b'\xff' * 4096)
    vectors[-32:] = prior_f[-32:]
    vectors[-4:-2] = (0x7e67).to_bytes(2, 'little')  # no J/reset startup contract
    fw.emit('app-demo-vectors-f000', 0xf000, vectors, 0x9010)
    report.update(launcher=symbols, launcher_bytes=len(code), app_table=TABLE,
        map_probe_entry=0xe011,map_probe_capability=0xe6e0,map_probe_descriptor=0x7d90,
        descriptor_bytes=32, descriptor_slots=8, fixed_f_unchanged=True,
        legacy_sr_unchanged=True, extension_allocation='B3:E000-E7FF',
        demo_bytes=len(demo), demo_bank=1, demo_start=0x9000, demo_entry=0x9010,
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.bin')},
        named_app_sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in SOURCE.iterdir() if p.is_file()})
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Named apps: launcher {len(code)} bytes; descriptors 8 x 32; demo {len(demo)} bytes.')
    print('Fixed F and legacy S/R/T unchanged. Candidate only; no board writes.')


if __name__ == '__main__':
    main()
