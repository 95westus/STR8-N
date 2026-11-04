"""2512-only RAM diagnostic runner. No flash/config/RTC setter is available.

Prepare and tests are offline; hardware stages are explicit CLI commands.
Each diagnostic G gets a cleared capsule and fresh nonce. RESET is performed
only by the owner after the already-open receiver announces ARMED.
"""
import argparse
import functools
import json
from pathlib import Path
import secrets
import socket
import sys
import time
import traceback

META_BEFORE = tuple(sys.meta_path)
SOCKETS_BEFORE = (socket.create_connection, socket.socket.connect, socket.socket.connect_ex)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as pf
board, r = pf.board, pf.board.r
CAP, CAP_BYTES = 0x6400, 256
ENTRY, END = 0x2000, 0x2400
ARM_SECONDS = 7200


def hygiene():
    r.require(tuple(sys.meta_path) == META_BEFORE
              and (socket.create_connection, socket.socket.connect, socket.socket.connect_ex) == SOCKETS_BEFORE
              and not any(type(f).__name__ == 'NoDevices' for f in sys.meta_path),
              'Production admission changed import/socket behavior')


def member(folder, name):
    value = (Path(folder) / name).resolve()
    r.require(value.parent == Path(folder).resolve(), 'Probe member must be a direct build member')
    return value


def probe_binding(folder):
    folder = Path(folder); manifest = r.read(folder / 'manifest.json')
    r.require(manifest['format'] == 1 and manifest['entry'] == ENTRY
              and ENTRY < manifest['code_end'] <= END and manifest['return_prompt_B160'] == 0xb160,
              'Probe code/capsule ABI changed')
    r.require(manifest['probe_source_sha256'] == r.sha((HERE / 'probe.asm').read_bytes())
              and manifest['builder_sha256'] == r.sha((HERE / 'build.py').read_bytes())
              and manifest['runtime_symbols_sha256'] == r.sha((pf.BUILD / 'symbols.json').read_bytes()),
              'Probe source/runtime binding changed')
    for name, digest in manifest['component_hashes'].items():
        r.require(digest == r.sha((pf.BUILD / 'payload' / name).read_bytes()), 'Probe runtime component changed')
    mon = (pf.BUILD / 'payload/monitor-b0-offline-component.bin').read_bytes()
    r.require(bytes.fromhex(manifest['return_prompt_preimage_hex']) == mon[0x160:0x170]
              and manifest['return_prompt_preimage_sha256'] == r.sha(mon[0x160:0x170]), 'Prompt preimage changed')
    cases = {row['id']: row for row in manifest['cases']}
    r.require(set(cases) == {0, 1, 2, 3, 4, 5, 8, 9, 10, 11}, 'Probe case inventory changed')
    for row in cases.values():
        body = member(folder, row['bin']).read_bytes()
        packet = member(folder, row['s19']).read_bytes()
        cells, entry = board.wire.read_s19(member(folder, row['s19']))
        r.require(row['entry'] == entry == ENTRY and 0 < len(body) <= END - ENTRY
                  and row['sha256'] == r.sha(body) and row['s19_sha256'] == r.sha(packet)
                  and cells == dict(enumerate(body, ENTRY)), 'Probe variant changed')
    proof = r.read(member(folder, manifest['qualification_report']))
    r.require(proof.get('passed') is True and proof.get('hardware') is False
              and proof.get('serial_access') is False, 'Offline probe CPU qualification required')
    # Final report supplies exact source/manifest bindings, per-CPU case IDs,
    # guards and preservation. Never import its executable model here.
    r.require(proof['manifest_sha256'] == r.sha((folder / 'manifest.json').read_bytes())
              and proof['checker_sha256'] == r.sha((HERE / 'test_probe.py').read_bytes())
              and proof['probe_source_sha256'] == manifest['probe_source_sha256']
              and proof['builder_sha256'] == manifest['builder_sha256']
              and proof['case_binary_hashes'] == {str(row['id']): row['sha256'] for row in cases.values()}
              and proof['component_hashes'] == manifest['component_hashes']
              and proof['runtime_symbols_sha256'] == manifest['runtime_symbols_sha256']
              and proof['pin_model_dependency_sha256']
                  == r.sha((pf.ROOT / 'output/qualification/physical-reset-ff-investigation/trace_reset.py').read_bytes()),
              'Probe CPU receipt changed')
    for name, digest in proof['reused_model_hashes'].items():
        r.require(digest == r.sha((pf.ROOT / name).read_bytes()), 'Probe model dependency changed')
    coverage = {(row['cpu'], row['case']) for row in proof['cases'] if row.get('category') == 'positive'}
    positive = [row for row in proof['cases'] if row.get('category') == 'positive']
    r.require(proof['checks'] == len(proof['cases']) == 64 and all(row['passed'] for row in proof['cases'])
              and proof['cpu_coverage'] == {'65c02': 32, '65c816-e': 32}
              and len(positive) == 40
              and {(row['cpu'], row['case'], row['released_WR']) for row in positive}
                  == {(cpu, case, released) for cpu in ('65c02', '65c816-e') for case in cases for released in (0, 1)}
              and all(row['no_flash_or_unapproved_RAM_writes'] and row['owner_ZP_00_DF_preserved']
                      and row['pending_input_preserved'] for row in positive)
              and {(cpu, case) for cpu in ('65c02', '65c816-e') for case in cases} <= coverage,
              'Both CPU probe case matrix is incomplete')
    return manifest, cases


