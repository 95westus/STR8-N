"""Offline, reset-aware comparison of recorded RTC power intervals.

No serial access or device writes. Keep zero-trim historical power intervals
separate from current-trim observations and never fit across a recorded SET.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import statistics

from rtc_drift_fit import fit_offsets

ROOT = Path(__file__).resolve().parents[1]
BOARDS = ('2205', '2604', '2609')
RESYNC = ROOT / 'output/qualification/rtc-ntp-resync-2026-10-14-210633Z'
SOAK = ROOT / 'output/qualification/beta25-rst-soak-2026-10-14'
LATEST = ROOT / 'output/qualification/rtc-short-2205-2604-2609-2026-10-16-120022'


def epoch(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def difference(first, last):
    seconds = last['baseline_reference_unix'] - first['baseline_reference_unix']
    assert seconds > 0
    low, high = first['rtc_minus_reference_interval_s']
    end_low, end_high = last['rtc_minus_reference_interval_s']
    bounds = [(end_low - high) / seconds * 1e6, (end_high - low) / seconds * 1e6]
    return dict(hours=seconds / 3600, ppm=bounds, seconds_per_day=[v * .0864 for v in bounds])


def main(out):
    sources = {}

    def read(path):
        sources[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())

    def observation(path, board, trim):
        r = read(path)
        assert r['passed'] and r['board'] == board and not r['flash_written'] and not r['trim_changed']
        valid = [v for v in r['readings'] if v['status'] == 0]
        assert valid and all(v['raw'][8] == trim for v in valid)
        assert not r.get('clock_set_attempted', False) or path.parent.parent == RESYNC
        return r

    # Historical near-matched power comparison, at TRIM 0 on both sides.
    pre = read(ROOT / 'output/qualification/rtc-residual-drift-2026-10-11-033931Z/summary.json')
    post = read(ROOT / 'output/qualification/rtc-residual-drift-2026-10-11-121944Z/summary.json')
    mains = read(ROOT / 'output/qualification/rtc-residual-drift-2026-10-11-203425Z/summary.json')
    assert pre['passed'] and post['passed'] and mains['passed']
    assert pre['baseline_index_sha256'] == post['baseline_index_sha256'] == mains['baseline_index_sha256']
    off = epoch('2026-10-10T23:00:00-05:00')
    on = epoch('2026-10-11T07:17:00-05:00')
    historical = []
    for board in BOARDS:
        rows = [next(b for b in s['boards'] if b['board'] == board) for s in (pre, post, mains)]
        raw = []
        for row in rows:
            assert row['current_trim_steps'] == 0
            p = Path(row['report'])
            assert hashlib.sha256(p.read_bytes()).hexdigest() == row['report_sha256']
            raw.append(observation(p, board, 0))
        a, b, c = raw
        ta, tb = a['baseline_reference_unix'], b['baseline_reference_unix']
        assert ta < off < on < tb
        tails = off - ta + tb - on
        delta = [b['rtc_minus_reference_interval_s'][0] - a['rtc_minus_reference_interval_s'][1],
                 b['rtc_minus_reference_interval_s'][1] - a['rtc_minus_reference_interval_s'][0]]
        prior_fit = rows[0]['line_fit']
        assert prior_fit['available']
        low, high = prior_fit['slope_interval_ppm']
        battery = [(delta[0] - tails * high / 1e6) / (on - off) * 1e6,
                   (delta[1] - tails * low / 1e6) / (on - off) * 1e6]
        main_bounds = difference(b, c)
        diff = [main_bounds['ppm'][0] - battery[1], main_bounds['ppm'][1] - battery[0]]
        historical.append(dict(board=board, trim_steps=0, battery_hours=(on-off)/3600,
                               powered_tails_minutes=tails/60, battery_ppm=battery,
                               main_hours=main_bounds['hours'], main_ppm=main_bounds['ppm'],
                               main_minus_battery_ppm=diff, difference_includes_zero=diff[0] <= 0 <= diff[1]))

    current = []
    for board, trim in [('2205', 17), ('2604', 12), ('2609', 14)]:
        start = observation(RESYNC / board / 'report.json', board, trim)
        assert start['clock_set_attempted'] and start['mode'] == 'UTC sync'
        last = observation(LATEST / board / 'measurement/report.json', board, trim)
        paths = [RESYNC / board / 'report.json', LATEST / board / 'measurement/report.json',
                 ROOT / f'output/qualification/rtc-all-ntp-20261015-033154Z/{board}/report.json',
                 ROOT / f'output/qualification/rtc-current-offset-2026-10-16-095707Z/{board}/report.json',
                 SOAK / f'drift/baseline/{board}/report.json']
        paths += list((SOAK / 'drift').glob(f'snapshot-*/{board}/report.json'))
        points = {}
        for p in paths:
            if p.exists():
                r = observation(p, board, trim)
                assert r['baseline_reference_unix'] >= start['baseline_reference_unix']
                points[r['baseline_reference_unix']] = r
        fit = fit_offsets([((t-start['baseline_reference_unix'])/3600, r['rtc_minus_reference_interval_s'])
                           for t, r in sorted(points.items())], current_trim_steps=-trim)
        powered_paths = [SOAK / f'drift/baseline/{board}/report.json']
        powered_paths += sorted((SOAK / 'drift').glob(f'snapshot-*/{board}/report.json'))
        powered = [observation(p, board, trim) for p in powered_paths if p.exists()]
        powered = sorted(powered, key=lambda r:r['baseline_reference_unix'])
        main_fit = None
        if len(powered) > 1:
            anchor = powered[0]['baseline_reference_unix']
            main_fit = fit_offsets([((r['baseline_reference_unix']-anchor)/3600, r['rtc_minus_reference_interval_s'])
                                    for r in powered], current_trim_steps=-trim)
        history_path = out / board / 'history.txt'
        assert history_path.exists(), 'Read-only history evidence missing'
        sources[str(history_path.resolve())] = hashlib.sha256(history_path.read_bytes()).hexdigest()
        text = history_path.read_bytes().decode().replace('\r','')
        outages = re.findall(r'Power down: (\d\d-\d\d \d\d:\d\d)\s+Power up:\s+(\d\d-\d\d \d\d:\d\d)', text)
        assert outages, 'No timestamped outage in retained history'
        down, up = [datetime.strptime('2026-'+v,'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc).timestamp() for v in outages[0]]
        assert start['baseline_reference_unix'] < down < up < last['baseline_reference_unix']
        before = max((r for t,r in points.items() if t < down),key=lambda r:r['baseline_reference_unix'])
        after = min((r for t,r in points.items() if t > up),key=lambda r:r['baseline_reference_unix'])
        recent_outage = dict(displayed_down_utc=outages[0][0], displayed_up_utc=outages[0][1],
                             displayed_duration_minutes=(up-down)/60,
                             duration_minutes_from_minute_resolution=[(up-down)/60-1,(up-down)/60+1],
                             nearest_before_utc=before['baseline_reference_utc'],nearest_after_utc=after['baseline_reference_utc'],
                             mixed_observation_gap=difference(before,after),
                             displayed_main_power_tail_hours=((down-before['baseline_reference_unix'])+(after['baseline_reference_unix']-up))/3600)
        current.append(dict(board=board, trim_steps=-trim, resync_utc=start['baseline_reference_utc'],
                            latest_utc=last['baseline_reference_utc'], endpoint_average=difference(start,last),
                            post_resync_fit=fit, current_trim_powered_soak_fit=main_fit,
                            powered_soak_samples=len(powered),
                            powered_soak_hours=(powered[-1]['baseline_reference_unix']-powered[0]['baseline_reference_unix'])/3600,
                            recent_recorded_battery_interval=recent_outage,
                            separate_current_trim_battery_rate_available=False,
                            battery_limitation='No NTP observations closely bracket the recorded recent battery intervals; do not label a mixed gap battery-only.'))

    result = dict(passed=True, hardware_settings_changed=False, trims_changed=False,
                  old_oct11_to_oct16_drift_invalid=True,
                  correction='UTC SET receipts on October 14 split the campaign. The prior October 11-to-16 negative rates and failed single-line fits cross those SETs and cannot measure drift.',
                  historical_power_comparison=historical, current_trim_comparison=current,
                  interpretation='Historical power-mode difference bounds include zero for every board. Corrected post-resync fits are feasible and include zero slope. Existing observations do not establish a battery-versus-main effect.',
                  limits=['Historical matched power observations use TRIM 0; keep separate from current negative trims.',
                          'Historical switch times are user-reported and approximate. Unspecified timing error is not in the bounds.',
                          'Powered-tail correction uses a pre-outage fit which itself mixes operating states.',
                          'Recent power timestamps have minute resolution and do not supply missing NTP endpoint observations.',
                          'Temperature and warm-up are not separately measured.',
                          'Bounds are measurement/model compatibility intervals, not statistical confidence intervals.'],
                  datasheet=dict(url='https://ww1.microchip.com/downloads/en/DeviceDoc/MCP79410-MCP79411-MCP79412-Battery-Backed%20I2C-RTCC-20002266J.pdf',
                                 section='5.6, page 30', finding='Digital trimming also occurs on the backup supply.'),
                  sources=sources)
    (out / 'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out / 'power-comparison.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['board','historical_trim','battery_low_ppm','battery_high_ppm','main_low_ppm','main_high_ppm','difference_low_ppm','difference_high_ppm'])
        for r in historical:writer.writerow([r['board'],0,*r['battery_ppm'],*r['main_ppm'],*r['main_minus_battery_ppm']])

    # Reuse the campaign plotter's interpreter-matched local wheel setup.
    from plot_rtc_drift import plt
    fig, axes=plt.subplots(1,2,figsize=(12,5))
    for i,r in enumerate(historical):
        for key,dy,color,label in [('battery_ppm',-.12,'#2878a0','Battery estimate'),('main_ppm',.12,'#b97125','Main-power interval')]:
            bounds=r[key];mid=statistics.mean(bounds)
            axes[0].errorbar(mid,i+dy,xerr=(bounds[1]-bounds[0])/2,fmt='o',capsize=4,color=color,label=label if i==0 else None)
    for i,r in enumerate(current):
        fit=r['post_resync_fit'];assert fit['available']
        bounds=[v*.0864 for v in fit['slope_interval_ppm']]
        axes[1].plot(bounds,[i,i],lw=3,color='#2878a0')
        axes[1].plot(fit['slope_ppm']*.0864,i,'o',color='#2878a0')
    for ax in axes:
        ax.set_yticks(range(3),BOARDS);ax.invert_yaxis();ax.axvline(0,color='gray',ls='--');ax.grid(axis='x',alpha=.25)
    axes[0].set(title='Oct 10–11 power comparison — TRIM 0\n8 h 17 min battery; about 8 h 15 min main',xlabel='Drift ppm (positive = gaining)')
    axes[0].legend(fontsize=9)
    axes[1].set(title='After Oct 14 UTC resync — current trims\nFits use mixed-power observations; not a mode comparison',xlabel='Drift seconds/day (positive = gaining)')
    fig.text(.02,.02,'Measurement/model bounds; temperature and switch-time uncertainty are not isolated. No settings changed.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,1))
    fig.savefig(out/'power-comparison.png',dpi=160)
    fig.savefig(out/'power-comparison.svg')
    plt.close(fig)
    print('PASS reset-aware offline power comparison',out)
    for r in historical:print('historical',r['board'],'battery',r['battery_ppm'],'main',r['main_ppm'],'difference',r['main_minus_battery_ppm'])
    for r in current:print('current',r['board'],'fit',r['post_resync_fit']['slope_interval_ppm'],'main fit',None if not r['current_trim_powered_soak_fit'] else r['current_trim_powered_soak_fit'].get('slope_interval_ppm'))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    main(parser.parse_args().out)
