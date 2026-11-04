"""Narrow host admission/serialization checks; no CPU, serial or flash model."""
import json
from pathlib import Path
import tempfile
import unittest

import nf_migrate as migration


F_IMAGE = (Path(__file__).resolve().parents[1]/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
TEST_ROOT = Path(__file__).resolve().parent/'.test-runs'


def temporary_directory():
    # Keep automatic recursive cleanup inside this task's checked test folder.
    assert TEST_ROOT.resolve().is_relative_to(Path(__file__).resolve().parent)
    TEST_ROOT.mkdir(exist_ok=True)
    (TEST_ROOT/'.gitignore').write_text('*\n', encoding='ascii')
    return tempfile.TemporaryDirectory(dir=TEST_ROOT)


def seal(row):
    row = bytearray(row)
    row[30:32] = migration.crc(row[:30]).to_bytes(2, 'little')
    row[252:254] = migration.crc(row[:252]).to_bytes(2, 'little')
    return bytes(row)


def blank_banks(f_installed=False):
    banks = [bytearray(b'\xff'*32768) for _ in range(4)]
    if f_installed:
        banks[3][-4096:] = F_IMAGE
    return banks


def with_snapshot(sequence=1, counts=None, f_installed=True):
    banks = blank_banks(f_installed)
    banks[3][0x4000:0x4100] = migration.snapshot(counts or [0]*32, sequence)
    return banks


class Admission(unittest.TestCase):
    def test_requires_explicit_provisioning(self):
        with self.assertRaisesRegex(ValueError, 'provision-cd'):
            migration.derive(blank_banks(), F_IMAGE, source_kind='wdcmonv2')

    def test_factory_plan_counts_and_scope(self):
        banks = blank_banks()
        # Unknown occupied C/D are a conversion only under the explicit declaration.
        banks[3][0x4000] = 0x42
        banks[3][0x5000] = 0x43
        banks[0][:] = bytes(range(256))*128
        banks[3][0x2000:0x4000] = b'X'*8192   # A/B user images stay unchanged.
        tx, transfers, expected = migration.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True)
        self.assertEqual([op['address'] for op in tx['operations']], [0xf000, 0xd000, 0xc000])
        self.assertEqual(tx['reserved_counts'], [int(n in (28, 29, 31)) for n in range(32)])
        self.assertEqual(tx['prior_history_unknown_mask'], 'ffffffff')
        self.assertEqual(expected[:3], list(map(bytes, banks[:3])))
        self.assertEqual(expected[3][:0x4000], banks[3][:0x4000])
        self.assertEqual(expected[3][0x6000:0x7000], banks[3][0x6000:0x7000])
        self.assertEqual(migration.classify_journal(expected[3])['default'], 'S')
        self.assertEqual(migration.classify_journal(expected[3])['enabled_mask'], 0)
        for transfer, final in transfers[1:]:
            self.assertEqual(transfer[255], 255)
            self.assertEqual(final[255], 0)
            self.assertEqual(transfer[:255]+b'\0'+transfer[256:], final)

    def test_programmer_f_route_does_not_erase_f(self):
        tx, _, _ = migration.derive(blank_banks(True), F_IMAGE, source_kind='nf-recovery', provision_cd=True)
        self.assertEqual([op['address'] for op in tx['operations']], [0xd000, 0xc000])
        self.assertEqual(tx['reserved_counts'][31], 0)
        self.assertEqual(tx['reserved_counts'][28:30], [1, 1])

    def test_existing_valid_settings_and_counts_preserved(self):
        banks = with_snapshot(counts=[7]*32)
        row = bytearray(banks[3][0x4000:0x4100])
        row[7], row[13], row[16] = ord('2'), 4, 10
        banks[3][0x4000:0x4100] = seal(row)
        tx, transfers, expected = migration.derive(banks, F_IMAGE, source_kind='nf-recovery')
        self.assertTrue(tx['completed_noop'])
        self.assertEqual(tx['journal_before']['default'], '2')
        self.assertEqual(tx['reserved_counts'], [7]*32)
        self.assertFalse(transfers)
        self.assertEqual(expected, list(map(bytes, banks)))

    def test_existing_journal_upgrade_requires_append_reservation(self):
        with self.assertRaisesRegex(ValueError, 'append reservation'):
            migration.derive(with_snapshot(f_installed=False), F_IMAGE, source_kind='wdcmonv2')

    def test_cannot_reinitialize_existing_valid_journal(self):
        with self.assertRaisesRegex(ValueError, 'preserved'):
            migration.derive(with_snapshot(), F_IMAGE, source_kind='nf-recovery', provision_cd=True)

    def test_damaged_committed_snapshot_is_not_vendor_data(self):
        banks = with_snapshot()
        banks[3][0x4000+70] ^= 1
        self.assertEqual(migration.classify_journal(banks[3])['kind'], 'uncertain')
        with self.assertRaisesRegex(ValueError, 'Damaged'):
            migration.derive(banks, F_IMAGE, source_kind='nf-recovery', provision_cd=True)

    def test_torn_snapshot_is_not_automatically_repaired(self):
        banks = with_snapshot()
        banks[3][0x40ff] = 255
        self.assertEqual(migration.classify_journal(banks[3])['kind'], 'uncertain')

    def test_equal_sequence_conflict_refused(self):
        banks = with_snapshot(counts=[1]*32)
        banks[3][0x5000:0x5100] = migration.snapshot([2]*32, 1)
        status = migration.classify_journal(banks[3])
        self.assertEqual(status['kind'], 'uncertain')
        self.assertIn('Conflicting', status['reason'])

    def test_counter_regression_refused(self):
        banks = with_snapshot(counts=[5]*32)
        banks[3][0x5000:0x5100] = migration.snapshot([4]*32, 2)
        self.assertIn('regress', migration.classify_journal(banks[3])['reason'])

    def test_legacy_and_mixed_history_refused(self):
        banks = blank_banks()
        banks[3][0x4080:0x4084] = b'WC\x01\x00'
        self.assertEqual(migration.classify_journal(banks[3])['kind'], 'uncertain')
        banks = with_snapshot()
        banks[3][0x5200] = 7
        self.assertEqual(migration.classify_journal(banks[3])['kind'], 'uncertain')

    def test_imported_history_must_match_and_not_overflow(self):
        banks = blank_banks()
        history = dict(schema=1, semantics='tracked-lower-bounds', counts=[9]*32,
                       sequence=100, unknown_mask='ffffffff', provenance='Owner supplied verified log',
                       source_sha256=migration.bank_hashes(banks))
        tx, _, _ = migration.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, history=history)
        self.assertEqual(tx['reserved_counts'][31], 10)
        self.assertEqual(tx['sequences'], [101, 102])
        history['source_sha256'] = ['0'*64]*4
        with self.assertRaisesRegex(ValueError, 'bound'):
            migration.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, history=history)
        history['source_sha256'] = migration.bank_hashes(banks)
        history['counts'][31] = 0xffffff
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            migration.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, history=history)

    def test_wrong_f_is_refused(self):
        image = bytearray(F_IMAGE)
        image[500] ^= 1
        with self.assertRaisesRegex(ValueError, 'frozen'):
            migration.derive(blank_banks(), image, source_kind='wdcmonv2', provision_cd=True)

    def test_engine_serialization(self):
        banks = blank_banks()
        tx, _, _ = migration.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True)
        plan = dict(cpu='65c816', source_kind='wdcmonv2', transaction=tx,
                    source_bank_fnv=[f'{migration.fnv(bank):08x}' for bank in banks])
        image, entry = migration.render_engine(b'\xff'*8192, plan)
        self.assertEqual(entry, 0x2010)
        self.assertEqual(image[0x1000:0x1008], b'NFM1\x01\x03\0\0')
        self.assertEqual(image[0x1020:0x1024], b'\xf0\0\0\0')
        self.assertEqual(image[0x1030:0x1034], b'\xd0\x01\0\0')
        self.assertEqual(image[0x1ffc:], migration.fnv(image[:0x1ffc]).to_bytes(4, 'little'))
        for line in migration.s19(image, entry).decode().splitlines():
            self.assertEqual(sum(bytes.fromhex(line[2:])) & 255, 255)


