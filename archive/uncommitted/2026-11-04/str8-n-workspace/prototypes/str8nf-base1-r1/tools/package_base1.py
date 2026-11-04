"""BASE1 packaging entry; firmware is copied without rebuilding."""
import argparse
from pathlib import Path
from package_release_candidate import package

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    package(parser.parse_args().out)
