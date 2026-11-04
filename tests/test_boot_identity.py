"""Static identity/freeze checks and malformed record rejection; no CPU/device."""
import sys
import json
import hashlib
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from boot_identity import decode


class BootIdentity(unittest.TestCase):
    def image(self):return (ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    def test_name_version_generation_and_private_contract(self):
        actual=decode(self.image());expected=json.loads((ROOT/'identity.json').read_text())
        for name in ('product','F_version','F_generation','profile','private_contract','public_ABI_major'):
            self.assertEqual(actual[name],expected[name])
        self.assertIn(b'STR8N-F 0.3.0 g00000001\r\nBASE1 / PR05\r\n',self.image())
        self.assertNotIn(b'EDU ON',self.image())
        self.assertNotEqual(actual['F_generation'],expected['SNBT_monitor_generation'])
    def test_frozen_bytes_and_sources(self):
        lock=json.loads((ROOT/'F_FREEZE.json').read_text())
        self.assertEqual(hashlib.sha256(self.image()).hexdigest(),lock['sha256'])
        for name,digest in lock['sources'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
    def test_absent_or_out_of_range_locator_refused(self):
        for pointer in (0,0xefff,0xffe0):
            image=bytearray(self.image());image[0x3e:0x40]=pointer.to_bytes(2,'little')
            with self.assertRaises(ValueError):decode(image)
        image=bytearray(self.image());image[0x3c:0x3e]=b'XX'
        with self.assertRaises(ValueError):decode(image)
    def test_identity_corruption_refused(self):
        image=bytearray(self.image());where=int.from_bytes(image[0x3e:0x40],'little')-0xf000
        image[where+20]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):decode(image)


if __name__=='__main__':unittest.main()
