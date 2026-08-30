#!/usr/bin/env python3
"""Experimental POSIX/pySerial WDCMONv2 RAM loader and terminal."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import select
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional

if os.name == "posix":
    import termios
    import tty
else:
    termios = None
    tty = None

SYNC = b"\x55\xAA"
READY = 0xCC
WRITE_MEMORY = 0x02
READ_MEMORY = 0x03
EXECUTE_MEMORY = 0x06
BOARD_INFO = 0x0C


class LoaderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationImage:
    path: Path
    first: int
    last: int
    entry: int
    data: bytes
    fnv1a: int
    sha256: str


@dataclass(frozen=True)
class BoardInfo:
    tag: str
    hardware: int
    software: int
    raw: bytes


class EventLog:
    def __init__(self, stream=None):
        self.stream = stream

    def write(self, text: str) -> None:
        if self.stream is None:
            return
        stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.stream.write(f"{stamp} {text}\n")
        self.stream.flush()


def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def u24le(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise LoaderError(f"Value does not fit a WDCMONv2 u24: {value}")
    return value.to_bytes(3, "little")


def read_migration_s19(path_value: str | Path) -> MigrationImage:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise LoaderError(f"S19 image not found: {path}")
    memory: dict[int, int] = {}
    entry: Optional[int] = None
    for line_number, raw in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if len(line) < 10 or not line.startswith("S"):
            raise LoaderError(f"Invalid S-record at line {line_number}")
        record_type = line[1]
        if record_type not in "012356789":
            raise LoaderError(f"Unsupported S-record type S{record_type} at line {line_number}")
        try:
            record = bytes.fromhex(line[2:])
        except ValueError as exc:
            raise LoaderError(f"Malformed hexadecimal S-record at line {line_number}") from exc
        if not record or record[0] != len(record) - 1:
            raise LoaderError(f"S-record count mismatch at line {line_number}")
        if sum(record) & 0xFF != 0xFF:
            raise LoaderError(f"S-record checksum mismatch at line {line_number}")
        address_bytes = 2 if record_type in "0159" else 3 if record_type in "268" else 4
        address = int.from_bytes(record[1 : 1 + address_bytes], "big")
        data = record[1 + address_bytes : -1]
        if record_type in "123":
            if record_type != "1":
                raise LoaderError(
                    f"Migration RAM images must use 16-bit S1 data records; found S{record_type} at line {line_number}"
                )
            for offset, byte in enumerate(data):
                target = address + offset
                if target in memory:
                    raise LoaderError(f"Overlapping S19 byte at ${target:04X}")
                memory[target] = byte
        elif record_type in "789":
            if record_type != "9":
                raise LoaderError(
                    f"Migration RAM images must use an S9 entry record; found S{record_type} at line {line_number}"
                )
            if data:
                raise LoaderError(f"S9 record carries unexpected data at line {line_number}")
            if entry is not None:
                raise LoaderError("S19 image contains more than one entry record")
            entry = address
    if not memory:
        raise LoaderError("S19 image contains no data")
    if entry is None:
        raise LoaderError("S19 image has no S9 entry record")
    first, last = min(memory), max(memory)
    if first < 0x2000 or last > 0x7AFF:
        raise LoaderError(f"Migration RAM image ${first:04X}-${last:04X} is outside the approved $2000-$7AFF window")
    if not first <= entry <= last:
        raise LoaderError(f"S9 entry ${entry:04X} is outside loaded bytes ${first:04X}-${last:04X}")
    if len(memory) != last - first + 1:
        raise LoaderError("Migration RAM image is sparse; a single dense range is required")
    data = bytes(memory[address] for address in range(first, last + 1))
    return MigrationImage(
        path=path,
        first=first,
        last=last,
        entry=entry,
        data=data,
        fnv1a=fnv1a32(data),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest().upper(),
    )


def read_exact(port, count: int, purpose: str) -> bytes:
    result = bytearray()
    while len(result) < count:
        chunk = port.read(count - len(result))
        if not chunk:
            raise LoaderError(f"WDCMONv2 timeout during {purpose}: received {len(result)}/{count} bytes")
        result.extend(chunk)
    return bytes(result)


def write_all(port, data: bytes) -> None:
    sent = port.write(data)
    if sent != len(data):
        raise LoaderError(f"Short serial write: sent {sent}/{len(data)} bytes")


def start_command(port, command: int) -> None:
    write_all(port, SYNC)
    ready = read_exact(port, 1, f"sync for command ${command:02X}")[0]
    if ready != READY:
        raise LoaderError(f"WDCMONv2 sync failed for command ${command:02X}: expected CC, received {ready:02X}")
    write_all(port, bytes((command,)))


def get_board_info(port) -> BoardInfo:
    start_command(port, BOARD_INFO)
    reply = read_exact(port, 12, "board-info reply")
    tag = reply[:4].decode("ascii", errors="replace")
    if tag != "SXB2":
        raise LoaderError(f"Unsupported WDCMONv2 board identity {reply.hex('-').upper()}; expected SXB2")
    hardware, software = struct.unpack_from("<II", reply, 4)
    return BoardInfo(tag, hardware, software, reply)


def write_memory(port, address: int, data: bytes) -> None:
    start_command(port, WRITE_MEMORY)
    write_all(port, u24le(address) + u24le(len(data)) + data)
    reply = read_exact(port, 1, f"write acknowledgement at ${address:04X}")[0]
    if reply:
        raise LoaderError(f"WDCMONv2 rejected RAM write at ${address:04X}: status ${reply:02X}")


def read_memory(port, address: int, count: int) -> bytes:
    start_command(port, READ_MEMORY)
    write_all(port, u24le(address) + u24le(count))
    return read_exact(port, count, f"RAM readback at ${address:04X}")


def execute_memory(port, address: int) -> None:
    start_command(port, EXECUTE_MEMORY)
    write_all(port, u24le(address))


class ProtocolMock:
    def __init__(self):
        self.receive = bytearray()
        self.sent = bytearray()
        self.commands = bytearray()
        self.memory = bytearray(65536)
        self.state = "sync0"
        self.command = 0
        self.payload = bytearray()
        self.need = 0
        self.executed_address = -1

    def write(self, data: bytes) -> int:
        for value in data:
            self._process(value)
        return len(data)

    def read(self, count: int) -> bytes:
        if not self.receive:
            return b""
        actual = min(count, len(self.receive))
        data = bytes(self.receive[:actual])
        del self.receive[:actual]
        return data

    def _process(self, value: int) -> None:
        self.sent.append(value)
        if self.state == "sync0":
            if value != 0x55:
                raise LoaderError("Mock expected sync $55")
            self.state = "sync1"
            return
        if self.state == "sync1":
            if value != 0xAA:
                raise LoaderError("Mock expected sync $AA")
            self.receive.append(READY)
            self.state = "command"
            return
        if self.state == "command":
            self.command = value
            self.commands.append(value)
            self.payload.clear()
            if value == BOARD_INFO:
                self.receive.extend(b"SXB2" + struct.pack("<II", 123, 200))
                self.state = "sync0"
            elif value in (WRITE_MEMORY, READ_MEMORY):
                self.need = 6
                self.state = "header"
            elif value == EXECUTE_MEMORY:
                self.need = 3
                self.state = "execute"
            else:
                raise LoaderError(f"Mock rejects unsupported command ${value:02X}")
            return
        self.payload.append(value)
        if self.state == "execute" and len(self.payload) == 3:
            self.executed_address = int.from_bytes(self.payload, "little")
            self.state = "sync0"
        elif self.state == "header" and len(self.payload) == 6:
            address = int.from_bytes(self.payload[:3], "little")
            length = int.from_bytes(self.payload[3:], "little")
            if address + length > len(self.memory):
                raise LoaderError("Mock memory range is invalid")
            if self.command == READ_MEMORY:
                self.receive.extend(self.memory[address : address + length])
                self.state = "sync0"
            elif length == 0:
                self.receive.append(0)
                self.state = "sync0"
            else:
                self.need = 6 + length
                self.state = "write"
        elif self.state == "write" and len(self.payload) == self.need:
            address = int.from_bytes(self.payload[:3], "little")
            length = int.from_bytes(self.payload[3:6], "little")
            self.memory[address : address + length] = self.payload[6:]
            self.receive.append(0)
            self.state = "sync0"


def self_test() -> None:
    if u24le(0x123456) != b"\x56\x34\x12":
        raise LoaderError("u24 little-endian codec self-test failed")
    if fnv1a32(b"hello") != 0x4F9F2CAB:
        raise LoaderError("FNV-1a self-test failed")
    mock = ProtocolMock()
    board = get_board_info(mock)
    if (board.tag, board.hardware, board.software) != ("SXB2", 123, 200):
        raise LoaderError("Board-info protocol self-test failed")
    fixture = b"\x11\x22\x33\x44"
    write_memory(mock, 0x2000, fixture)
    if read_memory(mock, 0x2000, len(fixture)) != fixture:
        raise LoaderError("RAM write/read protocol self-test failed")
    execute_memory(mock, 0x2345)
    expected_wire = bytes.fromhex(
        "55 AA 0C 55 AA 02 00 20 00 04 00 00 11 22 33 44 "
        "55 AA 03 00 20 00 04 00 00 55 AA 06 45 23 00"
    )
    if mock.commands != bytes((BOARD_INFO, WRITE_MEMORY, READ_MEMORY, EXECUTE_MEMORY)):
        raise LoaderError("WDCMONv2 command-order self-test failed")
    if mock.sent != expected_wire:
        raise LoaderError("WDCMONv2 wire-framing self-test failed")
    if mock.receive or mock.state != "sync0" or mock.executed_address != 0x2345:
        raise LoaderError("WDCMONv2 protocol self-test left invalid mock state")
    event_memory = io.StringIO()
    EventLog(event_memory).write("SELFTEST EVENT")
    if "SELFTEST EVENT" not in event_memory.getvalue():
        raise LoaderError("Session event-log self-test failed")
    print("PYTHON WDCMONV2 HOST BRIDGE SELF-TEST = PASS")
    print("PROTOCOL EMULATOR = PASS; $0C/$02/$03/$06 EXACT WIRE FRAMES")
    print("SESSION EVENT LOG SELF-TEST = PASS")


def require_pyserial():
    try:
        import serial
        import serial.tools.list_ports
    except ImportError as exc:
        raise LoaderError(
            "pySerial is required for board access; on Ubuntu install python3-serial or install pyserial in a virtual environment"
        ) from exc
    return serial


def list_ports() -> list[str]:
    require_pyserial()
    from serial.tools import list_ports as serial_list_ports

    return sorted(item.device for item in serial_list_ports.comports())


def open_serial(device: str, baud: int):
    serial = require_pyserial()
    port = serial.Serial()
    port.port = device
    port.baudrate = baud
    port.bytesize = serial.EIGHTBITS
    port.parity = serial.PARITY_NONE
    port.stopbits = serial.STOPBITS_ONE
    port.timeout = 1.0
    port.write_timeout = 5.0
    port.rtscts = True
    port.dtr = False
    if hasattr(port, "exclusive"):
        port.exclusive = True
    port.open()
    port.reset_input_buffer()
    port.reset_output_buffer()
    return port


def send_file(port, data: bytes) -> None:
    for offset in range(0, len(data), 64):
        write_all(port, data[offset : offset + 64])
        time.sleep(0.002)


def raw_terminal(
    port,
    transcript: Optional[BinaryIO],
    events: EventLog,
    transfer: tuple[str, bytes, str],
    transfer2: tuple[str, bytes, str],
) -> None:
    if os.name != "posix" or termios is None or tty is None:
        raise LoaderError("The experimental Python interactive terminal currently requires POSIX/Linux")
    if not sys.stdin.isatty():
        raise LoaderError("Interactive terminal input requires a real terminal")
    fd = sys.stdin.fileno()
    prior = termios.tcgetattr(fd)
    line = bytearray()
    print(
        f"TERMINAL ACTIVE; CTRL+] EXITS; CTRL+B PROBES WDCMON; "
        f"CTRL+U SENDS {transfer[0]}; CTRL+D SENDS {transfer2[0]}; ENTER SENDS CR"
    )
    events.write("TERMINAL START")
    try:
        tty.setraw(fd)
        while True:
            available = port.in_waiting
            if available:
                data = port.read(min(available, 4096))
                if data:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    if transcript is not None:
                        transcript.write(data)
                        transcript.flush()
            readable, _, _ = select.select([fd], [], [], 0.01)
            if not readable:
                continue
            value = os.read(fd, 1)
            if not value:
                continue
            byte = value[0]
            if byte == 0x1D:
                events.write("CTRL+] TERMINAL EXIT")
                break
            if byte == 0x02:
                try:
                    board = get_board_info(port)
                    events.write(
                        f"CTRL+B WDCMON PROBE PASS TAG={board.tag} HW={board.hardware / 100:.2f} WDCMON={board.software / 100:.2f}"
                    )
                    print(
                        f"\nWDCMON PROBE = {board.tag}; HW={board.hardware / 100:.2f}; WDCMON={board.software / 100:.2f}"
                    )
                except Exception as exc:  # keep the terminal available after a probe failure
                    events.write(f"CTRL+B WDCMON PROBE FAIL {exc}")
                    print(f"\nWARNING: WDCMON probe failed: {exc}")
                continue
            if byte == 0x15:
                name, data, digest = transfer
                events.write(f"CTRL+U FILE SEND NAME={name} BYTES={len(data)} SHA256={digest}")
                print(f"\nSENDING {name} ({len(data)} bytes)")
                send_file(port, data)
                print("FILE SENT")
                continue
            if byte == 0x04:
                name, data, digest = transfer2
                events.write(f"CTRL+D FILE SEND NAME={name} BYTES={len(data)} SHA256={digest}")
                print(f"\nSENDING {name} ({len(data)} bytes)")
                send_file(port, data)
                print("FILE SENT")
                continue
            if byte in (0x0A, 0x0D):
                events.write(f"TX LINE {line.decode('ascii', errors='replace')}")
                line.clear()
                byte = 0x0D
            elif byte in (0x08, 0x7F):
                if line:
                    line.pop()
            elif 0x20 <= byte <= 0x7E:
                line.append(byte)
            else:
                events.write(f"TX BYTE ${byte:02X}")
            write_all(port, bytes((byte,)))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, prior)
        events.write("TERMINAL STOP")


def run_loader(
    device: str,
    image: MigrationImage,
    transfer_path: Path,
    transfer2_path: Path,
    transcript_path: Path,
    baud: int = 115200,
    chunk_bytes: int = 256,
    force: bool = False,
) -> None:
    if not 16 <= chunk_bytes <= 4096:
        raise LoaderError("chunk size must be in the range 16..4096")
    transcript_path = transcript_path.expanduser().resolve()
    event_path = Path(str(transcript_path) + ".events.txt")
    for path in (transcript_path, event_path):
        if path.exists() and not force:
            raise LoaderError(f"Evidence file exists; use --force to replace it: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    transfer_data = transfer_path.read_bytes()
    transfer2_data = transfer2_path.read_bytes()
    transfer = (transfer_path.name, transfer_data, hashlib.sha256(transfer_data).hexdigest().upper())
    transfer2 = (transfer2_path.name, transfer2_data, hashlib.sha256(transfer2_data).hexdigest().upper())
    mode = "wb" if force else "xb"
    event_mode = "w" if force else "x"
    outcome = "INCOMPLETE"
    with event_path.open(event_mode, encoding="utf-8", newline="\n") as event_stream, transcript_path.open(mode) as transcript:
        events = EventLog(event_stream)
        events.write(f"SESSION START PORT={device} BAUD={baud} RESET=False HOST=PYTHON-EXPERIMENTAL")
        events.write(
            f"IMAGE SHA256={image.sha256} RANGE=${image.first:04X}-${image.last:04X} "
            f"BYTES={len(image.data)} ENTRY=${image.entry:04X} FNV1A={image.fnv1a:08X}"
        )
        events.write(f"TRANSFER READY NAME={transfer[0]} BYTES={len(transfer[1])} SHA256={transfer[2]}")
        events.write(f"TRANSFER2 READY NAME={transfer2[0]} BYTES={len(transfer2[1])} SHA256={transfer2[2]}")
        print(f"SESSION EVENT LOG = {event_path}")
        print(f"RAW RX TRANSCRIPT = {transcript_path}")
        port = open_serial(device, baud)
        try:
            print("PHYSICAL RESET GATE: reset the board, wait two seconds, then press ENTER here")
            input()
            discarded = port.in_waiting
            port.reset_input_buffer()
            events.write(f"PHYSICAL RESET GATE STARTUP_RX_DISCARDED={discarded}")
            print(f"PHYSICAL RESET GATE = RELEASED; STARTUP RX DISCARDED = {discarded}")
            board = get_board_info(port)
            events.write(f"BOARD TAG={board.tag} HW={board.hardware / 100:.2f} WDCMON={board.software / 100:.2f}")
            print(f"BOARD      = {board.tag}; HW={board.hardware / 100:.2f}; WDCMON={board.software / 100:.2f}")
            for offset in range(0, len(image.data), chunk_bytes):
                chunk = image.data[offset : offset + chunk_bytes]
                address = image.first + offset
                write_memory(port, address, chunk)
                readback = read_memory(port, address, len(chunk))
                if readback != chunk:
                    mismatch = next(i for i, pair in enumerate(zip(readback, chunk)) if pair[0] != pair[1])
                    raise LoaderError(
                        f"RAM readback mismatch at ${address + mismatch:04X}: "
                        f"wrote ${chunk[mismatch]:02X}, read ${readback[mismatch]:02X}"
                    )
                print(".", end="", flush=True)
            events.write("RAM READBACK BYTE-EXACT")
            print("\nRAM READBACK = BYTE-EXACT")
            print(f"EXECUTE      = ${image.entry:04X}")
            events.write(f"EXECUTE ${image.entry:04X}")
            execute_memory(port, image.entry)
            raw_terminal(port, transcript, events, transfer, transfer2)
            outcome = "TERMINAL CLOSED BY OPERATOR"
        except Exception as exc:
            events.write(f"ERROR {exc}")
            raise
        finally:
            events.write(f"SESSION END OUTCOME={outcome}")
            port.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Experimental Python WDCMONv2 RAM bridge")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--validate-image")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            self_test()
        if args.validate_image:
            image = read_migration_s19(args.validate_image)
            print(f"S19 SHA256 = {image.sha256}")
            print(f"RAM RANGE  = ${image.first:04X}-${image.last:04X} ({len(image.data)} bytes)")
            print(f"ENTRY      = ${image.entry:04X}")
            print(f"RAM FNV1A  = {image.fnv1a:08X}")
            print("MIGRATION S19 = VALID")
        if args.list_ports:
            for device in list_ports():
                print(device)
        if not (args.self_test or args.validate_image or args.list_ports):
            parser.error("choose --self-test, --validate-image, or --list-ports")
        return 0
    except (LoaderError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