class PrivatePlans(unittest.TestCase):
    def capture(self, root):
        capture = root/'capture'
        capture.mkdir()
        banks = blank_banks()
        for n, bank in enumerate(banks):
            for suffix in ('', '-repeat'):
                (capture/f'b{n}{suffix}.bin').write_bytes(bank)
        for stem, size in [('owner-ram', migration.OWNER_RAM_SIZE), ('owner-zp', migration.OWNER_ZP_SIZE)]:
            for suffix in ('', '-repeat'):
                (capture/f'{stem}{suffix}.bin').write_bytes(bytes(size))
        identity = dict(schema=1, cpu='65c02', board_model='W65C02SXB', source_kind='wdcmonv2',
                        method='independent-double-read', wdc_info_hex=(b'SXB2'+bytes(8)).hex(),
                        synthetic_test_fixture=True)
        (capture/'capture.json').write_text(json.dumps(identity), encoding='utf-8')
        return capture

    def test_prepare_private_inspect_and_tamper(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            capture = self.capture(root)
            f_file = root/'F.bin'
            f_file.write_bytes(F_IMAGE)
            plan = migration.prepare(capture, f_file, root/'plan', cpu='65c02',
                                     source_kind='wdcmonv2', provision_cd=True)
            self.assertFalse(plan['installation_permitted'])
            self.assertFalse(plan['owner_RAM_restored'])
            self.assertEqual((root/'plan/.gitignore').read_text(), '*\n')
            self.assertEqual(migration.inspect(root/'plan'), plan)
            member = root/'plan/expected-b0.bin'
            member.write_bytes(b'X'*32768)
            with self.assertRaisesRegex(ValueError, 'Changed plan member'):
                migration.inspect(root/'plan')

    def test_repeat_mismatch_refuses_before_output(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            capture = self.capture(root)
            (capture/'owner-ram-repeat.bin').write_bytes(b'X'*migration.OWNER_RAM_SIZE)
            with self.assertRaisesRegex(ValueError, 'repeated capture: owner-ram'):
                migration.read_capture(capture, '65c02', 'wdcmonv2')

    def test_cpu_declaration_cannot_change_in_private_plan(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            capture = self.capture(root)
            f_file = root/'F.bin'
            f_file.write_bytes(F_IMAGE)
            migration.prepare(capture, f_file, root/'plan', cpu='65c02', source_kind='wdcmonv2', provision_cd=True)
            path = root/'plan/plan.json'
            plan = json.loads(path.read_text())
            plan['cpu'], plan['board_model'] = '65c816', 'W65C816SXB'
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'CPU/board'):
                migration.inspect(root/'plan')


if __name__ == '__main__':
    unittest.main(verbosity=2)
