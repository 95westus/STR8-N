"""Extract a complete D start end readback from board_serial.py JSONL evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('start', type=lambda s: int(s, 16))
    parser.add_argument('end', type=lambda s: int(s, 16))
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    if not 0x2000 <= args.start <= args.end <= 0xFFFF:
        parser.error('range must lie in RAM or flash')
    transcript = b''.join(bytes.fromhex(json.loads(line)['hex'])
                          for line in args.log.read_text().splitlines()
                          if json.loads(line).get('direction') == 'RX').decode('ascii')
    cells = bytearray(args.end - args.start + 1)
    seen = bytearray(len(cells))
    rows = 0
    for line in transcript.splitlines():
        match = re.fullmatch(r'([0-9A-Fa-f]{4}):((?: [0-9A-Fa-f]{2}){1,16})', line.strip())
        if not match:
            continue
        address = int(match[1], 16)
        values = bytes.fromhex(match[2])
        if not args.start <= address <= args.end:
            continue
        if address + len(values) - 1 > args.end:
            raise SystemExit(f'Row exceeds requested range at ${address:04X}')
        for offset, value in enumerate(values):
            index = address + offset - args.start
            if seen[index] and cells[index] != value:
                raise SystemExit(f'Conflicting readback byte at ${address+offset:04X}')
            seen[index] = 1
            cells[index] = value
        rows += 1
    if not all(seen):
        first = seen.index(0)
        raise SystemExit(f'Incomplete readback; first missing ${args.start+first:04X}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(cells)
    print(f'{rows} rows, {len(cells)} bytes, SHA256={hashlib.sha256(cells).hexdigest()}')


if __name__ == '__main__':
    main()
