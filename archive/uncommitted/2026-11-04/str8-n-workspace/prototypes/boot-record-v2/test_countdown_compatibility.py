"""Bridge the frozen countdown proof to PR04 and reject mixed private ABIs.

The complete56-group input/timing matrix is bound as prior evidence, not
represented as rerun. New linked-F baselines execute every instruction and
both console delays. Mixed MON admission executes slot checks and startup.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('frozen_countdown_tests', HERE / 'test_boot_countdown.py')
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)
core = cd.core


def read(path):
    return json.loads(path.read_text())


def differences(before, after):
    assert len(before) == len(after)
    return [dict(offset=n, before=x, after=y) for n, (x, y) in enumerate(zip(before, after)) if x != y]


def manifest_hashes(build):
    return {p.name: core.sha(p.read_bytes()) for p in (build / 'payload').iterdir()
            if '-offline' in p.name and p.suffix in ('.bin', '.rlp1')}


def populated(f_build, mon_build, cpu, sector):
    core.GENERATION = read(f_build / 'prototype-report.json')['experimental_generation']
    h = cd.CountdownMachine(f_build, cpu)
    component = (mon_build / f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
    start = (sector - 0x80) << 8
    h.m.banks[3][start:start + 4096] = component
    h.flash = tuple(map(bytes, h.m.banks))
    return h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-build', type=Path, required=True,
                        help='Frozen PR03 r2 countdown build with complete56-group report')
    parser.add_argument('--build', type=Path, required=True, help='PR04 r3 countdown build')
    parser.add_argument('--legacy-build', type=Path, required=True, help='Actual installed b04 PR03 fixture')
    args = parser.parse_args()
    source, build, legacy = (p.resolve() for p in (args.source_build, args.build, args.legacy_build))
    started = time.monotonic()
    prior_path = source / 'boot-countdown-cpu-tests.json'
    prior = read(prior_path)
    assert prior['passed'] and prior['checks'] == 56 and len(prior['cases']) == 56
    assert all(case['passed'] for case in prior['cases'])
    assert prior['checker_sha256'] == core.sha((HERE / 'test_boot_countdown.py').read_bytes())
    assert prior['symbols_sha256'] == core.sha((source / 'symbols.json').read_bytes())
    assert prior['prototype_report_sha256'] == core.sha((source / 'prototype-report.json').read_bytes())
    assert prior['component_hashes'] == manifest_hashes(source)
    old_info, new_info, legacy_info = (read(p / 'prototype-report.json') for p in (source, build, legacy))
    assert old_info['boot_countdown'] and new_info['boot_countdown']
    assert old_info['experimental_generation'] == new_info['experimental_generation'] == 0x80000005
    assert old_info['bootstrap_contract'] == legacy_info['bootstrap_contract'] == 'PR03'
    assert new_info['bootstrap_contract'] == 'PR04'
    old_symbols, new_symbols = read(source / 'symbols.json'), read(build / 'symbols.json')
    assert old_symbols == new_symbols, 'PR04 update moved linked symbols'
    boot = new_symbols['core/str8n-v2-boot']
    before = (source / 'payload/f-offline-component.bin').read_bytes()
    after = (build / 'payload/f-offline-component.bin').read_bytes()
    compatibility = boot['BOOT_COMPAT_DATA'] - 0xf000
    assert before[compatibility:compatibility + 4] == b'PR03'
    assert after[compatibility:compatibility + 4] == b'PR04'
    f_changes = differences(before, after)
    assert f_changes == [dict(offset=compatibility + 3, before=ord('3'), after=ord('4'))]
    monitor_changes = {}
    for sector in (0xa0, 0xb0):
        name = f'monitor-{sector:02x}-offline-component.bin'
        old, new = (p / 'payload' / name for p in (source, build))
        old, new = old.read_bytes(), new.read_bytes()
        changed = differences(old, new)
        assert old[128:] == new[128:], 'MON executable body changed'
        assert old[20:24] == b'PR03' and new[20:24] == b'PR04'
        assert changed and all(item['offset'] in (18, 19, 20, 21, 22, 23) for item in changed)
        for image in (old, new):
            assert core.crc(image[:18] + image[32:]) == int.from_bytes(image[18:20], 'little')
        monitor_changes[name] = changed
    equal_payloads = {}
    for name in ('ram-config-offline.bin', 'ram-installer-offline.bin', 'ram-installer-offline.rlp1'):
        old, new = (source / 'payload' / name).read_bytes(), (build / 'payload' / name).read_bytes()
        assert old == new, ('Non-header runtime component changed', name)
        equal_payloads[name] = core.sha(new)
    for symbol, length, name in (('BOOT_WORKER_IMAGE', new_info['f']['worker_bytes'], 'worker'),
                                  ('BOOT_VECTOR_IMAGE', new_info['f']['vectors_bytes'], 'vectors')):
        offset = boot[symbol] - 0xf000
        assert before[offset:offset + length] == after[offset:offset + length]
        equal_payloads[name] = core.sha(after[offset:offset + length])
    cases = []

    def passed(cpu, case, **details):
        cases.append(dict(cpu=cpu, case=case, passed=True, **details))
        print('PASS', cpu, case, flush=True)

    for cpu in ('65c02', '65c816-e'):
        core.GENERATION = new_info['experimental_generation']
        h = cd.CountdownMachine(build, cpu, target='0')
        start = h.window()
        assert h.dispatch() == 0
        measured = cd.assert_countdown(h)
        expected = next(row for row in prior['cases'] if row['cpu'] == cpu
                        and row['case'] == 'no-input-three-to-zero-and-immediate-saved-default')
        assert measured == expected['consoles']
        assert h.c.processorCycles - start == expected['total_cycles']
        passed(cpu, 'PR04-exact-unaccelerated-three-to-zero-baseline',
               consoles=measured, total_cycles=h.c.processorCycles - start,
               saved_default_bank=0, no_acceleration=True,
               flash_and_application_RAM_unchanged=True)
        for f_name, f_build in (('b04-PR03', legacy), ('b05-PR04', build)):
            for mon_name, mon_build in (('b04-PR03', legacy), ('b05-PR04', build)):
                expected_accept = f_name == mon_name
                for sector in (0xa0, 0xb0):
                    direct = populated(f_build, mon_build, cpu, sector)
                    direct.m.ram[direct.b['BOOT_DEST']] = sector
                    direct.m.ram[0xe0:0xe2] = bytes((0, sector))
                    accepted = direct.call(direct.b['BOOT_SLOT_CHECK'])
                    assert accepted == expected_accept, ('Direct slot check', cpu, f_name, mon_name, sector, accepted)
                    direct.preserved()
                    manual = populated(f_build, mon_build, cpu, sector)
                    manual.m.rx.append(ord('A' if sector == 0xa0 else 'B'))
                    result = manual.dispatch()
                    assert result == (sector if expected_accept else 'recovery'), (
                        'Manual startup selection', cpu, f_name, mon_name, sector, result)
                    manual.preserved()
                    passed(cpu, f'{f_name}-F-with-{mon_name}-MON-{sector:02x}',
                           F_build=str(f_build), MON_build=str(mon_build), accepted=accepted,
                           direct_slot_check_executed=True, actual_manual_startup_executed=True,
                           rejected_to_recovery=not expected_accept,
                           stopped_before_MON_instructions=True,
                           flash_and_application_RAM_unchanged=True)
    output = dict(schema=1, passed=True, checks=len(cases), cases=cases,
                  hardware=False, serial_access=False, device_or_network_attempts=core.ATTEMPTS,
                  source_build=str(source), source_full_countdown_report_sha256=core.sha(prior_path.read_bytes()),
                  source_full_countdown_checker_sha256=prior['checker_sha256'],
                  source_full_countdown_groups=56, source_full_countdown_groups_rerun=False,
                  new_unaccelerated_baseline_groups=2, mixed_slot_matrix_groups=16,
                  proof_scope='The frozen56-group r2 proof is bridged by exact instruction/data/symbol identity '
                              'except the bootstrap contract data byte and MON compatibility header. '
                              'Two full unaccelerated r3 baselines and16 direct/manual slot combinations ran anew.',
                  F_contract_data_address=boot['BOOT_COMPAT_DATA'], F_differences=f_changes,
                  MON_header_differences=monitor_changes, unchanged_runtime_hashes=equal_payloads,
                  runtime_symbols_identical=True, component_hashes=manifest_hashes(build),
                  legacy_build=str(legacy), legacy_component_hashes=manifest_hashes(legacy),
                  source_symbols_sha256=core.sha((source / 'symbols.json').read_bytes()),
                  symbols_sha256=core.sha((build / 'symbols.json').read_bytes()),
                  prototype_report_sha256=core.sha((build / 'prototype-report.json').read_bytes()),
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  checker_sha256=core.sha(Path(__file__).read_bytes()))
    assert len(cases) == 18
    core.save(build / 'countdown-compatibility-cpu-tests.json', output)
    print('PASS total', len(cases), flush=True)


if __name__ == '__main__':
    main()
