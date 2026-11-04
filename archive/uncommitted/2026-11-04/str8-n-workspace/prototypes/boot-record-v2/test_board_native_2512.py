"""Offline admission and both-CPU exact-runtime FTDI-session shim checks."""
import argparse
import builtins
import importlib.util
from pathlib import Path
import sys
import tempfile
from copy import deepcopy
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / 'tools')]
real_import = builtins.__import__


def deny_serial(name, *args, **kwargs):
    if name == 'serial' or name.startswith('serial.'):
        raise AssertionError('Offline native adapter imported serial')
    return real_import(name, *args, **kwargs)


with patch.object(builtins, '__import__', deny_serial):
    import board_native_2512 as board


def shim_tests(build, plan):
    spec = importlib.util.spec_from_file_location('native_host_core', HERE / 'test.py')
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    plan = Path(plan); build = Path(build)
    info = board.r.read(plan / 'plan.json')
    source_build = Path(info['source_build'])
    original = (plan / 'capture/application-ram.bin').read_bytes()
    results = []
    for which, current, prefix in (('source-b04', source_build, 'source'), ('target-b06', build, 'expected')):
        prototype = board.r.read(current / 'prototype-report.json')
        core.GENERATION = prototype['experimental_generation']
        banks = [(plan / f'{prefix}-b{n}.bin').read_bytes() for n in range(4)]
        rows = [(off + 0x8000, row) for _, off, row in board.deployment_plan.snbt_records(banks)]
        for cpu in ('65c02', '65c816-e'):
            h = core.Machine(current, cpu, rows)
            h.m.banks = list(map(bytearray, banks))
            h.m.ram[0x200:0x6500] = original
            h.run(lambda: bytes(h.m.tx).endswith(b'B3> '), limit=20_000_000)
            h.m.tx.clear()
            assert h.m.ram[0x7d02] == 3
            before = tuple(map(bytes, h.m.banks))

            class Link:
                command = board.wire.Link.command
                dump = board.wire.Link.dump
                write_ram = board.wire.Link.write_ram
                def __init__(self):
                    self.pending = bytearray()
                def send(self, data):
                    h.m.rx.extend(data)
                def until(self, token, seconds=45):
                    if token not in self.pending:
                        h.run(lambda: token in self.pending + h.m.tx, limit=20_000_000)
                        self.pending.extend(h.m.tx); h.m.tx.clear()
                    end = self.pending.index(token) + len(token)
                    raw = bytes(self.pending[:end]); del self.pending[:end]
                    return raw

            link = Link()
            with tempfile.TemporaryDirectory(prefix='native-host-shim-', dir=ROOT / 'tmp') as tmp:
                with patch.object(board.time, 'sleep', return_value=None):
                    receipt = board.select_ftdi(link, current, banks, Path(tmp), which)
                assert receipt['passed'] and receipt['prompt_body'] == 0xb160
                acia_count = len(h.m.acia_writes)
                assert link.dump(0x8000, 0x80ff) == banks[3][:256]
                assert len(h.m.acia_writes) == acia_count, 'FTDI-only dump still wrote ACIA'
                shim = bytes.fromhex(receipt['shim_hex'])
                assert bytes(h.m.ram[0x200:0x2000]) == original[:0x1e00]
                assert bytes(h.m.ram[0x2000 + len(shim):0x6500]) == original[0x1e00 + len(shim):]
                with patch.object(board.time, 'sleep', return_value=None):
                    board.load_ram_span(link, 0x2000, bytes.fromhex(receipt['borrowed_original_hex']))
                assert bytes(h.m.ram[0x200:0x6500]) == original
                if which == 'target-b06':
                    startup = board.software_startup(link, Path(tmp), 'CPU-final-BOTH')
                    link.send(b'B'); boot = link.until(board.MON_PROMPT)
                    assert b'Consuming input\r\n' in startup
                    assert prototype['banner'].encode() in boot
                    assert h.m.ram[0x7d02] == 3
                    assert bytes(h.m.ram[0x200:0x6500]) == original
                assert tuple(map(bytes, h.m.banks)) == before and not h.m.events
                # Refuse a stale prompt preimage before any shim write or G.
                altered = list(banks); bad = bytearray(altered[3]); bad[0x3000] ^= 1; altered[3] = bytes(bad)
                try:
                    board.select_ftdi(link, current, altered, Path(tmp), 'must-refuse')
                except ValueError:
                    pass
                else:
                    raise AssertionError('Mismatched MON preimage accepted')
                assert bytes(h.m.ram[0x200:0x6500]) == original
            results.append(dict(cpu=cpu, case=which + '-exact-runtime-FTDI-session-shim', passed=True,
                                startup_initially_BOTH=True, runtime_explicitly_FTDI_only=True,
                                MON_F_worker_vectors_verified_before_G=True, exact_prompt_body=0xb160,
                                owner_RAM_borrowed_13_bytes_then_restored=True,
                                whole_application_RAM_preserved=True, no_flash_mutation=True,
                                stale_MON_preimage_refused_before_write=True,
                                new_target_J3_CRLF_safe_drain_BOTH_cleanup=which == 'target-b06',
                                FTDI_dump_issues_no_ACIA_writes=True))
            print('PASS native host', cpu, which, flush=True)
    return results


