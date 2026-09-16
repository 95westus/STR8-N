"""Execute the original and optimized workers with a modeled banked flash chip.

Runs actual linked 65C02 instructions, including the selector and flash command
sequences. The memory model supplies bank switching, delayed flash completion,
and injected failures; this is not electrical or on-board qualification.
Timeout cases shorten RAM counters after checking their production initial
values. Separate tests preserve the real counters and compare polling cycles.

Uses installed py65, STR8_TEST_DEPS/PY65_PATH, or an existing BUILD/v*/local/
test-deps directory. --baseline-only checks the harness without a candidate build.
"""

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'BUILD/v1.34'
for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS', 'PY65_PATH')
      for p in os.environ.get(key, '').split(os.pathsep) if p),
    REL / 'local/test-deps',
    *sorted((ROOT / 'BUILD').glob('v*/local/test-deps'), reverse=True),
]):
    if (directory / 'py65').is_dir():
        sys.path.insert(0, str(directory))
try:
    from py65.devices.mpu65c02 import MPU
except ImportError as error:
    raise SystemExit('py65 is required; set STR8_TEST_DEPS to its existing parent directory') from error


PCR, LED = 0x7FEC, 0x7FA0
PATTERNS = (0xCC, 0xCE, 0xEC, 0xEE)
STOP = 0x1F00
CASES = 0


def symbols(path):
    return {name: int(value, 16) for value, name in re.findall(
        r'^\s*([0-9a-fA-F]{8})\s+(\w+)\s*$', path.read_text(), re.M)}


@dataclass
class Variant:
    name: str
    image: bytes
    resident: dict
    sym: dict

    @property
    def worker(self):
        start = self.resident['STR8_WORKER_STORE'] - 0xF000
        size = self.sym['STR8W_LINKED_END'] - self.sym['START']
        return self.image[start:start + size]


class FlashMemory:
    """Minimal SST-style unlock/program/sector-erase model, not a timing model."""

    def __init__(self, worker):
        self.ram = bytearray(65536)
        self.ram[0x0200:0x0200 + len(worker)] = worker
        self.ram[PCR], self.ram[LED] = 0xFF, 0x43
        self.banks = [bytearray(b'\xff' * 0x8000) for _ in range(4)]
        self.events = []
        self.commands = []
        self.mutations = []
        self.state = [0] * 4
        self.pending = None
        self.delay_reads = 2
        self.fail_program = None
        self.fail_erase = False
        self.stuck_after_erase = None

    @property
    def bank(self):
        pattern = self.ram[PCR] & 0xEE
        assert pattern in PATTERNS, ('flash accessed during incomplete bank selection', pattern)
        return PATTERNS.index(pattern)

    def __getitem__(self, address):
        if isinstance(address, slice):
            return [self[i] for i in range(*address.indices(65536))]
        if address < 0x8000:
            return self.ram[address]
        bank = self.bank
        pending = self.pending
        if pending and pending['bank'] == bank and pending['address'] == address:
            if not pending['fail']:
                if pending['reads']:
                    pending['reads'] -= 1
                else:
                    if pending['kind'] == 'program':
                        self.banks[bank][address - 0x8000] &= pending['value']
                    else:
                        start = (address & 0xF000) - 0x8000
                        self.banks[bank][start:start + 0x1000] = b'\xff' * 0x1000
                        if self.stuck_after_erase is not None:
                            self.banks[bank][self.stuck_after_erase - 0x8000] = 0
                    self.pending = None
        return self.banks[bank][address - 0x8000]

    def __setitem__(self, address, value):
        assert 0 <= value <= 255
        if address < 0x8000:
            self.ram[address] = value
            if address in (PCR, LED):
                self.events.append((address, value))
            return
        bank = self.bank
        self.commands.append((bank, address, value))
        state = self.state[bank]
        if state == 'program':
            old = self.banks[bank][address - 0x8000]
            assert old & value == value, ('unsafe flash command escaped validation', old, value)
            self.begin('program', bank, address, value, address == self.fail_program)
            self.state[bank] = 0
        elif address == 0xD555 and value == 0xF0:
            self.pending = None
            self.state[bank] = 0
        elif state in (0, 3) and address == 0xD555 and value == 0xAA:
            self.state[bank] = state + 1
        elif state in (1, 4) and address == 0xAAAA and value == 0x55:
            self.state[bank] = state + 1
        elif state == 2 and address == 0xD555 and value in (0xA0, 0x80):
            self.state[bank] = 'program' if value == 0xA0 else 3
        elif state == 5 and value == 0x30:
            self.begin('erase', bank, address, 0xFF, self.fail_erase)
            self.state[bank] = 0
        else:
            raise AssertionError(('invalid flash command sequence', state, bank, address, value))

    def begin(self, kind, bank, address, value, fail=False):
        assert self.ram[LED] == 0xF0, 'flash mutation without the red LED latch'
        assert self.pending is None, 'new mutation before the preceding operation completed'
        self.mutations.append((kind, bank, address, value))
        self.pending = dict(kind=kind, bank=bank, address=address, value=value,
                            fail=fail, reads=self.delay_reads)


