"""Extract the latest complete HIMON top-sector dump and verify the image.

The live directory may differ from the factory BIN; all other 4032 bytes must
match. Optional baseline evidence requires the directory to remain identical.
Outputs are owner-local evidence, not distributable factory firmware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--log', required=True, type=Path)
p.add_argument('--expected', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--baseline', type=Path)
args = p.parse_args()
text = ''.join(bytes.fromhex(r['hex']).decode('ascii', 'replace')
               for line in args.log.read_text().splitlines()
               if (r := json.loads(line)).get('direction') == 'RX')
rows = {}
for match in re.finditer(r'(?:^|[\r\n])([0-9A-F]{4}): ((?:[0-9A-F]{2} ){8})\| ((?:[0-9A-F]{2} ){8})\|', text):
    address = int(match[1], 16)
    if address == 0xF000:
        rows = {}
    rows[address] = bytes.fromhex(match[2] + match[3])
assert all(address in rows for address in range(0xF000, 0x10000, 16)), 'incomplete dump'
actual = b''.join(rows[address] for address in range(0xF000, 0x10000, 16))
expected = args.expected.read_bytes()
assert len(expected) == 4096
assert actual[:0xFB0] == expected[:0xFB0], 'resident/worker mismatch'
assert actual[0xFF0:] == expected[0xFF0:], 'config/vector mismatch'
if args.baseline:
    assert actual[0xFB0:0xFF0] == args.baseline.read_bytes()[0xFB0:0xFF0], 'live directory changed'
assert not args.out.exists(), 'evidence already exists; choose a new output'
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_bytes(actual)
print('BOARD TOP PASS: all 4032 non-directory bytes match; directory=' + actual[0xFB0:0xFF0].hex())
print('SHA256=' + hashlib.sha256(actual).hexdigest() + '; saved=' + str(args.out))
