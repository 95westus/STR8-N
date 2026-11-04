"""Paced BASE1 OPAQUE read/replace client for an already loaded PR05 RAM tool.

No RAM upload, reset, boot-setting command, implicit retry or sector erase is
issued by this host. The matching RAM tool owns erase accounting and writes.
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from oip import allowed, crc, header

PROMPT = b'OPAQUE BASE1 / PR05 I Q> '
HEADER_READY = b'SEND OIP1 HEADER\r\n'
PAYLOAD_READY = b'SEND 4096\r\n'
READ_READY = b'READ SECTOR+CRC\r\n'


class ProtocolError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def durable_file(path, data):
    """Never replace an existing owner file; verify the durable local write."""
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != data:
        raise IOError('Local backup verification failed: '+str(path))


def save_receipt(path, value):
    temporary = path.with_suffix('.pending')
    data = (json.dumps(value, indent=2)+'\n').encode()
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Wire:
    """Small buffered transport; the serial object can be supplied by tests."""
    def __init__(self, serial_port, *, timeout=20, chunk=16, pause=0.003,
                 trace=None, progress=print, sleep=time.sleep):
        if not 1 <= chunk <= 16 or not 0 <= pause <= 0.1 or timeout <= 0:
            raise ValueError('Invalid pacing/timeout')
        self.port = serial_port
        self.timeout, self.chunk, self.pause = timeout, chunk, pause
        self.trace, self.progress, self.sleep = trace, progress, sleep
        self.pending = bytearray()

    def record(self, direction, data):
        if self.trace is not None and data:
            self.trace.write(json.dumps(dict(direction=direction, hex=data.hex()))+'\n')
            self.trace.flush()

    def send(self, data):
        self.record('TX', data)
        if self.port.write(data) != len(data):
            raise ProtocolError('Short serial write; no retry was attempted')
        self.port.flush()

    def paced(self, data, label):
        for offset in range(0, len(data), self.chunk):
            part = data[offset:offset+self.chunk]
            self.send(part)
            sent = offset+len(part)
            if len(data) > 20 and (sent % 512 == 0 or sent == len(data)):
                self.progress(f'{label}: {sent}/{len(data)} bytes')
            if sent < len(data) and self.pause:
                self.sleep(self.pause)

    def _read_more(self):
        data = self.port.read(max(1, min(4098, getattr(self.port, 'in_waiting', 1))))
        self.record('RX', data)
        self.pending.extend(data)

    def exact(self, count):
        deadline = time.monotonic()+self.timeout
        while len(self.pending) < count:
            if time.monotonic() >= deadline:
                raise ProtocolError(f'Incomplete binary reply: {len(self.pending)}/{count} bytes')
            self._read_more()
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    def text_until(self, token, *, startup_cancel=False):
        deadline = time.monotonic()+self.timeout
        while True:
            end = self.pending.find(token)
            if end >= 0:
                end += len(token)
                result = bytes(self.pending[:end])
                del self.pending[:end]
                failures = result
                if startup_cancel:
                    failures = failures.replace(b'REFUSED: I or Q\r\n', b'')
                if any(word in failures for word in (b'REFUSED:', b'FAILED:', b'LOCKED:')):
                    raise ProtocolError('Device refused/failed: '+repr(result[-240:]))
                return result
            stop_words = (b'FAILED:', b'LOCKED:') if startup_cancel else (
                b'REFUSED:', b'FAILED:', b'LOCKED:')
            if any(word in self.pending for word in stop_words):
                raise ProtocolError('Device refused/failed: '+repr(bytes(self.pending[-240:])))
            if len(self.pending) > 8192:
                raise ProtocolError('Unexpected oversized text reply')
            if time.monotonic() >= deadline:
                raise ProtocolError('Waiting for '+repr(token)+'; received '+repr(bytes(self.pending[-160:])))
            self._read_more()

    def admit(self, request_prompt=False):
        if request_prompt:
            # Keep stale text in the trace, but admit only the response to this
            # operator-requested cancellation. Do not confuse a queued old
            # prompt with the new response and send I across the cancellation.
            discarded = 0
            while getattr(self.port, 'in_waiting', 0):
                self._read_more()
                discarded += len(self.pending)
                self.pending.clear()
                if discarded > 8192:
                    raise ProtocolError('Unexpected streaming output before prompt request')
            self.progress('Requesting matching BASE1 prompt with ESC+CR; no install command sent')
            self.send(b'\x1b\r')
        else:
            self.progress('Waiting for a fresh matching BASE1 / PR05 prompt')
        self.text_until(PROMPT, startup_cancel=request_prompt)
        self.progress('Matching BASE1 / PR05 prompt received')

    def begin(self, packet):
        self.send(b'I\r')
        self.text_until(HEADER_READY)
        self.paced(packet, 'Header')

    def read_sector(self, bank, sector):
        self.progress(f'Reading B{bank}:{sector >> 4:X} — 4096 bytes plus CRC')
        self.begin(header(bank, sector))
        self.text_until(READ_READY)
        raw = self.exact(4098)
        if crc(raw[:4096]) != int.from_bytes(raw[4096:], 'little'):
            raise ProtocolError('Read CRC mismatch; no further command was sent')
        tail = self.text_until(PROMPT)
        if tail != b'\r\nOK: read\r\n'+PROMPT:
            raise ProtocolError('Unexpected read completion: '+repr(tail))
        self.progress('Read CRC verified; SHA-256 '+digest(raw[:4096]))
        return raw[:4096]

    def replace_sector(self, bank, sector, before, image):
        self.begin(header(bank, sector, image, crc(before)))
        self.text_until(PAYLOAD_READY)
        self.progress('Device ready for payload; target erase requires its durable journal reservation')
        self.paced(image, 'Payload')
        reply = self.text_until(PROMPT)
        if reply not in (b'OK: verified sector\r\n'+PROMPT,
                         b'OK: identical; no erase\r\n'+PROMPT):
            raise ProtocolError('Unexpected programming completion: '+repr(reply))
        self.progress(reply[:-len(PROMPT)].decode('ascii').strip())
        return reply.startswith(b'OK: identical;')


def operate(wire, operation, bank, sector, out, *, image=None, request_prompt=False):
    """One explicit target. A failed transfer ends the run without a retry."""
    # Reject bad inputs before opening output files or sending even a prompt probe.
    if operation not in ('read', 'replace') or not allowed(bank, sector):
        raise ValueError('Protected or invalid operation/target')
    if (operation == 'replace' and (image is None or len(image) != 4096)) or (
            operation == 'read' and image is not None):
        raise ValueError('Replace requires exactly 4096 bytes; read takes no image')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    state = dict(passed=False, operation=operation, profile='BASE1', private_F_compatibility='PR05',
                 bank=bank, sector=f'{sector*256:04X}', phase='prompt-admission',
                 target_may_have_changed=False, boot_settings_changed=False,
                 RAM_restored=False, automatic_retries=0,
                 image_sha256=digest(image) if image is not None else None)
    receipt = out/'receipt.json'
    save_receipt(receipt, state)
    try:
        wire.admit(request_prompt)
        state['phase'] = 'reading-preimage'
        save_receipt(receipt, state)
        before = wire.read_sector(bank, sector)
        backup = out/'before.bin'
        durable_file(backup, before)
        state.update(phase='preimage-backed-up', before_sha256=digest(before),
                     before_crc16=f'{crc(before):04X}', backup_file=backup.name)
        save_receipt(receipt, state)
        wire.progress('Durable owner-local backup verified: '+str(backup))
        if operation == 'read':
            state.update(passed=True, phase='read-complete', target_status='unchanged')
        elif before == image:
            wire.progress('Image already identical; no replace command or erase requested')
            state.update(passed=True, phase='identical-no-write', target_status='unchanged',
                         no_op=True)
        else:
            # Persist uncertainty before a payload can reach the RAM writer.
            state.update(phase='sending-replacement', target_may_have_changed=True,
                         target_status='unverified-until-readback')
            save_receipt(receipt, state)
            identical = wire.replace_sector(bank, sector, before, image)
            state['phase'] = 'independent-readback'
            save_receipt(receipt, state)
            after = wire.read_sector(bank, sector)
            durable_file(out/'after.bin', after)
            if after != image:
                raise ProtocolError('Independent readback differs from image; target is not accepted')
            state.update(passed=True, phase='replace-verified', target_status='verified',
                         after_sha256=digest(after), after_crc16=f'{crc(after):04X}',
                         device_identical_no_erase=identical)
            wire.progress('Independent byte-for-byte readback verified; boot settings unchanged')
        save_receipt(receipt, state)
        return state
    except Exception as error:
        state.update(passed=False, failed_phase=state['phase'], phase='failed', error=str(error),
                     next_action='Stop. Keep the backup and log; inspect device state. No retry or boot was issued.')
        save_receipt(receipt, state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('read', 'replace'))
    parser.add_argument('--port', required=True)
    parser.add_argument('--bank', type=int, required=True)
    parser.add_argument('--sector', type=lambda value: int(value, 16), required=True,
                        help='Full sector address, e.g. A000')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--request-prompt', action='store_true',
                        help='Operator has loaded matching BASE1 tool; send ESC+CR to request its prompt')
    args = parser.parse_args()
    if args.sector & 255 or not allowed(args.bank, args.sector >> 8):
        parser.error('Protected/noncanonical target; B3:C/D/F are reserved')
    image = args.image.read_bytes() if args.image else None
    if args.operation == 'replace' and (image is None or len(image) != 4096):
        parser.error('replace requires --image containing exactly 4096 bytes')
    if args.operation == 'read' and image is not None:
        parser.error('read does not take --image')
    if args.out.exists():
        parser.error('Use a fresh --out directory')
    # Import only for a real CLI invocation; host tests have no serial dependency.
    import serial
    print('Use only the already loaded OPAQUE BASE1 / PR05 RAM tool. Close other users of this port.')
    print('No RAM upload, reset, automatic retry or boot-setting change will be issued.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    log = args.out.with_name(args.out.name+'-serial.jsonl')
    if log.exists():
        parser.error('Serial log already exists; choose a fresh --out name')
    serial_port = serial.Serial(port=None, baudrate=115200, timeout=0.05, write_timeout=5)
    serial_port.dtr = False
    serial_port.rts = False
    serial_port.rtscts = False
    serial_port.port = args.port
    serial_port.open()
    # The log is kept beside the fresh run directory; it never enters release assets.
    try:
        with log.open('x', encoding='utf-8', newline='\n') as trace:
            result = operate(Wire(serial_port, trace=trace), args.operation, args.bank,
                             args.sector >> 8, args.out, image=image,
                             request_prompt=args.request_prompt)
            print('PASS:', result['phase'], '— receipt:', args.out/'receipt.json')
    finally:
        serial_port.close()


if __name__ == '__main__':
    main()
