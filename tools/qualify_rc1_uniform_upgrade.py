"""Finite, owner-authorized RC1 uniform-upgrade hardware qualification.

No generation49 rollback. The fixture is an exact generation50 v1f image,
followed by the ordinary v1g upgrade command. Flash trials require an explicit
owner authorization receipt plus a sealed passed CPU-model receipt. Current
verification is a separate no-write result, never a physical upgrade claim.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from datetime import datetime,timezone

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BOARDS={'2604':('COM5','A10MQGVHA'),'2609':('COM8','A10MPQXCA')}
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=BOARDS,required=True)
    ap.add_argument('--stage',choices=('current','fixture','upgrade'),required=True);a=ap.parse_args()
    run=a.run.resolve();assert run.is_relative_to(Q)
    auth=READ(run/'owner-authorization.json');assert auth['owner_authorized'] and auth['boards']==list(BOARDS)
    assert auth['native_debugging'] is False and auth['RTC_drift_in_release_qualification'] is False and auth['manual_rollback_through_generation49'] is False
    ad=READ(run/'admission.json');assert ad['passed'] and SHA(run/'owner-authorization.json')==ad['owner_authorization_sha256']
    for path,digest in ad['source_sha256'].items():assert SHA(path)==digest,path
    for path,digest in ad['evidence_sha256'].items():assert SHA(path)==digest,path
    kit=Path(ad['kit']);sys.path[:0]=[str(kit),str(kit/'engine')]
    import upgrade
    assert SHA(kit/'uniform-manifest.json')==ad['uniform_manifest_sha256']
    assert a.board not in READ(Q/'active-rtc-campaign.json')['powered_off_boards']
    if a.stage!='current':
        assert auth['physical_RESET_assistance_confirmed'] and auth['generation50_fixture_authorized']
        assert READ(run/a.board/'current/report.json')['passed'] and READ(run/a.board/'current/report.json')['already_current']
    if a.stage=='upgrade':assert READ(run/a.board/'fixture/report.json')['passed']
    path=Q/'device-operations'/f'{a.board}.json';marker=READ(path)
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not marker.get('application_RAM_restore_pending') and not marker.get('physical_reset_pending') and not marker.get('current_soak_worker_pid')
    assert not marker.get('register_edit_worker_active') and not marker.get('block_snapshot')
    initial=run/f'{a.board}-device-operation-before.json'
    if not initial.exists():upgrade.save(initial,marker)
    port,usb=BOARDS[a.board]
    def state(value):
        marker.update(state='rc1-uniform-'+value['phase'],uniform_upgrade_run=str(run),uniform_upgrade_worker_pid=os.getpid(),
                      uniform_upgrade_worker_active=value['phase'] not in ('completed','completed-no-write','inspection-required'),
                      application_RAM_restore_pending=value['application_RAM_restore_pending'],physical_reset_pending=value['physical_reset_pending'],
                      block_snapshot=value['phase'] not in ('completed','completed-no-write'),native_debugging=False,RTC_drift_in_release_qualification=False,
                      uniform_upgrade_receipt=str(run/a.board/a.stage/'report.json'))
        upgrade.save(path,marker)
    args=argparse.Namespace(port=port,usb_serial=usb,board=a.board,out=run/a.board/a.stage,
        coordination_root=Q/'serial-coordination',reset_timeout=900)
    result=upgrade.run(args,target='v1f' if a.stage=='fixture' else 'v1g',on_state=state,allow_flash=a.stage!='current',qualification=True)
    print(json.dumps(dict(passed=result['passed'],board=a.board,stage=a.stage,action=result['action'],source=result['source_profile'],
                         target=result['target_profile'],flash_written=result['flash_written']),indent=2),flush=True)


if __name__=='__main__':main()
