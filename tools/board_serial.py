"""Explicit serial exchanges with append-only evidence; never auto-confirm writes."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import serial


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM4')
    p.add_argument('--log', required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument('--hex', default='')
    g.add_argument('--s19', type=Path)
    p.add_argument('--wait', type=float, default=1.0)
    p.add_argument('--line-delay', type=float, default=0.04)
    p.add_argument('--follow-match', help='Send follow-hex once when this exact RX text appears')
    p.add_argument('--follow-hex', default='')
    args = p.parse_args()
    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as evidence:
        def record(direction, data):
            evidence.write(json.dumps(dict(time=time.time(), direction=direction,
                                           hex=data.hex(), text=data.decode('ascii', 'backslashreplace'))) + '\n')
            evidence.flush()
            if direction == 'RX':
                print(data.decode('ascii', 'backslashreplace'), end='', flush=True)

        with serial.Serial(port=None, baudrate=115200, timeout=0.05) as link:
            link.dtr = False
            link.rts = False
            link.port = args.port
            link.open()
            received = bytearray()
            followed = False
            def receive(duration):
                nonlocal followed
                deadline = time.monotonic() + duration
                while time.monotonic() < deadline:
                    data = link.read(max(1, link.in_waiting))
                    if data:
                        record('RX', data)
                        received.extend(data)
                        if args.follow_match and not followed and args.follow_match.encode('ascii') in received:
                            follow = bytes.fromhex(args.follow_hex)
                            record('TX', follow)
                            link.write(follow)
                            link.flush()
                            followed = True
            receive(0.1)
            if args.s19:
                payload = args.s19.read_bytes()
                evidence.write(json.dumps(dict(file=str(args.s19), sha256=hashlib.sha256(payload).hexdigest())) + '\n')
                lines = payload.splitlines()
                # Validate the entire transport before sending any byte.
                for line in lines:
                    if not line.startswith((b'S0', b'S1', b'S5', b'S9')):
                        raise ValueError('Unsupported S-record')
                    raw = bytes.fromhex(line[2:].decode('ascii'))
                    if len(raw) != raw[0] + 1 or sum(raw) & 255 != 255:
                        raise ValueError('Invalid S-record count/checksum')
                for line in lines:
                    data = line + b'\r\n'
                    record('TX', data)
                    link.write(data)
                    link.flush()
                    receive(args.line_delay)
            elif args.hex:
                data = bytes.fromhex(args.hex)
                record('TX', data)
                link.write(data)
                link.flush()
            receive(args.wait)


if __name__ == '__main__':
    main()