def backup_binding(backup_run, source_banks):
    """Accept only completed read-only or fully restored qualified-shim backups."""
    backup_run = Path(backup_run)
    identity, banks = board.capture.validate(backup_run / 'capture')
    meta, finished = r.read(backup_run / 'backup.json'), r.read(backup_run / 'preflight.json')
    zp = (backup_run / 'capture/owner-zp.bin').read_bytes()
    r.require(meta['passed'] is True and finished['passed'] is True and finished['serial_released'] is True
              and meta['flash_written'] is False and finished['flash_written'] is False
              and finished['marker_unchanged'] is True and meta['repeat_readbacks'] == 2
              and meta['fsynced_before_any_execution'] is True and len(zp) == 0xe0
              and zp == (backup_run / 'capture/owner-zp-repeat.bin').read_bytes()
              and identity['owner_zp_sha256'] == r.sha(zp)
              and meta['application_ram_sha256'] == identity['application_ram_sha256']
              and meta['owner_zp_sha256'] == r.sha(zp)
              and meta['source_sha256'] == r.hashes(banks) == source_banks,
              'Fresh repeated physical backup required')
    preflight_sha = r.sha(Path(pf.__file__).read_bytes())
    if finished['stage'] == 'backup':
        r.require(meta['RAM_written'] is False and finished['RAM_written'] is False
                  and finished['helper_sha256'] == preflight_sha and finished['no_G_or_R_or_reset'] is True,
                  'Read-only backup qualification changed')
        kind, helper_proof = 'read-only-backup', None
    else:
        helper = HERE / 'fast_backup.py'; checker = HERE / 'test_fast_backup.py'
        helper_proof = r.read(HERE / 'fast-backup-host-tests.json')
        helper_sha = r.sha(helper.read_bytes())
        r.require(finished['stage'] == 'fast-backup' and meta['kind'] == finished['kind'] == 'qualified-FTDI-shim-backup'
                  and meta['helper_sha256'] == finished['helper_sha256'] == helper_sha
                  and meta['preflight_sha256'] == finished['preflight_sha256'] == preflight_sha
                  and helper_proof['passed'] is True and helper_proof['hardware'] is False
                  and helper_proof['serial_access'] is False
                  and helper_proof['checks'] == len(helper_proof['cases']) == 11
                  and all(row['passed'] is True for row in helper_proof['cases'])
                  and helper_proof['helper_sha256'] == helper_sha
                  and helper_proof['checker_sha256'] == r.sha(checker.read_bytes())
                  and helper_proof['preflight_sha256'] == preflight_sha
                  and helper_proof['qualified_shim_adapter_sha256'] == r.sha(Path(board.__file__).read_bytes())
                  and helper_proof['source_firmware_sha256'] == r.sha((pf.BUILD / 'firmware.bin').read_bytes()),
                  'Qualified fast-backup helper proof changed')
        for receipt in (meta, finished):
            r.require(all(receipt[key] is True for key in ('RAM_written', 'RAM_borrowed_and_restored',
                      'RAM_restored', 'ZP_preserved', 'original_marker_restored_byte_identical'))
                      and receipt['diagnostic_probe_G'] is False and receipt['borrowed_address'] == ENTRY
                      and receipt['borrowed_bytes'] == 13 and receipt['restoration_full_RAM_comparisons'] == 3
                      and receipt['final_RAM_comparisons'] == 1 and receipt['final_ZP_comparisons'] == 2
                      and receipt['final_console_mode'] == 'BOTH',
                      'Fast backup has not completed exact RAM/ZP/BOTH preservation')
        r.require(finished['no_flash_or_config_writes'] is True, 'Fast backup scope changed')
        kind = meta['kind']
    return identity, zp, dict(kind=kind,
        backup_receipt_sha256=r.sha((backup_run / 'backup.json').read_bytes()),
        completion_receipt_sha256=r.sha((backup_run / 'preflight.json').read_bytes()),
        helper_qualification_sha256=r.sha((HERE / 'fast-backup-host-tests.json').read_bytes()) if helper_proof else None)


