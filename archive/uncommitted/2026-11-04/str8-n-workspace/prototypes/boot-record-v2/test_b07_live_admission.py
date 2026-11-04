"""Fresh-process production admission import hygiene; never opens a port."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--serial-import-only', action='store_true')
    args = parser.parse_args()
    build, plan = args.build.resolve(), args.plan.resolve()
    before_finders = tuple(sys.meta_path)
    before_sockets = (socket.create_connection, socket.socket.connect, socket.socket.connect_ex)
    assert not any(type(finder).__name__ == 'NoDevices' for finder in before_finders)
    assert not any(name in sys.modules for name in ('test_b07', 'test_monitor_size', 'prepare_monitor_size', 'serial'))
    sys.path[:0] = [str(HERE), str(ROOT / 'tools')]
    import board_b07_2512 as board
    proof = board.bindings(build, plan)
    rows = [dict(case='unmodified-production-bindings-actual-capture', passed=True)]
    assert tuple(sys.meta_path) == before_finders
    rows.append(dict(case='meta-path-finders-byte-identical-and-no-NoDevices', passed=True))
    assert (socket.create_connection, socket.socket.connect, socket.socket.connect_ex) == before_sockets
    rows.append(dict(case='socket-callables-identity-unchanged', passed=True))
    assert not any(name in sys.modules for name in ('test_b07', 'test_monitor_size', 'prepare_monitor_size', 'serial'))
    rows.append(dict(case='no-test-model-or-device-adapter-imported-by-admission', passed=True))
    actual = json.loads((build / 'cpu-tests.json').read_text())['frozen_b06_checker_adaptation']
    import b07_admission
    assert b07_admission.core_adaptation_hashes() == actual
    rows.append(dict(case='pure-text-adaptation-hashes-match-frozen-core-receipt', passed=True))
    if args.serial_import_only:
        # Module loading only: no Serial constructor, comports(), read, write,
        # lease, socket call, or device opening is performed by this checker.
        import serial
        import serial.tools.list_ports
        assert serial.Serial and serial.tools.list_ports.comports
        assert tuple(sys.meta_path) == before_finders
        assert (socket.create_connection, socket.socket.connect, socket.socket.connect_ex) == before_sockets
        rows.append(dict(case='serial-modules-importable-after-admission-without-open', passed=True))
    report = dict(passed=True, hardware=False, serial_access=False, serial_ports_opened=0,
                  network_access=False, fresh_process=True, checks=len(rows), cases=rows,
                  adapter_sha256=sha(board.__file__), admission_checker_sha256=sha(b07_admission.__file__),
                  checker_sha256=sha(__file__), plan_sha256=proof['plan_sha256'],
                  firmware_sha256=proof['firmware_sha256'],
                  pure_text_hashes_only=True, offline_guard_removed_or_disabled=False,
                  optional_serial_import_only=args.serial_import_only)
    board.save(build / 'live-admission-import-tests.json', report)
    print('PASS fresh-process production admission import hygiene', len(rows), flush=True)


if __name__ == '__main__':
    main()
