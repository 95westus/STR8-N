"""Buffered source-backup ordering and recovery-marker checks; no serial."""
import builtins
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
real_import = builtins.__import__
def deny_serial(name, *args, **kwargs):
    if name == 'serial' or name.startswith('serial.'):
        raise AssertionError('Buffered capture test imported serial')
    return real_import(name, *args, **kwargs)

with patch.object(builtins, '__import__', deny_serial):
    import capture_b07_2512 as c

def main():
    r, board = c.board.r, c.board
    expected = [(c.SOURCE_PLAN / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    original_ram = bytes((n * 17 + 3) & 255 for n in range(c.RAM_BYTES))
    results = []
    for fault in (None, 'flash-readback'):
        with tempfile.TemporaryDirectory(prefix='b07-capture-host-', dir=c.ROOT / 'tmp') as tmp:
            run = Path(tmp); marker_path = run / 'marker.json'
            marker = {'board': c.BOARD, 'test_marker': 'restore byte-for-byte',
                      'application_RAM_restore_pending': False}
            board.save(marker_path, marker); old_marker = marker_path.read_bytes()
            reads, flash_reads, restored = [], [], []
            class Link:
                def command(self, _): return board.MON_PROMPT
                def dump(self, start, end):
                    return b'\x02\x03' if start == 0x7d01 else b'\xb0'
            def read_range(*_):
                reads.append('RAM'); return original_ram
            def shim(*_):
                assert len(reads) == 2, 'Shim preceded repeated RAM backup'
                disk = run / 'capture'
                assert (disk / 'application-ram.bin').read_bytes() == original_ram
                assert (disk / 'application-ram-repeat.bin').read_bytes() == original_ram
                escrow = r.read(disk / 'RAM-escrow.json')
                assert escrow['twice_read_before_borrow'] and escrow['sha256'] == r.sha(original_ram)
                pending = r.read(marker_path)
                assert pending['application_RAM_restore_pending'] and pending['block_snapshot']
            def flash(*_):
                flash_reads.append('flash')
                if fault: raise RuntimeError('simulated flash readback failure')
                return expected
            def restore(*_): restored.append('RAM + BOTH')
            with patch.object(c, 'check_source'), patch.object(board.workflow, 'read_range', side_effect=read_range), \
                 patch.object(board, 'select_ftdi', side_effect=shim), \
                 patch.object(board.workflow, 'flash', side_effect=flash), \
                 patch.object(c, 'restore', side_effect=restore):
                try:
                    report = c.perform(Link(), marker_path, deepcopy(marker), run, expected)
                    assert fault is None and report['passed']
                except RuntimeError:
                    assert fault is not None
            if fault:
                pending = r.read(marker_path)
                assert pending['application_RAM_restore_pending'] and pending['block_snapshot']
                assert not pending['capture_worker_active'] and not restored
            else:
                assert len(flash_reads) == 2 and restored == ['RAM + BOTH']
                assert marker_path.read_bytes() == old_marker
                c.validate(run / 'capture')
            results.append(dict(case=fault or 'success', passed=True,
                repeated_RAM_escrow_before_shim=True, recovery_pending_on_failure=bool(fault),
                success_marker_byte_identical=not fault))
    report = dict(passed=True, hardware=False, serial_access=False, cases=results,
                  helper_sha256=r.sha(Path(c.__file__).read_bytes()), checker_sha256=r.sha(Path(__file__).read_bytes()),
                  limitation='Buffered ordering and refusal checks; actual shim CPU checks remain separately qualified')
    out = c.ROOT / 'BUILD/pr04-b07-startup/source-capture-host-tests.json'
    board.save(out, report); print('PASS buffered capture ordering/recovery checks', out)

if __name__ == '__main__': main()
