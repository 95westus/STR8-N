"""Read all four flash banks twice and save an owner-local verified backup.

Only bank selection and memory display commands are sent. No RAM program,
flash write, erase, reset, or automatic confirmation is issued.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from beta4_migration import Link


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--board', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    info = dict(board=args.board, port=args.port, bytes_per_bank=32768,
                flash_bytes=131072, repeat_verified=False, banks=[])
    manifest = args.out / 'manifest.json'
    with (args.out / 'capture.jsonl').open('x', encoding='utf-8') as log:
        link = Link(args.port, log)
        try:
            # Drain prior console output without changing control-line state.
            stop = time.monotonic() + .3
            while time.monotonic() < stop:
                link.read(max(1, link.serial.in_waiting))
            initial=link.command('', b'> ')
            if b'CLOCK>' in initial or b'BM>' in initial:
                link.command('Q')
            link.command('B3')
            (args.out / 'help.txt').write_bytes(link.command('?'))
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a + 4095, prompt)
                                for a in range(0x8000, 0x10000, 4096))
                (args.out / f'b{bank}.bin').write_bytes(data)
                info['banks'].append(dict(bank=bank, sha256=sha(data),
                                          bytes=len(data), repeat_verified=False))
                manifest.write_text(json.dumps(info, indent=2) + '\n')
                print(f'{args.board} captured B{bank}: {sha(data)}', flush=True)
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                again = b''.join(link.dump(a, a + 4095, prompt)
                                 for a in range(0x8000, 0x10000, 4096))
                original = (args.out / f'b{bank}.bin').read_bytes()
                if original != again:
                    raise IOError(f'Independent read mismatch in B{bank}')
                (args.out / f'b{bank}-repeat.bin').write_bytes(again)
                info['banks'][bank]['repeat_verified'] = True
                manifest.write_text(json.dumps(info, indent=2) + '\n')
                print(f'PASS {args.board} B{bank} independent exact comparison', flush=True)
            combined = b''.join((args.out / f'b{b}.bin').read_bytes() for b in range(4))
            (args.out / 'all-banks.bin').write_bytes(combined)
            info.update(repeat_verified=True, combined_sha256=sha(combined),
                        bank_order=[0, 1, 2, 3], address_range='8000-FFFF')
            manifest.write_text(json.dumps(info, indent=2) + '\n')
            print(f'PASS full {len(combined)}-byte flash backup: {args.out}', flush=True)
        finally:
            try:
                link.command('B3')
            finally:
                link.serial.close()


if __name__ == '__main__':
    main()
