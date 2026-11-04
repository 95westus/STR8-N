"""Fresh preserving b06 backup for b07; serial use is explicit CLI only.

RAM is twice read and durably escrowed before the qualified temporary FTDI
shim. Flash is twice read; original RAM and BOTH are restored before closure.
No flash/settings/RTC writes or physical reset are performed.
"""
import argparse
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / 'tools')]
import board_native_2512 as board
import capture_native_2512 as native_capture
from installer.common import inventory

BOARD, USB = board.BOARD, board.USB
RAM_BYTES = 0x6300
SOURCE_BUILD = ROOT / 'BUILD/pr04-b06-startup-r2'
SOURCE_PLAN = ROOT / 'tmp/pr04-b06-2512-native-plan-r2'
SOURCE_RUN = ROOT / 'output/qualification/pr04-b06-2512-install'
SOURCE_AUTH = ROOT / 'output/qualification/pr04-b06-2512-authorization/deploy-authorization.json'
validate = native_capture.validate


def restore_marker(path, original):
    path = Path(path); tmp = path.with_suffix('.backup-close.tmp')
    with tmp.open('wb') as stream:
        stream.write(original); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def check_source(marker, expected):
    r = board.r
    state = r.read(SOURCE_RUN / 'state.json')
    r.require(state['passed'] and state['phase'] == 'completed' and state['RAM_restored']
              and state['final_console_mode'] == 'BOTH', 'Completed b06 source required')
    r.require(marker['firmware'] == '2.0proto b06' and marker['monitor_generation'] == 0x80000006
              and marker['current_physical_bank_sha256'] == dict(zip(('B0', 'B1', 'B2', 'B3'), r.hashes(expected)))
              and marker['installer_run'] == str(SOURCE_RUN.resolve()), 'Current source binding differs')


