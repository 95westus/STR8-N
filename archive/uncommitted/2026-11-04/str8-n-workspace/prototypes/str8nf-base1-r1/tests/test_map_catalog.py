"""Narrow catalogue logic tests with synthetic banks; no vendor bytes/CPU/device."""
import hashlib
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import map_catalog as catalog


class MapCatalogue(unittest.TestCase):
    def bank(self,signature=b'SXB2'):
        body=bytearray(b'\xff'*32768)
        body[-2048:]=bytes(range(256))*8
        body[0x780c:0x7810]=signature
        body[-4:-2]=(0xf818).to_bytes(2,'little')
        return body
    def profile(self,bank):
        p=dict(catalog.PROFILES[0]);p.update(catalog.fingerprints(bank[-2048:]));return p
    def test_known_resident_is_not_whole_bank_or_boot_validation(self):
        bank=self.bank();profile=self.profile(bank)
        result=catalog.identify(bank,[profile])
        self.assertEqual(result['mark'],'W+')
        self.assertEqual(result['version'],'2.00')
        self.assertIsNone(result['generation'])
        self.assertFalse(result['whole_bank_recognized'] or result['bootability_verified'])
    def test_lower_bank_changes_do_not_change_resident_recognition(self):
        bank=self.bank();profile=self.profile(bank);bank[:4096]=b'X'*4096
        self.assertEqual(catalog.identify(bank,[profile])['mark'],'W+')
    def test_resident_modification_is_only_possible_WDC(self):
        bank=self.bank();profile=self.profile(bank);bank[-400]^=1
        result=catalog.identify(bank,[profile])
        self.assertEqual(result['mark'],'W?');self.assertIsNone(result['version'])
    def test_signature_without_vector_is_not_WDC(self):
        bank=self.bank();bank[-4:-2]=b'\xff\xff'
        self.assertEqual(catalog.identify(bank)['mark'],'U+')
    def test_text_elsewhere_does_not_identify_image(self):
        bank=bytearray(b'\xff'*32768);bank[0x7000:0x7008]=b'WDCMONv2'
        self.assertEqual(catalog.identify(bank)['mark'],'U+')
    def test_erased_and_bad_size(self):
        self.assertEqual(catalog.identify(bytes([255])*32768)['mark'],'..')
        with self.assertRaises(ValueError):catalog.identify(bytes(4096))
    def test_assembler_catalog_tracks_public_fingerprints(self):
        self.assertEqual((ROOT/'src/core/map-wdc-catalog.inc').read_text(),catalog.assembler_catalog())
        self.assertNotIn('board',catalog.assembler_catalog().lower())


if __name__=='__main__':unittest.main()
