"""Offline protocol/refusal tests; these are not CPU or hardware executions."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rc1_dbg_full_soak_units as units
import rc1_dbg_soak_variants as variants


class BaseLink:
    def __init__(self):
        self.context = 'B3'
        self.calls, self.raw = [], []
        self.override = {}
        self.status_count = 0
        self.changed_clock = False
        self.changed_config = False
        self.config_count = 0
        self.uninitialized = False

    @staticmethod
    def wear():
        return b'\r\n'.join(f'B{b}:{a:X} 000001'.encode()
                            for b in range(4) for a in range(8, 16))

    def command(self, command, prompt=b'\r\nB3> '):
        old = self.context
        self.calls.append((old, command, prompt))
        key = (old, command)
        if key in self.override:
            return self.override[key]
        if old.startswith('B') and old != 'BM':
            values = {
                'VERSION': b'STR8-N 2.0rc1 B3 65C02\r\nBoard: 2604\r\nRunning: MONITOR B, gen 00000032',
                'APPS': b'MAINT FLASH B2\r\nSRAM FLASH B2\r\nWORK FLASH B2\r\nEDU FLASH B2\r\nASM installed B1:E000',
                'T 1': b'B1:8000 0200-079E 059F C UCHESS\r\nB1:B000 2000-4FE1 2FE2 C CLOCK',
                'T 2': b'', 'P': b'Preferred B 00000032', 'W': self.wear(),
                'TIME': b'Tue 2026-10-20 03:42:21 (-05:00)',
                '?': b'M [1 grid|2 ranges|3 wear]\r\nBATCH cmd;cmd',
                'M 1': b'   8  9  A  B  C  D  E  F',
                'M 2': b'BANK RANGE CONTENTS ACCESS',
                'M 3': b'SECTOR RANGE E/U ERASE-ATTEMPTS CONTENTS ACCESS',
                'D 8000 800F': b'8000: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F',
            }
            if command == 'C':
                self.config_count += 1
                body = b'C 00 03 F007 ' + (b'0B' if self.changed_config and self.config_count > 1 else b'0A')
            elif command in ('B1', 'B2', 'B3'):
                self.context, body = command, b''
            elif command == 'BATCH APPS;VERSION':
                assert old == 'B3' and prompt == b'BATCH done'
                self.context = 'batch-complete'
                return b'BATCH APPS;VERSION\r\nMAINT\r\nASM installed\r\n2.0rc1 gen 00000032\r\nBATCH done'
            elif command in ('MAINT', 'SRAM', 'WORK', 'EDU', 'R CLOCK'):
                targets = {'MAINT': ('BM', b'STR8-N BANK MAINT 2.4'),
                           'SRAM': ('SRAM', b'SRAM 1.4'),
                           'WORK': ('WORK', b'WORK 1.4'), 'EDU': ('EDU', b'EDU 1.4'),
                           'R CLOCK': ('CLOCK', b'CLOCK 1.11')}
                self.context, body = targets[command]
            else:
                assert command in values, ('Unexpected monitor command', command)
                body = values[command]
        elif command == 'Q':
            self.context, body = 'B3', b''
        elif old == 'BM':
            body = {'?': b'BANKS AND MEMORY\r\nNAME\r\nQ Return to monitor',
                    'NAME': b'Board: 2604', 'M': b'BANK RANGE CONTENTS ACCESS'}[command]
        elif old == 'SRAM':
            body = {'?': b'S name start end entry; R/G/D name; T C F Q',
                    'T': b'SRAM: 40' if self.uninitialized else b'Free bytes: $FF00'}[command]
        elif old == 'WORK':
            body = {'?': b'Storage not initialized.' if self.uninitialized else b'Programs: 16 KiB; workspace: 114656 bytes',
                    'HELP': b'? capacity; P 16/32/48/64 (KiB); U upgrade; V repair; F format; HELP; Q'}[command]
        elif old == 'EDU':
            assert command == '?'
            body = b'EDU OFF'
        elif old == 'CLOCK':
            if command == 'STATUS':
                self.status_count += 1
                raw = 'D1 42 08 2A 20 10 26 00 ' + ('0D' if self.changed_clock and self.status_count > 1 else '0C')
                body = (b'Running: yes\r\nCalendar valid: yes\r\nBackup enabled: yes\r\nRTC registers (raw): ' + raw.encode() +
                        b'\r\nEUI: 54:10:EC:B6:63:A4 (not remembered)')
            else:
                body = {'HELP': b'TIME/R STATUS/S EUI HISTORY SHOW n\r\nQ/QUIT',
                        'TIME': b'UTC:   Tue 2026-10-20 08:42:21',
                        'EUI': b'EUI: 54:10:EC:B6:63:A4 (not remembered)',
                        'HISTORY': b'No saved event in requested history',
                        'STATS': b'Recent estimates: minutes; year inferred; <1yr assumed.'}[command]
        else:
            raise AssertionError(('Unknown fake context', old))
        assert prompt == units.PROMPTS[self.context], (command, self.context, prompt)
        return command.encode() + b'\r\n' + body + units.PROMPTS[self.context]

    def send(self, body):
        self.raw.append(body)
        if body == b'R 1 UCHESS\r':
            assert self.context == 'B3'
            self.context = 'UCHESS'
        elif body == b'Q':
            assert self.context == 'UCHESS'
            self.context = 'uchess-exit'
        else:
            raise AssertionError(('Unexpected raw command', body))

    def until(self, token, timeout=30):
        if self.context == 'batch-complete':
            assert token == units.PROMPTS['B3']
            self.context = 'B3'
            return token
        if self.context == 'UCHESS':
            assert token == b'Microchess Copyright'
            return token
        assert self.context == 'uchess-exit' and token == units.PROMPTS['B3']
        self.context = 'B3'
        return b'Peter Jennings\r\n' + token


def s19(body):
    def row(kind, address, data):
        raw = bytes([len(data) + 3, address >> 8, address & 255]) + data
        return 'S' + kind + (raw + bytes([(~sum(raw)) & 255])).hex().upper()
    return row('1', 0x200, body) + '\n' + row('9', 0x200, b'') + '\n'


class BuiltinLink:
    def __init__(self):
        self.current = None
        self.ram = {}
        self.context = 'B3'
        self.calls = []
        self.bad_register = False
        self.bad_prompt = False
        self.bad_functions = False
        self.change_context = False
        self.stale_lifecycle = False

    def command(self, command, prompt=b'\r\nB3> '):
        self.calls.append(command)
        if command == 'G 0200':
            assert self.context == 'B3'
            self.context = 'DBG'
            case = self.current
            context = bytes([3, 2, *case['registers'], 0x24 | int(case['carry']), 255])
            if self.bad_register:
                context = context[:2] + bytes([context[2] ^ 1]) + context[3:]
            self.ram.update(enumerate(context, 0x7000))
            body = (case['console_contains'] or '').encode()
        elif command == 'C':
            assert self.context == 'DBG'
            self.context, body = 'B3', b''
            self.ram.update(enumerate(bytes(4), 0x7BFC))
            if self.stale_lifecycle:
                self.ram[0x7BFF] = 0xA5
        else:
            assert self.context == 'DBG'
            context = bytes(self.ram[a] for a in range(0x7000, 0x7007))
            if command == '?':
                body = b'C S N R U D M B BC F X'
            elif command == 'R':
                body = (f'PC={int.from_bytes(context[:2], "little"):04X} ' +
                        ' '.join(f'{name}={value:02X}' for name, value in zip('AXYPS', context[2:]))).encode()
            elif command == 'F':
                body = b'80\r\n81\r\n82\r\n83\r\n' + (b'85' if self.bad_functions else b'84') + b'\r\n'
            elif command in ('B', 'BC *'):
                body = b''
            else:
                raise AssertionError(command)
            if self.change_context and command == 'BC *':
                self.ram[0x7002] ^= 1
        assert prompt == units.PROMPTS[self.context]
        return command.encode() + b'\r\n' + body + (b'ASM> ' if self.bad_prompt else prompt)

    def dump(self, first, last, prompt=b'\r\nB3> '):
        assert prompt == units.PROMPTS[self.context]
        return bytes(self.ram.get(a, 0) for a in range(first, last + 1))


class BuiltinTransport:
    def __init__(self, cases):
        self.cases = {c['name']: c for c in cases}
        self.loads = []
        self.corrupt = False

    def load(self, link, path):
        assert link.context == 'B3'
        case = self.cases[path.stem]
        self.loads.append(path.name)
        link.current = case
        cells = dict(enumerate(bytes.fromhex(case['assembled_hex']), 0x200))
        link.ram.update(cells)
        if self.corrupt:
            link.ram[0x200] ^= 1
        return cells

    def read_range(self, link, first, last, prompt=b'\r\nB3> '):
        return link.dump(first, last, prompt)


class FullSoakUnitTests(unittest.TestCase):
    def test_base_full_flow_all_map_views_and_exact_contexts(self):
        with patch.object(units.time, 'sleep'):
            for cycle in range(3):
                link = BaseLink()
                proof, text = units.base_and_utilities(link, None, cycle)
                self.assertTrue(proof['passed'])
                self.assertEqual(set(proof['utilities']), {'MAINT', 'SRAM', 'WORK', 'EDU', 'CLOCK', 'UCHESS'})
                self.assertEqual(proof['map_view'], cycle + 1)
                self.assertEqual(set(proof['base_status_sha256']), {'C', 'P', 'W'})
                self.assertEqual([r['bank'] for r in proof['volatile_flash_reads']], [1, 2, 3])
                self.assertEqual(link.context, 'B3')
                self.assertIn(b'Microchess Copyright', text)
                self.assertEqual(link.raw, [b'R 1 UCHESS\r', b'Q'])

    def test_documented_uninitialized_queries_do_not_initialize_storage(self):
        link = BaseLink(); link.uninitialized = True
        with patch.object(units.time, 'sleep'):
            proof, _ = units.base_and_utilities(link, None, 0)
        for name in ('SRAM', 'WORK'):
            self.assertEqual(proof['utilities'][name]['storage_status'], 'uninitialized-read-only-refusal')

    def test_all_issued_commands_are_explicitly_allowed_and_no_persistent_forms(self):
        link = BaseLink()
        with patch.object(units.time, 'sleep'):
            units.base_and_utilities(link, None, 0)
        for context, command, _ in link.calls:
            self.assertIn(command, units.ALLOWED_COMMANDS[context])
        self.assertFalse(any(command.startswith(('J', 'P ', 'C ', 'SET', 'TRIM', 'OFFSET', 'BATTERY', 'ACK', 'CLEAR', 'ACCEPT')) for _, command, _ in link.calls))

    def test_allowlist_refuses_mutators_before_sending(self):
        examples = [('B3', 'B0'), ('B3', 'J3'), ('B3', 'P A'), ('B3', 'C 0'),
                    ('BM', 'NAME NEW'), ('BM', 'W 1 8000'), ('SRAM', 'C'),
                    ('SRAM', 'F'), ('SRAM', 'D TEST'), ('WORK', 'U'),
                    ('WORK', 'V'), ('WORK', 'F'), ('EDU', 'ON'),
                    ('CLOCK', 'BATTERY'), ('CLOCK', 'SET 2026-10-20 00:00:00'),
                    ('CLOCK', 'TRIM -12'), ('CLOCK', 'OFFSET -05:00'),
                    ('CLOCK', 'ACK'), ('CLOCK', 'CLEAR ALL'), ('CLOCK', 'ACCEPT EUI')]
        for context, command in examples:
            link = BaseLink()
            with self.assertRaises(AssertionError):
                units.Session(link, context).command(command)
            self.assertEqual(link.calls, [])

    def test_wrong_prompt_stops_without_sending_into_new_context(self):
        link = BaseLink(); link.override[('B3', 'MAINT')] = b'MAINT\r\nASM> '
        with self.assertRaisesRegex(AssertionError, 'Unexpected prompt'):
            units.base_and_utilities(link, None, 0)
        self.assertEqual(link.calls[-1][1], 'MAINT')

    def test_missing_semantic_output_fails_even_at_correct_prompt(self):
        link = BaseLink(); link.override[('B3', 'APPS')] = b'APPS\r\nnot an application list\r\nB3> '
        with self.assertRaisesRegex(AssertionError, 'Missing semantic output'):
            units.base_and_utilities(link, None, 0)

    def test_clock_control_change_fails_without_issuing_mutator(self):
        link = BaseLink(); link.changed_clock = True
        with self.assertRaisesRegex(AssertionError, 'RTC controls'):
            units.base_and_utilities(link, None, 0)
        self.assertEqual(link.calls[-1][1], 'STATUS')

    def test_documented_nonempty_clock_history_rows_are_inspected(self):
        link = BaseLink()
        link.override[('CLOCK', 'HISTORY')] = b'HISTORY\r\nUTC slot 2 seq 0000002A pending\r\nCLOCK> '
        with patch.object(units.time, 'sleep'):
            proof, _ = units.base_and_utilities(link, None, 0)
        self.assertTrue(proof['utilities']['CLOCK']['passed'])

    def test_configuration_change_within_unit_fails(self):
        link = BaseLink(); link.changed_config = True
        with patch.object(units.time, 'sleep'), self.assertRaisesRegex(AssertionError, 'Configuration/preference/wear'):
            units.base_and_utilities(link, None, 0)

    def test_known_uchess_context_exits_even_when_wait_sleep_raises(self):
        link = BaseLink()
        with patch.object(units.time, 'sleep', side_effect=RuntimeError('injected')), self.assertRaises(RuntimeError):
            units.base_and_utilities(link, None, 0)
        self.assertEqual(link.context, 'B3')
        self.assertEqual(link.raw[-1], b'Q')

    def setUp(self):
        # Keep fixtures in the writable workspace under the desktop sandbox.
        temporary_root = Path(__file__).resolve().parents[1] / 'tmp'
        temporary_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root, prefix='full-soak-unit-')
        self.root = Path(self.temp.name)
        self.cases = copy.deepcopy(variants.cases())
        for case in self.cases:
            case['assembled_hex'] = '7800014C677E'
            if case['family'] in units.BUILTIN_FAMILIES:
                (self.root / (case['name'] + '.s19')).write_text(s19(bytes.fromhex(case['assembled_hex'])), encoding='ascii')

    def tearDown(self):
        self.temp.cleanup()

    def test_builtins_full_flow_covers_all_services_and_rotates_seeds(self):
        for cycle, seed in enumerate((0x12, 0x25, 0x38, 0x4B)):
            link, transport = BuiltinLink(), BuiltinTransport(self.cases)
            proof, _ = units.builtins_unit(link, transport, self.cases, self.root, cycle)
            self.assertEqual(proof['seed'], seed)
            self.assertEqual(proof['services'], list(range(0x80, 0x85)))
            self.assertEqual(len(transport.loads), 4)
            self.assertEqual(link.context, 'B3')
            self.assertEqual(link.calls.count('G 0200'), 4)
            self.assertEqual(link.calls.count('C'), 4)
            self.assertTrue(proof['cases'][0]['debugger_inspection']['context_preserved'])

    def test_wrong_fixture_bytes_refused_before_any_load(self):
        path = self.root / 'text-output-12.s19'
        path.write_text(s19(bytes.fromhex('EA00014C677E')), encoding='ascii')
        transport = BuiltinTransport(self.cases)
        with self.assertRaisesRegex(AssertionError, 'load refused'):
            units.builtins_unit(BuiltinLink(), transport, self.cases, self.root, 0)
        self.assertEqual(transport.loads, [])

    def test_loaded_image_mismatch_refuses_execution(self):
        link, transport = BuiltinLink(), BuiltinTransport(self.cases); transport.corrupt = True
        with self.assertRaisesRegex(AssertionError, 'execution refused'):
            units.builtins_unit(link, transport, self.cases, self.root, 0)
        self.assertNotIn('G 0200', link.calls)

    def test_wrong_saved_context_is_not_accepted(self):
        link = BuiltinLink(); link.bad_register = True
        with self.assertRaises(AssertionError):
            units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)
        self.assertNotIn('C', link.calls)

    def test_wrong_builtin_stop_prompt_is_not_accepted(self):
        link = BuiltinLink(); link.bad_prompt = True
        with self.assertRaisesRegex(AssertionError, 'Unexpected prompt'):
            units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)

    def test_function_list_must_include_exact_five_builtins(self):
        link = BuiltinLink(); link.bad_functions = True
        with self.assertRaisesRegex(AssertionError, 'Unexpected function list'):
            units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)

    def test_inspection_must_preserve_golden_context(self):
        link = BuiltinLink(); link.change_context = True
        with self.assertRaisesRegex(AssertionError, 'Inspection changed saved context'):
            units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)

    def test_hold_cleanup_requires_invalidation_not_physical_table_zero(self):
        link = BuiltinLink(); link.ram[0x7C30] = 0xC1
        proof, _ = units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)
        self.assertTrue(proof['passed'])
        link = BuiltinLink(); link.stale_lifecycle = True
        with self.assertRaisesRegex(AssertionError, 'HOLD lifecycle'):
            units.builtins_unit(link, BuiltinTransport(self.cases), self.cases, self.root, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
