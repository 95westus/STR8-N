"""Plot saved, accepted RTC campaign evidence. Never opens a board or network port."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
try:
    import matplotlib
except ModuleNotFoundError:
    for folder in (ROOT / 'tmp/chart-deps', ROOT / 'tmp/rtc-analysis-libs'):
        if (folder / 'matplotlib').is_dir():
            sys.path.insert(0, str(folder))
            break
    import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ZONE = ZoneInfo('America/Chicago')
BOARDS = ('2205', '2512', '2604', '2609')
COLORS = dict(zip(BOARDS, ('#1769aa', '#cb6b08', '#23834f', '#8054ab')))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def local(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(ZONE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=ROOT / 'output/qualification/rtc-drift-3hour-campaign.json')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    state = read(args.state)
    root = Path(state['root'])
    run = Path(state['last_summary']).parent
    summary = read(run / 'summary.json')
    audit = read(run / 'campaign-audit.json')
    analysis = read(root / 'latest-analysis.json')
    points = read(root / 'points.json')
    events = read(root / 'events.json')
    assert audit['summary_sha256'] == sha(run / 'summary.json')
    sources = {str(p.resolve()): sha(p) for p in (args.state, root / 'points.json', root / 'events.json', root / 'latest-analysis.json', run / 'summary.json', run / 'campaign-audit.json')}
    for p in points:
        receipt = Path(p['report'])
        assert sha(receipt) == p['report_sha256'] and read(receipt)['passed']
        assert p['low'] <= p['offset'] <= p['high']
        sources[str(receipt)] = sha(receipt)
    for item in summary['boards']:
        receipt = Path(item['report'])
        r = read(receipt)
        assert sha(receipt) == item['sha256'] and r['application_ram_restored'] and r['port_released']
        assert not any(r[k] for k in ('clock_set_attempted', 'trim_changed', 'flash_written'))
        admission = read(receipt.parent / 'prompt-admission.json')
        if admission['entered_from_REC']:
            assert r['returned_to_original_REC'] and (receipt.parent / 'final-REC.txt').read_bytes().endswith(b'REC> ')
        else:
            rx = b''.join(bytes.fromhex(x['hex']) for x in map(json.loads, (receipt.parent / 'serial.jsonl').read_text().splitlines()) if x['direction'] == 'RX')
            assert rx.endswith(b'\r\nB3> ')
            assert re.findall(rb'7D30: ([0-9A-Fa-f]{2})', rx)[-1].decode().lower() == r['monitor_before_hex'].lower()
    out = args.out or root / 'charts' / run.name
    if out.exists():
        assert (out / 'summary.json').read_bytes() == (run / 'summary.json').read_bytes(), 'Output belongs to a different collection'
    out.mkdir(parents=True, exist_ok=True)
    for name, path in {'campaign-state.json': args.state, 'points.json': root / 'points.json', 'events.json': root / 'events.json', 'analysis.json': root / 'latest-analysis.json', 'summary.json': run / 'summary.json', 'campaign-audit.json': run / 'campaign-audit.json'}.items():
        (out / name).write_bytes(path.read_bytes())
    latest_time = max(v['latest']['time'] for v in analysis['boards'].values())
    stamp = local(latest_time).strftime('%b %d, %Y · %I:%M %p %Z')
    failed = []
    accepted = {p['report'] for p in points}
    for path in sorted((root / 'captures').glob('*/batch-*/summary.json')):
        for item in read(path).get('failures', []):
            if item.get('report') in accepted:
                continue
            receipt = Path(item['report']) if item.get('report') else None
            failed.append({'board': item['board'], 'report': str(receipt), 'error': item.get('error')})
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 13, 'axes.labelsize': 11, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#aab4c0', 'text.color': '#182e45', 'axes.labelcolor': '#182e45', 'xtick.color': '#4c5f72', 'ytick.color': '#4c5f72', 'savefig.facecolor': 'white'})
    def export(fig, name):
        fig.savefig(out / (name + '.png'), dpi=170, facecolor='white')
        fig.savefig(out / (name + '.svg'), facecolor='white')
        plt.close(fig)
    first = min(p['time'] for p in points)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.subplots_adjust(left=.075, right=.97, bottom=.14, top=.83, hspace=.49, wspace=.23)
    fig.suptitle('RTCC offset from NIST through time', x=.075, y=.965, ha='left', fontsize=22, fontweight='bold')
    fig.text(.075, .915, f'Latest collection: {stamp}   |   Positive offset = clock ahead of NIST', fontsize=11)
    for board, ax in zip(BOARDS, axes.flat):
        rows = sorted((p for p in points if p['board'] == board), key=lambda p: p['time'])
        data = analysis['boards'][board]
        assert data['latest']['report'] == rows[-1]['report']
        spans = [[rows[0]]]
        board_events = [e for e in events if e['board'] == board]
        for p in rows[1:]:
            prev = spans[-1][-1]
            if (p['trim'], p['control']) != (prev['trim'], prev['control']) or any(prev['time'] < e['up'] <= p['time'] for e in board_events):
                spans.append([])
            spans[-1].append(p)
        for group in spans:
            xs = [local(p['time']) for p in group]
            ys = [p['offset'] for p in group]
            ax.errorbar(xs, ys, yerr=[[p['offset'] - p['low'] for p in group], [p['high'] - p['offset'] for p in group]], fmt='o-', ms=4.5, lw=1.2, elinewidth=1.4, capsize=3, color=COLORS[board], alpha=.85)
        for event in board_events:
            if event['down']==event['up']:
                ax.axvline(local(event['up']),color='#b73d42',alpha=.65,lw=1.2,ls=':')
            else:ax.axvspan(local(event['down']), local(event['up']), color='#b73d42', alpha=.15)
        f = data['fit']
        if f.get('available'):
            boundary = max([state['baselines'][board]['time']] + [e['up'] for e in board_events if e['up'] <= rows[-1]['time']])
            group = [p for p in rows if p['time'] >= boundary and p['trim'] == rows[-1]['trim'] and p['control'] == rows[-1]['control']]
            anchor = group[0]['time']
            slope = f['ppm'] / 1e6
            low = max(p['low'] - slope * (p['time'] - anchor) for p in group)
            high = min(p['high'] - slope * (p['time'] - anchor) for p in group)
            assert low <= high + 1e-9
            intercept = (low + high) / 2
            ax.plot([local(group[0]['time']), local(group[-1]['time'])], [intercept, intercept + slope * (group[-1]['time'] - anchor)], '--', color='#253b50', lw=1.4)
        ymin, ymax = min(p['low'] for p in rows), max(p['high'] for p in rows)
        pad = max(.06, (ymax - ymin) * .18)
        ax.set_ylim(ymin - pad, ymax + pad)
        if ymin - pad <= 0 <= ymax + pad:
            ax.axhline(0, color='#9ba8b4', lw=.9, ls=':')
        ax.set_title(f'{board}  ·  trim {rows[-1]["trim"]}  ·  {len(rows)} accepted snapshots', loc='left', color=COLORS[board], fontweight='bold')
        ax.set_ylabel('RTC − NIST (seconds)')
        ax.set_xlim(local(first) - timedelta(minutes=15), local(latest_time) + timedelta(minutes=20))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7, tz=ZONE))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M', tz=ZONE))
        ax.grid(alpha=.18)
    fig.text(.075, .065, 'Bars = acquisition/NTP bounds. Dashed = compatible rate fit. Red = recorded PF transition.', fontsize=10)
    fig.text(.075, .035, f'All times America/Chicago. Only post-clear campaign data. {len(events)} recorded PF events; {len(failed)} rejected attempts excluded.', fontsize=10, color='#526477')
    export(fig, 'offset-history')

    fig, (left, right) = plt.subplots(1, 2, figsize=(13, 6.3), gridspec_kw={'width_ratios': [1, 1.12]})
    fig.subplots_adjust(left=.10, right=.965, bottom=.23, top=.72, wspace=.38)
    fig.suptitle('Latest offsets and powered drift estimates', x=.07, y=.955, ha='left', fontsize=22, fontweight='bold')
    fig.text(.07, .88, f'{stamp}   |   Measurements were taken sequentially on the four boards.', fontsize=11)
    for index, board in enumerate(BOARDS):
        data = analysis['boards'][board]; p = data['latest']; f = data['fit']
        left.errorbar(p['offset'], index, xerr=[[p['offset'] - p['low']], [p['high'] - p['offset']]], fmt='o', ms=7, capsize=6, elinewidth=2, color=COLORS[board])
        left.annotate(f'{p["offset"]:+.3f} s', (p['offset'], index), xytext=(0, 15), textcoords='offset points', ha='center', fontsize=11, color=COLORS[board])
        if f.get('available'):
            lo, hi = f['bounds_ppm']; mid = f['ppm']
            right.errorbar(mid, index, xerr=[[mid-lo], [hi-mid]], fmt='o', ms=7, capsize=6, elinewidth=2, color=COLORS[board])
            right.annotate(f'{mid:+.2f} [{lo:+.2f}, {hi:+.2f}] ppm', (mid, index), xytext=(0, 15), textcoords='offset points', ha='center', fontsize=10, color=COLORS[board])
        else:
            right.text(.03, index, f['reason'], transform=right.get_yaxis_transform(), fontsize=10)
    left.set_yticks(range(4), [f'{b}\ntrim {analysis["boards"][b]["latest"]["trim"]}' for b in BOARDS])
    right.set_yticks(range(4), BOARDS)
    for ax in (left, right):
        ax.axvline(0, color='#68798b', lw=1, ls='--')
        ax.set_ylim(3.6, -.8)
        ax.grid(axis='x', alpha=.18)
        ax.margins(x=.22)
    left.set_title('RTCC − NIST', loc='left', fontweight='bold', pad=18)
    left.set_xlabel('Seconds · negative = behind, positive = ahead')
    right.set_title('Powered drift · campaign fit', loc='left', fontweight='bold', pad=18)
    right.set_xlabel('ppm · negative = losing time, positive = gaining')
    spans = [v['fit']['hours'] for v in analysis['boards'].values() if v['fit'].get('available')]
    recommendations = {b: analysis['boards'][b]['recommendation'] for b in BOARDS}
    verdict = 'Keep all current trims' if set(recommendations.values()) == {'Keep current trim'} else 'Review trim recommendations in report.json'
    span_label = ('about '+str(round(max(spans),1)) if round(min(spans),1)==round(max(spans),1) else f'{min(spans):.1f}–{max(spans):.1f}') if spans else 'less than one'
    fig.text(.07, .125, f'{verdict}. Available fits span {span_label} hours; no trim changes applied.', fontsize=12, fontweight='bold')
    fig.text(.07, .075, 'Bounds describe measurement compatibility, not statistical confidence. Midpoints alone do not establish a trim correction.', fontsize=10)
    fig.text(.07, .035, f'New PF events this run: {len(audit["new_PF_events"])}. Failed/rejected reads are excluded from the fit.', fontsize=10, color='#526477')
    export(fig, 'offsets-and-drift')
    result = {'offline_charts_only': True, 'board_ports_opened_by_plotter': False, 'latest_local': local(latest_time).isoformat(), 'collection_passed': summary['passed'], 'campaign_audit_passed': audit['passed'], 'new_PF_events': audit['new_PF_events'], 'events_since_baseline': events, 'rejected_reads': failed, 'boards': analysis['boards'], 'sources': sources, 'generator_sha256': sha(__file__)}
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    manifest = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'out': str(out.resolve()), 'latest_local': result['latest_local'], 'new_PF_events': result['new_PF_events'], 'recommendations': recommendations, 'charts': ['offset-history.png', 'offsets-and-drift.png']}, indent=2))


if __name__ == '__main__':
    main()
