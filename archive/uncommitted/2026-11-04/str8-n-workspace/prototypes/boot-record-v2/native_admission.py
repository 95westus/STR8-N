"""Exact offline proof bindings for the separate native 2512 deployment."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'tools')]
from installer.engine import runtime as r
import deployment_native as planning
import deployment_native_model as model
import capture_native_2512 as capture


def exact_report(build, name, *, minimum=1, checker=None):
    path = build / name; report = r.read(path)
    r.require(report.get('passed', report.get('pass')) is True and report.get('hardware') is False
              and report.get('serial_access', False) is False, 'Failed or non-offline receipt: ' + name)
    cases = report.get('cases', [])
    r.require(len(cases) >= minimum and all(row.get('passed') is True for row in cases)
              and {row.get('cpu', row.get('CPU')) for row in cases} == {'65c02', '65c816-e'},
              'Both CPU proof cases required: ' + name)
    for member, digest in report.get('component_hashes', {}).items():
        r.require(digest == r.sha((build / 'payload' / member).read_bytes()), 'Receipt component changed: ' + name)
    if 'symbols_sha256' in report:
        r.require(report['symbols_sha256'] == r.sha((build / 'symbols.json').read_bytes()), 'Receipt symbol binding changed')
    if 'prototype_report_sha256' in report:
        r.require(report['prototype_report_sha256'] == r.sha((build / 'prototype-report.json').read_bytes()), 'Receipt build report changed')
    if checker:
        key = 'checker_sha256' if 'checker_sha256' in report else 'test_source_sha256'
        r.require(report[key] == r.sha((HERE / checker).read_bytes()), 'Receipt checker changed: ' + name)
    return report, r.sha(path.read_bytes())


def bindings(build, plan, *, adapter_file):
    build, plan = Path(build), Path(plan)
    info = planning.verify(build, plan)
    identity, banks = capture.validate(plan / 'capture')
    r.require(info['synthetic_model_fixture'] is False, 'Synthetic native plan cannot be physically admitted')
    manifest = r.read(build / 'bench-target.json'); prototype = r.read(build / 'prototype-report.json')
    firmware_sha = r.sha((build / 'firmware.bin').read_bytes())
    r.require(manifest['firmware_sha256'] == info['firmware_sha256'] == firmware_sha
              and manifest['bench_core'] and not manifest['installation_permitted']
              and manifest['generation'] == prototype['experimental_generation'] == 0x80000006
              and manifest['banner'] == prototype['banner'] == '2.0proto b06'
              and prototype['bootstrap_contract'] == manifest['bootstrap_contract'] == 'PR04'
              and prototype['startup_drain'] and prototype['boot_countdown'], 'Wrong new startup target')
    sequence = prototype['startup_sequence']
    r.require(sequence['USB_wait_seconds'] == 3 and sequence['input_drain_seconds'] == 1
              and sequence['countdown_seconds'] == 3 and sequence['drain_message'] == 'Consuming input'
              and sequence['initial_input_consumption'] is False, 'Owner requested startup sequence differs')
    receipts = {'prototype-report.json': r.sha((build / 'prototype-report.json').read_bytes())}
    for name, count in (('cpu-tests.json', 352), ('journal-admission-cpu-tests.json', 58),
                        ('boot-startup-cpu-tests.json', 62), ('ram-tools-runtime-regression.json', 150),
                        ('native-host-cpu-tests.json', 4)):
        report, receipts[name] = exact_report(build, name, minimum=count)
        r.require(report['component_hashes'], 'Complete component bindings required: ' + name)
        if name == 'native-host-cpu-tests.json':
            source = Path(info['source_build'])
            r.require(report['adapter_sha256'] == r.sha(Path(adapter_file).read_bytes())
                      and report['checker_sha256'] == r.sha((HERE / 'test_board_native_2512.py').read_bytes())
                      and report['source_symbols_sha256'] == r.sha((source / 'symbols.json').read_bytes())
                      and report['source_prototype_report_sha256'] == r.sha((source / 'prototype-report.json').read_bytes())
                      and all(row['stale_MON_preimage_refused_before_write']
                              and row['whole_application_RAM_preserved'] for row in report['cases'])
                      and all(row['new_target_J3_CRLF_safe_drain_BOTH_cleanup']
                              for row in report['cases'] if row['case'].startswith('target-b06'))
                      and len(report['reset_watcher_cases']) == 2
                      and report['checks'] == 6 and len(report['cases']) == 4
                      and all(row['passed'] and row['no_TX_before_exact_boot'] for row in report['reset_watcher_cases']),
                      'Exact source/target shim host proof changed')
        if name == 'ram-tools-runtime-regression.json':
            r.require(report.get('status') == 'passed' and report.get('failures') == 0
                      and all(r.sha((HERE / member).read_bytes()) == digest
                              for member, digest in report['checker_hashes'].items()),
                      'New runtime protocol/checker proof changed')
    matrix = r.read(build / 'bench-target-tests.json')
    r.require(matrix['passed'] and matrix['hardware'] is False and matrix['firmware_sha256'] == firmware_sha
              and len(matrix['cases']) == 4
              and {(row['CPU'], row['slot']) for row in matrix['cases']}
              == {(cpu, slot) for cpu in ('65c02', '65c816-e') for slot in ('A', 'B')}
              and all(row['passed'] and row['legacy_auxiliary_instruction_fetches'] == 0
                      and row['default_BRK_pointer'] for row in matrix['cases']), 'Legacy auxiliary gate proof differs')
    receipts['bench-target-tests.json'] = r.sha((build / 'bench-target-tests.json').read_bytes())
    proof = r.read(plan / 'model-proof.json')
    r.require(proof['passed'] and not proof['hardware'] and not proof['serial_access']
              and proof['plan_sha256'] == r.sha((plan / 'plan.json').read_bytes())
              and proof['firmware_sha256'] == firmware_sha
              and proof['planner_sha256'] == r.sha(Path(planning.__file__).read_bytes())
              and proof['model_source_sha256'] == r.sha(Path(model.__file__).read_bytes())
              and proof['native_reserve_source_sha256'] == r.sha((HERE / 'native-reserve.asm').read_bytes())
              and proof['native_extension_receipt_sha256'] == r.sha((plan / 'native-reservation-extension.json').read_bytes()),
              'Native reservation/transaction model binding changed')
    rows = proof['models']
    r.require(len(rows) == 10 and all(row['passed'] and row['linked_FNV_checked'] for row in rows)
              and {(row['CPU'], row.get('fault')) for row in rows}
              == {(cpu, fault) for cpu in ('65C02', '65C816 E=1')
                  for fault in (None, 'stale', 'corrupt', 'reservation-corrupt', 'reservation-commit')},
              'Native success/refusal matrix incomplete')
    successes = [row for row in rows if not row.get('fault')]
    r.require(all(row['erases'] == 3 and row['C_D_erases'] == 0 and row['native_commit255_last']
                  and row['exact_all_four_bank_target'] and row['original_native_records_preserved'] for row in successes),
              'Native preservation model insufficient')
    return dict(board=capture.BOARD, usb_serial=capture.USB, firmware_sha256=firmware_sha,
                manifest_sha256=r.sha((build / 'bench-target.json').read_bytes()),
                plan_sha256=r.sha((plan / 'plan.json').read_bytes()),
                model_proof_sha256=r.sha((plan / 'model-proof.json').read_bytes()),
                adapter_sha256=r.sha(Path(adapter_file).read_bytes()),
                admission_checker_sha256=r.sha(Path(__file__).read_bytes()),
                capture_validator_sha256=r.sha(Path(capture.__file__).read_bytes()),
                native_reserve_source_sha256=r.sha((HERE / 'native-reserve.asm').read_bytes()),
                capture_manifest_sha256=info['capture_manifest_sha256'],
                application_ram_sha256=info['application_ram_sha256'],
                receipts=receipts, source_sha256=r.hashes(banks), expected_sha256=info['expected_sha256'])
