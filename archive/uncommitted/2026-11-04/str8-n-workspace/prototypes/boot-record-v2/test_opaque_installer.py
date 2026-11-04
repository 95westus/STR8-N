"""Linked CPU/NOR qualification of the MON-independent opaque RAM installer.

This is deliberately separate from test.py and its journal-only NOR policy.
Nothing in this file opens a serial port or a board connection.
"""
import argparse
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boot_record_v2_tests', HERE / 'test.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROOT = base.ROOT
crc, sha = base.crc, base.sha

ALLOWED = tuple((bank, sector) for bank in range(4)
                for sector in range(0x80, 0x100, 0x10)
                if bank != 3 or sector in (0x80, 0x90, 0xe0))
PROTECTED = ((3, 0xa0), (3, 0xb0), (3, 0xf0))
PROMPT = b'INSTALLER I Q> '
HEADER_READY = b'SEND OIP1 HEADER\r\n'
PAYLOAD_READY = b'SEND 4096\r\n'
READ_READY = b'READ SECTOR+CRC\r\n'
READ_DONE = b'\r\nOK: read\r\n'
LOCKED = b'LOCKED: RESET required\r\n'
BODY = bytes(range(256)) * 16


def frame(op=1, bank=0, sector=0x80, body=BODY, preimage=None,
          length=4096, reserved=bytes(4), magic=b'OIP1', version=1):
    before = crc(preimage) if preimage is not None else 0
    payload = crc(body) if op == 1 else 0
    raw = (magic + bytes((version, op, bank, sector))
           + length.to_bytes(2, 'little') + before.to_bytes(2, 'little')
           + payload.to_bytes(2, 'little') + reserved)
    assert len(raw) == 18
    return raw + crc(raw).to_bytes(2, 'little')


def reseal(raw):
    return bytes(raw[:18]) + crc(raw[:18]).to_bytes(2, 'little')


def valid_records(banks):
    rows = []
    for offset in range(0x4000, 0x6000, 256):
        row = bytes(banks[3][offset:offset + 256])
        if (row[:4] == b'SNBT' and row[255] == 0
                and crc(row[:30]) == int.from_bytes(row[30:32], 'little')
                and crc(row[:252]) == int.from_bytes(row[252:254], 'little')):
            rows.append(row)
    return rows


def latest_record(banks):
    rows = valid_records(banks)
    return max(rows, key=lambda r: int.from_bytes(r[8:12], 'little')) if rows else None


def counter(row, bank, sector):
    index = bank * 8 + (sector >> 4) - 8
    return int.from_bytes(row[64 + index * 3:67 + index * 3], 'little')


class PowerLoss(Exception):
    pass


class InstallerMemory(base.Memory):
    """Permit only this operation's target plus the existing C/D journal.

    The inherited AMD command decoder, busy-ROM-fetch assertion, erase behavior,
    and no-reprogram-before-erase checks remain unchanged.
    """
    def __init__(self, banks, dual=True):
        super().__init__(banks, dual)
        self.target = None
        self.baseline = None
        self.cut_after = None
        self.observer = None
        self.reservations = []
        self.target_erases = 0
        self.initial_counts = None
        self.newest = latest_record(self.banks)

    def arm(self, target):
        self.target = target
        self.baseline = tuple(bytes(bank) for bank in self.banks)
        self.initial_counts = latest_record(self.banks)
        self.newest = self.initial_counts
        self.target_erases = 0
        self.events.clear()
        self.reservations.clear()

    def mutated(self, kind, address, value):
        sector = address & 0xf000
        is_journal = self.bank == 3 and 0xc000 <= address < 0xe000
        assert is_journal or (self.bank, sector >> 8) == self.target, (
            'out-of-range mutation', kind, self.bank, hex(address), self.target)
        assert is_journal or self.target in ALLOWED
        if is_journal:
            self.newest = latest_record(self.banks)
        assert self.newest is not None, 'Mutation destroyed the final complete committed journal record'
        if kind == 'erase':
            newest = self.newest
            if is_journal:
                assert counter(newest, 3, sector >> 8) >= 2, 'Journal erase lacked durable reservation'
            else:
                self.target_erases += 1
                before = counter(self.initial_counts, self.bank, sector >> 8)
                after = counter(newest, self.bank, sector >> 8)
                assert after >= before + self.target_erases, 'Target erase preceded durable wear reservation'
                self.reservations.append(dict(bank=self.bank, sector=sector >> 8,
                                              count=after, journal_sha256=sha(newest)))
        self.events.append((kind, self.bank, address, value))
        if self.observer is not None:
            self.observer(self)
        if self.cut_after is not None and len(self.events) >= self.cut_after:
            raise PowerLoss()

    def assert_preserved(self):
        assert self.baseline is not None
        for bank in range(4):
            for sector in range(0x80, 0x100, 0x10):
                if (bank, sector) == self.target or bank == 3 and sector in (0xc0, 0xd0):
                    continue
                offset = (sector - 0x80) << 8
                assert self.banks[bank][offset:offset + 4096] == self.baseline[bank][offset:offset + 4096], (
                    'Unrelated sector changed', bank, hex(sector))


