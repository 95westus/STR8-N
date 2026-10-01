"""Load and execute one board-2609 alpha25 guarded E or F RAM updater."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import serial
from serial.tools import list_ports

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('e', 'f'), required=True)
    parser.add_argument('--port', default='COM8')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--e-install-log', type=Path,
                        help='Required for F: successful exact E-install transcript')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    key = args.phase + '_updater'
    path = Path(manifest[key])
    payload = path.read_bytes()
    if sha(payload) != manifest[key + '_sha256']:
        raise ValueError('Updater artifact hash mismatch')
    if args.phase == 'f':
        if args.e_install_log is None:
            raise ValueError('Exact successful E-install transcript required for F phase')
        rows = [json.loads(line) for line in args.e_install_log.read_text().splitlines()]
        sent = b''.join(bytes.fromhex(row['hex']) for row in rows
                        if row['direction'] == 'TX' and row['text'].startswith(('S0', 'S1', 'S9')))
        received = b''.join(bytes.fromhex(row['hex']) for row in rows
                            if row['direction'] == 'RX')
        if sha(sent) != manifest['e_updater_sha256'] or (
                b'B3:E exact; TYPE Y to repair>' not in received or
                b'B3:E VERIFIED; RESET' not in received or
                not any(row['direction'] == 'TX' and row['hex'] == '59' for row in rows)):
            raise ValueError('E-install transcript lacks exact updater and board verification')
    matches = [port for port in list_ports.comports() if port.device.upper() == args.port.upper()]
    if len(matches) != 1 or matches[0].serial_number != 'A10MPQXCA':
        raise ValueError('Expected board-2609 FT245 identity A10MPQXCA on selected port')
    lines = payload.splitlines(keepends=True)
    if not lines or not lines[-1].startswith(b'S9'):
        raise ValueError('Updater S19 has no entry record')
    # Builder already parsed every record; recheck transport identity here.
    from build_v2_a24 import read_s19
    image, entry = read_s19(path)
    if entry != 0x2000 or min(image) != 0x2000 or max(image) >= 0x6900:
        raise ValueError('RAM updater address range changed')
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open('w', encoding='utf8') as log:
        def record(direction, data):
            log.write(json.dumps({'time': time.time(), 'direction': direction,
                                  'hex': data.hex(), 'text': data.decode('latin1')}) + '\n')
            log.flush()

        with serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=5) as link:
            link.dtr = False
            link.rts = False
            link.port = args.port
            link.open()

            def send(data):
                link.write(data)
                link.flush()
                record('TX', data)

            pending = bytearray()
            def until(token, seconds):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    found = pending.find(token)
                    if found >= 0:
                        end = found + len(token)
                        matched = bytes(pending[:end])
                        del pending[:end]
                        return matched
                    data = link.read(256)
                    if data:
                        pending.extend(data)
                        record('RX', data)
                raise RuntimeError(f'Timeout waiting for {token!r}; tail={bytes(pending)[-160:]!r}')

            link.reset_input_buffer()
            send(b'\r')
            until(b'B3> ', 5)
            send(b'L\r')
            until(b'S19', 5)
            for index, line in enumerate(lines):
                send(line)
                time.sleep(.055)
                if index % 32 == 31:
                    data = link.read(link.in_waiting or 0)
                    if data:
                        pending.extend(data)
                        record('RX', data)
            result = until(b'B3> ', 12)
            if b'Entry 2000' not in result and b'entry 2000' not in result:
                raise RuntimeError(f'Loader did not report entry 2000: {result[-160:]!r}')
            send(b'G 2000\r')
            prompt = (b'B3:E exact; TYPE Y to repair> '
                      if args.phase == 'e' else b'B3:F exact; TYPE Y to update> ')
            until(prompt, 15)
            send(b'Y')
            verified = (b'B3:E VERIFIED; RESET' if args.phase == 'e'
                        else b'B3:F VERIFIED; RESET')
            until(verified, 60)
            until(b'B3> ', 20)
    print(f'{args.phase.upper()} phase verified by board; log: {args.log}')

if __name__ == '__main__':
    main()
