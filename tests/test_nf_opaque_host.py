"""Narrow host protocol/admission tests; fake transport, no CPU/device access."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from nf_opaque import (Wire, ProtocolError, operate, PROMPT, HEADER_READY,
                       PAYLOAD_READY, READ_READY)
from oip import crc


class ScriptPort:
    def __init__(self, data, *, fault=None, initial=PROMPT):
        self.data, self.fault = bytes(data), fault
        self.rx = bytearray(initial)
        self.writes, self.events = [], []
        self.state, self.staged = 'command', bytearray()
        self.reads = 0
        self.before_payload = None

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, count):
        count = min(count, 7, len(self.rx))  # Exercise fragmented text and binary replies.
        result = bytes(self.rx[:count])
        del self.rx[:count]
        return result

    def flush(self):
        pass

    def write(self, data):
        self.writes.append(bytes(data))
        if self.state == 'command':
            if data == b'\x1b\r':
                self.rx.extend(b'\r\nREFUSED: I or Q\r\n'+PROMPT)
                self.events.append('cancel-prompt')
            elif data == b'I\r':
                self.events.append('I')
                if self.fault == 'refused':
                    self.rx.extend(b'REFUSED: frame/range/CRC/timeout\r\nLOCKED: RESET required\r\n')
                else:
                    self.rx.extend(b'I\r\n'+HEADER_READY)
                    self.state = 'header'
            else:
                raise AssertionError('Unexpected command '+repr(data))
        else:
            self.staged.extend(data)
            if self.state == 'header' and len(self.staged) == 20:
                packet = bytes(self.staged)
                self.staged.clear()
                assert crc(packet[:18]) == int.from_bytes(packet[18:20], 'little')
                assert packet[6:8] == b'\x03\xa0'
                if packet[5] == 0:
                    self.events.append('read-header')
                    self.reads += 1
                    current = self.data
                    if self.fault == 'wrong-after' and self.reads > 1:
                        current = bytes((self.data[0] ^ 1,))+self.data[1:]
                    checksum = crc(current)
                    if self.fault == 'crc':
                        checksum ^= 1
                    if self.fault == 'truncated':
                        self.rx.extend(READ_READY+current[:100])
                    else:
                        self.rx.extend(READ_READY+current+checksum.to_bytes(2, 'little')+
                                       b'\r\nOK: read\r\n'+PROMPT)
                    self.state = 'command'
                else:
                    self.events.append('replace-header')
                    assert int.from_bytes(packet[10:12], 'little') == crc(self.data)
                    self.expected_crc = int.from_bytes(packet[12:14], 'little')
                    self.rx.extend(PAYLOAD_READY)
                    self.state = 'payload'
            elif self.state == 'payload':
                if len(self.staged) == len(data):
                    self.events.append('payload-start')
                    if self.before_payload:
                        self.before_payload()
                if len(self.staged) == 4096:
                    assert crc(self.staged) == self.expected_crc
                    self.data = bytes(self.staged)
                    self.staged.clear()
                    self.events.append('program-complete')
                    self.rx.extend(b'OK: verified sector\r\n'+PROMPT)
                    self.state = 'command'
        return len(data)


class OpaqueHost(unittest.TestCase):
    def setUp(self):
        temporary_root = (ROOT/'build/opaque-host-tests').resolve()
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temporary_root)
        # TemporaryDirectory recursively removes only this verified workspace child.
        self.assertTrue(Path(self.directory.name).resolve().is_relative_to(temporary_root))
        self.addCleanup(self.directory.cleanup)
        self.out = Path(self.directory.name)/'run'
        # Text that looks like a protocol failure must remain opaque binary data.
        self.before = (b'REFUSED: owner bytes\r\n'+bytes(range(256))*16)[:4096]
        self.image = bytes((value ^ 0x5a for value in self.before))

    def wire(self, port):
        return Wire(port, timeout=0.02, pause=0, progress=lambda text: None)

    def test_replace_backs_up_before_payload_and_verifies_independent_read(self):
        port = ScriptPort(self.before)
        def backup_precedes_payload():
            self.assertEqual((self.out/'before.bin').read_bytes(), self.before)
            receipt = json.loads((self.out/'receipt.json').read_text())
            self.assertEqual(receipt['phase'], 'sending-replacement')
            self.assertTrue(receipt['target_may_have_changed'])
        port.before_payload = backup_precedes_payload
        result = operate(self.wire(port), 'replace', 3, 0xa0, self.out, image=self.image)
        self.assertTrue(result['passed'])
        self.assertEqual((self.out/'after.bin').read_bytes(), self.image)
        self.assertEqual(port.events, ['I', 'read-header', 'I', 'replace-header',
                                      'payload-start', 'program-complete', 'I', 'read-header'])
        self.assertEqual(result['automatic_retries'], 0)
        self.assertFalse(result['boot_settings_changed'])

    def test_read_never_sends_payload_or_replace_header(self):
        port = ScriptPort(self.before)
        result = operate(self.wire(port), 'read', 3, 0xa0, self.out)
        self.assertTrue(result['passed'])
        self.assertEqual(port.events, ['I', 'read-header'])
        self.assertFalse(result['target_may_have_changed'])

    def test_identical_image_is_no_write(self):
        port = ScriptPort(self.before)
        result = operate(self.wire(port), 'replace', 3, 0xa0, self.out, image=self.before)
        self.assertEqual(result['phase'], 'identical-no-write')
        self.assertEqual(port.events, ['I', 'read-header'])

    def test_C_D_F_rejected_before_prompt_or_output(self):
        for sector in (0xc0, 0xd0, 0xf0):
            port = ScriptPort(self.before)
            with self.subTest(sector=sector), self.assertRaises(ValueError):
                operate(self.wire(port), 'replace', 3, sector, self.out, image=self.image,
                        request_prompt=True)
            self.assertEqual(port.writes, [])
            self.assertFalse(self.out.exists())

    def test_wrong_prompt_never_sends_I_or_header(self):
        port = ScriptPort(self.before, initial=b'REC> ')
        with self.assertRaises(ProtocolError):
            operate(self.wire(port), 'replace', 3, 0xa0, self.out, image=self.image)
        self.assertEqual(port.writes, [])
        self.assertFalse(json.loads((self.out/'receipt.json').read_text())['target_may_have_changed'])

    def test_explicit_cancel_requests_fresh_fragmented_prompt(self):
        port = ScriptPort(self.before)
        result = operate(self.wire(port), 'read', 3, 0xa0, self.out, request_prompt=True)
        self.assertTrue(result['passed'])
        self.assertEqual(port.writes[0], b'\x1b\r')
        self.assertEqual(port.events[:2], ['cancel-prompt', 'I'])

    def test_refusal_stops_without_header_or_payload(self):
        port = ScriptPort(self.before, fault='refused')
        with self.assertRaises(ProtocolError):
            operate(self.wire(port), 'replace', 3, 0xa0, self.out, image=self.image)
        self.assertEqual(port.writes, [b'I\r'])

    def test_crc_and_truncation_prevent_backup_and_write(self):
        for fault in ('crc', 'truncated'):
            out = self.out.with_name(fault)
            port = ScriptPort(self.before, fault=fault)
            with self.subTest(fault=fault), self.assertRaises(ProtocolError):
                operate(self.wire(port), 'replace', 3, 0xa0, out, image=self.image)
            self.assertFalse((out/'before.bin').exists())
            self.assertNotIn('replace-header', port.events)

    def test_different_independent_readback_is_not_accepted(self):
        port = ScriptPort(self.before, fault='wrong-after')
        with self.assertRaises(ProtocolError):
            operate(self.wire(port), 'replace', 3, 0xa0, self.out, image=self.image)
        result = json.loads((self.out/'receipt.json').read_text())
        self.assertFalse(result['passed'])
        self.assertTrue(result['target_may_have_changed'])
        self.assertEqual(result['failed_phase'], 'independent-readback')
        self.assertEqual(port.events.count('payload-start'), 1)


if __name__ == '__main__':
    unittest.main()