def watcher_tests(build):
    raw = b'Consuming input\r\n' + board.CHOICES + b'3 2 1 0\r\nSTR8-N 2.0proto b06 B3 65C02' + board.MON_PROMPT
    rows = []
    for valid in (True, False):
        class Link:
            def send(self, _):
                raise AssertionError('Prearmed receiver transmitted before boot')
            def until(self, token, seconds=45):
                assert token == board.MON_PROMPT and seconds == 1800
                return raw if valid else raw.replace(b'3 2 1 0', b'3')
        with tempfile.TemporaryDirectory(prefix='native-reset-watch-', dir=ROOT / 'tmp') as tmp:
            run = Path(tmp)
            state = dict(transaction_device_verified=True, flash_written=True, application_RAM_restore_pending=True,
                         physical_reset_pending=True, plan_sha256='a' * 64, passed=False)
            marker = dict(application_ram_restored=False)
            post_calls = []
            with patch.object(board, 'post_reset', side_effect=lambda *args: post_calls.append(args)):
                if valid:
                    board.watch_reset(build, run, run, Link(), run / 'marker.json', marker, state)
                    assert len(post_calls) == 1 and post_calls[0][3].fresh_link_startup == raw
                    assert state['prearmed_physical_reset_boot_verified']
                else:
                    try:
                        board.watch_reset(build, run, run, Link(), run / 'marker.json', marker, state)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Partial boot admitted')
                    assert not post_calls
        rows.append(dict(case='prearmed-reset-zero-TX-' + ('complete-boot' if valid else 'partial-boot-refusal'),
                         passed=True, model='buffered host protocol', no_TX_before_exact_boot=True))
    return rows


