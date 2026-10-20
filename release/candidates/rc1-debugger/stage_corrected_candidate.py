"""Stage the exact corrected candidate, with qualification pending. No ports."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
KIT=ROOT/'BUILD/rc1-debugger-boardtest-r2';BUILD=ROOT/'BUILD/rc1-debugger-v1f'
HARDWARE=ROOT/'output/qualification/rc1-dbg1-maint-requalification-2026-10-19-1718Z'
KIT_SHA='87f5b610ed309f0be7ab8bd63e7f630bbc9c2e9885ecd048022227502934bb7d'
IMAGE_SHA='923c8fee01310b873e89cc5e8982778e25fd425ccb9050735fb07604ef6228ba'
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')

def copy(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)

def safe(root,name):
    path=(root/name).resolve();require(not Path(name).is_absolute() and '\\' not in name and path.is_relative_to(root.resolve()),'Unsafe input path');return path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--review',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    review=a.review.resolve();out=a.out.resolve();archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256')
    require(not out.exists() and not archive.exists() and not checksum.exists(),'Use a fresh staging path')
    require(SHA(KIT/'board-test-manifest.json')==KIT_SHA and SHA(BUILD/'firmware.bin')==IMAGE_SHA,'Wrong corrected candidate')
    require(READ(ROOT/'output/qualification/rc1-dbg1-promotion-hold.json')['held'],'Promotion must remain held')
    r=READ(review/'report.json');docs=READ(review/'documentation-audit.json');hardware=READ(HARDWARE/'report.json')
    require(r['audit_completed'] and r['promotion_held'] and not r['release_qualification_passed'] and r['protected_inputs_unchanged'],'Incomplete review')
    require(not r['board_access'] and not r['native_debugging'] and not r['native_applications_tested'],'Wrong review scope')
    require(r['firmware_sha256']==IMAGE_SHA and r['package_manifest_sha256']==KIT_SHA and r['hardware_report_sha256']==SHA(HARDWARE/'report.json'),'Changed review inputs')
    require(docs['passed'] and hardware['passed'] and hardware['checks_complete'] and hardware['promotion_held'],'Incomplete evidence')
    for name,digest in docs['documentation'].items():require(SHA(ROOT/name)==digest,'Changed audited documentation: '+name)
    for path,digest in READ(review/'protected-inputs-before.json').items():require(SHA(path)==digest,'Changed protected input: '+path)
    for name,digest in READ(HARDWARE/'evidence-checksums.json')['files'].items():require(SHA(safe(HARDWARE,name))==digest,'Changed hardware evidence')
    kit=READ(KIT/'board-test-manifest.json')
    for name,info in kit['files'].items():require(SHA(safe(KIT,name))==info['sha256'],'Changed kit file');copy(KIT/name,out/'install'/name)
    copy(KIT/'board-test-manifest.json',out/'install/board-test-manifest.json')
    for path in (ROOT/'docs/rc1').rglob('*'):
        if path.is_file():copy(path,out/'docs/rc1'/path.relative_to(ROOT/'docs/rc1'))
    copy(ROOT/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md',out/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md')
    for name in ('README.md','BOARD_TEST.md','BRK_ABI.md'):copy(HERE/name,out/'release/candidates/rc1-debugger'/name)
    for name in ('README.md','INSTALL_ROLLBACK.md','verify_package.py'):copy(HERE/'package-staged'/name,out/name)
    for path in (ROOT/'release/rc1-uchess').iterdir():
        if path.is_file():copy(path,out/'release/rc1-uchess'/path.name)
    copy(ROOT/'LICENSE',out/'LICENSE');(out/'requirements.txt').write_text('pyserial==3.5\n',encoding='ascii')
    copy(BUILD/'firmware.bin',out/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin')
    copy(KIT/'sectors/b1-a000.bin',out/'firmware/debugger-a000.bin')
    observer=ROOT/'output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer'
    pin=READ(observer/'report.json');require(pin['passed'] and not pin['enters_native_mode'],'Invalid E=1 observer')
    for name,key in [('mode.asm','source_sha256'),('mode.bin','binary_sha256'),('mode.s19','s19_sha256')]:
        require(SHA(observer/name)==pin[key],'Changed E=1 observer');copy(observer/name,out/'diagnostics/emulation'/name)
    copy(observer/'report.json',out/'diagnostics/emulation/report.json')
    copy(ROOT/'tools/rc1_dbg_closeout_cases.py',out/'diagnostics/registrations/cases.py')
    for board,b in hardware['boards'].items():
        save(out/f'qualification/boards/{board}.json',dict(passed=b['passed'],board=board,runtime=b['CPU'],both_slots_passed=b['both_slots_MAINT_and_apps_passed'],
            registration_cases=b['registration_cases'],breakpoint_hits=b['breakpoint_hits'],rollback_reinstall_passed=b['rollback_reinstall_passed'],
            original_application_RAM_restored=b['original_application_RAM_restored'],RAM_bytes=b['RAM_bytes'],RTC_settings_preserved=b['RTC_settings_preserved'],
            preferred_monitor=b['preferred_monitor'],final_bank_sha256=b['final_bank_sha256'],source_final_receipt_sha256=SHA(b['final_receipt']),
            firmware_sha256=IMAGE_SHA,package_manifest_sha256=KIT_SHA,native_debugging=False))
    save(out/'qualification/review/summary.json',r);copy(review/'documentation-audit.json',out/'qualification/review/documentation-audit.json')
    for cpu,suffix in [('02',''),('816','-65c816-e')]:
        path=review/'model-build'/f'debugger-test{suffix}-manuals.json'
        require(SHA(path)==r['full_model_and_manual_checks'][cpu]['source_report_sha256'],'Changed model/manual evidence')
        copy(path,out/'qualification/offline'/path.name)
        edge=review/'edges-confirmed'/f'edge-review-{cpu}.json'
        require(SHA(edge)==r['additional_edge_review'][cpu]['source_report_sha256'],'Changed edge evidence');copy(edge,out/'qualification/review'/edge.name)
        registration=HARDWARE/f'registration-model-{cpu}.json';proof=READ(registration)
        require(proof['passed'] and len(proof['groups'])==36 and proof['case_source_sha256']==SHA(ROOT/'tools/rc1_dbg_closeout_cases.py'),'Wrong registration coverage')
        copy(registration,out/'qualification/offline'/registration.name)
    model=ROOT/'BUILD/rc1-debugger-boardtest-r2-offline/report.json';m=READ(model)
    require(m['passed'] and m['package_manifest_sha256']==KIT_SHA and m['actual_installer_instructions'] and not m['board_access'],'Wrong installer model')
    copy(model,out/'qualification/offline/board-package-model.json')
    save(out/'qualification/soak/pending.json',dict(status='pending',authorized_hours=6,boards=['2604','2609'],candidate_build='v1f-MAINT-corrected',
        firmware_sha256=IMAGE_SHA,package_manifest_sha256=KIT_SHA,final_drift_snapshot='pending',historical_v1e_soak_reused=False,
        note='Staged snapshot only. No final corrected-image soak/drift result is claimed. Create a new package after completion.'))
    save(out/'qualification/summary.json',dict(release_qualification_passed=False,promotion_held=True,candidate_build='v1f-MAINT-corrected',firmware_sha256=IMAGE_SHA,
        hardware_requalification_passed=True,hardware_registration_scenarios=72,hardware_breakpoint_hits=128,device_verified_transfers=84,
        hardware_source_report_sha256=SHA(HARDWARE/'report.json'),hardware_evidence_index_sha256=SHA(HARDWARE/'evidence-checksums.json'),
        full_model_and_manual_checks=r['full_model_and_manual_checks'],six_hour_soak_passed=None,final_drift_snapshot_passed=None,
        open_findings=[f['id'] for f in r['findings']],pending=['review-findings-resolution','corrected-six-hour-soak','end-of-soak-drift','explicit-promotion-decision'],
        board_access_during_staging=False,native_debugging=False,native_applications_tested=False,source_review_sha256=SHA(review/'report.json')))
    sys.path.insert(0,str(ROOT/'tools'));from audit_rc1_dbg_docs import audit
    links=audit(out,list(out.rglob('*.md')));require(links['passed'],'Broken staged link/anchor: '+str(links['errors']))
    save(out/'qualification/review/package-documentation-audit.json',links)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(out.rglob('*')) if p.is_file()}
    for name in files:
        require(not any(part in ('__pycache__','private','capture','before','after') for part in Path(name).parts) and not name.endswith(('.jsonl','.pyc','.zip')),'Private/cache file: '+name)
        if Path(name).suffix in ('.py','.md','.json','.txt'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',(out/name).read_text(encoding='utf-8')),'Host path leaked: '+name)
    save(out/'package-manifest.json',dict(schema=1,candidate='rc1-debugger-v1',candidate_build='v1f-MAINT-corrected',generation=50,distribution_revision=3,
        release_status='staged-promotion-held',promotion_held=True,runtime=['65C02','65C816 E=1'],native_debugging=False,native_applications_tested=False,
        application_RAM_reserved_bytes=0,debugger_code_bytes=3967,debugger_CRC_bytes=2,debugger_sector_free_bytes=127,
        firmware_sectors=9,transfers_per_transaction=11,tested_board_kit_manifest_sha256=KIT_SHA,firmware_sha256=IMAGE_SHA,
        reference_image_is_preserving_updater=False,board_backups_or_logs_included=False,board_specific_plans_included=False,published_generation49_release_changed=False,
        staged_utc=datetime.now(timezone.utc).isoformat(),package_markdown_links_checked=links['links_and_anchors_checked'],files=files))
    sums=dict(files);sums['package-manifest.json']=dict(bytes=(out/'package-manifest.json').stat().st_size,sha256=SHA(out/'package-manifest.json'))
    (out/'SHA256SUMS.txt').write_text(''.join(info['sha256']+'  '+name+'\n' for name,info in sorted(sums.items())),encoding='ascii')
    check=subprocess.run([sys.executable,str(out/'verify_package.py')],capture_output=True,text=True);require(check.returncode==0,check.stdout+check.stderr)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted([*sums,'SHA256SUMS.txt']):
            entry=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,19,0,0,0));entry.create_system=3;entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,(out/name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='dbg-stage-extract-',dir=ROOT/'tmp') as temp:
        with zipfile.ZipFile(archive) as z:
            require(z.testzip() is None,'Archive CRC error');z.extractall(temp)
        extracted=Path(temp)/out.name;test=subprocess.run([sys.executable,str(extracted/'verify_package.py')],capture_output=True,text=True)
        require(test.returncode==0,test.stdout+test.stderr)
    checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
    receipt=dict(integrity_passed=True,release_qualification_passed=False,promotion_held=True,archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_sha256=SHA(archive),archive_checksum=str(checksum),distribution=str(out),files_verified=len(sums)+1,extracted_archive_verified=True,
        markdown_links_and_anchors_checked=links['links_and_anchors_checked'],firmware_sha256=IMAGE_SHA,package_manifest_sha256=SHA(out/'package-manifest.json'),
        tested_kit_manifest_sha256=KIT_SHA,source_review_sha256=SHA(review/'report.json'),board_access=False,native_debugging=False,
        native_applications_tested=False,six_hour_soak='pending',final_drift='pending',open_findings=[f['id'] for f in r['findings']])
    save(review/'staging-package-report.json',receipt);print(check.stdout.strip());print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,KeyError,ValueError) as error:raise SystemExit('REFUSED: '+str(error))
