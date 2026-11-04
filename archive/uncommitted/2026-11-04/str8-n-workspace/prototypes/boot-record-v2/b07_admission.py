"""Exact offline proof bindings for the separate native 2512 deployment."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'tools')]
from installer.engine import runtime as r
import deployment_b07 as planning
import deployment_b07_model as model
import capture_b07_2512 as capture


def exact_report(build, name, *, minimum=1, checker=None):
    path = build / name; report = r.read(path)
    r.require(report.get('passed', report.get('pass')) is True and report.get('hardware') is False
              and report.get('serial_access', False) is False, 'Failed or non-offline receipt: ' + name)
    cases = report.get('cases', [])
    r.require(len(cases) >= minimum and all(row.get('passed') is True for row in cases)
              and report.get('checks') == len(cases) + len(report.get('reset_watcher_cases', []))
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


def source_dependencies(report, build):
    for member, digest in report.get('dependency_hashes', {}).items():
        path = HERE.parents[1] / member if '/' in member or '\\' in member else HERE / member
        if member == 'prototype-engine.inc':
            path = build / 's/core/prototype-engine.inc'
        r.require(r.sha(path.read_bytes()) == digest, 'Receipt dependency changed: ' + member)


def core_adaptation_hashes():
    """Reproduce test_b07's text hashes without importing/executing a model."""
    raw = (HERE / 'test.py').read_bytes()
    r.require(r.sha(raw) == 'e534a0374b59506f7a7e32e8f1829621bacde8c3434f8f61c06b34c6b101e410',
              'Frozen b06 core checker changed')
    source = raw.decode()
    old_full = "b'OFFLINE PROTOTYPE S A B 0 1 2 3\\r\\n'"
    r.require(source.count(old_full) == 2, 'Core full chooser assertion count changed')
    source = source.replace(old_full, repr(b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'))
    old_partial = "b'OFFLINE PROTOTYPE'"
    r.require(source.count(old_partial) == 1, 'Core partial chooser assertion count changed')
    source = source.replace(old_partial, "b'S=Recovery  A/B=Monitor  0-3=Bank'")
    return dict(base_checker_sha256=r.sha(raw), adapted_source_sha256=r.sha(source.encode()),
                full_chooser_marker_substitutions=2, partial_chooser_marker_substitutions=1,
                model_or_test_logic_changed=False)


def bindings(build, plan, *, adapter_file):
    build, plan = Path(build), Path(plan)
    info = planning.verify(build, plan)
    identity, banks = capture.validate(plan / 'capture')
    validator_sha = r.sha(Path(capture.native_capture.__file__).read_bytes())
    r.require(validator_sha == '05411a2a31e66f6ff52f8a6d663658ea96ef9b54525614de0dd3a11acb409e19',
              'Frozen native capture validator changed')
    r.require(info['synthetic_model_fixture'] is False, 'Synthetic native plan cannot be physically admitted')
    manifest = r.read(build / 'bench-target.json'); prototype = r.read(build / 'prototype-report.json')
    firmware_sha = r.sha((build / 'firmware.bin').read_bytes())
    r.require(manifest['firmware_sha256'] == info['firmware_sha256'] == firmware_sha
              and manifest['bench_core'] and not manifest['installation_permitted']
              and manifest['generation'] == prototype['experimental_generation'] == 0x80000007
              and manifest['banner'] == prototype['banner'] == '2.0proto b07'
              and prototype['bootstrap_contract'] == manifest['bootstrap_contract'] == 'PR04'
              and prototype['startup_drain'] and prototype['boot_countdown'], 'Wrong new startup target')
    sequence = prototype['startup_sequence']
    r.require(sequence['USB_wait_seconds'] == 3 and sequence['input_drain_seconds'] == 1
              and sequence['countdown_seconds'] == 3 and sequence['drain_message'] == 'WAIT...'
              and sequence['drain_message_bytes_hex'] == '0d0a574149542e2e2e0d0a'
              and sequence['choice_labels'] == 'S=Recovery  A/B=Monitor  0-3=Bank'
              and sequence['countdown_prefix'] == 'Boot : '
              and sequence['initial_input_consumption'] is False, 'Owner requested startup sequence differs')
    receipts = {'prototype-report.json': r.sha((build / 'prototype-report.json').read_bytes())}
    for name, count in (('cpu-tests.json', 352), ('journal-admission-cpu-tests.json', 58),
                        ('boot-startup-cpu-tests.json', 62), ('ram-tools-runtime-regression.json', 150),
                        ('native-host-cpu-tests.json', 4)):
        report, receipts[name] = exact_report(build, name, minimum=count)
        wanted = {p.name for p in (build / 'payload').iterdir()
                  if '-offline' in p.name and p.suffix == '.bin'}
        if name not in ('cpu-tests.json', 'journal-admission-cpu-tests.json'):
            wanted.add('ram-installer-offline.rlp1')
        r.require(set(report['component_hashes']) == wanted, 'Complete component bindings required: ' + name)
        if name == 'cpu-tests.json':
            adaptation = core_adaptation_hashes()
            r.require(report['checker_sha256'] == r.sha((HERE / 'test_b07.py').read_bytes())
                      and report['frozen_b06_checker_adaptation'] == adaptation
                      and report['b06_checker_source_unchanged'] is True,
                      'Core checker adaptation binding changed')
        if name == 'journal-admission-cpu-tests.json':
            r.require(report['test_source_sha256'] == r.sha((HERE / 'test_journal_admission.py').read_bytes()),
                      'Journal checker changed')
            source_dependencies(report, build)
        if name == 'native-host-cpu-tests.json':
            source = Path(info['source_build'])
            r.require(report['adapter_sha256'] == r.sha(Path(adapter_file).read_bytes())
                      and report['checker_sha256'] == r.sha((HERE / 'test_board_b07_2512.py').read_bytes())
                      and report['source_symbols_sha256'] == r.sha((source / 'symbols.json').read_bytes())
                      and report['source_prototype_report_sha256'] == r.sha((source / 'prototype-report.json').read_bytes())
                      and report['source_bank_sha256'] == info['source_sha256']
                      and report['expected_bank_sha256'] == info['expected_sha256']
                      and report['application_ram_sha256'] == info['application_ram_sha256']
                      and {(row['cpu'], row['case'].split('-exact-runtime-')[0]) for row in report['cases']}
                          == {(cpu, label) for cpu in ('65c02', '65c816-e') for label in ('source-b06', 'target-b07')}
                      and all(row['stale_MON_preimage_refused_before_write']
                              and row['whole_application_RAM_preserved'] for row in report['cases'])
                      and all(row['new_target_J3_CRLF_safe_drain_BOTH_cleanup']
                              for row in report['cases'] if row['case'].startswith('target-b07'))
                      and len(report['reset_watcher_cases']) == 2
                      and report['checks'] == 6 and len(report['cases']) == 4
                      and all(row['passed'] and row['no_TX_before_exact_boot'] for row in report['reset_watcher_cases']),
                      'Exact source/target shim host proof changed')
        if name == 'ram-tools-runtime-regression.json':
            r.require(report.get('status') == 'passed' and report.get('failures') == 0
                      and report['evidence_script_sha256'] == r.sha((HERE.parents[1] / 'tmp/test_pr04_b07_ram_tools.py').read_bytes())
                      and all(r.sha((HERE / member).read_bytes()) == digest
                              for member, digest in report['checker_hashes'].items()),
                      'New runtime protocol/checker proof changed')
    # The original instruction/timing matrix has 62 cases. New b07 exact
    # mirrored display and timed wire cases add four and two, respectively.
    for name, count in (('boot-startup-cpu-tests.json', 62),
                        ('boot-startup-output-bound.json', 4), ('boot-startup-timed-wire.json', 2),
                        ('boot-startup-b07-qualification.json', 68)):
        report, receipts[name] = exact_report(build, name, minimum=count, checker='test_boot_startup_b07.py')
        r.require(report['frozen_base_checker_sha256'] == r.sha((HERE / 'test_boot_startup.py').read_bytes())
                  and report['assertion_constant_replacements'] == 3
                  and report['exact_text'] == dict(wait=list(b'\r\nWAIT...\r\n'),
                      choices=list(b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'), prefix=list(b'Boot : ')),
                  'Startup frozen checker adaptation changed')
        source_dependencies(report, build)
        if name == 'boot-startup-b07-qualification.json':
            source = Path(info['source_build'])
            previous, current = r.read(source / 'symbols.json'), r.read(build / 'symbols.json')
            stable_counts = {}
            for module, symbols in previous.items():
                stable = {key: value for key, value in symbols.items() if key not in ('BOOT_END', '_END_CODE')}
                r.require(all(current[module].get(key) == value for key, value in stable.items()),
                          'Existing PR04 private entry moved: ' + module)
                stable_counts[module] = len(stable)
            r.require(report['b06_private_addresses_preserved'] == stable_counts
                      and report['b06_symbols_sha256'] == r.sha((source / 'symbols.json').read_bytes()),
                      'PR04 compatibility proof changed')
            for shard in report['source_shards']:
                r.require(shard['sha256'] == r.sha((build / Path(shard['path']).name).read_bytes()),
                          'Startup CPU shard changed')
            for member in ('boot-startup-cpu-tests.json', 'boot-startup-output-bound.json', 'boot-startup-timed-wire.json'):
                r.require(report['receipts'][member] == receipts[member], 'Startup combined receipt changed')
    source_capture = r.read(build / 'source-capture-host-tests.json')
    r.require(source_capture['passed'] and source_capture['hardware'] is False
              and source_capture['serial_access'] is False and len(source_capture['cases']) == 2
              and all(row['passed'] and row['repeated_RAM_escrow_before_shim'] for row in source_capture['cases'])
              and source_capture['helper_sha256'] == r.sha(Path(capture.__file__).read_bytes())
              and source_capture['checker_sha256'] == r.sha((HERE / 'test_capture_b07_2512.py').read_bytes()),
              'Repeated source RAM escrow ordering proof changed')
    receipts['source-capture-host-tests.json'] = r.sha((build / 'source-capture-host-tests.json').read_bytes())
    matrix = r.read(build / 'bench-target-tests.json')
    r.require(matrix['passed'] and matrix['hardware'] is False and matrix['firmware_sha256'] == firmware_sha
              and matrix['checker_sha256'] == r.sha((HERE / 'bench_target.py').read_bytes())
              and matrix['evidence_script_sha256'] == r.sha((HERE.parents[1] / 'tmp/test_pr04_b07_bench.py').read_bytes())
              and matrix['frozen_core_checker_sha256'] == r.sha((HERE / 'test.py').read_bytes())
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
                native_capture_validator_sha256=validator_sha,
                native_reserve_source_sha256=r.sha((HERE / 'native-reserve.asm').read_bytes()),
                capture_manifest_sha256=info['capture_manifest_sha256'],
                application_ram_sha256=info['application_ram_sha256'],
                receipts=receipts, source_sha256=r.hashes(banks), expected_sha256=info['expected_sha256'])
