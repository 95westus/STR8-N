"""Offline host-adapter protocol checks; no serial discovery, lease, or board."""
import argparse
import builtins
import copy
import json
import importlib.util
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
real_import = builtins.__import__


def no_devices(name, *args, **kwargs):
    if name.split('.')[0] in ('serial', 'socket'):
        raise AssertionError('Offline adapter test attempted a device/network import: ' + name)
    return real_import(name, *args, **kwargs)


with patch.object(builtins, '__import__', no_devices):
    import board_2512 as board


class FakeLink:
    """Coalesced replies deliberately leave raw bytes in until()'s buffer."""
    def __init__(self, tool, sector):
        self.tool, self.sector = tool, sector
        self.pending = bytearray()
        self.sent = []
        self.loading = bytearray()
        self.phase = 'recovery'

    def send(self, data):
        data = bytes(data); self.sent.append(data)
        if self.phase == 'rlp-frame':
            self.loading.extend(data)
            if len(self.loading) == len(self.tool) + 16:
                assert self.loading[:16] == board.rlp_header(self.tool)
                assert self.loading[16:] == self.tool
                self.pending.extend(b'LOADED; R runs, V reads back\r\nREC> ')
                self.phase = 'recovery-loaded'
            else:
                assert len(self.loading) < len(self.tool) + 16
            return
        if self.phase == 'oip-header':
            assert len(data) == 20 and data[:10] == b'OIP1\x01\x00\x00\x80\x00\x10'
            assert data[10:18] == bytes(8)
            assert int.from_bytes(data[18:], 'little') == board.wire.crc(data[:18])
            self.pending.extend(b'READ SECTOR+CRC\r\n' + self.sector
                                + board.wire.crc(self.sector).to_bytes(2, 'little')
                                + b'\r\nOK: read\r\nINSTALLER I Q> ')
            self.phase = 'installer'
            return
        if data == b'L\r' and self.phase == 'recovery':
            self.pending.extend(b'L\r\nSEND HEADER+BIN\r\n'); self.phase = 'rlp-frame'; return
        if data == b'V\r' and self.phase == 'recovery-loaded':
            self.pending.extend(b'V\r\n' + self.tool + board.wire.crc(self.tool).to_bytes(2, 'little') + b'REC> '); return
        if data == b'R\r' and self.phase == 'recovery-loaded':
            self.pending.extend(b'R\r\nINSTALLER I Q> '); self.phase = 'installer'; return
        if data == b'I\r' and self.phase == 'installer':
            self.pending.extend(b'I\r\nSEND OIP1 HEADER\r\n'); self.phase = 'oip-header'; return
        if data == b'Q\r' and self.phase == 'installer':
            self.pending.extend(b'Q\r\nREC> '); self.phase = 'recovery'; return
        raise AssertionError(('Unexpected host packet', self.phase, data[:32]))

    def command(self, text, token=board.MON_PROMPT):
        self.send(text.encode('ascii') + b'\r')
        return self.until(token)

    def until(self, token, seconds=45):
        assert token in self.pending, ('Expected marker absent', token, bytes(self.pending[:80]))
        end = self.pending.index(token) + len(token)
        raw = bytes(self.pending[:end]); del self.pending[:end]
        return raw

    def read(self, length):
        # All raw bytes are coalesced in pending. Reading the device directly
        # would lose them; this catches accidental use of legacy Link.exact.
        raise AssertionError('Raw bytes already reside in pending; adapter lost them')


