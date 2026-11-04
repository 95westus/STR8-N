"""Explicit, unqualified WDC USB capture/migration transport. Never auto-retries flash.

WDC sync/read/load framing and RTS policy are adapted from this project's
tools/installer/engine/legacy_transport.py (MIT); no vendor implementation or
firmware is included. Importing this module does not import serial or open a port.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time

import nf_migrate as planning


ENGINE_TEMPLATE_SHA256 = '794cc2cb3dc3ea514b4994b4661317cce4e6cb7e9d5dc6a77485a5d3dc682728'
ARCHIVER_SHA256 = '78e2ec2cdfd1145dd2396deef5df1d75409dba8d84b87277f5b3c83b82890b51'
READBACK_SHA256 = '0c04b65ed2354e564d5cec6e2bc113d58934889b35b076586ef14c466fb3a774'
ARCHIVE_READY = b'ARCHIVER READY; G then Enter> '
ARCHIVE_DONE = b'ARCHIVE COMPLETE; PRESS PHYSICAL RESET\r\n'
ENGINE_READY = b'Y then Enter> '
ENGINE_SELF_OK = b'CHECK: RAM image and plan verified\r\n'
ENGINE_SOURCE_OK = b'CHECK: all four bank preimages and SST39SF010A BF/B5 verified\r\n'
ROW_DONE = b'VERIFY: complete B3 postimage verified; sector finished\r\n'
ENGINE_DONE = b'MIGRATION VERIFIED; PRESS PHYSICAL RESET\r\n'
REC = b'REC> '
EXPECTED_ID = {'65c02': b'SXB2', '65c816': b'SXB6'}


class WdcLink:
    """Narrow WDC RAM protocol plus byte-exact console reads; one explicit port."""
    hardware_access = True

    def __init__(self, port, log):
        import serial
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=5)
        self.serial.dtr = False
        self.serial.rtscts = False
        self.serial.rts = True
        self.serial.port = port
        self.serial.open()
        self.log, self.pending = log, bytearray()
        self.loaded = None

    def close(self):
        self.serial.close()

    def record(self, direction, body):
        self.log.write(json.dumps(dict(time=time.time(), direction=direction, hex=body.hex()))+'\n')
        self.log.flush()

    def send(self, body):
        body = bytes(body)
        self.record('TX', body)
        if self.serial.write(body) != len(body):
            raise IOError('Short USB write')
        self.serial.flush()

    def read(self, count):
        body = self.serial.read(count)
        if body:
            self.record('RX', body)
        return body

    def exact(self, count, seconds=30):
        result = bytearray(self.pending[:count])
        del self.pending[:len(result)]
        deadline = time.monotonic()+seconds
        while len(result) < count:
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Incomplete USB response: {len(result)}/{count} bytes')
            result.extend(self.read(count-len(result)))
        return bytes(result)

    def until(self, token, seconds=60):
        deadline = time.monotonic()+seconds
        while True:
            end = self.pending.find(token)
            if end >= 0:
                end += len(token)
                body = bytes(self.pending[:end])
                del self.pending[:end]
                return body
            if b'REFUSED:' in self.pending or b'FAILED:' in self.pending or b'HALTED IN RAM.' in self.pending:
                raise IOError('Device refused/failed: '+bytes(self.pending[-500:]).decode('ascii', 'replace'))
            if time.monotonic() >= deadline:
                raise TimeoutError('Waiting for '+repr(token)+'; last bytes '+repr(bytes(self.pending[-200:])))
            self.pending.extend(self.read(max(1, self.serial.in_waiting)))

    def identity_after_reset(self, seconds=60):
        """Read-only repeated debugger sync while the operator presses RESET."""
        self.serial.reset_input_buffer()
        self.pending.clear()
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            self.send(b'U\xaa')
            received = bytearray()
            stop = min(deadline, time.monotonic()+1)
            while time.monotonic() < stop:
                received.extend(self.read(max(1, self.serial.in_waiting)))
                if b'\xcc' in received:
                    break
            if b'\xcc' not in received:
                continue
            time.sleep(.1)
            self.serial.reset_input_buffer()
            self.send(b'\x0c')
            try:
                identity = self.exact(12, seconds=min(1, max(.1, deadline-time.monotonic())))
            except TimeoutError:
                continue
            planning.require(identity[:3] == b'SXB' and 33 <= identity[3] <= 126,
                             'Unsupported WDC debugger identity')
            return identity
        raise TimeoutError('No WDC debugger identity in the RESET window')

    def protocol(self, command):
        self.send(b'U\xaa')
        planning.require(self.exact(1) == b'\xcc', 'WDC debugger sync failed')
        self.send(bytes((command,)))

    def stock_read(self, address, count):
        planning.require(0 <= address < 0x10000 and 1 <= count <= 32768
                         and address+count <= 0x10000, 'Out-of-range WDC read')
        self.protocol(3)
        self.send(address.to_bytes(3, 'little')+count.to_bytes(3, 'little'))
        return self.exact(count)

    def load_ram(self, image, entry):
        image = bytes(image)
        planning.require(len(image) == 8192 and entry in (0x2000, 0x2010), 'Unexpected RAM image extent/entry')
        self.loaded = None
        for offset in range(0, len(image), 256):
            body, address = image[offset:offset+256], 0x2000+offset
            self.protocol(2)
            self.send(address.to_bytes(3, 'little')+len(body).to_bytes(3, 'little')+body)
            planning.require(self.exact(1) == b'\0', f'WDC RAM load rejected at {address:04X}')
            planning.require(self.stock_read(address, len(body)) == body,
                             f'WDC RAM readback differs at {address:04X}; execution forbidden')
        planning.require(self.stock_read(0x2000, len(image)) == image,
                         'Final complete RAM readback differs; execution forbidden')
        self.loaded = (planning.sha(image), entry)

    def execute_ram(self, entry):
        planning.require(self.loaded is not None and self.loaded[1] == entry,
                         'RAM execution requires this connection to verify the complete upload')
        self.protocol(6)
        self.send(entry.to_bytes(3, 'little'))
        self.loaded = None

    def set_stock_handshake(self, stock):
        self.serial.rts = bool(stock)


class PhaseLog:
    """Append immutable, fsynced phase receipts before consequential operations."""
    def __init__(self, root, *, message=print):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.directory = self.root/'phases'
        self.directory.mkdir(exist_ok=True)
        planning.require(not list(self.directory.glob('*.json')), 'Fresh phase directory required')
        self.counter, self.message = 0, message

    def add(self, phase, **state):
        self.counter += 1
        record = dict(state)
        record.update(schema=1, phase=phase)
        path = self.directory/f'{self.counter:03d}-{phase}.json'
        planning.durable_write(path, planning.encoded(record))
        self.message(f'PHASE {self.counter}: {phase}', flush=True)
        return record


def private_root(root):
    root = Path(root).resolve()
    planning.require(not root.exists(), 'Use a fresh private output directory')
    root.mkdir(parents=True)
    planning.durable_write(root/'.gitignore', b'*\n')
    return root


def verify_identity(identity, cpu, expected=None):
    planning.require(cpu in EXPECTED_ID and len(identity) == 12 and identity[:4] == EXPECTED_ID[cpu],
                     'WDC CPU/board identity does not match the selected model')
    if expected is not None:
        planning.require(identity == expected, 'WDC identity changed from the private capture')


def repeated_read(link, address, count, first_path, repeat_path):
    first = link.stock_read(address, count)
    second = link.stock_read(address, count)
    planning.require(len(first) == count and first == second, f'Fresh repeated read differs at {address:04X}')
    planning.durable_write(first_path, first)
    planning.durable_write(repeat_path, second)
    return first


def capture_wdc(link, root, *, cpu, archiver, archiver_manifest, allow_unqualified=False,
                reset_wait=60, message=print):
    """Capture all banks in RAM, then RESET back to WDC. No flash commands."""
    planning.require(allow_unqualified, 'New archiver is unqualified; explicit --allow-unqualified is required')
    root = Path(root)
    planning.require(root.exists() and not (root/'capture.json').exists(), 'Fresh capture root required')
    phases = PhaseLog(root, message=message)
    phases.add('WDC-connect-requested', hardware_access=bool(link.hardware_access), flash_written=False)
    message('Press physical RESET to connect to the WDC debugger; no flash operation is requested.', flush=True)
    identity = link.identity_after_reset(seconds=reset_wait)
    verify_identity(identity, cpu)
    planning.durable_write(root/'WDC-identity.bin', identity)
    # Save the original owner bytes before the first helper upload.
    original_b3 = repeated_read(link, 0x8000, 32768, root/'wdc-b3-before.bin', root/'wdc-b3-before-repeat.bin')
    repeated_read(link, 0x0200, planning.OWNER_RAM_SIZE, root/'owner-ram.bin', root/'owner-ram-repeat.bin')
    repeated_read(link, 0, planning.OWNER_ZP_SIZE, root/'owner-zp.bin', root/'owner-zp-repeat.bin')
    body = Path(archiver).read_bytes()
    manifest = planning.read_json(archiver_manifest)
    declared = manifest.get('archive_sha256')
    planning.require(manifest.get('build_passed') is True and len(body) == 8192
                     and planning.sha(body) == declared == ARCHIVER_SHA256
                     and planning.fnv(body[:0x1ffc]) == int.from_bytes(body[0x1ffc:], 'little'),
                     'Read-only archiver template/hash manifest mismatch')
    planning.require(manifest.get('flash_commands') is False,
                     'Archiver manifest must explicitly exclude flash write commands')
    entry = 0x2010 if cpu == '65c816' else 0x2000
    phases.add('original-owner-escrow-durable', original_B3_sha256=planning.sha(original_b3),
               owner_RAM_restored=False, helper_upload_not_started=True)
    link.load_ram(body, entry)
    phases.add('archiver-RAM-readback-verified', bytes=len(body), sha256=planning.sha(body), flash_written=False)
    link.execute_ram(entry)
    link.until(ARCHIVE_READY, seconds=60)
    link.send(b'G\r')
    observed = {}
    for pass_number in (1, 2):
        for bank in range(4):
            marker = f'ARCHIVE B{bank} PASS {pass_number}\r\n'.encode('ascii')
            link.until(marker, seconds=60)
            data = link.exact(32768, seconds=60)
            digest = int.from_bytes(link.exact(4), 'little')
            planning.require(digest == planning.fnv(data), f'Archive transfer FNV differs for B{bank}')
            if bank == 3:
                planning.require(data == original_b3, 'RAM archive B3 differs from independent WDC reads')
            if pass_number == 2:
                planning.require(data == observed[bank], f'Independent RAM bank passes differ for B{bank}')
            observed[bank] = data
            suffix = '' if pass_number == 1 else '-repeat'
            planning.durable_write(root/f'b{bank}{suffix}.bin', data)
            phases.add(f'archive-pass-{pass_number}-bank-{bank}-saved', bytes=32768, sha256=planning.sha(data),
                       transfer_fnv=f'{digest:08x}', flash_written=False)
    link.until(ARCHIVE_DONE, seconds=60)
    phases.add('archive-complete-physical-reset-pending', flash_written=False, owner_RAM_restored=False)
    message('Archive saved. Press physical RESET; reconnecting the WDC debugger without launching the vendor application.', flush=True)
    link.set_stock_handshake(True)
    reconnected = link.identity_after_reset(seconds=reset_wait)
    verify_identity(reconnected, cpu, identity)
    again = repeated_read(link, 0x8000, 32768, root/'wdc-b3-after-reset.bin', root/'wdc-b3-after-reset-repeat.bin')
    planning.require(again == original_b3, 'B3 changed during archive/reset; inspect the private capture')
    capture = dict(schema=1, cpu=cpu, board_model=planning.CPU_MODELS[cpu], source_kind='wdcmonv2',
                   method='independent-double-read', wdc_info_hex=identity.hex(),
                   hardware_capture=bool(link.hardware_access), bank_capture='RAM archiver; two complete passes',
                   owner_capture='WDC read twice before first RAM helper upload',
                   post_archive_WDC_identity_rechecked=True, post_archive_B3_double_read_rechecked=True,
                   owner_RAM_restored=False, owner_RAM_restore_required=True,
                   helper_touched_RAM=['2000-3FFF', '6000-601F', 'E0-E9', '0100-01FF'],
                   vendor_startup_SPI_preservation_qualified=False)
    planning.durable_write(root/'capture.json', planning.encoded(capture))
    planning.read_capture(root, cpu, 'wdcmonv2')
    phases.add('capture-verified-stopped-at-WDC', flash_written=False, owner_RAM_restored=False,
               source_sha256=planning.bank_hashes([observed[n] for n in range(4)]))
    message('CAPTURE COMPLETE: flash unchanged; original owner RAM remains escrowed and still requires restoration.', flush=True)
    return capture


def execute_wdc(link, plan_root, run_root, *, allow_unqualified=False, reset_wait=60,
                post_rec=None, message=print, pace=time.sleep):
    """Execute one admitted plan; optional post_rec owns independent readback/restore."""
    planning.require(allow_unqualified, 'New RAM engine is unqualified; explicit --allow-unqualified is required')
    plan_root, run_root = Path(plan_root), Path(run_root)
    plan = planning.inspect(plan_root)
    planning.require(plan['source_kind'] == 'wdcmonv2', 'This executor is the WDC route; use the F-recovery loader separately')
    if plan['transaction']['completed_noop']:
        return dict(migration_needed=False, flash_written=False, owner_RAM_restored=False)
    planning.require(plan.get('engine_template_sha256') == ENGINE_TEMPLATE_SHA256,
                     'Plan is not rendered with the frozen, built NFM1 engine')
    phases = PhaseLog(run_root, message=message)
    state = dict(schema=1, hardware_access=bool(link.hardware_access), execution_qualified=False,
                 flash_written=False, flash_may_have_changed=False, engine_executed=False, device_transaction_verified=False,
                 REC_verified=False, independent_flash_readback_verified=False,
                 owner_RAM_restored=False, owner_RAM_restore_required=True, passed=False,
                 plan_sha256=planning.sha((plan_root/'plan.json').read_bytes()))
    try:
        phases.add('fresh-WDC-admission', **state)
        message('Connect to the WDC debugger (press physical RESET if needed).', flush=True)
        identity = link.identity_after_reset(seconds=reset_wait)
        verify_identity(identity, plan['cpu'], bytes.fromhex(plan['source_identity']['wdc_info_hex']))
        source_b3 = repeated_read(link, 0x8000, 32768, run_root/'fresh-b3.bin', run_root/'fresh-b3-repeat.bin')
        planning.require(source_b3 == (plan_root/'source/b3.bin').read_bytes(), 'Fresh WDC B3 preimage changed')
        # Preserve this working state too; it does not replace pre-archiver owner escrow.
        repeated_read(link, 0x0200, planning.OWNER_RAM_SIZE, run_root/'working-ram.bin', run_root/'working-ram-repeat.bin')
        repeated_read(link, 0, planning.OWNER_ZP_SIZE, run_root/'working-zp.bin', run_root/'working-zp-repeat.bin')
        planning.durable_write(run_root/'erase-intent-before-execution.json', (plan_root/'erase-intent.json').read_bytes())
        phases.add('fresh-source-and-erase-intent-durable', source_B3_sha256=planning.sha(source_b3),
                   other_banks_admission='RAM engine whole-bank FNV preflight before confirmation',
                   owner_RAM_restored=False, flash_written=False)
        image = (plan_root/'migrator.bin').read_bytes()
        entry = int(plan['RAM_entry'], 16)
        link.load_ram(image, entry)
        phases.add('migrator-RAM-readback-verified', bytes=len(image), sha256=planning.sha(image), flash_written=False)
        # This EXEC runs only guarded RAM preflight; flash awaits the later Y.
        state['engine_executed'] = True
        phases.add('RAM-preflight-starting', **state)
        link.execute_ram(entry)
        preflight = link.until(ENGINE_READY, seconds=60)
        planning.require(ENGINE_SELF_OK in preflight and ENGINE_SOURCE_OK in preflight,
                         'Engine did not verify its RAM, all four source banks and supported chip')
        planning.durable_write(run_root/'engine-preflight.txt', preflight)
        phases.add('all-source-guards-verified-before-flash', **state)
        # Durably mark potential mutation before authorizing it, never afterward.
        state['flash_may_have_changed'] = True
        phases.add('flash-authorized-no-automatic-retry', **state)
        message('BEGIN: durable backup/intent and fresh source guards passed; sending the one transaction confirmation.', flush=True)
        link.send(b'Y\r')
        for operation in plan['transaction']['operations']:
            marker = f"SEND 4096 BYTES FOR B3:{operation['address'] >> 12:X}\r\n".encode('ascii')
            ready = link.until(marker, seconds=60)
            phases.add('sector-'+f"{operation['address']:04X}"+'-payload-starting',
                       destination=f"B3:{operation['address']:04X}", bytes=4096,
                       source_b3_fnv=operation['source_b3_fnv'], transfer_sha256=operation['transfer_sha256'])
            body = (plan_root/operation['transfer_file']).read_bytes()
            for offset in range(0, 4096, 64):
                link.send(body[offset:offset+64])
                pace(.01)
            result = link.until(ROW_DONE, seconds=60)
            planning.durable_write(run_root/f"sector-{operation['index']:02d}-console.txt", ready+result)
            state['flash_written'] = True
            phases.add('sector-'+f"{operation['address']:04X}"+'-device-verified',
                       destination=f"B3:{operation['address']:04X}", final_b3_fnv=operation['final_b3_fnv'])
        complete = link.until(ENGINE_DONE, seconds=60)
        planning.durable_write(run_root/'engine-complete.txt', complete)
        state['device_transaction_verified'] = True
        phases.add('device-verified-physical-reset-pending', **state)
        link.set_stock_handshake(False)
        message('DEVICE VERIFIED: press physical RESET once. Waiting for N/F REC>; no automatic reset is issued.', flush=True)
        boot = link.until(REC, seconds=reset_wait)
        planning.require(b'Recovery L ' in boot, 'REC marker lacks the expected N/F recovery face')
        planning.durable_write(run_root/'physical-reset-REC.txt', boot)
        state['REC_verified'] = True
        phases.add('physical-reset-REC-verified', **state)
        if post_rec is not None:
            result = post_rec(link, plan_root, run_root, dict(state))
            planning.require(isinstance(result, dict), 'Post-recovery callback must return its evidence flags')
            state.update(result)
        state['passed'] = bool(state['device_transaction_verified'] and state['REC_verified']
                               and state['independent_flash_readback_verified'] and state['owner_RAM_restored'])
        state['owner_RAM_restore_required'] = not state['owner_RAM_restored']
        phases.add('migration-checkpoint', **state)
        if not state['passed']:
            message('CHECKPOINT: engine/reset passed; independent flash readback and original owner-RAM restoration remain pending.', flush=True)
        planning.durable_write(run_root/'result.json', planning.encoded(state))
        return state
    except BaseException as error:
        state['failure'] = str(error)
        phases.add('inspection-required-no-retry', **state)
        raise


class LoggedRecoveryStream:
    """Keep BASE1 traffic in the same private log, including already buffered bytes."""
    def __init__(self, link):
        self.link = link

    def write(self, body):
        self.link.send(body)
        return len(body)

    def read(self, count):
        if self.link.pending:
            body = bytes(self.link.pending[:count])
            del self.link.pending[:len(body)]
            return body
        return self.link.read(count)


def recovery_callback(readback_file, *, manifest_file=None, message=print, pace=time.sleep):
    """Bind the new BASE1 client; old 25344-byte RAM SERVICE is not compatible."""
    readback = Path(readback_file).read_bytes()
    planning.require(len(readback) == 3078 and planning.sha(readback) == READBACK_SHA256,
                     'Matching BASE1 READBACK image required for complete preservation')
    manifest_file = manifest_file or Path(__file__).resolve().parents[1]/'firmware/minimal-manifest.json'
    manifest = planning.read_json(manifest_file)
    record = manifest['artifacts']['STR8N-F-READBACK-RAM.bin']
    planning.require(manifest.get('profile') == 'BASE1' and manifest.get('F_sha256') == planning.F_SHA256
                     and record['sha256'] == READBACK_SHA256 and record['bytes'] == len(readback),
                     'READBACK does not match the BASE1 component manifest')
    module_path = Path(__file__).resolve().parents[1]/'tools/nf_recovery.py'
    spec = importlib.util.spec_from_file_location('nf_minimal_recovery', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def complete(link, plan_root, run_root, state):
        planning.require(state['REC_verified'], 'BASE1 restoration requires observed physical-reset REC>')
        plan = planning.inspect(plan_root)

        class RecordedClient(module.RecoveryClient):
            def flash(self, bank):
                body = super().flash(bank)
                planning.durable_write(Path(run_root)/f'fresh-post-b{bank}.bin', body)
                return body

        client = RecordedClient(LoggedRecoveryStream(link), progress=lambda text: message(text, flush=True), sleep=pace)
        client.load(readback, READBACK_SHA256, REC_observed=True)
        actual = client.verify_flash(plan['transaction']['expected_sha256'])
        planning.durable_write(Path(run_root)/'independent-flash-readback.json', planning.encoded(
            dict(passed=True, bank_sha256=actual, BASE1_READBACK_sha256=READBACK_SHA256)))
        ram = (Path(plan_root)/'source/owner-ram.bin').read_bytes()
        zp = (Path(plan_root)/'source/owner-zp.bin').read_bytes()
        result = client.restore_owner(ram, zp)
        planning.require(result.get('owner_RAM_restored') is True and result.get('owner_ZP_restored') is True
                         and result.get('stopped_at_REC') is True, 'BASE1 restoration did not finish at REC>')
        result['independent_flash_readback_verified'] = True
        result['fresh_post_bank_sha256'] = actual
        planning.durable_write(Path(run_root)/'owner-RAM-restored.json', planning.encoded(result))
        return result

    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture', help='escrow owner RAM, archive all banks twice in RAM, reset back to WDC')
    capture.add_argument('--archiver', type=Path, required=True)
    capture.add_argument('--archiver-manifest', type=Path, required=True)
    capture.add_argument('--cpu', choices=tuple(planning.CPU_MODELS), required=True)
    execute = sub.add_parser('execute', help='execute a rendered private WDC plan; restoration callback required for completion')
    execute.add_argument('--plan', type=Path, required=True)
    execute.add_argument('--readback', type=Path, required=True)
    execute.add_argument('--readback-manifest', type=Path)
    migrate = sub.add_parser('migrate', help='capture, prepare, migrate, independently verify and restore original owner RAM')
    migrate.add_argument('--archiver', type=Path, required=True)
    migrate.add_argument('--archiver-manifest', type=Path, required=True)
    migrate.add_argument('--cpu', choices=tuple(planning.CPU_MODELS), required=True)
    migrate.add_argument('--capture-out', type=Path, required=True)
    migrate.add_argument('--plan-out', type=Path, required=True)
    migrate.add_argument('--f-image', type=Path, required=True)
    migrate.add_argument('--engine-template', type=Path, required=True)
    migrate.add_argument('--readback', type=Path, required=True)
    migrate.add_argument('--readback-manifest', type=Path)
    migrate.add_argument('--provision-cd', action='store_true')
    migrate.add_argument('--history', type=Path)
    for command in (capture, execute, migrate):
        command.add_argument('--port', required=True)
        command.add_argument('--out', type=Path, required=True)
        command.add_argument('--allow-unqualified', action='store_true')
    args = parser.parse_args()
    if not args.allow_unqualified:
        parser.exit(2, 'REFUSED: this new transport/engine has not been execution-qualified; no port opened.\n')
    root, link = None, None
    try:
        complete = recovery_callback(args.readback, manifest_file=args.readback_manifest) if args.command in ('execute', 'migrate') else None
        if args.command == 'migrate':
            planning.require(planning.sha(args.engine_template.read_bytes()) == ENGINE_TEMPLATE_SHA256,
                             'Matching built RAM engine required before capture')
            planning.require(planning.sha(args.f_image.read_bytes()) == planning.F_SHA256,
                             'Matching frozen 4096-byte F required before capture')
        root = private_root(args.out)
        with (root/'serial.jsonl').open('x', encoding='utf-8', newline='\n') as log:
            link = WdcLink(args.port, log)
            try:
                if args.command == 'capture':
                    capture_wdc(link, root, cpu=args.cpu, archiver=args.archiver,
                                archiver_manifest=args.archiver_manifest, allow_unqualified=True)
                elif args.command == 'execute':
                    execute_wdc(link, args.plan, root, allow_unqualified=True, post_rec=complete)
                else:
                    planning.require(len({args.capture_out.resolve(), args.plan_out.resolve(), root}) == 3,
                                     'Capture, plan and run output directories must differ')
                    captured = private_root(args.capture_out)
                    capture_wdc(link, captured, cpu=args.cpu, archiver=args.archiver,
                                archiver_manifest=args.archiver_manifest, allow_unqualified=True)
                    planning.prepare(captured, args.f_image, args.plan_out, cpu=args.cpu,
                                     source_kind='wdcmonv2', provision_cd=args.provision_cd,
                                     history_file=args.history, template_file=args.engine_template)
                    execute_wdc(link, args.plan_out, root, allow_unqualified=True, post_rec=complete)
            finally:
                link.close()
                link = None
    except (KeyError, OSError, ValueError, TimeoutError) as error:
        parser.exit(2, 'STOPPED: '+str(error)+'\nKeep the private backup/phase log; do not automatically replay a partial operation.\n')


if __name__ == '__main__':
    main()
