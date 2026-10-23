"""Offline validation and exact-byte restore checks for the history archive reader."""
import importlib.abc
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


class NoSerial(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'serial' or fullname.startswith('serial.'):
            raise AssertionError('Serial imports prohibited in history archive tests')


sys.meta_path.insert(0, NoSerial())
import restore_history as history


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary_parent = history.ROOT/'tmp';temporary_parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='history-tests-',dir=temporary_parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.archive = self.root/'archive'; self.archive.mkdir()
        self.originals = {'src/old/a.asm': b'\0\xff\r\nlegacy\n', 'tools/old.py': b'raise AssertionError("never execute")\n'}
        self.make_archive()

    def make_archive(self, entries=None, *, symlink=False):
        entries = list(self.originals.items()) if entries is None else entries
        target = self.archive/'legacy-source.zip'
        with zipfile.ZipFile(target, 'w') as archive:
            for name, body in entries:
                info = zipfile.ZipInfo(name); info.create_system = 3
                info.external_attr = (stat.S_IFLNK|0o777 if symlink else stat.S_IFREG|0o644) << 16
                archive.writestr(info, body)
        self.manifest = dict(schema=1, archive=dict(file=target.name,bytes=target.stat().st_size,sha256=history.sha(target.read_bytes())),
            files={name:dict(bytes=len(body),sha256=history.sha(body),retired=True) for name,body in entries})
        self.save_manifest()

    def save_manifest(self):
        (self.archive/'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_exact_restore_and_existing_output(self):
        manifest, members = history.verify(self.archive); self.assertEqual(members,self.originals)
        out = self.root/'restored'; result = history.restore(self.archive,out)
        self.assertFalse(result['board_access']); self.assertFalse(result['source_execution'])
        self.assertEqual({p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()},self.originals)
        with self.assertRaisesRegex(ValueError,'Fresh'): history.restore(self.archive,out)
        self.assertEqual((out/'tools/old.py').read_bytes(),self.originals['tools/old.py'])

    def test_archive_hash_and_member_hash(self):
        path = self.archive/'legacy-source.zip'; body=bytearray(path.read_bytes());body[35]^=1;path.write_bytes(body)
        with self.assertRaisesRegex(ValueError,'Archive size/hash'): history.verify(self.archive)
        self.make_archive(); self.manifest['files']['src/old/a.asm']['sha256']='0'*64;self.save_manifest()
        out=self.root/'refused'
        with self.assertRaisesRegex(ValueError,'Member bytes/hash'):history.restore(self.archive,out)
        self.assertFalse(out.exists())

    def test_duplicate_and_unsafe_entries(self):
        with self.assertWarns(UserWarning):self.make_archive([('src/a',b'a'),('src/a',b'a')])
        with self.assertRaisesRegex(ValueError,'Duplicate'):history.verify(self.archive)
        for name in ('.','../escape','src//a','src/../a','/absolute','C:/drive','src\\backslash','src/NUL.txt','src/trailing.'):
            with self.subTest(name=name):
                self.make_archive([(name,b'x')])
                with self.assertRaises(ValueError):history.verify(self.archive)
        self.make_archive([('src/a',b'link')],symlink=True)
        with self.assertRaisesRegex(ValueError,'Nonregular'):history.verify(self.archive)

    def test_inventory_and_file_directory_conflict(self):
        del self.manifest['files']['tools/old.py'];self.save_manifest()
        with self.assertRaisesRegex(ValueError,'Unexpected'):history.verify(self.archive)
        self.make_archive([('src/a',b'a'),('src/a/b',b'b')])
        with self.assertRaisesRegex(ValueError,'Conflicting'):history.verify(self.archive)
        self.make_archive([('src/A',b'a'),('src/a',b'b')])
        with self.assertRaisesRegex(ValueError,'collide'):history.verify(self.archive)

    def test_protected_output_paths(self):
        for out in (history.ROOT,history.ROOT.parent,history.ROOT/'src/new',history.ROOT/'tools/new',
                    history.ROOT/'release/new',history.ROOT/'docs/new',history.ROOT/'examples/new',history.ROOT/'tests/new',self.archive/'out'):
            with self.subTest(out=out):
                with self.assertRaises(ValueError):history.restore(self.archive,out)

    def test_allowlisted_context_archived_original_wins(self):
        context = self.root/'context';context.mkdir()
        for name,body in {'README.md':b'current readme','LICENSE':b'license','tools/old.py':b'current wrapper',
            'tools/current.py':b'current tool','tools/__pycache__/bad.pyc':b'cache','docs/guide.md':b'guide',
            'docs/evidence/private.bin':b'private','BUILD/generated.bin':b'build','output/private.bin':b'private',
            'tests/baselines/pin.json':b'{}','tests/fixtures/fixture.bin':b'fixture','src/current/x.asm':b'current'}.items():
            path=context/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        with patch.object(history,'ROOT',context):history.restore(self.archive,context/'tmp/restored',context=True)
        out=context/'tmp/restored'
        self.assertEqual((out/'tools/old.py').read_bytes(),self.originals['tools/old.py'])
        self.assertEqual((out/'tools/current.py').read_bytes(),b'current tool')
        for name in ('tools/__pycache__','docs/evidence','BUILD','output'):
            self.assertFalse((out/name).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
