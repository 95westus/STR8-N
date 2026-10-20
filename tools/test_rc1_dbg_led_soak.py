"""Pure LED oracle/protocol/refusal tests; no CPU, serial or board execution."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import rc1_dbg_led_soak as led


FAKE_IMAGE = bytes.fromhex('7800014C677E')


def qualified_case(seed=0x12):
    case = next(c for c in led.cases() if c['seed'] == seed)
    case['assembled_hex'] = FAKE_IMAGE.hex()
    return case


def metadata(seed, original=0):
    # IRQ flags can change without a change in the six CRA control bits.
    return bytes([0xA5, original, 0x34, original, 0x34, 0, 8, 2,
                  seed, 0, 7, 0xB4, 0x74, 0])


class FakeLink:
    def __init__(self, case):
        self.case = case
        self.context = 'B3'
        self.calls = []
        self.image = bytes.fromhex(case['assembled_hex'])
        self.meta = metadata(case['seed'])
        self.writes = self.readbacks = bytes(led.frame_values(case['seed']))
        self.lifecycle = bytes(4)
        self.stop = bytes.fromhex('030200000034FF')
        self.bad_assembly = False
        self.bad_loaded_image = False
        self.changed_after_run = False
        self.g_runs = 0

    def command(self, text, prompt=led.B3):
        self.calls.append((self.context, text, prompt))
        if self.context == 'B3' and text == 'ASM':
            self.context, body = 'ASM', b'ASM 0.5'
        elif self.context == 'ASM':
            if text == 'QUIT':
                self.context, body = 'B3', b''
            elif text == 'ASM':
                body = f'OK {len(self.image) + int(self.bad_assembly)} bytes'.encode()
            else:
                assert text in ('NEW', 'DUMP', 'S19') or text in self.case['lines']
                body = b''
        elif self.context == 'B3' and text == 'G 0200':
            self.context, body = 'DBG', b'DBG1 BRK 01'
            self.g_runs += 1
        elif self.context == 'DBG' and text == 'C':
            self.context, body = 'B3', b''
        else:
            raise AssertionError(('Unexpected fake LED command', self.context, text))
        assert prompt == {'ASM': led.ASM, 'B3': led.B3, 'DBG': led.DBG}[self.context]
        return text.encode() + b'\r\n' + body + b'\r\n' + prompt

    def dump(self, first, last, prompt=led.B3):
        if first == 0x7000 and last == 0x7006:
            assert self.context == 'DBG' and prompt == led.DBG
            return self.stop
        assert first == 0x7BFC and last == 0x7BFF and self.context == 'B3'
        return self.lifecycle

    def read_range(self, link, first, last, prompt=led.B3):
        assert link is self
        if first == led.ENTRY:
            assert last == led.ENTRY + len(self.image) - 1
            if self.bad_loaded_image or self.changed_after_run and self.g_runs:
                return bytes([self.image[0] ^ 1]) + self.image[1:]
            return self.image
        assert self.context == 'DBG' and prompt == led.DBG
        for address, body in [(led.META, self.meta), (led.WRITE_TRACE, self.writes),
                              (led.READ_TRACE, self.readbacks)]:
            if first == address:
                assert last == address + len(body) - 1
                return body
        raise AssertionError(('Unexpected fake RAM read', first, last))


class LedTests(unittest.TestCase):
    def run_unit(self, link, *, check_timing=True, elapsed=7.95):
        with patch.object(led.time, 'monotonic', side_effect=[0, elapsed]):
            return led.led_unit(link, SimpleNamespace(read_range=link.read_range),
                                link.case, check_timing=check_timing)

    def test_all_four_oracles_are_complete_and_cyclic(self):
        for seed in led.SEEDS:
            with self.subTest(seed=seed):
                values = led.frame_values(seed)
                self.assertEqual(len(values), 520)
                self.assertEqual(values[:8], [0xF0, 0x0F] * 4)
                gray, count = values[8:264], values[264:]
                self.assertEqual(set(gray), set(range(256)))
                self.assertEqual(set(count), set(range(256)))
                for i in range(256):
                    self.assertEqual((gray[i] ^ gray[(i + 1) % 256]).bit_count(), 1)
                    self.assertEqual(count[i], (seed + i) & 255)

    def test_invalid_seed_refused(self):
        for seed in (-1, 256, True, 0.5, '18'):
            with self.subTest(seed=seed), self.assertRaises(AssertionError):
                led.frame_values(seed)

    def test_source_properties_and_four_distinct_variants(self):
        cases = led.cases()
        self.assertEqual(len({tuple(c['lines']) for c in cases}), 4)
        for case in cases:
            source = '\n'.join(case['lines'])
            self.assertEqual([int(x.split(' ', 1)[0]) for x in case['lines']],
                             list(range(10, 10 * len(case['lines']) + 1, 10)))
            self.assertIn('AND #$3F', source)
            self.assertIn('CMP #$34', source)
            self.assertNotIn('STA $7FA1', source)
            self.assertNotIn('STZ $7FA1', source)
            self.assertEqual(source.count('STA $7FA0'), 4)  # Three phase loops, one restore.
            self.assertIn('BRK $01', source)
            self.assertIn('JMP $7E67', source)
            self.assertFalse(case['native_applications'])
            self.assertFalse(case['native_debugging'])

    def test_all_four_oracles_accept_saved_display_and_volatile_flags(self):
        for seed in led.SEEDS:
            values = bytes(led.frame_values(seed))
            proof = led.check_result(qualified_case(seed), metadata(seed, 0xA5), values, values,
                                     expected_entry_led=0xA5)
            self.assertTrue(proof['original_led_restored_before_BRK'])
            self.assertTrue(proof['actual_pin_readback_matches_every_frame'])
            self.assertEqual(proof['frames'], 520)

    def test_all_four_protocol_units(self):
        for seed in led.SEEDS:
            link = FakeLink(qualified_case(seed))
            proof, transcript = self.run_unit(link)
            self.assertTrue(proof['passed'])
            self.assertEqual(proof['elapsed_seconds'], 7.95)
            self.assertEqual(proof['HOLD_cleanup']['lifecycle_hex'], '00000000')
            self.assertIn(b'BRK 01', transcript)
            self.assertEqual(link.context, 'B3')
            self.assertEqual(link.g_runs, 1)
            self.assertIn(('DBG', 'C', led.B3), link.calls)

    def test_unqualified_case_refused_before_assembly(self):
        link = FakeLink(qualified_case())
        del link.case['assembled_hex']
        with self.assertRaises(KeyError):
            self.run_unit(link)
        self.assertFalse(link.calls)

    def test_changed_canonical_source_or_oracle_refused(self):
        for key, value in [('lines', ['10 ORG $0200', '20 STA $7FA1']),
                           ('frame_count', 8), ('expected_frame_hex', '00')]:
            link = FakeLink(qualified_case())
            link.case[key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.run_unit(link)
            self.assertFalse(link.calls)

    def test_code_overlap_or_wrong_exit_refused(self):
        for body in (b'\xEA' * 1025, b'\xEA\xEA'):
            case = qualified_case()
            case['assembled_hex'] = body.hex()
            with self.assertRaises(AssertionError):
                led.validate_case(case)

    def test_wrong_assembler_size_refuses_execution(self):
        link = FakeLink(qualified_case())
        link.bad_assembly = True
        with self.assertRaises(AssertionError):
            self.run_unit(link)
        self.assertEqual(link.g_runs, 0)

    def test_wrong_exact_image_refuses_execution(self):
        link = FakeLink(qualified_case())
        link.bad_loaded_image = True
        with self.assertRaises(AssertionError):
            self.run_unit(link)
        self.assertEqual(link.g_runs, 0)

    def test_malformed_context_returns_through_known_hold(self):
        for body in (b'', bytes.fromhex('020200000034FF'), bytes.fromhex('030201000034FF'),
                     bytes.fromhex('030200000035FF'), bytes.fromhex('030200000034FE')):
            link = FakeLink(qualified_case())
            link.stop = body
            with self.subTest(body=body.hex()), self.assertRaises(AssertionError):
                self.run_unit(link)
            self.assertEqual(link.context, 'B3')

    def test_bad_metadata_returns_through_known_hold(self):
        for index, value in [(0, 0xE1), (0, 0xE2), (0, 0xE3), (0, 0xE4), (1, 1),
                             (2, 0x30), (3, 1), (4, 0x35), (5, 1), (6, 7),
                             (7, 1), (8, 0x25), (9, 1), (10, 3), (11, 0x30),
                             (12, 0x35), (13, 1)]:
            link = FakeLink(qualified_case())
            raw = bytearray(link.meta)
            raw[index] = value
            link.meta = bytes(raw)
            with self.subTest(index=index, value=value), self.assertRaises(AssertionError):
                self.run_unit(link)
            self.assertEqual(link.context, 'B3')

    def test_each_trace_must_equal_oracle(self):
        for key in ('writes', 'readbacks'):
            link = FakeLink(qualified_case())
            raw = bytearray(getattr(link, key))
            raw[300] ^= 1
            setattr(link, key, bytes(raw))
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.run_unit(link)
            self.assertEqual(link.context, 'B3')

    def test_short_or_long_elapsed_refused_after_safe_hold(self):
        for elapsed in (5.99, 20.01):
            link = FakeLink(qualified_case())
            with self.subTest(elapsed=elapsed), self.assertRaises(AssertionError):
                self.run_unit(link, elapsed=elapsed)
            self.assertEqual(link.context, 'B3')

    def test_model_can_disable_wall_timing_explicitly(self):
        proof, _ = self.run_unit(FakeLink(qualified_case()), check_timing=False, elapsed=300)
        self.assertFalse(proof['wall_timing_checked'])

    def test_stale_hold_lifecycle_refused(self):
        link = FakeLink(qualified_case())
        link.lifecycle = bytes.fromhex('000000A5')
        with self.assertRaises(AssertionError):
            self.run_unit(link)

    def test_modified_code_after_run_refused(self):
        link = FakeLink(qualified_case())
        link.changed_after_run = True
        with self.assertRaises(AssertionError):
            self.run_unit(link)


if __name__ == '__main__':
    unittest.main()
