#!/usr/bin/env python3
"""Linux a24c1 stock-board launcher and WDCMON USB terminal."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import select
import struct
import sys
import time

ROOT = Path(__file__).resolve().parent
COLORS = {'cyan': 36, 'yellow': 33, 'green': 32, 'red': 31}


def show(text, color='cyan', end='\n'):
    if sys.stdout.isatty():
        text = f'\033[{COLORS[color]}m{text}\033[0m'
    print(text, end=end, flush=True)


def prompt(text):
    show(text, 'yellow', end='')
    return input()


def resolve(name, repository):
    for path in (ROOT / name, ROOT / repository):
        if path.is_file():
            return path
    raise ValueError(f'Missing {name}; extract the complete kit or build repository files.')


def read_s19(path):
    memory = {}
    entry = None
    for number, line in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if entry is not None or not re.fullmatch(r'S[019][0-9A-Fa-f]+', line):
            raise ValueError(f'{path.name}:{number}: expected S0/S1/S9 records with S9 last')
        raw = bytes.fromhex(line[2:])
        if len(raw) < 4 or raw[0] != len(raw) - 1 or sum(raw) & 255 != 255:
            raise ValueError(f'{path.name}:{number}: invalid count or checksum')
        address = int.from_bytes(raw[1:3], 'big')
        if line[1] == '1':
            data = raw[3:-1]
            if not data or address + len(data) > 65536:
                raise ValueError('Empty or wrapping S1 record')
            for offset, byte in enumerate(data, address):
                if offset in memory:
                    raise ValueError('Overlapping S1 records')
                memory[offset] = byte
        elif line[1] == '9':
            if len(raw) != 4:
                raise ValueError('S9 entry record must not contain data')
            entry = address
    if not memory or entry is None:
        raise ValueError('S19 requires data and an S9 entry')
    first, last = min(memory), max(memory)
    if first < 0x2000 or last > 0x7AFF or not first <= entry <= last:
        raise ValueError('S19 outside 2000-7AFF RAM window or invalid entry')
    if len(memory) != last - first + 1:
        raise ValueError('S19 must be dense')
    return first, entry, bytes(memory[a] for a in range(first, last + 1))


def send(link, data):
    if link.write(data) != len(data):
        raise IOError('Short serial write')


def read_exact(link, count):
    result = bytearray()
    while len(result) < count:
        part = link.read(count - len(result))
        if not part:
            raise IOError(f'WDCMON timeout: received {len(result)}/{count} bytes')
        result.extend(part)
    return bytes(result)


def command(link, code):
    send(link, b'\x55\xaa')
    ready = read_exact(link, 1)
    if ready != b'\xcc':
        raise IOError(f'WDCMON sync expected CC, received {ready.hex().upper()}')
    send(link, bytes([code]))


def u24(value):
    return value.to_bytes(3, 'little')


def board_info(link):
    command(link, 0x0C)
    reply = read_exact(link, 12)
    if reply[:3] != b'SXB' or not 0x21 <= reply[3] <= 0x7E:
        raise ValueError(f'Unsupported board identity: {reply.hex()}')
    hw, version = struct.unpack('<II', reply[4:])
    return reply[:4].decode('ascii'), hw / 100, version / 100


def load_ram(link, first, entry, image):
    for offset in range(0, len(image), 256):
        data = image[offset:offset + 256]
        address = first + offset
        command(link, 0x02)
        send(link, u24(address) + u24(len(data)) + data)
        if read_exact(link, 1) != b'\0':
            raise IOError(f'WDCMON rejected RAM write at {address:04X}')
        command(link, 0x03)
        send(link, u24(address) + u24(len(data)))
        if read_exact(link, len(data)) != data:
            raise IOError(f'RAM readback mismatch at {address:04X}; execution refused')
        show('.', end='')
    show('\nRAM READBACK = BYTE-EXACT', 'green')
    show(f'EXECUTE = ${entry:04X}')
    command(link, 0x06)
    send(link, u24(entry))


def board_color(text):
    if re.search(r'FAIL|REFUSE|CANCEL|HALTED|INVALID|ERROR', text):
        return 'red'
    if re.search(r'NO RESET|NO RECOVERY|ERASING|PROGRAMMING|TYPE|CHOOSE|PRESS|SEND|>', text):
        return 'yellow'
    if re.search(r'VERIFIED|COMPLETE|SUCCESS|==', text):
        return 'green'
    return 'cyan'


def terminal(link, core, maint, installed=False):
    # POSIX modules are imported here so offline validation also works on Windows.
    import termios
    import tty
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    pending = ''
    received = time.monotonic()
    transfer1 = maint if installed else core
    show(f'TERMINAL ACTIVE; Ctrl+] exits; Ctrl+U sends {transfer1.name}; '
         f'Ctrl+D sends {maint.name}; Enter sends CR', 'yellow')
    try:
        tty.setraw(fd)
        link.timeout = 0.05
        while True:
            if link.in_waiting:
                data = link.read(min(link.in_waiting, 4096))
                received = time.monotonic()
                for char in data.decode('latin-1'):
                    pending += char
                    if char in '\n>':
                        show(pending, board_color(pending), end='')
                        pending = ''
            if pending and time.monotonic() - received >= 0.1:
                show(pending, board_color(pending), end='')
                pending = ''
            if select.select([fd], [], [], 0.01)[0]:
                key = os.read(fd, 1)
                if not key or key == b'\x1d':
                    break
                if key in (b'\x15', b'\x04'):
                    path = transfer1 if key == b'\x15' else maint
                    data = path.read_bytes()
                    show(f'\r\nSENDING {path.name} ({len(data)} bytes)\r', 'yellow')
                    for offset in range(0, len(data), 64):
                        send(link, data[offset:offset + 64])
                        time.sleep(0.002)
                    show('FILE SENT\r', 'green')
                else:
                    send(link, b'\r' if key in (b'\n', b'\r') else key)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        if pending:
            show(pending, board_color(pending), end='')
        show('')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Linux device, e.g. /dev/ttyUSB0')
    parser.add_argument('--validate-only', action='store_true', help='File checks, no serial access')
    parser.add_argument('--terminal-only', action='store_true', help='Connect to installed STR8-N without reset/load')
    args = parser.parse_args()
    installer = resolve('str8n-v2-a24c1-wdcmonv2-install-2000.s19',
                        'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-wdcmonv2-install-2000.s19')
    core = resolve('str8n-v2-a24c1-f000-ffff.bin',
                   'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-f000-ffff.bin')
    maint = resolve('str8n-bank-maint-2000.s19', 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19')
    first, entry, image = read_s19(installer)
    read_s19(maint)
    if core.stat().st_size != 4096:
        raise ValueError('Core BIN must be exactly 4096 bytes')
    show(f'S19 SHA256 = {hashlib.sha256(installer.read_bytes()).hexdigest().upper()}')
    show(f'RAM RANGE = ${first:04X}-${first + len(image) - 1:04X}; ENTRY = ${entry:04X}')
    if args.validate_only:
        show('A24C1 LINUX FILE CHECK = PASS (no serial device opened)', 'green')
        return
    if sys.platform != 'linux' or not sys.stdin.isatty():
        raise ValueError('Live use requires an interactive Linux terminal')
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as error:
        raise ValueError('Install Python 3 pyserial; on Debian/Ubuntu: sudo apt install python3-serial') from error
    ports = [port.device for port in list_ports.comports()]
    show('Detected ports: ' + (', '.join(sorted(ports)) or '(none)'))
    port = args.port or prompt('Enter board device (for example /dev/ttyUSB0); Q to quit: ').strip()
    if port.upper() == 'Q':
        return
    if not port.startswith('/dev/') or not Path(port).exists():
        raise ValueError('Enter an existing Linux serial device under /dev/')
    show('Close other terminals using this device.', 'yellow')
    # Set modem-control state before opening; physical RESET is the only reset gate.
    with serial.Serial(port=None, baudrate=115200, timeout=1, write_timeout=5,
                       rtscts=True, exclusive=True) as link:
        link.dtr = False
        link.port = port
        link.open()
        if not args.terminal_only:
            prompt('PHYSICAL RESET GATE: press RESET, wait two seconds, then press Enter here: ')
            link.reset_input_buffer()
            tag, hw, version = board_info(link)
            show(f'BOARD = {tag}; HW={hw:.2f}; WDCMON={version:.2f}')
            model = prompt('Type W65C02SXB or W65C816SXB exactly in uppercase: ').strip()
            if model not in ('W65C02SXB', 'W65C816SXB'):
                raise ValueError('Board not confirmed; RAM installer was not loaded')
            show(f'PHYSICAL BOARD TYPE = {model}', 'green')
            load_ram(link, first, entry, image)
        terminal(link, core, maint, args.terminal_only)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        show(f'ERROR: {error}', 'red')
        if isinstance(error, PermissionError):
            show('Check serial-device permissions and membership in your distribution serial-access group.', 'yellow')
        sys.exit(1)
    except KeyboardInterrupt:
        show('\nCanceled', 'red')
        sys.exit(130)
