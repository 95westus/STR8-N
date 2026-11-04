"""Seal the RAM-only STATUS evidence and return2609 to its original REC prompt."""
import json,re,hashlib
from pathlib import Path
import install_2512_native_utilities as d
t=d.t
Q=t.ROOT/'output/qualification'
CASE=Q/'STATUS-RAM-closeout-20261031-r1'
def run():
    CASE.mkdir(exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    rows={}
    for board,name in [('2512','2512-STATUS-g1-RAM-20261031-r1'),('2609','2609-STATUS-g1-RAM-20261031-r2')]:
        r=json.loads((Q/name/'report.json').read_text());assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
        rows[board]=dict(RAM_trial=str(Q/name/'report.json'),RAM_sha256=r['RAM_sha256'],ZP_sha256=r['ZP_sha256'])
    prepared=Q/'2512-STATUS-prepared-SRAM-20261031-r1'
    pr=json.loads((prepared/'report.json').read_text());assert pr['owner_RAM_restored'] and pr['owner_ZP_restored']
    raw=(prepared/'WORKBENCH-SRAM.txt').read_bytes();screen=(prepared/'new-VERSION.txt').read_bytes()
    page=re.search(rb'0800 to page ([0-9A-F]{2})',raw);assert page
    boundary=(int(page[1],16) or 256)*256
    expected=(boundary-2048,131072-boundary-32)
    assert f'SSRAM: PROGRAM payload {expected[0]} bytes'.encode() in screen
    assert f'SSRAM: WORKSPACE {expected[1]} bytes'.encode() in screen
    review=dict(passed=True,expected_from_observed_WORKBENCH_page=page[1].decode(),boundary=boundary,
        PROGRAM_payload_bytes=expected[0],WORKSPACE_bytes=expected[1],
        capture_sha256=t.sha(screen),owner_restored=True,additional_board_commands=0,
        correction='The executed host assertion assumed32768 boundary; actual admitted page00 means65536. Captured display matches actual format. Original failed report retained.')
    t.save(prepared/'capacity-review.json',review)
    calendar=json.loads((Q/'2512-STATUS-calendar-RAM-20261031-r2/report.json').read_text())
    assert calendar['passed'] and calendar['owner_RAM_restored'] and calendar['owner_ZP_restored']
    with t.serial_lease('2609-STATUS-restore-original-REC',timeout=30):
        with (CASE/'serial-2609-final.jsonl').open('x') as log:
            s=d.Session(CASE,log,'2609')
            try:
                s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.MON:s.command('Q',(t.REC,))
                assert s.context==t.REC
            finally:s.link.close()
    for board in ('2512','2609'):
        path=Q/f'device-operations/{board}.json';marker=json.loads(path.read_text())
        assert not marker['application_RAM_restore_pending'] and marker['application_ram_restored']
        assert not marker.get('status_worker_active')
        marker.update(last_STATUS_RAM_closeout=str(CASE/'report.json'),final_prompt='B3>' if board=='2512' else 'REC>')
        t.save(path,marker)
    report=dict(passed=True,boards=rows,capacity_review=str(prepared/'capacity-review.json'),
        calendar_cases=8,calendar_report=str(Q/'2512-STATUS-calendar-RAM-20261031-r2/report.json'),
        flash_writes=0,journal_writes=0,F_writes=0,RTC_SET=0,RTC_PF_ACK=0,SRAM_data_writes=0,
        explicit_disabled_VIA_CB_flags_acknowledged_on_2512=True,all_ports_released=True,
        final_prompts={'2512':'B3>','2609':'REC>'},installation_pending=True)
    t.save(CASE/'report.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':run()
