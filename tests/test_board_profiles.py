"""Optional host identity profiles: synthetic data, no serial ports or Tk."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from nf_console import load_board_profiles


class BoardProfiles(unittest.TestCase):
    def load(self,value):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'profiles.json'
            path.write_text(json.dumps(value),encoding='utf-8')
            return load_board_profiles(path)

    def test_explicit_profiles_and_empty_inventory(self):
        self.assertEqual(self.load({}),{})
        self.assertEqual(self.load({'EXAMPLE_ADAPTER_A':['Lab A','65C02']}),
                         {'EXAMPLE_ADAPTER_A':('Lab A','65C02')})

    def test_invalid_inventory_is_rejected(self):
        for value in ([],None,{'': ['Lab A','65C02']},
                      {'EXAMPLE_ADAPTER_A':'Lab A'},
                      {'EXAMPLE_ADAPTER_A':['Lab A']},
                      {'EXAMPLE_ADAPTER_A':['Lab A',5]},
                      {'EXAMPLE_ADAPTER_A':['  ','65C02']},
                      {'EXAMPLE_ADAPTER_A':['Lab\nA','65C02']}):
            with self.subTest(value=value), self.assertRaises(ValueError):self.load(value)

    def test_missing_profile_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):load_board_profiles(Path(folder)/'absent.json')


if __name__=='__main__':unittest.main()