class InstallerMachine(base.Machine):
    def __init__(self, build, cpu, rows=None, banks=None):
        if rows is None:
            rows = [(0xc000, base.record())]
        super().__init__(build, cpu, rows, opaque=True)
        old = self.m
        memory = InstallerMemory(banks or old.banks, dual=self.dual)
        # F has already initialized the real RAM worker, vectors, and console.
        memory.ram[:] = old.ram
        memory.bank = old.bank
        memory.cpu = self.c
        self.m = self.c.memory = memory
        self.build = build
        self.i = self.sy['core/ram-installer']
        self.hooks = {}
        self.accelerate_local_crc = True

    def run(self, stop, limit=4000000):
        for _ in range(limit):
            if stop():
                return
            c, m = self.c, self.m
            self.steps += 1
            hook = getattr(self, 'hooks', {}).get(c.pc)
            if hook is not None:
                hook(self)
                continue
            if c.pc == self.b['J_CRC_BYTE'] and m.bank == 3 and self.accelerate_crc:
                base.fast_crc(c, m, 0x7d38)
                continue
            if (getattr(self, 'accelerate_local_crc', False)
                    and c.pc == self.i['OI_CRC_BYTE']):
                base.fast_crc(c, m, self.i['OI_CRC'])
                continue
            if self.dual and self.accelerate_acia and c.pc == self.w['V2W_ACIA_DELAY_OUTER']:
                c.processorCycles += 4183
                c.a = 0
                c.p = (c.p & ~0x82) | 2
                c.pc = self.w['V2W_ACIA_SEND'] + 14
                continue
            if c.pc == self.w['V2W_BOOT_DELAY_OUTER']:
                c.pc = self.w['V2W_BOOT_DELAY_DONE']
                continue
            op = m[c.pc]
            if self.name == '65c02' and op & 15 == 15:
                pc = c.pc
                bit = bool(m[m[(pc + 1) & 65535]] & (1 << ((op >> 4) & 7)))
                take = bit if op & 128 else not bit
                d = m[(pc + 2) & 65535]
                c.pc = (pc + 3 + ((d if d < 128 else d - 256) if take else 0)) & 65535
            else:
                c.step()
        raise AssertionError(('timeout', self.name, hex(self.c.pc), bytes(self.m.tx[-200:])))

    def load(self, via_f=True):
        binary = (self.build / 'payload/ram-installer-offline.bin').read_bytes()
        if via_f:
            self.recovery()
            self.command(b'L\r', b'SEND HEADER+BIN\r\n')
            out = self.command(base.header(binary) + binary)
            assert b'LOADED;' in out
            self.command(b'R\r', PROMPT)
        else:
            self.m.ram[0x2000:0x2000 + len(binary)] = binary
            self.c.pc = 0x2000
            self.run(lambda: bytes(self.m.tx).endswith(PROMPT))
        assert self.m.banks[3][0x2000:0x4000] == b'\xff' * 8192, 'MON A/B must be absent'
        self.m.rx.clear()
        self.m.acia_rx.clear()
        self.run(lambda: self.c.pc == self.w['V2W_GETC'])

    def begin(self, port=1, ending=b'\r'):
        return self.port_command(port, b'I' + ending, HEADER_READY)

    def request(self, raw, body=None, port=1, ending=b'\r', result_ending=PROMPT):
        self.begin(port, ending)
        if body is None:
            return self.port_command(port, raw, result_ending)
        self.port_command(port, raw, PAYLOAD_READY)
        return self.port_command(port, body, result_ending)

    def sector(self, bank, sector):
        start = (sector - 0x80) << 8
        return bytes(self.m.banks[bank][start:start + 4096])


def patterned_machine(build, cpu, rows=None, banks=None, via_f=False):
    h = InstallerMachine(build, cpu, rows, banks)
    if banks is None:
        # Distinct non-erased targets expose unintended bank/sector writes.
        for bank, sector in ALLOWED:
            offset = (sector - 0x80) << 8
            h.m.banks[bank][offset:offset + 4096] = bytes((n + bank * 37 + sector) & 255 for n in range(4096))
    h.load(via_f)
    return h


