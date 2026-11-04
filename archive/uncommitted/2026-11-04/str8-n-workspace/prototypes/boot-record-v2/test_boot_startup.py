"""Offline linked-CPU qualification of USB wait, input drain, and countdown.

Every measured phase executes its actual instructions, including both console
paths and the ACIA transmit delay. Checkpoint copies only avoid repeating an
already measured phase for the independent post-drain input matrix.
"""
import argparse
from collections import deque
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('startup_countdown_model', HERE / 'test_boot_countdown.py')
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)
core = cd.core
CPU_HZ = cd.CPU_HZ
TIMING_CORRECTIONS = {0x80: 1, 0xce: 3}


def timed_step(cpu, opcode):
    """Correct two installed emulator cycle tables without changing semantics.

    BRA is three cycles (+one on an emulation page crossing); absolute DEC
    is six cycles for these eight-bit modes. Both installed libraries report
    two and three respectively. The actual opcode still executes normally.
    """
    cpu.step()
    correction = TIMING_CORRECTIONS.get(opcode, 0)
    cpu.processorCycles += correction
    return correction


def check_instruction_timing(cpu_type):
    rows = []
    for opcode, pc, program, expected in (
            (0x80, 0x1000, [0x80, 0], 3),
            (0x80, 0x10fd, [0x80, 1], 4),
            (0xce, 0x1000, [0xce, 0, 0x70], 6)):
        memory = [0] * 65536
        memory[pc:pc + len(program)] = program
        memory[0x7000] = 9
        cpu = cpu_type(memory=memory, pc=pc)
        cpu.pc = pc  # py65816's constructor always applies its reset vector.
        begin = cpu.processorCycles
        adjustment = timed_step(cpu, opcode)
        elapsed = cpu.processorCycles - begin
        assert elapsed == expected, (opcode, pc, elapsed, expected)
        if opcode == 0xce:
            assert memory[0x7000] == 8
        else:
            assert cpu.pc == pc + 2 + program[1]
        rows.append(dict(opcode=opcode, pc=pc, installed_cycles=elapsed - adjustment,
                         correction_cycles=adjustment, corrected_cycles=elapsed))
    return rows


class StartupMemory(cd.ReadOnlyMemory):
    def __init__(self, banks, dual=True):
        super().__init__(banks, dual)
        self.input_reads = []
        self.software_changes = []

    def __getitem__(self, address):
        if address in (0x7fe0, 0x7fe1, 0x7f80, 0x7f81) and self.cpu is not None:
            self.input_reads.append((self.cpu.processorCycles, address))
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if address in (0xf9, 0xfd, 0xfa, 0xf8, 0xf1, 0x7c2b, 0x7c2c, 0x7c2d):
            self.software_changes.append((self.cpu.processorCycles, address, self.ram[address], value & 255))
        super().__setitem__(address, value)


class StartupMachine(cd.CountdownMachine):
    def __init__(self, build, cpu, target='0', monitors=False):
        super().__init__(build, cpu, target, monitors)
        old = self.m
        memory = StartupMemory(old.banks, self.dual)
        memory.ram[:] = old.ram
        memory.bank = old.bank
        memory.cpu = self.c
        self.m = self.c.memory = memory
        self.timing_correction_cycles = 0

    def run(self, stop, limit=12_000_000):
        if not isinstance(self.m, StartupMemory):
            return cd.CountdownMachine.run(self, stop, limit)
        for _ in range(limit):
            if stop():
                return
            self.steps += 1
            opcode = self.m[self.c.pc]
            assert not (self.name == '65c02' and opcode & 15 == 15)
            self.timing_correction_cycles += timed_step(self.c, opcode)
        raise AssertionError(('timeout', self.name, hex(self.c.pc), bytes(self.m.tx[-160:])))

    def preserved(self):
        # Input arriving during the deliberate silent interval can overrun a
        # one-byte ACIA latch. Discarding it is intentional; model that count
        # explicitly rather than requiring input preservation during startup.
        assert self.application == bytes(self.m.ram[0x0200:0x6500])
        assert self.flash == tuple(map(bytes, self.m.banks))
        assert not self.m.events


