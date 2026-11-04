"""STR8-N Terminal — launch a named component kit; no connection on startup."""
import argparse
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--kit', type=Path, default=root/'BUILD/str8n-copyright-r2')
args, rest = parser.parse_known_args()
entry = args.kit.resolve()/'str8n-terminal.py'
if not entry.is_file():
    raise SystemExit('Build the named kit first or pass --kit PATH')
sys.argv = [str(entry)]+rest
runpy.run_path(str(entry), run_name='__main__')