def bindings(probe, backup_run):
    proof = pf.source_binding(r.read(pf.MARKER), allow_pending=True)
    backup_run = Path(backup_run)
    identity, zp, backup = backup_binding(backup_run, proof['expected_sha256'])
    manifest, _ = probe_binding(probe)
    host_proof = r.read(HERE / 'host-tests.json')
    r.require(host_proof['passed'] is True and host_proof['hardware'] is False
              and host_proof['serial_access'] is False and host_proof['checks'] == len(host_proof['cases']) == 17
              and all(row['passed'] is True for row in host_proof['cases'])
              and host_proof['host_sha256'] == r.sha(Path(__file__).read_bytes())
              and host_proof['preflight_sha256'] == r.sha(Path(pf.__file__).read_bytes())
              and host_proof['checker_sha256'] == r.sha((HERE / 'test_host.py').read_bytes())
              and host_proof['probe_manifest_sha256'] == r.sha((Path(probe) / 'manifest.json').read_bytes()),
              'Current buffered host safety qualification required')
    hygiene()
    return dict(board=board.BOARD, usb_serial=board.USB,
                firmware_sha256=proof['firmware_sha256'], source_bank_sha256=proof['expected_sha256'],
                probe_manifest_sha256=r.sha((Path(probe) / 'manifest.json').read_bytes()),
                probe_CPU_receipt_sha256=r.sha(member(probe, manifest['qualification_report']).read_bytes()),
                host_qualification_sha256=r.sha((HERE / 'host-tests.json').read_bytes()),
                backup_manifest_sha256=r.sha((backup_run / 'capture/capture.json').read_bytes()),
                backup=backup,
                application_ram_sha256=identity['application_ram_sha256'], owner_zp_sha256=r.sha(zp),
                host_sha256=r.sha(Path(__file__).read_bytes()), preflight_sha256=r.sha(Path(pf.__file__).read_bytes()))


def prepare(probe, backup_run, run):
    proof = bindings(probe, backup_run)
    r.require(not Path(run).exists(), 'Use a fresh diagnostic run directory')
    Path(run).mkdir(parents=True); (Path(run) / '.gitignore').write_text('*\n')
    pf.save(Path(run) / 'admission.json', proof)
    pf.save(Path(run) / 'state.json', dict(phase='prepared', passed=False,
        application_RAM_restore_pending=False, physical_reset_pending=False,
        backup_run=str(Path(backup_run).resolve()), probe_build=str(Path(probe).resolve()), trials=[]))
    return proof


def admit(args, auth):
    proof = bindings(args.probe, args.backup_run)
    r.require(r.read(args.run / 'admission.json') == proof, 'Prepared diagnostic admission changed')
    pf.auth_check(auth, ram=True)
    r.require(auth.get('RAM_writes_authorized') is True
              and auth.get('host_sha256') == proof['host_sha256']
              and auth.get('probe_manifest_sha256') == proof['probe_manifest_sha256']
              and auth.get('source_firmware_sha256') == proof['firmware_sha256'], 'Exact RAM-only probe scope changed')
    r.require(auth.get('software_cases') == [0, 1, 2, 3, 4, 5]
              and set(auth.get('physical_reset_cases', [])) <= {8, 9, 10, 11}, 'Diagnostic case scope changed')
    return proof