def checkpoint(source):
    """Copy the exact installed CPU state, stack, ABI RAM and input model."""
    h = object.__new__(StartupMachine)
    h.__dict__ = dict(source.__dict__)
    memory = StartupMemory(source.m.banks, source.dual)
    # Constructors read FFFC; do that before copying pending timed arrivals.
    cpu = type(source.c)(memory=memory, pc=source.c.pc)
    for name, value in source.m.__dict__.items():
        if name in ('cpu', 'banks', 'ram'):
            continue
        if isinstance(value, bytearray):
            value = bytearray(value)
        elif isinstance(value, deque):
            value = deque(value)
        elif isinstance(value, list):
            value = list(value)
        elif isinstance(value, set):
            value = set(value)
        setattr(memory, name, value)
    memory.ram[:] = source.m.ram
    for name, value in source.c.__dict__.items():
        if name != 'memory':
            setattr(cpu, name, value)
    memory.cpu = cpu
    h.m, h.c = memory, cpu
    assert h.c.pc == source.c.pc and h.c.memory is h.m and h.m.cpu is h.c
    assert h.c is not source.c and h.m is not source.m
    assert h.m.ram == source.m.ram and h.m.ram[0x100:0x200] == source.m.ram[0x100:0x200]
    assert {k: v for k, v in h.c.__dict__.items() if k != 'memory'} == {
        k: v for k, v in source.c.__dict__.items() if k != 'memory'}
    return h


def clear_input(h):
    h.m.rx.clear()
    h.m.acia_rx.clear()
    h.m.acia_wire.clear()
    h.m.acia_latch = None
    h.m.acia_error = 0
    h.m.arrivals.clear()


def seed_software(h):
    for address, value in ((0xf9, 64), (0xfd, 13), (0xfa, 77), (0xf8, 1), (0xf1, 1),
                           (0x7c29, 2), (0x7c2a, 2), (0x7c2b, 2), (0x7c2d, 3),
                           (0x7c2f, 3), (0x7c78, 1)):
        h.m.ram[address] = value
    h.m.ram[0x7d40:0x7d80] = (b'\r\nSAB0123\0\xff' * 7)[:64]


def queue_flags_clear(h):
    assert all(h.m.ram[address] == 0 for address in
               (0xf9, 0xfd, 0xfa, 0xf8, 0xf1, 0x7c29, 0x7c2b, 0x7c2d, 0x7c2f))


def consuming_message(h):
    h.run(lambda: h.c.pc == h.b['BOOT_DRAIN_BEGIN'])
    assert bytes(h.m.tx) == b'Consuming input\r\n'
    assert bytes(h.m.acia_tx) == b'Consuming input\r\n'
    queue_flags_clear(h)
    assert h.m.ram[0x7d02] == 3


def drain(h):
    assert h.c.pc == h.b['BOOT_DRAIN_BEGIN']
    begin = h.c.processorCycles
    adjustments = h.timing_correction_cycles
    counts = len(h.m.consumed)
    h.run(lambda: h.c.pc == h.b['BOOT_DRAIN_DONE'])
    elapsed = h.c.processorCycles - begin
    assert elapsed == 8_000_495, (h.name, 'drain cycle budget', elapsed)
    h.preserved()
    h.last_drain_timing = dict(corrected_cycles=elapsed,
                              installed_uncorrected_cycles=elapsed - h.timing_correction_cycles + adjustments,
                              local_cycle_corrections=h.timing_correction_cycles - adjustments)
    return elapsed, h.m.consumed[counts:]


def active(h):
    origin = h.window()
    queue_flags_clear(h)
    assert h.m.ram[h.b['RL_VALID']] == 0
    assert h.m.ram[0xec] == 0
    h.preserved()
    return origin


