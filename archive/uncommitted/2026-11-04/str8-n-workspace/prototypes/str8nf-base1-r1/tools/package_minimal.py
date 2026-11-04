"""Compatibility entry point for the BASE1 package builder."""
import argparse
from pathlib import Path
from package_base1 import package

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();package(args.out)