def admission_tests(build, plan, authorization, run):
    auth = board.r.read(authorization)
    proof = board.prepare(build, plan, run)
    assert board.admission(build, plan, run, auth) == proof
    results = [dict(case='exact-physical-capture-prepare-and-human-authorization', passed=True)]
    actual_read = board.r.read
    mutations = [
        ('startup-missing-CPU', build / 'boot-startup-cpu-tests.json', lambda x: x.__setitem__('cases', x['cases'][:1])),
        ('runtime-component-hash', build / 'ram-tools-runtime-regression.json',
         lambda x: x['component_hashes'].__setitem__('f-offline-component.bin', '0' * 64)),
        ('host-runtime-preimage-check', build / 'native-host-cpu-tests.json',
         lambda x: x['cases'][0].__setitem__('stale_MON_preimage_refused_before_write', False)),
        ('native-commit-order-model', plan / 'model-proof.json',
         lambda x: x['models'][0].__setitem__('native_commit255_last', False)),
        ('owner-RAM-escrow-binding', plan / 'plan.json', lambda x: x.__setitem__('application_ram_sha256', '0' * 64)),
    ]
    for label, path, mutate in mutations:
        def altered_read(candidate):
            value = actual_read(candidate)
            if Path(candidate).resolve() == path.resolve():
                value = deepcopy(value); mutate(value)
            return value
        with patch.object(board.r, 'read', side_effect=altered_read):
            try:
                board.bindings(build, plan)
            except (ValueError, AssertionError):
                pass
            else:
                raise AssertionError('Mutated native proof accepted: ' + label)
        results.append(dict(case='refuse-' + label, passed=True, receipt_files_unchanged=True))
    for label, key, value in (('different-target', 'firmware_sha256', '0' * 64),
                              ('different-plan', 'plan_sha256', '0' * 64),
                              ('other-board-scope', 'other_boards_authorized', True),
                              ('RTC-resume-scope', 'RTC_campaign_resume_authorized', True),
                              ('inactive-feature-scope', 'bench_features_inactive_accepted', False)):
        altered = deepcopy(auth); altered[key] = value
        try:
            board.admission(build, plan, run, altered)
        except ValueError:
            pass
        else:
            raise AssertionError('Mutated owner scope accepted: ' + label)
        results.append(dict(case='refuse-owner-' + label, passed=True, authorization_file_unchanged=True))
    report = dict(passed=True, hardware=False, serial_access=False, checks=len(results), cases=results,
                  authorization_sha256=board.r.sha(authorization.read_bytes()),
                  admission_sha256=board.r.sha((run / 'admission.json').read_bytes()),
                  adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
                  admission_checker_sha256=proof['admission_checker_sha256'],
                  checker_sha256=board.r.sha(Path(__file__).read_bytes()))
    board.save(run / 'offline-admission-tests.json', report)
    print('PASS native positive/negative offline admission', len(results), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True); p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--authorization', type=Path); p.add_argument('--prepare-run', type=Path)
    p.add_argument('--admission-only', action='store_true')
    args = p.parse_args()
    build, plan = args.build.resolve(), args.plan.resolve()
    if args.admission_only:
        assert args.authorization and args.prepare_run
        admission_tests(build, plan, args.authorization.resolve(), args.prepare_run.resolve())
        return
    cases = shim_tests(build, plan)
    watch_cases = watcher_tests(build)
    report = dict(passed=True, hardware=False, serial_access=False, checks=len(cases) + len(watch_cases), cases=cases,
                  component_hashes={p.name: board.r.sha(p.read_bytes()) for p in (build / 'payload').iterdir()
                                    if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')},
                  source_symbols_sha256=board.r.sha((Path(board.r.read(plan / 'plan.json')['source_build']) / 'symbols.json').read_bytes()),
                  source_prototype_report_sha256=board.r.sha((Path(board.r.read(plan / 'plan.json')['source_build']) / 'prototype-report.json').read_bytes()),
                  symbols_sha256=board.r.sha((build / 'symbols.json').read_bytes()),
                  prototype_report_sha256=board.r.sha((build / 'prototype-report.json').read_bytes()),
                  adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),
                  checker_sha256=board.r.sha(Path(__file__).read_bytes()))
    report['reset_watcher_cases'] = watch_cases
    board.save(build / 'native-host-cpu-tests.json', report)
    if args.prepare_run:
        proof = board.prepare(build, plan, args.prepare_run)
        if args.authorization:
            board.admission(build, plan, args.prepare_run, board.r.read(args.authorization))
        print('PASS exact native prepare/admission', args.prepare_run, flush=True)
    print('PASS offline native host checks', len(cases), flush=True)


if __name__ == '__main__':
    main()