def checkpoint(args, marker, state, phase, active):
    state.update(phase=phase, updated_utc=board.now())
    pf.save(args.run / 'state.json', state)
    marker.update(state='reset-ff-ram-' + phase, reset_ff_run=str(args.run.resolve()),
                  reset_ff_worker_active=active, block_snapshot=state['application_RAM_restore_pending'],
                  application_RAM_restore_pending=state['application_RAM_restore_pending'],
                  application_ram_restored=not state['application_RAM_restore_pending'],
                  physical_reset_pending=state['physical_reset_pending'])
    pf.save(args.marker, marker)


def quiet_capture(link, *, seconds=1.0, maximum=8.0):
    """Fresh-link/setup raw capture only; never called during binary frames."""
    initial = bytes(link.pending); link.pending.clear()
    data = bytearray(initial); start = last = time.monotonic()
    while time.monotonic() - last < seconds:
        if time.monotonic() - start >= maximum:
            raise TimeoutError('Diagnostic stream did not become quiet')
        chunk = link.read(4096)
        if chunk:
            data.extend(chunk); last = time.monotonic()
    return bytes(data)


def fresh_sync(link, run, stage):
    # FF/A5/00 are diagnostic observations. Preserve every raw startup byte;
    # unlike the frozen text-only deployment synchronizer, never decode it.
    startup = response = trailing = b''
    try:
        startup = quiet_capture(link)
        link.send(b'\r')
        response = link.until(board.MON_PROMPT, 15)
        trailing = quiet_capture(link)
        r.require(not trailing or trailing.endswith(board.MON_PROMPT), 'Unexpected trailing diagnostic startup')
    finally:
        pf.atomic(Path(run) / ('fresh-link-' + stage + '.bin'), startup + response + trailing + bytes(link.pending))


def owner_check(link, args, *, fresh=False):
    cap = args.backup_run / 'capture'
    ram = (cap / 'application-ram.bin').read_bytes(); zp = (cap / 'owner-zp.bin').read_bytes()
    for _ in range(2):
        r.require(link.dump(0, pf.ZP_LAST) == zp, 'Owner ZP00-DF differs; retain escrow for inspection')
        if fresh:
            r.require(board.workflow.read_range(link, pf.RAM_FIRST, pf.RAM_LAST) == ram,
                      'Latest owner RAM differs from fresh backup; make a new backup')


def borrowed(args, link, marker, state):
    r.require(state['phase'] == 'prepared' and not state['application_RAM_restore_pending'], 'Single-use software start required')
    pf.identity(link); owner_check(link, args, fresh=True)
    original = args.marker.read_bytes(); pf.atomic(args.run / 'device-marker-before.json', original)
    state.update(application_RAM_restore_pending=True)
    checkpoint(args, marker, state, 'borrowing-escrowed-RAM', True)
    board.select_ftdi(link, pf.BUILD, pf.expected_banks(), args.run, 'diagnostic-begin')
    r.require(board.workflow.flash(link) == pf.expected_banks(), 'Source flash changed since repeated backup')


