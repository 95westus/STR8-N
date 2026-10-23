"""Required FT245/WDC RAM transport and serialization helpers; no vendor images."""
import binascii,json,re,time
from pathlib import Path

def crc(data):
    return binascii.crc_hqx(data, 65535)

def fnv(data):
    value = 2166136261
    for byte in data:
        value = (value ^ byte) * 16777619 & 4294967295
    return value

def config_sum(config):
    a = b = 0
    for v in config[:14]:
        a = a + v & 255
        b = b + a & 255
    return bytes((a, b))

def slot_valid(data, page):
    return len(data) == 4096 and data[:4] == b'MI\x01' + bytes((page,)) and (data[31] == 0) and (crc(data[:18] + data[32:]) == int.from_bytes(data[18:20], 'little'))

def read_s19(path, max_end=16384):
    cells = {}
    entry = None
    for line in Path(path).read_text(encoding='ascii').splitlines():
        if not re.fullmatch('S[019][0-9A-Fa-f]+', line):
            raise ValueError('Unsupported S-record')
        raw = bytes.fromhex(line[2:])
        address = int.from_bytes(raw[1:3], 'big')
        if len(raw) != raw[0] + 1 or sum(raw) & 255 != 255:
            raise ValueError('S-record checksum/count mismatch')
        if line[1] == '1':
            for offset, value in enumerate(raw[3:-1], address):
                if offset in cells:
                    raise ValueError('S-record overlap')
                cells[offset] = value
        elif line[1] == '9':
            if entry is not None or len(raw) != 4:
                raise ValueError('Invalid S9 entry')
            entry = address
    if not cells or entry is None or set(cells) != set(range(min(cells), max(cells) + 1)):
        raise ValueError('Incomplete/sparse RAM image')
    if not 8192 <= min(cells) <= entry <= max(cells) < max_end:
        raise ValueError('RAM image outside approved range')
    return (cells, entry)

def s_record(kind, address, data=b''):
    raw = bytes((len(data) + 3,)) + address.to_bytes(2, 'big') + data
    return 'S' + kind + (raw + bytes((255 - (sum(raw) & 255),))).hex().upper()

def s19(cells, entry):
    first, last = (min(cells), max(cells))
    lines = [s_record('0', 0, b'STR8-N 2.0b4 exact source migration')]
    lines += [s_record('1', a, bytes((cells[i] for i in range(a, min(a + 32, last + 1))))) for a in range(first, last + 1, 32)]
    return ('\n'.join(lines + [s_record('9', entry)]) + '\n').encode('ascii')

