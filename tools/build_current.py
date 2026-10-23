#!/usr/bin/env python3
"""Build src/current offline and verify its selected firmware baseline."""
import argparse
from pathlib import Path
import shutil

from str8build.build import build

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'BUILD/current')
    parser.add_argument('--assembler',default=shutil.which('wdc02as'))
    parser.add_argument('--linker',default=shutil.which('wdcln'))
    args = parser.parse_args(argv)
    assembler = shutil.which(args.assembler) if args.assembler else None
    linker = shutil.which(args.linker) if args.linker else None
    if not assembler or not linker:
        parser.error('Install WDC02AS and WDCLN separately and put them on PATH')
    out, source = args.out.resolve(), ROOT/'src/current'
    if out.exists():
        parser.error('--out must be a new directory (existing outputs are preserved)')
    if out.is_relative_to(source) or source.is_relative_to(out):
        parser.error('--out must be separate from src/current')
    if len(str(out)) > 70:
        parser.error('Use a short --out path; legacy WDC tools fail on long paths')
    build(ROOT,out,assembler,linker)


if __name__ == '__main__':
    main()
