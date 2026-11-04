"""Preimage-bound b11 -> b12 deployment admission with no recovery D/V use."""
from pathlib import Path
import b11_admission as frozen

source=frozen.source
start=source.index('    qualification =')
stop=source.index('    host =',start)
source=source[:start]+'''    qualification=r.read(build/'b12-qualification.json')
    r.require(qualification['passed'] and qualification['failures']==0 and not qualification['hardware']
              and not qualification['flashed'] and qualification['identity']=='2.0proto b12'
              and qualification['generation_hex']=='8000000C' and qualification['total_test_groups']==500
              and qualification['checker_sha256']==r.sha((HERE/'qualify_b12.py').read_bytes()), 'b12 firmware proof differs')
    receipts={}
    for row in qualification['receipt_bindings']:
        r.require(Path(row['file']).name==row['file'], 'Unsafe receipt path')
        digest=r.sha((build/row['file']).read_bytes())
        r.require(digest==row['sha256'],'Changed b12 qualified member: '+row['file']);receipts[row['file']]=digest
    r.require(set(receipts)=={'cpu-tests.json','b12-selection-tests.json','b12-wait-tests.json','b12-command-tests.json',
        'b12-usb-wait-65c02.json','b12-usb-wait-65c816-e.json','bench-target-tests.json','prototype-report.json',
        'bench-target.json','symbols.json','firmware.bin'}, 'Incomplete b12 firmware receipts')
    for name,digest in qualification['source_bindings'].items():
        r.require(Path(name).name==name and r.sha((HERE/name).read_bytes())==digest,'b12 checker/builder changed')
    for name,count in [('cpu-tests.json',352),('b12-selection-tests.json',426),('b12-wait-tests.json',32),('b12-command-tests.json',36)]:
        row=r.read(build/name)
        r.require(row['passed'] and row['checks']==count and not row['failures'],'Failed/incomplete '+name)
    selection=r.read(build/'b12-selection-tests.json')
    r.require(len(selection['cases'])==74 and all(row['passed'] for row in selection['cases'])
              and {row['cpu'] for row in selection['cases']}=={'65c02','65c816-e'},'Selection coverage changed')
    core=r.read(build/'cpu-tests.json')
    for name,digest in core['component_hashes'].items():
        r.require(r.sha((build/'payload'/name).read_bytes())==digest,'Changed CPU-tested component')
    for cpu in ('65c02','65c816-e'):
        row=r.read(build/f'b12-usb-wait-{cpu}.json')
        r.require(row['passed'] and row['cycles']==15998781 and not row['hardware']
                  and row['F_sha256']==r.sha((build/'payload/f-offline-component.bin').read_bytes()),'USB timing differs')
    r.require(prototype['f']['bytes']==3969 and prototype['f']['free']==95
              and prototype['b12_recovery_patch']['removed_commands']==['D','V']
              and prototype['b12_recovery_patch']['recovery_RAM_may_be_overwritten'], 'Wrong b12 recovery profile')
    old_sy,sy=r.read(source/'symbols.json'),r.read(build/'symbols.json')
    old_F=(source/'payload/f-offline-component.bin').read_bytes();new_F=(build/'payload/f-offline-component.bin').read_bytes()
    for label in ('BOOT_READ_RECORD','BOOT_CHECK_FIELDS','BOOT_PRINT','BOOT_API_LINE','BOOT_API_CFG','J_CRC_INIT','J_CRC_BYTE','RL_LOAD','RL_GET','RL_ADVANCE','BOOT_STARTUP'):
        r.require(old_sy['core/str8n-v2-boot'][label]==sy['core/str8n-v2-boot'][label],'Shared F entry moved')
    r.require(not any(label in sy['core/str8n-v2-boot'] for label in ('RL_DUMP','RL_VERIFY','RL_OUTPUT','DC_BINARY_TX_BAD')),'Removed handler remains')
    for name in ('ram-config-offline.bin','ram-installer-offline.bin','ram-installer-offline.rlp1'):
        r.require((source/'payload'/name).read_bytes()==(build/'payload'/name).read_bytes(),'Standalone RAM tool changed')
    for label,size in [('BOOT_WORKER_IMAGE',1000),('BOOT_VECTOR_IMAGE',196)]:
        offset=sy['core/str8n-v2-boot'][label]-0xf000
        r.require(old_F[offset:offset+size]==new_F[offset:offset+size],'Copied ABI runtime differs')
    r.require(old_F[0xfe0:]==new_F[0xfe0:],'Hardware vectors differ')
    for name in ('monitor-a0-offline-component.bin','monitor-b0-offline-component.bin'):
        a=(source/'payload'/name).read_bytes();b=(build/'payload'/name).read_bytes()
        r.require([n for n in range(4096) if a[n]!=b[n]]==[8,18,19,2511]
                  and a[2510:2512]==b'11' and b[2510:2512]==b'12','MON changed beyond identity/CRC')
    probe=r.read(build/'b12-probe-host-tests.json')
    r.require(probe['passed'] and not probe['hardware'] and not probe['serial_access'] and probe['checks']==19
              and all(row['passed'] for row in probe['cases']) and probe['adapter_sha256']==r.sha(Path(adapter_file).read_bytes())
              and probe['checker_sha256']==r.sha((HERE/'test_b12_probe.py').read_bytes()),'b12 no-D/V host probes changed')
    live_cpu=r.read(build/'b12-deployment-cpu-tests.json')
    r.require(live_cpu['passed'] and not live_cpu['hardware'] and not live_cpu['serial_access']
              and live_cpu['checks']==2 and {row['cpu'] for row in live_cpu['cases']}=={'65c02','65c816-e'}
              and all(row['passed'] and row['F_load_run_with_MON_absent'] and row['MON_independent_RAM_readback_verified']
                      and row['flash_mutations']==0 for row in live_cpu['cases'])
              and live_cpu['adapter_sha256']==r.sha(Path(adapter_file).read_bytes())
              and live_cpu['checker_sha256']==r.sha((HERE/'test_b12_deployment_cpu.py').read_bytes())
              and live_cpu['F_sha256']==r.sha(new_F)
              and live_cpu['RAM_tool_sha256']==r.sha((build/'payload/ram-installer-offline.bin').read_bytes()), 'No-V CPU verification path changed')
'''+source[stop:]
# Preserve the b11 inherited proof and all native host/transaction safeguards.
# Target names advance first, then installed-source references advance to b11.
source=source.replace('b11','b12').replace('b10','b11')
source=source.replace('BUILD/pr04-b11-wait','BUILD/pr04-b11-help-r7')
source=source.replace('0x8000000B','0x8000000C')
source=source.replace('unchanged_b07_preservation_and_binary_code_verified=True','preservation_services_and_no_D_V_CPU_path_verified=True')
source=source.replace('Exact installed b07 required','Exact installed b11 required').replace('qualified installed b07','qualified installed b11').replace('Wrong b09 target','Wrong b12 target')
source=source.replace("'build_b12.py','test_b12_wait.py')","'build_b12.py','test_b12_wait.py','test_b12_probe.py','test_b12_deployment_cpu.py')")
source=source.replace("        exact_host_proof_sha256=", "        probe_host_proof_sha256=r.sha((build/'b12-probe-host-tests.json').read_bytes()),\n        deployment_CPU_proof_sha256=r.sha((build/'b12-deployment-cpu-tests.json').read_bytes()),\n        exact_host_proof_sha256=")
exec(compile(source,str(Path(frozen.__file__)),'exec'),globals())
