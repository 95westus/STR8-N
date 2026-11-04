"""Host-only admission tests for the newly writable B3 A/B sectors.

These do not load a CPU model or access a device.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from oip import allowed, crc, header


class MinimalPolicy(unittest.TestCase):
    def test_exact_sector_set_matches_layout(self):
        expected = {(bank, sector) for bank in range(3)
                    for sector in range(0x80, 0x100, 0x10)}
        expected |= {(3, sector) for sector in (0x80, 0x90, 0xa0, 0xb0, 0xe0)}
        actual = {(bank, sector) for bank in range(4) for sector in range(256)
                  if allowed(bank, sector)}
        self.assertEqual(actual, expected)
        layout = json.loads((ROOT/'layout.json').read_text())
        declared = {(int(bank[1]), int(sector, 16)*16)
                    for bank, sectors in layout['opaque_sectors'].items()
                    for sector in sectors}
        self.assertEqual(declared, expected)
        self.assertEqual(len(actual)*4096, layout['opaque_bytes'])

    def test_new_targets_have_valid_read_and_replace_frames(self):
        payload = bytes(range(256))*16
        for sector in (0xa0, 0xb0):
            for body in (None, payload):
                with self.subTest(sector=sector, write=body is not None):
                    packet = header(3, sector, body, 0x1234 if body is not None else 0)
                    self.assertEqual(packet[:5], b'OIP1\x01')
                    self.assertEqual(packet[6:10], bytes((3, sector, 0, 16)))
                    self.assertEqual(int.from_bytes(packet[18:20], 'little'), crc(packet[:18]))
                    if body is not None:
                        self.assertEqual(int.from_bytes(packet[12:14], 'little'), crc(payload))

    def test_journal_and_F_are_never_serialized(self):
        for sector in (0xc0, 0xd0, 0xf0):
            for body in (None, bytes(4096)):
                with self.subTest(sector=sector, write=body is not None):
                    with self.assertRaises(ValueError):
                        header(3, sector, body)

    def test_malformed_destinations_and_sizes_fail(self):
        for bank, sector in ((-1, 0x80), (4, 0x80), (3, 0xa1), (3, 0x70), (3, 0x100)):
            with self.subTest(bank=bank, sector=sector):
                with self.assertRaises(ValueError):
                    header(bank, sector)
        for size in (0, 4095, 4097):
            with self.assertRaises(ValueError):
                header(3, 0xa0, bytes(size))


if __name__ == '__main__':
    unittest.main()
