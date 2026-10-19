"""Bundle the exact tested DBG1 kit, current manuals and public results. No ports."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
Q=ROOT/'output/qualification'
BUILD=ROOT/'BUILD/rc1-debugger-v1e'
KIT=ROOT/'BUILD/rc1-debugger-boardtest-r1'
KIT_SHA='3287d719b703b1ae87300c05ffba9fe803594995e4a9156781c03c86d4fb0e9c'
IMAGE_SHA='e3c7ae6247f23e579a2ffc31ea72986eb62611d22fc862da321371139ae6727a'
READ=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
SHA=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')

def copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)

def safe(root,name):
    path=(root/name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()),'Unsafe path: '+name)
    return path

def public_board(board,path,kit_hash):
    proof=READ(path)
    for key in ('passed','both_monitor_slots_passed','RAM_restored_host_verified','application_RAM_capacity_unchanged',
                'all_four_banks_matched_install_target_before_slot_switches','all_seven_firmware_sectors_reverified_after_tests',
                'B0_B2_and_other_flash_data_unchanged','settings_preserved_except_candidate_generation',
                'exactly_planned_nine_erases_accounted','RTC_controls_trims_oscillator_backup_preserved'):
        require(proof[key] is True,board+': missing '+key)
    require(proof['board']==board and proof['generation']==50 and proof['RAM_bytes']==25344 and proof['breakpoint_hits_total']==32,'Wrong board receipt')
    require(proof['package_manifest_sha256']==kit_hash and not proof['native_debugging'] and not proof['rollback_executed'],'Wrong package/scope')
    slots={}
    for slot in ('A','B'):
        source=proof['slots'][slot];report=Path(source['report']);raw=READ(report)
        require(SHA(report)==source['sha256'] and raw['passed'] and raw['breakpoint_hits_verified']==16 and raw['smoke_program_bytes_restored'],'Changed smoke receipt')
        require(f'Running: MONITOR {slot}, gen 00000032' in raw['version'] and len(raw['smoke_tests_completed'])==4,'Incomplete smoke')
        slots[slot]=dict(passed=True,breakpoint_hits=16,all_eight_hit_twice=True,BRK_C_S_N=True,shared_D_M_U=True,
            ninth_refused=True,clear_individual_and_all=True,X_HOLD_cleanup=True,BRK_80_query=True,
            program_code_restored=True,source_smoke_report_sha256=SHA(report))
    modes=proof.get('emulation_runtime_observations',{})
    if board=='2609':
        require(len(modes)==6,'Missing E=1 observations')
        for mode in modes.values():
            require(mode['emulation_mode_before_probe'] and not mode['probe_enters_native_mode'] and
                    mode['DBR']==mode['PBR']==mode['direct_page']==0 and mode['IRQ_disabled'] and mode['decimal_clear'],'E=1 ABI observation failed')
    return dict(passed=True,board=board,cpu=proof['cpu'],candidate='rc1-debugger-v1',generation=50,
        package_manifest_sha256=kit_hash,source_receipt_sha256=SHA(path),finished_utc=proof['finished_utc'],
        both_monitor_slots_passed=True,slots=slots,breakpoint_hits_total=32,
        fresh_repeated_flash_backup=True,flash_banks=4,bytes_per_flash_bank=32768,RAM_bytes=25344,
        RAM_restored_host_verified=True,application_RAM_capacity_unchanged=True,
        original_preference_restored=proof['original_preference_restored'],settings_preserved_except_candidate_generation=True,
        all_four_banks_matched_install_target_before_slot_switches=True,all_seven_firmware_sectors_reverified_after_tests=True,
        B0_B2_and_other_flash_data_unchanged=True,installation_transfers_device_verified=9,exactly_planned_nine_erases_accounted=True,
        RTC_controls_trims_oscillator_backup_preserved=True,clock_set=False,trim_changed=False,
        E1_runtime_observations=len(modes),rollback_plan_prepared_and_verified_offline=True,rollback_executed=False,
        native_debugging=False,native_applications_tested=False,
        scope='Bounded installation and both-slot debugger smoke; callback registration covered offline; no interrupted-write recovery')

def links_resolve(root):
    checked=0
    for path in root.rglob('*.md'):
        for ref in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if re.match(r'[a-z]+:',ref):continue
            name=ref.split('#')[0]
            target=(path.parent/name).resolve() if name else path
            require(target.is_relative_to(root) and target.is_file(),f'Broken package link: {path.relative_to(root)} -> {ref}')
            checked+=1
    return checked

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();out=args.out.resolve();archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256')
    require(not out.exists() and not archive.exists() and not checksum.exists(),'Use a new distribution path')
    require(SHA(KIT/'board-test-manifest.json')==KIT_SHA and SHA(BUILD/'firmware.bin')==IMAGE_SHA,'Untested input kit/image')
    sys.path.insert(0,str(KIT));import board_plan as plans
    manifest=plans.package(KIT)
    pointer=READ(Q/'rc1-debugger-docs-current.json');audit_path=Path(pointer['report'])
    require(SHA(audit_path)==pointer['sha256'],'Documentation audit changed')
    audit=READ(audit_path);require(audit['passed'] and not audit['board_access'] and audit['frozen_rc1_sources_verified']==97,'Documentation audit incomplete')
    for name,info in audit['documentation'].items():require(SHA(ROOT/name)==info['sha256'],'Changed audited documentation: '+name)
    for name,info in READ(ROOT/'release/candidates/rc1/source-provenance.json').items():
        require(SHA(ROOT/'release/candidates/rc1'/name)==info['sha256'],'Frozen rc1 source changed: '+name)
    boards={}
    for board in ('2604','2609'):
        entry=audit['boards'][board];path=Path(entry['report']);require(SHA(path)==entry['sha256'],'Changed hardware evidence')
        boards[board]=public_board(board,path,KIT_SHA)
    proof_names=('debugger-test.json','debugger-test-65c816-e.json','debugger-test-manuals.json','debugger-test-65c816-e-manuals.json')
    for name in proof_names:
        proof=READ(BUILD/name)
        require(proof['passed'] and proof['full_boot_tested'] and not proof['board_access'] and not proof['native_816_tested'] and proof['firmware_sha256']==IMAGE_SHA,'Wrong offline scope')
        if 'manuals' in name:
            require(proof['manual_example_cases']==8 and proof['test_harness_sha256']==SHA(ROOT/'tools/test_rc1_debugger.py'),'Stale manual test')
            for doc,digest in proof['manual_sources_sha256'].items():require(SHA(ROOT/'docs/rc1'/doc)==digest,'Changed example')
    model=READ(ROOT/'BUILD/rc1-debugger-boardtest-model-r1/report.json')
    require(model['passed'] and model['package_manifest_sha256']==KIT_SHA and len(model['checks'])==21 and all(c['passed'] for c in model['checks']),'Installer model proof incomplete')
    out.mkdir(parents=True)
    for name in manifest['files']:copy(safe(KIT,name),safe(out/'install',name))
    copy(KIT/'board-test-manifest.json',out/'install/board-test-manifest.json')
    for path in (ROOT/'docs/rc1').rglob('*'):
        if path.is_file():copy(path,out/'docs/rc1'/path.relative_to(ROOT/'docs/rc1'))
    copy(ROOT/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md',out/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md')
    for name in ('README.md','BOARD_TEST.md','BRK_ABI.md'):copy(HERE/name,out/'release/candidates/rc1-debugger'/name)
    for path in (ROOT/'release/rc1-uchess').iterdir():
        if path.is_file():copy(path,out/'release/rc1-uchess'/path.name)
    copy(ROOT/'LICENSE',out/'LICENSE')
    for name in ('README.md','INSTALL_ROLLBACK.md','verify_package.py'):copy(HERE/'package'/name,out/name)
    (out/'requirements.txt').write_text('pyserial==3.5\n',encoding='ascii')
    copy(BUILD/'firmware.bin',out/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin')
    copy(KIT/'sectors/b1-a000.bin',out/'firmware/debugger-a000.bin')
    debug=(out/'firmware/debugger-a000.bin').read_bytes();require(len(debug)==4096 and binascii.crc_hqx(debug,65535)==0,'Debugger CRC mismatch')
    for sector in manifest['sectors']:
        body=(out/'install'/sector['target']).read_bytes();offset=(sector['bank']-1)*32768+sector['address']-0x8000
        require((BUILD/'firmware.bin').read_bytes()[offset:offset+4096]==body,'Image/sector mismatch')
    for board,proof in boards.items():save(out/f'qualification/boards/{board}.json',proof)
    for name in (*proof_names,'debugger-build.json'):copy(BUILD/name,out/'qualification/offline'/name)
    copy(ROOT/'BUILD/rc1-debugger-boardtest-model-r1/report.json',out/'qualification/offline/board-package-model.json')
    save(out/'qualification/offline/documentation-audit-summary.json',dict(passed=True,source_receipt_sha256=SHA(audit_path),
        local_links_checked=audit['local_links_checked'],manual_files_checked=audit['manual_files_checked'],frozen_rc1_sources_verified=97,
        board_access=False,native_debugging=False,documentation=audit['documentation'],finished_utc=audit['finished_utc']))
    observer=Path(audit['boards']['2609']['report']).parent/'mode-observer';pin=READ(observer/'report.json')
    for name,key in (('mode.bin','binary_sha256'),('mode.s19','s19_sha256'),('mode.asm','source_sha256')):
        require(SHA(observer/name)==pin[key],'Mode observer changed');copy(observer/name,out/'diagnostics/emulation'/name)
    require(pin['passed'] and not pin['enters_native_mode'],'Invalid mode observer');copy(observer/'report.json',out/'diagnostics/emulation/report.json')
    save(out/'qualification/summary.json',dict(passed=True,candidate='rc1-debugger-v1',generation=50,
        tested_board_kit_manifest_sha256=KIT_SHA,firmware_sha256=IMAGE_SHA,hardware_boards=['2604','2609'],monitor_slots=['A','B'],
        runtime=['65C02','65C816 E=1'],breakpoint_hits_total=64,original_application_RAM_host_verified=True,
        original_preferences_restored=True,RTC_controls_trims_preserved=True,offline_groups=dict(original_65c02=21,original_65c816_e=24,manuals_65c02=22,manuals_65c816_e=25,installer_package_model=21),
        manual_example_executions=16,system_user_registration_hardware_tested=False,rollback_hardware_executed=False,
        native_debugging=False,native_applications_tested=False,unchanged_reset_CPU_detection=True,
        not_qualified=['native applications/debugging','interrupted-write recovery','electrical timing','general occupied-bank upgrades','full endurance/RTC qualification'],
        source_hardware_receipt_sha256={board:proof['source_receipt_sha256'] for board,proof in boards.items()}))
    link_count=links_resolve(out)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(out.rglob('*')) if p.is_file()}
    for name in files:
        require(not any(part in ('__pycache__','before','after','private','capture') for part in Path(name).parts) and not name.endswith(('.jsonl','.pyc','.zip')),'Private/cache/archive file: '+name)
        path=out/name
        if path.suffix in ('.py','.md','.json','.txt'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',path.read_text(encoding='utf-8')),'Host path leaked: '+name)
    save(out/'package-manifest.json',dict(schema=1,candidate='rc1-debugger-v1',version='2.0rc1 DBG1',generation=50,distribution_revision=1,
        runtime=['65C02','65C816 E=1'],native_debugging=False,native_applications_tested=False,application_RAM_reserved_bytes=0,
        debugger_code_bytes=3967,debugger_CRC_bytes=2,debugger_sector_free_bytes=127,tested_board_kit_manifest_sha256=KIT_SHA,
        firmware_sha256=IMAGE_SHA,install_method='Fresh exact-source standalone RAM plan; seven firmware sectors; nine 4K transfers',
        board_transport='Windows, Python 3.10+, pyserial 3.5; explicit COM/USB/board identity',
        board_backups_or_logs_included=False,board_specific_plans_included=False,reference_image_is_preserving_updater=False,
        published_generation49_release_changed=False,package_markdown_links_checked=link_count,files=files))
    sums=dict(files);sums['package-manifest.json']=dict(bytes=(out/'package-manifest.json').stat().st_size,sha256=SHA(out/'package-manifest.json'))
    (out/'SHA256SUMS.txt').write_text(''.join(info['sha256']+'  '+name+'\n' for name,info in sorted(sums.items())),encoding='ascii')
    check=subprocess.run([sys.executable,str(out/'verify_package.py')],capture_output=True,text=True)
    require(check.returncode==0,check.stdout+check.stderr)
    names=sorted([*sums,'SHA256SUMS.txt'])
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            entry=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,18,0,0,0));entry.create_system=3;entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,(out/name).read_bytes())
    checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
    receipt=Q/(out.name+'-package-report.json');require(not receipt.exists(),'Package receipt already exists')
    save(receipt,dict(passed=True,archive=str(archive),bytes=archive.stat().st_size,sha256=SHA(archive),checksum=str(checksum),
        distribution=str(out),files=len(names),markdown_links_checked=link_count,tested_board_kit_manifest_sha256=KIT_SHA,
        firmware_sha256=IMAGE_SHA,boards=['2604','2609'],board_access=False,native_debugging=False,private_captures_included=False))
    print(check.stdout.strip());print('PASS packaged',archive);print('SHA256',SHA(archive));print('Receipt',receipt)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
