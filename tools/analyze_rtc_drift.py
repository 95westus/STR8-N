"""Run the same baseline-bound, read-only RTC analysis manually or on schedule."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_history_policy import excluded_reports

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT/'output/qualification/rtc-2604-onboarding-2026-10-09/baseline-index.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def active_index():
    pointer=ROOT/'output/qualification/active-rtc-campaign.json'
    if not pointer.exists():return DEFAULT_INDEX
    selected=json.loads(pointer.read_text());path=Path(selected['baseline_index'])
    assert sha(path)==selected['baseline_index_sha256'], 'Active campaign index modified'
    return path


def compatible_histories(index, current, baseline_index=None):
    """Keep unique successful checks from each board's unchanged baseline."""
    originals = {b['board']: b for b in index['boards']}
    seen = set(); accepted = []
    excluded=excluded_reports(baseline_index or active_index())
    for path in sorted((ROOT/'output/qualification').glob('*/summary.json')):
        if path.parent.resolve() == current.resolve(): continue
        try:
            summary = json.loads(path.read_text())
            assert summary['passed'] and summary['original_baselines_preserved']
            keys = []
            for b in summary['boards']:
                original = originals[b['board']]
                report = Path(b['report'])
                assert b['report_sha256'] not in excluded, 'Observation excluded by campaign policy'
                assert sha(report) == b['report_sha256']
                r = json.loads(report.read_text())
                assert r['passed'] and r['mode'] == 'read-only drift measurement'
                assert not r['flash_written'] and not r['trim_changed'] and not r.get('clock_set_attempted', False)
                assert Path(r['compared_baseline']).resolve() == Path(original['baseline_report']).resolve()
                steps = original['trim_steps']; raw = abs(steps) | (0x80 if steps > 0 else 0)
                control = original.get('control_register', 0x80)
                assert all(x['raw'][8] == raw and x['raw'][7] == control for x in r['readings'] if x['status'] == 0)
                key = (b['board'], r['baseline_reference_utc'])
                assert key not in seen
                keys.append(key)
            accepted.append(path); seen.update(keys)
        except (AssertionError, KeyError, ValueError, OSError):
            continue  # Other baselines, failed runs and duplicate summaries are not observations.
    return accepted


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-index', type=Path, default=active_index())
    p.add_argument('--root', type=Path)
    p.add_argument('--server', default='132.163.96.6')
    a = p.parse_args(); index = json.loads(a.baseline_index.read_text()); assert index['passed']
    for b in index['boards']:
        for key in ('sync', 'baseline'):
            assert sha(Path(b[key+'_report'])) == b[key+'_sha256'], 'Baseline modified'
    run = a.root or ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('rtc-residual-drift-%Y-%m-%d-%H%M%SZ')
    run.mkdir(parents=True, exist_ok=False)
    def execute(script, *args):
        result = subprocess.run([sys.executable, str(ROOT/'tools'/script), *map(str, args)],
                                cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True)
        (run/(script+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError(f'{script} failed; evidence retained at {run}:\n{result.stderr[-1500:]}')
        return result
    # Control/trim/identity checks precede the NTP measurements.
    execute('capture_rtc_drift_status.py', '--root', run/'preflight', '--baseline-index', a.baseline_index)
    ports = {p.serial_number: p.device for p in comports()}
    for b in index['boards']:
        board = b['board']; output = run/board
        # Status acquisition already created the board directory; measurement needs a new directory.
        measurement = output/'measurement'
        result = execute('rtc_utc_baseline.py', '--board', board, '--port', ports[SERIALS[board]],
                         '--server', a.server, '--baseline', b['baseline_report'], '--out', measurement)
        (run/f'{board}-measurement.log').write_text(result.stdout+result.stderr)
        # Retain raw acquisition in measurement/, place the plotting report at its standard location.
        (output/'report.json').write_bytes((measurement/'report.json').read_bytes())
    # Recheck every enrolled board after sampling; preflight evidence stays separate.
    execute('capture_rtc_drift_status.py', '--root', run, '--baseline-index', a.baseline_index)
    histories = compatible_histories(index, run, a.baseline_index)
    (run/'history-index.json').write_text(json.dumps(
        [dict(path=str(path), sha256=sha(path)) for path in histories], indent=2)+'\n')
    args = ['--root', run, '--baseline-index', a.baseline_index]
    for path in histories: args.extend(['--history', path])
    execute('plot_rtc_drift.py', *args)
    summary = json.loads((run/'summary.json').read_text()); assert summary['passed']
    print('PASS read-only drift analysis:', run)
    for b in summary['boards']:
        print(b['board'], 'offset', b['utc_offset_seconds'], 'ppm', b['drift_ppm'],
              'current TRIM', b['current_trim_steps'], 'checks', b['statistics']['sample_count'])


if __name__ == '__main__': main()
