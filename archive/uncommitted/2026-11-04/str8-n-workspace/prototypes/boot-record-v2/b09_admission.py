"""Exact b09 receipts plus unchanged, previously qualified b07 preservation code."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT/'tools')]
from installer.engine import runtime as r
import b07_admission as prior
import deployment_b09 as planning
import deployment_b09_model as model


def bindings(build, plan, *, adapter_file):
    build, plan = Path(build), Path(plan)
    info = planning.verify(build, plan)
    identity, banks = planning.capture.validate(plan/'capture')
    r.require(not info['synthetic_model_fixture'] and identity['hardware_capture'],
              'A physical repeated 2512 capture is required')
    source = Path(info['source_build'])
    r.require(source.resolve() == (ROOT/'BUILD/pr04-b07-startup').resolve(), 'Exact installed b07 required')
    inherited = prior.bindings(source, ROOT/'tmp/pr04-b07-2512-native-plan',
                              adapter_file=HERE/'board_b07_2512.py')
    r.require(info['source_sha256'] == inherited['expected_sha256'], 'Capture differs from qualified installed b07')
    firmware_sha = r.sha((build/'firmware.bin').read_bytes())
    manifest = r.read(build/'bench-target.json'); prototype = r.read(build/'prototype-report.json')
    r.require(manifest['firmware_sha256'] == info['firmware_sha256'] == firmware_sha
              and manifest['banner'] == prototype['banner'] == '2.0proto b09'
              and manifest['generation'] == prototype['experimental_generation'] == 0x80000009
              and prototype['bootstrap_contract'] == manifest['bootstrap_contract'] == 'PR04'
              and manifest['bench_core'] and not manifest['installation_permitted'], 'Wrong b09 target')
    sequence = prototype['startup_sequence']
    r.require(sequence['USB_wait_seconds'] == 2 and sequence['input_drain_seconds'] == 1
              and sequence['countdown_seconds'] == 6 and sequence['drain_message'] == 'WAIT...'
              and sequence['choice_labels'] == 'S=Recovery  A/B=Monitor  0-3=Bank'
              and sequence['countdown_prefix'] == 'Boot : ', 'Wrong owner startup sequence')
    qualification = r.read(build/'b09-qualification.json')
    r.require(qualification['passed'] and not qualification['hardware'] and not qualification['flashed']
              and qualification['regression_and_selection_groups'] == 426
              and qualification['failures'] == 0, 'Failed b09 offline qualification')
    receipts = {}
    for row in qualification['receipt_bindings']:
        r.require(Path(row['file']).name == row['file'], 'Receipt path is not a direct member')
        digest = r.sha((build/row['file']).read_bytes())
        r.require(row['sha256'] == digest, 'Changed qualified member: '+row['file'])
        receipts[row['file']] = digest
    required = {'b09-selection-tests.json','cpu-tests.json','b09-usb-wait-65c02.json',
                'b09-usb-wait-65c816-e.json','bench-target-tests.json','bench-target.json',
                'prototype-report.json','firmware.bin'}
    r.require(set(receipts) == required, 'Incomplete b09 qualification binding')
    core = r.read(build/'cpu-tests.json')
    r.require(core['passed'] and core['checks'] == 352 and core['failures'] == 0
              and {row['cpu'] for row in core['cases']} == {'65c02','65c816-e'}, 'Core matrix incomplete')
    for name, digest in core['component_hashes'].items():
        r.require(digest == r.sha((build/'payload'/name).read_bytes()), 'Core component changed')
    selection = r.read(build/'b09-selection-tests.json')
    r.require(selection['passed'] and selection['checks'] == 426 and selection['failures'] == 0
              and len(selection['cases']) == 74 and all(row['passed'] for row in selection['cases'])
              and {row['cpu'] for row in selection['cases']} == {'65c02','65c816-e'}
              and selection['baseline_report_sha256'] == receipts['cpu-tests.json']
              and selection['prototype_report_sha256'] == receipts['prototype-report.json']
              and selection['checker_sha256'] == r.sha((HERE/'test_b09.py').read_bytes()), 'Selection proof changed')
    for cpu in ('65c02','65c816-e'):
        wait = r.read(build/f'b09-usb-wait-{cpu}.json')
        r.require(wait['passed'] and wait['cpu'] == cpu and wait['cycles'] == 15998781
                  and wait['no_output_or_input_access'] and not wait['hardware']
                  and wait['F_sha256'] == r.sha((build/'payload/f-offline-component.bin').read_bytes())
                  and wait['checker_sha256'] == r.sha((HERE/'test_b09_usb_wait.py').read_bytes()), 'USB timing binding changed')
    b08 = ROOT/'BUILD/pr04-b08-six-second'
    old_F = (b08/'payload/f-offline-component.bin').read_bytes()
    new_F = (build/'payload/f-offline-component.bin').read_bytes()
    r.require([n for n,(a,b) in enumerate(zip(old_F,new_F)) if a != b] == [0xf1a]
              and old_F[0xf1a] == 30 and new_F[0xf1a] == 20, 'Unexpected F change from timed b08')
    for row in qualification['inherited_countdown_timing']:
        path = ROOT/row['file']; timing = r.read(path)
        r.require(row['sha256'] == r.sha(path.read_bytes()) and timing['passed']
                  and timing['F_sha256'] == r.sha(old_F)
                  and timing['countdown_seconds'] == 6, 'Inherited six-second timing changed')
    old_sy, sy = r.read(source/'symbols.json'), r.read(build/'symbols.json')
    for module, symbols in old_sy.items():
        r.require(all(sy[module].get(label) == address for label,address in symbols.items()
                      if label not in ('BOOT_END','_END_CODE')), 'Existing private entry moved')
    old_F = (source/'payload/f-offline-component.bin').read_bytes()
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        r.require((source/'payload'/name).read_bytes() == (build/'payload'/name).read_bytes(), 'RAM tool changed')
    boot = sy['core/str8n-v2-boot']
    for label,size in (('BOOT_WORKER_IMAGE',prototype['f']['worker_bytes']),
                       ('BOOT_VECTOR_IMAGE',prototype['f']['vectors_bytes'])):
        start = boot[label]-0xf000
        r.require(old_F[start:start+size] == new_F[start:start+size], 'Copied ABI runtime changed')
    r.require(old_F[0x33e:0x540] == new_F[0x33e:0x540], 'Binary handlers changed')
    r.require(old_F[0xf1b:0xf81] == new_F[0xf1b:0xf81], 'Drain code changed')
    for name in ('monitor-a0-offline-component.bin','monitor-b0-offline-component.bin'):
        before, after = (source/'payload'/name).read_bytes(), (build/'payload'/name).read_bytes()
        r.require([n for n,(a,b) in enumerate(zip(before,after)) if a != b] == [8,18,19,2511]
                  and before[2511] == ord('7') and after[2511] == ord('9'), 'MON changed beyond identity/header CRC')
    host = r.read(build/'native-host-cpu-tests.json')
    r.require(host['passed'] and not host['hardware'] and not host['serial_access']
              and host['checks'] == 6 and len(host['cases']) == 4 and len(host['reset_watcher_cases']) == 2
              and {(row['cpu'],row['case'].split('-exact-runtime-')[0]) for row in host['cases']}
                  == {(cpu,label) for cpu in ('65c02','65c816-e') for label in ('source-b07','target-b09')}
              and all(row['passed'] and row['stale_MON_preimage_refused_before_write']
                      and row['whole_application_RAM_preserved'] for row in host['cases'])
              and all(row['new_target_J3_CRLF_safe_drain_BOTH_cleanup'] for row in host['cases']
                      if row['case'].startswith('target-b09'))
              and all(row['passed'] and row['no_TX_before_exact_boot'] for row in host['reset_watcher_cases'])
              and host['source_bank_sha256'] == info['source_sha256']
              and host['expected_bank_sha256'] == info['expected_sha256']
              and host['adapter_sha256'] == r.sha(Path(adapter_file).read_bytes())
              and host['checker_sha256'] == r.sha((HERE/'test_board_b09_2512.py').read_bytes())
              and host['source_symbols_sha256'] == r.sha((source/'symbols.json').read_bytes())
              and host['source_prototype_report_sha256'] == r.sha((source/'prototype-report.json').read_bytes())
              and host['symbols_sha256'] == r.sha((build/'symbols.json').read_bytes())
              and host['prototype_report_sha256'] == r.sha((build/'prototype-report.json').read_bytes())
              and host['application_ram_sha256'] == info['application_ram_sha256'], 'Exact source/target host proof changed')
    for name,digest in host['component_hashes'].items():
        r.require(r.sha((build/'payload'/name).read_bytes()) == digest, 'Host component changed')
    model_proof = r.read(plan/'model-proof.json')
    r.require(model_proof['passed'] and not model_proof['hardware'] and not model_proof['serial_access']
              and model_proof['plan_sha256'] == r.sha((plan/'plan.json').read_bytes())
              and model_proof['firmware_sha256'] == firmware_sha
              and model_proof['planner_sha256'] == r.sha(Path(planning.__file__).read_bytes())
              and model_proof['model_source_sha256'] == r.sha(Path(model.__file__).read_bytes())
              and model_proof['native_reserve_source_sha256'] == r.sha((HERE/'native-reserve.asm').read_bytes())
              and model_proof['native_extension_receipt_sha256'] == r.sha((plan/'native-reservation-extension.json').read_bytes()),
              'Native transaction model binding changed')
    rows = model_proof['models']
    r.require(len(rows) == 10 and all(row['passed'] and row['linked_FNV_checked'] for row in rows)
              and {(row['CPU'],row.get('fault')) for row in rows}
                  == {(cpu,fault) for cpu in ('65C02','65C816 E=1')
                      for fault in (None,'stale','corrupt','reservation-corrupt','reservation-commit')}, 'Native fault matrix incomplete')
    r.require(all(row['erases'] == 3 and row['C_D_erases'] == 0 and row['native_commit255_last']
                  and row['exact_all_four_bank_target'] and row['original_native_records_preserved']
                  for row in rows if not row.get('fault')), 'Native preservation failed')
    dependencies = ('deployment_b07.py','deployment_b07_model.py','board_b07_2512.py',
                    'test_board_b07_2512.py','build_b08.py','build_b09.py','test_b08.py','test_b09.py',
                    'deployment_b09.py','deployment_b09_model.py','b09_admission.py')
    return dict(board='2512', usb_serial='A10MQFLCA', firmware_sha256=firmware_sha,
        manifest_sha256=r.sha((build/'bench-target.json').read_bytes()),
        plan_sha256=r.sha((plan/'plan.json').read_bytes()),
        model_proof_sha256=r.sha((plan/'model-proof.json').read_bytes()),
        adapter_sha256=r.sha(Path(adapter_file).read_bytes()),
        admission_checker_sha256=r.sha(Path(__file__).read_bytes()),
        source_sha256=info['source_sha256'], expected_sha256=info['expected_sha256'],
        application_ram_sha256=info['application_ram_sha256'],
        inherited_b07_qualification=inherited,
        unchanged_b07_preservation_and_binary_code_verified=True,
        receipt_hashes=receipts, dependency_hashes={name:r.sha((HERE/name).read_bytes()) for name in dependencies},
        exact_host_proof_sha256=r.sha((build/'native-host-cpu-tests.json').read_bytes()))
