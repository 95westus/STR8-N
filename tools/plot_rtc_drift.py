"""Verify preserved baselines and graph read-only RTC drift reports.

Run with --root containing BOARD/report.json for each baseline-index board;
repeat --history for prior comparison summary.json files.
Requires matplotlib. Positive ppm means gaining time against the NTP reference.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import statistics
from rtc_drift_fit import fit_offsets, PPM_PER_STEP
from rtc_history_policy import excluded_reports

ROOT = Path(__file__).resolve().parents[1]
python_tag = f'cp{sys.version_info.major}{sys.version_info.minor}'
# Local compiled wheels belong to the interpreter that installed them.
for plot_deps in (ROOT/f'BUILD/plot-deps-py{sys.version_info.major}{sys.version_info.minor}',
                  ROOT/'BUILD/plot-deps'):
    if plot_deps.is_dir() and any(plot_deps.rglob(f'*.{python_tag}-*.pyd')):
        sys.path.insert(0, str(plot_deps))
        break
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--history', action='append', default=[], type=Path)
    p.add_argument('--baseline-index', type=Path, help='Calibrated baseline index; defaults to original zero-trim baselines')
    a = p.parse_args()
    baseline_index = a.baseline_index or ROOT / 'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json'
    baseline = read(baseline_index)
    excluded=excluded_reports(baseline_index)
    assert baseline['passed']
    boards, histories, rate_samples = [], {}, {}
    for b in baseline['boards']:
        for key in ('sync', 'baseline'):
            assert digest(ROOT / b[key + '_report']) == b[key + '_sha256']
        path = a.root / b['board'] / 'report.json'
        assert digest(path) not in excluded, 'Latest report is excluded from this campaign'
        r = read(path)
        assert r['passed'] and r['mode'] == 'read-only drift measurement'
        assert not r['flash_written'] and not r['trim_changed'] and 'set_operation' not in r
        assert r['clock_advanced'] and not r.get('clock_set_attempted', False)
        assert Path(r['compared_baseline']).resolve() == (ROOT / b['baseline_report']).resolve()
        prior = read(ROOT / b['baseline_report'])
        elapsed = r['baseline_reference_unix'] - prior['baseline_reference_unix']
        low, high = r['rtc_minus_reference_interval_s']
        change = [low - prior['rtc_minus_reference_interval_s'][1],
                  high - prior['rtc_minus_reference_interval_s'][0]]
        ppm = [v / elapsed * 1e6 for v in change]
        assert r['elapsed_seconds'] == elapsed and r['drift_seconds_interval'] == change
        assert r['drift_ppm_interval'] == ppm
        status = read(a.root / b['board'] / 'status-check.json')
        current_trim = b.get('trim_steps', 0)
        expected_raw = abs(current_trim) | (0x80 if current_trim > 0 else 0)
        assert status['passed'] and status['trim_register'] == expected_raw
        control = b.get('control_register', 0x80)
        assert not control & 0x7F and status['control_register'] == control, 'Normal trim/coarse OFF required for recommendation'
        assert all(item['raw'][8] == expected_raw for item in prior['readings'] if item['status'] == 0)
        assert all(item['raw'][8] == expected_raw for item in r['readings'] if item['status'] == 0)
        midpoint = statistics.mean(ppm)
        adjustment = round(-midpoint / PPM_PER_STEP)
        trim = current_trim + adjustment
        row = dict(board=b['board'], reference_utc=r['baseline_reference_utc'],
                   elapsed_hours=elapsed / 3600, utc_offset_seconds=[low, high],
                   drift_seconds=change, drift_ppm=ppm,
                   drift_seconds_per_day=r['drift_seconds_per_day_interval'],
                   trim_register=status['trim_register'], current_trim_steps=current_trim, report=str(path.resolve()),
                   report_sha256=digest(path), baseline_sha256=b['baseline_sha256'])
        row['measurement_uncertainty'] = {
            key: dict(midpoint=statistics.mean(bounds), half_width=(bounds[1] - bounds[0]) / 2,
                      interval=bounds)
            for key, bounds in [('utc_offset_seconds', [low, high]),
                                ('drift_seconds', change), ('drift_ppm', ppm),
                                ('drift_seconds_per_day', r['drift_seconds_per_day_interval'])]}
        row['measurement_uncertainty'].update(
            ntp_reference_seconds=r['reference_uncertainty_s'],
            baseline_ntp_reference_seconds=prior['reference_uncertainty_s'],
            method='Midpoint +/- half interval width: measurement bounds, not a statistical confidence level. '
                   'RTC quantization, serial read brackets and NTP reference uncertainty are included; '
                   'drift also includes original baseline uncertainty.')
        row['recommended_trim'] = dict(steps=trim, command=f'TRIM {trim:+d}',
            basis_ppm_midpoint=midpoint, ppm_per_step=1.0172526, applied=False,
            basis_ppm_uncertainty_half_width=(ppm[1] - ppm[0]) / 2,
            correction_steps_interval=[round(-ppm[1] / 1.0172526), round(-ppm[0] / 1.0172526)],
            current_trim_steps=current_trim, trim_adjustment_steps=adjustment,
            predicted_residual_ppm_interval=[v + adjustment * PPM_PER_STEP for v in ppm],
            note='Absolute recommendation adjusts existing trim using the measured residual slope. Recommendation only.')
        row['recommended_trim']['correction_steps_interval'] = [current_trim + round(-v / PPM_PER_STEP) for v in reversed(ppm)]
        boards.append(row)
        histories[b['board']] = [(0, prior['rtc_minus_reference_interval_s'])]
        rate_samples[b['board']] = {r['baseline_reference_utc']: dict(
            reference_utc=r['baseline_reference_utc'], elapsed_hours=elapsed / 3600,
            ppm_interval=ppm, ppm_midpoint=statistics.mean(ppm),
            utc_offset_midpoint_s=statistics.mean([low, high]), report_sha256=digest(path))}
    for path in a.history:
        history = read(path)
        assert history['passed'] and history['original_baselines_preserved']
        for b in history['boards']:
            report = Path(b['report']) if 'report' in b else path.parent / b['board'] / 'report.json'
            if b['report_sha256'] in excluded:continue
            assert digest(report) == b['report_sha256']
            r = read(report)
            assert r['passed'] and r['mode'] == 'read-only drift measurement'
            # Pin historical comparisons to the same original baseline.
            original = next(x for x in baseline['boards'] if x['board'] == b['board'])
            assert Path(r['compared_baseline']).resolve() == (ROOT / original['baseline_report']).resolve()
            assert not r['flash_written'] and not r['trim_changed']
            assert not r.get('clock_set_attempted', False)
            expected_steps = original.get('trim_steps', 0)
            expected_raw = abs(expected_steps) | (0x80 if expected_steps > 0 else 0)
            assert all(item['raw'][8] == expected_raw for item in r['readings'] if item['status'] == 0), 'Historical trim differs from baseline'
            assert r['baseline_reference_utc'] not in rate_samples[b['board']], 'Duplicate measurement'
            histories[b['board']].append((r['elapsed_seconds'] / 3600, r['rtc_minus_reference_interval_s']))
            rate_samples[b['board']][r['baseline_reference_utc']] = dict(
                reference_utc=r['baseline_reference_utc'], elapsed_hours=r['elapsed_seconds'] / 3600,
                ppm_interval=r['drift_ppm_interval'],
                ppm_midpoint=statistics.mean(r['drift_ppm_interval']),
                utc_offset_midpoint_s=statistics.mean(r['rtc_minus_reference_interval_s']),
                report_sha256=digest(report))
    for b in boards:
        samples = sorted(rate_samples[b['board']].values(), key=lambda s: s['reference_utc'])
        b['historical_samples'] = samples
        b['statistics'] = dict(sample_count=len(samples))
        for name, key in [('ppm', 'ppm_midpoint'), ('utc_offset_seconds', 'utc_offset_midpoint_s')]:
            values = [s[key] for s in samples]
            b['statistics'][name] = dict(mean=statistics.mean(values), median=statistics.median(values),
                sample_standard_deviation=statistics.stdev(values) if len(values) > 1 else None)
        b['line_fit'] = fit_offsets(histories[b['board']] + [(b['elapsed_hours'], b['utc_offset_seconds'])], b['current_trim_steps'])
        fit = b['line_fit']
        b['latest_interval_trim_comparison'] = b['recommended_trim']
        if fit['available']:
            steps = fit['recommended_trim_steps']
            b['recommended_trim'] = dict(steps=steps, command=f'TRIM {steps:+d}' if -127 <= steps <= 127 else None, applied=False,
                basis='Fitted absolute UTC offset slope with free initial intercept',
                current_trim_steps=b['current_trim_steps'], trim_adjustment_steps=fit['trim_adjustment_steps'],
                basis_ppm=fit['slope_ppm'], basis_ppm_interval=fit['slope_interval_ppm'],
                correction_steps_interval=fit['correction_steps_interval'], ppm_per_step=PPM_PER_STEP,
                predicted_residual_ppm_interval=fit['predicted_residual_ppm_interval'],
                predictions_after_trim=fit['predictions_after_trim'])
        else:
            b['recommended_trim']['note'] += ' Full-history constant-rate fit unavailable; latest-interval fallback only.'
        if fit['available']:
            low_rate, high_rate = fit['slope_interval_ppm']
            supported = low_rate > 0 or high_rate < 0
            valid_trim = -127 <= b['recommended_trim']['steps'] <= 127
            fit['hardware_trim_supported'] = valid_trim
            b['recommended_trim']['hardware_trim_supported'] = valid_trim
            if not valid_trim:
                b['recommended_trim']['predictions_after_trim'] = []
            b['recommended_trim']['nonzero_residual_supported'] = supported
            b['recommended_trim']['operational_recommendation'] = (
                f"TRIM {b['recommended_trim']['steps']:+d}" if supported and valid_trim
                else f"Retain current TRIM {b['current_trim_steps']:+d}; " +
                     ('slope bounds include zero' if not supported else 'fit exceeds hardware trim range'))
    unavailable=[]
    if not any(b['board']=='2512' for b in boards):
        absent = read(a.root / '2512/status-check.json')
        assert absent['passed'] and absent['rtc_available'] is False
        unavailable=[dict(board='2512',reason='No EDU/RTC or excluded from this campaign')]
    by_board={b['board']:b for b in boards}
    difference=([by_board['2205']['utc_offset_seconds'][0]-by_board['2609']['utc_offset_seconds'][1],
                 by_board['2205']['utc_offset_seconds'][1]-by_board['2609']['utc_offset_seconds'][0]]
                if '2205' in by_board and '2609' in by_board else None)
    summary = dict(passed=True, reference='Fresh NIST NTP 132.163.96.6; final reference checks passed',
                   clock_set=False, trim_changed=False, original_baselines_preserved=True,
                   baseline_index_sha256=digest(baseline_index), boards=boards,
                   unavailable_boards=unavailable,
                   board_2205_minus_2609_seconds=difference,
                   ppm_formula='(current offset - baseline offset) / elapsed seconds * 1000000',
                   uncertainty='Ranges include RTC one-second quantization, serial acquisition brackets and NTP reference uncertainty; not statistical confidence intervals.',
                   comparison_note='Boards sampled sequentially. Midpoints are visual guides, not separately measured exact rates.')
    summary['statistics_method'] = ('Unweighted descriptive statistics of verified historical measurement interval midpoints, '
        'including the latest reading and excluding the initial baseline. Sample standard deviation uses n-1. '
        'Cumulative ppm estimates share a baseline and are correlated; this standard deviation is not oscillator jitter or reference uncertainty.')
    (a.root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (a.root / 'residuals.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['board', 'elapsed_hours', 'offset_midpoint_s', 'fitted_offset_s', 'residual_s', 'residual_low_s', 'residual_high_s'])
        for b in boards:
            for r in b['line_fit'].get('residuals', []):
                writer.writerow([b['board'], r['elapsed_hours'], r['offset_midpoint_s'], r['fitted_offset_s'],
                                 r['residual_s'], *r['residual_interval_s']])
    with (a.root / 'trim-predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['board', 'trim_steps', 'horizon_hours', 'additional_error_s', 'additional_error_low_s',
                         'additional_error_high_s', 'total_utc_offset_low_s', 'total_utc_offset_high_s'])
        for b in boards:
            fit = b['line_fit']
            for prediction in (fit.get('predictions_after_trim', []) if fit.get('hardware_trim_supported', False) else []):
                writer.writerow([b['board'], fit['recommended_trim_steps'], prediction['horizon_hours'],
                                 prediction['additional_error_seconds'], *prediction['additional_error_interval_s'],
                                 *prediction['total_utc_offset_interval_s']])
    with (a.root / 'measurements.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['board', 'reference_utc', 'elapsed_hours', 'offset_low_s', 'offset_high_s',
                         'drift_low_s', 'drift_high_s', 'ppm_low', 'ppm_high', 'seconds_per_day_low', 'seconds_per_day_high'])
        for b in boards:
            writer.writerow([b['board'], b['reference_utc'], b['elapsed_hours'], *b['utc_offset_seconds'],
                             *b['drift_seconds'], *b['drift_ppm'], *b['drift_seconds_per_day']])
        if unavailable:writer.writerow(['2512', 'RTC unavailable'])
    with (a.root / 'uncertainty.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['board', 'quantity', 'midpoint', 'uncertainty_half_width', 'low', 'high'])
        for b in boards:
            for key in ('utc_offset_seconds', 'drift_seconds', 'drift_ppm', 'drift_seconds_per_day'):
                u = b['measurement_uncertainty'][key]
                writer.writerow([b['board'], key, u['midpoint'], u['half_width'], *u['interval']])
    with (a.root / 'statistics.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['board', 'quantity', 'n', 'mean', 'median', 'sample_standard_deviation'])
        for b in boards:
            for key in ('ppm', 'utc_offset_seconds'):
                s = b['statistics'][key]
                writer.writerow([b['board'], key, b['statistics']['sample_count'],
                                 s['mean'], s['median'], s['sample_standard_deviation']])
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, grid = plt.subplots(2, 2, figsize=(14, 10))
    axes = grid.flatten()
    colors = {'2205': '#1976b9', '2609': '#d36518', '2604': '#39834c', '2512': '#8659b4'}
    for b in boards:
        history = sorted(histories[b['board']] + [(b['elapsed_hours'], b['utc_offset_seconds'])])
        xs = [x[0] for x in history]
        ys = [(x[1][0] + x[1][1]) / 2 for x in history]
        errors = [(x[1][1] - x[1][0]) / 2 for x in history]
        axes[0].errorbar(xs, ys, yerr=errors, fmt='o-', capsize=5, color=colors[b['board']],
                         label='Board ' + b['board'], lw=1.8, markersize=6)
        if b['line_fit']['available']:
            fit = b['line_fit']['fitted_points']
            axes[0].plot([p['elapsed_hours'] for p in fit], [p['fitted_offset_s'] for p in fit],
                         '--', color=colors[b['board']], lw=1.4)
    axes[0].set(xlabel='Hours since each board\'s selected baseline', ylabel='RTC minus NIST UTC (seconds)',
                title='Measured UTC offset over time')
    axes[0].legend(loc='upper left', frameon=False)
    for ax, key, title, label in zip(axes[1:3], ['drift_seconds', 'drift_ppm'],
                                    ['Latest accumulated drift', 'Latest average drift rate'],
                                    ['Change since baseline (seconds)', 'Parts per million (ppm)']):
        for index, b in enumerate(boards):
            low, high = b[key]
            ax.errorbar((low + high) / 2, index, xerr=(high - low) / 2,
                        fmt='o', capsize=8, color=colors[b['board']], lw=3, markersize=7)
            ax.annotate(f'{(low + high) / 2:+.2f} +/- {(high - low) / 2:.2f}\n'
                        f'[{low:+.2f} to {high:+.2f}]', ((low + high) / 2, index),
                        xytext=(0, 18), textcoords='offset points', ha='center', fontweight='bold')
        ax.set(yticks=list(range(len(boards))), yticklabels=[b['board'] for b in boards],
               ylim=(-1.0, len(boards)-.4), xlabel=label, title=title)
        ax.invert_yaxis()
        ax.margins(x=.25)
    for ax in axes[:3]:
        ax.axvline(0, color='#7e8791', ls='--', lw=1) if ax != axes[0] else ax.axhline(0, color='#7e8791', ls='--', lw=1)
        ax.grid(axis='both', alpha=.18)
        ax.set_axisbelow(True)
    axes[3].axis('off')
    axes[3].set_title('Historical ppm midpoint statistics', pad=20)
    rows = []
    for b in boards:
        s = b['statistics']['ppm']
        rows.append([b['board'], str(b['statistics']['sample_count']), f"{s['mean']:.2f}",
                     f"{s['median']:.2f}", f"{s['sample_standard_deviation']:.2f}" if s['sample_standard_deviation'] is not None else 'N/A',
                     str(b['recommended_trim']['steps']) if b['recommended_trim'].get('nonzero_residual_supported') and b['recommended_trim'].get('hardware_trim_supported')
                     else f"Keep {b['current_trim_steps']}"])
    table = axes[3].table(cellText=rows, colLabels=['Board', 'n', 'Mean', 'Median', 'Std dev', 'Action*'],
                          colWidths=[.15,.08,.17,.17,.21,.22], cellLoc='center', bbox=[.04, .38, .92, .42])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#d4dae1')
        if row == 0:
            cell.set_facecolor('#eaf0f6')
            cell.set_text_props(weight='bold')
    axes[3].text(.5, .20, 'Units: ppm. Equal weight per historical check; latest check included.\n'
                 'Sample std dev (n-1); baseline excluded.\n'
                 'Shared-baseline estimates are correlated. Std dev is not clock jitter.\n'
                 '*Retain trim when bounds include zero or proposal exceeds hardware range.',
                 ha='center', va='center', transform=axes[3].transAxes, fontsize=10, color='#505963')
    times = ' | '.join(f"{b['board']}: {b['reference_utc'][:19].replace('T', ' ')} UTC ({b['elapsed_hours']:.2f} h)" for b in boards)
    fig.suptitle('STR8-N board clock drift against NIST UTC', fontsize=21, fontweight='bold', y=.98)
    fig.text(.5, .935, times, ha='center', fontsize=10)
    fig.text(.04, .055, 'Positive ppm = gaining time. +/- values are half-width measurement bounds, not standard deviations. No clock or trim adjustment.', fontsize=10)
    fig.text(.04, .028, 'Bounds include RTC resolution, serial timing and NTP uncertainty. Boards sampled sequentially.'+(' Board 2512: RTC unavailable/excluded.' if unavailable else ''), fontsize=10, color='#505963')
    fig.subplots_adjust(left=.08, right=.97, top=.86, bottom=.13, wspace=.3, hspace=.48)
    fig.savefig(a.root / 'clock-drift.png', dpi=180, facecolor='white')
    fig.savefig(a.root / 'clock-drift.svg', facecolor='white')
    plt.close(fig)
    fig, grid = plt.subplots(2, 2, figsize=(14, max(10, 5*len(boards))))
    ax = grid.flatten()
    fit_labels = []
    for b in boards:
        fit = b['line_fit']
        if not fit['available']:
            fit_labels.append(f"{b['board']}: {fit['reason']}")
            continue
        color = colors[b['board']]
        pts = fit['fitted_points']; rs = fit['residuals']
        xs = [p['elapsed_hours'] for p in pts]
        ax[0].fill_between(xs, [p['fitted_offset_interval_s'][0] for p in pts],
                           [p['fitted_offset_interval_s'][1] for p in pts], color=color, alpha=.18)
        ax[0].plot(xs, [p['fitted_offset_s'] for p in pts], color=color, label=b['board'])
        ax[0].scatter(xs, [r['offset_midpoint_s'] for r in rs], color=color, s=20)
        ax[1].errorbar(xs, [r['residual_s'] for r in rs],
                       yerr=[[r['residual_s']-r['residual_interval_s'][0] for r in rs],
                             [r['residual_interval_s'][1]-r['residual_s'] for r in rs]],
                       fmt='o', capsize=3, color=color, label=b['board'])
        if not fit.get('hardware_trim_supported', False):
            low, high = fit['slope_interval_ppm']
            fit_labels.append(f"Board {b['board']} ({fit['sample_count']} offsets, baseline included)\n"
                f"Slope {fit['slope_ppm']:+.2f} ppm [{low:+.2f}, {high:+.2f}]\n"
                f"Insufficient precision for a hardware trim proposal.\nRetain current TRIM {b['current_trim_steps']:+d}.")
            continue
        preds = fit['predictions_after_trim']
        days = [0]+[p['horizon_hours']/24 for p in preds]
        ax[2].plot(days, [0]+[p['additional_error_seconds'] for p in preds], color=color,
                   label=f"{b['board']} nominal TRIM {fit['recommended_trim_steps']:+d}")
        ax[2].fill_between(days, [0]+[p['additional_error_interval_s'][0] for p in preds],
                           [0]+[p['additional_error_interval_s'][1] for p in preds], color=color, alpha=.18)
        low, high = fit['slope_interval_ppm']
        daily = preds[0]['additional_error_interval_s']
        fit_labels.append(f"Board {b['board']} ({fit['sample_count']} offsets, baseline included)\n"
            f"Slope {fit['slope_ppm']:+.2f} ppm [{low:+.2f}, {high:+.2f}]\n"
            f"Residual RMSE {fit['residual_rmse_seconds']:.3f} s; max {fit['max_absolute_residual_seconds']:.3f} s\n"
            f"Nominal TRIM {fit['recommended_trim_steps']:+d}; next-day added error [{daily[0]:+.3f}, {daily[1]:+.3f}] s")
        if fit['slope_interval_ppm'][0] <= 0 <= fit['slope_interval_ppm'][1]:
            fit_labels[-1] += f"\nRetain current TRIM {b['current_trim_steps']:+d}: bounds include zero."
        if fit['sample_count'] == 2:
            fit_labels[-1] += '\nTwo-point fit: zero residuals are automatic.\nThey do not demonstrate clock stability.'
    ax[0].set(title='Fitted UTC offset and compatible-line envelope', xlabel='Hours since baseline', ylabel='RTC minus UTC (seconds)')
    ax[1].set(title='Residuals with reading measurement bounds', xlabel='Hours since baseline', ylabel='Measured midpoint minus fit (seconds)')
    ax[2].set(title='Hypothetical additional error after nominal trim proposal', xlabel='Days after trim', ylabel='Added clock error (seconds)')
    if not any(b['line_fit'].get('available') and b['line_fit'].get('hardware_trim_supported') for b in boards):
        ax[2].text(.5,.5,'No hardware-supported trim proposal yet.\nContinue collecting; retain current trims.',ha='center',va='center',transform=ax[2].transAxes)
    for panel in ax[:3]:
        panel.grid(alpha=.2);panel.legend(frameon=False)
    ax[1].axhline(0, color='gray', ls='--', lw=1)
    ax[2].axhline(0, color='gray', ls='--', lw=1)
    ax[3].axis('off');ax[3].text(.03,.9,'\n\n'.join(fit_labels),va='top',fontsize=10 if len(boards) > 2 else 11,transform=ax[3].transAxes)
    fig.suptitle('STR8-N drift calibration: fitted slope, residuals and trim prediction', fontsize=18, fontweight='bold', y=.97)
    fig.text(.04,.065,'Bounds span constant-rate lines compatible with every measured offset interval; no Gaussian-error or confidence-level assumption.',fontsize=10)
    fig.text(.04,.035,'Predictions assume unchanged rate/temperature. Added error excludes the existing UTC offset. Trim recommendations have not been applied.',fontsize=10)
    fig.subplots_adjust(left=.08,right=.97,top=.86,bottom=.15,wspace=.3,hspace=.45)
    fig.savefig(a.root/'calibration-fit.png',dpi=180,facecolor='white')
    fig.savefig(a.root/'calibration-fit.svg',facecolor='white')
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
