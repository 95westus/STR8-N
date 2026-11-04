"""Render a detailed, portable report from saved RTC campaign evidence only."""
import argparse
import base64
import html
import json
import shutil
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import plot_rtc_drift_campaign as basic
from rtc_drift_campaign import fit

plt, mdates = basic.plt, basic.mdates
BOARDS, COLORS, ZONE = basic.BOARDS, basic.COLORS, basic.ZONE
read, sha, local = basic.read, basic.sha, basic.local


def stamp(t):
    return local(t).strftime('%m/%d %H:%M:%S')


def segments(rows, board, state, events):
    cuts = [e['up'] for e in events if e['board'] == board]
    if board in state.get('segment_boundaries', {}):
        cuts.append(state['segment_boundaries'][board]['time'])
    groups = [[rows[0]]]
    for p in rows[1:]:
        previous = groups[-1][-1]
        if ((p['trim'], p['control']) != (previous['trim'], previous['control'])
                or any(previous['time'] < t <= p['time'] for t in cuts)):
            groups.append([])
        groups[-1].append(p)
    return groups


def table(headers, rows):
    esc = lambda value: html.escape(str(value))
    return '<table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=basic.ROOT / 'output/qualification/rtc-drift-3hour-campaign.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    original = sys.argv
    sys.argv = [basic.__file__, '--state', str(args.state), '--out', str(args.out)]
    try:
        basic.main()
    finally:
        sys.argv = original
    out = args.out
    state, points, events, analysis = [read(out / name) for name in ('campaign-state.json', 'points.json', 'events.json', 'analysis.json')]
    evidence = read(out / 'report.json')
    rows_by_board = {b: sorted((p for p in points if p['board'] == b), key=lambda p: p['time']) for b in BOARDS}
    first, last = min(p['time'] for p in points), max(p['time'] for p in points)
    snapshot_stats, board_stats = [], {}
    sources = dict(evidence['sources'])
    for b, rows in rows_by_board.items():
        for p in rows:
            receipt = read(p['report'])
            if p.get('source'):
                assert sha(p['source']) == p['source_sha256']
                samples = read(p['source'])['samples']
                sources[p['source']] = p['source_sha256']
            else:
                samples = receipt['readings']
            intervals = [s['rtc_minus_reference_interval_s'] if 'rtc_minus_reference_interval_s' in s else s['offset_bounds_s'] for s in samples]
            mids = [statistics.mean(interval) for interval in intervals]
            refs = receipt['reference_samples']
            assert len(mids) >= 2 and all(r['stratum'] == 1 for r in refs)
            lo = max(interval[0] for interval in intervals)
            hi = min(interval[1] for interval in intervals)
            assert abs(lo - p['low']) < 1e-8 and abs(hi - p['high']) < 1e-8
            snapshot_stats.append(dict(board=b, time=p['time'], local=local(p['time']).isoformat(),
                offset_s=p['offset'], bounds_s=[lo, hi], bound_width_s=hi-lo,
                trim=p['trim'], control=p['control'], n=len(mids), mean_s=statistics.mean(mids),
                median_s=statistics.median(mids), burst_SD_s=statistics.stdev(mids),
                NTP_RTT_mean_s=statistics.mean(r['round_trip_delay_s'] for r in refs),
                NTP_uncertainty_s=receipt['reference_uncertainty_s'],
                PF_latched=p.get('PF_latched', False), PF_records=p.get('active_PF_records', 0),
                report=p['report'], report_sha256=p['report_sha256']))
        groups = segments(rows, b, state, events)
        history = []
        for number, group in enumerate(groups, 1):
            evolution = []
            for n in range(2, len(group)+1):
                f = fit(group[:n])
                if f['available']:
                    evolution.append(dict(time=group[n-1]['time'], **f))
            history.append(dict(number=number, start=group[0]['time'], end=group[-1]['time'],
                checkpoints=len(group), fit=fit(group), cumulative=evolution))
        current = history[-1]['fit']
        assert current == analysis['boards'][b]['fit'], 'Recomputed current fit differs from accepted campaign report'
        values = [p['offset'] for p in rows]
        q = [s for s in snapshot_stats if s['board'] == b]
        board_stats[b] = dict(checkpoints=len(rows), accepted_individual_reads=sum(s['n'] for s in q),
            elapsed_h=(rows[-1]['time']-rows[0]['time'])/3600,
            first_offset_s=values[0], latest_offset_s=values[-1], net_offset_change_s=values[-1]-values[0],
            minimum_checkpoint_midpoint_s=min(values), maximum_checkpoint_midpoint_s=max(values),
            mean_checkpoint_midpoint_s=statistics.mean(values), checkpoint_midpoint_SD_s=statistics.stdev(values),
            burst_SD_median_s=statistics.median(s['burst_SD_s'] for s in q),
            NTP_RTT_mean_s=statistics.mean(s['NTP_RTT_mean_s'] for s in q),
            segments=history, latest=q[-1], recommendation=analysis['boards'][b]['recommendation'])

    def export(fig, name):
        fig.savefig(out / (name+'.png'), dpi=175, facecolor='white')
        fig.savefig(out / (name+'.svg'), facecolor='white')
        plt.close(fig)

    def date_axis(ax):
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7, tz=ZONE))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M', tz=ZONE))
        ax.grid(alpha=.18)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.6))
    fig.subplots_adjust(left=.075, right=.97, bottom=.14, top=.83, hspace=.48, wspace=.24)
    fig.suptitle('How the powered ppm estimates developed', x=.075, y=.965, ha='left', fontsize=22, fontweight='bold')
    fig.text(.075, .915, 'Each estimate uses all accepted checkpoints in its own power / trim / maintenance segment.', fontsize=11)
    for b, ax in zip(BOARDS, axes.flat):
        for seg in board_stats[b]['segments']:
            series = seg['cumulative']
            if not series:
                continue
            xs = [local(s['time']) for s in series]
            ax.fill_between(xs, [s['bounds_ppm'][0] for s in series], [s['bounds_ppm'][1] for s in series], color=COLORS[b], alpha=.15)
            ax.plot(xs, [s['ppm'] for s in series], 'o-', color=COLORS[b], ms=4.5, lw=1.4)
        f = board_stats[b]['segments'][-1]['fit']
        current_segment = board_stats[b]['segments'][-1]
        label = f'{f["ppm"]:+.2f} ppm [{f["bounds_ppm"][0]:+.2f}, {f["bounds_ppm"][1]:+.2f}]' if f['available'] else f'Current segment: {(current_segment["end"]-current_segment["start"])/60:.0f} min; ppm pending'
        ax.set_title(b + '  ·  trim ' + str(rows_by_board[b][-1]['trim']), loc='left', fontweight='bold', color=COLORS[b])
        ax.text(.02, .04, label, transform=ax.transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=.85, edgecolor='none'))
        ax.axhline(0, lw=1, color='#64778b', ls='--')
        for e in events:
            if e['board'] == b:
                ax.axvline(local(e['up']), color='#b73d42', lw=1, ls=':')
        boundary = state.get('segment_boundaries', {}).get(b)
        if boundary:
            ax.axvline(local(boundary['time']), color='#9b6200', lw=1, ls='--')
        ax.set_xlim(local(first), local(last))
        ax.set_ylabel('Powered rate (ppm)')
        date_axis(ax)
    fig.text(.075, .065, 'Shading = compatible constant-rate bounds, not confidence intervals. Fits need at least one hour.', fontsize=10)
    fig.text(.075, .035, '2512: earlier fit retained as history; no ppm fit bridges the PF / firmware-maintenance gap. All times CDT.', fontsize=10, color='#526477')
    export(fig, 'ppm-evolution')

    fig, axes = plt.subplots(3, 1, figsize=(13, 9.5), sharex=True)
    fig.subplots_adjust(left=.09, right=.97, bottom=.13, top=.84, hspace=.30)
    fig.suptitle('Measurement quality through the campaign', x=.075, y=.965, ha='left', fontsize=22, fontweight='bold')
    fig.text(.075, .915, 'Accepted measurements only. Lower bars and spreads indicate tighter acquisition evidence.', fontsize=11)
    specs = [('bound_width_s', 'Offset bound width (ms)'), ('burst_SD_s', 'Within-burst sample SD (ms)'), ('NTP_RTT_mean_s', 'NIST NTP mean RTT (ms)')]
    for ax, (key, label) in zip(axes, specs):
        for b in BOARDS:
            q = [s for s in snapshot_stats if s['board'] == b]
            ax.plot([local(s['time']) for s in q], [s[key]*1000 for s in q], 'o-', color=COLORS[b], label=b, lw=1.3, ms=4)
        ax.set_ylabel(label)
        ax.grid(alpha=.18)
    axes[0].legend(ncol=4, frameon=False, loc='upper right')
    date_axis(axes[-1])
    fig.text(.075, .055, 'Burst SD includes one-second RTC quantization and host acquisition timing; it does not measure oscillator stability.', fontsize=10)
    fig.text(.075, .025, 'A smaller SD is not by itself evidence for a trim change. NTP RTT is network round-trip time. All times CDT.', fontsize=10, color='#526477')
    export(fig, 'measurement-quality')

    fig, ax = plt.subplots(figsize=(13, 5.4))
    fig.subplots_adjust(left=.09, right=.97, bottom=.24, top=.74)
    fig.suptitle('Sampling coverage and recorded power event', x=.075, y=.96, ha='left', fontsize=22, fontweight='bold')
    fig.text(.075, .88, f'{sum(s["n"] for s in snapshot_stats)} accepted RTC reads in {len(points)} board checkpoints · {len(events)} recorded PF event', fontsize=11)
    for y, b in enumerate(BOARDS):
        rows = rows_by_board[b]
        ax.hlines(y, local(rows[0]['time']), local(rows[-1]['time']), color=COLORS[b], alpha=.25, lw=2)
        ax.scatter([local(p['time']) for p in rows], [y]*len(rows), color=COLORS[b], s=35, zorder=3)
    for e in events:
        y = BOARDS.index(e['board'])
        ax.scatter([local(e['up'])], [y], marker='v', color='#b73d42', s=110, zorder=5)
        fig.text(.075, .79, f'{e["board"]} PF: {stamp(e["up"])} CDT; down/up in the same recorded minute.', fontsize=11, color='#b73d42')
    for b, boundary in state.get('segment_boundaries', {}).items():
        y = BOARDS.index(b)
        ax.scatter([local(boundary['time'])], [y], marker='s', color='#9b6200', s=60, zorder=4)
    ack_points = [p for p in points if p.get('capture_profile') == 'BASE1-PF-ACK1']
    for p in ack_points:
        y = BOARDS.index(p['board'])
        ax.scatter([local(p['time'])], [y], marker='D', color='#182e45', s=50, zorder=5)
    ax.set_yticks(range(4), BOARDS)
    ax.set_ylim(3.5, -.65)
    date_axis(ax)
    fig.text(.075, .115, 'Dots: accepted checkpoints   Red triangle: PF   Amber square: qualified BASE1 segment start   Diamond: post-ACK', fontsize=10)
    fig.text(.075, .065, 'PF timestamps resolve minutes; the duration of the same-minute outage is unknown. ACK preserved its journal record.', fontsize=10)
    fig.text(.075, .025, 'Lines show observation coverage, not independently proven continuous power. All times America/Chicago (CDT).', fontsize=10, color='#526477')
    export(fig, 'coverage-and-power')

    latest_rows, segment_rows, all_rows, descriptive_rows = [], [], [], []
    for b in BOARDS:
        data = board_stats[b]; q = data['latest']; f = data['segments'][-1]['fit']
        rate = f'{f["ppm"]:+.3f} [{f["bounds_ppm"][0]:+.3f}, {f["bounds_ppm"][1]:+.3f}]' if f['available'] else 'Pending: new segment <1 h'
        perday = f'{f["ppm"]*.0864:+.4f}' if f['available'] else '—'
        latest_rows.append([b, stamp(q['time']), f'{q["offset_s"]:+.4f} [{q["bounds_s"][0]:+.4f}, {q["bounds_s"][1]:+.4f}]', rate, perday, q['trim'], f'{q["burst_SD_s"]*1000:.1f}', data['recommendation']])
        descriptive_rows.append([b, data['accepted_individual_reads'], f'{data["elapsed_h"]:.3f}', f'{data["first_offset_s"]:+.4f}', f'{data["net_offset_change_s"]:+.4f}', f'{data["minimum_checkpoint_midpoint_s"]:+.4f} / {data["maximum_checkpoint_midpoint_s"]:+.4f}', f'{data["mean_checkpoint_midpoint_s"]:+.4f}', f'{data["checkpoint_midpoint_SD_s"]*1000:.1f}', f'{data["burst_SD_median_s"]*1000:.1f}', f'{data["NTP_RTT_mean_s"]*1000:.1f}'])
        for seg in data['segments']:
            f = seg['fit']
            rate = f'{f["ppm"]:+.3f} [{f["bounds_ppm"][0]:+.3f}, {f["bounds_ppm"][1]:+.3f}]' if f['available'] else f['reason']
            segment_rows.append([b, seg['number'], stamp(seg['start']), stamp(seg['end']), seg['checkpoints'], f'{(seg["end"]-seg["start"])/3600:.3f}', rate])
    for q in sorted(snapshot_stats, key=lambda q: (q['time'], q['board'])):
        all_rows.append([q['board'], stamp(q['time']), f'{q["offset_s"]:+.4f}', f'[{q["bounds_s"][0]:+.4f}, {q["bounds_s"][1]:+.4f}]', q['n'], f'{q["burst_SD_s"]*1000:.1f}', f'{q["NTP_RTT_mean_s"]*1000:.1f}', q['trim'], 'set' if q['PF_latched'] else 'clear', q['PF_records']])
    headers = ['Board', 'Latest CDT', 'RTC − NIST s [bounds]', 'Powered ppm [bounds]', 's/day estimate', 'Trim', 'Burst SD ms', 'Recommendation']
    segheads = ['Board', 'Segment', 'Start CDT', 'End CDT', 'Checkpoints', 'Span h', 'Powered ppm [bounds]']
    allheads = ['Board', 'CDT', 'Offset s', 'Bounds s', 'Reads', 'Burst SD ms', 'NTP RTT ms', 'Trim', 'PF latch', 'PF rows']
    descriptive_heads = ['Board', 'RTC reads', 'Elapsed h', 'First offset s', 'Net change s', 'Min / max offset s', 'Mean offset s', 'Checkpoint SD ms', 'Median burst SD ms', 'Mean NTP RTT ms']
    notes = [
        'Positive offsets mean RTC ahead of NIST; positive ppm means gaining time. 1 ppm = 0.0864 seconds/day.',
        'Rate bounds describe compatibility with acquisition intervals, not statistical confidence. Current available bounds all include zero; keep all current trims.',
        'The per-checkpoint offset is the midpoint of the intersection of its read intervals, not the arithmetic mean of the raw read midpoints.',
        'Burst SD uses the n−1 sample divisor and includes one-second RTC quantization and host acquisition timing. It is not oscillator stability.',
        'Campaign offset means, ranges and checkpoint SD are descriptive only: they include initial clock error, drift and measurement variation. 2512 net change also crosses its maintenance gap and is not a powered rate estimate.',
        '2512 earlier and current segments are kept separate at the recorded PF / unverified firmware-maintenance gap. ACK did not set UTC, alter trim, or start a new segment.',
        'One PF event is recorded: 2512, October 28 at 20:14 CDT. Down/up share a recorded minute; actual outage duration is unresolved. Its latch is now clear and one journal record is preserved.',
        'An uncleared PF latch can retain an older event; the absence of another timestamp cannot establish uninterrupted power.',
        'This report uses saved accepted evidence only. No board or NTP port was opened and no time, trim, firmware, or configuration was changed.',
    ]
    charts = ['offset-history', 'offsets-and-drift', 'ppm-evolution', 'measurement-quality', 'coverage-and-power']
    blocks = ''.join('<figure><img alt="' + name.replace('-', ' ') + '" src="data:image/png;base64,' + base64.b64encode((out/(name+'.png')).read_bytes()).decode() + '"></figure>' for name in charts)
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RTC drift campaign detail</title><style>body{font:16px/1.5 system-ui,sans-serif;color:#182e45;background:#f4f7fa;margin:0}main{max-width:1400px;margin:auto;padding:28px}h1{font-size:32px;margin-bottom:5px}h2{margin-top:32px}table{border-collapse:collapse;width:100%;background:white;font-size:13px}td,th{padding:9px 10px;border-bottom:1px solid #dce4eb;text-align:left}th{background:#e7eef5}figure{margin:28px 0;background:white}img{width:100%;height:auto}li{margin:8px 0}.scroll{overflow-x:auto}summary{cursor:pointer;font-weight:600}</style><main><h1>RTC / NIST drift campaign</h1><p>' + html.escape(stamp(first)+' – '+stamp(last)+' CDT, 2026 · saved evidence') + '</p><div class="scroll">' + table(headers, latest_rows) + '</div>' + blocks + '<h2>Powered segments</h2><div class="scroll">' + table(segheads, segment_rows) + '</div><h2>Interpretation and limits</h2><ul>' + ''.join('<li>'+html.escape(n)+'</li>' for n in notes) + '</ul><details open><summary>All accepted checkpoints</summary><div class="scroll">' + table(allheads, all_rows) + '</div></details><details><summary>Unsuccessful attempts excluded from analysis</summary><pre>' + html.escape(json.dumps(evidence['rejected_reads'], indent=2)) + '</pre></details></main></html>'
    document = document.replace('<h2>Interpretation and limits</h2>', '<h2>Campaign descriptive statistics</h2><div class="scroll">' + table(descriptive_heads, descriptive_rows) + '</div><h2>Interpretation and limits</h2>')
    (out/'campaign-detail.html').write_text(document, encoding='utf-8')
    def mdtable(h, rows):
        return '\n'.join(['| '+' | '.join(map(str,h))+' |', '| '+' | '.join(['---']*len(h))+' |'] + ['| '+' | '.join(map(str,row))+' |' for row in rows])
    markdown = '# Detailed RTC / NIST campaign\n\n' + stamp(first)+' – '+stamp(last)+' CDT, 2026\n\n' + mdtable(headers, latest_rows) + '\n\n## Powered segments\n\n' + mdtable(segheads, segment_rows) + '\n\n## Interpretation\n\n' + '\n'.join('- '+n for n in notes) + '\n\n## All accepted checkpoints\n\n' + mdtable(allheads, all_rows) + '\n'
    markdown = markdown.replace('## Interpretation\n', '## Campaign descriptive statistics\n\n' + mdtable(descriptive_heads, descriptive_rows) + '\n\n## Interpretation\n')
    (out/'campaign-detail.md').write_text(markdown, encoding='utf-8')
    result = dict(generated_UTC=datetime.now(timezone.utc).isoformat(), offline_only=True,
        first_local=local(first).isoformat(), last_local=local(last).isoformat(),
        checkpoints=len(points), accepted_individual_reads=sum(q['n'] for q in snapshot_stats),
        boards=board_stats, checkpoints_detail=snapshot_stats, events=events,
        unsuccessful_attempts=evidence['rejected_reads'], notes=notes, sources=sources,
        charts=[name+'.png' for name in charts], generator_sha256=sha(__file__))
    (out/'detailed-statistics.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    shutil.copyfile(__file__, out/'plot_rtc_campaign_detail.py')
    for path, expected in sources.items():
        assert sha(path) == expected, 'Source changed during rendering; rerender from a stable snapshot'
    (out/'manifest.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, out=str(out.resolve()), checkpoints=len(points), accepted_individual_reads=result['accepted_individual_reads'], latest=latest_rows, segments=segment_rows), indent=2))


if __name__ == '__main__':
    main()
