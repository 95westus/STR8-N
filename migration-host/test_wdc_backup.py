"""Backup policy/overwrite/transfer checks only; no CPU, flash or serial model."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import nf_migrate as planning
import nf_migrate_live as live
import test_nf_migrate as host_tests
from test_nf_migrate import F_IMAGE, blank_banks, temporary_directory, with_snapshot
from test_nf_migrate_live import FakeLink, quiet


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT/'migrator/candidates/nfm2-b0-v1/template.bin'


def source_banks():
    banks = blank_banks()
    banks[0][:] = b'X'*32768  # Occupied B0; never inferred to be scratch.
    banks[3][:] = bytes(range(256))*128
    banks[3][:4] = b'WDC\0'
    banks[3][0x7ffc:0x7ffe] = b'\x04\x80'
    return banks


def make_plan(root, choice):
    capture = host_tests.PrivatePlans().capture(root)
    banks = source_banks()
    for n in (0, 3):
        for suffix in ('', '-repeat'):
            (capture/f'b{n}{suffix}.bin').write_bytes(banks[n])
    f_file = root/'F.bin'
    f_file.write_bytes(F_IMAGE)
    template = TEMPLATE if choice in ('b0', 'both') else ROOT/'migrator/payload/template.bin'
    plan = planning.prepare(capture, f_file, root/'plan', cpu='65c02', source_kind='wdcmonv2',
                            provision_cd=True, wdc_backup=choice, template_file=template)
    return plan, banks


class BackupPolicy(unittest.TestCase):
    def test_prompt_choices_and_eof_noninteractive_refusal(self):
        for value, expected in (('', 'host'), ('h', 'host'), ('b0', 'b0'), ('both', 'both')):
            self.assertEqual(live.choose_wdc_backup(input_fn=lambda _: value, interactive=True, message=quiet), expected)
        with self.assertRaisesRegex(ValueError, 'Noninteractive'):
            live.choose_wdc_backup(interactive=False, message=quiet)
        def eof(_):
            raise EOFError
        with self.assertRaisesRegex(ValueError, 'No backup choice'):
            live.choose_wdc_backup(input_fn=eof, interactive=True, message=quiet)
        self.assertEqual(live.choose_wdc_backup('both', interactive=False), 'both')

    def test_each_destination_and_exact_host_backup(self):
        for choice in ('host', 'b0', 'both'):
            with self.subTest(choice=choice), temporary_directory() as temporary:
                root = Path(temporary)
                plan, banks = make_plan(root, choice)
                self.assertEqual(planning.inspect(root/'plan'), plan)
                standalone = root/'plan/wdcmonv2-b3-32768.bin'
                self.assertEqual(standalone.exists(), choice in ('host', 'both'))
                if standalone.exists():
                    self.assertEqual(standalone.read_bytes(), banks[3])
                # Original B0 and both original WDC reads survive every choice.
                self.assertEqual((root/'plan/source/b0.bin').read_bytes(), banks[0])
                self.assertEqual((root/'plan/source/b3-repeat.bin').read_bytes(), banks[3])
                self.assertFalse(plan['wdc_backup']['B0_boot_qualified'])
                self.assertEqual(plan['wdc_backup']['reset_vector'], '8004')
                self.assertEqual((root/'plan/expected-b0.bin').read_bytes(), banks[0] if choice == 'host' else banks[3])
                if choice == 'host':
                    self.assertEqual((root/'plan/migrator.bin').read_bytes()[0x1000:0x1004], b'NFM1')

    def test_copy_precedes_f_and_counts_cover_all_eleven_erases(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            plan, banks = make_plan(root, 'both')
            tx = plan['transaction']
            self.assertEqual([(o['bank'], o['address']) for o in tx['operations']],
                             [(0, a) for a in range(0x8000, 0x10000, 4096)]+[(3, 0xf000), (3, 0xd000), (3, 0xc000)])
            self.assertEqual(tx['reserved_counts'], [int(i < 8 or i in (28, 29, 31)) for i in range(32)])
            self.assertEqual(tx['operations'][7]['after_sha256'][0], planning.sha(banks[3]))
            for o in tx['operations'][:8]:
                self.assertIsNone(o['commit_address'])  # Even B0:C/D are ordinary opaque bytes.
                self.assertEqual((root/'plan'/o['transfer_file']).read_bytes(), (root/'plan'/o['final_file']).read_bytes())
            for o in tx['operations'][-2:]:
                self.assertEqual((root/'plan'/o['transfer_file']).read_bytes()[255], 255)
                self.assertEqual((root/'plan'/o['final_file']).read_bytes()[255], 0)
            params = planning.engine_plan(plan)
            self.assertEqual(params[:8], b'NFM2\x02\x0b\x08\0')
            self.assertEqual(params[32+8*16:36+8*16], b'\xf0\0\x03\0')
            final = (root/'plan/expected-b3.bin').read_bytes()
            self.assertEqual(planning.classify_journal(final)['counts'], tx['reserved_counts'])

    def test_skip_identical_sectors_including_entire_bank(self):
        banks = source_banks()
        banks[0][:4096] = banks[3][:4096]
        tx, _, _ = planning.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, backup_b0=True)
        self.assertEqual(tx['operations'][0]['address'], 0x9000)
        self.assertEqual(tx['reserved_counts'][0], 0)
        banks[0][:] = banks[3]
        tx, _, expected = planning.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, backup_b0=True)
        self.assertEqual([o['bank'] for o in tx['operations']], [3, 3, 3])
        self.assertEqual(expected[0], banks[0])
        params = planning.engine_plan(dict(transaction=tx, source_bank_fnv=['00000000']*4,
                                           wdc_backup=dict(choice='b0')))
        self.assertEqual(params[:8], b'NFM2\x02\x03\0\0')

    def test_existing_journal_and_exhausted_history_refuse_new_b0_writes(self):
        with self.assertRaisesRegex(ValueError, 'append reservations'):
            planning.derive(with_snapshot(), F_IMAGE, source_kind='wdcmonv2', backup_b0=True)
        banks = source_banks()
        counts = [4]*32
        counts[0] = planning.MAX_COUNT
        history = dict(schema=1, semantics='tracked-lower-bounds', source_sha256=planning.bank_hashes(banks),
                       counts=counts, sequence=50, unknown_mask='ffffffff', provenance='synthetic checked history')
        with self.assertRaisesRegex(ValueError, 'exhausted for B0:8000'):
            planning.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, history=history, backup_b0=True)
        counts[0] = 4
        tx, _, _ = planning.derive(banks, F_IMAGE, source_kind='wdcmonv2', provision_cd=True, history=history, backup_b0=True)
        self.assertEqual(tx['reserved_counts'][0], 5)
        self.assertEqual(tx['reserved_counts'][8], 4)
        self.assertEqual(tx['sequence_after'], 52)
        self.assertEqual(tx['prior_history_unknown_mask'], 'ffffffff')

    def test_policy_tamper_is_not_a_target_authorization(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            make_plan(root, 'host')
            path = root/'plan/plan.json'
            plan = json.loads(path.read_text())
            plan['wdc_backup']['choice'] = 'both'
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Changed WDC backup policy'):
                planning.inspect(root/'plan')

    def test_overwrite_refusal_precedes_any_board_protocol(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            make_plan(root, 'b0')
            fake = FakeLink(source_banks(), root/'run')
            with patch.object(live.sys.stdin, 'isatty', return_value=False):
                with self.assertRaisesRegex(ValueError, 'overwrite-b0'):
                    live.execute_wdc(fake, root/'plan', root/'run', allow_unqualified=True, message=quiet)
            self.assertEqual(fake.events, [])
            self.assertEqual(fake.sent, [])

    def test_nfm2_host_waits_for_b0_verified_rows_before_f_payload(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            make_plan(root, 'both')
            run = live.private_root(root/'run')
            fake = FakeLink(source_banks(), run)
            result = live.execute_wdc(fake, root/'plan', run, allow_unqualified=True,
                                      overwrite_b0=True, message=quiet, pace=lambda _: None)
            tokens = [event[1] for event in fake.events if isinstance(event, tuple) and event[0] == 'until']
            f_start = tokens.index(b'SEND 4096 BYTES FOR B3:F\r\n')
            self.assertEqual(tokens[:f_start].count(live.B0_ROW_DONE), 8)
            self.assertEqual(tokens.count(live.B0_ROW_DONE), 11)
            self.assertTrue(result['device_transaction_verified'])
            self.assertFalse(result['passed'])  # No independent hardware readback/owner restoration in this host check.
            self.assertEqual(planning.sha(TEMPLATE.read_bytes()), live.B0_ENGINE_TEMPLATE_SHA256)


if __name__ == '__main__':
    unittest.main(verbosity=2)