def decode_capsule(raw, case, nonce):
    r.require(len(raw) == 256 and len(nonce) == 16 and any(nonce), 'Invalid capsule/nonce span')
    r.require(raw[:5] == b'RFP1\x01' and raw[5] == case and raw[10] == (case ^ 255)
              and raw[7] in (1, 2, 128) and raw[11] == (raw[7] ^ 255)
              and raw[12] ^ raw[13] == 255 and raw[15] == 0xa5
              and raw[240:] == nonce and raw[6] <= 14,
              'Fresh diagnostic capsule identity/commit/nonce differs')
    checksum = functools.reduce(int.__xor__, (b for n, b in enumerate(raw) if n != 15), 0)
    r.require(checksum == 0, 'Capsule checksum differs')
    phase = 0xf0 if raw[7] == 1 else (0xa0 | case) if raw[7] == 2 else 0xe0
    r.require(raw[6] >= 1 and raw[12] == phase
              and (raw[7] == 128 or raw[16 + (raw[6] - 1) * 16] == phase),
              'Capsule phase/status/final snapshot differs')
    fields = ('stage', 'DDRA', 'DDRB', 'IFR_before', 'IER_before', 'PCR', 'ACR', 'ORB', 'ORA_no_handshake', 'IFR_after', 'IER_after')
    rows = [dict(zip(fields, raw[16 + 16*n:27 + 16*n])) for n in range(raw[6])]
    return dict(passed=raw[7] != 128, case=case, status=raw[7], reason=raw[8], phase=raw[12], rows=rows,
                nonce_hex=nonce.hex(), sha256=r.sha(raw))


def read_capsule(args, link, state, *, allow_invalid=False):
    trial = state['current_trial']
    raw = link.dump(CAP, CAP + CAP_BYTES - 1)
    stem = f'trial-{trial["number"]:02d}-case-{trial["case"]:02x}'
    pf.atomic(args.run / (stem + '-capsule.bin'), raw)
    try:
        decoded = decode_capsule(raw, trial['case'], bytes.fromhex(trial['nonce_hex']))
    except ValueError as error:
        trial.update(capsule_verified=False, capsule_valid=False, capsule_captured_before_recovery_G=True,
                     capsule_validation_failure=str(error))
        pf.save(args.run / (stem + '-capsule.json'), dict(passed=False, sha256=r.sha(raw),
                validation_failure=str(error), recovery_only=True))
        if not allow_invalid:
            raise
        return None
    pf.save(args.run / (stem + '-capsule.json'), decoded)
    trial.update(capsule_verified=True, capsule_valid=True, capsule=decoded)
    return decoded


def load_trial(args, link, marker, state, case, row):
    # Read any previous capsule before changing probe code or launching a shim.
    r.require(not state.get('current_trial') or state['current_trial'].get('capsule_verified'),
              'Read the preceding committed capsule before any new G')
    owner_check(link, args)
    board.load_ram_span(link, ENTRY, member(args.probe, row['bin']).read_bytes())
    nonce = secrets.token_bytes(16)
    r.require(any(nonce) and nonce.hex() not in {x['nonce_hex'] for x in state['trials']}, 'Nonce collision')
    capsule = bytes(240) + nonce
    board.load_ram_span(link, CAP, capsule)
    trial = dict(number=len(state['trials']), case=case, nonce_hex=nonce.hex(), capsule_verified=False)
    state['current_trial'] = trial
    state['trials'].append(trial)
    checkpoint(args, marker, state, 'probe-loaded-' + f'{case:02x}', True)
    return trial


def payload(reply):
    echo = b'G 2000\r\n'
    r.require(reply.startswith(echo) and reply.endswith(board.MON_PROMPT), 'Probe MON echo/prompt framing differs')
    return reply[len(echo):-len(board.MON_PROMPT)]


def software(args, link, marker, state, cases):
    borrowed(args, link, marker, state)
    controls = True
    for case in range(6):
        trial = load_trial(args, link, marker, state, case, cases[case])
        reply = link.command('G 2000'); pf.atomic(args.run / f'trial-{trial["number"]:02d}-software.bin', reply)
        # A complete return always reads capsule first, including unexpected bytes.
        cap = read_capsule(args, link, state)
        r.require(cap['status'] == 1, 'Software probe refused or did not finish')
        data = payload(reply); trial.update(raw_payload_hex=data.hex(), completed=True)
        if case in (3, 4):
            trial['known_control_passed'] = data == (b'\xa5' if case == 3 else b'\0')
            controls &= trial['known_control_passed']
        else:
            trial['unexpected_bytes_are_diagnostic_findings'] = True
        owner_check(link, args)
        checkpoint(args, marker, state, 'software-case-complete-' + f'{case:02x}', True)
    state['software_controls_passed'] = controls
    checkpoint(args, marker, state, 'software-tested', False)
    print('Software diagnostic cases captured; RAM remains escrowed/pending. Known controls:', controls, flush=True)


