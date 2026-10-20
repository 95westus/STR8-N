"""Verify the offline-only v1g staging snapshot with stdlib. Never opens ports."""
import binascii
import hashlib
import json
from pathlib import Path
import re

KIT_SHA='42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf'
IMAGE_SHA='6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
BUILD='v1g-BRK82-84-edge-fix'
FIXES={'DBG1-REVIEW-82-ZERO','DBG1-REVIEW-84-END'}
READ=lambda p:json.loads(p.read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def verify(root=None):
    root=Path(root or Path(__file__).resolve().parent).resolve();m=READ(root/'package-manifest.json')
    require(m['candidate_build']==BUILD and m['generation']==50 and m['distribution_revision']==4,'Wrong candidate')
    require(m['release_status']=='staged-promotion-held' and m['promotion_held'] and not m['hardware_qualified'] and not m['soak_qualified'],'Wrong qualification scope')
    require(m['runtime']==['65C02','65C816 E=1'] and not m['native_debugging'] and not m['native_applications_tested'],'Unsupported runtime')
    require(m['application_RAM_reserved_bytes']==0 and m['debugger_code_bytes']==3975 and m['debugger_CRC_bytes']==2 and m['debugger_sector_free_bytes']==119,'Wrong memory scope')
    require(m['firmware_sectors']==9 and m['transfers_per_transaction']==11 and m['tested_board_kit_manifest_sha256']==KIT_SHA and m['firmware_sha256']==IMAGE_SHA,'Wrong image/kit pin')
    files=m['files'];expected=dict(files);manifest=root/'package-manifest.json'
    expected['package-manifest.json']=dict(bytes=manifest.stat().st_size,sha256=SHA(manifest));sums={}
    for line in (root/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        require(match is not None and match[2] not in sums,'Invalid checksum inventory');sums[match[2]]=match[1]
    require(set(sums)==set(expected),'Checksum inventory differs')
    for name,info in expected.items():
        path=(root/name).resolve();require(not Path(name).is_absolute() and '\\' not in name and path.is_relative_to(root),'Unsafe package path')
        require(path.stat().st_size==info['bytes'] and SHA(path)==info['sha256']==sums[name],'Changed file: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual==set(expected)|{'SHA256SUMS.txt'},'Unexpected/missing files')
    kit=root/'install';require(SHA(kit/'board-test-manifest.json')==KIT_SHA,'Changed offline-qualified kit')
    original=READ(kit/'board-test-manifest.json')
    require(original['candidate_build']==BUILD and not original['hardware_qualified'] and not original['soak_qualified'],'Wrong kit scope')
    for name,info in original['files'].items():require(files.get('install/'+name)==info,'Changed kit inventory: '+name)
    image=root/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin';require(SHA(image)==IMAGE_SHA,'Wrong reference image')
    raw=image.read_bytes();require(len(raw)==98304 and len(original['sectors'])==9,'Wrong image/sector count')
    for sector in original['sectors']:
        offset=(sector['bank']-1)*32768+sector['address']-0x8000
        require((kit/sector['target']).read_bytes()==raw[offset:offset+4096],'Kit/image mismatch')
    debugger=(root/'firmware/debugger-a000.bin').read_bytes()
    require(len(debugger)==4096 and binascii.crc_hqx(debugger,65535)==0 and debugger==raw[0x2000:0x3000],'Debugger CRC/image mismatch')
    summary=READ(root/'qualification/summary.json');offline=READ(root/'qualification/offline/summary.json')
    require(summary['candidate_build']==BUILD and summary['firmware_sha256']==IMAGE_SHA and summary['promotion_held'] and summary['release_qualification_passed'] is False,'Premature release claim')
    require(summary['hardware_requalification_passed'] is None and summary['six_hour_soak_passed'] is None and summary['final_drift_snapshot_passed'] is None,'Premature hardware/soak/drift claim')
    require(summary['hardware_registration_scenarios']==summary['hardware_breakpoint_hits']==summary['device_verified_hardware_transfers']==0 and summary['offline_registration_scenarios']==72,'Parent hardware evidence reused')
    require(not summary['parent_hardware_or_soak_results_reused'] and not (root/'qualification/boards').exists(),'Parent hardware evidence included')
    for kind in ('hardware','soak'):
        pending=READ(root/f'qualification/{kind}/pending.json')
        require(pending['status']=='pending-not-started' and pending['candidate_build']==BUILD and pending['firmware_sha256']==IMAGE_SHA and not pending['parent_results_reused'],'Wrong pending scope')
    require(offline['passed'] and offline['offline_qualification_passed'] and offline['firmware_sha256']==IMAGE_SHA and offline['candidate_build']==BUILD,'Wrong offline summary')
    require(offline['promotion_held'] and not offline['hardware_qualified'] and not offline['soak_qualified'] and not offline['release_qualification_passed'],'Offline summary claims hardware acceptance')
    require(not offline['board_access'] and not offline['native_debugging'] and not offline['native_applications_tested'],'Wrong offline runtime')
    require(offline['expanded_regression_cases']==7256 and offline['original_edge_checks']==88 and offline['registration_scenario_executions']==72 and offline['manual_example_executions']==16,'Incomplete offline coverage')
    require(set(offline['findings_resolved_offline_in_this_candidate'])==FIXES,'Missing offline fix evidence')
    for cpu,suffix,groups in [('02','',23),('816','-65c816-e',26)]:
        r=READ(root/f'qualification/offline/debugger-test{suffix}-manuals.json')
        require(r['passed'] and r['full_boot_tested'] and r['check_groups']==groups and r['manual_example_cases']==8 and r['board_smoke_cases']==8 and r['firmware_sha256']==IMAGE_SHA and not r['board_access'] and not r['native_816_tested'],'Wrong full model/manual evidence')
        for name,digest in r['manual_sources_sha256'].items():require(SHA(root/'docs/rc1'/name)==digest,'Changed tested manual: '+name)
        edge=READ(root/f'qualification/offline/edge-review-{cpu}.json')
        require(edge['passed'] and edge['firmware_sha256']==IMAGE_SHA and len(edge['checks'])==44 and all(c['passed'] and c['expected']==c['observed'] for c in edge['checks']),'Failed original edge regression')
        extended=READ(root/f'qualification/offline/brk-regressions-{cpu}.json')
        require(extended['passed'] and extended['firmware_sha256']==IMAGE_SHA and extended['cases']==3628 and sum(g['cases'] for g in extended['groups'])==3628 and not extended['failures'],'Failed expanded regression')
        reg=READ(root/f'qualification/offline/registration-model-{cpu}.json')
        require(reg['passed'] and reg['firmware_sha256']==IMAGE_SHA and len(reg['groups'])==36 and all(g['passed'] for g in reg['groups']) and reg['case_source_sha256']==SHA(root/'diagnostics/registrations/cases.py'),'Incomplete registration evidence')
    installer=READ(root/'qualification/offline/board-package-model.json')
    require(installer['passed'] and installer['package_manifest_sha256']==KIT_SHA and installer['actual_installer_instructions'] and len(installer['checks'])==21 and all(c['passed'] for c in installer['checks']) and not installer['board_access'] and not installer['native_debugging'],'Wrong installer evidence')
    comparison=READ(root/'qualification/offline/build-comparison.json')
    require(comparison['passed'] and comparison['firmware_sha256']==comparison['repro_firmware_sha256']==IMAGE_SHA and comparison['only_changed_sector']=='B1:A000-AFFF','Wrong reproducibility evidence')
    provenance=READ(root/'qualification/offline/candidate-provenance.json')
    require(provenance['candidate_build']==BUILD and provenance['firmware_sha256']==IMAGE_SHA and provenance['promotion_held'] and not provenance['hardware_qualified'] and not provenance['soak_qualified'],'Wrong provenance')
    for name,digest in provenance['candidate_source_sha256'].items():require(SHA(root/'source/debugger'/name)==digest,'Changed debugger source')
    require(READ(root/'qualification/documentation-audit.json')['passed'],'Documentation audit failed')
    require('3,975 code bytes plus two CRC bytes, 119 free' in (root/'docs/rc1/TECHNICAL_MANUAL.md').read_text(encoding='utf-8'),'Stale technical footprint')
    contents=(root/'docs/rc1/FIRMWARE_CONTENTS.md').read_text(encoding='utf-8')
    require('nine firmware sectors' in contents and 'eleven-transfer install' in contents,'Stale firmware install map')
    return dict(integrity_passed=True,files_verified=len(expected)+1,candidate_build=BUILD,promotion_held=True,offline_qualification_passed=True,
        release_qualification_passed=False,hardware='pending',soak='pending',final_drift='pending',board_access=False,native_debugging=False)

if __name__=='__main__':
    try:print(json.dumps(verify(),indent=2))
    except (OSError,KeyError,ValueError) as error:raise SystemExit('REFUSED: '+str(error))