class Run:
    def __init__(self, variant, status=0xA0):
        self.variant, self.sym = variant, variant.sym
        self.mem = FlashMemory(variant.worker)
        self.cpu = MPU(memory=self.mem)
        self.cpu.a, self.cpu.x, self.cpu.y = 0x5A, 0xC3, 0xA7
        self.cpu.p = status
        self.initial_status = status
        self.timeout_seeds = []

    def set(self, name, value):
        self.mem.ram[self.sym[name]] = value

    def word(self, name, value):
        address = self.sym[name]
        self.mem.ram[address:address + 2] = bytes((value & 255, value >> 8))

    def get_word(self, name):
        address = self.sym[name]
        return self.mem.ram[address] | self.mem.ram[address + 1] << 8

    def run(self, entry='START', stop=(), hook=None, limit=1_000_000):
        self.cpu.sp = 0xFF
        self.cpu.stPushWord(STOP - 1)
        self.cpu.pc = self.sym[entry]
        poll = self.sym['STR8W_FLASH_WAIT'] + 6
        accelerated = False
        for _ in range(limit):
            if self.cpu.pc == STOP or self.cpu.pc in stop:
                return self.cpu.pc
            assert 0x0200 <= self.cpu.pc < self.sym['STR8W_LINKED_END'], (
                'worker executed outside its RAM image', hex(self.cpu.pc))
            if hook:
                hook(self)
            pending = self.mem.pending
            if self.cpu.pc == poll and pending and pending['fail'] and not accelerated:
                timer = self.sym['STR8W_TMO0']
                actual = tuple(self.mem.ram[timer:timer + 3])
                expected = (0, 0, 8 if pending['kind'] == 'erase' else 2)
                assert actual == expected, ('production timeout initializer', actual, expected)
                self.timeout_seeds.append(actual)
                # Exercise the actual DEC/BNE chain and reset-failure tail without
                # spending hundreds of thousands of iterations on a modeled stall.
                self.mem.ram[timer:timer + 3] = b'\x01\x01\x01'
                accelerated = True
            opcode = self.mem[self.cpu.pc]
            assert self.cpu.disassemble[opcode][0] != '???', hex(opcode)
            self.cpu.step()
        raise AssertionError(('instruction limit', self.variant.name, entry, hex(self.cpu.pc)))

    def returned(self, carry, bank=3, led=1):
        assert self.cpu.pc == STOP and self.cpu.sp == 0xFF
        assert self.cpu.p & 1 == carry
        # PHP/PLP supplies the software B/U bits; every other entry flag is restored.
        assert self.cpu.p & 0xCE == self.initial_status & 0xCE
        assert self.mem.bank == bank and self.mem.ram[LED] == led

    def outcome(self):
        # A/X/Y and private scratch are not full-worker result contracts.
        return (self.cpu.pc, self.cpu.p, self.cpu.sp, self.mem.ram[PCR],
                self.mem.ram[LED], bytes(self.mem.ram[0x7DE7:0x7E00]),
                bytes(self.mem.ram[0x7E95:0x7EA9]), self.mem.events,
                self.mem.commands, self.mem.mutations, self.timeout_seeds,
                tuple(hashlib.sha256(bank).digest() for bank in self.mem.banks))


