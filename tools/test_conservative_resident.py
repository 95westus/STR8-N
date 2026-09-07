"""Differential tests against the canonical 521fd0a resident (not board flash).

Requires py65==1.2.0, installed normally or in BUILD/v1.32/local/test-deps.
Executes actual linked 65C02 code. Console transport and flash hardware are
stubbed explicitly; this does not constitute board or flash-programming proof.
"""
import base64
from collections import deque
import hashlib
import json
from pathlib import Path
import random
import sys

from test_resident_reclaim import ROOT, REL, symbols

sys.path.insert(0, str(REL / 'local/test-deps'))
try:
    from py65.devices.mpu65c02 import MPU
except ImportError:
    raise SystemExit('Install the optional differential-test dependency: py65==1.2.0')

GOLDEN = json.loads((ROOT / 'tools/fixtures/resident-521fd0a.json').read_text())
OLD = base64.b64decode(GOLDEN['image'])
assert hashlib.sha256(OLD).hexdigest() == GOLDEN['sha256']
NEW = (REL / 'bin/str8n-v1.32-bank3-f000-ffff.bin').read_bytes()
MAPS = [GOLDEN['symbols'], symbols(REL / 'map/str8n-v1.32-f000.map')]


class Run:
    def __init__(self, variant, seed=0):
        self.sym = MAPS[variant]
        rng = random.Random(seed)
        self.mem = [0] * 65536
        self.mem[0xF000:] = [*([OLD, NEW][variant])]
        self.cpu = MPU(memory=self.mem)
        self.cpu.a, self.cpu.x, self.cpu.y = [rng.randrange(256) for _ in range(3)]
        self.cpu.p = rng.randrange(256) & ~self.cpu.DECIMAL
        self.input = deque()
        self.output = []
        self.calls = []
        self.hooks = {}

    def hook(self, name, action):
        self.hooks[self.sym[name]] = action

    def carry(self, value):
        self.cpu.p = (self.cpu.p & ~self.cpu.CARRY) | int(bool(value))

    def console(self, data=b''):
        self.input = deque(data)
        def read():
            self.cpu.a = self.input.popleft() if self.input else 3
            self.carry(True)
        def write():
            self.output.append(self.cpu.a)
            self.carry(True)
        self.hook('STR8_CON_READ_BYTE_BLOCK', read)
        self.hook('STR8_CON_WRITE_BYTE_BLOCK', write)

    def run(self, name, limit=2_000_000, stop_extra=()):
        self.cpu.sp = 0xFF
        self.cpu.stPushWord(0x1EFF)  # outer RTS stops below the legal L window
        self.cpu.pc = self.sym[name]
        for _ in range(limit):
            if self.cpu.pc == 0x1F00 or self.cpu.pc in stop_extra:
                self.exit_address = self.cpu.pc
                return
            action = self.hooks.get(self.cpu.pc)
            if action:
                action()
                self.cpu.pc = (self.cpu.stPopWord() + 1) & 0xFFFF
            else:
                op = self.mem[self.cpu.pc]
                assert self.cpu.disassemble[op][0] != '???', (hex(self.cpu.pc), hex(op))
                self.cpu.step()
        raise AssertionError(('instruction limit', name, hex(self.cpu.pc)))

    def result(self):
        return self.cpu.a, self.cpu.p & (self.cpu.CARRY | self.cpu.DECIMAL)


def srec(kind, address, data=b''):
    raw = bytes([len(data) + 3, address >> 8, address & 255]) + data
    return b'S' + str(kind).encode() + (raw + bytes([~sum(raw) & 255])).hex().upper().encode()


def parse(variant, text, source, seed=0, pointer=0x4000, length=None, op=1, fmt=1):
    r = Run(variant, seed)
    r.console(text)
    if source == 0:
        for i, byte in enumerate(text):
            r.mem[(pointer + i) & 65535] = byte
    r.mem[0x7E95:0x7E9C] = [op, fmt, source, 0xA5, pointer & 255, pointer >> 8,
                            (len(text) & 255) if length is None else length]
    r.run('STR8_RECORD_SERVICE_BODY')
    return r.result(), bytes(r.mem[0x7E95:0x7EA9]), bytes(r.mem[0x7B00:0x7BFC]), bytes(r.input), r.mem[0x7DF1]


