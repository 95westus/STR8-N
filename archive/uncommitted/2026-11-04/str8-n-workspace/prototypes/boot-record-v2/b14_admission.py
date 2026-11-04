"""Exact b14 firmware, source, native transaction and host proof admission."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'tools')]
from installer.engine import runtime as r
import deployment_b14 as planning
import deployment_b14_model as model
import capture_b07_2512 as capture

def bindings(build,plan,*,adapter_file):
    build,plan=Path(build).resolve(),Path(plan).resolve()
    info=planning.verify(build,plan)
    r.require(not info['synthetic_model_fixture'],'Physical backup required')
    r.require(Path(info['source_build']).resolve()==ROOT/'BUILD/pr04-b12-no-readback-r4','Exact b12 source build required')
    _,banks=capture.validate(plan/'capture')
    # Retain the prior installed build's full admission chain unchanged.
    import board_b12_2512 as old_board
    inherited=old_board.bindings(ROOT/'BUILD/pr04-b12-no-readback-r4',ROOT/'tmp/pr04-b12-2512-native-plan')
    r.require(r.hashes(banks)==inherited['expected_sha256'],'Fresh backup differs from admitted installed b12')
    manifest=r.read(build/'bench-target.json');prototype=r.read(build/'prototype-report.json')
    r.require(manifest['banner']==prototype['banner']=='2.0proto b14' and
        manifest['generation']==prototype['experimental_generation']==0x8000000e and
        manifest['bootstrap_contract']==prototype['bootstrap_contract']=='PR04' and
        manifest['bench_core'] and not manifest['installation_permitted'] and
        manifest['firmware_sha256']==info['firmware_sha256']==r.sha((build/'firmware.bin').read_bytes()),'Wrong target')
    q=r.read(build/'b14-qualification.json')
    r.require(q['passed'] and q['failures']==0 and not q['hardware'] and not q['flashed'] and
        q['identity']=='2.0proto b14' and q['generation_hex']=='8000000E' and q['total_test_groups']==618 and
        q['checker_sha256']==r.sha((HERE/'qualify_b14.py').read_bytes()),'b14 firmware qualification changed')
    for row in q['receipt_bindings']:
        r.require(Path(row['file']).name==row['file'] and r.sha((build/row['file']).read_bytes())==row['sha256'],'Changed qualified receipt: '+row['file'])
    for name,digest in q['source_bindings'].items():
        r.require(Path(name).name==name and r.sha((HERE/name).read_bytes())==digest,'Qualified source changed: '+name)
    raw=prototype['raw_loader']
    r.require(raw['load_start']==raw['entry']==0x200 and raw['end_exclusive']==0x6500 and
        raw['idle_seconds']==3 and raw['header_bytes']==0 and not raw['CRC'] and not raw['length_field'] and not raw['run_command'], 'Wrong raw receiver')
    proof=r.read(plan/'model-proof.json');models=proof['models']
    r.require(proof['passed'] and not proof['hardware'] and not proof['serial_access'] and
        proof['plan_sha256']==r.sha((plan/'plan.json').read_bytes()) and
        proof['firmware_sha256']==info['firmware_sha256'] and
        proof['planner_sha256']==r.sha(Path(planning.__file__).read_bytes()) and
        proof['model_source_sha256']==r.sha(Path(model.__file__).read_bytes()) and
        proof['native_reserve_source_sha256']==r.sha((HERE/'native-reserve.asm').read_bytes()) and
        proof['native_extension_receipt_sha256']==r.sha((plan/'native-reservation-extension.json').read_bytes()),'Native model binding changed')
    r.require(len(models)==10 and all(row['passed'] and row['linked_FNV_checked'] for row in models) and
        {(row['CPU'],row.get('fault')) for row in models}=={(cpu,fault) for cpu in ['65C02','65C816 E=1'] for fault in [None,'stale','corrupt','reservation-corrupt','reservation-commit']},'Native fault matrix incomplete')
    r.require(all(row['erases']==3 and row['C_D_erases']==0 and row['native_commit255_last'] and row['exact_all_four_bank_target'] and row['original_native_records_preserved'] for row in models if not row.get('fault')),'Native preservation failed')
    host=r.read(build/'b14-native-host-cpu-tests.json')
    r.require(host['passed'] and not host['hardware'] and not host['serial_access'] and host['checks']==6 and
        host['adapter_sha256']==r.sha(Path(adapter_file).read_bytes()) and host['checker_sha256']==r.sha((HERE/'test_board_b14_2512.py').read_bytes()) and
        host['source_bank_sha256']==info['source_sha256'] and host['expected_bank_sha256']==info['expected_sha256'] and
        all(row['passed'] and row['stale_MON_preimage_refused_before_write'] and row['whole_application_RAM_preserved'] for row in host['cases']) and
        len(host['cases'])==4 and len(host['reset_watcher_cases'])==2 and all(row['passed'] and row['no_TX_before_exact_boot'] for row in host['reset_watcher_cases']), 'Host/reset watcher proof differs')
    probe=r.read(build/'b14-probe-host-tests.json')
    r.require(probe['passed'] and not probe['hardware'] and not probe['serial_access'] and probe['checks']>=12 and
        probe['adapter_sha256']==r.sha(Path(adapter_file).read_bytes()) and probe['checker_sha256']==r.sha((HERE/'test_b14_probe.py').read_bytes()) and
        all(row['passed'] for row in probe['cases']),'Raw probe buffered proof changed')
    live=r.read(build/'b14-deployment-cpu-tests.json')
    r.require(live['passed'] and not live['hardware'] and not live['serial_access'] and live['checks']==2 and
        live['adapter_sha256']==r.sha(Path(adapter_file).read_bytes()) and live['checker_sha256']==r.sha((HERE/'test_b14_deployment_cpu.py').read_bytes()) and
        live['F_sha256']==r.sha((build/'payload/f-offline-component.bin').read_bytes()) and
        all(row['passed'] and row['F_load_run_with_MON_absent'] and row['MON_independent_RAM_readback_verified'] and row['flash_mutations']==0 for row in live['cases']),'Raw CPU independent readback changed')
    return dict(board='2512',usb_serial='A10MQFLCA',firmware_sha256=info['firmware_sha256'],
        manifest_sha256=r.sha((build/'bench-target.json').read_bytes()),plan_sha256=r.sha((plan/'plan.json').read_bytes()),
        model_proof_sha256=r.sha((plan/'model-proof.json').read_bytes()),adapter_sha256=r.sha(Path(adapter_file).read_bytes()),
        admission_checker_sha256=r.sha(Path(__file__).read_bytes()),capture_manifest_sha256=info['capture_manifest_sha256'],
        application_ram_sha256=info['application_ram_sha256'],source_sha256=info['source_sha256'],expected_sha256=info['expected_sha256'],
        firmware_qualification_sha256=r.sha((build/'b14-qualification.json').read_bytes()),
        exact_host_proof_sha256=r.sha((build/'b14-native-host-cpu-tests.json').read_bytes()),
        probe_host_proof_sha256=r.sha((build/'b14-probe-host-tests.json').read_bytes()),
        deployment_CPU_proof_sha256=r.sha((build/'b14-deployment-cpu-tests.json').read_bytes()),
        inherited_source_proof=inherited,raw_0200_no_header_no_R=True)