def startup_sync_checks():
    class Clock:
        value = 0.0
        def monotonic(self):
            return self.value

    footer = b'MONITOR B gen 00000034 VALID default\r\n\r\nB3> '
    version = (b'VERSION\r\nSTR8-N 2.0rc1 g0034 B3 65C02\r\nBoard: 2512\r\n'
               b'Build: rc1-r10p2-current\r\nMONITOR A gen 00000034 VALID\r\n' + footer)

    class Link:
        def __init__(self, clock, events, pending=b''):
            self.clock = clock; self.events = list(events); self.pending = bytearray(pending)
            self.serial = SimpleNamespace(in_waiting=4096); self.sent = []
        def read(self, length):
            self.events.sort(key=lambda event:event[0])
            if self.events and self.events[0][0] <= self.clock.value:
                when, raw = self.events.pop(0)
                if len(raw) > length:
                    self.events.insert(0, (when, raw[length:]))
                return raw[:length]
            self.clock.value += .05
            return b''
        def send(self, raw):
            self.sent.append((self.clock.value, raw))
            if raw == b'\r':
                # The second prompt is delayed >200 ms, matching the failure's
                # observed long startup gaps and defeating a short quiet drain.
                self.events.extend(((self.clock.value + .03, board.MON_PROMPT),
                                    (self.clock.value + .35, b'\r\n' + board.MON_PROMPT)))
            elif raw == b'VERSION\r':
                # A stale prompt precedes a fragmented, genuine VERSION reply.
                self.events.extend(((self.clock.value + .02, board.MON_PROMPT + version[:55]),
                                    (self.clock.value + .40, version[55:-20]),
                                    (self.clock.value + .85, version[-20:])))
            else:
                raise AssertionError('Unexpected startup synchronization command')
        def until(self, token, seconds=45):
            return board.wire.Link.until(self, token, seconds)

    scenarios = (
        ('coalesced-startup-stale-and-double-prompts', [(0, b'\r\nBoard: 2512\r\n' + board.MON_PROMPT * 2)], board.MON_PROMPT),
        ('fragmented-startup-pauses-over-200ms', [(0.05, b'\r\nBoard: 2512\r\nSSRAM: '),
                                                 (.35, b'PROGRAM payload\r\n'),
                                                 (.95, b'RTCC: clock read\r\n'),
                                                 (1.55, b'Battery: within age policy\r\n' + board.MON_PROMPT * 2)], b''),
    )
    rows = []
    source_cfg = '01000307f00a0050b03400000000398d'
    for name, events, pending in scenarios:
        clock = Clock(); link = Link(clock, events, pending)
        with tempfile.TemporaryDirectory(dir=board.ROOT / 'tmp') as tmp:
            assert Path(tmp).resolve().is_relative_to((board.ROOT / 'tmp').resolve())
            with patch.object(board.time, 'monotonic', clock.monotonic):
                result = board.fresh_link_sync(link, Path(tmp), 'install')
                assert result['passed'] and not link.pending and not link.events
                assert link.sent == [(link.sent[0][0], b'\r')]
                idle_cr_time = link.sent[0][0]
                assert clock.value - idle_cr_time >= 1.35
                with patch.object(board.r, 'read', return_value={'transaction': {'source_config': source_cfg}}):
                    reply = board.source_version(link, Path(tmp))
                assert version in reply and reply.endswith(footer)
                assert b'Board: 2512' in link.fresh_link_startup
                assert Path(link.fresh_link_startup_path).read_bytes() == link.fresh_link_startup
                assert not link.pending and not link.events
                assert link.sent[1][0] >= idle_cr_time + 1.35
            evidence = board.r.read(next(Path(tmp).glob('*.json')))
            assert evidence['passed'] and evidence['captured_sha256'] == board.r.sha(link.fresh_link_startup)
        rows.append(dict(case=name, passed=True, quiet_seconds=1.0,
                         delayed_duplicate_prompt_drained=True, unique_VERSION_footer_required=True,
                         startup_bytes_preserved=True))
    for name, events, pending, error in (
            ('non-text-fresh-link-refused-without-command', [(0, board.MON_PROMPT)], b'\x00\xff', ValueError),
            ('continuous-startup-bounded-timeout', [(n * .4, b'STARTUP\r\n') for n in range(23)], b'', TimeoutError)):
        clock = Clock(); link = Link(clock, events, pending)
        with tempfile.TemporaryDirectory(dir=board.ROOT / 'tmp') as tmp:
            assert Path(tmp).resolve().is_relative_to((board.ROOT / 'tmp').resolve())
            with patch.object(board.time, 'monotonic', clock.monotonic):
                try:
                    board.fresh_link_sync(link, Path(tmp), 'install')
                except error:
                    pass
                else:
                    raise AssertionError('Unsafe startup input accepted')
            assert not link.sent and clock.value <= 8.1
            evidence = board.r.read(next(Path(tmp).glob('*.json')))
            assert evidence['passed'] is False
        rows.append(dict(case=name, passed=True, no_command_sent=True, evidence_preserved=True))
    return rows