def parser_tests():
    cases = [srec(0, 0, b'HEADER'), srec(1, 0x20FF, b'\x00\xff\x31'), srec(9, 0x2345),
             b'', b'S', b'S1', b'S20000', b'S9032000DC', b'S9022000DD',
             b'S1032000DBextra', b'X1032000DC', b'\x03', b'S1ZZ', srec(9, 0x2000, b'x')]
    good = srec(1, 0x7AF0, bytes(range(17)))
    for i in range(len(good)):
        cases.extend([good[:i], good[:i] + b'Z' + good[i + 1:]])
    for size in (0, 1, 16, 64, 122, 123, 252):
        cases.append(srec(1, 0xFFFF, bytes(i & 255 for i in range(size))))
    count = 0
    for source in (0, 1):
        for text in cases:
            for seed in (0, 1, 255):
                for ending in ((b'',) if source == 0 else (b'\r', b'\n', b'\r\n')):
                    payload = text + ending
                    if source == 0 and len(payload) > 255:
                        continue
                    assert parse(0, payload, source, seed) == parse(1, payload, source, seed), (source, payload)
                    count += 1
    for source in (0, 1, 2, 255):
        for op in (0, 1, 2, 255):
            for fmt in (0, 1, 255):
                assert parse(0, good, source, op=op, fmt=fmt) == parse(1, good, source, op=op, fmt=fmt)
                count += 1
    for pointer, length in ((0xFFFF, 0), (0xFFFF, 1), (0xFFFE, 3), (0x40FF, len(good))):
        assert parse(0, b'X' if pointer >= 0xFFFE else good, 0, pointer=pointer, length=length) == parse(1, b'X' if pointer >= 0xFFFE else good, 0, pointer=pointer, length=length)
        count += 1
    assert parse(1, good, 0)[0] == (0, 1)
    assert parse(1, good + b'\r', 1)[0] == (0, 1)
    print(f'PARSER DIFFERENTIAL: {count} cases PASS')


def directory(variant, address, length, fault=-1):
    r = Run(variant, address + length)
    r.mem[0x7E9E:0x7EA1] = [address & 255, address >> 8, length]
    r.mem[0x7B00:0x7C00] = [i ^ 0xA5 for i in range(256)]
    def worker():
        r.calls.append((address, length))
        if fault == -2:
            r.carry(False)
            return
        r.mem[address:address + length] = r.mem[0x7B00:0x7B00 + length]
        if 0 <= fault < length:
            r.mem[address + fault] ^= 1
        r.cpu.x, r.cpu.y = 3, 0xA7  # scratch registers are deliberately poisoned
        r.carry(True)
    r.hook('STR8_RUN_PROGRAM_RECORD_WORKER', worker)
    r.run('STR8_DIR_WRITE_BYTES')
    return r.result(), bytes(r.mem[0x7E98:0x7EA9]), r.calls


def directory_tests():
    count = 0
    for address in range(0xFFAF, 0xFFF2):
        for length in (0, 1, 2, 16, 63, 64, 65, 255):
            for fault in (-2, -1, 0, length - 1):
                a, b = directory(0, address, length, fault), directory(1, address, length, fault)
                assert a == b, (address, length, fault, a, b)
                valid = length > 0 and 0xFFB0 <= address and address + length <= 0xFFF0
                assert bool(b[2]) == valid, (address, length, 'preflight')
                if valid and fault == -1:
                    assert b[0] == (0, 1)
                count += 1
    print(f'DIRECTORY DIFFERENTIAL: {count} cases PASS (worker stubbed; checks retained)')


def loader(variant, address, length, entry, seed=0, corrupt=False):
    r = Run(variant, seed)
    data = bytes((i * 17 + 9) & 255 for i in range(length))
    record = srec(1, address, data)
    if corrupt:
        record = record[:-2] + b'00'  # checksum deliberately incorrect for these fixtures
    r.console(record + b'\r\n' + srec(9, entry) + b'\r\n')
    r.run('STR8_CMD_LOAD_RAM', stop_extra={entry} if 0x2000 <= entry < 0x7B00 else ())
    valid = not corrupt and length > 0 and 0x2000 <= address and address + length <= 0x7B00 and 0x2000 <= entry < 0x7B00
    assert r.exit_address == (entry if valid else 0x1F00)
    if valid:
        assert bytes(r.mem[address:address + length]) == data
    return r.exit_address, bytes(r.output), bytes(r.mem[0x2000:0x7B00]), bytes(r.mem[0x7E95:0x7EA9])


def loader_tests():
    count = 0
    for address, length, entry in ((0x2000, 1, 0x2000), (0x20FF, 252, 0x2100),
                                   (0x7AFF, 1, 0x7AFF), (0x7AFE, 2, 0x7AFF),
                                   (0x7AFE, 3, 0x7AFF), (0x1FFF, 2, 0x2000),
                                   (0x2000, 0, 0x2000), (0x2000, 2, 0x1FFF),
                                   (0x2000, 2, 0x7B00), (0xFFFF, 2, 0x2000)):
        for seed in (0, 1, 255):
            assert loader(0, address, length, entry, seed) == loader(1, address, length, entry, seed)
            count += 1
    assert loader(0, 0x2000, 16, 0x2000, corrupt=True) == loader(1, 0x2000, 16, 0x2000, corrupt=True)
    print(f'RAM LOADER DIFFERENTIAL: {count + 1} cases PASS')


