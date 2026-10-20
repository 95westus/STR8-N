"""Stage v1g with offline evidence and pending hardware acceptance. No ports."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BUILD=ROOT/'BUILD/rc1-debugger-v1g';KIT=ROOT/'BUILD/rc1-debugger-v1g-boardtest-r1'
KIT_SHA='42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf'
IMAGE_SHA='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
LABEL='v1g-BRK82-84-edge-fix'
sys.path.insert(0,str(HERE.parent/'rc1-debugger'))
from stage_corrected_candidate import copy,save,safe,require
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--offline',type=Path,required=True);ap.add_argument('--record',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    offline=a.offline.resolve();record=a.record.resolve();out=a.out.resolve();archive=Path(str(out)+'.zip');checksum=Path(str(archive)+'.sha256')
    require(not out.exists() and not archive.exists() and not checksum.exists(),'Use a fresh staging directory')
    require(not (record/'package-report.json').exists(),'Staging receipt already exists')
    scope=READ(record/'owner-scope.json');proof=READ(offline/'report.json')
    require(scope['candidate_build']==LABEL and scope['candidate_firmware_sha256']==IMAGE_SHA and scope['promotion_held'],'Wrong authorized staging scope')
    require(READ(ROOT/'output/qualification/rc1-dbg1-promotion-hold.json')['held'],'Promotion must remain held')
    for path,digest in READ(record/'protected-inputs-before.json').items():require(SHA(path)==digest,'Changed protected input: '+path)
    evidence=READ(offline/'evidence-checksums.json')
    for name,digest in evidence['files'].items():
        path=Path(name) if Path(name).is_absolute() else safe(offline,name)
        require(SHA(path)==digest,'Changed offline evidence: '+name)
    require(proof['passed'] and proof['offline_qualification_passed'] and proof['candidate_build']==LABEL and proof['firmware_sha256']==IMAGE_SHA,'Wrong offline qualification')
    require(proof['promotion_held'] and not proof['hardware_qualified'] and not proof['soak_qualified'] and not proof['release_qualification_passed'] and not proof['board_access'] and not proof['native_debugging'] and not proof['native_applications_tested'],'Wrong qualification/runtime scope')
    require(SHA(BUILD/'firmware.bin')==IMAGE_SHA and SHA(KIT/'board-test-manifest.json')==KIT_SHA==proof['tested_kit_manifest_sha256'],'Wrong image/kit')
    manifest=READ(KIT/'board-test-manifest.json')
    for name,info in manifest['files'].items():
        require(SHA(safe(KIT,name))==info['sha256'],'Changed kit file: '+name);copy(KIT/name,out/'install'/name)
    copy(KIT/'board-test-manifest.json',out/'install/board-test-manifest.json')
    for path in (ROOT/'docs/rc1').rglob('*'):
        if path.is_file():copy(path,out/'docs/rc1'/path.relative_to(ROOT/'docs/rc1'))
    for path in (HERE/'package-staged/docs').rglob('*'):
        if path.is_file():copy(path,out/'docs'/path.relative_to(HERE/'package-staged/docs'))
    release_paths=out/'docs/rc1/RELEASE_PATHS.md'
    text=release_paths.read_text(encoding='utf-8')
    require('../../release/candidates/rc1-debugger/BOARD_TEST.md' in text,'Expected inherited board-procedure link')
    release_paths.write_text(text.replace('../../release/candidates/rc1-debugger/BOARD_TEST.md','../../INSTALL_ROLLBACK.md'),encoding='utf-8')
    copy(ROOT/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md',out/'docs/STR8N_RC1_UTC_BOARD_UPDATE_2026-10-18.md')
    copy(HERE.parent/'rc1-debugger/BRK_ABI.md',out/'release/candidates/rc1-debugger/BRK_ABI.md')
    copy(HERE/'README.md',out/'release/candidates/rc1-debugger-brkfix-r1/README.md')
    for name in ('README.md','INSTALL_ROLLBACK.md','verify_package.py'):copy(HERE/'package-staged'/name,out/name)
    for path in (ROOT/'release/rc1-uchess').iterdir():
        if path.is_file():copy(path,out/'release/rc1-uchess'/path.name)
    copy(ROOT/'LICENSE',out/'LICENSE');(out/'requirements.txt').write_text('pyserial==3.5\n',encoding='ascii')
    copy(BUILD/'firmware.bin',out/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin');copy(KIT/'sectors/b1-a000.bin',out/'firmware/debugger-a000.bin')
    for path in (HERE/'source').iterdir():
        if path.is_file():copy(path,out/'source/debugger'/path.name)
    copy(BUILD/'debugger/generated.inc',out/'source/debugger/generated.inc')
    observer=ROOT/'output/qualification/rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer';pin=READ(observer/'report.json')
    require(pin['passed'] and not pin['enters_native_mode'],'Invalid E=1 observer')
    for name,key in [('mode.asm','source_sha256'),('mode.bin','binary_sha256'),('mode.s19','s19_sha256')]:
        require(SHA(observer/name)==pin[key],'Changed E=1 observer');copy(observer/name,out/'diagnostics/emulation'/name)
    copy(observer/'report.json',out/'diagnostics/emulation/report.json')
    copy(ROOT/'tools/rc1_dbg_closeout_cases.py',out/'diagnostics/registrations/cases.py')
    copy(offline/'report.json',out/'qualification/offline/summary.json')
    copy(offline/'build-comparison.json',out/'qualification/offline/build-comparison.json')
    for suffix in ('','-65c816-e'):copy(BUILD/f'debugger-test{suffix}-manuals.json',out/f'qualification/offline/debugger-test{suffix}-manuals.json')
    for name in ('debugger-build.json','candidate-provenance.json','test-aliases.json'):copy(BUILD/name,out/'qualification/offline'/name)
    for cpu in ('02','816'):
        copy(offline/'original-88-regressions'/f'edge-review-{cpu}.json',out/f'qualification/offline/edge-review-{cpu}.json')
        copy(offline/'expanded-regressions'/f'brk-regressions-{cpu}.json',out/f'qualification/offline/brk-regressions-{cpu}.json')
        copy(offline/f'registration-model-{cpu}.json',out/f'qualification/offline/registration-model-{cpu}.json')
    copy(ROOT/'BUILD/rc1-debugger-v1g-boardtest-model-r1/report.json',out/'qualification/offline/board-package-model.json')
    save(out/'qualification/offline/source-evidence.json',dict(source_report_sha256=SHA(offline/'report.json'),source_evidence_index_sha256=SHA(offline/'evidence-checksums.json'),source_files_verified=len(evidence['files']),board_access=False))
    for kind in ('hardware','soak'):
        save(out/f'qualification/{kind}/pending.json',dict(status='pending-not-started',candidate_build=LABEL,firmware_sha256=IMAGE_SHA,boards=['2604','2609'],
            monitor_slots=['A','B'],runtime=['65C02','65C816 E=1'],parent_results_reused=False,board_access_during_staging=False,
            note='Not performed for this image. Staging does not authorize or start hardware work.'))
    save(out/'qualification/summary.json',dict(candidate_build=LABEL,firmware_sha256=IMAGE_SHA,promotion_held=True,release_qualification_passed=False,
        offline_qualification_passed=True,hardware_requalification_passed=None,six_hour_soak_passed=None,final_drift_snapshot_passed=None,
        hardware_registration_scenarios=0,hardware_breakpoint_hits=0,device_verified_hardware_transfers=0,offline_registration_scenarios=72,
        parent_hardware_or_soak_results_reused=False,findings_resolved_offline=proof['findings_resolved_offline_in_this_candidate'],
        pending=['both-board-both-slot-hardware-requalification','physical-rollback-reinstall','separately-authorized-soak','final-drift-review','explicit-promotion-decision'],
        source_offline_report_sha256=SHA(offline/'report.json'),board_access_during_staging=False,native_debugging=False,native_applications_tested=False))
    sys.path.insert(0,str(ROOT/'tools'));from audit_rc1_dbg_docs import audit
    docs=audit(out,list(out.rglob('*.md')));require(docs['passed'],'Broken link/anchor: '+str(docs['errors']));save(out/'qualification/documentation-audit.json',docs)
    files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=SHA(p)) for p in sorted(out.rglob('*')) if p.is_file()}
    for name in files:
        require(not any(part in ('__pycache__','private','capture','before','after') for part in Path(name).parts) and not name.endswith(('.jsonl','.pyc','.zip')),'Private/cache file included: '+name)
        if Path(name).suffix in ('.py','.md','.json','.txt'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/',(out/name).read_text(encoding='utf-8')),'Host path leaked: '+name)
    save(out/'package-manifest.json',dict(schema=1,candidate='rc1-debugger-v1',candidate_build=LABEL,generation=50,distribution_revision=4,
        release_status='staged-promotion-held',promotion_held=True,hardware_qualified=False,soak_qualified=False,runtime=['65C02','65C816 E=1'],
        native_debugging=False,native_applications_tested=False,application_RAM_reserved_bytes=0,debugger_code_bytes=3975,debugger_CRC_bytes=2,debugger_sector_free_bytes=119,
        firmware_sectors=9,transfers_per_transaction=11,tested_board_kit_manifest_sha256=KIT_SHA,firmware_sha256=IMAGE_SHA,
        reference_image_is_preserving_updater=False,board_backups_or_logs_included=False,board_specific_plans_included=False,published_generation49_release_changed=False,
        staged_utc=datetime.now(timezone.utc).isoformat(),package_markdown_links_checked=docs['links_and_anchors_checked'],files=files))
    sums=dict(files);sums['package-manifest.json']=dict(bytes=(out/'package-manifest.json').stat().st_size,sha256=SHA(out/'package-manifest.json'))
    (out/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in sorted(sums.items())),encoding='ascii')
    check=subprocess.run([sys.executable,str(out/'verify_package.py')],capture_output=True,text=True);require(check.returncode==0,check.stdout+check.stderr)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted([*sums,'SHA256SUMS.txt']):
            entry=zipfile.ZipInfo(out.name+'/'+name,date_time=(2026,10,19,0,0,0));entry.create_system=3;entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,(out/name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='dbg-v1g-stage-extract-',dir=ROOT/'tmp') as temp:
        with zipfile.ZipFile(archive) as z:
            require(z.testzip() is None,'Archive CRC error');z.extractall(temp)
        extracted=Path(temp)/out.name;test=subprocess.run([sys.executable,str(extracted/'verify_package.py')],capture_output=True,text=True);require(test.returncode==0,test.stdout+test.stderr)
    checksum.write_text(SHA(archive)+'  '+archive.name+'\n',encoding='ascii')
    receipt=dict(integrity_passed=True,offline_qualification_passed=True,promotion_held=True,release_qualification_passed=False,hardware='pending',soak='pending',final_drift='pending',
        candidate_build=LABEL,firmware_sha256=IMAGE_SHA,tested_kit_manifest_sha256=KIT_SHA,package_manifest_sha256=SHA(out/'package-manifest.json'),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=SHA(archive),archive_checksum=str(checksum),distribution=str(out),
        files_verified=len(sums)+1,extracted_archive_verified=True,markdown_links_and_anchors_checked=docs['links_and_anchors_checked'],board_access=False,native_debugging=False,native_applications_tested=False)
    save(record/'package-report.json',receipt);print(check.stdout.strip());print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,KeyError,ValueError) as error:raise SystemExit('REFUSED: '+str(error))
