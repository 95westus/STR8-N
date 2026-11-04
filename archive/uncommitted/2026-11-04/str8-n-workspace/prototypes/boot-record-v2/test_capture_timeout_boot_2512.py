"""Buffered host checks only; no firmware rerun or hardware/serial access."""
import argparse
import builtins
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
real_import = builtins.__import__


def offline_import(name, *args, **kwargs):
    if name == 'serial' or name.startswith('serial.'):
        raise AssertionError('Read-only buffered check attempted serial import')
    return real_import(name, *args, **kwargs)


with patch.object(builtins, '__import__', offline_import):
    import capture_timeout_boot_2512 as helper


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    plan = args.plan.resolve()
    original = (plan / 'capture/application-ram.bin').read_bytes()
    results = []
    for fault in (None, 'countdown', 'banner', 'CPU', 'console', 'RAM'):
        class BufferedLink:
            def __init__(self):
                self.sent = []
                self.boundaries = 0
            def send(self, data):
                self.sent.append(data)
            def until(self, token, seconds=45):
                self.boundaries += 1
                if token == b'Consuming input\r\n':
                    return b'J3\r\nConsuming input\r\n'
                if token == helper.board.CHOICES:
                    return helper.board.CHOICES
                assert token == helper.board.MON_PROMPT
                tail = b'3 2 1 0\r\nSTR8-N 2.0proto b06 B3 65C02' + token
                if fault == 'countdown':
                    tail = tail.replace(b'3 2 1 0', b'3 2 1')
                if fault == 'banner':
                    tail = tail.replace(b'b06', b'b04')
                return tail
            def dump(self, first, last, prompt=None):
                if first == 0x7d01:
                    return (b'\x16' if fault == 'CPU' and self.boundaries else b'\x02') + (
                        b'\x01' if fault == 'console' and self.boundaries else b'\x03')
                if first == 0x7d30:
                    return b'\xb0'
                assert 0x200 <= first <= last <= 0x64ff
                data = original[first - 0x200:last - 0x200 + 1]
                if fault == 'RAM' and first == 0x200:
                    data = bytes([data[0] ^ 1]) + data[1:]
                return data
        link = BufferedLink()
        with tempfile.TemporaryDirectory(prefix='software-timeout-host-', dir=ROOT / 'tmp') as temp:
            if fault:
                try:
                    helper.capture(link, plan, Path(temp))
                except ValueError:
                    pass
                else:
                    raise AssertionError('Invalid read-only evidence accepted: ' + fault)
            else:
                report = helper.capture(link, plan, Path(temp))
                assert report['passed'] and report['no_selection_transmitted']
                assert report['full_RAM_readbacks_after_this_boot'] == 1
                assert report['physical_boot_capture'] is False
            assert link.sent == [b'J3\r\n', b'\r\n']
        results.append(dict(case='buffered-' + (fault + '-refused' if fault else 'complete-software-timeout'),
                            passed=True, host_startup_transmissions_only=True))
    receiver = helper.StartupReceiver(BufferedLink())
    receiver.send(b'J3\r\n'); receiver.send(b'\r\n')
    try:
        receiver.send(b'B')
    except ValueError:
        pass
    else:
        raise AssertionError('Selection transmission was accepted')
    results.append(dict(case='selection-TX-refused', passed=True))
    with patch.object(helper.board, 'admission', side_effect=AssertionError('No admission in buffered tests')):
        # Capture has no dependency that can silently admit execution or load RAM.
        assert not hasattr(helper.StartupReceiver, 'command') and not hasattr(helper.StartupReceiver, 'dump')
    helper.board.save(args.out, dict(passed=True, hardware=False, serial_access=False,
         firmware_tests_rerun=False, checks=len(results), cases=results,
         helper_sha256=helper.board.r.sha(Path(helper.__file__).read_bytes()),
         checker_sha256=helper.board.r.sha(Path(__file__).read_bytes()),
         admitted_adapter_sha256=helper.board.r.sha(Path(helper.board.__file__).read_bytes())))
    print('PASS buffered read-only software timeout helper', len(results), flush=True)


if __name__ == '__main__':
    main()
