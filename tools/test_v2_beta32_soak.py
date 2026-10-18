"""Host fault tests for the preserving soak; never opens a board port."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_v2_beta32_soak as soak


class RamLink:
    def __init__(self, fail_at=None, fail_restore=False):
        self.original = bytes(range(256))
        self.data = self.original
        self.writes = 0
        self.fail_at = fail_at
        self.fail_restore = fail_restore

    def dump(self, first, last):
        assert (first, last) == (0x200, 0x2FF)
        return self.data

    def write_ram(self, address, data):
        assert address == 0x200 and len(data) == 256
        self.writes += 1
        if self.writes == self.fail_at or (self.fail_restore and self.writes > self.fail_at):
            # Model a short write before the host notices an error.
            self.data = data[:128] + self.data[128:]
            raise IOError('Injected short write')
        self.data = data


class SoakTests(unittest.TestCase):
    def test_rtc_calendar_validated_and_utc_decoded(self):
        import datetime
        expected = datetime.datetime(2026, 10, 16, 7, 51, 42, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual(soak.rtc_epoch(bytes.fromhex('c2 51 07 2c 16 10 26 80 0c')), expected)
        for value in ['fa 51 07 2c 16 10 26 80 0c', 'c2 51 47 2c 16 10 26 80 0c']:
            with self.assertRaises(AssertionError): soak.rtc_epoch(bytes.fromhex(value))

    def test_pattern_success_restores_all_bytes(self):
        with tempfile.TemporaryDirectory(dir=soak.ROOT / 'output/qualification') as folder:
            link = RamLink()
            result = soak.restore_patterns(link, Path(folder), 37)
            self.assertEqual(result['patterns'], 13)
            self.assertEqual(link.data, link.original)
            self.assertFalse(json.loads((Path(folder) / 'restore-state.json').read_text())['needs_restore'])

    def test_short_write_restores_before_propagating(self):
        with tempfile.TemporaryDirectory(dir=soak.ROOT / 'output/qualification') as folder:
            link = RamLink(fail_at=3)
            with self.assertRaisesRegex(IOError, 'short write'):
                soak.restore_patterns(link, Path(folder), 0)
            self.assertEqual(link.data, link.original)
            self.assertEqual(link.writes, 4)
            self.assertFalse(json.loads((Path(folder) / 'restore-state.json').read_text())['needs_restore'])

    def test_failed_restoration_leaves_durable_recovery_record(self):
        with tempfile.TemporaryDirectory(dir=soak.ROOT / 'output/qualification') as folder:
            link = RamLink(fail_at=3, fail_restore=True)
            with self.assertRaises(IOError):
                soak.restore_patterns(link, Path(folder), 0)
            state = json.loads((Path(folder) / 'restore-state.json').read_text())
            self.assertTrue(state['needs_restore'])
            self.assertEqual(bytes.fromhex(state['original_hex']), link.original)

    def test_flash_mismatch_always_restores_bank_before_failure(self):
        class FlashLink:
            def __init__(self): self.commands = []
            def command(self, command, prompt=soak.PROMPT): self.commands.append(command)
            def dump(self, first, last, prompt=soak.PROMPT): return bytes(last - first + 1)
        link = FlashLink()
        with self.assertRaisesRegex(AssertionError, 'Flash B2 changed'):
            soak.unit(link, 'flash-2', Path('.'), {'expected_hashes': ['bad'] * 4}, b'', 0)
        self.assertEqual(link.commands, ['B2', 'B3'])

    def test_batch_length_and_line_injection_refused_before_send(self):
        link = object()
        for text in ['X' * 35, 'TIME\rJ3', 'TIME\nJ3']:
            with self.assertRaises(AssertionError): soak.batch(link, text)

    def test_batch_consumes_completion_before_final_prompt(self):
        class BatchLink:
            def command(self, command, prompt):
                assert command == 'BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q'
                assert prompt == b'BATCH done'
                return b'BM> SRAM> WORK> EDU> BATCH done'
            def until(self, prompt):
                assert prompt == soak.PROMPT
                return prompt
        self.assertTrue(soak.batch(BatchLink(), 'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q').endswith(soak.PROMPT))

    def test_sram_read_is_bounded_and_never_issues_write_request(self):
        class SramLink:
            def __init__(self): self.writes = []; self.commands = []
            def write_ram(self, address, data): self.writes.append((address, data))
            def command(self, command): self.commands.append(command)
            def dump(self, first, last):
                if first == 0x3E10:
                    result = bytearray(41); result[9] = 0x40
                    return bytes(result)
                assert (first, last) == (0x4000, 0x5FFF)
                return b'\xa5' * 8192
        with patch.object(soak, 'load_image', return_value=soak.CLIENT_HASH):
            for block in range(16):
                link = SramLink()
                result = soak.unit(link, f'sram-{block}', Path('.'), {}, b'\xa5' * 131072, 0)
                self.assertEqual(result['address'], block * 8192)
                self.assertEqual(link.writes[0], (0x3E20, b'\x01\x03\0'))
                self.assertEqual(link.writes[1][1][0], 1)  # read only
                self.assertEqual(int.from_bytes(link.writes[1][1][2:5], 'little'), block * 8192)
                self.assertEqual(link.commands, ['G 2003'])

    def test_complete_cycle_covers_all_retained_addresses_before_apps(self):
        self.assertEqual(soak.GROUPS[:4], [f'flash-{i}' for i in range(4)])
        self.assertEqual(soak.GROUPS[4:20], [f'sram-{i}' for i in range(16)])
        self.assertEqual(soak.GROUPS[-1], 'reset')
        self.assertEqual(len(soak.GROUPS), 27)


if __name__ == '__main__':
    unittest.main()
