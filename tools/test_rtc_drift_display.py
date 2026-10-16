"""Read-only drift preflight accepts retained and current console wording."""
import unittest
from unittest.mock import patch
from capture_rtc_drift_status import valid_time_display, identity_fields, launch_clock, CLOCK18_SHA256


class DisplayTests(unittest.TestCase):
    def test_missing_flash_clock_uses_verified_ram_image(self):
        class Link:
            def __init__(self): self.commands = []
            def command(self, command, prompt):
                self.commands.append(command)
                return b'SR error 05\r\nB3> ' if command == 'R CLOCK' else b'CLOCK 1.8\r\nCLOCK> '
        link = Link()
        with patch('capture_rtc_drift_status.load_image', return_value=CLOCK18_SHA256):
            self.assertTrue(launch_clock(link).endswith(b'CLOCK> '))
        self.assertEqual(link.commands, ['R CLOCK', 'G 2000'])

    def test_wrong_ram_image_cannot_execute(self):
        class Link:
            def command(self, command, prompt):
                assert command == 'R CLOCK'
                return b'SR error 05\r\nB3> '
        with patch('capture_rtc_drift_status.load_image', return_value='wrong'):
            with self.assertRaises(AssertionError): launch_clock(Link())

    def test_time_formats(self):
        for line in (b'RTCC: UTC 2026-10-16 16:56:40',
                     b'RTCC: UTC Fri 2026-10-16 16:56:40',
                     b'Fri 2026-10-16 11:56:40 (-05:00)'):
            self.assertTrue(valid_time_display(b'TIME\r\n\r\n' + line + b'\r\nB3> '))

    def test_unavailable_is_not_a_time(self):
        for line in (b'RTCC: unavailable', b'RTCC: Time unavailable', b'Bad cmd'):
            self.assertFalse(valid_time_display(line))

    def test_bound_identity_formats(self):
        for line in (b'RTCC: EUI 54:10:EC:B6:64:D3, matches remembered',
                     b'EUI: 54:10:EC:B6:64:D3 (matches remembered)'):
            self.assertEqual(identity_fields(line), ('54:10:EC:B6:64:D3', True))

    def test_unbound_identity_formats(self):
        for line in (b'RTCC: EUI 54:10:EC:B6:63:A4, unbound',
                     b'EUI: 54:10:EC:B6:63:A4 (not remembered)'):
            self.assertEqual(identity_fields(line), ('54:10:EC:B6:63:A4', False))

    def test_changed_or_missing_identity_refused(self):
        for line in (b'EUI unavailable', b'RTCC: EUI 54:10:EC:B6:64:D3, changed'):
            with self.assertRaises(AssertionError): identity_fields(line)


if __name__ == '__main__':
    unittest.main()