def physical_stream(raw):
    tokens = (b'\r\nWAIT...\r\n', board.CHOICES, b'Boot : 3 2 1 0\r\n', b'STR8-N 2.0proto b07 B3 65C02')
    positions = [raw.find(token) for token in tokens]
    r.require(all(n >= 0 for n in positions) and positions == sorted(positions), 'Complete exact b07 physical boot missing')
    return dict(prefix_before_WAIT_hex=raw[:positions[0]].hex(), bytes=len(raw), sha256=r.sha(raw))


def arm(args, link, marker, state, cases):
    r.require(state.get('software_controls_passed') is True and args.case in cases and args.case >= 8,
              'Qualified known controls and an authorized arm case are required')
    r.require(not state.get('current_trial') or state['current_trial'].get('capsule_verified'),
              'Read the preceding committed capsule before any arm shim or G')
    if link.dump(0x7d02, 0x7d02) != b'\x01':
        board.select_ftdi(link, pf.BUILD, pf.expected_banks(), args.run, 'before-arm-' + f'{args.case:02x}')
    row = cases[args.case]; trial = load_trial(args, link, marker, state, args.case, row)
    state['physical_reset_pending'] = True
    checkpoint(args, marker, state, 'executing-arm-' + f'{args.case:02x}', True)
    link.send(b'G 2000\r')
    setup = link.until(bytes.fromhex(row['arm_marker_hex']), 30)
    setup += quiet_capture(link, seconds=1.0, maximum=8.0)
    pf.atomic(args.run / f'trial-{trial["number"]:02d}-arm-setup.bin', setup)
    r.require(board.MON_PROMPT not in setup, 'Arm returned instead of halting')
    trial['armed_ready_utc'] = board.now()
    checkpoint(args, marker, state, 'awaiting-owner-reset-' + f'{args.case:02x}', True)
    print(f'ARMED 2512 case {args.case:02X}; receiver open for 7200 seconds; press physical RESET once. No TX until boot.', flush=True)
    try:
        raw = link.until(board.MON_PROMPT, ARM_SECONDS)
    except BaseException:
        pf.atomic(args.run / f'trial-{trial["number"]:02d}-reset-partial.bin', bytes(link.pending))
        raise
    pf.atomic(args.run / f'trial-{trial["number"]:02d}-physical-boot.bin', raw)
    # Capsule is the FIRST command after the raw boot, before any shim/reload.
    cap = read_capsule(args, link, state)
    r.require(cap['status'] == 2, 'Physical reset did not retain the fresh committed ARMED capsule')
    trial.update(physical_boot=physical_stream(raw), completed=True, no_TX_after_ARM_before_prompt=True)
    owner_check(link, args)
    state['physical_reset_pending'] = False
    checkpoint(args, marker, state, 'physical-case-complete-' + f'{args.case:02x}', False)


