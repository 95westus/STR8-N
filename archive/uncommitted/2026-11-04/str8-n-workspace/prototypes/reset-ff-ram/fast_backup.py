"""2512 RAM-escrowed fast backup; qualified FTDI shim only, never flash writes.

Fresh BOTH RAM/ZP copies are fsynced before the sole G handoff. The borrowed
13-byte span is restored, full RAM is checked three times, and public J3
returns through the complete ordinary BOTH startup before final verification.
"""
import argparse
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as pf

board, r = pf.board, pf.board.r
KIND = 'qualified-FTDI-shim-backup'
SHIM_ADDRESS, SHIM_BYTES = 0x2000, 13


def auth_check(auth):
    r.require(auth.get('owner_authorized') is True
              and auth.get('action') == 'reset-ff-ram-fast-backup'
              and (auth.get('board'), auth.get('usb_serial')) == (board.BOARD, board.USB)
              and auth.get('RAM_writes_authorized') is True
              and auth.get('flash_writes_authorized') is False
              and auth.get('other_boards_authorized') is False
              and auth.get('RTC_campaign_resume_authorized') is False
              and auth.get('backup_helper_sha256') == r.sha(Path(__file__).read_bytes()),
              'Exact 2512 RAM-only fast-backup authorization required')


def qualification():
    proof = r.read(HERE / 'fast-backup-host-tests.json')
    r.require(proof.get('passed') is True and proof.get('hardware') is False
              and proof.get('serial_access') is False and proof.get('checks', 0) >= 8
              and proof['helper_sha256'] == r.sha(Path(__file__).read_bytes())
              and proof['checker_sha256'] == r.sha((HERE / 'test_fast_backup.py').read_bytes())
              and proof['preflight_sha256'] == r.sha(Path(pf.__file__).read_bytes()),
              'Fresh buffered fast-backup qualification required')


def checkpoint(args, marker, state, phase, *, active):
    state.update(phase=phase, updated_utc=board.now())
    pf.save(args.run / 'state.json', state)
    marker.update(state='reset-ff-fast-backup-' + phase,
                  reset_ff_run=str(args.run.resolve()), reset_ff_worker_active=active,
                  application_RAM_restore_pending=state['application_RAM_restore_pending'],
                  application_ram_restored=not state['application_RAM_restore_pending'],
                  block_snapshot=state['application_RAM_restore_pending'], physical_reset_pending=False)
    pf.save(args.marker, marker)


def early_escrow(args, ram, zp):
    folder = args.run / 'capture'
    r.require(not folder.exists(), 'Fresh fast-backup capture directory required')
    folder.mkdir()
    for name, body in (
        ('application-ram.bin', ram), ('application-ram-repeat.bin', ram),
        ('owner-zp.bin', zp), ('owner-zp-repeat.bin', zp),
        ('restore-application-ram.s19', board.wire.s19(dict(enumerate(ram, pf.RAM_FIRST)), pf.RAM_FIRST))):
        pf.atomic(folder / name, body)
    proof = dict(passed=True, kind=KIND, bytes=len(ram), owner_zp_bytes=len(zp),
                 application_ram_sha256=r.sha(ram), owner_zp_sha256=r.sha(zp),
                 twice_read_before_borrow=True, fsynced_before_any_execution=True,
                 files=pf.inventory(folder))
    pf.save(args.run / 'early-RAM-escrow.json', proof)
    return validate_escrow(args)


def validate_escrow(args):
    folder = args.run / 'capture'; proof = r.read(args.run / 'early-RAM-escrow.json')
    r.require(proof['passed'] and proof['kind'] == KIND
              and proof['twice_read_before_borrow'] and proof['fsynced_before_any_execution'],
              'Incomplete pre-G RAM escrow')
    for name, info in proof['files'].items():
        r.require(Path(name).name == name, 'Escrow member is not a direct file')
        body = (folder / name).read_bytes()
        r.require(len(body) == info['bytes'] and r.sha(body) == info['sha256'], 'Pre-G escrow changed: ' + name)
    ram = (folder / 'application-ram.bin').read_bytes()
    zp = (folder / 'owner-zp.bin').read_bytes()
    r.require(len(ram) == 0x6300 and ram == (folder / 'application-ram-repeat.bin').read_bytes()
              and r.sha(ram) == proof['application_ram_sha256']
              and len(zp) == 0xe0 and zp == (folder / 'owner-zp-repeat.bin').read_bytes()
              and r.sha(zp) == proof['owner_zp_sha256']
              and (folder / 'restore-application-ram.s19').read_bytes()
              == board.wire.s19(dict(enumerate(ram, pf.RAM_FIRST)), pf.RAM_FIRST),
              'Repeated RAM/ZP escrow differs')
    return ram, zp


