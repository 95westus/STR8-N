"""Offline ten-pattern LED-runner admission, safe-stop and drift regressions.

The supplied run directory provides frozen Python modules and scope receipts.
All workload/restore/collector operations below are fakes; no port is opened.
"""
import argparse
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
args, unittest_args = parser.parse_known_args()
RUN = args.run.resolve()
ROOT = Path('C:/SRC/STR8-N')
sys.path.insert(0, str(RUN))
import runner


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


class Schedule(unittest.TestCase):
    epoch = 1792491363.6864507
    interval = 14400

    def test_initial_boundary_uses_original_campaign_epoch(self):
        self.assertEqual(runner.first_drift_after(self.epoch + 1000, self.epoch),
                         self.epoch + self.interval)

    def test_exact_boundary_is_strictly_future(self):
        for multiple in (0, 1, 2, 10):
            with self.subTest(multiple=multiple):
                current = self.epoch + self.interval * multiple
                self.assertEqual(runner.first_drift_after(current, self.epoch),
                                 self.epoch + self.interval * (multiple + 1))

    def test_before_and_after_boundary_do_not_reset_four_hour_clock(self):
        boundary = self.epoch + self.interval * 2
        self.assertEqual(runner.first_drift_after(boundary - .25, self.epoch), boundary)
        self.assertEqual(runner.first_drift_after(boundary + .25, self.epoch),
                         boundary + self.interval)

    def test_late_start_skips_elapsed_boundaries(self):
        start = self.epoch + 7 * self.interval + 123
        due = runner.first_drift_after(start, self.epoch)
        self.assertEqual(due, self.epoch + 8 * self.interval)
        self.assertGreater(due, start)
        self.assertLessEqual(due - start, self.interval)


