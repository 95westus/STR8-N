"""Verify this extracted candidate distribution with Python stdlib; no ports."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

def verify(root=ROOT):
    root=Path(root).resolve();manifest=json.loads((root/'package-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('candidate')!='rc1-debugger-v1' or manifest.get('generation')!=50 or manifest.get('native_debugging') is not False:
        raise ValueError('Wrong candidate or scope')
    files=manifest['files'];expected=dict(files)
    data=(root/'package-manifest.json').read_bytes()
    expected['package-manifest.json']=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    checksums={}
    for line in (root/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        if not match or match[2] in checksums:raise ValueError('Invalid/duplicate checksum entry')
        checksums[match[2]]=match[1]
    if set(checksums)!=set(expected):raise ValueError('Checksum inventory differs')
    for name,info in expected.items():
        path=(root/name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root) or '\\' in name:raise ValueError('Unsafe package path')
        body=path.read_bytes();digest=hashlib.sha256(body).hexdigest()
        if len(body)!=info['bytes'] or digest!=info['sha256'] or digest!=checksums[name]:raise ValueError('Changed file: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual!=set(expected)|{'SHA256SUMS.txt'}:raise ValueError('Unexpected or missing package files')
    kit=root/'install';pin=hashlib.sha256((kit/'board-test-manifest.json').read_bytes()).hexdigest()
    if pin!=manifest['tested_board_kit_manifest_sha256']:raise ValueError('Different board-test kit')
    original=json.loads((kit/'board-test-manifest.json').read_text(encoding='utf-8'))
    for name,info in original['files'].items():
        if files.get('install/'+name)!=info:raise ValueError('Board-test kit changed: '+name)
    summary=json.loads((root/'qualification/summary.json').read_text(encoding='utf-8'))
    if not summary['passed'] or summary['native_debugging'] or summary['breakpoint_hits_total']!=64:raise ValueError('Wrong qualification scope')
    for board in ('2604','2609'):
        proof=json.loads((root/f'qualification/boards/{board}.json').read_text(encoding='utf-8'))
        if not proof['passed'] or not proof['both_monitor_slots_passed'] or proof['breakpoint_hits_total']!=32 or not proof['RAM_restored_host_verified']:
            raise ValueError('Incomplete board summary: '+board)
    if manifest.get('distribution_revision')!=2:raise ValueError('Wrong distribution revision')
    soak=json.loads((root/'qualification/soak/summary.json').read_text(encoding='utf-8'))
    drift=json.loads((root/'qualification/soak/drift.json').read_text(encoding='utf-8'))
    if not soak['passed'] or soak['native_debugging'] or soak['native_applications_tested'] or not 28800<=soak['duration_seconds']<28920 or soak['failures']:
        raise ValueError('Incomplete soak qualification')
    if not drift['passed'] or drift['clock_set'] or drift['trim_changed'] or drift['original_baseline_index_sha256']!=soak['original_baseline_index_sha256']:
        raise ValueError('Invalid drift scope/baseline')
    if {b['board'] for b in drift['boards']}!={'2604','2609'}:raise ValueError('Missing drift board')
    for board,slot in (('2604','B'),('2609','A')):
        b=soak['boards'][board]
        if not b['passed'] or b['slot']!=slot or b['passed_cycles']!=431 or b['breakpoint_hits']!=6896 or len(b['cycle_receipt_sha256'])!=431 or not b['RAM_verified_after_snapshot'] or not b['all_four_flash_banks_unchanged']:
            raise ValueError('Invalid soak board: '+board)
    recovery=next(b for b in drift['boards'] if b['board']=='2609')
    if recovery['measurement_segment']!='2609-post-RTC-recovery-2026-10-18-r1' or recovery['original_baseline_replaced']:
        raise ValueError('Recovery comparison segment changed')
    return dict(passed=True,generation=50,distribution_revision=2,files_verified=len(expected)+1,soak_passed=True,final_drift_passed=True,board_access=False,native_debugging=False)

if __name__=='__main__':
    try:print(json.dumps(verify(),indent=2))
    except (OSError,ValueError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))
