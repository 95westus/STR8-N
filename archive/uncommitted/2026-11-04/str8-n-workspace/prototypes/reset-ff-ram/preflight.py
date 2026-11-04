"""Explicit receive/read-only 2512 RAM-probe preflight; no execution or setters."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'prototypes/boot-record-v2'), str(ROOT / 'tools')]
import board_b07_2512 as board
from installer.common import inventory

BUILD = ROOT / 'BUILD/pr04-b07-startup'
PLAN = ROOT / 'tmp/pr04-b07-2512-native-plan'
COMPLETED = ROOT / 'output/qualification/pr04-b07-2512-install-r2'
MARKER = ROOT / 'output/qualification/device-operations/2512.json'
RAM_FIRST, RAM_LAST = 0x200, 0x64ff
ZP_LAST = 0xdf


def atomic(path, body):
    path = Path(path); tmp = path.with_suffix(path.suffix + '.pending')
    with tmp.open('wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def save(path, value):
    atomic(path, (json.dumps(value, indent=2) + '\n').encode())


def expected_banks():
    return [(PLAN / f'expected-b{n}.bin').read_bytes() for n in range(4)]


def source_binding(marker, *, allow_pending=False):
    proof = board.bindings(BUILD, PLAN)
    source = board.r.read(COMPLETED / 'state.json')
    board.r.require(source['passed'] and source['phase'] == 'completed' and source['RAM_restored'],
                    'A completed b07 source is required')
    board.r.require(marker['firmware'] == '2.0proto b07' and marker['monitor_generation'] == 0x80000007
                    and marker['current_physical_bank_sha256'] == dict(zip(('B0', 'B1', 'B2', 'B3'), proof['expected_sha256'])),
                    'Exact current 2512 b07 physical-bank binding required')
    if not allow_pending:
        board.marker_ready(marker, COMPLETED, PLAN, pending=False)
    return proof


def identity(link):
    board.r.require(link.command('').endswith(board.MON_PROMPT)
                    and link.dump(0x7d01, 0x7d02) == b'\x02\x03'
                    and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Idle b07 65C02 BOTH MON B required')


def auth_check(auth, *, ram=False):
    action = 'reset-ff-ram-isolation' if ram else 'reset-ff-ram-read-only-preflight'
    board.r.require(auth.get('owner_authorized') is True and auth.get('action') == action
                    and (auth.get('board'), auth.get('usb_serial')) == (board.BOARD, board.USB)
                    and auth.get('flash_writes_authorized') is False
                    and auth.get('other_boards_authorized') is False
                    and auth.get('RTC_campaign_resume_authorized') is False,
                    'Exact 2512-only, no-flash diagnostic authorization required')


@contextlib.contextmanager
def link_for(args, *, pending=False, raw_watch=False):
    """Shared repository lease; imports are confined to explicit CLI I/O."""
    from serial_test_coordination import serial_lease, ROOT as lease_root
    from serial.tools.list_ports import comports
    board.r.require(args.coordination.resolve() == lease_root.resolve() == board.DEFAULT_COORDINATION.resolve(),
                    'Repository shared serial coordination is required')
    with serial_lease('reset-ff-ram-2512-' + args.stage, timeout=30):
        marker = board.r.read(args.marker)
        source_binding(marker, allow_pending=pending)
        if pending:
            board.r.require(marker.get('application_RAM_restore_pending') is True
                            and marker.get('reset_ff_run') == str(args.run.resolve())
                            and not any(v for k, v in marker.items() if k.endswith('_worker_active'))
                            and not marker.get('current_soak_worker_pid') and not marker.get('owner_application_running')
                            and not marker.get('power_off_reported') and not marker.get('poweroff_pending_owner_confirmation')
                            and marker.get('soak_owner_stopped') is True and marker.get('RTC_sampling_owner_stopped') is True,
                            'Exact inactive pending diagnostic escrow required')
        ports = [port for port in comports() if port.serial_number == board.USB]
        board.r.require(len(ports) == 1, 'Unique 2512 USB serial required; other boards are excluded')
        log_path = args.run / ('serial-' + args.stage + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '.jsonl')
        with log_path.open('x') as log:
            link = board.wire.Link(ports[0].device, log)
            try:
                if not raw_watch:
                    board.fresh_link_sync(link, args.run, args.stage)
                yield link, marker
            finally:
                link.serial.close()


def backup(link, run):
    """Read-only and intentionally slower BOTH path: no G before qualification."""
    identity(link)
    zp = [link.dump(0, ZP_LAST) for _ in range(2)]
    ram = [board.workflow.read_range(link, RAM_FIRST, RAM_LAST) for _ in range(2)]
    banks = [board.workflow.flash(link) for _ in range(2)]
    board.r.require(zp[0] == zp[1] and ram[0] == ram[1] and banks[0] == banks[1] == expected_banks(),
                    'Repeated fresh owner RAM/ZP or source flash differs')
    folder = Path(run) / 'capture'; folder.mkdir()
    for name, body in [('application-ram.bin', ram[0]), ('application-ram-repeat.bin', ram[1]),
                       ('owner-zp.bin', zp[0]), ('owner-zp-repeat.bin', zp[1]),
                       ('restore-application-ram.s19', board.wire.s19(dict(enumerate(ram[0], RAM_FIRST)), RAM_FIRST))]:
        atomic(folder / name, body)
    for n in range(4):
        for suffix in ('', '-repeat'):
            atomic(folder / f'b{n}{suffix}.bin', banks[0][n])
    save(folder / 'capture.json', dict(schema=2, board=board.BOARD, usb_serial=board.USB,
         journal_format='SNBT1/256', repeat_verified=True, hardware_capture=True, synthetic_model_fixture=False,
         bank_sha256=board.r.hashes(banks[0]), application_ram_sha256=board.r.sha(ram[0]),
         owner_zp_sha256=board.r.sha(zp[0]), owner_zp_range='0000-00DF', captured_utc=board.now(), files=inventory(folder)))
    board.capture.validate(folder)
    save(Path(run) / 'backup.json', dict(passed=True, flash_written=False, RAM_written=False,
         source_sha256=board.r.hashes(banks[0]), application_ram_sha256=board.r.sha(ram[0]),
         owner_zp_sha256=board.r.sha(zp[0]), repeat_readbacks=2, fsynced_before_any_execution=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('check', 'backup'))
    p.add_argument('--run', type=Path, required=True); p.add_argument('--authorization', type=Path, required=True)
    p.add_argument('--marker', type=Path, default=MARKER)
    p.add_argument('--coordination', type=Path, default=board.DEFAULT_COORDINATION)
    args = p.parse_args(); args.run = args.run.resolve()
    auth_check(board.r.read(args.authorization))
    source_binding(board.r.read(args.marker))
    board.r.require(not args.run.exists(), 'Use a fresh read-only run directory')
    args.run.mkdir(parents=True); (args.run / '.gitignore').write_text('*\n')
    before = args.marker.read_bytes()
    with link_for(args) as (link, marker):
        identity(link)
        if args.stage == 'backup':
            backup(link, args.run)
    board.r.require(args.marker.read_bytes() == before, 'Read-only preflight marker changed externally')
    save(args.run / 'preflight.json', dict(passed=True, stage=args.stage, serial_released=True,
         helper_sha256=board.r.sha(Path(__file__).read_bytes()), flash_written=False, RAM_written=False,
         marker_unchanged=True, no_G_or_R_or_reset=True))
    print('PASS read-only 2512 preflight; serial released', args.run, flush=True)


if __name__ == '__main__':
    main()
