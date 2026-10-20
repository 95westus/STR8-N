"""Verify this held staging snapshot using stdlib only. Never accesses a board."""
import binascii
import hashlib
import json
from pathlib import Path
import re

KIT_SHA='87f5b610ed309f0be7ab8bd63e7f630bbc9c2e9885ecd048022227502934bb7d'
IMAGE_SHA='923c8fee01310b873e89cc5e8982778e25fd425ccb9050735fb07604ef6228ba'
ISSUES={'DBG1-REVIEW-82-ZERO','DBG1-REVIEW-84-END'}
READ=lambda p:json.loads(p.read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def verify(root=None):
    root=Path(root or Path(__file__).resolve().parent).resolve();m=READ(root/'package-manifest.json')
    require(m['candidate']=='rc1-debugger-v1' and m['candidate_build']=='v1f-MAINT-corrected' and m['generation']==50,'Wrong candidate')
    require(m['distribution_revision']==3 and m['release_status']=='staged-promotion-held' and m['promotion_held'],'Wrong staging scope')
    require(m['runtime']==['65C02','65C816 E=1'] and not m['native_debugging'] and not m['native_applications_tested'],'Unsupported runtime')
    require(m['application_RAM_reserved_bytes']==0 and m['firmware_sectors']==9 and m['transfers_per_transaction']==11,'Wrong memory/install scope')
    require(m['tested_board_kit_manifest_sha256']==KIT_SHA and m['firmware_sha256']==IMAGE_SHA,'Wrong firmware pin')
    files=m['files'];expected=dict(files);manifest=root/'package-manifest.json'
    expected['package-manifest.json']=dict(bytes=manifest.stat().st_size,sha256=SHA(manifest))
    sums={}
    for line in (root/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        require(match is not None and match[2] not in sums,'Invalid checksum inventory');sums[match[2]]=match[1]
    require(set(sums)==set(expected),'Checksum inventory differs')
    for name,info in expected.items():
        path=(root/name).resolve()
        require(not Path(name).is_absolute() and path.is_relative_to(root) and '\\' not in name,'Unsafe package path')
        require(path.stat().st_size==info['bytes'] and SHA(path)==info['sha256']==sums[name],'Changed file: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual==set(expected)|{'SHA256SUMS.txt'},'Unexpected/missing files')
    kit=root/'install';require(SHA(kit/'board-test-manifest.json')==KIT_SHA,'Changed tested kit')
    original=READ(kit/'board-test-manifest.json')
    for name,info in original['files'].items():require(files.get('install/'+name)==info,'Changed kit inventory: '+name)
    image=root/'firmware/str8n-2.0rc1-dbg1-gen50-reference.bin';require(SHA(image)==IMAGE_SHA,'Changed reference firmware')
    raw=image.read_bytes();require(len(raw)==98304 and len(original['sectors'])==9,'Wrong image/sector count')
    for sector in original['sectors']:
        offset=(sector['bank']-1)*32768+sector['address']-0x8000
        require((kit/sector['target']).read_bytes()==raw[offset:offset+4096],'Kit/image mismatch')
    debugger=(root/'firmware/debugger-a000.bin').read_bytes()
    require(len(debugger)==4096 and binascii.crc_hqx(debugger,65535)==0 and debugger==raw[0x2000:0x3000],'Debugger CRC/image mismatch')
    summary=READ(root/'qualification/summary.json');pending=READ(root/'qualification/soak/pending.json')
    require(summary['promotion_held'] and summary['release_qualification_passed'] is False,'Premature qualification claim')
    require(summary['six_hour_soak_passed'] is None and summary['final_drift_snapshot_passed'] is None,'Premature soak/drift claim')
    require(pending['status']=='pending' and pending['authorized_hours']==6 and pending['historical_v1e_soak_reused'] is False,'Wrong pending scope')
    require(set(summary['open_findings'])==ISSUES,'Review findings missing')
    require(summary['hardware_registration_scenarios']==72 and summary['hardware_breakpoint_hits']==128 and summary['device_verified_transfers']==84,'Wrong hardware totals')
    for board in ('2604','2609'):
        b=READ(root/f'qualification/boards/{board}.json')
        require(b['passed'] and b['both_slots_passed'] and b['registration_cases']==36 and b['breakpoint_hits']==64 and b['rollback_reinstall_passed'] and b['original_application_RAM_restored'],'Incomplete board evidence')
    for suffix in ('','-65c816-e'):
        r=READ(root/f'qualification/offline/debugger-test{suffix}-manuals.json')
        require(r['passed'] and r['full_boot_tested'] and r['manual_example_cases']==8 and r['board_smoke_cases']==8 and r['firmware_sha256']==IMAGE_SHA and not r['board_access'] and not r['native_816_tested'],'Wrong offline evidence')
    for cpu in ('02','816'):
        edge=READ(root/f'qualification/review/edge-review-{cpu}.json')
        require(edge['audit_completed'] and edge['passed'] is False and len(edge['checks'])==44 and sum(not c['passed'] for c in edge['checks'])==10 and edge['firmware_sha256']==IMAGE_SHA and not edge['board_access'] and not edge['native_debugging'],'Wrong edge-review scope')
    require(READ(root/'qualification/review/documentation-audit.json')['passed'],'Documentation audit failed')
    return dict(integrity_passed=True,files_verified=len(expected)+1,promotion_held=True,release_qualification_passed=False,six_hour_soak='pending',final_drift='pending',open_findings=sorted(ISSUES),board_access=False,native_debugging=False)

if __name__=='__main__':
    try:print(json.dumps(verify(),indent=2))
    except (OSError,KeyError,ValueError) as error:raise SystemExit('REFUSED: '+str(error))