def compare(variants, setup, check, entry='START', stop=(), hook=None, status=0xA0):
    global CASES
    results = []
    for variant in variants:
        run = Run(variant, status)
        setup(run)
        run.run(entry, stop, hook)
        check(run)
        results.append(run.outcome())
    assert results[0] == results[1], ('differential mismatch', CASES, entry)
    CASES += 1


def selector_tests(variants):
    for bank in range(256):
        for initial in range(4):
            extra = (bank & 1) | ((bank & 2) << 3)
            raw = PATTERNS[initial] | extra
            status = (0x20, 0xA4, 0x69, 0xED)[(bank + initial) & 3]

            def setup(run):
                run.cpu.a = bank
                run.mem.ram[PCR] = raw

            def check(run):
                valid = bank < 4
                run.returned(int(valid), bank if valid else initial, 0x43)
                assert run.cpu.y == 0xA7
                assert run.mem.ram[PCR] == (PATTERNS[bank] | extra if valid else raw)
                assert not run.mem.commands
                if not valid:
                    assert not run.mem.events

            compare(variants, setup, check, 'STR8W_BANK_SELECT_SERVICE', status=status)


def mode_tests(variants):
    for mode in range(256):
        if mode in (5, 7, 8):
            continue

        def setup(run):
            run.set('STR8_COPY_MODE', mode)
            run.mem.ram[PCR] = PATTERNS[1] | 0x11

        def check(run):
            run.returned(0, 1, 0x43)
            assert not run.mem.commands and not run.mem.events

        compare(variants, setup, check, status=0xE5)


def record_tests(variants):
    cases = [
        (0xFFB0, b'', b''),
        (0xFFB0, b'\xa5' * 64, b'\xa5' * 64),
        (0xFFB0, b'\xff' * 64, bytes(range(64))),
        (0x90FE, b'\xff' * 252, bytes((i * 17) & 255 for i in range(252))),
        (0x90FF, b'\xff\xa5\xf0\x00', b'\xff\xa5\x80\x00'),
    ]
    for address, old, new in cases:
        def setup(run):
            run.set('STR8_COPY_MODE', 7)
            run.word('STR8_REC_ADDR_LO', address)
            run.set('STR8_REC_DATA_LEN', len(new))
            run.mem.ram[0x7B00:0x7B00 + len(new)] = new
            run.mem.banks[3][address - 0x8000:address - 0x8000 + len(old)] = old
            # Preflight must select Bank 3 even when another bank looks incompatible.
            run.mem.ram[PCR] = PATTERNS[1] | 0x11
            run.mem.banks[1][address - 0x8000:address - 0x8000 + len(old)] = b'\x00' * len(old)

        def check(run):
            run.returned(1)
            assert run.mem.banks[3][address - 0x8000:address - 0x8000 + len(new)] == new
            assert len(run.mem.mutations) == sum(a != b for a, b in zip(old, new))

        compare(variants, setup, check, status=0xE5)

    for bad_index in (0, 1, 63):
        def setup(run):
            run.set('STR8_COPY_MODE', 7)
            run.word('STR8_REC_ADDR_LO', 0xFFB0)
            run.set('STR8_REC_DATA_LEN', 64)
            run.mem.ram[0x7B00:0x7B40] = b'\xa5' * 64
            run.mem.banks[3][0x7FB0 + bad_index] = 0

        def check(run):
            run.returned(0)
            assert run.get_word('STR8_REC_FAIL_LO') == 0xFFB0 + bad_index
            assert run.mem.ram[run.sym['STR8_REC_OBSERVED']] == 0
            assert run.mem.ram[run.sym['STR8_REC_EXPECTED']] == 0xA5
            assert not run.mem.commands, 'record preflight must finish before any flash command'

        compare(variants, setup, check)

    def timeout_setup(run):
        run.set('STR8_COPY_MODE', 7)
        run.word('STR8_REC_ADDR_LO', 0xFFB0)
        run.set('STR8_REC_DATA_LEN', 4)
        run.mem.ram[0x7B00:0x7B04] = b'\xa5' * 4
        run.mem.fail_program = 0xFFB2

    def timeout_check(run):
        run.returned(0)
        assert run.get_word('STR8_REC_FAIL_LO') == 0xFFB2
        assert run.mem.ram[run.sym['STR8_REC_OBSERVED']] == 0xFF
        assert run.mem.ram[run.sym['STR8_REC_EXPECTED']] == 0xA5
        assert run.mem.banks[3][0x7FB0:0x7FB4] == b'\xa5\xa5\xff\xff'
        assert run.timeout_seeds == [(0, 0, 2)]
        assert run.mem.commands[-1] == (3, 0xD555, 0xF0)

    compare(variants, timeout_setup, timeout_check)

    # Check the internal per-write guard itself, including a nonzero incoming Y.
    for observed, wanted, success in ((0, 0xFF, False), (0xA5, 0xA5, True)):
        def setup(run):
            run.word('STR8W_ADDR_LO', 0x9001)
            run.set('STR8W_DATA', wanted)
            run.mem.banks[3][0x1001] = observed

        def check(run):
            assert bool(run.cpu.p & 1) == success
            assert not run.mem.mutations
            assert run.mem.commands == ([] if success else [(3, 0xD555, 0xF0)])

        compare(variants, setup, check, 'STR8W_FLASH_WRITE')