class Authorization(unittest.TestCase):
    def test_exact_scope_is_accepted(self):
        runner.validate_led_authorization(read(RUN / 'owner-authorization.json'))

    def test_LED_write_permission_cannot_extend_to_control_or_other_IO(self):
        auth = read(RUN / 'owner-authorization.json')
        for field, value in (('LED_allowed_data_address', 0x7FA1),
                             ('LED_CRA_writes', True), ('LED_DDRA_writes', True),
                             ('LED_restore_entry_value', False), ('LED_frames_per_unit', 631),
                             ('LED_patterns', False)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                runner.validate_led_authorization(dict(auth, **{field: value}))

    def test_all_ten_exact_pattern_names_and_count_are_required(self):
        auth = read(RUN / 'owner-authorization.json')
        names = list(runner.LED_PATTERN_NAMES)
        for field, value in (('LED_pattern_count', 3), ('LED_pattern_count', 5),
                             ('LED_pattern_names', names[:5]),
                             ('LED_pattern_names', list(reversed(names))),
                             ('LED_pattern_names', [names[0]] * 10),
                             ('LED_pattern_names', names[:-1] + ['unknown-pattern'])):
            with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                runner.validate_led_authorization(dict(auth, **{field: value}))

    def test_legacy_three_pattern_scope_is_rejected(self):
        auth = read(RUN / 'owner-authorization.json')
        with self.assertRaises(AssertionError):
            runner.validate_led_authorization(dict(auth, LED_pattern_count=3,
                LED_pattern_names=['wigwag', 'gray-code', 'binary-counter'], LED_frames_per_unit=520))

    def test_native_persistent_writes_promotion_and_fixed_duration_are_refused(self):
        auth = read(RUN / 'owner-authorization.json')
        for field, value in (('owner_authorized', False), ('run_until_owner_stop', False),
                             ('hours', 3), ('drift_interval_seconds', 10800),
                             ('promotion_held', False), ('native_applications', True),
                             ('native_debugging', True), ('flash_writes', True),
                             ('clock_set', True), ('trim_changed', True), ('settings_changed', True)):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                runner.validate_led_authorization(dict(auth, **{field: value}))

    def test_nonfinite_campaign_epoch_is_refused(self):
        auth = read(RUN / 'owner-authorization.json')
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                runner.validate_led_authorization(dict(auth, campaign_drift_epoch_unix=value))

    def test_constructor_rejects_changed_module_cases_and_parent_bytes(self):
        for changed in ('led_units.py', 'LED-cases.json', 'broader_runner.py'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
                destination = Path(folder)
                auth = read(RUN / 'owner-authorization.json')
                for name in ('led_units.py', 'LED-cases.json', 'broader_runner.py'):
                    source = RUN / name
                    # An unqualified draft is sufficient to test hash rejection;
                    # the constructor must fail before importing/executing it.
                    if name == 'LED-cases.json' and not source.exists():
                        source = RUN / 'LED-cases-unqualified.json'
                    (destination / name).write_bytes(source.read_bytes())
                for name, key in (('led_units.py', 'LED_module_sha256'),
                                  ('LED-cases.json', 'LED_cases_sha256'),
                                  ('broader_runner.py', 'broader_runner_sha256')):
                    auth[key] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
                (destination / changed).write_bytes((destination / changed).read_bytes() + b' ')
                def parent_init(obj, workspace, run):
                    obj.run, obj.auth = Path(run), auth
                    obj.state = {'boards': {board: {} for board in runner.base.BOARDS}}
                with patch.object(runner.broader.Runner, '__init__', new=parent_init):
                    with self.assertRaises(AssertionError):
                        runner.Runner(ROOT, destination)

    def construct_with_contract(self, *, module_change=None, case_change=None):
        auth = read(RUN / 'owner-authorization.json')
        cases = [dict(seed=seed, pattern_count=10, pattern_names=list(runner.LED_PATTERN_NAMES))
                 for seed in runner.LED_SEEDS]
        module = SimpleNamespace(FRAME_COUNT=630, SEEDS=runner.LED_SEEDS,
            PATTERNS=[dict(name=name, frames=count) for name, count in runner.LED_PATTERN_SPECS],
            validate_case=lambda case: b'qualified-contract')
        if module_change:
            module_change(module)
        if case_change:
            case_change(cases)
        def parent_init(obj, workspace, run):
            obj.run, obj.auth = RUN, auth
            obj.state = {'boards': {board: {} for board in runner.base.BOARDS}}
        real_read, real_sha, real_import = runner.base.READ, runner.base.SHA, runner.importlib.import_module
        def fake_read(path):
            return cases if Path(path) == RUN / 'LED-cases.json' else real_read(path)
        def fake_sha(path):
            keys = {'broader_runner.py': 'broader_runner_sha256', 'led_units.py': 'LED_module_sha256',
                    'LED-cases.json': 'LED_cases_sha256'}
            key = keys.get(Path(path).name)
            return auth.get(key, 'test-cases-pin') if key else real_sha(path)
        def fake_import(name):
            return module if name == 'led_units' else real_import(name)
        with patch.object(runner.broader.Runner, '__init__', new=parent_init), \
             patch.object(runner.base, 'READ', side_effect=fake_read), \
             patch.object(runner.base, 'SHA', side_effect=fake_sha), \
             patch.object(runner.importlib, 'import_module', side_effect=fake_import):
            # No real image is executed. This isolates constructor admission of
            # the module/case contract from the CPU-qualified opcode checks.
            auth.setdefault('LED_cases_sha256', 'test-cases-pin')
            return runner.Runner(ROOT, RUN)

    def test_constructor_admits_full_contract_and_initializes_zero_counters(self):
        obj = self.construct_with_contract()
        self.assertEqual(obj.state['LED_pattern_count'], 10)
        self.assertEqual(obj.state['LED_frames_per_unit'], 630)
        self.assertEqual(obj.state['LED_pattern_names'], list(runner.LED_PATTERN_NAMES))
        for row in obj.state['boards'].values():
            self.assertEqual(row['LED_frames'], 0)
            self.assertEqual(row['LED_patterns_completed'], 0)

    def test_constructor_rejects_wrong_module_or_case_seed_and_pattern_contract(self):
        changes = (
            dict(module_change=lambda module: setattr(module, 'FRAME_COUNT', 520)),
            dict(module_change=lambda module: setattr(module, 'SEEDS', tuple(reversed(module.SEEDS)))),
            dict(module_change=lambda module: module.PATTERNS.pop()),
            dict(module_change=lambda module: module.PATTERNS[1].update(name='wigwag')),
            dict(module_change=lambda module: module.PATTERNS[0].update(frames=9)),
            dict(case_change=lambda cases: cases.reverse()),
            dict(case_change=lambda cases: cases[0].update(pattern_count=3)),
            dict(case_change=lambda cases: cases[0]['pattern_names'].reverse()),
        )
        for index, change in enumerate(changes):
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.construct_with_contract(**change)


class Cycle(unittest.TestCase):
    def fake_runner(self, folder, *, failed_LED=False, raised_LED=False, wrong_frames=False,
                    corrupt_LED=None, failed_after_LED=None):
        obj = runner.Runner.__new__(runner.Runner)
        obj.run, obj.root, obj.kit = Path(folder), ROOT, Path(folder) / 'kit'
        obj.auth, obj.case_modules = {}, ()
        obj.original = {board: b'original' for board in runner.base.BOARDS}
        obj.last_flash = {board: 100.0 for board in runner.base.BOARDS}
        obj.cases = [dict(name='source-' + str(index)) for index in range(40)]
        obj.led_cases = [dict(seed=index) for index in range(4)]
        obj.events, obj.publications = [], []
        obj.state = dict(boards={board: dict(passed_cycles=0, breakpoint_hits=0,
            base_status_reference=None, ASM_variant_indices=[], LED_pattern_units=0,
            LED_frames=0, LED_variant_indices=[]) for board in runner.base.BOARDS})
        obj.transport = SimpleNamespace(plans=SimpleNamespace(package=lambda kit: None))
        def publish(path, value):
            obj.publications.append((Path(path), copy.deepcopy(value)))
        obj.publish = publish
        obj.status = lambda phase, **fields: obj.state.update(state=phase, **fields)
        obj.marker = lambda *args, **fields: None
        @contextlib.contextmanager
        def connection(board, path):
            yield object()
        obj.connection = connection
        obj.establish = lambda link: None
        obj.guard = lambda link, board: 'verified'
        obj.mode = lambda link, board: dict(E_before_probe=True)
        obj.clock = lambda link, board: (dict(passed=True), b'clock')
        obj.units = SimpleNamespace(
            base_and_utilities=lambda *args: (dict(passed=True, base_status_sha256={
                command: 'unchanged-' + command for command in ('C', 'P', 'W')}), b'utilities'),
            builtins_unit=lambda *args: (dict(passed=True, services=list(range(0x80, 0x85))), b'BRK'))
        def LED(*args):
            obj.events.append('LED')
            if raised_LED:
                raise RuntimeError('LED restoration failed')
            proof = dict(passed=not failed_LED, frames=629 if wrong_frames else 630,
                        pattern_count=10, pattern_names=list(runner.LED_PATTERN_NAMES),
                        patterns=[dict(name=name, frames=count) for name, count in runner.LED_PATTERN_SPECS],
                        original_led_restored_before_BRK=True, entry_led=0, restored_led_before_BRK=0,
                        CRA_before=0x34, CRA_after=0x34, actual_pin_readback_matches_every_frame=True,
                        exact_model_image_verified_before_execution=True,
                        HOLD_cleanup=dict(lifecycle_hex='00000000', registry_valid=False))
            if corrupt_LED:
                corrupt_LED(proof)
            return proof, b'LED'
        obj.led = SimpleNamespace(led_unit=LED)
        obj.failed_after_LED = failed_after_LED
        return obj

    @contextlib.contextmanager
    def unit_fakes(self, obj):
        def ASM(*args):
            obj.events.append('ASM')
            return dict(passed=obj.failed_after_LED != 'ASM'), b'ASM'
        def debugger(*args):
            obj.events.append('debugger')
            return dict(passed=obj.failed_after_LED != 'debugger', breakpoint_hits=16)
        with patch.object(runner.continuing, 'verify_workload', return_value=1), \
             patch.object(runner.base, 'targeted_unit', return_value={'passed': True}), \
             patch.object(runner.variants, 'asm_unit', side_effect=ASM), \
             patch.object(runner.base, 'debugger_unit', side_effect=debugger), \
             patch.object(runner.time, 'monotonic', return_value=100.0):
            yield

    def test_success_counts_only_complete_LED_and_preserves_all_workloads(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.fake_runner(folder)
            with self.unit_fakes(obj):
                for _ in range(5):
                    obj.cycle('2604')
            self.assertEqual(obj.events, ['LED', 'ASM', 'debugger'] * 5)
            row = obj.state['boards']['2604']
            self.assertEqual(row['passed_cycles'], 5)
            self.assertEqual(row['LED_pattern_units'], 5)
            self.assertEqual(row['LED_frames'], 3150)
            self.assertEqual(row['LED_patterns_completed'], 50)
            self.assertEqual(row['LED_variant_indices'], [0, 1, 2, 3])
            self.assertEqual(row['breakpoint_hits'], 80)
            self.assertEqual(row['fixed_BRK_services_passed'], list(range(0x80, 0x85)))
            completed = [value for path, value in obj.publications
                         if path.name == 'report.json' and value['passed']]
            self.assertEqual(len(completed), 5)
            for value in completed:
                self.assertTrue(value['base_utilities']['passed'])
                self.assertTrue(value['targeted']['passed'])
                self.assertTrue(value['builtins']['passed'])
                self.assertTrue(value['LED_patterns']['passed'])
                self.assertEqual(value['LED_patterns']['frames'], 630)
                self.assertEqual(value['LED_patterns']['pattern_count'], 10)
                self.assertEqual(value['LED_patterns']['pattern_names'], list(runner.LED_PATTERN_NAMES))
                self.assertTrue(value['ASM']['passed'])
                self.assertTrue(value['debugger']['passed'])
                self.assertTrue(value['mode_before']['E_before_probe'])
                self.assertTrue(value['mode_after']['E_before_probe'])

    def test_failed_LED_receipt_never_publishes_pass_or_runs_later_code(self):
        for option in ('failed_LED', 'wrong_frames', 'raised_LED'):
            with self.subTest(option=option), tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
                obj = self.fake_runner(folder, **{option: True})
                with self.unit_fakes(obj), self.assertRaises((AssertionError, RuntimeError)):
                    obj.cycle('2604')
                self.assertEqual(obj.events, ['LED'])
                self.assertEqual(obj.state['boards']['2604']['passed_cycles'], 0)
                self.assertEqual(obj.state['boards']['2604']['LED_frames'], 0)
                self.assertFalse(any(value.get('passed') for path, value in obj.publications
                                     if path.name == 'report.json'))

    def test_partial_duplicate_reordered_or_wrong_length_pattern_never_counts(self):
        corruptions = {
            'count': lambda proof: proof.update(pattern_count=5),
            'missing-name': lambda proof: proof['pattern_names'].pop(),
            'reordered': lambda proof: proof['pattern_names'].reverse(),
            'duplicate': lambda proof: proof['patterns'].__setitem__(1, dict(proof['patterns'][0])),
            'wrong-segment-size': lambda proof: proof['patterns'][0].update(frames=9),
            'unrestored-output': lambda proof: proof.update(restored_led_before_BRK=0xAA),
            'changed-CRA': lambda proof: proof.update(CRA_after=0x30),
            'invalid-registry': lambda proof: proof['HOLD_cleanup'].update(registry_valid=True),
        }
        for label, corrupt in corruptions.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
                obj = self.fake_runner(folder, corrupt_LED=corrupt)
                with self.unit_fakes(obj), self.assertRaises(AssertionError):
                    obj.cycle('2604')
                self.assertEqual(obj.events, ['LED'])
                self.assertEqual(obj.state['boards']['2604']['passed_cycles'], 0)
                self.assertFalse(any(value.get('passed') for path, value in obj.publications
                                     if path.name == 'report.json'))

    def test_successful_LED_does_not_count_if_later_workload_fails(self):
        for component in ('ASM', 'debugger'):
            with self.subTest(component=component), tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
                obj = self.fake_runner(folder, failed_after_LED=component)
                with self.unit_fakes(obj), self.assertRaises(AssertionError):
                    obj.cycle('2604')
                self.assertEqual(obj.state['boards']['2604']['LED_frames'], 0)
                self.assertEqual(obj.state['boards']['2604']['passed_cycles'], 0)
                self.assertFalse(any(value.get('passed') for path, value in obj.publications
                                     if path.name == 'report.json'))

    def test_both_board_counters_and_four_seed_rotation_are_independent(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.fake_runner(folder)
            seeds = []
            original_LED = obj.led.led_unit
            def trace_LED(link, transport, case):
                seeds.append(case['seed'])
                return original_LED(link, transport, case)
            obj.led.led_unit = trace_LED
            with self.unit_fakes(obj):
                for _ in range(4):
                    obj.cycle('2604')
                obj.cycle('2609')
            self.assertEqual(seeds, [0, 1, 2, 3, 0])
            self.assertEqual(obj.state['boards']['2604']['LED_frames'], 2520)
            self.assertEqual(obj.state['boards']['2604']['LED_patterns_completed'], 40)
            self.assertEqual(obj.state['boards']['2609']['LED_frames'], 630)
            self.assertEqual(obj.state['boards']['2609']['LED_patterns_completed'], 10)


class Policy(unittest.TestCase):
    def execute_simulation(self, folder, *, immediate_stop=False,
                           stop_during_first=False, fail_cycle=False,
                           fail_checkpoint=False):
        """Exercise the actual execute method against deterministic host fakes."""
        obj = runner.Runner.__new__(runner.Runner)
        obj.run = Path(folder)
        obj.root = ROOT
        obj.kit = obj.run / 'fake-kit'
        obj.original, obj.flash_hashes, obj.last_flash = {}, {}, {}
        obj.auth = read(RUN / 'owner-authorization.json')
        obj.auth['campaign_drift_epoch_unix'] = Schedule.epoch
        obj.events, obj.statuses, obj.checkpoint_times = [], [], []
        obj.state = dict(checkpoints=[], boards={
            board: dict(passed_cycles=0) for board in runner.base.BOARDS})
        for board in runner.base.BOARDS:
            capture = obj.run / (board + '-before')
            capture.mkdir()
            (capture / 'application-ram.bin').write_bytes(b'original-' + board.encode())
        def capture(path):
            board = path.name.split('-')[0]
            return dict(board=board, usb_serial=runner.base.BOARDS[board][1]), [b'bank'] * 4
        obj.transport = SimpleNamespace(plans=SimpleNamespace(capture=capture))
        obj.publish = lambda path, value: path.write_text(json.dumps(value))
        def status(phase, **fields):
            obj.state.update(state=phase, **fields)
            obj.statuses.append((phase, copy.deepcopy(fields)))
        obj.status = status
        obj.campaign = lambda active: obj.events.append('campaign-' + str(active))
        now = [0.0]
        def checkpoint(label, collect=True):
            passed = not (fail_checkpoint and label.startswith('periodic-'))
            obj.events.append(label)
            obj.checkpoint_times.append((label, Schedule.epoch + 1000 + now[0]))
            obj.state['checkpoints'].append(dict(passed=passed, label=label))
            return dict(passed=passed, boards={
                board: dict(passed=True, RAM_restored_host_verified=True,
                            RAM_verified_after_snapshot=True)
                for board in runner.base.BOARDS}, drift=dict(passed=passed))
        obj.checkpoint = checkpoint
        def cycle(board):
            obj.events.append('cycle-' + board)
            if fail_cycle:
                raise RuntimeError('simulated LED unit failed before restoration proof')
            count = sum(event.startswith('cycle-') for event in obj.events)
            if stop_during_first or count == 3:
                (obj.run / 'STOP').write_text('owner stop')
            now[0] += 10801 if count == 1 else 2600 if count == 2 else 1
            obj.state['boards'][board]['passed_cycles'] += 1
        obj.cycle = cycle
        if immediate_stop:
            (obj.run / 'STOP').write_text('owner stop')
        real_read, real_sha = runner.base.READ, runner.base.SHA
        def fake_read(path):
            path = Path(path)
            if path == obj.kit / 'board-test-manifest.json':
                return {'sectors': []}
            if path.name == 'report.json' and path.parent.name.endswith('-before'):
                return {'passed': True}
            return real_read(path)
        def fake_sha(path):
            path = Path(path)
            if path == obj.kit / 'board-test-manifest.json':
                return runner.base.KIT_SHA
            if path == Path(obj.auth['baseline_index']):
                return obj.auth['baseline_index_sha256']
            return real_sha(path)
        # Patching the real module's clock changes no board timer or OS clock.
        with patch.object(runner.base, 'READ', side_effect=fake_read), \
             patch.object(runner.base, 'SHA', side_effect=fake_sha), \
             patch.object(runner.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(runner.time, 'time', side_effect=lambda: Schedule.epoch + 1000 + now[0]), \
             patch.object(runner.time, 'sleep', side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)), \
             patch.object(runner.ctypes.windll.kernel32, 'SetThreadExecutionState', return_value=1):
            obj.execute()
        return obj

    def test_owner_stop_before_first_unit_still_closes_safely(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.execute_simulation(folder, immediate_stop=True)
            self.assertFalse(any(event.startswith('cycle-') for event in obj.events))
            self.assertIn('final', obj.events)
            self.assertTrue(obj.state['passed'])
            self.assertTrue(obj.state['owner_stop_observed'])
            self.assertEqual(obj.state['next_drift_unix'], None)

    def test_stop_during_unit_finishes_unit_and_never_starts_other_board(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.execute_simulation(folder, stop_during_first=True)
            cycles = [event for event in obj.events if event.startswith('cycle-')]
            self.assertEqual(cycles, ['cycle-2604'])
            self.assertTrue(obj.state['passed'])
            self.assertIn('final', obj.events)

    def test_no_three_hour_deadline_and_checkpoint_uses_campaign_boundary(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.execute_simulation(folder)
            work = [event for event in obj.events if event.startswith(('cycle-', 'periodic-', 'final'))]
            self.assertEqual(work, ['cycle-2604', 'cycle-2609', 'periodic-000001',
                                    'cycle-2604', 'final'])
            self.assertTrue(obj.state['passed'])
            self.assertGreater(obj.state['monitored_seconds'], 10800)
            scheduled = [fields['next_drift_unix'] for _, fields in obj.statuses
                         if fields.get('next_drift_unix') is not None]
            self.assertEqual(scheduled[0], Schedule.epoch + 14400)
            self.assertEqual(scheduled[1], Schedule.epoch + 28800)
            periodic = next(at for label, at in obj.checkpoint_times if label.startswith('periodic-'))
            self.assertGreaterEqual(periodic, Schedule.epoch + 14400)
            self.assertLess(periodic, Schedule.epoch + 14410)

    def test_LED_failure_stops_and_invokes_final_restoration_without_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.execute_simulation(folder, fail_cycle=True)
            work = [event for event in obj.events if event.startswith(('cycle-', 'periodic-', 'final'))]
            self.assertEqual(work, ['cycle-2604', 'final'])
            self.assertFalse(obj.state['passed'])
            self.assertIn('simulated LED unit failed', obj.state['workload_failure'])
            self.assertFalse(obj.state.get('owner_stop_observed', False))
            self.assertEqual(sum(row['passed_cycles'] for row in obj.state['boards'].values()), 0)

    def test_failed_periodic_checkpoint_never_resumes_workload(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.execute_simulation(folder, fail_checkpoint=True)
            work = [event for event in obj.events if event.startswith(('cycle-', 'periodic-', 'final'))]
            self.assertEqual(work, ['cycle-2604', 'cycle-2609', 'periodic-000001', 'final'])
            self.assertFalse(obj.state['passed'])
            self.assertIn('checkpoint failed', obj.state['workload_failure'])


class Checkpoints(unittest.TestCase):
    def fake_runner(self, folder, fail_restore=False):
        obj = runner.Runner.__new__(runner.Runner)
        obj.run, obj.root = Path(folder), ROOT
        obj.state, obj.events = {'checkpoints': []}, []
        obj.original = {board: b'original-' + board.encode() for board in runner.base.BOARDS}
        obj.source_pins = {}
        obj.auth = read(RUN / 'owner-authorization.json')
        obj.status = lambda phase, **fields: obj.events.append(phase)
        obj.publish = lambda path, value: path.write_text(json.dumps(value))
        def restore(board):
            obj.events.append('restore-' + board)
            return dict(passed=not (fail_restore and board == '2604'),
                        RAM_restored_host_verified=True, errors=[])
        obj.restore = restore
        @contextlib.contextmanager
        def connection(board, path):
            obj.events.append('verify-' + board)
            yield board
        obj.connection = connection
        obj.establish, obj.guard = lambda link: None, lambda link, board: None
        obj.transport = SimpleNamespace(read_range=lambda board, first, last: obj.original[board])
        return obj

    def test_periodic_restores_both_before_collector_and_rechecks_both_after(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.fake_runner(folder)
            snapshot = Path(folder) / 'snapshot'
            snapshot.mkdir()
            rows = [dict(board=board, baseline_index=obj.auth['baseline_index'],
                         application_ram_restored=True) for board in runner.base.BOARDS]
            rows[1].update(measurement_segment=obj.auth['measurement_segment_2609'],
                           original_baseline_replaced=False)
            (snapshot / 'summary.json').write_text(json.dumps(dict(
                passed=True, boards=rows, clock_set=False, trim_changed=False, flash_written=False)))
            def collect(*args, **kwargs):
                self.assertEqual(obj.events[-3:], ['restore-2604', 'restore-2609', 'checkpoint-drift'])
                self.assertEqual(args[0][-4:], ['--board', '2604', '--board', '2609'])
                return SimpleNamespace(returncode=0, stdout='SNAPSHOT ' + str(snapshot) + '\n', stderr='')
            with patch.object(runner.subprocess, 'run', side_effect=collect):
                proof = obj.checkpoint('periodic-000001')
            self.assertTrue(proof['passed'])
            self.assertEqual(obj.events[-2:], ['verify-2604', 'verify-2609'])
            self.assertTrue(all(row['RAM_verified_after_snapshot'] for row in proof['boards'].values()))

    def test_first_board_restore_failure_still_attempts_second_and_refuses_drift(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.fake_runner(folder, fail_restore=True)
            with patch.object(runner.subprocess, 'run') as collector:
                proof = obj.checkpoint('periodic-000001')
            self.assertFalse(proof['passed'])
            collector.assert_not_called()
            self.assertIn('restore-2604', obj.events)
            self.assertIn('restore-2609', obj.events)

    def test_failed_collector_still_rereads_original_RAM_on_both_boards(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            obj = self.fake_runner(folder)
            with patch.object(runner.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=1, stdout='', stderr='simulated collector failure')):
                proof = obj.checkpoint('periodic-000001')
            self.assertFalse(proof['passed'])
            self.assertTrue(all(row['RAM_verified_after_snapshot'] for row in proof['boards'].values()))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + unittest_args, verbosity=2)
