"""Integrity/refusal tests for the actual extracted beta35 review kit."""
import importlib.util
import argparse
from datetime import datetime, timezone
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('kit',type=Path,nargs='?',default=ROOT/'tmp/k35a')
parser.add_argument('--report',type=Path)
args, remaining = parser.parse_known_args()
KIT = args.kit.resolve()
sys.argv = [sys.argv[0],*remaining]
sys.path.insert(0,str(KIT))
spec = importlib.util.spec_from_file_location('kit_verify',KIT/'verify.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ReviewIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='q35-',dir=ROOT/'tmp')
        self.root = Path(self.temp.name)/'kit'
        shutil.copytree(KIT,self.root,ignore=shutil.ignore_patterns('__pycache__'))

    def tearDown(self):
        if not Path(self.temp.name).resolve().is_relative_to((ROOT/'tmp').resolve()):
            raise ValueError('Temporary cleanup target escaped workspace tmp')
        self.temp.cleanup()

    def test_exact_kit(self):
        result = verifier.verify(self.root)
        self.assertTrue(result['passed'])
        self.assertEqual((result['sources'],result['payloads'],result['mapped_ranges']),(97,18,13))

    def test_changed_clock_refused(self):
        path = self.root/'payload/clock/clock.bin'
        image = path.read_bytes()
        self.assertIn(b'CLOCK 1.10',image)
        path.write_bytes(image.replace(b'CLOCK 1.10',b'CLOCK 1.9 '))
        with self.assertRaisesRegex(ValueError,'Size/hash mismatch'):
            verifier.verify(self.root)

    def test_extra_full_bank_refused(self):
        (self.root/'payload/b0.bin').write_bytes(bytes(32768))
        with self.assertRaisesRegex(ValueError,'unexpected package files'):
            verifier.verify(self.root)

    def test_missing_source_refused(self):
        (self.root/'source/core/str8n-v2-worker.asm').unlink()
        with self.assertRaises(FileNotFoundError):
            verifier.verify(self.root)

    def test_unsafe_manifest_path_refused(self):
        path = self.root/'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files']['../outside.bin'] = {'sha256':'0'*64,'bytes':0}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Unsafe package path'):
            verifier.verify(self.root)


if __name__=='__main__':
    result = unittest.main(exit=False).result
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'kit':str(KIT),
            'finished_utc':datetime.now(timezone.utc).isoformat()},indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
