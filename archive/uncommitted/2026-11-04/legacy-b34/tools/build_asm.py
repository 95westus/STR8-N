"""Build the ROM-resident ASM application. No serial access or board writes."""
from pathlib import Path
import hashlib
import json
import shutil

import build_v2_recovery as fw
from build_bank_maint_v2 import long_branches

ROOT = fw.ROOT
SOURCE = ROOT / 'src/asm'
OUT = ROOT / 'BUILD/asm'
VERSION = '0.5'
ADDRESS = 0x9000
MODES = ('imp', 'acc', 'imm', 'zpg', 'zpx', 'zpy', 'abs', 'abx', 'aby',
         'inx', 'iny', 'zpi', 'ind', 'iax', 'rel', 'zpr')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'asm').mkdir(exist_ok=True)
    (OUT / 'build.json').unlink(missing_ok=True)
    (OUT / 'test-results.json').unlink(missing_ok=True)
    rows = json.loads((SOURCE / 'opcodes.json').read_text())
    assert len(rows) == 212 and len({r['opcode'] for r in rows}) == 212
    table = bytearray()
    for row in rows:
        table += row['name'].encode().ljust(4, b'\0')
        table += bytes((MODES.index(row['mode']), row['opcode']))
    text = (SOURCE / 'asm.asm').read_text()
    for name in ('shell.inc', 'editor.inc', 'core.inc', 'expression.inc'):
        text = text.replace('INCLUDE "' + name + '"', (SOURCE / name).read_text())
    text = text.replace('INCLUDE "opcodes.inc"', ''.join(
        ' DB ' + ','.join(f'${v:02X}' for v in table[i:i+12]) + '\n'
        for i in range(0, len(table), 12)))
    generated = OUT / 'asm-generated.asm'
    generated.write_text(long_branches(text), encoding='ascii')
    fw.link.OUT = OUT
    fw.link.SOURCE = ROOT / 'src/v2-config'
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise SystemExit('WDC02AS and WDCLN must be on PATH')
    def assemble():
        return fw.link.assemble('asm-app', ADDRESS, assembler, linker,
                               source_file=generated, include_dirs=(SOURCE,))
    memory, symbols = assemble()
    memory, symbols = fw.relax_branches(generated, memory, symbols, assemble)
    image = bytearray(fw.link.dense_image(memory, ADDRESS, symbols['APP_END']))
    if not 0x8000 <= ADDRESS < symbols['APP_END'] <= 0xffe0:
        raise ValueError('ASM overlaps the application-bank hardware vectors')
    image[4:6] = len(image).to_bytes(2, 'little')
    image[14:16] = fw.crc(image[:14]).to_bytes(2, 'little')
    stem = f'asm-{ADDRESS:04x}'
    (OUT / (stem+'.bin')).write_bytes(image)
    lines = [fw.link.record('0', 0, f'STR8-N ASM {VERSION} ROM application'.encode('ascii'))]
    lines += [fw.link.record('1', ADDRESS+i, image[i:i+32]) for i in range(0,len(image),32)]
    lines += [fw.link.record('9', symbols['APP_START'])]
    (OUT / (stem+'.s19')).write_text('\n'.join(lines)+'\n')
    report = dict(version=VERSION, start=ADDRESS, entry=symbols['APP_START'], bytes=len(image),
        target='W65C02', host_abi=1, encodings=len(rows),
        ram_first=symbols['OUTPUT_START'], ram_last=symbols['STATE_END']-1, zp_first=0, zp_last=0x3f,
        source_first=symbols['SOURCE_START'], source_end=symbols['SOURCE_END'],
        output_first=symbols['OUTPUT_START'], output_end=symbols['OUTPUT_END'],
        symbols=symbols, sha256=hashlib.sha256(image).hexdigest(),
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()})
    (OUT / 'build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'ASM {VERSION}: {len(image)} ROM bytes, {len(rows)} W65C02 encodings; no board writes.')


if __name__ == '__main__':
    main()