def install_protected_monitor_fixtures(h):
    for sector in (0xa0, 0xb0):
        component = (h.build / f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
        start = (sector - 0x80) << 8
        h.m.banks[3][start:start + 4096] = component


def protocol_tests(build, cpu, passed):
    for bank, sector in ALLOWED:
        h = patterned_machine(build, cpu)
        h.m.arm((bank, sector))
        before = h.sector(bank, sector)
        settings = latest_record(h.m.banks)
        application = (bytes(h.m.ram[0x200:0x2000]), bytes(h.m.ram[h.i['INSTALLER_END']:0x6500]))
        out = h.request(frame(bank=bank, sector=sector, preimage=before), BODY)
        assert b'OK' in out, out
        assert h.sector(bank, sector) == BODY
        assert len(h.m.reservations) == 1
        newest = latest_record(h.m.banks)
        for b in range(4):
            for s in range(0x80, 0x100, 0x10):
                assert counter(newest, b, s) == counter(settings, b, s) + int((b, s) == (bank, sector))
        assert newest[7:8] + newest[12:30] + newest[32:64] + newest[160:252] == settings[7:8] + settings[12:30] + settings[32:64] + settings[160:252]
        h.m.assert_preserved()
        events = len(h.m.events)
        target_programs = sum(e[0] == 'program' and (e[1], e[2] & 0xf000) == (bank, sector << 8)
                              for e in h.m.events)
        assert target_programs == 4080
        reserved = h.m.reservations[0]
        n = len(h.m.events)
        out = h.request(frame(op=0, bank=bank, sector=sector))
        assert out == READ_READY + BODY + crc(BODY).to_bytes(2, 'little') + READ_DONE + PROMPT, (out[:80], out[-80:])
        assert len(h.m.events) == n
        # A byte-identical retry must consume no endurance reservation or erase.
        h.m.arm((bank, sector))
        image = tuple(map(bytes, h.m.banks))
        out = h.request(frame(bank=bank, sector=sector, preimage=BODY), BODY)
        assert b'OK' in out and not h.m.events
        assert tuple(map(bytes, h.m.banks)) == image
        assert application == (bytes(h.m.ram[0x200:0x2000]), bytes(h.m.ram[h.i['INSTALLER_END']:0x6500]))
        passed(cpu, f'allowed-B{bank}-{sector >> 4:X}-write-readback-noop',
               payload_bytes=4096, all_byte_values=True, mutation_events=events,
               target_programs=target_programs, durable_reservation=reserved,
               unrelated_sectors_unchanged=29, application_RAM_preserved=True,
               configuration_and_other_wear_counters_preserved=True)

    refusals = []
    for op in (0, 1):
        for sector in (0xa0, 0xb0, 0xc0, 0xd0, 0xf0):
            refusals.append((f'protected-op{op}-B3-{sector >> 4:X}', frame(op=op, bank=3, sector=sector)))
    for bank in (4, 0xff):
        refusals.append((f'bank-{bank}', frame(bank=bank)))
    for sector in (0, 0x70, 0x81, 0x8f, 0xe1, 0xf8, 0xff):
        refusals.append((f'sector-{sector:02X}', frame(sector=sector)))
    for length in (0, 1, 4095, 4097, 8192, 0xffff):
        refusals.append((f'spanning-or-invalid-length-{length}', frame(length=length)))
    for bank, sector in ((3, 0x90), (3, 0xe0), (0, 0xf0)):
        for length in (4097, 8192):
            refusals.append((f'protected-span-B{bank}-{sector:X}-{length}',
                             frame(bank=bank, sector=sector, length=length)))
    for label, changes in (
            ('magic', dict(magic=b'XIP1')), ('version', dict(version=2)),
            ('opcode', dict(op=2)), ('reserved-14', dict(reserved=b'\x01\0\0\0')),
            ('reserved-15', dict(reserved=b'\0\x01\0\0')),
            ('reserved-16', dict(reserved=b'\0\0\x01\0')),
            ('reserved-17', dict(reserved=b'\0\0\0\x01'))):
        refusals.append((label, frame(**changes)))
    bad = bytearray(frame()); bad[18] ^= 1
    refusals.append(('header-CRC', bytes(bad)))
    for byte in (10, 12):
        bad = bytearray(frame(op=0)); bad[byte] = 1
        refusals.append((f'read-nonzero-CRC-field-{byte}', reseal(bad)))
    for label, raw in refusals:
        h = patterned_machine(build, cpu)
        h.m.arm(None)
        before = tuple(map(bytes, h.m.banks))
        out = h.request(raw, result_ending=LOCKED)
        assert b'REFUSED' in out and not h.m.events, (label, out)
        assert tuple(map(bytes, h.m.banks)) == before
        assert_quarantined(h)
    passed(cpu, 'malformed-and-protected-frames-refused-before-any-mutation',
           comparisons=len(refusals), cases=[label for label, _ in refusals])

    for label in ('payload-CRC', 'preimage-CRC'):
        h = patterned_machine(build, cpu)
        h.m.arm((0, 0x80))
        before = tuple(map(bytes, h.m.banks))
        raw = bytearray(frame(preimage=h.sector(0, 0x80)))
        raw[12 if label == 'payload-CRC' else 10] ^= 1
        out = h.request(reseal(raw), BODY, result_ending=LOCKED if label == 'payload-CRC' else PROMPT)
        assert b'REFUSED' in out and not h.m.events
        assert tuple(map(bytes, h.m.banks)) == before
        if label == 'payload-CRC':
            assert_quarantined(h)
        passed(cpu, label + '-refused-before-reservation')

    # Both streams and every text terminator must preserve binary 00/03/0A/0D/FF.
    for port in (1, 2):
        for ending in (b'\r', b'\n', b'\r\n'):
            h = patterned_machine(build, cpu)
            h.m.arm((0, 0x80))
            h.begin(port, ending)
            other = h.m.acia_rx if port == 1 else h.m.rx
            noise = b'I\rQ\r\x03\0\xff'
            other.extend(noise)
            h.port_command(port, frame(preimage=h.sector(0, 0x80)), PAYLOAD_READY)
            out = h.port_command(port, BODY, PROMPT)
            assert b'OK' in out and h.sector(0, 0x80) == BODY
            assert bytes(other) == noise, 'Binary operation consumed the other console'
            other.clear()
            h.m.assert_preserved()
            passed(cpu, f'raw-4K-port-{port}-ending-{ending.hex()}', payload_bytes=4096)

    for phase, lengths in (('header', (0, 1, 4, 19)), ('payload', (0, 1, 255, 4095))):
        for length in lengths:
            h = patterned_machine(build, cpu)
            h.m.arm((0, 0x80))
            before = tuple(map(bytes, h.m.banks))
            h.begin()
            if phase == 'payload':
                h.port_command(1, frame(preimage=h.sector(0, 0x80)), PAYLOAD_READY)
                part = BODY[:length]
            else:
                part = frame(preimage=h.sector(0, 0x80))[:length]
            n = len(h.m.tx)
            h.m.rx.extend(part)
            h.run(lambda: len(h.m.tx) > n and bytes(h.m.tx).endswith(LOCKED), limit=12000000)
            assert b'REFUSED' in h.m.tx[n:] and not h.m.events
            assert tuple(map(bytes, h.m.banks)) == before
            assert_quarantined(h)
            passed(cpu, f'partial-{phase}-{length}-timeout-without-mutation')

    for label, recs in (
            ('missing-journal', []),
            ('corrupt-full-record-CRC', [(0xc000, bytes(bytearray(base.record())[:64])
                                         + bytes([base.record()[64] ^ 1]) + base.record()[65:])]),
            ('saturated-target-counter', [(0xc000, base.record(counts=[0xffffff] + [1] * 31))]),
            ('same-sequence-divergent-committed-history',
             [(0xc000, base.record()), (0xc100, base.record(counts=[200] * 32))])):
        h = patterned_machine(build, cpu, rows=recs)
        h.m.arm((0, 0x80))
        before = tuple(map(bytes, h.m.banks))
        out = h.request(frame(preimage=h.sector(0, 0x80)), BODY)
        assert b'REFUSED' in out and not h.m.events, (label, out)
        assert tuple(map(bytes, h.m.banks)) == before
        passed(cpu, label + '-refused-before-target-erase')

    for phase in ('header', 'payload'):
        h = patterned_machine(build, cpu)
        h.m.arm((0, 0x80))
        h.begin()
        if phase == 'payload':
            h.port_command(1, frame(preimage=h.sector(0, 0x80)), PAYLOAD_READY)
            data = BODY
        else:
            data = frame(preimage=h.sector(0, 0x80))
        h.m.ram[0xf1] = 1
        out = h.port_command(1, data, LOCKED)
        assert b'REFUSED' in out and not h.m.events
        assert_quarantined(h)
        passed(cpu, phase + '-sticky-receive-error-quarantines')

    h = patterned_machine(build, cpu)
    h.m.arm((0, 0x80))
    h.m.ft_tx_blocked = True
    h.m.rx.extend(b'I\r')
    h.run(lambda: bytes(h.m.acia_tx).endswith(LOCKED))
    assert b'REFUSED: TX blocked' in h.m.acia_tx and not h.m.events
    h.m.ft_tx_blocked = False
    assert_quarantined(h)
    passed(cpu, 'blocked-binary-ready-TX-quarantines-and-drains-late-tail')

    for fault in ('erase_verify', 'final-readback'):
        h = patterned_machine(build, cpu)
        h.m.arm((0, 0x80))
        if fault == 'erase_verify':
            h.m.fault = 'erase_verify'
        else:
            def corrupt(t):
                del t.hooks[t.i['OI_PROGRAM_END']]
                t.m.banks[0][37] ^= 1
            h.hooks[h.i['OI_PROGRAM_END']] = corrupt
        out = h.request(frame(preimage=h.sector(0, 0x80)), BODY)
        assert b'FAILED: flash/readback' in out
        assert h.sector(0, 0x80) != BODY
        assert len(h.m.reservations) == 1
        h.m.assert_preserved()
        h.m.fault = None
        h.m.arm((0, 0x80))
        out = h.request(frame(preimage=h.sector(0, 0x80)), BODY)
        assert b'OK' in out and h.sector(0, 0x80) == BODY
        h.m.assert_preserved()
        passed(cpu, fault + '-failure-retains-protected-sectors-and-fresh-retry-recovers')

    h = patterned_machine(build, cpu)
    install_protected_monitor_fixtures(h)
    h.m.arm((2, 0xf0))
    out = h.request(frame(bank=2, sector=0xf0, preimage=h.sector(2, 0xf0)), BODY)
    assert b'OK' in out and h.sector(2, 0xf0) == BODY
    h.m.assert_preserved()
    passed(cpu, 'populated-MON-A-B-and-F-components-preserved')


def assert_quarantined(h):
    h.run(lambda: h.c.pc == h.i['OI_LOCK_DRAIN'])
    before = tuple(map(bytes, h.m.banks))
    event_count = len(h.m.events)
    output = (bytes(h.m.tx), bytes(h.m.acia_tx))
    # A timed-out body can contain command-looking delayed bytes. Neither
    # console can turn them into Q or F load/run/monitor/journal commands.
    tail = b'Q\rL\rR\rA\rB\rI\r\x03\0\xff'
    h.m.rx.extend(tail)
    h.m.acia_rx.extend(tail)
    end = h.steps + 12000
    h.run(lambda: h.steps >= end, limit=12001)
    h.run(lambda: h.c.pc == h.i['OI_LOCK_DRAIN'])
    assert not h.m.rx and not h.m.acia_rx
    assert output == (bytes(h.m.tx), bytes(h.m.acia_tx))
    assert len(h.m.events) == event_count and tuple(map(bytes, h.m.banks)) == before
    assert h.m.bank == 3 and h.m.ram[0xf4] == 0 and h.m.ram[0x7c2b] == 0


def word(memory, address):
    return int.from_bytes(memory.ram[address:address + 2], 'little')


def store_word(memory, address, value):
    memory.ram[address:address + 2] = (value & 65535).to_bytes(2, 'little')


def return_from_call(h, carry=True):
    h.c.p = (h.c.p & ~1) | int(carry)
    h.c.pc = (h.c.stPopWord() + 1) & 65535


def select_bank(h, bank):
    h.m[0x7fec] = (h.m.ram[0x7fec] & 0x11) | (0xcc, 0xce, 0xec, 0xee)[bank]


def primitive_byte(h, address, value):
    """Same AMD transactions as linked V2W_BYTE, through unmodified NOR."""
    m = h.m
    m[0xd555] = 0xaa
    m[0xaaaa] = 0x55
    m[0xd555] = 0xa0
    m[address] = value
    while m.busy:
        m[address]
    m[0xd555] = 0xf0


def accelerated_hooks(h, journal_cache=None):
    """Validated loop summaries used only for exhaustive retry replay.

    Ordinary protocol tests execute these loops instruction by instruction.
    Erase and journal byte summaries use the inherited AMD NOR decoder.
    Target programming replays the differentially verified trace in bulk,
    checking bounds, an erased target, and one-program-per-erase preconditions.
    """
    i, w, m = h.i, h.w, h.m

    def receive(t):
        port = t.m.ram[0x7c2b]
        queue = t.m.rx if port == 1 else t.m.acia_rx
        assert len(queue) >= 4096
        data = bytes(queue.popleft() for _ in range(4096))
        t.m.ram[0x6800:0x7800] = data
        t.m.ram[i['OI_CRC']:i['OI_CRC'] + 2] = crc(data).to_bytes(2, 'little')
        store_word(t.m, 0xe0, 0x7800)
        t.m.ram[i['OI_PAGES']] = 0
        t.c.pc = receive_done

    def target_crc(t):
        bank, sector = t.m.ram[i['OI_HEADER'] + 6:i['OI_HEADER'] + 8]
        select_bank(t, bank)
        store_word(t.m, 0xe4, sector << 8)
        store_word(t.m, 0xe0, (sector + 0x10) << 8)
        t.m.ram[i['OI_PAGES']] = 0
        t.m.ram[i['OI_CRC']:i['OI_CRC'] + 2] = crc(t.sector(bank, sector)).to_bytes(2, 'little')
        t.c.x = 0
        return_from_call(t)

    def compare(t):
        bank, sector = t.m.ram[i['OI_HEADER'] + 6:i['OI_HEADER'] + 8]
        select_bank(t, bank)
        desired = bytes(t.m.ram[0x6800:0x7800])
        actual = t.sector(bank, sector)
        equal = actual == desired
        offset = 4096 if equal else next(n for n in range(4096) if actual[n] != desired[n])
        store_word(t.m, 0xe4, (sector << 8) + offset)
        store_word(t.m, 0xe6, 0x6800 + offset)
        t.m.ram[i['OI_PAGES']] = 16 - (offset >> 8)
        return_from_call(t, equal)

    def erase_verify(t):
        address = word(t.m, 0xe4)
        assert t.sector(t.m.bank, address >> 8) == b'\xff' * 4096
        store_word(t.m, 0xe4, address + 4096)
        t.m.ram[i['OI_PAGES']] = 0
        # The immediately following JSR OI_TARGET precedes OI_PROGRAM setup.
        t.c.pc = erase_done

    def program(t):
        address = word(t.m, 0xe4)
        assert word(t.m, 0xe6) == 0x6800
        bank = t.m.bank
        assert (bank, address >> 8) == t.m.target and t.m.target in ALLOWED
        assert t.sector(bank, address >> 8) == b'\xff' * 4096
        assert not any(b == bank and address <= a < address + 4096 for b, a in t.m.programmed)
        desired = bytes(t.m.ram[0x6800:0x7800])
        events = [('program', bank, address + n, value) for n, value in enumerate(desired) if value != 255]
        if t.m.cut_after is not None or t.m.observer is not None:
            for _, _, at, value in events:
                primitive_byte(t, at, value)
        else:
            # Replay the exact already-differentially-checked AMD trace as one
            # vector operation. Erase, bounds, reservation and no-reprogram
            # preconditions are checked before this summary is applicable.
            t.m.banks[bank][address - 0x8000:address - 0x8000 + 4096] = desired
            t.m.programmed.update((bank, at) for _, _, at, _ in events)
            t.m.events.extend(events)
        store_word(t.m, 0xe4, address + 4096)
        store_word(t.m, 0xe6, 0x7800)
        t.m.ram[i['OI_PAGES']] = 0
        t.c.pc = i['OI_PROGRAM_END']

    def byte(t):
        primitive_byte(t, word(t.m, 0xe4), t.m.ram[0xf0])
        t.c.a = 0xf0
        t.c.x = t.c.y = 0
        return_from_call(t)

    def erase(t):
        address = word(t.m, 0xe4)
        for address_out, value in ((0xd555, 0xaa), (0xaaaa, 0x55), (0xd555, 0x80),
                                   (0xd555, 0xaa), (0xaaaa, 0x55), (address, 0x30)):
            t.m[address_out] = value
        t.m.ram[0xf0] = 255
        while t.m.busy:
            t.m[address]
        t.m[0xd555] = 0xf0
        t.c.a = 0xf0
        t.c.x = t.c.y = 0
        return_from_call(t)

    def journal(t):
        key = (bytes(t.m.banks[3][0x4000:0x6000]), t.m.ram[0x7d3c], t.c.a)
        saved_zp = bytes(t.m.ram[0xe0:0x100])
        if key not in journal_cache:
            before = bytes(t.m.ram)
            count = len(t.m.events)
            sp = t.c.sp
            return_pc = (t.m.ram[0x100 + ((sp + 1) & 255)]
                         | t.m.ram[0x100 + ((sp + 2) & 255)] << 8) + 1
            hook = t.hooks.pop(i['JE_ENTER'])
            try:
                t.run(lambda: t.c.pc == return_pc and t.c.sp == (sp + 2) & 255)
            finally:
                t.hooks[i['JE_ENTER']] = hook
            changes = [(n, value) for n, value in enumerate(t.m.ram)
                       if value != before[n] and not 0xe0 <= n < 0x100
                       and not 0x7dcb <= n < 0x7deb]
            journal_cache[key] = dict(image=bytes(t.m.banks[3][0x4000:0x6000]),
                                      events=list(t.m.events[count:]), changes=changes,
                                      newest=t.m.newest, a=t.c.a, p=t.c.p & 0x83,
                                      programmed={x for x in t.m.programmed if x[0] == 3})
            return
        result = journal_cache[key]
        t.m.banks[3][0x4000:0x6000] = result['image']
        t.m.events.extend(result['events'])
        t.m.programmed.update(result['programmed'])
        t.m.newest = result['newest']
        for address, value in result['changes']:
            t.m.ram[address] = value
        t.m.ram[0x7dcb:0x7deb] = saved_zp
        t.c.a = result['a']
        t.c.p = (t.c.p & ~0x83) | result['p']
        t.c.pc = (t.c.stPopWord() + 1) & 65535

    # Resolve loop successors from linked bytes and assert their exact shape.
    code = bytes(m.ram[i['OI_RECEIVE']:i['OI_RECEIVE'] + 48])
    receive_done = i['OI_RECEIVE'] + code.index(bytes((0xa5, 0xf1)))
    code = bytes(m.ram[i['OI_ERASE_VERIFY']:i['OI_ERASE_VERIFY'] + 48])
    target_jsr = bytes((0x20, i['OI_TARGET'] & 255, i['OI_TARGET'] >> 8))
    erase_done = i['OI_ERASE_VERIFY'] + code.index(target_jsr)
    hooks = {i['OI_RECEIVE']: receive, i['OI_TARGET_CRC']: target_crc,
            i['OI_COMPARE']: compare, i['OI_ERASE_VERIFY']: erase_verify,
            i['OI_PROGRAM']: program, w['V2W_BYTE']: byte, w['V2W_BYTE'] + 2: byte,
            w['V2W_ERASE_RAW']: erase, w['V2W_ERASE_RAW'] + 2: erase}
    if journal_cache is not None:
        hooks[i['JE_ENTER']] = journal
    return hooks


def clone_prepared(prepared, banks):
    """Power cycle with F-initialized ABI/tool RAM from a verified checkpoint."""
    h = object.__new__(InstallerMachine)
    h.__dict__ = dict(prepared.__dict__)
    h.m = InstallerMemory(banks, prepared.dual)
    h.m.ram[:] = prepared.m.ram
    h.m.bank = prepared.m.bank
    h.c = (base.CPU02 if h.name == '65c02' else base.CPU816)(memory=h.m, pc=prepared.c.pc)
    # py65816 ignores its constructor's pc argument and reset() loads FFFC.
    # Copy the actual checkpoint explicitly, including its 816 mode/bank state.
    for name in ('pc', 'a', 'x', 'y', 'p', 'sp', 'b', 'mode', 'dbr', 'pbr', 'dpr',
                 'IRQ_pin', 'waiting', 'processorCycles', 'excycles', 'addcycles', 'start_pc'):
        if hasattr(prepared.c, name):
            setattr(h.c, name, getattr(prepared.c, name))
    h.m.cpu = h.c
    h.steps = 0
    h.hooks = {}
    assert h.c.memory is h.m and h.m.cpu is h.c
    assert h.c is not prepared.c and h.m is not prepared.m
    assert h.m.ram == prepared.m.ram
    assert h.m.ram[0x100:0x200] == prepared.m.ram[0x100:0x200]
    return h


def assert_exact_checkpoint_clone(h):
    sample = clone_prepared(h, h.m.banks)
    # These synthetic values are never executed. They ensure equality is
    # demonstrated for non-default hidden accumulator/bank/timing/IRQ state.
    for name, value in dict(b=0xa5, dbr=0x12, pbr=0x34, dpr=0x4567,
                            processorCycles=0x123456, excycles=7,
                            addcycles=True, waiting=True, IRQ_pin=0,
                            start_pc=0x2468).items():
        if hasattr(sample.c, name):
            setattr(sample.c, name, value)
    copied = clone_prepared(sample, sample.m.banks)
    actual = {k: v for k, v in copied.c.__dict__.items() if k != 'memory'}
    expected = {k: v for k, v in sample.c.__dict__.items() if k != 'memory'}
    assert actual == expected, ('Checkpoint CPU state differs', actual, expected)


def validate_acceleration(build, cpu, passed):
    h = patterned_machine(build, cpu)
    assert_exact_checkpoint_clone(h)
    h.accelerate_local_crc = False
    comparisons = 0
    for seed in (0, 65535, 0x8000, 0x7fff, 0x1234, 0x55aa):
        for value in range(256):
            h.m.ram[h.i['OI_CRC']:h.i['OI_CRC'] + 2] = seed.to_bytes(2, 'little')
            h.call(h.i['OI_CRC_BYTE'], value)
            assert word(h.m, h.i['OI_CRC']) == base.binascii.crc_hqx(bytes([value]), seed)
            comparisons += 1
    passed(cpu, 'linked-local-RAM-CRC-all-bytes-six-seeds', comparisons=comparisons)
    # A complete linked write and summarized write must produce exactly the
    # same flash bytes, ordered mutation trace, response and durable counter.
    for scenario, recs in interruption_fixtures():
        real = patterned_machine(build, cpu, rows=recs)
        checkpoint = clone_prepared(real, real.m.banks)
        fast = clone_prepared(real, real.m.banks)
        for item in (real, fast):
            item.m.arm((0, 0x80))
        cache = {}
        fast.hooks = accelerated_hooks(fast, cache)
        raw = frame(preimage=real.sector(0, 0x80))
        actual = real.request(raw, BODY)
        summarized = fast.request(raw, BODY)
        assert actual == summarized
        assert real.m.banks == fast.m.banks
        assert real.m.events == fast.m.events
        assert real.m.reservations == fast.m.reservations
        hit = clone_prepared(checkpoint, checkpoint.m.banks)
        hit.m.arm((0, 0x80))
        hit.hooks = accelerated_hooks(hit, cache)
        assert hit.request(raw, BODY) == actual
        assert hit.m.banks == real.m.banks and hit.m.events == real.m.events
        # A different torn target has the same journal input. The memoized JE
        # call must preserve its caller's different pointers and CRC context.
        changed = list(map(bytearray, checkpoint.m.banks))
        changed[0][:117] = BODY[:117]
        slow_partial = clone_prepared(checkpoint, changed)
        fast_partial = clone_prepared(checkpoint, changed)
        for item in (slow_partial, fast_partial):
            item.m.arm((0, 0x80))
        fast_partial.hooks = accelerated_hooks(fast_partial, cache)
        partial_frame = frame(preimage=slow_partial.sector(0, 0x80))
        assert slow_partial.request(partial_frame, BODY) == fast_partial.request(partial_frame, BODY)
        assert slow_partial.m.banks == fast_partial.m.banks
        assert slow_partial.m.events == fast_partial.m.events
        passed(cpu, 'loop-summary-differential-' + scenario,
               equal_mutation_events=len(real.m.events), full_linked_execution=True,
               exact_checkpoint_registers_stack_RAM_and_independent_memory_checked=True,
               journal_cache_hit_and_different_torn_target_checked=True)


def interruption_fixtures():
    return (('append', [(0xc000, base.record())]),
            ('rollover', [(0xc000 + n * 256, base.record(n + 1)) for n in range(15)]
             + [(0xd000, base.record(0))]))


def interruption_tests(build, cpu, passed):
    validate_acceleration(build, cpu, passed)
    for scenario, recs in interruption_fixtures():
        prepared = patterned_machine(build, cpu, rows=recs)
        install_protected_monitor_fixtures(prepared)
        original = tuple(map(bytes, prepared.m.banks))
        reference = clone_prepared(prepared, original)
        reference.m.arm((0, 0x80))
        reference.hooks = accelerated_hooks(reference)
        assert b'OK' in reference.request(frame(preimage=reference.sector(0, 0x80)), BODY)
        trace = reference.m.events
        state = list(map(bytearray, original))
        boots = set()
        retries = 0
        refusals = 0
        refusal_prefixes = []
        journal_cache = {}
        for cut, (kind, bank, address, value) in enumerate(trace, 1):
            offset = address - 0x8000
            if kind == 'erase':
                state[bank][offset:offset + 4096] = b'\xff' * 4096
            else:
                state[bank][offset] = value
            # The identical F/MON/journal state needs one actual scanner call.
            # All later target-only prefixes have exactly the same F inputs.
            journal = bytes(state[3][0x4000:0x6000])
            journal_hash = sha(journal)
            retry = clone_prepared(prepared, state)
            retry.m.arm((0, 0x80))
            retry.m.assert_preserved()
            assert state[3][0x2000:0x4000] == original[3][0x2000:0x4000]
            assert state[3][0x7000:0x8000] == original[3][0x7000:0x8000]
            if journal_hash not in boots:
                assert retry.call(retry.b['BOOT_READ_RECORD']), (cpu, scenario, cut)
                assert retry.m.ram[0x6707] == ord('S')
                assert not retry.m.events
                boots.add(journal_hash)
                # Restore the command checkpoint after the independent call.
                retry = clone_prepared(prepared, state)
                retry.m.arm((0, 0x80))
            retry.hooks = accelerated_hooks(retry, journal_cache)
            retry_image = tuple(map(bytes, retry.m.banks))
            out = retry.request(frame(preimage=retry.sector(0, 0x80)), BODY)
            if b'OK' in out:
                assert retry.sector(0, 0x80) == BODY, (cpu, scenario, cut)
                retries += 1
            else:
                assert b'REFUSED: durable wear reservation' in out, (cpu, scenario, cut, out)
                assert not retry.m.events
                assert tuple(map(bytes, retry.m.banks)) == retry_image
                refusals += 1
                refusal_prefixes.append(cut)
            retry.m.assert_preserved()
            assert latest_record(retry.m.banks) is not None
            if cut % 1000 == 0:
                print('PROGRESS', cpu, scenario, cut, 'of', len(trace), flush=True)
        assert retries + refusals == len(trace)
        if scenario == 'append':
            assert refusals == 0
        passed(cpu, 'every-mutation-prefix-reboot-and-retry-' + scenario,
               prefixes=len(trace), successful_retries=retries,
               safe_reservation_refusals=refusals, safe_refusal_prefixes=refusal_prefixes,
               distinct_journal_states_boot_scanned=len(boots),
               target_may_be_torn=True, protected_F_MON_journal_preserved=True,
               retry_loop_summaries_validated_against_linked_execution=True,
               distinct_journal_retry_paths_executed=len(journal_cache),
               trace_sha256=sha(json.dumps(trace, separators=(',', ':')).encode()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--build', required=True, type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--cpu', choices=('65c02', '65c816-e'))
    mode.add_argument('--merge', action='store_true', help='Merge two current, hash-identical CPU shard receipts')
    args = p.parse_args()
    build = args.build.resolve()
    report = json.loads((build / 'prototype-report.json').read_text())
    base.GENERATION = report['experimental_generation']
    started = datetime.now(timezone.utc).isoformat()
    start_clock = time.monotonic()
    bindings = dict(component_hashes={p.name: sha(p.read_bytes()) for p in (build / 'payload').iterdir()
                                      if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')},
                    symbols_sha256=sha((build / 'symbols.json').read_bytes()),
                    prototype_report_sha256=sha((build / 'prototype-report.json').read_bytes()),
                    test_source_sha256=sha(Path(__file__).read_bytes()))
    failed_log = build / 'opaque-installer-test-failure-816-clone.log'
    failed_checker = build / 'test_opaque_installer_before_clone_fix.py'
    prior_attempts = []
    if failed_log.exists() and failed_checker.exists():
        prior_attempts.append(dict(status='failed', hardware=False,
                                   log=str(failed_log), log_sha256=sha(failed_log.read_bytes()),
                                   checker=str(failed_checker), checker_sha256=sha(failed_checker.read_bytes()),
                                   case='65c816-e loop-summary-differential-append',
                                   root_cause='Harness clone passed pc to py65816 constructor, which ignores it and loads FFFC. '
                                              'Explicit post-construction checkpoint register restoration fixes this. '
                                              'All groups were then executed afresh in the hash-bound CPU shards.'))

    def receipt(cases, status='passed', **extra):
        return dict(passed=status == 'passed', status=status, checks=len(cases),
                    failures=int(status == 'failed'), hardware=False, serial_access=False,
                    device_or_network_attempts=base.ATTEMPTS, selected_source_unchanged=status == 'passed',
                    allowed_targets_per_cpu=len(ALLOWED),
                    mutation_prefixes=sum(r.get('prefixes', 0) for r in cases),
                    successful_retries=sum(r.get('successful_retries', 0) for r in cases),
                    safe_reservation_refusals=sum(r.get('safe_reservation_refusals', 0) for r in cases),
                    retry_method='Every prefix is retried through linked framing, validation and control flow. '
                                 'Bulk loops are differentially checked against full linked executions; '
                                 'each distinct journal input executes the linked writer, with identical '
                                 'journal inputs memoized. Target program uses the same verified NOR trace.',
                    started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                    elapsed_seconds=round(time.monotonic() - start_clock, 3),
                    prior_attempts=prior_attempts, cases=cases, **bindings, **extra)

    def assert_bindings():
        assert sha(Path(__file__).read_bytes()) == bindings['test_source_sha256'], 'Checker changed during testing'
        assert sha((build / 'symbols.json').read_bytes()) == bindings['symbols_sha256']
        assert sha((build / 'prototype-report.json').read_bytes()) == bindings['prototype_report_sha256']
        for name, digest in bindings['component_hashes'].items():
            assert sha((build / 'payload' / name).read_bytes()) == digest
        assert all(sha((ROOT / name).read_bytes()) == digest
                   for name, digest in report['selected_source_hashes'].items())

    if args.merge:
        shards, combined = {}, []
        for cpu in ('65c02', '65c816-e'):
            path = build / f'opaque-installer-cpu-tests-{cpu}.json'
            shard = json.loads(path.read_text())
            assert shard['passed'] and shard['checks'] == 60 and shard['failures'] == 0
            assert len(shard['cases']) == 60 and all(r['passed'] and r['cpu'] == cpu for r in shard['cases'])
            assert all(shard[key] == value for key, value in bindings.items()), 'Shard uses different source/components'
            combined.extend(shard['cases'])
            shards[cpu] = dict(report=str(path), sha256=sha(path.read_bytes()),
                               started_utc=shard['started_utc'], finished_utc=shard['finished_utc'],
                               elapsed_seconds=shard['elapsed_seconds'])
        assert_bindings()
        assert len({(r['cpu'], r['case']) for r in combined}) == 120
        final = receipt(combined, shards=shards)
        final['started_utc'] = min(s['started_utc'] for s in shards.values())
        final['elapsed_seconds'] = round((datetime.now(timezone.utc)
                                           - datetime.fromisoformat(final['started_utc'])).total_seconds(), 3)
        base.save(build / 'opaque-installer-cpu-tests.json', final)
        print('PASS total', len(combined), flush=True)
        return

    rows = []
    cpus = (args.cpu,) if args.cpu else ('65c02', '65c816-e')
    suffix = '-' + args.cpu if args.cpu else ''
    progress_path = build / f'opaque-installer-cpu-progress{suffix}.json'

    def passed(cpu, case, **details):
        rows.append(dict(cpu=cpu, case=case, passed=True, **details))
        print('PASS', cpu, case, flush=True)
        base.save(progress_path, receipt(rows, status='running'))

    try:
        for cpu in cpus:
            h = patterned_machine(build, cpu, via_f=True)
            assert not h.m.events
            passed(cpu, 'F-load-run-with-both-MON-slots-absent',
                   bytes=(build / 'payload/ram-installer-offline.bin').stat().st_size)
            protocol_tests(build, cpu, passed)
            interruption_tests(build, cpu, passed)
        assert_bindings()
        assert len(rows) == 60 * len(cpus)
    except Exception as error:
        base.save(progress_path, receipt(rows, status='failed', error=repr(error)))
        raise
    output = receipt(rows)
    base.save(build / f'opaque-installer-cpu-tests{suffix}.json', output)
    base.save(progress_path, output)
    print('PASS total', len(rows), flush=True)


if __name__ == '__main__':
    main()
