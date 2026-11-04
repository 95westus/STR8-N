"""Compatibility CLI: build only BASE1 opaque; frozen F is reused."""
import argparse
from pathlib import Path
from build_base1 import build


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    build(args.out,only=['opaque'])
