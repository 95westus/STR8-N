"""Explicit staged 2512 bench deployment adapter; never run by import.

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
from installer import capture, workflow
from installer.common import board_profile, save
from installer.engine import legacy_transport as wire, install_transport as transport, runtime as r
import deployment_plan

BOARD = '2512'
USB = 'A10MQFLCA'
MON_PROMPT = b'\r\nB3> '
REC_PROMPT = b'REC> '
CHOICES = b'OFFLINE PROTOTYPE S A B 0 1 2 3\r\n'
OI_PROMPT = b'INSTALLER I Q> '
DEFAULT_COORDINATION = ROOT / 'output/qualification/serial-coordination'


def now():
    return datetime.now(timezone.utc).isoformat()


def opaque_admission(build):
    build = Path(build)
    direct = build / 'opaque-installer-cpu-tests.json'
    if direct.exists():
        receipt = r.read(direct)
        r.require(receipt['passed'] and receipt['hardware'] is False and receipt['serial_access'] is False
                  and receipt['symbols_sha256'] == r.sha((build / 'symbols.json').read_bytes())
                  and receipt['prototype_report_sha256'] == r.sha((build / 'prototype-report.json').read_bytes()),
                  'Opaque installer receipt belongs to another exact build')
        for name, digest in receipt['component_hashes'].items():
            r.require(r.sha((build / 'payload' / name).read_bytes()) == digest, 'Opaque component differs: ' + name)
        r.require(receipt['checks'] == 120 and len(receipt['cases']) == 120
                  and all(row['passed'] for row in receipt['cases'])
                  and {row['cpu'] for row in receipt['cases']} == {'65c02', '65c816-e'},
                  'Full opaque suite required on both CPU models')
        return {direct.name: r.sha(direct.read_bytes())}
    path = build / 'bench-runtime-equivalence.json'
    equivalent = r.read(path)
    source = Path(equivalent['source_build'])
    source_path = source / 'opaque-installer-cpu-tests.json'
    report = r.read(source_path)
    r.require(equivalent['passed'] is True and equivalent['hardware'] is False
              and equivalent['serial_access'] is False and equivalent['monitor_execution_qualified'] is False
              and equivalent['source_report_sha256'] == r.sha(source_path.read_bytes())
              and report['passed'] is True and report['checks'] == equivalent['source_cases'] == 120
              and report['hardware'] is False and report['serial_access'] is False
              and len(report['cases']) == 120 and all(row['passed'] for row in report['cases']),
              'Full source OIP1 proof and explicit limited equivalence required')
    r.require(report['symbols_sha256'] == r.sha((source / 'symbols.json').read_bytes())
              and report['prototype_report_sha256'] == r.sha((source / 'prototype-report.json').read_bytes())
              and report['test_source_sha256'] == r.sha((HERE / 'test_opaque_installer.py').read_bytes()),
              'Opaque reference proof changed')
    r.require(equivalent['bench_firmware_sha256'] == r.sha((build / 'firmware.bin').read_bytes())
              and equivalent['bench_symbols_sha256'] == r.sha((build / 'symbols.json').read_bytes())
              and equivalent['bench_core_report_sha256'] == r.sha((build / 'cpu-tests.json').read_bytes())
              and equivalent['bench_target_report_sha256'] == r.sha((build / 'bench-target-tests.json').read_bytes())
              and equivalent['checker_sha256'] == r.sha((HERE / 'test_bench_opaque_equivalence.py').read_bytes()),
              'Bench equivalence bindings changed')
    components = ('f-offline-component.bin', 'ram-config-offline.bin',
                  'ram-installer-offline.bin', 'ram-installer-offline.rlp1')
    r.require(set(equivalent['runtime_component_hashes']) == set(components), 'Incomplete OIP1 runtime equivalence')
    for name in components:
        digest = equivalent['runtime_component_hashes'][name]
        r.require(digest == report['component_hashes'][name]
                  == r.sha((source / 'payload' / name).read_bytes())
                  == r.sha((build / 'payload' / name).read_bytes()), 'Runtime component differs: ' + name)
    for name in ('monitor-a0-offline-component.bin', 'monitor-b0-offline-component.bin'):
        r.require(equivalent['bench_monitor_hashes'][name] == r.sha((build / 'payload' / name).read_bytes()),
                  'Protected bench MON bytes differ')
    source_symbols = r.read(source / 'symbols.json'); symbols = r.read(build / 'symbols.json')
    modules = ('core/str8n-v2-boot', 'core/str8n-v2-worker', 'core/str8n-v2-vectors',
               'core/ram-config', 'core/ram-installer')
    r.require(set(equivalent['runtime_symbols']) == set(modules), 'Incomplete runtime symbol equivalence')
    for module in modules:
        r.require(equivalent['runtime_symbols'][module] == source_symbols[module] == symbols[module],
                  'Runtime symbols differ: ' + module)
    fixed = (build / 'payload/f-offline-component.bin').read_bytes()
    for label, size_key, digest_key in (('BOOT_WORKER_IMAGE', 'worker_bytes', 'worker_sha256'),
                                      ('BOOT_VECTOR_IMAGE', 'vectors_bytes', 'vectors_sha256')):
        off = symbols['core/str8n-v2-boot'][label] - 0xf000
        r.require(r.sha(fixed[off:off + equivalent[size_key]]) == equivalent[digest_key],
                  'Copied RAM runtime bytes differ')
    target_cases = [row for row in equivalent['cases'] if 'bank' in row]
    fallback_cases = [row for row in equivalent['cases'] if 'bank' not in row]
    r.require(len(target_cases) == 4 and len(fallback_cases) == 2
              and {(row['cpu'], row['bank'], row['sector']) for row in target_cases}
              == {(cpu, bank, sector) for cpu in ('65c02', '65c816-e') for bank, sector in ((0, 0xf0), (3, 0xe0))}
              and all(row['passed'] and row['MON_instructions_executed'] == 0
                      and row['F_MON_AB_other_sectors_and_application_RAM_preserved']
                      and row['F_startup_S_selection'] and row['F_RLP1_load_with_MON_absent']
                      for row in target_cases)
              and {row['cpu'] for row in fallback_cases} == {'65c02', '65c816-e'}
              and all(row['passed'] and row['F_startup_control_flow_executed']
                      and row['MON_instructions_executed'] == 0 for row in fallback_cases),
              'Targeted bench OIP1 proof incomplete')
    return {path.name: r.sha(path.read_bytes()), 'source_opaque_report': r.sha(source_path.read_bytes())}


def bindings(build, plan):
    build, plan = Path(build), Path(plan)
    info = deployment_plan.verify(build, plan)
    manifest = r.read(build / 'bench-target.json')
    r.require(manifest.get('bench_core') is True and manifest.get('installation_permitted') is False,
              'An explicit bench-core manifest is required')
    firmware_sha = r.sha((build / 'firmware.bin').read_bytes())
    r.require(manifest['firmware_sha256'] == info['firmware_sha256'] == firmware_sha,
              'Bench target differs from plan')
    r.require(manifest['changed_sectors'] == [[3, 0xa000], [3, 0xb000], [3, 0xf000]],
              'Only F and MON A/B may change in the bench target')
    identity, banks = capture.validate(plan / 'capture', BOARD)
    r.require(identity.get('hardware_capture') is True and identity.get('synthetic_model_fixture') is False,
              'Live workflow requires an original repeated physical capture')
    receipts = {}
    for name in ('prototype-report.json', 'cpu-tests.json', 'bench-target-tests.json'):
        receipt = r.read(build / name)
        r.require(receipt.get('passed', receipt.get('all_components_fit')) is True
                  and receipt.get('hardware', False) is False, 'Missing or failed offline receipt: ' + name)
        receipts[name] = r.sha((build / name).read_bytes())
    prototype = r.read(build / 'prototype-report.json')
    r.require(prototype['bench_core'] and prototype['dual_console']
              and prototype['bootstrap_contract'] == 'PR03', 'Wrong bench component profile')
    payload = build / 'payload'
    for name in ('cpu-tests.json',):
        receipt = r.read(build / name)
        for member, digest in receipt['component_hashes'].items():
            r.require(r.sha((payload / member).read_bytes()) == digest, 'Component receipt differs: ' + member)
        r.require(all(row['passed'] for row in receipt['cases']), 'Failed CPU case')
        r.require({row.get('cpu') for row in receipt['cases']} == {'65c02', '65c816-e'},
                  'Both CPU models required')
    receipts.update(opaque_admission(build))
    matrix = r.read(build / 'bench-target-tests.json')
    r.require(matrix['firmware_sha256'] == firmware_sha and len(matrix['cases']) == 4
              and {(x['CPU'], x['slot']) for x in matrix['cases']}
              == {(cpu, slot) for cpu in ('65c02', '65c816-e') for slot in ('A', 'B')}
              and all(x['passed'] and x['legacy_auxiliary_instruction_fetches'] == 0
                      and x['default_BRK_pointer'] for x in matrix['cases']),
              'Exact live-auxiliary bench gate matrix required')
    proof = r.read(plan / 'model-proof.json')
    import deployment_model
    r.require(proof.get('passed') is True and proof.get('hardware') is False
              and proof['plan_sha256'] == r.sha((plan / 'plan.json').read_bytes())
              and proof['firmware_sha256'] == firmware_sha
              and proof['planner_sha256'] == r.sha(Path(deployment_plan.__file__).read_bytes())
              and proof['model_source_sha256'] == r.sha(Path(deployment_model.__file__).read_bytes()),
              'Exact migration model proof required')
    models = proof['models']
    r.require(len(models) == 6 and all(row['passed'] for row in models)
              and {row.get('CPU') for row in models if row.get('fault') is None}
              == {'65C02', '65C816 E=1'}
              and sum(row.get('fault') == 'stale' for row in models) == 2
              and sum(row.get('fault') == 'corrupt' for row in models) == 2,
              'Success/stale/corrupt migration cases required on both CPUs')
    return dict(board=BOARD, usb_serial=USB, firmware_sha256=firmware_sha,
                manifest_sha256=r.sha((build / 'bench-target.json').read_bytes()),
                plan_sha256=r.sha((plan / 'plan.json').read_bytes()),
                model_proof_sha256=r.sha((plan / 'model-proof.json').read_bytes()),
                adapter_sha256=r.sha(Path(__file__).read_bytes()), receipts=receipts,
                source_sha256=r.hashes(banks), expected_sha256=info['expected_sha256'])


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
                                 application_RAM_restore_pending=False, physical_reset_pending=False))
    return proof


def admission(build, plan, run, auth):
    proof = bindings(build, plan)
    prepared = r.read(Path(run) / 'admission.json')
    for key, value in proof.items():
        r.require(prepared[key] == value, 'Prepared admission changed: ' + key)
    r.require(auth.get('owner_authorized') is True and auth.get('action') == 'deploy-bench-core'
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
    marker.update(state='pr03-bench-' + phase, installer_worker_active=active,
                  installer_plan_sha256=state['plan_sha256'], installer_run=str(Path(run).resolve()),
                  application_RAM_restore_pending=state['application_RAM_restore_pending'],
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


def source_version(link, plan):
    # VERSION's unique final line and following prompt are one token. Earlier
    # queued prompts or a partial startup banner cannot satisfy this command.
    cfg = bytes.fromhex(r.read(Path(plan) / 'plan.json')['transaction']['source_config'])
    footer = b'MONITOR B gen 00000034 VALID' + (b' default' if cfg[8] == 0xb0 else b'') + b'\r\n\r\nB3> '
    link.send(b'VERSION\r')
    version = link.until(footer, 45)
    r.require(b'Build: rc1-r10p2-current' in version and b'Board: 2512' in version
              and b'65C02' in version and b'2.0rc1 g0034' in version,
              'Incomplete or wrong g0034 VERSION identity')
    return version


def source_identity(link, plan):
    version = source_version(link, plan)
    r.require(b'Board: 2512' in version and b'65C02' in version and b'2.0rc1 g0034' in version
              and all(f'MONITOR {slot} gen 00000034 VALID'.encode() in version for slot in ('A', 'B')),
              'Expected physical 2512 g0034 source identity')
    r.require(link.dump(0x7bfc, 0x7bff) == bytes(4), 'Debugger must be inactive')
    _, banks = capture.validate(Path(plan) / 'capture', BOARD)
    original = (Path(plan) / 'capture/application-ram.bin').read_bytes()
    for _ in range(2):
        r.require(workflow.flash(link) == banks, 'Fresh repeated flash differs from escrow')
        r.require(workflow.read_range(link, 0x200, 0x1ff + len(original)) == original,
                  'Fresh repeated owner RAM differs from escrow')
    r.require(int.from_bytes(link.dump(0x7d0a, 0x7d0b), 'little') == 0x1ff + len(original),
              'Source application RAM limit changed')
    expected_slot = bytes.fromhex(r.read(Path(plan) / 'plan.json')['transaction']['source_config'])[8]
    r.require(link.dump(0x7d30, 0x7d30) == bytes([expected_slot]), 'Active monitor differs from saved source default')
    return version


def install(build, plan, run, link, marker_path, marker, state):
    r.require(state['phase'] == 'prepared' and not state.get('flash_written'),
              'Install is single use; pending runs require post-reset/resume')
    (Path(run) / 'version-before.txt').write_bytes(source_identity(link, plan))
    deployment_plan.verify(build, plan)
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
    r.require(len(rows) == 2 and max(rows)[2][32:48] == cfg, 'Final migrated settings differ')
    return expected, symbols, cfg


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
        expected, symbols, cfg = target_check(link, build, plan)
        state.update(physical_reset_pending=False, all_four_banks_verified=True)
        checkpoint(run, marker_path, marker, state, 'read-only-recovery-probe', active=True)
        startup = link.command('J3', CHOICES)
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
        r.require(workflow.flash(link) == expected, 'Read-only recovery probe changed flash')
        state.update(J3_S_verified=True, RLP1_load_readback_verified=True,
                     OIP1_read_only_sector_verified=True, read_only_probe_flash_unchanged=True,
                     boot_verified=True, boot_evidence='software F-to-MON banner plus unique USB identity and full flash hashes',
                     physical_reset_boot_banner_captured=banner in boot,
                     board_identity_evidence='USB serial A10MQFLCA plus original g0034 Board: 2512 admission')
        checkpoint(run, marker_path, marker, state, 'restoring-owner-ram', active=True)
        restore_original_ram(link, Path(plan) / 'capture')
        state.update(application_RAM_restore_pending=False, RAM_restored=True,
                     loader_full_range_readback=True, full_RAM_rereads=2,
                     physical_reset_pending=False, passed=True, completed_utc=now())
        state.pop('failure', None)
        marker.update(firmware=r.read(Path(build) / 'bench-target.json')['banner'], monitor_generation=int.from_bytes(cfg[9:13], 'little'),
                      current_firmware_profile='experimental-bench-core',
                      current_firmware_sha256=r.sha((Path(build) / 'firmware.bin').read_bytes()),
                      application_ram_restored=True, bench_features_inactive=True)
        checkpoint(run, marker_path, marker, state, 'completed', active=False)
    except BaseException:
        state.update(passed=False, failure=traceback.format_exc())
        checkpoint(run, marker_path, marker, state, 'inspection-required', active=False)
        raise


def resume(build, plan, run, link, marker_path, marker, state):
    r.require(link.command('').endswith(MON_PROMPT), 'Physical RESET to a known idle MON is required before resume')
    actual = workflow.flash(link)
    source = [(Path(plan) / f'source-b{n}.bin').read_bytes() for n in range(4)]
    expected = [(Path(plan) / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    if actual == expected:
        state['target_observed_complete_on_resume'] = True
        return post_reset(build, plan, run, link, marker_path, marker, state)
    if actual == source:
        source_identity_without_ram = source_version(link, plan)
        r.require(b'Board: 2512' in source_identity_without_ram and b'2.0rc1 g0034' in source_identity_without_ram,
                  'Original source monitor identity differs')
        restore_original_ram(link, Path(plan) / 'capture')
        state.update(application_RAM_restore_pending=False, physical_reset_pending=False,
                     RAM_restored=True, full_RAM_rereads=2, passed=True,
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
    with serial_lease('pr03-bench-2512-' + args.stage, timeout=30):
        marker = r.read(args.marker)
        marker_ready(marker, args.run, args.plan, pending=pending, campaign_receipt=campaign)
        ports = [port for port in comports() if port.serial_number == USB]
        r.require(len(ports) == 1, 'Unique 2512 USB discovery required; no other board may be opened')
        with (args.run / ('serial-' + args.stage + '-' + datetime.now().strftime('%Y%m%dT%H%M%S') + '.jsonl')).open('x') as log:
            link = wire.Link(ports[0].device, log)
            try:
                fresh_link_sync(link, args.run, args.stage)
                yield link, marker
            finally:
                link.serial.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'install', 'post-reset', 'resume'))
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
    if args.stage == 'post-reset':
        r.require(state.get('transaction_device_verified') is True and state.get('flash_written') is True
                  and state.get('phase') in ('awaiting-physical-reset', 'inspection-required'),
                  'Normal post-reset requires an exact device-verified pending install')
    save(args.run / 'owner-authorization.json', auth)
    with live_link(args, pending=args.stage != 'install') as (link, marker):
        try:
            if args.stage == 'install':
                install(args.build, args.plan, args.run, link, args.marker, marker, state)
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
