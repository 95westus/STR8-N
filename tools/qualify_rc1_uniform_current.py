"""Qualify only the corrected uniform entry's already-current no-write path.

No fixtures, RAM loaders, reset, flash mutation, native mode or drift sampling.
The ordinary upgrade workflow must independently admit exact current v1g.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
BOARDS={'2604':('COM5','A10MQGVHA'),'2609':('COM8','A10MPQXCA')}
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=BOARDS,required=True)
    a=ap.parse_args();run=a.run.resolve();assert run.is_relative_to(Q)
    source_sha=SHA(__file__);ad=READ(run/'admission-v2.json');auth=READ(run/'owner-authorization.json')
    assert auth['owner_authorized'] and auth['boards']==list(BOARDS)
    assert not auth['native_debugging'] and not auth['RTC_drift_in_release_qualification']
    assert ad['passed'] and SHA(run/'owner-authorization.json')==ad['owner_authorization_sha256']
    for group in ('source_sha256','evidence_sha256'):
        for path,digest in ad[group].items():assert SHA(path)==digest,path
    kit=Path(ad['kit']);sys.path[:0]=[str(kit),str(kit/'engine')]
    import upgrade as u
    assert SHA(kit/'uniform-manifest.json')==ad['uniform_manifest_sha256']
    assert set(READ(Q/'active-rtc-campaign.json')['powered_off_boards'])=={'2205','2512'}
    marker_path=Q/'device-operations'/f'{a.board}.json';marker=READ(marker_path)
    assert marker['soak_owner_stopped'] and marker['RTC_sampling_owner_stopped']
    assert not any(marker.get(k) for k in ('application_RAM_restore_pending','physical_reset_pending',
        'current_soak_worker_pid','register_edit_worker_active','uniform_upgrade_worker_active','block_snapshot'))
    final=READ(run/a.board/'final/report.json')
    assert final['passed'] and final['RAM_restored'] and final['full_RAM_rereads']==2
    exit_proof=READ(run/a.board/'final/process-exit.json')
    assert exit_proof['actual_exit_verified'] and exit_proof['exit_code']==0
    assert exit_proof['source_report_sha256']==SHA(run/a.board/'final/report.json')
    port,usb=BOARDS[a.board];out=run/a.board/'current-v2'
    def state(value):
        marker.update(state='uniform-current-'+value['phase'],uniform_upgrade_run=str(run),
            uniform_upgrade_worker_pid=os.getpid(),uniform_upgrade_worker_active=value['phase'] not in ('completed','completed-no-write','inspection-required'),
            application_RAM_restore_pending=value['application_RAM_restore_pending'],physical_reset_pending=value['physical_reset_pending'],
            block_snapshot=value['phase'] not in ('completed','completed-no-write'),uniform_upgrade_receipt=str(out/'report.json'),
            native_debugging=False,RTC_drift_in_release_qualification=False)
        u.save(marker_path,marker)
    args=argparse.Namespace(port=port,usb_serial=usb,board=a.board,out=out,
        coordination_root=Q/'serial-coordination',reset_timeout=900)
    result=u.run(args,allow_flash=False,qualification=True,on_state=state)
    assert result['passed'] and result['already_current'] and result['action']=='already-current-no-write'
    assert not result['flash_written'] and result['all_four_banks_verified'] and result['application_RAM_unchanged']
    assert not result['physical_reset_pending'] and not result['application_RAM_restore_pending']
    tx=[bytes.fromhex(json.loads(line)['hex']) for line in (out/'serial.jsonl').read_text().splitlines()
        if json.loads(line)['direction']=='TX']
    assert all(body.strip().split(b' ',1)[0] not in (b'L',b'G',b'I',b'U',b'E') for body in tx)
    assert SHA(__file__)==source_sha
    u.save(out/'independent-no-write-audit.json',dict(passed=True,board=a.board,source_sha256=source_sha,
        workflow_report_sha256=SHA(out/'report.json'),no_RAM_loader_or_execution_commands=True,
        no_flash_programming_commands=True,already_current=True,physical_RESET_requested=False,
        native_debugging=False,RTC_drift_in_release_qualification=False,verified_utc=datetime.now(timezone.utc).isoformat()))
    print('PASS',a.board,'corrected uniform entry: exact current v1g; no RAM load/execution, flash/journal write or RESET',flush=True)


if __name__=='__main__':main()
