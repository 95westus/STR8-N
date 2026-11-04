"""Fresh b07 startup qualification using the frozen b06 instruction tests.

Only the three old WAIT-message assertion constants are adapted in memory. The
frozen source stays unchanged. All timing, mutation guards, checkpoint copies,
input cases, and real CPU instructions retain their original implementation.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import time
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = HERE / 'test_boot_startup.py'
FROZEN_SHA = '1751fa0f0d2263716ba664b15273fa7b74f06c9d7e0779384c0b690cdb0451f0'
WAIT = b'\r\nWAIT...\r\n'
CHOICES = b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
PREFIX = b'Boot : '


class TextAssertions(ast.NodeTransformer):
    def __init__(self):
        self.replacements = 0

    def visit_Constant(self, node):
        if node.value == b'Consuming input\r\n':
            self.replacements += 1
            return ast.copy_location(ast.Constant(value=WAIT), node)
        return node


def load_frozen_suite():
    source = FROZEN.read_bytes()
    import hashlib
    assert hashlib.sha256(source).hexdigest() == FROZEN_SHA
    tree = ast.parse(source, filename=str(FROZEN))
    adapter = TextAssertions()
    tree = adapter.visit(tree)
    assert adapter.replacements == 3
    ast.fix_missing_locations(tree)
    module = types.ModuleType('b07_frozen_startup_suite')
    module.__file__ = str(FROZEN)
    exec(compile(tree, str(FROZEN), 'exec'), module.__dict__)
    return module


m = load_frozen_suite()
core = m.core
original_active = m.active


def active_with_exact_text(h):
    origin = original_active(h)
    for output in (h.m.tx, h.m.acia_tx):
        assert bytes(output).endswith(WAIT + CHOICES + PREFIX), bytes(output[-100:])
    return origin


m.active = active_with_exact_text


def dependencies():
    paths = [Path(__file__), FROZEN, HERE / 'test_boot_countdown.py', HERE / 'test.py',
             ROOT / 'tools/installer/flash_model.py', ROOT / 'tools/test_monitor_size.py',
             ROOT / 'tools/prepare_monitor_size.py',
             ROOT / 'BUILD/v1.30/local/test-deps/py65/devices/mpu65c02.py',
             ROOT / 'BUILD/v1.30/local/test-deps/py65/devices/mpu6502.py',
             ROOT / 'BUILD/test-deps-816/py65816/devices/mpu65c816.py']
    return {str(p.relative_to(ROOT)): core.sha(p.read_bytes()) for p in paths}


def bindings(build, baseline):
    current = json.loads((build / 'symbols.json').read_text())
    previous = json.loads((baseline / 'symbols.json').read_text())
    stable = {}
    for module, symbols in previous.items():
        assert module in current
        # Linked MON symbol tables also import F's end-marker constants.
        ignored = {'BOOT_END', '_END_CODE'}
        for name, address in symbols.items():
            if name not in ignored:
                assert current[module].get(name) == address, (module, name, address, current[module].get(name))
        stable[module] = len(symbols.keys() - ignored)
    components = {p.name: core.sha(p.read_bytes()) for p in (build / 'payload').iterdir()
                  if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')}
    comparisons = {}
    for name, digest in components.items():
        old = baseline / 'payload' / name
        comparisons[name] = dict(b07_sha256=digest,
                                 b06_sha256=core.sha(old.read_bytes()) if old.exists() else None,
                                 identical_to_b06=old.exists() and core.sha(old.read_bytes()) == digest)
    return dict(component_hashes=components,
                symbols_sha256=core.sha((build / 'symbols.json').read_bytes()),
                prototype_report_sha256=core.sha((build / 'prototype-report.json').read_bytes()),
                dependency_hashes=dependencies(), checker_sha256=core.sha(Path(__file__).read_bytes()),
                frozen_base_checker_sha256=FROZEN_SHA, assertion_constant_replacements=3,
                exact_text=dict(wait=list(WAIT), choices=list(CHOICES), prefix=list(PREFIX)),
                b06_private_addresses_preserved=stable,
                b06_symbols_sha256=core.sha((baseline / 'symbols.json').read_bytes()),
                component_comparison=comparisons)


def message_bounds(build, cpu, passed):
    for blocked in (False, True):
        h = m.StartupMachine(build, cpu)
        m.seed_software(h)
        h.c.pc = h.b['BOOT_USB_WAIT_DONE']
        h.m.ft_tx_blocked = blocked
        begin, steps = h.c.processorCycles, h.steps
        h.run(lambda: h.c.pc == h.b['BOOT_DRAIN_BEGIN'])
        elapsed = h.c.processorCycles - begin
        assert elapsed < 1_000_000
        assert bytes(h.m.acia_tx) == WAIT
        assert bytes(h.m.tx) == (b'' if blocked else WAIT)
        m.queue_flags_clear(h)
        h.preserved()
        passed(cpu, 'WAIT-message-FT-blocked' if blocked else 'WAIT-message-both-ports',
               category='message', cycles=elapsed, ms_at_8MHz=elapsed / 8000,
               instructions=h.steps - steps, FT_blocked=blocked,
               scope='Message phase from BOOT_USB_WAIT_DONE; no earlier delay rerun claim')


def timed_wire(build, cpu, passed):
    h = m.StartupMachine(build, cpu, monitors=True)
    h.c.pc = h.b['BR_B']
    h.run(lambda: bytes(h.m.acia_tx).endswith(b'B3> '))
    h.run(lambda: h.c.pc == h.w['V2W_GETC'])
    assert not h.m.acia_rx and h.m.acia_latch is None and not h.m.acia_wire
    h.m.ram[h.b['RL_VALID']] = 1
    command_count = len(h.m.consumed)
    h.m.schedule(2, h.c.processorCycles + 100, b'J3\r\n', spacing=4167)
    h.run(lambda: h.c.pc == h.b['BOOT_START_CHOICES'])
    assert h.m.ram[h.b['RL_VALID']] == 0
    command = h.m.consumed[command_count:]
    command_bytes = bytes(byte for _, port, byte in command)
    assert command_bytes in (b'J3\r', b'J3\r\n')
    assert all(port == 2 for _, port, _ in command)
    assert h.m.acia_overruns == 0 and not h.m.acia_rx
    beginning = h.c.processorCycles
    reads, outputs = len(h.m.input_reads), (len(h.m.tx), len(h.m.acia_tx))
    h.m.schedule(2, beginning + m.CPU_HZ, b'\nS\rA\r0\r', spacing=4167)
    h.run(lambda: h.c.pc == h.b['BOOT_USB_WAIT_DONE'])
    quiet = h.c.processorCycles - beginning
    assert 23_980_000 <= quiet <= 24_020_000
    assert len(h.m.input_reads) == reads
    assert len(h.m.consumed) == command_count + len(command)
    assert (len(h.m.tx), len(h.m.acia_tx)) == outputs
    assert h.m.ram[h.b['RL_VALID']] == 0
    h.run(lambda: h.c.pc == h.b['BOOT_DRAIN_BEGIN'])
    assert bytes(h.m.tx[outputs[0]:]) == bytes(h.m.acia_tx[outputs[1]:]) == WAIT
    duration, discarded = m.drain(h)
    assert bytes(byte for _, port, byte in discarded) == b'\n'
    assert all(port == 2 for _, port, _ in discarded)
    overruns = 4 - len(command) + 7 - 1
    assert h.m.acia_overruns == overruns
    assert not h.m.acia_rx and not h.m.acia_wire and h.m.acia_latch is None and not h.m.arrivals
    m.active(h)
    assert h.m.ram[h.b['RL_VALID']] == 0
    fresh_S = h.c.processorCycles + 100
    h.m.schedule(2, fresh_S, b'S', spacing=4167)
    h.run(lambda: bytes(h.m.acia_tx).endswith(b'REC> '))
    assert h.m.consumed[-1][1:] == (2, ord('S'))
    latency = h.m.consumed[-1][0] - fresh_S
    assert 0 <= latency < 90_000
    assert not h.m.acia_rx and not h.m.acia_wire and h.m.acia_latch is None
    h.preserved()
    passed(cpu, 'paced-ACIA-MON-B-J3-CRLF-late-input-WAIT-new-text-and-fresh-S',
           category='wire', command_consumed_bytes=list(command_bytes),
           ACIA_spacing_cycles=4167, synthetic_ACIA_FIFO_used=False,
           USB_wait_cycles=quiet, drain_cycles=duration, fresh_S_response_cycles=latency,
           intentional_stale_wire_overruns=overruns,
           no_input_reads_or_output_during_USB_wait=True,
           MON_J3_clears_permission_before_F_wrapper=True,
           flash_and_application_RAM_unchanged=True)


def receipt(common, cases, elapsed, **extra):
    return dict(common, passed=True, checks=len(cases), cases=cases,
                hardware=False, serial_access=False, device_or_network_attempts=core.ATTEMPTS,
                CPU_Hz=m.CPU_HZ, elapsed_seconds=round(elapsed, 3),
                timing_model='Real linked opcodes at nominal8MHz with local BRA+1/DECabs+3 corrections; no bus-cycle/electrical claim',
                limitations='64KiB or continuous sender backlog can remain after fixed one-second drain; no quiet-after-deadline guarantee',
                **extra)


def merge(build, common):
    cases, shards = [], []
    for cpu in ('65c02', '65c816-e'):
        path = build / f'boot-startup-b07-{cpu}.json'
        row = json.loads(path.read_text())
        assert row['passed'] and row['checks'] == 34
        assert row['device_or_network_attempts'] == []
        assert all(row[key] == value for key, value in common.items())
        assert all(case['passed'] and case['cpu'] == cpu for case in row['cases'])
        assert len({case['case'] for case in row['cases']}) == 34
        assert [sum(case['category'] == category for case in row['cases'])
                for category in ('main', 'message', 'wire')] == [31, 2, 1]
        cases.extend(row['cases'])
        shards.append(dict(cpu=cpu, path=str(path), sha256=core.sha(path.read_bytes()),
                           elapsed_seconds=row['elapsed_seconds']))
    outputs = {}
    for category, filename in (('main', 'boot-startup-cpu-tests.json'),
                               ('message', 'boot-startup-output-bound.json'),
                               ('wire', 'boot-startup-timed-wire.json')):
        part = [case for case in cases if case['category'] == category]
        result = receipt(common, part, max(item['elapsed_seconds'] for item in shards),
                         source_shards=shards, fresh_b07_execution=True)
        if category == 'wire':
            result['main_report_sha256'] = outputs['boot-startup-cpu-tests.json']
        path = build / filename
        core.save(path, result)
        outputs[filename] = core.sha(path.read_bytes())
    bundle = receipt(common, cases, max(item['elapsed_seconds'] for item in shards),
                     source_shards=shards, receipts=outputs, fresh_b07_execution=True)
    core.save(build / 'boot-startup-b07-qualification.json', bundle)
    print('PASS merged', len(cases), outputs, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'BUILD/pr04-b06-startup-r2')
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'))
    parser.add_argument('--merge', action='store_true')
    args = parser.parse_args()
    assert bool(args.cpu) != args.merge
    build, baseline = args.build.resolve(), args.baseline.resolve()
    manifest = json.loads((build / 'prototype-report.json').read_text())
    assert manifest['dual_console'] and manifest['startup_drain']
    core.GENERATION = manifest['experimental_generation']
    common = bindings(build, baseline)
    if args.merge:
        merge(build, common)
        return
    started, cases = time.monotonic(), []

    def passed(cpu, case, **details):
        category = details.pop('category', 'main')
        cases.append(dict(cpu=cpu, case=case, category=category, passed=True, **details))
        print('PASS', cpu, category, case, flush=True)

    m.startup_tests(build, args.cpu, passed)
    message_bounds(build, args.cpu, passed)
    timed_wire(build, args.cpu, passed)
    assert common == bindings(build, baseline), 'Runtime or checker dependency changed during execution'
    assert len(cases) == 34
    result = receipt(common, cases, time.monotonic() - started, cpu=args.cpu,
                     checkpoint_reuse='Exact CPU/stack/RAM/MMIO copies only after actual measured prefix')
    core.save(build / f'boot-startup-b07-{args.cpu}.json', result)
    print('PASS shard', args.cpu, len(cases), flush=True)


if __name__ == '__main__':
    main()
