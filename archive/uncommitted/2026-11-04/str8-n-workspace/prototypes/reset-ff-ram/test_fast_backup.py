"""Buffered fast-backup preservation/failure tests; never imports serial."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_backup as h


def main():
    b, r = h.board, h.r
    banks = h.pf.expected_banks()
    original = bytes((n * 29 + 17 + (n >> 8)) & 255 for n in range(0x6300))
    owner_zp = bytes(range(0xe0))
    cases = []

    class Fixture:
        def __init__(self, root, fault=None):
            self.args = argparse.Namespace(run=root / 'run', marker=root / 'marker.json', stage='backup')
            self.args.run.mkdir()
            self.marker = dict(board='2512', application_RAM_restore_pending=False, physical_reset_pending=False,
                               block_snapshot=False, reset_ff_worker_active=False)
            h.pf.save(self.args.marker, self.marker)
            self.before = self.args.marker.read_bytes()
            h.pf.atomic(self.args.run / 'device-marker-before.json', self.before)
            self.ram = bytearray(original); self.zp = owner_zp; self.console = 3
            self.fault = fault; self.reads = []; self.flashes = 0; self.loads = []; self.shims = 0; self.zp_reads = 0
            self.startups = 0

        def command(self, text):
            assert text == ''
            return b.MON_PROMPT

        def dump(self, first, last):
            if (first, last) == (0, 0xdf):
                self.zp_reads += 1
                return bytes([self.zp[0] ^ 1]) + self.zp[1:] if self.fault == 'fresh-zp' and self.zp_reads == 2 else self.zp
            return {(0x7d01, 0x7d01): b'\x02', (0x7d01, 0x7d02): bytes([2, self.console]),
                    (0x7d30, 0x7d30): b'\xb0'}[(first, last)]

        def until(self, prompt, timeout):
            assert prompt == b.MON_PROMPT and timeout == 60
            return b'Boot : 3 2 1 0\r\nSTR8-N 2.0proto b07 B3 65C02' + b.MON_PROMPT

        def read_range(self, link, first, last):
            assert link is self and (first, last) == (0x200, 0x64ff)
            self.reads.append(self.console)
            if self.fault == 'fresh-ram' and len(self.reads) == 2:
                return bytes([self.ram[0] ^ 1]) + bytes(self.ram[1:])
            if self.fault == 'final-ram' and self.startups:
                return bytes([self.ram[0] ^ 1]) + bytes(self.ram[1:])
            return bytes(self.ram)

        def flash(self, link):
            assert link is self
            self.flashes += 1
            if self.fault == 'banks' and self.flashes == 2:
                bad = bytearray(banks[0]); bad[0] ^= 1
                return [bytes(bad), *banks[1:]]
            return banks

        def select(self, link, build, expected, run, phase):
            assert link is self and expected == banks and phase == 'fast-backup'
            ram, zp = h.validate_escrow(self.args)
            assert ram == original and zp == owner_zp and len(self.reads) == 2 and self.zp_reads == 2
            assert r.read(self.args.marker)['application_RAM_restore_pending'] is True
            assert (run / 'device-marker-before.json').read_bytes() == self.before
            self.shims += 1
            old = bytes(self.ram[0x1e00:0x1e0d])
            self.ram[0x1e00:0x1e0d] = bytes.fromhex('78D8A9018D027D20797E4C60B1')
            self.console = 1
            if self.fault == 'shim-interrupted':
                raise OSError('buffered transport interruption after shim borrow')
            h.pf.save(run / 'ftdi-session-fast-backup.json', dict(borrowed_address=0x2000,
                                                               borrowed_original_hex=old.hex()))

        def load(self, link, address, data):
            assert link is self and address == 0x2000 and len(data) == 13
            assert bytes(data) == original[0x1e00:0x1e0d]
            self.loads.append((address, bytes(data)))
            self.ram[0x1e00:0x1e0d] = data

        def startup(self, link, run, phase):
            assert link is self and bytes(self.ram) == original and phase == 'fast-backup-final-BOTH'
            assert self.loads and self.reads[-3:] == [self.console] * 3
            self.startups += 1; self.console = 3
            return b'\r\nWAIT...\r\n' + b.CHOICES

        @contextmanager
        def patched(self):
            with patch.object(b.workflow, 'read_range', side_effect=self.read_range), \
                 patch.object(b.workflow, 'flash', side_effect=self.flash), \
                 patch.object(b, 'select_ftdi', side_effect=self.select), \
                 patch.object(b, 'load_ram_span', side_effect=self.load), \
                 patch.object(b, 'software_startup', side_effect=self.startup):
                yield

    def passed(name):
        cases.append(dict(case=name, passed=True))

    with tempfile.TemporaryDirectory(prefix='ff-fast-good-', dir=h.pf.ROOT / 'tmp') as tmp:
        f = Fixture(Path(tmp))
        with f.patched():
            h.perform_backup(f.args, f, f.marker)
        result = r.read(f.args.run / 'backup.json')
        assert result['kind'] == h.KIND and result['RAM_written'] and not result['flash_written']
        assert result['RAM_borrowed_and_restored'] and result['RAM_restored'] and result['ZP_preserved']
        assert f.args.marker.read_bytes() == f.before and bytes(f.ram) == original and f.zp == owner_zp
        assert f.shims == 1 and len(f.loads) == 1 and f.flashes == 2 and f.reads == [3, 3, 1, 1, 1, 3]
        assert r.read(f.args.run / 'preflight.json')['stage'] == 'fast-backup'
        assert r.read(f.args.run / 'preflight.json')['serial_released'] is False
        h.finish_closed(f.args)
        assert r.read(f.args.run / 'preflight.json')['serial_released'] is True
        b.capture.validate(f.args.run / 'capture')
        passed('fresh-RAM2-ZP2-fsynced-before-single-qualified-shim')
        passed('flash2-exact-and-13-byte-restore-full-RAM3-final-BOTH-RAM1-ZP2')
        passed('original-marker-byte-exact-and-native-capture-schema2')

    for fault in ('fresh-ram', 'fresh-zp'):
        with tempfile.TemporaryDirectory(prefix='ff-fast-refuse-', dir=h.pf.ROOT / 'tmp') as tmp:
            f = Fixture(Path(tmp), fault)
            with f.patched():
                try:
                    h.perform_backup(f.args, f, f.marker)
                except ValueError:
                    assert f.shims == 0 and f.flashes == 0 and f.args.marker.read_bytes() == f.before
                    assert not (f.args.run / 'capture').exists()
                else:
                    raise AssertionError('Different fresh escrow was accepted')
        passed(fault + '-difference-refused-before-G-or-marker-mutation')

    for fault in ('banks', 'shim-interrupted'):
        with tempfile.TemporaryDirectory(prefix='ff-fast-recover-', dir=h.pf.ROOT / 'tmp') as tmp:
            f = Fixture(Path(tmp), fault)
            with f.patched():
                try:
                    h.perform_backup(f.args, f, f.marker)
                except (ValueError, OSError):
                    assert h.validate_escrow(f.args) == (original, owner_zp)
                    assert r.read(f.args.marker)['application_RAM_restore_pending']
                    assert not (f.args.run / 'backup.json').exists()
                else:
                    raise AssertionError('Injected failure not surfaced')
                f.fault = None
                h.perform_restore(f.args, f, f.marker)
            assert bytes(f.ram) == original and f.args.marker.read_bytes() == f.before and f.shims == 1
            assert r.read(f.args.run / 'state.json')['passed']
        passed(fault + '-retains-escrow-and-restore-only-runs-no-new-G')

    with tempfile.TemporaryDirectory(prefix='ff-fast-final-', dir=h.pf.ROOT / 'tmp') as tmp:
        f = Fixture(Path(tmp), 'final-ram')
        with f.patched():
            try:
                h.perform_backup(f.args, f, f.marker)
            except ValueError:
                assert r.read(f.args.marker)['application_RAM_restore_pending']
                assert not (f.args.run / 'backup.json').exists()
            else:
                raise AssertionError('Final RAM mismatch accepted')
    passed('final-BOTH-RAM-mismatch-keeps-pending-and-withholds-receipt')

    with tempfile.TemporaryDirectory(prefix='ff-fast-escrow-', dir=h.pf.ROOT / 'tmp') as tmp:
        f = Fixture(Path(tmp)); h.early_escrow(f.args, original, owner_zp)
        (f.args.run / 'capture/owner-zp.bin').write_bytes(bytes(0xe0))
        try:
            h.validate_escrow(f.args)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed escrow accepted')
    passed('corrupt-escrow-refused-before-restoration')

    auth = dict(owner_authorized=True, action='reset-ff-ram-fast-backup', board='2512', usb_serial='A10MQFLCA',
                RAM_writes_authorized=True, flash_writes_authorized=False, other_boards_authorized=False,
                RTC_campaign_resume_authorized=False, backup_helper_sha256=r.sha(Path(h.__file__).read_bytes()))
    h.auth_check(auth)
    for key, value in (('board', '2609'), ('flash_writes_authorized', True), ('RAM_writes_authorized', False)):
        try:
            h.auth_check(dict(auth, **{key: value}))
        except ValueError:
            pass
        else:
            raise AssertionError('Wrong authorization scope accepted')
    passed('2512-only-no-flash-exact-helper-authorization')
    assert 'serial' not in sys.modules and 'serial.tools.list_ports' not in sys.modules
    passed('production-import-and-buffered-tests-no-serial-import')
    h.pf.save(HERE / 'fast-backup-host-tests.json', dict(passed=True, hardware=False, serial_access=False,
        checks=len(cases), cases=cases, helper_sha256=r.sha(Path(h.__file__).read_bytes()),
        checker_sha256=r.sha(Path(__file__).read_bytes()), preflight_sha256=r.sha(Path(h.pf.__file__).read_bytes()),
        qualified_shim_adapter_sha256=r.sha(Path(b.__file__).read_bytes()),
        source_firmware_sha256=r.sha((h.pf.BUILD / 'firmware.bin').read_bytes())))
    print('PASS buffered fast-backup', len(cases), flush=True)


if __name__ == '__main__':
    main()