def journal(variant, bank, pair, complete, current):
    r = Run(variant, pair)
    r.mem[0x90], r.mem[0x98] = bank, pair
    address = 0xFFB0 + 16 * bank + 12 + pair // 4
    r.mem[address] = current
    def write():
        actual = r.mem[0x7E9E] | r.mem[0x7E9F] << 8
        r.calls.append((actual, r.mem[0x7EA0], r.mem[0x7B00]))
        r.cpu.a = 0
        r.carry(True)
    r.hook('STR8_DIR_WRITE_BYTES', write)
    r.run('STR8_I_WRITE_JOURNAL_COMPLETE' if complete else 'STR8_I_WRITE_JOURNAL_START')
    expected = current & ~(1 << ((pair * 2 + complete) & 7))
    assert r.calls == [(address, 1, expected)]
    return r.result(), r.calls


def staging(variant, size, chunk, bad=False, commit=True):
    r = Run(variant, chunk)
    start = 0xC000
    payload = bytes((i * 13 + 7) & 255 for i in range(size))
    records = [srec(0, 0, b'TEST')]
    records += [srec(1, start + i, payload[i:i + chunk]) for i in range(0, size, chunk)]
    if bad:
        records[1] = srec(1, start + 1, payload[:chunk])
    records.append(srec(9, start))
    r.console(b'\r\n'.join(records) + b'\r\n')
    r.mem[0x90], r.mem[0x97] = 3, 1
    r.mem[0xA1:0xA3] = [start >> 8, (start + size) >> 8]
    def confirm():
        r.calls.append(('commit',))
        r.carry(commit)
    def worker():
        r.calls.append(('sector', r.mem[0x7DE9], bytes(r.mem[0xA00:0x1A00])))
        r.cpu.x, r.cpu.y = 3, 0x5A
        r.carry(True)
    r.hook('STR8_I_CONFIRM_COMMIT', confirm)
    r.hook('STR8_I_RUN_SECTOR_WORKER', worker)
    r.run('STR8_I_RECEIVE_DENSE')
    if not bad and commit:
        assert r.cpu.p & 1
        written = b''.join(call[2] for call in r.calls if call[0] == 'sector')
        assert written == payload
    else:
        assert not r.cpu.p & 1
    return r.cpu.p & 1, bytes(r.mem[0x90:0xA3]), bytes(r.mem[0x7E95:0x7EA9]), bytes(r.output), r.calls


def invariant_tests():
    assert NEW[0xD5C:] == OLD[0xD5C:], 'worker/directory/config/vectors changed'
    assert len(NEW) == len(OLD) == 4096
    # Resident data intentionally differs in the version digit and reset face;
    # test_resident_reclaim.py proves the exact normalized data transition.
    for name, length in [('STR8_DELAY_FIXED_A', 15), ('STR8_IVY_ENTRY_NMI', 20),
                         ('STR8_IVY_ENTRY_IRQ_MASTER', 46), ('STR8_REC_ADVANCE_APPLY_POINTERS', 13),
                         ('STR8_CON_INIT', 12), ('STR8_IN65_EDU_QUIET', 21),
                         ('STR8_CON_READ_BYTE_NONBLOCK', 31), ('STR8_CON_WRITE_BYTE_BLOCK', 37)]:
        old, new = (m[name] - 0xF000 for m in MAPS)
        assert OLD[old:old + length] == NEW[new:new + length], name
    for bank in range(4):
        for pair in range(16):
            for complete in (False, True):
                for current in (0, 0x55, 0xAA, 0xFF):
                    assert journal(0, bank, pair, complete, current) == journal(1, bank, pair, complete, current)
    for bank in range(4):
        results = []
        for variant in (0, 1):
            r = Run(variant)
            r.console()
            r.cpu.a = bank
            r.run('STR8_JUMP_BANK_PREP_A')
            # X is the relocated message low byte, not a preserved register.
            assert r.cpu.x == r.sym['MSG_CRLF'] & 255
            results.append((r.result(), r.cpu.y, bytes(r.output), bytes(r.mem[0x7DF2:0x7DF6])))
        assert results[0] == results[1]
        assert results[1][2] == f'\r\nJ B{bank}\r\n'.encode()
    print('INVARIANTS / 512 JOURNAL CASES / JUMP TEXT: PASS')


if __name__ == '__main__':
    invariant_tests()
    parser_tests()
    directory_tests()
    loader_tests()
    for size in (4096, 8192):
        for chunk in (16, 64, 128):
            for bad, commit in ((False, True), (True, True), (False, False)):
                assert staging(0, size, chunk, bad, commit) == staging(1, size, chunk, bad, commit), (size, chunk, bad, commit)
    print('STAGING DIFFERENTIAL: 18 cases PASS (flash calls recorded, never executed)')
