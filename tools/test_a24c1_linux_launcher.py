"""Offline Linux-launcher checks: exact WDC frames and execution gates."""
from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launcher', ROOT / 'install_a24c1_linux.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class Link:
    def __init__(self, replies):
        self.replies = bytearray(replies)
        self.wire = bytearray()

    def write(self, data):
        self.wire.extend(data)
        return len(data)

    def read(self, count):
        # Force partial reads as real USB transfers may be fragmented.
        data = bytes(self.replies[:min(count, 2)])
        del self.replies[:len(data)]
        return data


class LauncherTests(unittest.TestCase):
    def test_exact_load_read_execute_frames(self):
        data = b'\x11\x22\x33'
        link = Link(b'\xcc\0\xcc' + data + b'\xcc')
        with redirect_stdout(io.StringIO()):
            launcher.load_ram(link, 0x2000, 0x2000, data)
        self.assertEqual(bytes(link.wire),
                         b'\x55\xaa\x02\x00\x20\x00\x03\x00\x00' + data +
                         b'\x55\xaa\x03\x00\x20\x00\x03\x00\x00' +
                         b'\x55\xaa\x06\x00\x20\x00')
        self.assertFalse(link.replies)

    def test_mismatch_never_executes(self):
        link = Link(b'\xcc\0\xcc\x99')
        with self.assertRaisesRegex(OSError, 'readback mismatch'):
            launcher.load_ram(link, 0x2000, 0x2000, b'\x11')
        self.assertNotIn(b'\x55\xaa\x06', link.wire)

    def test_failed_ack_never_reads_or_executes(self):
        link = Link(b'\xcc\x01')
        with self.assertRaisesRegex(OSError, 'rejected RAM write'):
            launcher.load_ram(link, 0x2000, 0x2000, b'\x11')
        self.assertNotIn(b'\x55\xaa\x03', link.wire)
        self.assertNotIn(b'\x55\xaa\x06', link.wire)

    def test_sync_and_timeout(self):
        with self.assertRaisesRegex(OSError, 'sync expected CC'):
            launcher.command(Link(b'\x0d'), 0x0C)
        with self.assertRaisesRegex(OSError, 'timeout'):
            launcher.command(Link(b''), 0x0C)

    def test_board_reply(self):
        link = Link(b'\xccSXB2\x2c\x01\0\0\xc8\0\0\0')
        self.assertEqual(launcher.board_info(link), ('SXB2', 3.0, 2.0))
        self.assertEqual(link.wire, b'\x55\xaa\x0c')

    def test_checksum_refused(self):
        with patch.object(Path, 'read_text', return_value='S10420001100\nS9032000DC\n'):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                launcher.read_s19(Path('bad.s19'))

    def test_current_installer_and_maintenance(self):
        for path in (
            ROOT / 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-wdcmonv2-install-2000.s19',
            ROOT / 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19',
        ):
            first, entry, data = launcher.read_s19(path)
            self.assertEqual((first, entry), (0x2000, 0x2000))
            self.assertGreater(len(data), 0)

    def test_colors(self):
        self.assertEqual(launcher.board_color('MIGRATION VERIFIED; PRESS PHYSICAL RESET'), 'yellow')
        self.assertEqual(launcher.board_color('REFUSE: INVALID'), 'red')
        self.assertEqual(launcher.board_color('BACKUP VERIFIED'), 'green')

    @unittest.skipUnless(os.name == 'posix', 'requires a POSIX terminal')
    def test_posix_terminal_transfer_and_restore(self):
        import pty
        import termios
        master, slave = pty.openpty()
        before = termios.tcgetattr(slave)
        link = Link(b'')
        link.in_waiting = 0
        core = ROOT / 'BUILD/v2-a24c1-wdcmon-ram/str8n-v2-a24c1-f000-ffff.bin'
        maint = ROOT / 'BUILD/bank-maint-v2/str8n-bank-maint-2000.s19'
        try:
            with patch.object(launcher.sys, 'stdin') as stdin, \
                 patch.object(launcher.select, 'select', return_value=([slave], [], [])), \
                 patch.object(launcher.os, 'read', side_effect=[b'\x15', b'\x1d']), \
                 patch.object(launcher.time, 'sleep'), redirect_stdout(io.StringIO()):
                stdin.fileno.return_value = slave
                launcher.terminal(link, core, maint)
            self.assertEqual(bytes(link.wire), core.read_bytes())
            self.assertEqual(termios.tcgetattr(slave), before)
        finally:
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
