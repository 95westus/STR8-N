"""Buffered read-only backup checks; no serial modules or ports."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as h


def main():
    b = h.board; banks = h.expected_banks()
    ram = bytes((n * 11 + 5) & 255 for n in range(0x6300)); zp = bytes(range(0xe0))
    cases = []
    class Link:
        def command(self, text):
            assert text == ''; return b.MON_PROMPT
        def dump(self, first, last):
            return {(0x7d01, 0x7d02): b'\x02\x03', (0x7d30, 0x7d30): b'\xb0', (0, 0xdf): zp}[(first, last)]
    for fault in (False, True):
        with tempfile.TemporaryDirectory(prefix='reset-ff-ro-', dir=h.ROOT / 'tmp') as tmp:
            repeated = list(banks)
            if fault:
                bad = bytearray(repeated[0]); bad[0] ^= 1; repeated[0] = bytes(bad)
            with patch.object(b.workflow, 'read_range', return_value=ram), \
                 patch.object(b.workflow, 'flash', side_effect=[banks, repeated]):
                try:
                    h.backup(Link(), Path(tmp))
                except ValueError:
                    assert fault and not (Path(tmp) / 'capture').exists()
                else:
                    assert not fault
                    identity, _ = b.capture.validate(Path(tmp) / 'capture')
                    assert identity['owner_zp_sha256'] == b.r.sha(zp)
                    assert (Path(tmp) / 'capture/owner-zp.bin').read_bytes() == zp
                    assert b.r.read(Path(tmp) / 'backup.json')['fsynced_before_any_execution']
            cases.append(dict(case='different-repeat-refused' if fault else 'repeated-read-only-escrow', passed=True))
    h.auth_check(dict(owner_authorized=True, action='reset-ff-ram-read-only-preflight', board='2512',
        usb_serial='A10MQFLCA', flash_writes_authorized=False, other_boards_authorized=False, RTC_campaign_resume_authorized=False))
    cases.append(dict(case='exact-read-only-scope', passed=True))
    assert 'serial' not in sys.modules
    h.save(HERE / 'preflight-host-tests.json', dict(passed=True, hardware=False, serial_access=False,
        checks=len(cases), cases=cases, helper_sha256=b.r.sha(Path(h.__file__).read_bytes()),
        checker_sha256=b.r.sha(Path(__file__).read_bytes())))
    print('PASS buffered preflight', len(cases), flush=True)


if __name__ == '__main__': main()
