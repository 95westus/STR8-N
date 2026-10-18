"""Host-only serial lease cleanup regressions; never opens a COM port."""
import ctypes,json,os,tempfile,threading,time,unittest,warnings
from pathlib import Path
from unittest.mock import patch
import serial_test_coordination as coordination

class CleanupTests(unittest.TestCase):
    def test_priority_firmware_request_preserves_owner_kind_and_yields_soak(self):
        before=os.environ.get('STR8_DRIFT_LEASE_PID')
        with coordination.serial_lease('firmware-update',priority=True):
            self.assertTrue(coordination.drift_pending())
            self.assertEqual(json.loads((self.root/'owner.json').read_text())['kind'],'firmware-update')
            self.assertEqual(os.environ.get('STR8_DRIFT_LEASE_PID'),before)
        self.assertFalse(coordination.drift_pending())

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'output/qualification');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.scope=patch.object(coordination,'ROOT',self.root);self.scope.start();self.addCleanup(self.scope.stop)

    def test_real_windows_delete_sharing_conflict(self):
        marker=self.root/'drift-test.json';marker.write_text(json.dumps(dict(created=time.time())))
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
        api.CreateFileW.restype=ctypes.c_void_p
        api.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=api.CreateFileW(str(marker),0x80000000,3,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        timer=threading.Timer(.2,lambda:api.CloseHandle(handle));timer.start()
        try:coordination.release_marker(marker)
        finally:timer.join()
        self.assertFalse(marker.exists())

    def test_retained_released_marker_is_not_pending(self):
        real=coordination.sharing_retry
        def deny_delete(action,seconds=3):
            if 'unlink' in action.__code__.co_names:raise ctypes.WinError(32)
            return real(action,seconds)
        before=os.environ.get('STR8_DRIFT_LEASE_PID')
        with patch.object(coordination,'sharing_retry',side_effect=deny_delete),warnings.catch_warnings(record=True) as logged:
            with coordination.serial_lease('drift'):
                self.assertTrue(coordination.drift_pending())
            self.assertEqual(len(logged),1)
        self.assertFalse(coordination.drift_pending())
        self.assertEqual(os.environ.get('STR8_DRIFT_LEASE_PID'),before)
        with coordination.serial_lease('soak',timeout=1):pass

    def test_other_errors_are_not_hidden(self):
        with self.assertRaises(PermissionError):
            coordination.sharing_retry(lambda:(_ for _ in ()).throw(PermissionError('denied')))

if __name__=='__main__':unittest.main()
