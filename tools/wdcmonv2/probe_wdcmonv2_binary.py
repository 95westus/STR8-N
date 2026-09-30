"""One-shot, read-only WDCMONv2 binary identity probe.

Send one $55/$AA sync pair, require $CC, then send only BOARD_INFO $0C.
This does not reset the board, read memory, or load an installer. Use it only
when the serial port is idle after the board's physical reset.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import time


SYNC = b'\x55\xaa'
READY = b'\xcc'
BOARD_INFO = b'\x0c'


def probe(port, expected='SXB?', record=None):
    events = []

    def event(direction, data):
        item = {'direction': direction, 'hex': data.hex().upper()}
        events.append(item)
        if record:
            record(item)

    event('TX', SYNC)
    port.write(SYNC)
    response = port.read(1)
    event('RX', response)
    if response != READY:
        return {'result': 'NO_WDCMON_SYNC', 'events': events}
    event('TX', BOARD_INFO)
    port.write(BOARD_INFO)
    reply = bytearray()
    while len(reply) < 12:
        chunk = port.read(12 - len(reply))
        event('RX', chunk)
        if not chunk:
            return {'result': 'INCOMPLETE_BOARD_INFO', 'received': len(reply),
                    'events': events}
        reply.extend(chunk)
    tag = bytes(reply[:4]).decode('ascii', 'replace')
    hardware, software = struct.unpack_from('<II', reply, 4)
    signature = bytes(reply[:3]) == b'SXB' and 0x21 <= reply[3] <= 0x7E
    result = 'PASS' if signature and (expected == 'SXB?' or tag == expected) else 'UNEXPECTED_BOARD_TAG'
    return {'result': result, 'tag': tag, 'hardware': hardware,
            'software': software, 'raw': bytes(reply).hex().upper(),
            'events': events}


class MockPort:
    def __init__(self, sync_response, board_reply=b''):
        self.responses = [sync_response, board_reply]
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def read(self, size):
        return self.responses.pop(0) if self.responses else b''


def self_test():
    good = MockPort(READY, b'SXB6' + struct.pack('<II', 300, 200))
    assert probe(good)['result'] == 'PASS'
    assert good.writes == [SYNC, BOARD_INFO]
    menu = MockPort(b'W')
    assert probe(menu)['result'] == 'NO_WDCMON_SYNC'
    assert menu.writes == [SYNC]
    partial = MockPort(READY, b'')
    assert probe(partial)['result'] == 'INCOMPLETE_BOARD_INFO'
    assert partial.writes == [SYNC, BOARD_INFO]
    wrong = MockPort(READY, b'SXB2' + struct.pack('<II', 123, 200))
    assert probe(wrong, expected='SXB6')['result'] == 'UNEXPECTED_BOARD_TAG'
    future = MockPort(READY, b'SXB7' + struct.pack('<II', 300, 200))
    assert probe(future)['result'] == 'PASS'
    invalid = MockPort(READY, b'BAD4' + struct.pack('<II', 300, 200))
    assert probe(invalid)['result'] == 'UNEXPECTED_BOARD_TAG'
    print('WDCMONv2 binary probe mock: PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Serial port such as COM8')
    parser.add_argument('--expected', choices=('SXB?', 'SXB2', 'SXB3', 'SXB6'), default='SXB?')
    parser.add_argument('--log', type=Path, help='Append-only JSONL wire log')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--arm-seconds', type=int, default=0,
                        help='Retry the identity handshake for this many seconds after physical RESET')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.port or not args.log:
        parser.error('--port and --log are required for a physical probe')
    if not 0 <= args.arm_seconds <= 120:
        parser.error('--arm-seconds must be in the range 0..120')
    import serial
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open('x', encoding='utf-8') as log:
        def record(item):
            log.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                  **item}) + '\n')
            log.flush()
        with serial.Serial(port=None, baudrate=115200, timeout=0.4) as link:
            link.dtr = False
            link.rts = False
            link.port = args.port
            link.open()
            link.reset_input_buffer()
            deadline = time.monotonic() + args.arm_seconds
            while True:
                result = probe(link, expected=args.expected, record=record)
                if result['result'] in ('PASS', 'UNEXPECTED_BOARD_TAG') \
                        or args.arm_seconds == 0 or time.monotonic() >= deadline:
                    break
                time.sleep(min(0.6, max(0, deadline - time.monotonic())))
        record({'direction': 'RESULT', 'result': result['result']})
    print(json.dumps({k: v for k, v in result.items() if k != 'events'}, indent=2))
    if result['result'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
