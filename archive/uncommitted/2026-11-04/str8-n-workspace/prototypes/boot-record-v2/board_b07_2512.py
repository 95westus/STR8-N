"""Separate native-SNBT b06 -> b07 PR04 bench adapter; never run by import.

prepare/self-test are offline. install/post-reset/resume are the only commands
which may import serial, and require exact owner scope, receipts and the shared
repository serial lease. This adapter itself has no hardware qualification.
"""
import argparse
import contextlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from installer import workflow
from installer.common import board_profile, save
from installer.engine import legacy_transport as wire, install_transport as transport, runtime as r
import deployment_b07 as deployment_plan
import capture_b07_2512 as capture

BOARD = '2512'
USB = 'A10MQFLCA'
MON_PROMPT = b'\r\nB3> '
REC_PROMPT = b'REC> '
CHOICES = b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'
OI_PROMPT = b'INSTALLER I Q> '
DEFAULT_COORDINATION = ROOT / 'output/qualification/serial-coordination'


def now():
    return datetime.now(timezone.utc).isoformat()


def bindings(build, plan):
    from b07_admission import bindings as native_bindings
    return native_bindings(build, plan, adapter_file=Path(__file__))


def prepare(build, plan, run):
    build, plan, run = map(lambda p: Path(p).resolve(), (build, plan, run))
    proof = bindings(build, plan)
    r.require(not run.exists(), 'Use a fresh private run directory')
    run.mkdir(parents=True); (run / '.gitignore').write_text('*\n')
    save(run / 'admission.json', dict(**proof, prepared_utc=now(), hardware=False,
                                     adapter_hardware_qualified=False, build=str(build), plan=str(plan),
                                     unsupported_steps=[
                                         'Interrupted F erase/program may require external root recovery; OIP1 cannot rewrite F',
                                         'Automatic partial-flash resume or reflash',
                                         'ACIA electrical/CTS qualification',
                                         'Live RTC time/trim measurements; this adapter issues no RTC setter/trim/ACK command']))
    save(run / 'state.json', dict(phase='prepared', passed=False, board=BOARD,
                                 plan_sha256=proof['plan_sha256'], flash_written=False,
                                 plan_path=str(plan), build_path=str(build),
                                 application_RAM_restore_pending=False, physical_reset_pending=False))
    return proof


def admission(build, plan, run, auth):
    proof = bindings(build, plan)
    prepared = r.read(Path(run) / 'admission.json')
    for key, value in proof.items():
        r.require(prepared[key] == value, 'Prepared admission changed: ' + key)
    r.require(auth.get('owner_authorized') is True and auth.get('action') == 'deploy-native-b07-bench-core'
              and (auth.get('board'), auth.get('usb_serial')) == (BOARD, USB)
              and auth.get('bench_features_inactive_accepted') is True
              and auth.get('scope_profile') == 'bench-core'
              and auth.get('other_boards_authorized') is False
              and auth.get('RTC_campaign_resume_authorized') is False,
              'Explicit owner acceptance of the bench feature scope is required')
    for key in ('firmware_sha256', 'manifest_sha256', 'plan_sha256'):
        r.require(auth.get(key) == proof[key], 'Owner authorization differs: ' + key)
    return proof


def marker_ready(marker, run, plan, *, pending=False, campaign_receipt=None):
    r.require(marker.get('board') == BOARD, 'Marker must identify only 2512')
    r.require(not any(value for key, value in marker.items() if key.endswith('_worker_active'))
              and not marker.get('current_soak_worker_pid') and not marker.get('owner_application_running')
              and not marker.get('power_off_reported') and not marker.get('poweroff_pending_owner_confirmation'),
              'A board owner, worker or power operation remains active')
    stopped = marker.get('soak_owner_stopped') is True and marker.get('RTC_sampling_owner_stopped') is True
    if not stopped and campaign_receipt is not None:
        stopped = campaign_receipt.get('passed') is True and campaign_receipt.get('ports_released') is True
    r.require(stopped, 'Stopped campaign owners or their completed ports-released receipt required')
    if pending:
        r.require(marker.get('application_RAM_restore_pending') is True
                  and marker.get('installer_plan_sha256') == r.sha((Path(plan) / 'plan.json').read_bytes())
                  and marker.get('installer_run') == str(Path(run).resolve()), 'No exact pending run escrow')
    else:
        r.require(not any(marker.get(key) for key in ('block_snapshot', 'application_RAM_restore_pending',
                                                     'physical_reset_pending', 'RTC_collection_pending_monitor_recovery')),
                  'Board has a pending operation')


