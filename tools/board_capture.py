"""Receive-only serial capture with automatic USB reconnect and append-only logs.

No serial bytes are transmitted. DTR and RTS remain deasserted. Intended for
operator-controlled power-cycle tests, not for firmware transfers.
"""
import argparse
import json
from pathlib import Path
import time

import serial


def capture(port, log, duration):
    deadline = time.monotonic() + duration
    link = None
    waiting = False
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as evidence:
        def record(direction, data):
            evidence.write(json.dumps(dict(time=time.time(), direction=direction,
                                           hex=data.hex(), text=data.decode('ascii', 'backslashreplace'))) + '\n')
            evidence.flush()
            print(data.decode('ascii', 'backslashreplace'), end='', flush=True)

        def event(message):
            record('EVENT', ('\n[CAPTURE ' + message + ']\n').encode('ascii', 'backslashreplace'))

        event('START receive-only ' + port)
        try:
            while time.monotonic() < deadline:
                try:
                    if link is None:
                        link = serial.Serial(port=None, baudrate=115200, timeout=0.05)
                        link.dtr = False
                        link.rts = False
                        link.port = port
                        link.open()
                        event('CONNECTED ' + port)
                        waiting = False
                    data = link.read(max(1, link.in_waiting))
                    if data:
                        record('RX', data)
                except (serial.SerialException, OSError) as error:
                    if link is not None:
                        try:
                            link.close()
                        except (serial.SerialException, OSError):
                            pass
                        link = None
                    if not waiting:
                        event('WAITING FOR RECONNECT ' + str(error))
                        waiting = True
                    time.sleep(0.1)
        finally:
            if link is not None:
                try:
                    link.close()
                except (serial.SerialException, OSError):
                    pass
            event('STOP')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM4')
    parser.add_argument('--log', required=True, type=Path)
    parser.add_argument('--wait', type=float, default=55)
    args = parser.parse_args()
    if not 0 < args.wait <= 300:
        parser.error('--wait must be greater than zero and at most 300 seconds')
    capture(args.port, args.log, args.wait)


if __name__ == '__main__':
    main()
