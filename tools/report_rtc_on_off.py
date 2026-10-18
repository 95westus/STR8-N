"""Add a power-state timeline and ppm comparison to an offline campaign report."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from plot_rtc_drift import plt
import matplotlib.dates as dates

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo('America/Chicago')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    out = parser.parse_args().out
    report = json.loads((out / 'report.json').read_text())
    active = json.loads((ROOT / 'output/qualification/active-rtc-campaign.json').read_text())
    index = Path(active['baseline_index'])
    assert hashlib.sha256(index.read_bytes()).hexdigest() == active['baseline_index_sha256']
    baseline = json.loads(index.read_text())
    events = [json.loads(line) for line in (out / 'power-events-at-report.jsonl').read_text().splitlines() if line.strip()]
    now = datetime.now(timezone.utc)
    rows = []
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), layout='constrained')
    rate_rows = []
    for i, board in enumerate(('2205', '2512', '2604', '2609')):
        base = next(b for b in baseline['boards'] if b['board'] == board)
        bp = Path(base['baseline_report'])
        assert hashlib.sha256(bp.read_bytes()).hexdigest() == base['baseline_sha256']
        initial = json.loads(bp.read_text())
        start = datetime.fromtimestamp(initial['baseline_reference_unix'], timezone.utc)
        board_events = sorted([e for e in events if e.get('board') == board], key=lambda e: e['recorded_utc'])
        cursor, state = start, 'ON'
        for event in board_events:
            new_state = ('OFF' if event['event'] in ('power_off_announced', 'controlled_power_off_user_confirmed') else
                         'ON' if event['event'] in ('power_on_announced', 'controlled_power_on_user_confirmed') else None)
            if new_state is None:
                continue
            when = datetime.fromisoformat(event['recorded_utc'])
            axes[0].plot([cursor, when], [i, i], lw=13, color='#1f8a70' if state == 'ON' else '#d9a441', solid_capstyle='butt')
            cursor, state = when, new_state
        assert (state == 'OFF') == (board in active['powered_off_boards'])
        axes[0].plot([cursor, now], [i, i], lw=13, color='#1f8a70' if state == 'ON' else '#d9a441', solid_capstyle='butt')
        data = report['boards'].get(board)
        if data:
            axes[0].scatter([datetime.fromtimestamp(o['reference_unix'], timezone.utc) for o in data['observations']], [i]*len(data['observations']), marker='|', s=220, color='#132b40', zorder=3)
            if board == '2512':
                first, last = data['observations'][0], data['observations'][-1]
                span = last['reference_unix'] - first['reference_unix']
                bounds = [last['rate_low_ppm'], last['rate_high_ppm']]
                samples = len(data['observations'])
            else:
                segment = data['powered_on_since_return']
                bounds = segment['mean_rate_interval_ppm']
                span, samples = segment['elapsed_hours']*3600, segment['samples']
            if bounds:
                rate_rows.append((board, bounds))
                rows.append(dict(board=board, reported_state=state, mode='ON', hours=span/3600, samples=samples,
                                 midpoint_ppm=sum(bounds)/2, low_ppm=bounds[0], high_ppm=bounds[1],
                                 low_seconds_day=bounds[0]*.0864, high_seconds_day=bounds[1]*.0864,
                                 last_measurement_local=data['latest']['local_time'], off_rate_available=False))
        else:
            axes[0].scatter([start], [i], marker='|', s=220, color='#132b40', zorder=3)
            rows.append(dict(board=board, reported_state=state, mode='ON', hours=0, samples=1,
                             midpoint_ppm=None, low_ppm=None, high_ppm=None, low_seconds_day=None,
                             high_seconds_day=None, last_measurement_local=start.astimezone(ZONE).isoformat(), off_rate_available=False))
    axes[0].set_yticks(range(4), ['2205 · OFF', '2512 · OFF', '2604 · ON', '2609 · ON'])
    axes[0].invert_yaxis()
    axes[0].xaxis.set_major_formatter(dates.DateFormatter('%m-%d\n%H:%M', tz=ZONE))
    axes[0].set_title('Reported power history: green ON, amber OFF; vertical ticks = RTC samples')
    axes[0].set_xlabel('America/Chicago · reported switch times are approximate')
    for i, (board, bounds) in enumerate(rate_rows):
        mid = sum(bounds)/2
        axes[1].errorbar(mid, i, xerr=[[mid-bounds[0]], [bounds[1]-mid]], fmt='o', capsize=6, color='#176a95')
        axes[1].annotate(f'  {mid:+.2f} [{bounds[0]:+.2f}, {bounds[1]:+.2f}]', (bounds[1], i), fontsize=9, va='center')
    axes[1].set_yticks(range(len(rate_rows)), [b for b, _ in rate_rows])
    axes[1].invert_yaxis()
    axes[1].axvline(0, color='gray', ls='--')
    axes[1].grid(axis='x', alpha=.2)
    axes[1].margins(x=.5)
    axes[1].set_title('Powered-on endpoint rates · 2512 before shutdown; 2604/2609 after latest return')
    axes[1].set_xlabel('ppm · positive = gaining · acquisition bounds, not confidence intervals')
    fig.suptitle('RTC on/off drift analysis · original baseline preserved')
    for ext in ('png', 'svg'):
        fig.savefig(out / f'on-off-summary.{ext}', dpi=160)
    plt.close(fig)
    with (out / 'on-off-rates.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = dict(generated_local=now.astimezone(ZONE).isoformat(), hardware_accessed=False, rates=rows,
                  off_rate_available=False, conclusion='All powered-on rate bounds include zero. Current off intervals lack return observations. Earlier baseline-to-return rates mix power states and cannot isolate off-state drift.',
                  method='Endpoint rate bounds: [(last low - first high)/elapsed, (last high - first low)/elapsed] times 1e6. One ppm is 0.0864 seconds/day. Power state is user reported; temperature, firmware and workload effects are not isolated.')
    (out / 'on-off-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    table = ''.join(f'<tr><td>{r["board"]}</td><td>{r["reported_state"]}</td><td>{r["hours"]:.2f}</td><td>'+('Unavailable' if r['midpoint_ppm'] is None else f'{r["midpoint_ppm"]:+.2f} [{r["low_ppm"]:+.2f}, {r["high_ppm"]:+.2f}]')+'</td></tr>' for r in rows)
    (out / 'on-off.html').write_text('<!doctype html><meta charset="utf-8"><title>RTC on/off drift</title><style>body{font:17px system-ui;max-width:1150px;margin:35px auto;padding:20px;color:#172b3a}img{width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}p{line-height:1.6}</style><h1>RTC on/off drift analysis</h1><p>'+html.escape(result['generated_local'])+'</p><p>'+html.escape(result['conclusion'])+'</p><img src="on-off-summary.png"><table><tr><th>Board</th><th>Reported state</th><th>ON sample span (h)</th><th>ON ppm midpoint [bounds]</th></tr>'+table+'</table><p>'+html.escape(result['method'])+'</p><p>Measurements are historical and sequential; the timeline extends reported power state to report generation without implying additional RTC readings. No hardware accessed.</p><p><a href="report.html">Detailed drift and offset charts</a> · <a href="on-off-rates.csv">Rate data</a></p>', encoding='utf-8')
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != 'on-off-manifest.json'}
    (out / 'on-off-manifest.json').write_text(json.dumps(dict(files=files, generators=[str(ROOT/'tools/report_rtc_powered_campaign.py'),str(Path(__file__).resolve())]), indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
