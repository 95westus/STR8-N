"""Destructive image-planning invariants; no serial or firmware execution."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from nf_factory_image import prepare


class FactoryImagePlan(unittest.TestCase):
    def test_scopes_and_rejections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = bytes((i//4096) for i in range(131072))
            f = bytearray(b'\xff'*4096)
            f[0x80C:0x810] = b'SXB2'
            f[0xFFC:0xFFE] = bytes.fromhex('18 F8')
            bank = b'\xA6'*28672+f
            (root/'current.bin').write_bytes(current)
            (root/'f.bin').write_bytes(f)
            (root/'bank.bin').write_bytes(bank)
            def run(source, destination, scope='f-only', cpu='65c02'):
                with contextlib.redirect_stdout(io.StringIO()):
                    return prepare(root/'current.bin', root/source, cpu, root/destination, scope)
            p = run('f.bin', 'f-only')
            result = (root/'f-only/factory-full-chip.bin').read_bytes()
            self.assertEqual(result[:0x1F000], current[:0x1F000])
            self.assertEqual(result[0x1F000:], f)
            self.assertEqual(p['changed_sectors'], ['B3:F'])
            self.assertFalse(p['boot_wear_journal_will_be_replaced'])
            self.assertEqual((root/'f-only/previous-B3.bin').read_bytes(), current[0x18000:])
            run('bank.bin', 'bank-f-only')
            self.assertEqual((root/'bank-f-only/factory-full-chip.bin').read_bytes(), result)
            p = run('bank.bin', 'bank', 'b3')
            self.assertEqual((root/'bank/factory-full-chip.bin').read_bytes(), current[:0x18000]+bank)
            self.assertTrue(p['boot_wear_journal_will_be_replaced'])
            for source, destination, scope, cpu in (
                ('f.bin','reject-short','b3','65c02'),
                ('f.bin','reject-cpu','f-only','65c816e'),
                ('f.bin','reject-scope','all','65c02'),
            ):
                with self.assertRaises(ValueError):
                    run(source,destination,scope,cpu)
                self.assertFalse((root/destination).exists())
            with self.assertRaises(ValueError):
                run('f.bin','f-only')


if __name__ == '__main__':
    unittest.main()