def cpu_protocol(build):
    spec = importlib.util.spec_from_file_location('board_adapter_cpu_components', HERE / 'test.py')
    tests = importlib.util.module_from_spec(spec)
    # The existing CPU fixture imports socket only to install its deny guard.
    # The live adapter above was imported with serial/socket imports forbidden.
    with patch.object(builtins, '__import__', real_import):
        spec.loader.exec_module(tests)
    report = board.r.read(build / 'prototype-report.json')
    body = (build / 'payload/ram-installer-offline.bin').read_bytes()
    rows = []
    for cpu in ('65c02', '65c816-e'):
        cfg = bytearray([1, 0, 3, 7, 0xf0, 10, 0, ord('P'), 0xb0, 0, 0, 0, 0, 0, 0, 0])
        cfg[9:13] = report['experimental_generation'].to_bytes(4, 'little')
        cfg[14:] = board.wire.config_sum(cfg)
        row = board.deployment_plan.snapshot(bytes(cfg), [1] * 32, 1, 'B', report['experimental_generation'])
        h = tests.Machine(build, cpu, [(0xc000, row)])
        sector = bytes(range(256)) * 16
        h.m.banks[0][:4096] = sector
        h.m.ram[0x200:0x6500] = bytes((n * 17 + 3) & 255 for n in range(0x6300))
        original = bytes(h.m.ram[0x200:0x6500])
        h.run(lambda:bytes(h.m.tx).endswith(b'B3> ')); h.m.tx.clear()
        flash = tuple(map(bytes, h.m.banks))

        class CPULink:
            def __init__(self):
                self.pending = bytearray()
            def send(self, data):
                h.m.rx.extend(data)
            def command(self, text, token=board.MON_PROMPT):
                return board.wire.Link.command(self, text, token)
            def until(self, token, seconds=45):
                if token not in self.pending:
                    h.run(lambda:token in self.pending + h.m.tx)
                    self.pending.extend(h.m.tx); h.m.tx.clear()
                end = self.pending.index(token) + len(token)
                raw = bytes(self.pending[:end]); del self.pending[:end]
                return raw
            def read(self, length):
                h.run(lambda:len(h.m.tx) >= length)
                raw = bytes(h.m.tx[:length]); del h.m.tx[:length]
                return raw

        link = CPULink()
        link.command('J3', board.CHOICES); link.send(b'S'); link.until(board.REC_PROMPT)
        link.command('C1', board.REC_PROMPT)
        board.rlp_load_readback(link, body)
        board.oip_read_only(link, sector)
        banner = link.command('B', board.MON_PROMPT)
        cpu_banner = b'65C02' if cpu == '65c02' else b'65C816'
        assert b'STR8-N ' + report['banner'].encode() + b' B3 ' + cpu_banner in banner, banner
        assert tuple(map(bytes, h.m.banks)) == flash and not h.m.events
        end = 0x2000 + len(body)
        assert bytes(h.m.ram[0x200:0x2000]) == original[:0x1e00]
        assert bytes(h.m.ram[end:0x6500]) == original[end - 0x200:]
        rows.append(dict(case='linked-CPU-host-J3-S-RLP1-OIP1-read-only-MON-boot', cpu=cpu, passed=True,
                         exact_software_boot_banner=True, flash_unchanged=True,
                         application_RAM_outside_escrowed_tool_preserved=True, hardware=False))
    return rows


