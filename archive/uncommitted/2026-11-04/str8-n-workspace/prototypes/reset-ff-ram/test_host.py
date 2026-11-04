"""Buffered protocol/recovery tests, plus pure receipt binding; no ports."""
from pathlib import Path
from types import SimpleNamespace
import functools
import json
import socket
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
before_finders = tuple(sys.meta_path)
before_sockets = (socket.create_connection, socket.socket.connect, socket.socket.connect_ex)
import host as h


def capsule(case=8, status=2, nonce=b'nonce-0123456789'):
    raw = bytearray(256); raw[:5] = b'RFP1\x01'; raw[5] = case; raw[6] = 2; raw[7] = status
    raw[10], raw[11] = case ^ 255, status ^ 255
    phase = 0xf0 if status == 1 else (0xa0 | case) if status == 2 else 0xe0
    raw[12], raw[13] = phase, phase ^ 255; raw[32] = phase
    raw[240:] = nonce; raw[14] = functools.reduce(int.__xor__, raw, 0); raw[15] = 0xa5
    return bytes(raw)


def main():
    cases = []
    nonce = b'nonce-0123456789'; good = capsule(nonce=nonce)
    assert h.decode_capsule(good, 8, nonce)['status'] == 2
    cases.append(dict(case='fresh-committed-nonce-status-phase-capsule', passed=True))
    for label, change in (
        ('stale-nonce', lambda b: b.__setitem__(240, b[240] ^ 1)),
        ('uncommitted', lambda b: b.__setitem__(15, 0)),
        ('checksum', lambda b: b.__setitem__(21, b[21] ^ 1)),
        ('phase-status-join', lambda b: (b.__setitem__(12, 0xf0), b.__setitem__(13, 0x0f))),
    ):
        bad = bytearray(good); change(bad)
        if label == 'phase-status-join':
            bad[14] = 0; bad[14] = functools.reduce(int.__xor__, (v for n, v in enumerate(bad) if n != 15), 0)
        try: h.decode_capsule(bytes(bad), 8, nonce)
        except ValueError: pass
        else: raise AssertionError('Bad capsule accepted: ' + label)
        cases.append(dict(case='refuse-' + label, passed=True))
    for body in (b'', b'\xff', b'\xa5', b'\0', b'\xff\0'):
        assert h.payload(b'G 2000\r\n' + body + h.board.MON_PROMPT) == body
    cases.append(dict(case='raw-software-bytes-retained-including-FF-A5-NUL', passed=True))

    with tempfile.TemporaryDirectory(prefix='reset-ff-host-', dir=h.pf.ROOT / 'tmp') as tmp:
        run = Path(tmp); args = SimpleNamespace(run=run, case=8)
        trial = dict(number=0, case=8, nonce_hex=nonce.hex(), capsule_verified=False)
        state = dict(software_controls_passed=True, current_trial=None, trials=[])
        events = []; ticks = [0.0]
        physical = b'\xff\r\nWAIT...\r\n' + h.board.CHOICES + b'Boot : 3 2 1 0\r\nSTR8-N 2.0proto b07 B3 65C02' + h.board.MON_PROMPT
        marker = b'\r\nRFP1 ARM 08\r\n'
        class ArmLink:
            def __init__(self): self.pending = bytearray(); self.sent = []
            def dump(self, a, b): assert a == b == 0x7d02; return b'\1'
            def send(self, data): self.sent.append(data); events.append('G')
            def read(self, count): ticks[0] += .05; return b''
            def until(self, token, seconds=45):
                if token == marker:
                    self.pending.extend(b'\xff'); return b'G 2000\r\n' + marker
                assert token == h.board.MON_PROMPT and seconds == 7200
                events.append('physical-MON'); return physical
        link = ArmLink()
        def loaded(*_): state['current_trial'] = trial; state['trials'].append(trial); return trial
        def read_cap(*_):
            events.append('capsule-first'); trial['capsule_verified'] = True; return dict(status=2)
        with patch.object(h, 'owner_check'), patch.object(h, 'load_trial', side_effect=loaded), \
             patch.object(h, 'read_capsule', side_effect=read_cap), patch.object(h, 'checkpoint'), \
             patch.object(h.time, 'monotonic', side_effect=lambda: ticks[0]):
            h.arm(args, link, {}, state, {8: dict(arm_marker_hex=marker.hex())})
        assert link.sent == [b'G 2000\r']
        assert events == ['G', 'physical-MON', 'capsule-first']
        assert (run / 'trial-00-arm-setup.bin').read_bytes().endswith(b'\xff')
        assert (run / 'trial-00-physical-boot.bin').read_bytes().startswith(b'\xff')
        assert trial['physical_boot']['prefix_before_WAIT_hex'] == 'ff'
        cases.append(dict(case='setup-ghost-separated-and-zero-TX-armed-watch-first-capsule', passed=True))

    # Exercise actual CLI guard before its context manager can import serial.
    for stage in ('arm-reset', 'restore'):
        with tempfile.TemporaryDirectory(prefix='reset-ff-guard-', dir=h.pf.ROOT / 'tmp') as tmp:
            run = Path(tmp); h.pf.save(run / 'state.json', dict(passed=False, physical_reset_pending=True,
                application_RAM_restore_pending=True, current_trial=dict(capsule_verified=False)))
            h.pf.save(run / 'auth.json', dict(physical_reset_cases=[8]))
            argv = ['host.py', stage, '--probe', str(run), '--backup-run', str(run), '--run', str(run),
                    '--authorization', str(run / 'auth.json'), '--case', '08']
            with patch.object(sys, 'argv', argv), patch.object(h, 'admit'), \
                 patch.object(h, 'probe_binding', return_value=({}, {})), patch.object(h.pf, 'link_for') as opened:
                try: h.main()
                except ValueError as e: assert 'zero TX' in str(e)
                else: raise AssertionError('Halted stage admitted without zero-TX restore watcher')
                assert not opened.called
        cases.append(dict(case='pre-port-block-halted-' + stage, passed=True))

    with tempfile.TemporaryDirectory(prefix='reset-ff-recover-', dir=h.pf.ROOT / 'tmp') as tmp:
        run = Path(tmp); cap = run / 'capture'; cap.mkdir()
        ram = b'\x5a' * 0x6300; zp = bytes(range(0xe0))
        (cap / 'application-ram.bin').write_bytes(ram); (cap / 'owner-zp.bin').write_bytes(zp)
        original = b'{"original_marker":true}\n'; (run / 'device-marker-before.json').write_bytes(original)
        marker_path = run / 'marker.json'; marker_path.write_text('{}')
        args = SimpleNamespace(run=run, backup_run=run, marker=marker_path)
        trial = dict(number=0, case=8, nonce_hex=nonce.hex(), capsule_verified=False)
        state = dict(application_RAM_restore_pending=True, physical_reset_pending=True, trials=[trial], current_trial=trial)
        trace = []
        class RestoreLink:
            def dump(self, a, b):
                if a == h.CAP: trace.append('raw-capsule'); return bytes(256)
                return {(0x7d01, 0x7d01): b'\2', (0x7d30, 0x7d30): b'\xb0',
                        (0x7d01, 0x7d02): b'\2\3', (0, h.pf.ZP_LAST): zp}[(a, b)]
            def until(self, *args):
                return b'Boot : 3 2 1 0\r\nSTR8-N 2.0proto b07 B3 65C02' + h.board.MON_PROMPT
        def shim(*_):
            assert trace == ['raw-capsule']; trace.append('qualified-shim')
        def restored(*_): trace.append('full-RAM-restore')
        prefix = b'J3\r\n\r\nWAIT...\r\n' + h.board.CHOICES
        with patch.object(h.board, 'select_ftdi', side_effect=shim), \
             patch.object(h.board.workflow, 'flash', return_value=h.pf.expected_banks()), \
             patch.object(h.board, 'restore_original_ram', side_effect=restored), \
             patch.object(h.board, 'software_startup', return_value=prefix), \
             patch.object(h.board.workflow, 'read_range', return_value=ram):
            h.restore(args, RestoreLink(), {}, state)
        assert trace == ['raw-capsule', 'qualified-shim', 'full-RAM-restore']
        assert state['preservation_passed'] and not state['diagnostic_all_trials_valid']
        assert not trial['capsule_verified'] and trial['capsule_captured_before_recovery_G']
        assert marker_path.read_bytes() == original
        cases.append(dict(case='invalid-capsule-recorded-but-qualified-owner-RAM-recovery-completes', passed=True))

    with tempfile.TemporaryDirectory(prefix='reset-ff-backup-binding-', dir=h.pf.ROOT / 'tmp') as tmp:
        run = Path(tmp); cap = run / 'capture'; cap.mkdir()
        zp = bytes(range(0xe0)); (cap / 'owner-zp.bin').write_bytes(zp); (cap / 'owner-zp-repeat.bin').write_bytes(zp)
        banks = [bytes([n]) for n in range(4)]; hashes = h.r.hashes(banks)
        identity = dict(owner_zp_sha256=h.r.sha(zp), application_ram_sha256='RAM-fixture')
        common = dict(passed=True, source_sha256=hashes, application_ram_sha256='RAM-fixture',
            owner_zp_sha256=h.r.sha(zp), repeat_readbacks=2, flash_written=False,
            fsynced_before_any_execution=True)
        fast = dict(common, kind='qualified-FTDI-shim-backup', RAM_written=True,
            RAM_borrowed_and_restored=True, RAM_restored=True, ZP_preserved=True,
            original_marker_restored_byte_identical=True, diagnostic_probe_G=False,
            borrowed_address=0x2000, borrowed_bytes=13, restoration_full_RAM_comparisons=3,
            final_RAM_comparisons=1, final_ZP_comparisons=2, final_console_mode='BOTH',
            helper_sha256=h.r.sha((HERE / 'fast_backup.py').read_bytes()),
            preflight_sha256=h.r.sha(Path(h.pf.__file__).read_bytes()))
        finished = dict(fast, stage='fast-backup', serial_released=True,
            marker_unchanged=True, no_flash_or_config_writes=True)
        def write_receipts(meta, done):
            h.pf.save(run / 'backup.json', meta); h.pf.save(run / 'preflight.json', done)
        with patch.object(h.board.capture, 'validate', return_value=(identity, banks)):
            write_receipts(fast, finished)
            assert h.backup_binding(run, hashes)[2]['kind'] == 'qualified-FTDI-shim-backup'
            cases.append(dict(case='qualified-fast-backup-exact-current-helper11-and-preservation-admitted', passed=True))
            for key, value in (('RAM_restored', False), ('final_RAM_comparisons', 0),
                               ('helper_sha256', 'stale'), ('serial_released', False)):
                bad = dict(finished, **{key: value}); write_receipts(fast, bad)
                try: h.backup_binding(run, hashes)
                except ValueError: pass
                else: raise AssertionError('Incomplete fast backup accepted: ' + key)
                cases.append(dict(case='refuse-fast-backup-' + key, passed=True))
            readonly = dict(common, RAM_written=False)
            done = dict(readonly, stage='backup', serial_released=True, marker_unchanged=True,
                helper_sha256=h.r.sha(Path(h.pf.__file__).read_bytes()), no_G_or_R_or_reset=True)
            write_receipts(readonly, done)
            assert h.backup_binding(run, hashes)[2]['kind'] == 'read-only-backup'
            cases.append(dict(case='original-read-only-backup-branch-retained', passed=True))

    manifest, inventory = h.probe_binding(h.pf.ROOT / 'BUILD/reset-ff-ram-probe-r5')
    h.hygiene()
    assert tuple(sys.meta_path) == before_finders
    assert (socket.create_connection, socket.socket.connect, socket.socket.connect_ex) == before_sockets
    assert 'serial' not in sys.modules and 'prepare_monitor_size' not in sys.modules
    cases.append(dict(case='exact-64-case-probe-receipt-pure-hash-admission-no-model-or-serial-import', passed=True))
    h.pf.save(HERE / 'host-tests.json', dict(passed=True, hardware=False, serial_access=False,
        checks=len(cases), cases=cases, host_sha256=h.r.sha(Path(h.__file__).read_bytes()),
        preflight_sha256=h.r.sha(Path(h.pf.__file__).read_bytes()),
        checker_sha256=h.r.sha(Path(__file__).read_bytes()),
        probe_manifest_sha256=h.r.sha((h.pf.ROOT / 'BUILD/reset-ff-ram-probe-r5/manifest.json').read_bytes())))
    print('PASS buffered host protocol and production import hygiene', len(cases), flush=True)


if __name__ == '__main__': main()
