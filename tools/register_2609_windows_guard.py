"""Register the owner-authorized 2609 migration backup, without opening a port."""
import json
from pathlib import Path
from serial_test_coordination import serial_lease
from atomic_json import publish

Q=Path(__file__).resolve().parents[1]/'output/qualification'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))

def main():
    auth=Q/'bf1-2609-windows-migration-owner-authorization-2026-10-18-r1.json'
    assert read(auth)['owner_authorized'] and read(auth)['board']=='2609'
    active=read(Q/'active-rtc-campaign.json')
    assert set(active['powered_off_boards'])=={'2205','2512'}
    state=read(Path(active['campaign_state']));run=Path(state['additional_soak_runs']['2609'])
    status=read(run/'status.json');restore=read(run/'restore-needed.json')
    assert status['state']=='stopped-by-request' and status['application_ram_restored']
    assert not restore['needed'] and restore['verified']
    with serial_lease('register-2609-windows-backup',timeout=600,priority=True):
        marker=Q/'device-operations/2609.json';old=read(marker)
        assert not old.get('block_snapshot'),'Another operation owns 2609'
        publish(marker,dict(board='2609',state='windows-migration-backup-authorized',block_snapshot=True,authorization=str(auth)))
    print('PASS 2609 backup guard registered; no board port opened',flush=True)

if __name__=='__main__':main()
