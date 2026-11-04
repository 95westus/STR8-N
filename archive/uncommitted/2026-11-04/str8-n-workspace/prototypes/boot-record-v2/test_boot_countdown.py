"""Instruction/cycle and dual-console checks of the linked F countdown.

No board or serial access. Timing is the CPU/register model at nominal8MHz;
the tests do not claim electrical, oscillator, baud, or physical timing proof.
"""
import argparse
from collections import deque
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('countdown_core_tests', HERE / 'test.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
CPU_HZ = 8_000_000


class ReadOnlyMemory(core.Memory):
    def __init__(self, banks, dual=True):
        super().__init__(banks, dual)
        self.arrivals = deque()
        self.delivered = []
        self.ft_writes = []
        self.consumed = []

    def schedule(self, port, cycle, data, spacing=4167):
        events = list(self.arrivals)
        events.extend((cycle + n * spacing, port, byte) for n, byte in enumerate(data))
        self.arrivals = deque(sorted(events))

    def __getitem__(self, address):
        while self.arrivals and self.cpu.processorCycles >= self.arrivals[0][0]:
            cycle, port, byte = self.arrivals.popleft()
            if port == 1:
                self.rx.append(byte)
            else:
                self.acia_wire.append((cycle, byte, 0))
            self.delivered.append((cycle, port, byte))
        pending = address == 0x7f80 and (self.acia_latch is not None or bool(self.acia_rx))
        value = super().__getitem__(address)
        if pending:
            self.consumed.append((self.cpu.processorCycles, 2, value))
        return value

    def __setitem__(self, address, value):
        assert address < 0x8000, ('Unexpected flash write', hex(address), value)
        assert not 0x0200 <= address < 0x6500, ('Application RAM write', hex(address), value)
        before = len(self.tx)
        rx_before = len(self.rx)
        rx_byte = self.rx[0] if self.rx else None
        super().__setitem__(address, value)
        if len(self.tx) != before:
            self.ft_writes.append((self.cpu.processorCycles, self.tx[-1]))
        if len(self.rx) < rx_before:
            self.consumed.append((self.cpu.processorCycles, 1, rx_byte))

    def mutated(self, kind, address, value):
        raise AssertionError(('Unexpected flash mutation', kind, self.bank, hex(address), value))


class CountdownMachine(core.Machine):
    def __init__(self, build, cpu, target='S', monitors=False):
        super().__init__(build, cpu, [(0xc000, core.record(target=target))], opaque=not monitors)
        old = self.m
        memory = ReadOnlyMemory(old.banks, self.dual)
        memory.ram[:] = old.ram
        memory.bank = old.bank
        self.m = self.c.memory = memory
        memory.cpu = self.c
        self.application = bytes(memory.ram[0x0200:0x6500])
        self.flash = tuple(map(bytes, memory.banks))
        self.timer_start = None

    def run(self, stop, limit=12_000_000):
        # During super().__init__, retain its proven reset setup until choices.
        if not isinstance(self.m, ReadOnlyMemory):
            return core.Machine.run(self, stop, limit)
        for _ in range(limit):
            if stop():
                return
            self.steps += 1
            opcode = self.m[self.c.pc]
            assert not (self.name == '65c02' and opcode & 15 == 15), (
                'Timing path needs an unsupported py65 bit-branch opcode', hex(self.c.pc), opcode)
            self.c.step()
        raise AssertionError(('timeout', self.name, hex(self.c.pc), bytes(self.m.tx[-160:])))

    def preserved(self):
        assert self.application == bytes(self.m.ram[0x0200:0x6500])
        assert self.flash == tuple(map(bytes, self.m.banks))
        assert not self.m.events and self.m.acia_overruns == 0

    def writes(self, port):
        return self.m.ft_writes if port == 1 else self.m.acia_writes

    def window(self):
        self.run(lambda: self.c.pc == self.b['BR_COUNTDOWN'])
        assert self.m.ram[self.b['BR_TICKS']] == 3 and self.m.ram[0x7d02] == 3
        self.timer_start = self.c.processorCycles
        return self.timer_start

    def dispatch(self):
        self.run(lambda: self.c.pc in (self.b['BOOT_RECOVERY'], self.b['BOOT_LAUNCH'])
                 or self.c.pc == 0x8000)
        if self.c.pc == self.b['BOOT_RECOVERY']:
            return 'recovery'
        if self.c.pc == self.b['BOOT_LAUNCH']:
            return chr(self.m.ram[self.b['BOOT_ACTIVE']]) if self.m.ram[self.b['BOOT_ACTIVE']] in (ord('A'), ord('B')) else self.m.ram[self.b['BOOT_ACTIVE']]
        return self.m.bank

    def output(self, port):
        return bytes(byte for cycle, byte in self.writes(port) if cycle >= self.timer_start)


def assert_countdown(h, expected='3 2 1 0\r\n'):
    timings = {}
    for port in (1, 2):
        assert h.output(port) == expected.encode(), (h.name, port, h.output(port))
        digits = [(cycle, byte) for cycle, byte in h.writes(port)
                  if cycle >= h.timer_start and byte in b'3210']
        assert bytes(byte for _, byte in digits) == b'3210'
        offsets = [cycle - digits[0][0] for cycle, _ in digits]
        # Count both actual console paths, including the timed ACIA PUTC loop.
        # ~0.2% admits instruction/loop quantization while detecting any fourth
        # second, missing wait, or per-invalid-input restart.
        for index, offset in enumerate(offsets):
            assert abs(offset - index * CPU_HZ) <= 48_000, (h.name, port, offsets)
        timings[str(port)] = dict(digit_offsets_cycles=offsets,
                                  zero_after_three_ms=offsets[-1] / 8000)
    assert 23_952_000 <= h.c.processorCycles - h.timer_start <= 24_064_000
    h.preserved()
    return timings


def countdown_tests(build, cpu, passed):
    h = CountdownMachine(build, cpu, target='0')
    start = h.window()
    assert h.dispatch() == 0
    timings = assert_countdown(h)
    zero_cycle = next(cycle for cycle, byte in h.m.ft_writes if cycle >= start and byte == ord('0'))
    zero_offset = zero_cycle - start
    baseline_total = h.c.processorCycles - start
    passed(cpu, 'no-input-three-to-zero-and-immediate-saved-default',
           consoles=timings, total_cycles=baseline_total,
           total_ms_at_8MHz=baseline_total / 8000, saved_default_bank=0,
           accelerated_instructions=False, ACIA_transmit_delay_executed=True,
           flash_and_application_RAM_unchanged=True)

    ignored = CountdownMachine(build, cpu, target='0')
    origin = ignored.window()
    for port, offset, byte in ((1, 1_600_000, 13), (2, 5_600_000, 10),
                               (1, 8_800_000, 255), (2, 13_600_000, ord('?')),
                               (1, 20_800_000, ord('X')),
                               (2, zero_offset + 1000, 10)):
        ignored.m.schedule(port, origin + offset, bytes([byte]))
    assert ignored.dispatch() == 0
    ignored_timings = assert_countdown(ignored)
    assert len(ignored.m.consumed) == 6
    assert abs((ignored.c.processorCycles - origin) - baseline_total) <= 8_000
    passed(cpu, 'CR-LF-invalid-and-post-zero-LF-do-not-restart-or-extend-deadline',
           ignored_bytes=6, consoles=ignored_timings,
           deadline_delta_cycles=ignored.c.processorCycles - origin - baseline_total)

    for port in (1, 2):
        late = CountdownMachine(build, cpu, target='0')
        origin = late.window()
        late.m.schedule(port, origin + 1_600_000, b'\n')
        key_cycle = origin + 3_600_000
        late.m.schedule(port, key_cycle, b'S')
        assert late.dispatch() == 'recovery'
        assert [byte for _, _, byte in late.m.consumed] == [10, ord('S')]
        latency = late.m.consumed[-1][0] - key_cycle
        assert 0 <= latency <= 90_000
        late.preserved()
        passed(cpu, f'late-LF-ignored-then-S-port-{port}', response_cycles=latency)

        final = CountdownMachine(build, cpu, target='0')
        origin = final.window()
        key_cycle = origin + zero_offset - 1000
        final.m.schedule(port, key_cycle, b'S')
        assert final.dispatch() == 'recovery'
        assert final.m.consumed[-1][2] == ord('S')
        assert 0 <= final.m.consumed[-1][0] - key_cycle <= 90_000
        assert final.output(1).startswith(b'3 2 1 0') and final.output(2).startswith(b'3 2 1 0')
        final.preserved()
        passed(cpu, f'key-in-final-delay-slice-accepted-before-default-port-{port}',
               response_cycles=final.m.consumed[-1][0] - key_cycle)

        for byte in b'SsAaBb0123\x03':
            text = chr(byte) if byte >= 32 else 'CTRL-C'
            mon = byte in b'AaBb'
            key = CountdownMachine(build, cpu, target='0', monitors=mon)
            origin = key.window()
            key_cycle = origin + 160_000
            key.m.schedule(port, key_cycle, bytes([byte]))
            result = key.dispatch()
            expected = ('recovery' if byte in b'Ss\x03' else
                        (0xa0 if byte in b'Aa' else 0xb0) if mon else byte - ord('0'))
            assert result == expected, (cpu, port, byte, result, expected)
            assert len(key.m.consumed) == 1 and key.m.consumed[0][2] == byte
            latency = key.m.consumed[0][0] - key_cycle
            assert 0 <= latency <= 90_000
            key.preserved()
            passed(cpu, f'startup-key-{text}-port-{port}', result=result,
                   input_poll_latency_cycles=latency,
                   dispatch_after_input_cycles=key.c.processorCycles - key_cycle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    manifest = json.loads((build / 'prototype-report.json').read_text())
    core.GENERATION = manifest['experimental_generation']
    assert manifest['dual_console']
    started = time.monotonic()
    cases = []

    def passed(cpu, case, **details):
        cases.append(dict(cpu=cpu, case=case, passed=True, **details))
        print('PASS', cpu, case, flush=True)

    for cpu in ('65c02', '65c816-e'):
        countdown_tests(build, cpu, passed)
    report = dict(passed=True, checks=len(cases), cases=cases, hardware=False,
                  serial_access=False, device_or_network_attempts=core.ATTEMPTS,
                  timing_model='Linked CPU instructions and FT245/ACIA registers; nominal8MHz; no electrical timing claim',
                  CPU_Hz=CPU_HZ, elapsed_seconds=round(time.monotonic() - started, 3),
                  component_hashes={p.name: core.sha(p.read_bytes()) for p in (build / 'payload').iterdir()
                                    if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')},
                  symbols_sha256=core.sha((build / 'symbols.json').read_bytes()),
                  prototype_report_sha256=core.sha((build / 'prototype-report.json').read_bytes()),
                  checker_sha256=core.sha(Path(__file__).read_bytes()))
    core.save(build / 'boot-countdown-cpu-tests.json', report)
    print('PASS total', len(cases), flush=True)


if __name__ == '__main__':
    main()
