"""Host protocol ordering only: no serial port, CPU model or flash model."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import nf_migrate as planning
import nf_migrate_live as live
import test_nf_migrate as host_tests

F_IMAGE = host_tests.F_IMAGE
blank_banks = host_tests.blank_banks
temporary_directory = host_tests.temporary_directory


quiet = lambda *args, **kwargs: None


class FakeLink:
    hardware_access = False

    def __init__(self, banks, run_root, *, bad_archive=False, bad_RAM=False):
        self.banks = list(map(bytes, banks))
        self.run_root = Path(run_root)
        self.bad_archive, self.bad_RAM = bad_archive, bad_RAM
        self.events, self.sent, self.pending = [], [], bytearray()
        self.stream = []
        for _ in range(2):
            for bank in self.banks:
                self.stream.extend((bank, (planning.fnv(bank)^int(bad_archive)).to_bytes(4, 'little')))

    def identity_after_reset(self, **kwargs):
        self.events.append('identity')
        return b'SXB2'+bytes(8)

    def stock_read(self, address, count):
        self.events.append(('stock_read', address, count))
        if address == 0x8000:
            return self.banks[3]
        return bytes(count)

    def load_ram(self, image, entry):
        self.events.append(('load', len(image), entry))
        if self.bad_RAM:
            raise ValueError('RAM readback mismatch')

    def execute_ram(self, entry):
        self.events.append(('exec', entry))

    def until(self, token, **kwargs):
        self.events.append(('until', token))
        if token == live.ENGINE_READY:
            return live.ENGINE_SELF_OK+live.ENGINE_SOURCE_OK+token
        if token == live.REC:
            return b'WAIT...\r\nRecovery L A/B 0-3 C1/2/3 ?\r\nREC> '
        return token

    def exact(self, count, **kwargs):
        body = self.stream.pop(0)
        assert len(body) == count
        return body

    def send(self, body):
        if body == b'Y\r':
            assert list((self.run_root/'phases').glob('*flash-authorized-no-automatic-retry.json'))
        self.sent.append(bytes(body))

    def set_stock_handshake(self, value):
        self.events.append(('RTS', value))


class WdcRamLoadFake(live.WdcLink):
    def __init__(self, corrupt=False):
        self.memory, self.commands = bytearray(65536), []
        self.loaded, self.corrupt = None, corrupt

    def protocol(self, command):
        self.commands.append(command)

    def send(self, body):
        if self.commands[-1] == 2:
            address, count = int.from_bytes(body[:3], 'little'), int.from_bytes(body[3:6], 'little')
            self.memory[address:address+count] = body[6:]

    def exact(self, count, **kwargs):
        return b'\0'

    def stock_read(self, address, count):
        body = bytes(self.memory[address:address+count])
        return bytes((body[0]^1,))+body[1:] if self.corrupt else body


class LiveOrdering(unittest.TestCase):
    def make_plan(self, root):
        capture = host_tests.PrivatePlans().capture(root)
        f_file, template = root/'F.bin', root/'engine.bin'
        f_file.write_bytes(F_IMAGE)
        template.write_bytes(bytes(8192))
        plan_root = root/'plan'
        planning.prepare(capture, f_file, plan_root, cpu='65c02', source_kind='wdcmonv2',
                         provision_cd=True, template_file=template)
        return plan_root, planning.sha(template.read_bytes())

    def test_unqualified_flag_refuses_before_transport(self):
        fake = FakeLink(blank_banks(), Path('.'))
        with self.assertRaisesRegex(ValueError, 'allow-unqualified'):
            live.execute_wdc(fake, '.', '.')
        self.assertEqual(fake.events, [])

    def test_ram_readback_failure_prevents_execute(self):
        fake = WdcRamLoadFake(corrupt=True)
        with self.assertRaisesRegex(ValueError, 'execution forbidden'):
            fake.load_ram(bytes(8192), 0x2000)
        with self.assertRaisesRegex(ValueError, 'verify the complete upload'):
            fake.execute_ram(0x2000)
        self.assertNotIn(6, fake.commands)

    def test_ram_complete_verification_precedes_execute(self):
        fake = WdcRamLoadFake()
        fake.load_ram(bytes(8192), 0x2000)
        self.assertNotIn(6, fake.commands)
        fake.execute_ram(0x2000)
        self.assertEqual(fake.commands[-1], 6)

    def test_capture_streams_twice_and_returns_WDC(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            out = live.private_root(root/'capture')
            body = bytearray(bytes(8192))
            body[0x1ffc:] = planning.fnv(body[:0x1ffc]).to_bytes(4, 'little')
            archive, manifest = root/'archive.bin', root/'archive.json'
            archive.write_bytes(body)
            manifest.write_text(json.dumps(dict(build_passed=True, archive_sha256=planning.sha(body), flash_commands=False)))
            fake = FakeLink(blank_banks(), out)
            with patch.object(live, 'ARCHIVER_SHA256', planning.sha(body)):
                result = live.capture_wdc(fake, out, cpu='65c02', archiver=archive,
                    archiver_manifest=manifest, allow_unqualified=True, message=quiet)
            self.assertFalse(result['hardware_capture'])
            self.assertFalse(result['owner_RAM_restored'])
            self.assertEqual(fake.sent, [b'G\r'])
            self.assertEqual(fake.events.count('identity'), 2)
            self.assertEqual((out/'b2.bin').read_bytes(), (out/'b2-repeat.bin').read_bytes())
            self.assertTrue((out/'owner-ram.bin').exists())
            planning.read_capture(out, '65c02', 'wdcmonv2')

    def test_execute_orders_guard_confirmation_payload_and_restoration(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            plan_root, template_sha = self.make_plan(root)
            run = live.private_root(root/'run')
            fake = FakeLink(blank_banks(), run)
            def restored(link, plan, log, state):
                self.assertTrue(state['REC_verified'])
                return dict(independent_flash_readback_verified=True, owner_RAM_restored=True, owner_ZP_restored=True)
            with patch.object(live, 'ENGINE_TEMPLATE_SHA256', template_sha):
                result = live.execute_wdc(fake, plan_root, run, allow_unqualified=True,
                                          post_rec=restored, message=quiet, pace=lambda _: None)
            self.assertTrue(result['passed'])
            self.assertFalse(result['hardware_access'])
            self.assertFalse(result['execution_qualified'])
            self.assertEqual(fake.sent[0], b'Y\r')
            self.assertEqual(len(fake.sent), 1+3*64)
            self.assertEqual(len(b''.join(fake.sent[1:])), 3*4096)
            self.assertEqual(fake.events.count(('exec', 0x2000)), 1)
            self.assertTrue((run/'erase-intent-before-execution.json').exists())

    def test_execute_cannot_claim_restoration_without_callback(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            plan_root, template_sha = self.make_plan(root)
            run = live.private_root(root/'run')
            fake = FakeLink(blank_banks(), run)
            with patch.object(live, 'ENGINE_TEMPLATE_SHA256', template_sha):
                result = live.execute_wdc(fake, plan_root, run, allow_unqualified=True, message=quiet, pace=lambda _: None)
            self.assertFalse(result['passed'])
            self.assertTrue(result['owner_RAM_restore_required'])

    def test_changed_fresh_B3_prevents_RAM_execution_and_confirmation(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            plan_root, template_sha = self.make_plan(root)
            run = live.private_root(root/'run')
            banks = blank_banks()
            banks[3][400] ^= 1
            fake = FakeLink(banks, run)
            with patch.object(live, 'ENGINE_TEMPLATE_SHA256', template_sha):
                with self.assertRaisesRegex(ValueError, 'preimage changed'):
                    live.execute_wdc(fake, plan_root, run, allow_unqualified=True, message=quiet, pace=lambda _: None)
            self.assertFalse(fake.sent)
            self.assertFalse(any(isinstance(event, tuple) and event[0] in ('load', 'exec') for event in fake.events))

    def test_recovery_adapter_keeps_pending_bytes_and_trace(self):
        class Link:
            def __init__(self):
                self.pending, self.sent = bytearray(b'ABC'), []
            def send(self, body):
                self.sent.append(body)
            def read(self, count):
                return b'Z'[:count]
        link = Link()
        stream = live.LoggedRecoveryStream(link)
        self.assertEqual(stream.read(2), b'AB')
        self.assertEqual(stream.read(2), b'C')
        self.assertEqual(stream.read(1), b'Z')
        self.assertEqual(stream.write(b'W'), 1)
        self.assertEqual(link.sent, [b'W'])

    def test_matching_BASE1_callback_binds_without_opening_port(self):
        root = Path(__file__).resolve().parents[1]
        callback = live.recovery_callback(root/'firmware/payload/STR8N-F-READBACK-RAM.bin', message=quiet)
        self.assertTrue(callable(callback))

    def test_wrong_BASE1_manifest_refuses_before_recovery(self):
        with temporary_directory() as temporary:
            root = Path(temporary)
            tool_root = Path(__file__).resolve().parents[1]
            manifest = planning.read_json(tool_root/'firmware/minimal-manifest.json')
            manifest['profile'] = 'other'
            path = root/'wrong-manifest.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'BASE1 component manifest'):
                live.recovery_callback(tool_root/'firmware/payload/STR8N-F-READBACK-RAM.bin', manifest_file=path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
