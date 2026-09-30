"""Load the exact board-2609 B3:E RAM updater and run its guarded install."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import build_v2_a24 as a24


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM8')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--log', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding='ascii'))
    if manifest['board'] != '2609 W65C816SXB':
        raise ValueError('Updater is not bound to board 2609')
    image = Path(manifest['updater_s19'])
    payload = image.read_bytes()
    if sha(payload) != manifest['updater_s19_sha256']:
        raise ValueError('Updater S19 hash differs from manifest')
    memory, entry = a24.read_s19(image)
    if entry != 0x2000 or min(memory) != 0x2000 or max(memory) >= 0x6900:
        raise ValueError('Updater RAM range or S9 entry invalid')
    if manifest['old_e_sha256'] != 'ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7':
        raise ValueError('Board 2609 old E identity differs')
    if not args.validate_only and not args.log:
        parser.error('--log is required for a physical install')
    print(f'UPDATER SHA256={sha(payload)} RANGE=$2000-${max(memory):04X} S9=$2000')
    if args.validate_only:
        return

    import serial
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open('x', encoding='utf-8') as evidence:
        def record(direction, data):
            evidence.write(json.dumps({'time': time.time(), 'direction': direction,
                                       'hex': data.hex().upper(),
                                       'text': data.decode('ascii', 'backslashreplace')}) + '\n')
            evidence.flush()

        with serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=5) as link:
            link.dtr = False
            link.rts = False
            link.port = args.port
            link.open()

            def send(data):
                record('TX', data)
                if link.write(data) != len(data):
                    raise IOError('Short serial write')
                link.flush()

            def until(token, seconds):
                deadline = time.monotonic() + seconds
                received = bytearray()
                while time.monotonic() < deadline:
                    chunk = link.read(max(1, min(link.in_waiting, 4096)))
                    if chunk:
                        record('RX', chunk)
                        received.extend(chunk)
                        if token in received:
                            return bytes(received)
                raise TimeoutError(f'Timed out waiting for {token!r}; tail={bytes(received)[-200:]!r}')

            send(b'\r')
            until(b'B3> ', 10)
            send(b'L\r')
            until(b'S19', 10)
            lines = payload.splitlines()
            for index, line in enumerate(lines):
                wire = line + b'\r\n'
                send(wire)
                time.sleep(0.06)
                available = link.in_waiting if index < len(lines) - 1 else 0
                if available:
                    chunk = link.read(available)
                    record('RX', chunk)
                    if any(error in chunk for error in (b'Long line', b'Bad S', b'Checksum', b'Protected')):
                        raise RuntimeError(f'S19 load failed at line {index+1}: {chunk[-160:]!r}')
            loaded = until(b'B3> ', 15)
            if b'2000' not in loaded or b'entry' not in loaded.lower() \
                    or any(error in loaded for error in (b'Long line', b'Bad S', b'Checksum')):
                raise RuntimeError(f'No RAM load entry confirmation: {loaded[-250:]!r}')
            print('RAM S19 LOAD = PASS; ENTRY $2000')
            send(b'G 2000\r')
            preview = until(b'TYPE Y to repair> ', 15)
            if b'B3:E exact' not in preview:
                raise RuntimeError(f'Old E preflight not confirmed: {preview[-250:]!r}')
            print('OLD B3:E EXACT = PASS; GUARDED PROMPT REACHED')
            send(b'Y')
            result = until(b'B3:E VERIFIED; RESET', 45)
            if b'B3:E OLD RESTORED' in result or b'B3:E REPAIR FAILED' in result:
                raise RuntimeError(f'Updater failed: {result[-250:]!r}')
            print('B3:E VERIFIED BY RAM UPDATER')
            until(b'B3> ', 15)
            print('B3 PROMPT RETURNED')


if __name__ == '__main__':
    main()