def admission_checks(build, plan, authorization, run):
    r = board.r
    auth = r.read(authorization)
    proof = board.prepare(build, plan, run)
    assert board.admission(build, plan, run, auth) == proof
    rows = [dict(case='positive-exact-bindings-prepare-and-human-backed-admission', passed=True,
                 run=str(run), authorization_sha256=r.sha(authorization.read_bytes()))]
    path = build / 'bench-runtime-equivalence.json'
    equivalent = r.read(path)
    real_read = r.read
    mutations = []
    for case, edit in (
            ('runtime-component', lambda x:x['runtime_component_hashes'].__setitem__('f-offline-component.bin', '0' * 64)),
            ('firmware', lambda x:x.__setitem__('bench_firmware_sha256', '0' * 64)),
            ('source-report', lambda x:x.__setitem__('source_report_sha256', '0' * 64)),
            ('protected-MON', lambda x:x['bench_monitor_hashes'].__setitem__('monitor-a0-offline-component.bin', '0' * 64)),
            ('runtime-symbol', lambda x:x['runtime_symbols']['core/str8n-v2-worker'].__setitem__('V2W_END', 0)),
            ('MON-execution', lambda x:x['cases'][-1].__setitem__('MON_instructions_executed', 1))):
        damaged = copy.deepcopy(equivalent); edit(damaged)
        mutations.append((case, path, damaged, lambda:board.opaque_admission(build)))
    model_path = plan / 'model-proof.json'
    damaged_model = real_read(model_path); damaged_model['plan_sha256'] = '0' * 64
    mutations.append(('migration-plan-proof', model_path, damaged_model, lambda:board.bindings(build, plan)))
    admission_path = run / 'admission.json'
    damaged_admission = real_read(admission_path); damaged_admission['adapter_sha256'] = '0' * 64
    mutations.append(('prepared-adapter-binding', admission_path, damaged_admission,
                      lambda:board.admission(build, plan, run, auth)))
    for case, changed_path, damaged, action in mutations:
        def read_changed(candidate):
            return copy.deepcopy(damaged) if Path(candidate).resolve() == changed_path.resolve() else real_read(candidate)
        with patch.object(r, 'read', read_changed):
            try:
                action()
            except (ValueError, AssertionError):
                pass
            else:
                raise AssertionError('Mutated admission evidence accepted: ' + case)
        rows.append(dict(case='mutated-receipt-refused-' + case, passed=True))
    for key, value in (('firmware_sha256', '0' * 64), ('other_boards_authorized', True)):
        damaged = copy.deepcopy(auth); damaged[key] = value
        try:
            board.admission(build, plan, run, damaged)
        except ValueError:
            pass
        else:
            raise AssertionError('Mutated owner scope accepted: ' + key)
        rows.append(dict(case='mutated-owner-admission-refused-' + key, passed=True))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--prepare-run', type=Path)
    args = parser.parse_args()
    rows = []
    with patch.object(builtins, '__import__', no_devices), patch.object(board.time, 'sleep', return_value=None):
        for length in (1, 63, 64, 65, 2412, 0x4000):
            tool = (bytes(range(256)) * ((length + 255) // 256))[:length]
            # Include marker-like bytes and every raw byte, including Ctrl-C,
            # CR/LF and FF, to ensure fixed-length reads never scan payloads.
            sector = (b'REC> \r\nINSTALLER I Q> ' + bytes(range(256)) * 16)[:4096]
            link = FakeLink(tool, sector)
            board.rlp_load_readback(link, tool)
            board.oip_read_only(link, sector)
            assert not link.pending and link.phase == 'recovery'
            frames = [p for p in link.sent if p.startswith(b'OIP1')]
            assert len(frames) == 1 and frames[0][5] == 0
            rows.append(dict(case='coalesced-RLP1-readback-and-read-only-OIP1', bytes=length, passed=True))
        rows.extend(startup_sync_checks())
        for changed in ('owner_authorized', 'bench_features_inactive_accepted'):
            proof = dict(firmware_sha256='f', manifest_sha256='m', plan_sha256='p')
            auth = dict(owner_authorized=True, action='deploy-bench-core', board='2512', usb_serial=board.USB,
                        bench_features_inactive_accepted=True, scope_profile='bench-core',
                        other_boards_authorized=False, RTC_campaign_resume_authorized=False, **proof)
            auth[changed] = False
            with tempfile.TemporaryDirectory(dir=board.ROOT / 'tmp') as tmp:
                assert Path(tmp).resolve().is_relative_to((board.ROOT / 'tmp').resolve())
                board.save(Path(tmp) / 'admission.json', proof)
                with patch.object(board, 'bindings', return_value=proof):
                    try:
                        board.admission(Path(tmp), Path(tmp), Path(tmp), auth)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Missing human scope accepted')
            rows.append(dict(case='missing-owner-scope-refused-' + changed, passed=True))
        marker = dict(board='2512', block_snapshot=False, application_RAM_restore_pending=False,
                      physical_reset_pending=False, soak_owner_stopped=True, RTC_sampling_owner_stopped=True)
        board.marker_ready(marker, Path('.'), Path('.'))
        for key in ('installer_worker_active', 'block_snapshot', 'application_RAM_restore_pending',
                    'physical_reset_pending', 'owner_application_running'):
            unsafe = dict(marker, **{key: True})
            try:
                board.marker_ready(unsafe, Path('.'), Path('.'))
            except ValueError:
                pass
            else:
                raise AssertionError('Pending marker was accepted: ' + key)
            rows.append(dict(case='busy-marker-refused-' + key, passed=True))
        if args.build:
            rows.extend(cpu_protocol(args.build.resolve()))
        if any((args.plan, args.authorization, args.prepare_run)):
            assert all((args.build, args.plan, args.authorization, args.prepare_run))
            rows.extend(admission_checks(args.build.resolve(), args.plan.resolve(),
                                         args.authorization.resolve(), args.prepare_run.resolve()))
    output = dict(passed=True, hardware=False, serial_access=False, network_access=False,
                  checks=len(rows), cases=rows, adapter_hardware_qualified=False,
                  adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
                  test_sha256=board.r.sha(Path(__file__).read_bytes()))
    board.save(args.out, output)
    print('PASS', len(rows), 'offline adapter protocol/scope checks; no hardware qualification', flush=True)


if __name__ == '__main__':
    main()