def save_banks(args, banks, ram, zp):
    folder = args.run / 'capture'
    for n in range(4):
        for suffix in ('', '-repeat'):
            pf.atomic(folder / f'b{n}{suffix}.bin', banks[n])
    pf.save(folder / 'capture.json', dict(schema=2, board=board.BOARD, usb_serial=board.USB,
        journal_format='SNBT1/256', repeat_verified=True, hardware_capture=True, synthetic_model_fixture=False,
        bank_sha256=r.hashes(banks), application_ram_sha256=r.sha(ram), owner_zp_sha256=r.sha(zp),
        owner_zp_range='0000-00DF', captured_utc=board.now(), backup_kind=KIND, files=pf.inventory(folder)))
    board.capture.validate(folder)


def restore_and_verify(args, link, marker, state):
    ram, zp = validate_escrow(args)
    r.require(state['application_RAM_restore_pending'], 'No fast-backup RAM restoration is pending')
    r.require(link.command('').endswith(board.MON_PROMPT)
              and link.dump(0x7d01, 0x7d01) == b'\x02'
              and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Known idle 65C02 MON B required')
    checkpoint(args, marker, state, 'restoring-borrowed-span', active=True)
    # No execution of owner bytes: the public S19 loader replaces only the
    # exact 13 bytes borrowed by the admitted FTDI selection shim.
    first = SHIM_ADDRESS - pf.RAM_FIRST
    board.load_ram_span(link, SHIM_ADDRESS, ram[first:first + SHIM_BYTES])
    for _ in range(3):
        r.require(board.workflow.read_range(link, pf.RAM_FIRST, pf.RAM_LAST) == ram,
                  'Full application RAM differs after shim restoration')
    for _ in range(2):
        r.require(link.dump(0, pf.ZP_LAST) == zp, 'Owner ZP00-DF differs after shim')
    state['restoration_full_RAM_comparisons'] = 3
    checkpoint(args, marker, state, 'final-normal-BOTH-startup', active=True)
    prefix = board.software_startup(link, args.run, 'fast-backup-final-BOTH')
    boot = link.until(board.MON_PROMPT, 60)
    raw = prefix + boot
    tokens = (b'\r\nWAIT...\r\n', board.CHOICES, b'Boot : 3 2 1 0\r\n', b'STR8-N 2.0proto b07 B3 65C02')
    positions = [raw.find(token) for token in tokens]
    pf.atomic(args.run / 'final-BOTH-boot.bin', raw)
    r.require(all(n >= 0 for n in positions) and positions == sorted(positions)
              and link.dump(0x7d01, 0x7d02) == b'\x02\x03'
              and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Full final b07 BOTH startup differs')
    r.require(board.workflow.read_range(link, pf.RAM_FIRST, pf.RAM_LAST) == ram,
              'Full application RAM differs after final BOTH startup')
    for _ in range(2):
        r.require(link.dump(0, pf.ZP_LAST) == zp, 'Owner ZP00-DF differs after final BOTH startup')
    state.update(RAM_restored=True, ZP_preserved=True, RAM_borrowed_and_restored=True,
                 application_RAM_restore_pending=False, final_console_mode='BOTH',
                 final_RAM_comparisons=1, final_ZP_comparisons=2)
    return ram, zp


def complete(args, marker, state):
    r.require(state['RAM_restored'] and state['ZP_preserved'] and state.get('flash_readback_repeat_verified'),
              'Fast backup is not fully verified')
    ram, zp = validate_escrow(args)
    board.capture.validate(args.run / 'capture')
    result = dict(passed=True, kind=KIND, source_sha256=state['source_sha256'],
                  application_ram_sha256=r.sha(ram), owner_zp_sha256=r.sha(zp), repeat_readbacks=2,
                  fsynced_before_any_execution=True, RAM_written=True, flash_written=False,
                  RAM_borrowed_and_restored=True, RAM_restored=True, ZP_preserved=True,
                  borrowed_address=SHIM_ADDRESS, borrowed_bytes=SHIM_BYTES, diagnostic_probe_G=False,
                  restoration_full_RAM_comparisons=3, final_RAM_comparisons=1, final_ZP_comparisons=2,
                  final_console_mode='BOTH', original_marker_restored_byte_identical=True,
                  helper_sha256=r.sha(Path(__file__).read_bytes()), preflight_sha256=r.sha(Path(pf.__file__).read_bytes()))
    pf.save(args.run / 'backup.json', result)
    state.update(passed=True, completed_utc=board.now(), phase='completed')
    pf.save(args.run / 'state.json', state)
    pf.atomic(args.marker, (args.run / 'device-marker-before.json').read_bytes())
    r.require(args.marker.read_bytes() == (args.run / 'device-marker-before.json').read_bytes(), 'Original marker restoration differs')
    pf.save(args.run / 'preflight.json', dict(result, stage='fast-backup', serial_released=False,
                                              marker_unchanged=True, no_flash_or_config_writes=True))


def finish_closed(args):
    proof = r.read(args.run / 'preflight.json')
    r.require(proof['passed'] and proof['kind'] == KIND and proof['RAM_restored']
              and args.marker.read_bytes() == (args.run / 'device-marker-before.json').read_bytes(),
              'Closed-session completion is incomplete')
    pf.save(args.run / 'preflight.json', dict(proof, serial_released=True))


def perform_backup(args, link, marker):
    pf.identity(link)
    zp = [link.dump(0, pf.ZP_LAST) for _ in range(2)]
    ram = [board.workflow.read_range(link, pf.RAM_FIRST, pf.RAM_LAST) for _ in range(2)]
    r.require(zp[0] == zp[1] and len(zp[0]) == 0xe0 and ram[0] == ram[1] and len(ram[0]) == 0x6300,
              'Fresh repeated owner RAM/ZP differs; no execution permitted')
    early_escrow(args, ram[0], zp[0])
    state = dict(kind=KIND, phase='RAM-escrowed', passed=False, application_RAM_restore_pending=True,
                 physical_reset_pending=False, source_sha256=r.hashes(pf.expected_banks()),
                 borrowed_address=SHIM_ADDRESS, borrowed_bytes=SHIM_BYTES)
    checkpoint(args, marker, state, 'RAM-escrowed-before-first-G', active=True)
    # The existing helper reads F/MON/worker/vectors and its borrowed preimage
    # before its exact 13-byte S19/G operation. No new diagnostic code runs.
    board.select_ftdi(link, pf.BUILD, pf.expected_banks(), args.run, 'fast-backup')
    shim = r.read(args.run / 'ftdi-session-fast-backup.json')
    first = SHIM_ADDRESS - pf.RAM_FIRST
    r.require(shim['borrowed_address'] == SHIM_ADDRESS
              and bytes.fromhex(shim['borrowed_original_hex']) == ram[0][first:first + SHIM_BYTES],
              'Qualified shim borrowed preimage differs from fresh escrow')
    banks = [board.workflow.flash(link) for _ in range(2)]
    r.require(banks[0] == banks[1] == pf.expected_banks(), 'Repeated full source flash differs')
    save_banks(args, banks[0], ram[0], zp[0])
    state['flash_readback_repeat_verified'] = True
    checkpoint(args, marker, state, 'flash-readback-complete', active=True)
    restore_and_verify(args, link, marker, state)
    complete(args, marker, state)


def perform_restore(args, link, marker):
    state = r.read(args.run / 'state.json')
    r.require(state['kind'] == KIND and not state.get('passed') and state['application_RAM_restore_pending'],
              'Exact incomplete fast-backup escrow required')
    ram, zp = validate_escrow(args)
    # A failed bank read does not count as an unchanged-flash receipt.
    banks = [board.workflow.flash(link) for _ in range(2)]
    r.require(banks[0] == banks[1] == pf.expected_banks(), 'Repeated recovery flash differs; retain escrow')
    save_banks(args, banks[0], ram, zp)
    state['flash_readback_repeat_verified'] = True
    restore_and_verify(args, link, marker, state)
    complete(args, marker, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('backup', 'restore-only'))
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--marker', type=Path, default=pf.MARKER)
    parser.add_argument('--coordination', type=Path, default=board.DEFAULT_COORDINATION)
    args = parser.parse_args(); args.run = args.run.resolve()
    auth_check(r.read(args.authorization)); qualification()
    pending = args.stage == 'restore-only'
    pf.source_binding(r.read(args.marker), allow_pending=pending)
    if pending:
        validate_escrow(args)
    else:
        r.require(not args.run.exists(), 'Use a fresh fast-backup run directory')
        args.run.mkdir(parents=True); (args.run / '.gitignore').write_text('*\n')
    try:
        with pf.link_for(args, pending=pending) as (link, marker):
            if pending:
                perform_restore(args, link, marker)
            else:
                pf.atomic(args.run / 'device-marker-before.json', args.marker.read_bytes())
                perform_backup(args, link, marker)
        finish_closed(args)
    except BaseException:
        if (args.run / 'state.json').exists():
            state = r.read(args.run / 'state.json')
            if state.get('application_RAM_restore_pending'):
                state['failure'] = traceback.format_exc()
                checkpoint(args, r.read(args.marker), state, 'inspection-required', active=False)
        raise
    print('PASS fast RAM-escrowed 2512 backup; full RAM/ZP restored, BOTH, serial released', args.run, flush=True)


if __name__ == '__main__':
    main()
