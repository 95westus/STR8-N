"""Fetch the pinned test-only 816 model once; debugger tests themselves are offline."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
COMMIT='530658b4fd848c69bfb2065f8e9bb5e70ef5d2a9'
SOURCE=f'https://raw.githubusercontent.com/tmr4/py65816/{COMMIT}'
MODEL_SHA256='a94fc4c40f3a252b0c5197252ce0ea35310b6f5ada986c40eae16c649d5bfc02'
FILES={
    'py65816/devices/mpu65c816.py':MODEL_SHA256,
    'LICENSE':'1850574260790ab6dba09b5828dd92f2380a7072103f6c9806384153eabf414c',
}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'BUILD/test-deps-816')
    args=ap.parse_args()
    for name,wanted in FILES.items():
        path=args.out/name
        if path.exists():
            data=path.read_bytes()
        else:
            with urlopen(f'{SOURCE}/{name}',timeout=30) as response:
                data=response.read()
        actual=hashlib.sha256(data).hexdigest()
        if actual!=wanted:raise RuntimeError(f'{name}: expected {wanted}, got {actual}')
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
        print(f'PASS {name}: {actual}')
    (args.out/'COMMIT').write_text(COMMIT+'\n')


if __name__=='__main__':main()
