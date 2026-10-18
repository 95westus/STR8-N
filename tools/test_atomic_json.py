"""Host-only atomic publication regressions; no board access."""
import ctypes,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from atomic_json import publish

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'output/qualification')
        self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'status.json'
        publish(self.path,dict(old=True))

    def test_windows_reader_temporarily_blocks_replace(self):
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
        api.CreateFileW.restype=ctypes.c_void_p;api.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=api.CreateFileW(str(self.path),0x80000000,3,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        timer=threading.Timer(.2,lambda:api.CloseHandle(handle));timer.start()
        try:publish(self.path,dict(new=True))
        finally:timer.join()
        self.assertEqual(json.loads(self.path.read_text()),dict(new=True))

    def test_timeout_preserves_previous_document(self):
        with patch('atomic_json.os.replace',side_effect=ctypes.WinError(5)):
            with self.assertRaises(OSError):publish(self.path,dict(new=True),timeout=.01)
        self.assertEqual(json.loads(self.path.read_text()),dict(old=True))

    def test_concurrent_publishers_use_distinct_staging(self):
        errors=[]
        def one(n):
            try:publish(self.path,dict(writer=n,payload='x'*10000))
            except Exception as e:errors.append(e)
        workers=[threading.Thread(target=one,args=(n,)) for n in range(8)]
        for worker in workers:worker.start()
        for worker in workers:worker.join()
        self.assertFalse(errors);self.assertEqual(len(json.loads(self.path.read_text())['payload']),10000)
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

if __name__=='__main__':unittest.main()
