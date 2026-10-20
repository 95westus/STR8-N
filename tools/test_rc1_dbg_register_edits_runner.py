"""Host-only register qualification policy and recovery tests; no ports.

Every connection, transport and application operation below is a fake. Real
files are limited to a new temporary directory used for the private archive.
"""
import copy
from contextlib import contextmanager, redirect_stdout
import importlib.util
import io
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('register_edit_worker_under_test', ROOT / 'tools/run_rc1_dbg_register_edits.py')
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def authorization():
    return dict(owner_authorized=True, boards=list(worker.BOARDS), monitor_slots=['A', 'B'],
        promotion_held=True, native_debugging=False, native_applications=False, RTC_issue_deferred=True,
        RTC_endurance_or_drift_collection_authorized=False,
        reset_firmware_install_or_persistent_setting_changes_authorized=False,
        firmware_sha256=worker.FIRMWARE_SHA, package_manifest_sha256=worker.KIT_SHA)


class Policy(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='dbg-register-policy-', dir=ROOT / 'tmp')
        self.addCleanup(self.folder.cleanup)
        self.q = Path(self.folder.name) / 'qualification'
        self.run = self.q / 'run'
        self.kit = Path(self.folder.name) / 'kit'
        self.auth = authorization()
        self.admission = dict(passed=True, owner_authorization_sha256='auth', native_debugging=False,
            RTC_issue_deferred=True, source_sha256={'source.py': 'source'}, evidence_sha256={'proof.json': 'proof'},
            runner_sha256='runner')
        self.records = {'owner-authorization.json': self.auth, 'admission.json': self.admission,
            'rc1-dbg1-promotion-hold.json': {'held': True},
            'active-rtc-campaign.json': {'powered_off_boards': ['2205', '2512']}}
        self.hashes = {'owner-authorization.json': 'auth', 'board-test-manifest.json': worker.KIT_SHA,
            'run_rc1_dbg_register_edits.py': 'runner', 'source.py': 'source', 'proof.json': 'proof'}
        self.addCleanup(patch.stopall)
        patch.object(worker, 'Q', self.q).start()
        patch.object(worker, 'KIT', self.kit).start()
        patch.object(worker, 'READ', side_effect=lambda p: copy.deepcopy(self.records[Path(p).name])).start()
        patch.object(worker, 'SHA', side_effect=lambda p: self.hashes[Path(p).name]).start()

    def test_read_only_capture_authorization(self):
        self.assertEqual(worker.admit(self.run, False), self.auth)

    def test_execute_requires_all_pinned_admission(self):
        self.assertEqual(worker.admit(self.run, True), self.auth)

    def test_scope_changes_refuse(self):
        changes = [('owner_authorized', False), ('boards', ['2604']), ('monitor_slots', ['A']),
            ('promotion_held', False), ('native_debugging', True), ('native_applications', True),
            ('RTC_issue_deferred', False), ('RTC_endurance_or_drift_collection_authorized', True),
            ('reset_firmware_install_or_persistent_setting_changes_authorized', True),
            ('firmware_sha256', 'changed'), ('package_manifest_sha256', 'changed')]
        for field, value in changes:
            original = self.records['owner-authorization.json'][field]
            self.records['owner-authorization.json'][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                worker.admit(self.run, True)
            self.records['owner-authorization.json'][field] = original

    def test_outside_qualification_directory_refuses(self):
        with self.assertRaises(AssertionError):
            worker.admit(self.q.parent / 'other', False)

    def test_global_promotion_hold_required(self):
        self.records['rc1-dbg1-promotion-hold.json']['held'] = False
        with self.assertRaises(AssertionError):
            worker.admit(self.run, True)

    def test_powered_off_board_set_required(self):
        self.records['active-rtc-campaign.json']['powered_off_boards'].append('2609')
        with self.assertRaises(AssertionError):
            worker.admit(self.run, True)

    def test_authentication_and_all_source_evidence_hashes_refuse_changes(self):
        for name in self.hashes:
            original = self.hashes[name]
            self.hashes[name] = 'changed'
            with self.subTest(path=name), self.assertRaises(AssertionError):
                worker.admit(self.run, True)
            self.hashes[name] = original

    def test_failed_or_native_admission_refuses(self):
        for field, value in [('passed', False), ('native_debugging', True), ('RTC_issue_deferred', False)]:
            original = self.records['admission.json'][field]
            self.records['admission.json'][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                worker.admit(self.run, True)
            self.records['admission.json'][field] = original


class Identity(unittest.TestCase):
    def make(self, board='2609'):
        obj = worker.Qualification.__new__(worker.Qualification)
        obj.board, obj.cpu = board, worker.BOARDS[board][3]
        values = {(0x7d01, 0x7d01): bytes([obj.cpu]), (0x7d0a, 0x7d0b): bytes.fromhex('ff64'),
            (0x7d0c, 0x7d0c): b'\x80', (0x7e02, 0x7e03): bytes.fromhex('817b'),
            (0x7d30, 0x7d30): b'\xb0', (0x7bfc, 0x7bff): bytes(4)}
        obj.t = SimpleNamespace(identity=lambda link, board, generation: 'Running: MONITOR B, gen 00000032')
        link = SimpleNamespace(dump=lambda first, last: values[(first, last)])
        return obj, link, values

    def test_exact_generation_cpu_ram_abi_slot_and_inactive_lifecycle_pass(self):
        obj, link, _ = self.make()
        self.assertIn('MONITOR B', obj.identity(link, 'B'))

    def test_wrong_cpu_ram_boundary_abi_or_lifecycle_refuses(self):
        for address, value in [((0x7d01, 0x7d01), b'\x02'), ((0x7d0a, 0x7d0b), b'\xff\x66'),
            ((0x7d0c, 0x7d0c), b'\x00'), ((0x7e02, 0x7e03), bytes(2)),
            ((0x7bfc, 0x7bff), b'\x01\x00\x00\x00')]:
            obj, link, values = self.make()
            values[address] = value
            with self.subTest(address=address), self.assertRaises(AssertionError):
                obj.identity(link, 'B')

    def test_wrong_current_slot_refuses(self):
        obj, link, _ = self.make()
        with self.assertRaises(AssertionError):
            obj.identity(link, 'A')


class FixtureGrouping(unittest.TestCase):
    def test_sparse_fixture_groups_are_ordered_and_byte_exact(self):
        self.assertEqual(worker.groups({0x202: 3, 0x200: 1, 0x201: 2, 0x500: 4}),
                         [(0x200, bytes((1, 2, 3))), (0x500, b'\x04')])


class Controls(unittest.TestCase):
    def test_capture_status_does_not_load_clock_or_any_application(self):
        obj = worker.Qualification.__new__(worker.Qualification)
        obj.board = '2604'
        calls = []
        def command(text, *args):
            calls.append(text)
            self.assertIn(text, ('C', 'P', 'W'))
            return text.encode()
        result = obj.controls(SimpleNamespace(command=command), clock=False)
        self.assertEqual(calls, ['C', 'P', 'W'])
        self.assertEqual(set(result), {'status_sha256'})

    def test_clock_query_checks_expected_read_only_rtc_controls(self):
        obj = worker.Qualification.__new__(worker.Qualification)
        obj.board = '2609'
        calls = []
        def command(text, *args):
            calls.append(text)
            if text == 'STATUS':
                return b'Running: yes\r\nBackup enabled: yes\r\nRTC registers (raw): 80 00 00 08 00 00 00 80 0E\r\n'
            return b'unchanged'
        result = obj.controls(SimpleNamespace(command=command))
        self.assertEqual(calls, ['C', 'P', 'W', 'R CLOCK', 'STATUS', 'Q'])
        self.assertEqual((result['RTC_control'], result['RTC_trim_encoding']), (0x80, 0x0e))
        self.assertTrue(result['RTC_oscillator_start'] and result['RTC_backup_enabled'])


class OperationOwnership(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='dbg-register-owner-', dir=ROOT / 'tmp')
        self.addCleanup(self.folder.cleanup)
        self.obj = worker.Qualification.__new__(worker.Qualification)
        self.obj.run, self.obj.board = Path(self.folder.name) / 'run', '2604'
        self.value = dict(soak_owner_stopped=True, RTC_sampling_owner_stopped=True,
            current_soak_worker_pid=None, one_shot_collection_authorized=False,
            application_RAM_restore_pending=False, register_edit_worker_active=False,
            block_snapshot=False, physical_reset_pending=False, power_off_reported=False)
        self.saved = []
        self.obj.publish = lambda path, value: self.saved.append((Path(path), copy.deepcopy(value)))
        self.addCleanup(patch.stopall)
        patch.object(worker, 'READ', side_effect=lambda path: copy.deepcopy(self.value)).start()

    def test_idle_marker_can_be_claimed(self):
        self.obj.marker('new qualification', register_edit_worker_active=True)
        self.assertTrue(self.saved[-1][1]['register_edit_worker_active'])
        self.assertEqual(self.saved[-1][1]['register_edit_worker_pid'], os.getpid())

    def test_foreign_active_or_restore_pending_operations_refuse(self):
        changes = [('soak_owner_stopped', False), ('RTC_sampling_owner_stopped', False),
            ('current_soak_worker_pid', 123), ('one_shot_collection_authorized', True),
            ('application_RAM_restore_pending', True), ('register_edit_worker_active', True),
            ('block_snapshot', True), ('physical_reset_pending', True), ('power_off_reported', True)]
        for name, value in changes:
            original = self.value[name]
            self.value[name] = value
            self.saved.clear()
            with self.subTest(field=name), self.assertRaises(AssertionError):
                self.obj.marker('must refuse')
            self.assertFalse(any(path.name == '2604.json' for path, value in self.saved))
            self.value[name] = original

    def test_same_run_active_worker_requires_exact_own_pid(self):
        self.value.update(register_edit_run=str(self.obj.run), register_edit_worker_active=True,
            register_edit_worker_pid=os.getpid() + 10000, block_snapshot=True,
            application_RAM_restore_pending=True)
        with self.assertRaises(AssertionError):
            self.obj.marker('must not steal same run')
        self.value['register_edit_worker_pid'] = os.getpid()
        self.obj.marker('own progress')
        self.assertEqual(self.saved[-1][1]['state'], 'own progress')


class ExecutionRecovery(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='dbg-register-recovery-', dir=ROOT / 'tmp')
        self.addCleanup(self.folder.cleanup)
        self.obj = worker.Qualification.__new__(worker.Qualification)
        obj = self.obj
        obj.run = Path(self.folder.name) / 'run'
        obj.run.mkdir()
        obj.board, obj.usb, obj.preferred = '2604', worker.BOARDS['2604'][1], 'B'
        obj.before, obj.out = obj.run / '2604-before', obj.run / '2604'
        obj.before.mkdir()
        self.original = bytes(n & 255 for n in range(25344))
        (obj.before / 'application-ram.bin').write_bytes(self.original)
        (obj.before / 'restore-application-ram.s19').write_bytes(b'fake private restore image')
        self.banks = [bytes((n,)) * 32768 for n in range(4)]
        self.status = dict(status_sha256=dict(C='config', P='preference', W='wear'))
        self.complete = dict(self.status, RTC_control=0, RTC_trim_encoding=12,
            RTC_oscillator_start=True, RTC_backup_enabled=True)
        obj.borrowed, obj.original, obj.banks, obj.baseline = False, None, None, None
        obj.result = dict(passed=False, slots={}, RAM_restored_host_verified=False)
        self.events, self.publications, self.markers = [], [], []
        self.failures = {}
        self.counts = {}
        def event(name, value=None):
            self.events.append((name, value))
            self.counts[name] = self.counts.get(name, 0) + 1
            failure = self.failures.get((name, self.counts[name]))
            if failure:
                raise RuntimeError(failure)
        self.event = event
        obj.publish = lambda path, value: self.publications.append((Path(path), copy.deepcopy(value)))
        obj.marker = lambda state, **fields: self.markers.append((state, fields))
        self.link = SimpleNamespace()
        @contextmanager
        def connection(log):
            event('connect')
            try:
                yield self.link
            finally:
                event('disconnect')
        obj.connection = connection
        def identity(link, slot=None):
            event('identity', slot)
            return 'correct exact candidate identity'
        obj.identity = identity
        def controls(link, clock=True):
            event('CLOCK' if clock else 'CPW')
            if clock:
                self.assertTrue(obj.borrowed, 'No application may load before borrowed ownership is recorded')
            return copy.deepcopy(self.complete if clock else self.status)
        obj.controls = controls
        def read_flash(link):
            event('flash')
            return self.banks
        obj.read_flash = read_flash
        obj.recover = lambda link: event('recover')
        def switch(link, slot):
            event('switch', slot)
            self.assertTrue(obj.borrowed)
            return dict(passed=True, target_slot=slot)
        obj.switch = switch
        def mode(link):
            event('mode')
            self.assertTrue(obj.borrowed)
            return dict(cpu='65C02', native_debugging=False)
        obj.mode = mode
        def slot(link, cases, name):
            event('slot', name)
            self.assertTrue(obj.borrowed)
            obj.result['slots'][name] = dict(passed=True)
        obj.slot = slot
        def restore_load(link, path):
            event('restore-load', Path(path).name)
            self.assertTrue(obj.borrowed)
            self.assertEqual(Path(path), obj.before / 'restore-application-ram.s19')
        def read_range(link, first, last):
            event('RAM-read')
            self.assertEqual((first, last), (0x200, 0x64ff))
            return self.original
        obj.t = SimpleNamespace(plans=SimpleNamespace(capture=lambda path:
            (dict(board=obj.board, usb_serial=obj.usb), self.banks)), load=restore_load, read_range=read_range)
        self.addCleanup(patch.stopall)
        patch.object(worker, 'READ', return_value=dict(passed=True, controls=self.status)).start()

    def invoke(self, should_pass):
        with redirect_stdout(io.StringIO()):
            if should_pass:
                self.obj.execute()
            else:
                with self.assertRaises(RuntimeError):
                    self.obj.execute()
        self.assertEqual(self.obj.result['passed'], should_pass)

    def test_complete_operation_restores_two_reads_and_original_slot(self):
        self.invoke(True)
        names = [name for name, value in self.events]
        self.assertLess(names.index('RAM-read'), names.index('CLOCK'))
        self.assertLess(names.index('flash'), names.index('CLOCK'))
        self.assertEqual([value for name, value in self.events if name == 'slot'], ['A', 'B'])
        self.assertEqual(self.counts['RAM-read'], 3)
        self.assertEqual(self.counts['restore-load'], 1)
        self.assertTrue(self.obj.result['RAM_restored_host_verified'])
        self.assertFalse(self.markers[-1][1]['application_RAM_restore_pending'])
        self.assertFalse(self.markers[-1][1]['register_edit_worker_active'])

    def test_full_capture_never_loads_an_application_before_archiving_ram(self):
        self.obj.before = self.obj.run / 'fresh-before'
        def capture_controls(link, clock=True):
            self.assertFalse(clock, 'Capture must not load CLOCK before the original RAM archive exists')
            self.event('capture-CPW')
            return self.status
        self.obj.controls = capture_controls
        self.obj.t.wire = SimpleNamespace(s19=lambda cells, entry: b'exact fake restore image')
        expected = [hashlib.sha256(body).hexdigest() for body in self.banks]
        evidence = dict(restoration=dict(boards={'2604': dict(flash=dict(all_four_bank_sha256=expected))}))
        with patch.object(worker, 'READ', return_value=evidence), redirect_stdout(io.StringIO()):
            self.obj.capture()
        self.assertEqual(self.counts['flash'], 2)
        self.assertEqual(self.counts['RAM-read'], 2)
        self.assertEqual((self.obj.before / 'application-ram.bin').read_bytes(), self.original)
        self.assertEqual((self.obj.before / 'application-ram-repeat.bin').read_bytes(), self.original)
        self.assertFalse(any(name in ('CLOCK', 'switch', 'mode', 'slot', 'restore-load') for name, value in self.events))
        reports = [data for path, data in self.publications if path.name == 'report.json']
        self.assertTrue(reports[-1]['passed'] and reports[-1]['repeat_verified'])
        self.assertFalse(reports[-1]['board_RAM_written'])

    def test_initial_identity_failure_never_borrows_or_runs_application(self):
        self.failures['identity', 1] = 'wrong board or firmware'
        self.invoke(False)
        self.assertFalse(self.obj.borrowed)
        self.assertTrue(self.obj.result['RAM_restoration_not_required'])
        self.assertFalse(any(name in ('CLOCK', 'switch', 'mode', 'slot', 'restore-load') for name, value in self.events))
        self.assertFalse(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_initial_status_or_flash_failure_never_borrows(self):
        self.failures['CPW', 1] = 'changed settings'
        self.invoke(False)
        self.assertFalse(self.obj.borrowed)
        self.assertNotIn('restore-load', self.counts)
        self.assertFalse(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_first_clock_failure_still_restores_original_ram(self):
        self.failures['CLOCK', 1] = 'clock application failed during entry'
        self.invoke(False)
        self.assertTrue(self.obj.borrowed)
        self.assertEqual(self.counts['restore-load'], 1)
        self.assertTrue(self.obj.result['RAM_restored_host_verified'])
        self.assertFalse(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_slot_failure_cannot_publish_pass_and_still_restores(self):
        self.failures['slot', 2] = 'simulated register qualification assertion'
        self.invoke(False)
        self.assertTrue(self.obj.result['RAM_restored_host_verified'])
        self.assertEqual(self.counts['restore-load'], 1)
        self.assertFalse(self.markers[-1][1]['register_edit_qualified'])

    def test_final_clock_preservation_failure_does_not_skip_ram_restore(self):
        self.failures['CLOCK', 2] = 'changed RTC control'
        self.invoke(False)
        self.assertIn('preservation_failure', self.obj.result)
        self.assertEqual(self.counts['restore-load'], 1)
        self.assertTrue(self.obj.result['RAM_restored_host_verified'])

    def test_final_flash_failure_does_not_skip_ram_restore(self):
        self.failures['flash', 2] = 'flash differs'
        self.invoke(False)
        self.assertIn('preservation_failure', self.obj.result)
        self.assertEqual(self.counts['restore-load'], 1)
        self.assertTrue(self.obj.result['RAM_restored_host_verified'])

    def test_unknown_recovery_context_refuses_blind_ram_write(self):
        self.failures['recover', 1] = 'unknown prompt'
        self.invoke(False)
        self.assertIn('recovery_failure', self.obj.result)
        self.assertNotIn('restore-load', self.counts)
        self.assertTrue(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_failed_final_identity_refuses_restore_to_unverified_target(self):
        self.failures['identity', 4] = 'identity lost before restore'
        self.invoke(False)
        self.assertIn('restoration_failure', self.obj.result)
        self.assertNotIn('restore-load', self.counts)
        self.assertTrue(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_restore_transport_failure_stays_pending_without_pass(self):
        self.failures['restore-load', 1] = 'restore transfer failed'
        self.invoke(False)
        self.assertFalse(self.obj.result['RAM_restored_host_verified'])
        self.assertTrue(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_restore_readback_failure_stays_pending_without_pass(self):
        self.failures['RAM-read', 2] = 'restored RAM readback differs'
        self.invoke(False)
        self.assertFalse(self.obj.result['RAM_restored_host_verified'])
        self.assertTrue(self.markers[-1][1]['application_RAM_restore_pending'])

    def test_connection_admission_failure_is_recorded_without_false_ram_debt(self):
        self.failures['connect', 1] = 'wrong serial device or unavailable lease'
        self.invoke(False)
        self.assertFalse(self.obj.borrowed)
        self.assertTrue(self.obj.result['RAM_restoration_not_required'])
        self.assertIn('entry_failure', self.obj.result)
        self.assertFalse(self.markers[-1][1]['application_RAM_restore_pending'])
        self.assertFalse(self.markers[-1][1]['register_edit_worker_active'])
        self.assertFalse(any(name in ('CLOCK', 'switch', 'mode', 'slot', 'restore-load') for name, value in self.events))


if __name__ == '__main__':
    unittest.main(verbosity=2)