def staged_setup(run, bank, sector, data, dirty=False, stage=0x3000):
    run.set('STR8_COPY_MODE', 5)
    run.set('STR8_COPY_DST_BANK', bank)
    run.set('STR8_MARK_SECTOR_HI', sector >> 8)
    run.set('STR8_STAGE_BUF_HI', stage >> 8)
    run.mem.ram[stage:stage + 0x1000] = data
    if dirty:
        start = sector - 0x8000
        run.mem.banks[bank][start:start + 0x1000] = b'\x00' * 0x1000


def staged_tests(variants):
    for bank, sector, dirty, erased in (
        (0, 0x8000, False, True),
        (1, 0xB000, True, True),
        (2, 0x8000, False, False),
        (3, 0xF000, True, False),
    ):
        data = b'\xff' * 4096 if erased else bytes((i * 17 + 9) & 255 for i in range(4096))

        def setup(run):
            staged_setup(run, bank, sector, data, dirty, 0x0A00 if bank & 1 else 0x3000)

        def check(run):
            run.returned(1)
            assert run.mem.banks[bank][sector - 0x8000:sector - 0x8000 + 4096] == data
            kinds = [entry[0] for entry in run.mem.mutations]
            assert kinds.count('erase') == int(dirty)
            assert kinds.count('program') == sum(value != 0xFF for value in data)
            assert not run.timeout_seeds

        compare(variants, setup, check, status=0xE5)

    for fault in ('erase_timeout', 'erase_verify', 'program_timeout', 'program_verify'):
        data = b'\x5a' * 4096

        def setup(run):
            staged_setup(run, 2, 0x8000, data, fault.startswith('erase'))
            run.mem.fail_erase = fault == 'erase_timeout'
            run.mem.stuck_after_erase = 0x8123 if fault == 'erase_verify' else None
            run.mem.fail_program = 0x8101 if fault == 'program_timeout' else None

        def hook(run):
            if fault == 'program_verify' and run.cpu.pc == run.sym['STR8W_VERIFY_DST_SECTOR']:
                run.mem.banks[2][0x2FE] ^= 1

        def check(run):
            run.returned(0)
            expected = dict(erase_timeout=0x8000, erase_verify=0x8123,
                            program_timeout=0x8101, program_verify=0x82FE)[fault]
            assert run.get_word('STR8_MARK_ADDR_LO') == expected
            if fault.endswith('timeout'):
                assert run.timeout_seeds == [(0, 0, 8 if fault.startswith('erase') else 2)]
                assert run.mem.commands[-1] == (2, 0xD555, 0xF0)
            else:
                assert not run.timeout_seeds
            if fault.startswith('erase'):
                assert not any(item[0] == 'program' for item in run.mem.mutations)

        compare(variants, setup, check, hook=hook)