def escrow(folder, first, second):
    r = board.r; folder.mkdir()
    r.require(first == second and len(first) == RAM_BYTES, 'Repeated RAM differs')
    for name, body in (('application-ram.bin', first), ('application-ram-repeat.bin', second),
                       ('restore-application-ram.s19', board.wire.s19(dict(enumerate(first, 0x200)), 0x200))):
        with (folder / name).open('wb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
    board.save(folder / 'RAM-escrow.json', dict(passed=True, bytes=RAM_BYTES, sha256=r.sha(first),
         restore_sha256=r.sha((folder / 'restore-application-ram.s19').read_bytes()),
         twice_read_before_borrow=True, recorded_utc=board.now()))


def restore(link, folder):
    meta = board.r.read(folder / 'RAM-escrow.json')
    original = (folder / 'application-ram.bin').read_bytes()
    board.r.require(meta['passed'] and board.r.sha(original) == meta['sha256']
                    and original == (folder / 'application-ram-repeat.bin').read_bytes(), 'RAM escrow changed')
    board.restore_original_ram(link, folder)
    prefix = board.software_startup(link, folder.parent, 'capture-b06-BOTH')
    link.send(b'B'); boot = link.until(board.MON_PROMPT)
    (folder.parent / 'source-final-BOTH-boot.txt').write_bytes(prefix + boot)
    board.r.require(b'STR8-N 2.0proto b06 B3 65C02' in boot
                    and link.dump(0x7d01, 0x7d02) == b'\x02\x03'
                    and link.dump(0x7d30, 0x7d30) == b'\xb0'
                    and board.workflow.read_range(link, 0x200, 0x64ff) == original,
                    'Final b06 BOTH boot/RAM differs')


def perform(link, marker_path, marker, run, expected):
    """Lease-held capture; useful for buffered checks without serial imports."""
    r = board.r; run = Path(run); folder = run / 'capture'
    original_marker = Path(marker_path).read_bytes()
    (run / 'device-marker-before.json').write_bytes(original_marker)
    borrowed = False
    try:
        check_source(marker, expected)
        r.require(link.command('').endswith(board.MON_PROMPT)
                  and link.dump(0x7d01, 0x7d02) == b'\x02\x03'
                  and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Idle b06 65C02/BOTH/MON B required')
        first = board.workflow.read_range(link, 0x200, 0x64ff)
        second = board.workflow.read_range(link, 0x200, 0x64ff)
        escrow(folder, first, second)
        marker.update(state='b07-source-backup-borrowing', block_snapshot=True,
                      application_RAM_restore_pending=True, application_ram_restored=False,
                      capture_worker_active=True, capture_run=str(run.resolve()),
                      capture_RAM_escrow=str(folder.resolve()), installer_run=str(run.resolve()))
        board.save(marker_path, marker)
        borrowed = True
        board.select_ftdi(link, SOURCE_BUILD, expected, run, 'b07-source-b06')
        banks = board.workflow.flash(link); repeat = board.workflow.flash(link)
        r.require(banks == repeat == expected, 'Repeated flash differs from completed b06 source')
        for n, body in enumerate(banks):
            for suffix in ('', '-repeat'):
                (folder / f'b{n}{suffix}.bin').write_bytes(body)
        identity = dict(schema=2, board=BOARD, usb_serial=USB, journal_format='SNBT1/256',
                        repeat_verified=True, hardware_capture=True, synthetic_model_fixture=False,
                        bank_sha256=r.hashes(banks), application_ram_sha256=r.sha(first), captured_utc=board.now(),
                        source_evidence=dict(source_build=str(SOURCE_BUILD), source_plan=str(SOURCE_PLAN),
                            source_run=str(SOURCE_RUN), RAM_escrow_precedes_temporary_shim=True), files=inventory(folder))
        board.save(folder / 'capture.json', identity); validate(folder)
        restore(link, folder)
        borrowed = False
        restore_marker(marker_path, original_marker)
        return dict(passed=True, source='2.0proto b06', board=BOARD, source_sha256=r.hashes(banks),
                    application_ram_sha256=r.sha(first), application_ram_bytes=len(first),
                    RAM_twice_escrowed_before_borrow=True, flash_readbacks=2,
                    original_RAM_restoration_readbacks=3, RAM_reread_after_BOTH_boot=True,
                    final_console_mode='BOTH', final_active_monitor='B', marker_restored_byte_identical=True,
                    flash_written=False, settings_written=False, physical_reset_requested=False,
                    temporary_13_byte_RAM_shim_restored=True, capture_json_sha256=r.sha((folder / 'capture.json').read_bytes()))
    except BaseException:
        if borrowed:
            marker.update(state='b07-source-backup-recovery-required', capture_worker_active=False,
                          installer_worker_active=False, block_snapshot=True,
                          application_RAM_restore_pending=True, application_ram_restored=False)
            board.save(marker_path, marker)
        else:
            restore_marker(marker_path, original_marker)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--authorization', type=Path, required=True)
    p.add_argument('--coordination', type=Path, default=board.DEFAULT_COORDINATION)
    p.add_argument('--marker', type=Path, default=ROOT / 'output/qualification/device-operations/2512.json')
    args = p.parse_args(); args.run = args.run.resolve()
    auth = board.r.read(args.authorization)
    board.r.require(auth.get('owner_authorized') is True and auth.get('action') == 'capture-native-b07-source'
                    and (auth.get('board'), auth.get('usb_serial')) == (BOARD, USB)
                    and auth.get('other_boards_authorized') is False
                    and auth.get('RTC_campaign_resume_authorized') is False, 'Exact new source-backup scope required')
    board.r.require(board.r.sha(Path(board.__file__).read_bytes()) == 'cda026d2905e63267a3961b3beb7898c8061d40a7965a32b1338dd8381e23afc',
                    'Qualified b06 host dependency changed')
    board.admission(SOURCE_BUILD, SOURCE_PLAN, SOURCE_RUN, board.r.read(SOURCE_AUTH))
    expected = [(SOURCE_PLAN / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    check_source(board.r.read(args.marker), expected)
    board.r.require(not args.run.exists(), 'Use a fresh backup directory')
    args.run.mkdir(parents=True); (args.run / '.gitignore').write_text('*\n')
    args.plan, args.stage, args.campaign_receipt = SOURCE_PLAN, 'capture-b07-source', None
    with board.live_link(args, pending=False) as (link, marker):
        report = perform(link, args.marker, marker, args.run, expected)
    report.update(completed_utc=board.now(), serial_released=True,
                  helper_sha256=board.r.sha(Path(__file__).read_bytes()))
    board.save(args.run / 'capture-report.json', report)
    print('PASS fresh b06 native backup; RAM/BOTH restored and serial released', args.run / 'capture', flush=True)


if __name__ == '__main__':
    main()
