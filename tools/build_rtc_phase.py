"""Build the qualified temporary RTC phase routine from repository source; offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from str8build.assemble import Assembly
from rtc_phase_contract import DEFAULT_BUILD, ROOT, verify_image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_BUILD,
                        help='fresh output directory (existing directories are refused)')
    parser.add_argument('--assembler', default='wdc02as')
    parser.add_argument('--linker', default='wdcln')
    args = parser.parse_args(argv)
    assembler, linker = shutil.which(args.assembler), shutil.which(args.linker)
    if not assembler or not linker:
        parser.error('WDC02AS and WDCLN must be installed or supplied explicitly')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = out / 's/core'
    stage.mkdir(parents=True)
    source = ROOT / 'src/rtc-phase/phase.asm'
    shutil.copyfile(source, stage / 'phase.asm')
    assembly = object.__new__(Assembly)
    assembly.out, assembly.assembler, assembly.linker = out, assembler, linker
    assembly.symbols, assembly.compiled = {}, []
    image, symbols = assembly.link('core', 'phase', 0x2000, 'SERVICE_END')
    verify_image(image, symbols)
    (out / 'phase.bin').write_bytes(image)
    (out / 'symbols.json').write_text(json.dumps(symbols, indent=2) + '\n', encoding='utf-8')
    manifest = dict(image_sha256=hashlib.sha256(image).hexdigest(),
                    source='src/rtc-phase/phase.asm',
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    bytes=len(image), model_proof_required=True)
    (out / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Built', len(image), manifest['image_sha256'])
    print('Run tools/test_rtc_phase.py --build', out, 'before using the host tool.')


if __name__ == '__main__':
    main()