def checkpoint(run, marker_path, marker, state, phase, *, active):
    state.update(phase=phase, updated_utc=now())
    save(Path(run) / 'state.json', state)
    marker.update(state='pr04-native-bench-' + phase, installer_worker_active=active,
                  installer_plan_sha256=state['plan_sha256'], installer_run=str(Path(run).resolve()),
                  installer_plan=state.get('plan_path', marker.get('installer_plan')),
                  application_RAM_restore_pending=state['application_RAM_restore_pending'],
                  application_ram_restored=not state['application_RAM_restore_pending']
                      and (state.get('RAM_restored') or marker.get('application_ram_restored', False)),
                  physical_reset_pending=state['physical_reset_pending'],
                  block_snapshot=state['application_RAM_restore_pending'] or not state.get('passed', False))
    save(marker_path, marker)


def fresh_link_sync(link, run, stage, *, quiet_seconds=1.0, maximum_seconds=8.0):
    """Capture fresh-link text and establish one quiet command boundary.

    This runs once immediately after opening a link, before any stage protocol.
    It never flushes a device buffer and must never be called mid-binary-frame.
    """
    r.require(quiet_seconds >= 1.0 and maximum_seconds >= quiet_seconds, 'Unsafe startup quiet bound')
    captured = bytearray()
    phases = []
    prefix = Path(run) / ('fresh-link-' + stage + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    result = dict(passed=False, stage=stage, fresh_link_only=True, quiet_seconds=quiet_seconds,
                  maximum_seconds_per_drain=maximum_seconds, phases=phases)

    def drain(name, require_prompt=False):
        start = last = time.monotonic()
        initial = bytes(link.pending)
        raw = bytearray(initial); captured.extend(initial)
        while True:
            moment = time.monotonic()
            if moment - last >= quiet_seconds and (not require_prompt or raw.endswith(MON_PROMPT)):
                # Clear only captured, validated startup text from the host's
                # pending buffer. Newly read bytes were never discarded there.
                r.require(all(byte in (8, 9, 10, 13, 127) or 32 <= byte <= 126 for byte in raw),
                          'Fresh link contains non-text bytes; retain evidence and RESET to MON')
                del link.pending[:len(initial)]
                phases.append(dict(name=name, bytes=len(raw), elapsed_seconds=moment-start,
                                   sha256=r.sha(raw), ended_with_MON_prompt=raw.endswith(MON_PROMPT)))
                return bytes(raw)
            if moment - start >= maximum_seconds:
                raise TimeoutError('No quiet fresh-link ' + name + ' boundary within the bounded startup window')
            data = link.read(4096)
            if data:
                raw.extend(data); captured.extend(data); last = time.monotonic()

    try:
        drain('startup')
        link.send(b'\r')
        drain('idle-command', require_prompt=True)
        r.require(not link.pending, 'Fresh synchronization left unconsumed startup bytes')
        link.fresh_link_startup = bytes(captured)
        result['passed'] = True
        return result
    finally:
        Path(str(prefix) + '.bin').write_bytes(captured)
        result.update(captured_bytes=len(captured), captured_sha256=r.sha(captured),
                      captured_path=str(Path(str(prefix) + '.bin')))
        save(Path(str(prefix) + '.json'), result)
        link.fresh_link_startup = bytes(captured)
        link.fresh_link_startup_path = result['captured_path']


def source_identity(link, plan):
    # The bench profile deliberately has no legacy VERSION provider.
    capture.validate(Path(plan) / 'capture')
    r.require(link.command('').endswith(MON_PROMPT)
              and link.dump(0x7d01, 0x7d01) == b'\x02', 'Expected idle 2512 65C02 bench monitor')
    original = (Path(plan) / 'capture/application-ram.bin').read_bytes()
    for _ in range(2):
        r.require(workflow.read_range(link, 0x200, 0x1ff + len(original)) == original,
                  'Fresh repeated owner RAM differs from escrow')
    expected_slot = bytes.fromhex(r.read(Path(plan) / 'plan.json')['transaction']['source_config'])[8]
    r.require(link.dump(0x7d30, 0x7d30) == bytes([expected_slot]), 'Active monitor differs from saved source default')
    return dict(board=BOARD, usb_serial=USB, CPU='65C02', source='2.0proto b06',
                original_RAM_rereads=2, provider_VERSION_required=False)


def load_ram_span(link, address, body):
    """Direct public S19 loader; bench M is an inactive provider command."""
    r.require(0x200 <= address < address + len(body) <= 0x6500, 'Borrowed RAM span outside owner escrow')
    packet = wire.s19(dict(enumerate(body, address)), address)
    link.command('L', b'S19')
    for row in packet.splitlines():
        link.send(row + b'\r\n'); time.sleep(.04)
    reply = link.until(MON_PROMPT)
    r.require(f'Entry {address:04X}'.encode() in reply
              and not any(item in reply for item in (b'Bad', b'Protected', b'Wrap', b'Error'))
              and link.dump(address, address + len(body) - 1) == body, 'Borrowed RAM S19 load/readback failed')


def select_ftdi(link, build, banks, run, phase):
    """Escrowed 13-byte application shim; execute only after exact runtime reads.

    Callers must already mark application_RAM_restore_pending before calling.
    It jumps to the actual MON B prompt body, bypassing all reinitialization.
    """
    build = Path(build)
    sy = r.read(build / 'symbols.json')
    prototype = r.read(build / 'prototype-report.json')
    r.require(prototype['bench_core'] and prototype['dual_console'], 'Exact dual bench runtime required')
    r.require(link.command('B3').endswith(MON_PROMPT)
              and link.dump(0x7d30, 0x7d30) == b'\xb0', 'FTDI shim requires active resident MON B')
    # Full code sectors and the actual copied RAM ABI are read before G.
    for first in (0xb000, 0xf000):
        r.require(link.dump(first, first + 4095) == banks[3][first - 0x8000:first - 0x7000],
                  'FTDI shim code preimage differs')
    fixed = banks[3][-4096:]
    boot, worker = sy['core/str8n-v2-boot'], sy['core/str8n-v2-worker']
    for label, start, count in (('BOOT_WORKER_IMAGE', 0x7800, prototype['f']['worker_bytes']),
                                ('BOOT_VECTOR_IMAGE', 0x7e20, prototype['f']['vectors_bytes'])):
        off = boot[label] - 0xf000
        r.require(link.dump(start, start + count - 1) == fixed[off:off + count],
                  'FTDI shim copied runtime differs')
    prompt = sy['core/monitor-b0']['V2_PROMPT']
    r.require(prompt == 0xb160 and banks[3][prompt - 0x8000:prompt - 0x8000 + 5]
              == bytes.fromhex('ADF97DC954'), 'Exact prompt-body opcodes differ')
    shim = bytes.fromhex('78D8A9018D027D20797E4C') + prompt.to_bytes(2, 'little')
    borrowed = link.dump(0x2000, 0x2000 + len(shim) - 1)
    load_ram_span(link, 0x2000, shim)
    reply = link.command('G 2000')
    r.require(reply.endswith(MON_PROMPT) and link.dump(0x7d02, 0x7d02) == b'\x01', 'FTDI-only prompt return failed')
    evidence = dict(passed=True, phase=phase, build=str(build), runtime_mask=1,
                    prompt_body=prompt, prompt_prefix_hex='ADF97DC954', shim_hex=shim.hex(),
                    borrowed_address=0x2000, borrowed_original_hex=borrowed.hex(),
                    restore_covered_by_full_application_RAM_escrow=True,
                    F_MON_worker_vectors_readback_before_G=True,
                    F_sha256=r.sha(fixed), MON_B_sha256=r.sha(banks[3][0x3000:0x4000]),
                    startup_initialization_policy_unchanged=True)
    save(Path(run) / ('ftdi-session-' + phase + '.json'), evidence)
    return evidence


def install(build, plan, run, link, marker_path, marker, state):
    r.require(state['phase'] == 'prepared' and not state.get('flash_written'),
              'Install is single use; pending runs require post-reset/resume')
    save(Path(run) / 'source-identity.json', source_identity(link, plan))
    deployment_plan.verify(build, plan)
    state.update(application_RAM_restore_pending=True, physical_reset_pending=False, passed=False)
    checkpoint(run, marker_path, marker, state, 'preparing-FTDI-session', active=True)
    _, banks = capture.validate(Path(plan) / 'capture')
    source_build = Path(r.read(Path(plan) / 'plan.json')['source_build'])
    select_ftdi(link, source_build, banks, run, 'source-b06')
    for _ in range(2):
        r.require(workflow.flash(link) == banks, 'Fresh repeated flash differs from native escrow')
    state.update(application_RAM_restore_pending=True, physical_reset_pending=True,
                 flash_may_have_changed=True, passed=False)
    checkpoint(run, marker_path, marker, state, 'installing', active=True)
    try:
        def progress(n, operation):
            state.update(transfers_sent=n, last_destination=f'B{operation["bank"]}:{operation["address"]:04X}')
            checkpoint(run, marker_path, marker, state, 'installing', active=True)
        state.update(transport.execute(link, plan, host_readback=True, progress=progress))
        state['flash_written'] = True
        checkpoint(run, marker_path, marker, state, 'awaiting-physical-reset', active=False)
        print('2512: device-verified transaction halted. Press physical RESET once; keep power on. Then run post-reset.', flush=True)
    except BaseException:
        state['failure'] = traceback.format_exc()
        checkpoint(run, marker_path, marker, state, 'inspection-required', active=False)
        raise


def exact(link, length, seconds=30):
    """Consume bytes already buffered by until(), then bounded raw reads."""
    out = bytearray(link.pending[:length]); del link.pending[:len(out)]
    deadline = time.monotonic() + seconds
    while len(out) < length:
        if time.monotonic() >= deadline:
            raise TimeoutError('Incomplete fixed-length binary read')
        out.extend(link.read(length - len(out)))
    return bytes(out)


def rlp_header(body):
    header = (b'RLP1\x01\x01' + (0x2000).to_bytes(2, 'little')
              + len(body).to_bytes(2, 'little') + (0x2000).to_bytes(2, 'little')
              + wire.crc(body).to_bytes(2, 'little'))
    return header + wire.crc(header).to_bytes(2, 'little')


def rlp_load_readback(link, body):
    r.require(0 < len(body) <= 0x4000, 'RAM tool exceeds F load window')
    link.command('L', b'SEND HEADER+BIN\r\n')
    packet = rlp_header(body) + body
    for off in range(0, len(packet), 64):
        link.send(packet[off:off + 64]); time.sleep(.01)
    reply = link.until(REC_PROMPT)
    r.require(b'LOADED; R runs, V reads back' in reply and b'REFUSED' not in reply, 'RLP1 load refused')
    link.send(b'V\r'); link.until(b'V\r\n')
    raw = exact(link, len(body) + 2)
    r.require(raw[:-2] == body and wire.crc(raw[:-2]) == int.from_bytes(raw[-2:], 'little'),
              'RLP1 readback differs')
    link.until(REC_PROMPT)


def oip_read_only(link, expected):
    r.require(len(expected) == 4096, 'One exact source sector required')
    link.command('R', OI_PROMPT)
    link.command('I', b'SEND OIP1 HEADER\r\n')
    # op=0, B0:8000, length=4096, preimage/payload fields and reserved all zero.
    header = b'OIP1\x01\x00\x00\x80\x00\x10' + bytes(8)
    link.send(header + wire.crc(header).to_bytes(2, 'little'))
    link.until(b'READ SECTOR+CRC\r\n')
    raw = exact(link, 4098)
    r.require(raw[:-2] == expected and wire.crc(expected) == int.from_bytes(raw[-2:], 'little'),
              'Read-only OIP1 sector or CRC differs')
    reply = link.until(OI_PROMPT)
    r.require(b'OK: read' in reply, 'OIP1 read completion missing')
    link.command('Q', REC_PROMPT)


def restore_original_ram(link, cap):
    cap = Path(cap)
    original = (cap / 'application-ram.bin').read_bytes()
    path = cap / 'restore-application-ram.s19'
    r.require(path.read_bytes() == wire.s19(dict(enumerate(original, 0x200)), 0x200)
              and len(original) in (0x6300, 0x6500), 'Escrow restore image changed')
    # Bench AP gating deliberately leaves SVC_DESC at zero. Use the admitted
    # captured application range, rather than legacy workflow.load_ram's probe.
    link.command('L', b'S19')
    for row in path.read_bytes().splitlines():
        link.send(row + b'\r\n'); time.sleep(.04)
    reply = link.until(MON_PROMPT)
    r.require(b'Entry 0200' in reply and not any(x in reply for x in (b'Bad', b'Protected', b'Wrap', b'Error')),
              'Owner RAM restore S19 refused')
    for _ in range(3):
        r.require(workflow.read_range(link, 0x200, 0x1ff + len(original)) == original,
                  'Restored original full application RAM differs')


def target_check(link, build, plan):
    r.require(link.command('').endswith(MON_PROMPT), 'Reset must return to idle MON before verification')
    r.require(link.dump(0x7d01, 0x7d01) == b'\x02', '65C02 runtime identity differs')
    expected = [(Path(plan) / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    for _ in range(2):
        r.require(workflow.flash(link) == expected, 'Repeated full target readback differs')
    symbols = r.read(Path(build) / 'symbols.json')
    r.require(link.dump(0x7e02, 0x7e03) == symbols['core/str8n-v2-vectors']['V2V_DEFAULT'].to_bytes(2, 'little'),
              'Bench default BRK handler differs')
    cfg = bytes.fromhex(r.read(Path(plan) / 'plan.json')['transaction']['target_config'])
    r.require(link.dump(0x7d30, 0x7d30) == cfg[8:9], 'Saved monitor selection differs')
    rows = deployment_plan.snbt_records(expected)
    source_rows = deployment_plan.snbt_records([(Path(plan) / f'source-b{n}.bin').read_bytes() for n in range(4)])
    r.require(len(rows) == len(source_rows) + 1 and max(rows)[2][32:48] == cfg, 'Final migrated settings differ')
    return expected, symbols, cfg


def software_startup(link, run, phase):
    """Use the owner's CRLF case; inject only safe terminators during drain."""
    sent = now()
    link.send(b'J3\r\n')
    before = link.until(b'\r\nWAIT...\r\n', 60)
    drain_seen = now()
    link.send(b'\r\n')
    choices = link.until(CHOICES, 60)
    save(Path(run) / ('software-startup-' + phase + '.json'), dict(passed=True,
         J3_sent_utc=sent, WAIT_received_utc=drain_seen, choices_received_utc=now(),
         J3_terminator='CRLF', injected_during_drain_hex='0d0a',
         injected_input_contains_no_selection_keys=True, startup_sha256=r.sha(before + choices)))
    return before + choices


def post_reset(build, plan, run, link, marker_path, marker, state):
    r.require(state.get('application_RAM_restore_pending') is True
              and (state.get('transaction_device_verified') is True or state.get('target_observed_complete_on_resume') is True),
              'Post-reset requires a device-verified pending install or exact full target observed by resume')
    try:
        checkpoint(run, marker_path, marker, state, 'verifying-target', active=True)
        # A halted RAM installer cannot answer this; a target prompt confirms
        # restart. Record all startup bytes still buffered by the adapter.
        boot = getattr(link, 'fresh_link_startup', b'') + link.command('')
        (Path(run) / 'post-reset-stream.txt').write_bytes(boot)
        target_banks = [(Path(plan) / f'expected-b{n}.bin').read_bytes() for n in range(4)]
        select_ftdi(link, build, target_banks, run, 'target-before-probe')
        expected, symbols, cfg = target_check(link, build, plan)
        state.update(physical_reset_pending=False, all_four_banks_verified=True)
        checkpoint(run, marker_path, marker, state, 'read-only-recovery-probe', active=True)
        startup = software_startup(link, run, 'recovery')
        link.send(b'S'); recovery = link.until(REC_PROMPT)
        (Path(run) / 'software-boot-recovery.txt').write_bytes(startup + recovery)
        r.require(b'RAM recovery L/R/D/V A/B' in recovery, 'F recovery identity differs')
        link.command('C1', REC_PROMPT)
        body = (Path(build) / 'payload/ram-installer-offline.bin').read_bytes()
        rlp_load_readback(link, body)
        oip_read_only(link, expected[0][:4096])
        selected = 'A' if cfg[8] == 0xa0 else 'B'
        reply = link.command(selected, MON_PROMPT)
        (Path(run) / 'monitor-after-probe.txt').write_bytes(reply)
        banner = r.read(Path(build) / 'bench-target.json')['banner'].encode('ascii')
        r.require(b'STR8-N ' + banner + b' B3 65C02' in reply,
                  'Exact software F-to-MON boot banner missing')
        r.require(link.dump(0x7d01, 0x7d01) == b'\x02', 'Post-boot 65C02 identity differs')
        select_ftdi(link, build, expected, run, 'target-after-probe')
        r.require(workflow.flash(link) == expected, 'Read-only recovery probe changed flash')
        state.update(J3_S_verified=True, RLP1_load_readback_verified=True,
                     J3_CRLF_and_safe_CRLF_drain_verified=True,
                     OIP1_read_only_sector_verified=True, read_only_probe_flash_unchanged=True,
                     boot_verified=True, boot_evidence='software F-to-MON banner plus unique USB identity and full flash hashes',
                     physical_reset_boot_banner_captured=banner in boot,
                     board_identity_evidence='USB serial A10MQFLCA plus exact physical native b06 repeated capture',
                     FTDI_only_sessions_explicit_and_escrowed=True)
        checkpoint(run, marker_path, marker, state, 'restoring-owner-ram', active=True)
        restore_original_ram(link, Path(plan) / 'capture')
        # Restore the owner's ordinary BOTH session through public startup.
        # This uses no extra physical reset or flash command and borrows no RAM.
        final_startup = software_startup(link, run, 'final-BOTH')
        # No selection key is sent: capture the complete three-second
        # countdown and saved default B as the final ordinary BOTH session.
        final_boot = link.until(MON_PROMPT, 60)
        r.require(b'Boot : 3 2 1 0\r\n' in final_boot,
                  'Complete final default countdown missing')
        (Path(run) / 'final-BOTH-software-boot.txt').write_bytes(final_startup + final_boot)
        r.require(b'STR8-N ' + banner + b' B3 65C02' in final_boot
                  and link.dump(0x7d02, 0x7d02) == b'\x03'
                  and link.dump(0x7d01, 0x7d01) == b'\x02'
                  and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Final ordinary BOTH MON B boot differs')
        original = (Path(plan) / 'capture/application-ram.bin').read_bytes()
        r.require(workflow.read_range(link, 0x200, 0x64ff) == original,
                  'Original full RAM differs after final public software boot')
        state.update(application_RAM_restore_pending=False, RAM_restored=True,
                     loader_full_range_readback=True, full_RAM_rereads=3,
                     final_software_boot_RAM_reread=True, final_console_mode='BOTH',
                     final_software_boot_verified=True, full_timeout_default_B_verified=True,
                     final_software_boot_no_selection_TX=True,
                     physical_reset_pending=False, passed=True, completed_utc=now())
        state.pop('failure', None)
        marker.update(firmware=r.read(Path(build) / 'bench-target.json')['banner'], monitor_generation=int.from_bytes(cfg[9:13], 'little'),
                      current_firmware_profile='experimental-bench-core',
                      current_firmware_sha256=r.sha((Path(build) / 'firmware.bin').read_bytes()),
                      current_physical_bank_sha256=dict(zip(('B0', 'B1', 'B2', 'B3'), r.hashes(expected))),
                      application_ram_restored=True, application_RAM_restore_verified=True,
                      bench_features_inactive=True, firmware_build='pr04-b07-bench-core',
                      recorded_utc=now(), reason='b07 startup/boot/recovery, exact flash and original full RAM verified',
                      last_recovery_scope='b07 startup, boot/recovery and read-only RLP1/OIP1 probes; bench core',
                      last_recovery_report=str(Path(run) / 'state.json'))
        checkpoint(run, marker_path, marker, state, 'completed', active=False)
    except BaseException:
        state.update(passed=False, failure=traceback.format_exc())
        checkpoint(run, marker_path, marker, state, 'inspection-required', active=False)
        raise


def watch_reset(build, plan, run, link, marker_path, marker, state):
    """Prearmed receiver: absolutely no TX until the complete new boot arrives."""
    r.require(state.get('transaction_device_verified') is True and state.get('flash_written') is True
              and state.get('application_RAM_restore_pending') is True,
              'Reset receiver requires the exact device-verified halted transaction')
    checkpoint(run, marker_path, marker, state, 'watching-physical-reset', active=True)
    armed = now()
    save(Path(run) / 'prearmed-reset-armed.json', dict(receiver_armed_utc=armed,
         maximum_receive_seconds=7200, no_TX_before_exact_boot=True, waiting_for_owner_physical_RESET=True))
    print('2512: RESET receiver armed; waiting for owner physical RESET. No commands are being sent.', flush=True)
    try:
        raw = link.until(MON_PROMPT, 7200)
    except BaseException:
        (Path(run) / 'prearmed-reset-partial.txt').write_bytes(bytes(getattr(link, 'pending', b'')))
        raise
    (Path(run) / 'prearmed-reset-boot.txt').write_bytes(raw)
    banner = b'STR8-N ' + r.read(Path(build) / 'bench-target.json')['banner'].encode() + b' B3 65C02'
    positions = [raw.find(token) for token in (b'\r\nWAIT...\r\n', CHOICES, b'Boot : 3 2 1 0\r\n', banner)]
    r.require(all(pos >= 0 for pos in positions) and positions == sorted(positions) and len(set(positions)) == 4,
              'Complete ordered b07 physical reset startup missing')
    save(Path(run) / 'prearmed-reset-receipt.json', dict(passed=True, receiver_armed_utc=armed,
         boot_received_utc=now(), boot_sha256=r.sha(raw), input_consumption_countdown_and_banner_observed=True,
         no_TX_before_exact_boot=True, exact_physical_press_time_not_measured=True,
         timestamps_in_serial_RX_jsonl=True))
    link.fresh_link_startup = raw
    state.update(prearmed_physical_reset_boot_verified=True, physical_reset_pending=False)
    return post_reset(build, plan, run, link, marker_path, marker, state)


def resume(build, plan, run, link, marker_path, marker, state):
    r.require(link.command('').endswith(MON_PROMPT), 'Physical RESET to a known idle MON is required before resume')
    actual = workflow.flash(link)
    source = [(Path(plan) / f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected = [(Path(plan) / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    if actual == expected:
        state['target_observed_complete_on_resume'] = True
        return post_reset(build, plan, run, link, marker_path, marker, state)
    if actual == source:
        r.require(link.dump(0x7d01, 0x7d01) == b'\x02' and link.dump(0x7d30, 0x7d30) == b'\xb0',
                  'Original source 65C02 MON B identity differs')
        restore_original_ram(link, Path(plan) / 'capture')
        state.update(application_RAM_restore_pending=False, physical_reset_pending=False,
                     RAM_restored=True, full_RAM_rereads=3, passed=True,
                     source_restored_without_flash=True, completed_utc=now())
        state.pop('failure', None)
        checkpoint(run, marker_path, marker, state, 'aborted-source-ram-restored', active=False)
        return
    # Neither known payload progress nor a partially programmed sector is an
    # authorization to reflash. Retain the exact escrow and pending flags.
    save(Path(run) / 'resume-observed-flash.json', dict(observed_utc=now(), sha256=r.hashes(actual)))
    raise ValueError('Partial/unknown flash state: automatic resume/reflash is unsupported; retain escrow for inspection')


@contextlib.contextmanager
def live_link(args, pending):
    # Imports occur only after all offline bindings and owner scope pass.
    from serial_test_coordination import serial_lease, ROOT as lease_root
    from serial.tools.list_ports import comports
    r.require(args.coordination.resolve() == lease_root.resolve() == DEFAULT_COORDINATION.resolve(),
              'Use the repository shared serial coordination directory')
    campaign = r.read(args.campaign_receipt) if args.campaign_receipt else None
    with serial_lease('pr04-native-bench-2512-' + args.stage, timeout=30):
        marker = r.read(args.marker)
        marker_ready(marker, args.run, args.plan, pending=pending, campaign_receipt=campaign)
        ports = [port for port in comports() if port.serial_number == USB]
        r.require(len(ports) == 1, 'Unique 2512 USB discovery required; no other board may be opened')
        with (args.run / ('serial-' + args.stage + '-' + datetime.now().strftime('%Y%m%dT%H%M%S') + '.jsonl')).open('x') as log:
            link = wire.Link(ports[0].device, log)
            try:
                if args.stage != 'watch-reset':
                    fresh_link_sync(link, args.run, args.stage)
                yield link, marker
            finally:
                link.serial.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'install', 'watch-reset', 'post-reset', 'resume'))
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--marker', type=Path, default=ROOT / 'output/qualification/device-operations/2512.json')
    parser.add_argument('--coordination', type=Path)
    parser.add_argument('--campaign-receipt', type=Path)
    args = parser.parse_args()
    args.build, args.plan, args.run = map(lambda p:p.resolve(), (args.build, args.plan, args.run))
    if args.stage == 'prepare':
        prepare(args.build, args.plan, args.run)
        print('PASS offline preparation only; no serial/device access or execution admission', flush=True)
        return
    r.require(args.authorization and args.coordination, 'Explicit authorization and shared coordination are required')
    auth = r.read(args.authorization)
    admission(args.build, args.plan, args.run, auth)
    state = r.read(args.run / 'state.json')
    r.require(not state.get('passed'), 'A completed run cannot be executed again')
    r.require(state['plan_sha256'] == r.sha((args.plan / 'plan.json').read_bytes()), 'Run state plan binding changed')
    if args.stage in ('post-reset', 'watch-reset'):
        r.require(state.get('transaction_device_verified') is True and state.get('flash_written') is True
                  and state.get('phase') in ('awaiting-physical-reset', 'inspection-required'),
                  'Normal post-reset requires an exact device-verified pending install')
    save(args.run / 'owner-authorization.json', auth)
    with live_link(args, pending=args.stage != 'install') as (link, marker):
        try:
            if args.stage == 'install':
                install(args.build, args.plan, args.run, link, args.marker, marker, state)
            elif args.stage == 'watch-reset':
                watch_reset(args.build, args.plan, args.run, link, args.marker, marker, state)
            elif args.stage == 'post-reset':
                post_reset(args.build, args.plan, args.run, link, args.marker, marker, state)
            else:
                resume(args.build, args.plan, args.run, link, args.marker, marker, state)
        except BaseException:
            if state.get('application_RAM_restore_pending'):
                state.update(passed=False, failure=traceback.format_exc())
                checkpoint(args.run, args.marker, marker, state, 'inspection-required', active=False)
            raise


if __name__ == '__main__':
    main()