def restore(args, link, marker, state):
    r.require(state['application_RAM_restore_pending'], 'No pending diagnostic escrow to restore')
    if state.get('current_trial') and not state['current_trial'].get('capsule_verified'):
        read_capsule(args, link, state, allow_invalid=True)
    r.require(link.dump(0x7d01, 0x7d01) == b'\x02' and link.dump(0x7d30, 0x7d30) == b'\xb0',
              'Known 65C02 resident MON B required for preservation recovery')
    board.select_ftdi(link, pf.BUILD, pf.expected_banks(), args.run, 'final-preservation')
    r.require(board.workflow.flash(link) == pf.expected_banks(), 'Diagnostic flash differs; preserve evidence and inspect')
    board.restore_original_ram(link, args.backup_run / 'capture')
    prefix = board.software_startup(link, args.run, 'diagnostic-final-BOTH')
    boot = link.until(board.MON_PROMPT, 60)
    physical_stream(prefix + boot)
    pf.atomic(args.run / 'final-BOTH-boot.bin', prefix + boot)
    r.require(link.dump(0x7d01, 0x7d02) == b'\x02\x03' and link.dump(0x7d30, 0x7d30) == b'\xb0',
              'Final ordinary 65C02 BOTH MON B differs')
    owner_check(link, args)
    r.require(board.workflow.read_range(link, pf.RAM_FIRST, pf.RAM_LAST)
              == (args.backup_run / 'capture/application-ram.bin').read_bytes(), 'Full RAM differs after final BOTH boot')
    state.update(passed=True, application_RAM_restore_pending=False, physical_reset_pending=False,
        RAM_restored=True, restoration_full_RAM_comparisons=3, final_RAM_comparisons=1,
        preservation_passed=True, hypothesis_evaluated=False,
        diagnostic_all_trials_valid=all(x.get('capsule_verified') and x.get('completed') for x in state['trials']),
        owner_ZP_preserved=True, flash_unchanged=True, final_console_mode='BOTH', completed_utc=board.now())
    pf.save(args.run / 'state.json', dict(state, phase='completed'))
    pf.atomic(args.marker, (args.run / 'device-marker-before.json').read_bytes())
    print('PASS diagnostic preservation: flash unchanged, full RAM/ZP restored, BOTH MON B; serial closes on exit', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'software-tests', 'arm-reset', 'restore'))
    p.add_argument('--probe', type=Path, required=True); p.add_argument('--backup-run', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--authorization', type=Path)
    p.add_argument('--case', type=lambda x: int(x, 16)); p.add_argument('--watch-reset', action='store_true')
    p.add_argument('--marker', type=Path, default=pf.MARKER)
    p.add_argument('--coordination', type=Path, default=board.DEFAULT_COORDINATION)
    args = p.parse_args()
    args.probe, args.backup_run, args.run = [x.resolve() for x in (args.probe, args.backup_run, args.run)]
    if args.stage == 'prepare':
        prepare(args.probe, args.backup_run, args.run); print('PASS offline diagnostic preparation', flush=True); return
    r.require(args.authorization, 'Explicit RAM-only diagnostic authorization required')
    auth = r.read(args.authorization); admit(args, auth)
    state = r.read(args.run / 'state.json')
    r.require(not state.get('passed'), 'Completed diagnostic run cannot execute again')
    _, cases = probe_binding(args.probe)
    if args.stage == 'arm-reset':
        r.require(args.case in auth['physical_reset_cases'], 'Physical arm case is outside exact owner scope')
    unverified = state.get('current_trial') and not state['current_trial'].get('capsule_verified')
    r.require(not (state.get('physical_reset_pending') or unverified)
              or (args.stage == 'restore' and args.watch_reset),
              'An unverified/halted probe permits only restore --watch-reset, with zero TX before boot')
    with pf.link_for(args, pending=state['application_RAM_restore_pending'], raw_watch=True) as (link, marker):
        try:
            if args.stage == 'restore' and args.watch_reset:
                print('RESTORE receiver ARMED; owner physical RESET needed; zero TX before MON.', flush=True)
                raw = link.until(board.MON_PROMPT, ARM_SECONDS)
                pf.atomic(args.run / 'recovery-physical-boot.bin', raw)
                if state.get('current_trial') and not state['current_trial'].get('capsule_verified'):
                    read_capsule(args, link, state, allow_invalid=True)
            else:
                fresh_sync(link, args.run, args.stage)
            if args.stage == 'software-tests': software(args, link, marker, state, cases)
            elif args.stage == 'arm-reset': arm(args, link, marker, state, cases)
            else: restore(args, link, marker, state)
        except BaseException:
            state['failure'] = traceback.format_exc()
            if state['application_RAM_restore_pending']:
                checkpoint(args, marker, state, 'inspection-required', False)
            else:
                pf.save(args.run / 'state.json', state)
            raise
    # A positive released receipt is created only after serial.close and the
    # shared lease context both return successfully.
    suffix = '-' + f'{args.case:02x}' if args.stage == 'arm-reset' else ''
    pf.save(args.run / ('stage-result-' + args.stage + suffix + '.json'), dict(
        stage_completed=True, stage=args.stage, serial_released=True, shared_lease_released=True,
        completed_utc=board.now(), state_sha256=r.sha((args.run / 'state.json').read_bytes()),
        marker_sha256=r.sha(args.marker.read_bytes()), preservation_passed=state.get('preservation_passed', False)))


if __name__ == '__main__': main()