class Link:

    def __init__(self, port, log, *, stock=False):
        import serial
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=0.05, write_timeout=5)
        self.serial.dtr = False
        # FT245/USB boards may leave CTS inactive. RTS is the board handshake;
        # enabling host CTS gating prevented the historical debugger probe.
        self.serial.rtscts = False
        self.serial.rts = stock
        self.serial.port = port
        self.serial.open()
        self.log = log
        self.pending = bytearray()

    def record(self, direction, data):
        self.log.write(json.dumps(dict(time=time.time(), direction=direction, hex=data.hex())) + '\n')
        self.log.flush()

    def send(self, data):
        self.record('TX', data)
        if self.serial.write(data) != len(data):
            raise IOError('Short serial write')
        self.serial.flush()

    def read(self, count):
        data = self.serial.read(count)
        if data:
            self.record('RX', data)
        return data

    def exact(self, count):
        out = bytearray()
        deadline = time.monotonic() + 20
        while len(out) < count:
            data = self.read(count - len(out))
            out.extend(data)
            if time.monotonic() > deadline:
                raise TimeoutError('Serial reply incomplete')
        return bytes(out)

    def until(self, token, seconds=45):
        deadline = time.monotonic() + seconds
        while True:
            end = self.pending.find(token)
            if end >= 0:
                end += len(token)
                result = bytes(self.pending[:end])
                del self.pending[:end]
                return result
            if time.monotonic() > deadline:
                raise TimeoutError('Waiting for ' + repr(token) + ': ' + repr(bytes(self.pending[-160:])))
            data = self.read(max(1, self.serial.in_waiting))
            self.pending.extend(data)
            if b'MIGRATION REFUSED/FAILED' in self.pending:
                raise IOError('RAM migrator refused/failed; keep power on and inspect the log')

    def command(self, text, prompt=b'\r\nB3> '):
        self.send(text.encode('ascii') + b'\r')
        return self.until(prompt)

    def write_ram(self, address, data, prompt=b'\r\nB3> '):
        """Stage RAM in short monitor commands; refuse errors and verify bytes."""
        data = bytes(data)
        if not 0 <= address < 32768 or address + len(data) > 32768:
            raise ValueError('RAM staging must stay below 8000')
        for offset in range(0, len(data), 8):
            line = f'M {address + offset:04X} ' + ' '.join((f'{v:02X}' for v in data[offset:offset + 8]))
            reply = self.command(line, prompt)
            if any((error in reply for error in (b'Long line', b'Bad', b'Protected', b'Wrap'))):
                raise IOError('Monitor rejected RAM staging at ' + f'{address + offset:04X}' + ': ' + repr(reply))
        if data and self.dump(address, address + len(data) - 1, prompt) != data:
            raise IOError('RAM staging readback mismatch at ' + f'{address:04X}')

    def dump(self, first, last, prompt=b'\r\nB3> '):
        result = self.command(f'D {first:04X} {last:04X}', prompt)
        cells = {}
        for line in result.decode('ascii').splitlines():
            m = re.fullmatch('([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})', line.strip())
            if m:
                cells.update(((int(m[1], 16) + i, v) for i, v in enumerate(bytes.fromhex(m[2]))))
        if set(cells) != set(range(first, last + 1)):
            raise IOError('Incomplete memory readback')
        return bytes((cells[a] for a in range(first, last + 1)))

    def protocol(self, command):
        self.send(b'U\xaa')
        if self.exact(1) != b'\xcc':
            raise IOError('Stock monitor sync failed; press RESET and restart')
        self.send(bytes((command,)))

    def stock_info_after_reset(self, seconds=60):
        """Read-only startup probe while the operator presses RESET.

        Some retained board images start a program unless the debugger
        connects during startup. Repeated sync/identity probes issue no
        memory writes or execution commands.
        """
        deadline = time.monotonic() + seconds
        self.serial.reset_input_buffer()
        self.pending.clear()
        while time.monotonic() < deadline:
            self.send(b'U\xaa')
            received=bytearray();end=min(deadline,time.monotonic()+2)
            while time.monotonic()<end:
                received.extend(self.read(max(1,self.serial.in_waiting)))
                if b'\xcc' in received:break
            if b'\xcc' not in received:
                continue
            time.sleep(0.1)
            self.serial.reset_input_buffer()
            self.send(b'\x0c')
            reply = bytearray()
            end = min(deadline, time.monotonic() + 1)
            while len(reply) < 12 and time.monotonic() < end:
                reply.extend(self.read(12 - len(reply)))
            if len(reply) != 12:
                continue
            if reply[:3] != b'SXB' or not 33 <= reply[3] <= 126:
                raise ValueError('Unsupported stock board identity: ' + bytes(reply).hex())
            return bytes(reply)
        raise TimeoutError('No stock debugger identity during RESET window; no RAM or flash writes were issued')

    def stock_read(self, address, count):
        self.protocol(3)
        self.send(address.to_bytes(3, 'little') + count.to_bytes(3, 'little'))
        return self.exact(count)

    def stock_load(self, cells, entry):
        first, last = (min(cells), max(cells))
        for a in range(first, last + 1, 256):
            data = bytes((cells[i] for i in range(a, min(a + 256, last + 1))))
            self.protocol(2)
            self.send(a.to_bytes(3, 'little') + len(data).to_bytes(3, 'little') + data)
            if self.exact(1) != b'\x00' or self.stock_read(a, len(data)) != data:
                raise IOError('Installer RAM readback mismatch; execution refused')
        self.protocol(6)
        self.send(entry.to_bytes(3, 'little'))

    def monitor_load(self, path):
        cells, entry = read_s19(path)
        self.command('L', b'S19')
        for line in Path(path).read_bytes().splitlines():
            self.send(line + b'\r\n')
            time.sleep(0.04)
        self.until(b'\r\nB3> ')
        if self.dump(min(cells), max(cells)) != bytes((cells[a] for a in range(min(cells), max(cells) + 1))):
            raise IOError('Installer RAM readback mismatch; execution refused')
        self.send(f'G {entry:04X}\r'.encode())