def jump_tests(variants):
    for bank, vector in ((0, 0), (1, 0x7FFF), (2, 0x8000), (3, 0xFFFE),
                         (0, 0xFF00), (1, 0xFFFF), (4, 0x8000), (255, 0x8000)):
        valid = bank < 4 and 0x8000 <= vector < 0xFFFF

        def setup(run):
            run.set('STR8_COPY_MODE', 8)
            run.set('STR8_JUMP_BANK', bank)
            if bank < 4:
                run.mem.banks[bank][0x7FFC:0x7FFE] = bytes((vector & 255, vector >> 8))

        def check(run):
            assert not run.mem.commands
            if valid:
                assert run.cpu.pc == vector and run.cpu.sp == 0xFF and run.cpu.x == 0xFF
                assert run.cpu.p & (run.cpu.INTERRUPT | run.cpu.DECIMAL) == run.cpu.INTERRUPT
                assert run.mem.bank == bank and run.mem.ram[LED] == 0
                assert run.mem.ram[0x7DFD:0x7E00] == bytes((ord('B'), ord('J'), bank))
                assert run.mem.ram[0x7DF5] == 0x80
            else:
                run.returned(0)
                expected = 1 if bank >= 4 else 2 if vector < 0x8000 else 3
                assert run.mem.ram[0x7DF5] == expected

        compare(variants, setup, check, stop=(vector,) if valid else (), status=0xE9)


def poll_timing_tests(variants):
    # No counter acceleration: compare execution cycles across the real low-byte
    # rollover as well as immediate and delayed completion.
    for delay in (0, 1, 15, 255, 256, 257):
        cycles = []
        for variant in variants:
            run = Run(variant)
            run.word('STR8W_ADDR_LO', 0x9000)
            run.set('STR8W_DATA', 0x5A)
            run.mem.ram[LED] = 0xF0
            run.mem.delay_reads = delay
            run.mem.begin('program', 3, 0x9000, 0x5A)
            run.cpu.a = 2
            run.run('STR8W_FLASH_WAIT')
            assert run.cpu.p & 1 and not run.timeout_seeds
            cycles.append(run.cpu.processorCycles)
        assert cycles[0] == cycles[1], ('polling cycles changed', delay, cycles)


def layout_tests(variants, baseline_only):
    old, new = variants
    for variant in variants:
        assert len(variant.image) == 4096
        assert variant.sym['START'] == 0x0200
        assert variant.sym['STR8W_BANK_SELECT_SERVICE'] == 0x0203
        assert variant.sym['STR8W_LINKED_SELECT_END'] < 0x0300
        assert variant.resident['STR8_WORKER_STORE'] + len(variant.worker) == 0xFFB0
    if not baseline_only:
        assert len(old.worker) == 608 and len(new.worker) == 568
        assert new.sym['STR8W_LINKED_END'] == 0x0438
        assert new.sym['STR8W_LINKED_SELECT_END'] == 0x0227
        assert new.resident['STR8_WORKER_STORE'] == 0xFD78
    waits = []
    for variant in variants:
        start = variant.sym['STR8W_FLASH_WAIT'] - 0x0200
        end = variant.sym['STR8W_FLASH_UNLOCK'] - 0x0200
        waits.append(variant.worker[start:end])
    assert waits[0] == waits[1], 'flash polling instructions or timeout counters changed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    fixture = json.loads((ROOT / 'tools/fixtures/resident-v133-before-size.json').read_text())
    old_image = base64.b64decode(fixture['image'])
    assert hashlib.sha256(old_image).hexdigest() == fixture['sha256']
    old = Variant('baseline', old_image, fixture['symbols'], fixture['worker_symbols'])
    new = old if args.baseline_only else Variant(
        'candidate', (REL / 'bin/str8n-v1.34-bank3-f000-ffff.bin').read_bytes(),
        symbols(REL / 'map/str8n-v1.34-f000.map'),
        symbols(REL / 'map/str8n-v1.34-worker-0200.map'))
    variants = (old, new)
    layout_tests(variants, args.baseline_only)
    for suite in (selector_tests, mode_tests, record_tests, staged_tests, jump_tests, poll_timing_tests):
        suite(variants)
        print(f'{suite.__name__}: PASS', flush=True)
    print(f'WORKER DIFFERENTIAL: {CASES} cases PASS; modeled hardware, accelerated failure timeouts')
    if args.baseline_only:
        print('BASELINE ONLY: candidate bytes were not tested')


if __name__ == '__main__':
    main()
