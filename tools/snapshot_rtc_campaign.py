"""One-shot NTP snapshot; preserve temporary client RAM and persistent settings."""
import hashlib
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from beta4_migration import Link, read_s19
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from serial.tools.list_ports import comports
from rtc_campaign_segments import recovery_segment

def save(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', action='append', choices=tuple(SERIALS))
    args = parser.parse_args()
    campaign = json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
    baseline_path = Path(campaign['baseline_index'])
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == campaign['baseline_index_sha256']
    baselines = {b['board']: b for b in json.loads(baseline_path.read_text())['boards']}
    state=json.loads(Path(campaign['campaign_state']).read_text()) if campaign.get('campaign_state') else {}
    segments={b:recovery_segment(state,b,campaign['baseline_index_sha256']) for b in baselines}
    boards = args.board or [b for b in ('2205','2512','2604','2609') if b not in campaign.get('powered_off_boards', [])]
    assert boards, 'No boards selected'
    # A planned single-board interruption must not suppress the powered-on
    # boards' scheduled measurements. Retain each skipped attempt explicitly.
    blocked=[dict(board=b,reason='User-reported powered off; no port opened')
             for b in boards if b in campaign.get('powered_off_boards', [])]
    boards=[b for b in boards if b not in campaign.get('powered_off_boards', [])]
    for board in list(boards):
        marker=ROOT/'output/qualification/device-operations'/f'{board}.json'
        if marker.exists():
            operation=json.loads(marker.read_text())
            if operation.get('block_snapshot'):
                blocked.append(dict(board=board,reason='Device operation or recovery owns this board',operation=operation));boards.remove(board)
    assert boards, 'Selected board has a pending device operation; no port opened'
    root = ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('rtc-campaign-snapshot-%Y-%m-%d-%H%M%SZ')
    root.mkdir()
    print('SNAPSHOT', root, flush=True)
    cells, _ = read_s19(ROOT/'BUILD/v2-rtc-kernel/utc-client/rtc-sample-client.s19')
    ranges = [(min(cells), max(cells)), (0x2440, 0x247F)]
    summary = dict(passed=False, started_utc=datetime.now(timezone.utc).isoformat(),
                   clock_set=False, trim_changed=False, flash_written=False,
                   outage_duration_analyzed=False, sequential_not_simultaneous=True, boards=[],skipped_boards=blocked)
    save(root/'summary.json',summary)
    # The preserving CPU-RAM pattern unit can take several minutes over USB.
    # Wait for its safe boundary; never interrupt restoration or use stale NTP.
    with serial_lease('drift', timeout=600):
        ports = {p.serial_number:p.device for p in comports()}
        for board in boards:
            # Recheck under the lease: an operation may have registered after
            # the initial selection while this snapshot waited for the soak.
            marker = ROOT/'output/qualification/device-operations'/f'{board}.json'
            if marker.exists():
                operation = json.loads(marker.read_text())
                if operation.get('block_snapshot'):
                    blocked.append(dict(board=board,reason='Device operation registered while awaiting serial lease',operation=operation))
                    save(root/'summary.json',summary)
                    print('SKIP',board,'device operation owns board',flush=True)
                    continue
            port = ports[SERIALS[board]]
            out = root/board
            out.mkdir()
            original = []
            with (out/'preservation-serial.jsonl').open('x') as log:
                link = Link(port, log)
                try:
                    establish_b3(link)
                    (out/'time-before.txt').write_bytes(link.command('TIME'))
                    for first,last in ranges:
                        data = link.dump(first,last)
                        assert data == link.dump(first,last), 'Unstable application RAM'
                        (out/f'ram-{first:04x}-before.bin').write_bytes(data)
                        original.append((first,data))
                finally:
                    link.serial.close()
                result = None
                try:
                    result = subprocess.run([sys.executable,str(ROOT/'tools/rtc_utc_baseline.py'),
                        '--board',board,'--port',port,'--server','132.163.96.6',
                        '--baseline',segments[board]['anchor_report'] if segments[board] else baselines[board]['baseline_report'],
                        '--out',str(out/'measurement')],cwd=ROOT,capture_output=True,text=True)
                    (out/'measurement.log').write_text(result.stdout+result.stderr)
                finally:
                    link = Link(port, log)
                    try:
                        establish_b3(link)
                        for first,data in original:
                            link.write_ram(first,data)
                            actual = link.dump(first,first+len(data)-1)
                            assert actual == data, 'Application RAM restore mismatch'
                            (out/f'ram-{first:04x}-restored.bin').write_bytes(actual)
                        save(out/'preservation.json',dict(passed=True,application_ram_restored=True,
                             ranges=[[first,first+len(data)-1] for first,data in original]))
                    finally:
                        link.serial.close()
                assert result is not None and result.returncode == 0, (board, result.stderr if result else 'no result')
            report_path = out/'measurement/report.json'
            r = json.loads(report_path.read_text())
            assert r['passed'] and not r.get('clock_set_attempted',False)
            low,high = r['rtc_minus_reference_interval_s']
            raw = r['readings'][-1]['raw']
            assert all(x['raw'][7:9] == raw[7:9] for x in r['readings'])
            trim = (raw[8]&127)*(1 if raw[8]&128 else -1)
            assert trim == baselines[board]['trim_steps'] and raw[7] == baselines[board]['control_register'], 'RTC settings differ from baseline'
            item = dict(board=board,usb_serial=SERIALS[board],port=port,
                 reference_utc=r['baseline_reference_utc'],offset_seconds=(low+high)/2,
                 offset_bounds_seconds=[low,high],trim_steps=trim,control_register=raw[7],
                 report=str(report_path),report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
                 application_ram_restored=True)
            item.update(baseline_index=str(baseline_path), elapsed_seconds=r['elapsed_seconds'],
                        drift_seconds_interval=r['drift_seconds_interval'])
            if segments[board]:item.update(measurement_segment=segments[board]['id'],
                comparison_anchor=segments[board]['anchor_report'],original_baseline_replaced=False)
            summary['boards'].append(item)
            save(root/'summary.json',summary)
            print('RESULT',json.dumps(item),flush=True)
    assert summary['boards'], 'Every selected board was skipped; no fresh measurement collected'
    summary.update(passed=True,finished_utc=datetime.now(timezone.utc).isoformat(),ports_released=True)
    save(root/'summary.json',summary)
    print('PASS',root/'summary.json',flush=True)

if __name__ == '__main__':
    main()