def startup_tests(build, cpu, passed):
    h = StartupMachine(build, cpu)
    instruction_timing = check_instruction_timing(type(h.c))
    seed_software(h)
    software_before = bytes(h.m.ram[0x7d40:0x7d80])
    initial_flags = bytes(h.m.ram[0xf8:0x100]) + bytes(h.m.ram[0x7c29:0x7c30])
    initial_input = (b'\r\nSAB0123\0\xff' * 44)[:480]
    h.m.rx.extend(initial_input)
    h.m.acia_rx.extend(b'\r')
    begin = h.c.processorCycles
    h.m.schedule(1, begin + CPU_HZ, b'SAB0\r\n' * 5 + b'XX')
    h.m.schedule(2, begin + CPU_HZ, b'\nSAB0123\r\n')
    h.run(lambda: h.c.pc == h.b['BOOT_USB_WAIT_DONE'])
    usb_cycles = h.c.processorCycles - begin
    assert 23_980_000 <= usb_cycles <= 24_020_000, (cpu, 'USB quiet delay', usb_cycles)
    assert not h.m.tx and not h.m.acia_tx and not h.m.consumed
    assert not h.m.input_reads, 'Silent wait accessed hardware input registers'
    assert len(h.m.rx) == 512 and bytes(h.m.acia_rx) == b'\r'
    assert software_before == bytes(h.m.ram[0x7d40:0x7d80])
    assert initial_flags == bytes(h.m.ram[0xf8:0x100]) + bytes(h.m.ram[0x7c29:0x7c30])
    h.preserved()
    usb_done = checkpoint(h)
    passed(cpu, 'three-second-silent-USB-delay-never-reads-consumes-or-selects-input',
           cycles=usb_cycles, ms_at_8MHz=usb_cycles / 8000,
           instruction_cycle_regression=instruction_timing,
           retained_FT_bytes=512, retained_software_bytes=64,
           both_console_outputs_empty=True, stale_binary_cancel_and_queue_flags_preserved_until_drain=True)

    consuming_message(h)
    drain_begin = checkpoint(h)
    elapsed, consumed = drain(h)
    ft = [cycle for cycle, port, _ in consumed if port == 1]
    assert len(ft) == 512 and not h.m.rx
    assert not h.m.acia_rx and h.m.acia_latch is None and not h.m.acia_wire
    assert h.m.acia_error == 0
    assert ft[-1] - ft[0] < 160_000, '512-byte FIFO was not drained promptly'
    origin = active(h)
    ready = checkpoint(h)
    assert h.dispatch() == 0
    countdown = cd.assert_countdown(h)
    passed(cpu, 'fixed-one-second-drain-discards-stale-FIFO-and-software-then-three-to-zero',
           drain_cycles=elapsed, drain_ms_at_8MHz=elapsed / 8000,
           drain_timing_model=h.last_drain_timing,
           FIFO_bytes=512, FIFO_clear_cycles=ft[-1] - ft[0],
           consumed_ACIA_bytes=sum(port == 2 for _, port, _ in consumed),
           intentional_pre_wait_ACIA_overruns=h.m.acia_overruns,
           countdown=countdown, total_sequence_cycles=h.c.processorCycles - begin,
           countdown_to_default_cycles=h.c.processorCycles - origin,
           binary_and_run_permission_cleared=True)

    for scenario in ('idle', '64KiB-FT-backlog', 'continuous-both-ready', 'paced-ACIA-and-FIFO', 'FT-output-blocked'):
        item = checkpoint(drain_begin)
        clear_input(item)
        item.m.consumed.clear()
        at = item.c.processorCycles
        if scenario == '64KiB-FT-backlog':
            item.m.rx.extend(bytes(range(256)) * 256)
        elif scenario == 'continuous-both-ready':
            item.m.rx.extend(b'S' * 65536)
            item.m.acia_rx.extend(b'B' * 65536)
        elif scenario == 'paced-ACIA-and-FIFO':
            item.m.rx.extend(bytes(range(256)) * 2)
            item.m.schedule(2, at + 100, bytes(range(256)) * 7 + bytes(range(128)), spacing=4167)
        elif scenario == 'FT-output-blocked':
            item = checkpoint(usb_done)
            clear_input(item)
            item.m.ft_tx_blocked = True
            item.run(lambda: item.c.pc == item.b['BOOT_DRAIN_BEGIN'])
            assert not item.m.tx and bytes(item.m.acia_tx) == b'Consuming input\r\n'
            assert item.m.ram[0x7c2e] & 1
            queue_flags_clear(item)
        if scenario == 'idle':
            # Prove the complete summary with deliberately non-default C/V:
            # BIT samples V from VIA port bit6, while the drain preserves C.
            item.c.p = (item.c.p | 1) & ~0x40
            item.m.ram[0x7fe0] |= 0x40
            empty_before_p = item.c.p
            empty_expected_p = (empty_before_p & ~0xc2) | 2 | (item.m[0x7fe0] & 0x40)
        duration, discarded = drain(item)
        ft_count = sum(port == 1 for _, port, _ in discarded)
        acia_count = sum(port == 2 for _, port, _ in discarded)
        if scenario == 'idle':
            assert (item.c.a, item.c.x, item.c.y, item.c.p & 0x82,
                    item.m.ram[item.b['BR_TICKS']]) == (0, 0, 0, 2, 0)
            assert item.c.p == empty_expected_p, (cpu, item.c.p, empty_expected_p)
        elif scenario == '64KiB-FT-backlog':
            assert ft_count == 32256 and len(item.m.rx) == 33280
        elif scenario == 'continuous-both-ready':
            assert ft_count == acia_count == 32256
            assert len(item.m.rx) == len(item.m.acia_rx) == 33280
        elif scenario == 'paced-ACIA-and-FIFO':
            assert ft_count == 512 and acia_count == 1920
            assert not item.m.rx and not item.m.acia_wire and item.m.acia_latch is None
            assert not item.m.arrivals
        passed(cpu, 'bounded-drain-' + scenario, cycles=duration,
               timing_model=item.last_drain_timing,
               discarded_FT_bytes=ft_count, discarded_ACIA_bytes=acia_count,
               remaining_FT_bytes=len(item.m.rx), remaining_ACIA_model_bytes=len(item.m.acia_rx),
               empty_full_P_checked=scenario == 'idle',
               oversized_backlog_not_claimed_to_be_fully_cleared=True,
               no_quiet_gap_required=True)

    # These forks preserve exact CPU/stack/ABI state after the measured drain.
    # Every key and subsequent instruction still executes normally.
    for port in (1, 2):
        for byte in b'SsAaBb0123\x03':
            key = checkpoint(ready)
            if byte in b'AaBb':
                for sector in (0xa0, 0xb0):
                    offset = (sector - 0x80) << 8
                    key.m.banks[3][offset:offset + 4096] = (build / f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
                key.flash = tuple(map(bytes, key.m.banks))
            origin = key.c.processorCycles
            key.m.schedule(port, origin + 160_000, bytes([byte]))
            seen = len(key.m.consumed)
            result = key.dispatch()
            expected = ('recovery' if byte in b'Ss\x03' else
                        (0xa0 if byte in b'Aa' else 0xb0) if byte in b'AaBb' else byte - ord('0'))
            assert result == expected
            event = key.m.consumed[seen:]
            assert len(event) == 1 and event[0][1:] == (port, byte)
            latency = event[0][0] - origin - 160_000
            assert 0 <= latency <= 90_000
            key.preserved()
            passed(cpu, f'post-drain-key-{byte:02x}-port-{port}', result=result,
                   poll_latency_cycles=latency, exact_measured_phase_checkpoint=True)

    permission = checkpoint(ready)
    permission.m.rx.extend(b'S')
    permission.run(lambda: bytes(permission.m.tx).endswith(b'REC> '))
    response = permission.command(b'R\r')
    assert b'REFUSED' in response and permission.m.ram[permission.b['RL_VALID']] == 0
    permission.preserved()
    passed(cpu, 'post-drain-recovery-refuses-stale-RAM-run-permission')

    j3_test(build, cpu, ready, usb_cycles, passed)


def j3_test(build, cpu, ready, usb_cycles, passed):
    h = checkpoint(ready)
    for sector in (0xa0, 0xb0):
        offset = (sector - 0x80) << 8
        h.m.banks[3][offset:offset + 4096] = (build / f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
    h.flash = tuple(map(bytes, h.m.banks))
    h.m.acia_rx.extend(b'B')
    h.run(lambda: bytes(h.m.acia_tx).endswith(b'B3> '))
    h.run(lambda: h.c.pc == h.w['V2W_GETC'])
    h.m.ram[h.b['RL_VALID']] = 1
    h.m.acia_rx.extend(b'J3\r\n')
    h.run(lambda: h.c.pc == h.b['BOOT_START_CHOICES'])
    beginning = h.c.processorCycles
    outputs = (len(h.m.tx), len(h.m.acia_tx))
    count = len(h.m.consumed)
    h.m.schedule(2, beginning + CPU_HZ, b'\nS\rA\r0\r')
    h.run(lambda: h.c.pc == h.b['BOOT_USB_WAIT_DONE'])
    assert h.c.processorCycles - beginning == usb_cycles
    assert len(h.m.consumed) == count
    assert (len(h.m.tx), len(h.m.acia_tx)) == outputs
    h.run(lambda: h.c.pc == h.b['BOOT_DRAIN_BEGIN'])
    h.m.schedule(1, h.c.processorCycles + 1_600_000, b'B\r\n')
    h.m.schedule(2, h.c.processorCycles + 7_200_000, b'\r\n')
    duration, discarded = drain(h)
    assert duration == 8_000_495 and discarded
    active(h)
    assert not h.m.rx and not h.m.acia_rx and not h.m.acia_wire and h.m.acia_latch is None
    h.m.acia_rx.extend(b'S')
    h.run(lambda: bytes(h.m.acia_tx).endswith(b'REC> '))
    assert h.m.ram[h.b['RL_VALID']] == 0
    h.preserved()
    passed(cpu, 'actual-MON-B-ACIA-J3-CRLF-late-bytes-drained-then-fresh-S',
           USB_wait_cycles=usb_cycles, drain_cycles=duration,
           stale_input_bytes_consumed_during_drain=len(discarded),
           no_input_or_output_during_USB_wait=True, new_S_reaches_recovery=True,
           run_permission_cleared=True)


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
        startup_tests(build, cpu, passed)
    report = dict(passed=True, checks=len(cases), cases=cases, hardware=False,
                  serial_access=False, device_or_network_attempts=core.ATTEMPTS,
                  timing_model='Exact linked CPU/register model at nominal8MHz; no electrical timing claim',
                  local_cycle_corrections={'BRA_80': '+1: installed2 to ISA3 (page-cross extra retained)',
                                           'DEC_absolute_CE': '+3: installed3 to ISA6 in eight-bit modes'},
                  timing_primary_sources=[
                      dict(url='https://www.westerndesigncenter.com/wdc/documentation/w65c02s.pdf',
                           location='p20 Table4-1: absolute4 +RMW2; relative2 +taken1'),
                      dict(url='https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf',
                           location='p36 Table5-7 absolute RMW6 at M8; p41 relative and p43 notes5/6')],
                  prior_model_attempt=dict(
                      result='Failed exact cycle assertion before local ISA corrections; firmware unchanged',
                      seeded_drain_installed_cycles=7_999_603,
                      BRA_reads=514, absolute_DEC_executions=126,
                      correction_cycles=514 + 126 * 3,
                      log_sha256=core.sha((build / 'boot-startup-cycle-mismatch.log').read_bytes())),
                  CPU_Hz=CPU_HZ, elapsed_seconds=round(time.monotonic() - started, 3),
                  component_hashes={p.name: core.sha(p.read_bytes()) for p in (build / 'payload').iterdir()
                                    if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')},
                  symbols_sha256=core.sha((build / 'symbols.json').read_bytes()),
                  prototype_report_sha256=core.sha((build / 'prototype-report.json').read_bytes()),
                  countdown_model_sha256=core.sha((HERE / 'test_boot_countdown.py').read_bytes()),
                  checker_sha256=core.sha(Path(__file__).read_bytes()))
    core.save(build / 'boot-startup-cpu-tests.json', report)
    print('PASS total', len(cases), flush=True)


if __name__ == '__main__':
    main()
