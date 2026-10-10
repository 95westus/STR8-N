"""Combine the two established donor rate fits for a new-board initial trim."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
from rtc_drift_fit import PPM_PER_STEP, fit_offsets

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--summary', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); summary = json.loads(a.summary.read_text())
    assert summary['passed'] and summary['original_baselines_preserved']
    donors = []
    archived = {sha(f): f for f in (ROOT/'output/qualification').rglob('report.json')}
    for board in ('2205', '2609'):
        b = next(b for b in summary['boards'] if b['board'] == board)
        assert sha(Path(b['report'])) == b['report_sha256']
        report = json.loads(Path(b['report']).read_text())
        baseline = Path(report['compared_baseline'])
        assert sha(baseline) == b['baseline_sha256']
        initial = json.loads(baseline.read_text())
        offsets = [(0, initial['rtc_minus_reference_interval_s'])]
        for sample in b['historical_samples']:
            path = archived[sample['report_sha256']]
            historical = json.loads(path.read_text())
            assert historical['board'] == board and historical['passed']
            assert Path(historical['compared_baseline']).resolve() == baseline.resolve()
            assert all(r['raw'][8] == 0 for r in historical['readings'] if r['status'] == 0)
            offsets.append((historical['elapsed_seconds']/3600, historical['rtc_minus_reference_interval_s']))
        fit = fit_offsets(offsets, b.get('current_trim_steps', 0)); assert fit['available']
        assert abs(fit['slope_ppm']-b['line_fit']['slope_ppm']) < 1e-9
        current = b.get('current_trim_steps', 0)
        # Remove the configured correction to estimate the free-running rate.
        raw_rate = fit['slope_ppm'] - current*PPM_PER_STEP
        raw_bounds = [v-current*PPM_PER_STEP for v in fit['slope_interval_ppm']]
        donors.append(dict(board=board, current_trim_steps=current,
                           free_running_ppm=raw_rate, compatible_rate_bounds_ppm=raw_bounds,
                           offset_sample_count=fit['sample_count'], report_sha256=b['report_sha256']))
    rates = [b['free_running_ppm'] for b in donors]
    mean = statistics.mean(rates)
    bounds = [statistics.mean(b['compatible_rate_bounds_ppm'][i] for b in donors) for i in (0, 1)]
    report = dict(passed=True, target_board='2604', source_summary=str(a.summary.resolve()),
                  source_summary_sha256=sha(a.summary), donors=donors, board_weights=[.5, .5],
                  combined_free_running_ppm=mean, combined_mean_rate_bounds_ppm=bounds,
                  between_board_sample_std_ppm=statistics.stdev(rates),
                  trim_steps=round(-mean/PPM_PER_STEP), ppm_per_step=PPM_PER_STEP,
                  mean_correction_steps_bounds=[round(-v/PPM_PER_STEP) for v in reversed(bounds)],
                  method='Equal weight per donor board fitted rate, then round the pooled continuous correction once. '
                         'Repeated cumulative checkpoints are not treated as independent donor boards. '
                         'Compatible-line bounds are propagated by averaging endpoints; not Gaussian confidence intervals.',
                  limitation='Initial transferred estimate only. Donor mean bounds do not bound an unmeasured third oscillator; '
                             '2604 requires its own post-trim drift observations.', applied=False)
    a.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
