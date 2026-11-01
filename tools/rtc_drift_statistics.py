"""Descriptive statistics from accepted saved RTC observations; no hardware."""
import json,math,statistics
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ZONE=ZoneInfo('America/Chicago')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write_statistics(state):
    root=Path(state['root']);analysis=read(root/'latest-analysis.json');boards={}
    lines=['# RTC / NIST statistics','', 'Offset = RTC − NIST; positive means ahead. SD describes the nine within-collection offset midpoints, including one-second RTC quantization and acquisition timing. It is not oscillator stability or a confidence interval.','',
        '| Board | Latest (CDT) | Offset s [bounds] | Powered ppm [bounds] | Burst SD ms | Trim | Recommendation |','|---|---|---|---|---:|---:|---|']
    for board,data in analysis['boards'].items():
        p=data['latest'];r=read(p['report']);samples=r['readings'];assert r['passed'] and len(samples)==9
        mid=[statistics.mean(s['rtc_minus_reference_interval_s']) for s in samples]
        refs=r['reference_samples'];f=data['fit'];sd=statistics.stdev(mid)
        b=dict(latest_UTC=p['UTC'],latest_local=datetime.fromtimestamp(p['time'],timezone.utc).astimezone(ZONE).isoformat(),
            offset_s=p['offset'],offset_bounds_s=[p['low'],p['high']],trim=p['trim'],trim_freshly_verified=p.get('trim_verified',True),PF_history_freshly_read=p.get('PF_history_freshly_read',True),control=p['control'],recommendation=data['recommendation'],
            powered_fit=f,seconds_per_day=f['ppm']*.0864 if f.get('available') else None,
            seconds_per_day_bounds=[x*.0864 for x in f['bounds_ppm']] if f.get('available') else None,
            burst=dict(n=len(mid),mean_offset_s=statistics.mean(mid),median_offset_s=statistics.median(mid),sample_SD_s=sd,sample_variance_s2=statistics.variance(mid),min_offset_midpoint_s=min(mid),max_offset_midpoint_s=max(mid)),
            NTP=dict(n=len(refs),server=refs[0]['server'],stratum=refs[0]['stratum'],reference_uncertainty_s=r['reference_uncertainty_s'],round_trip_mean_s=statistics.mean(x['round_trip_delay_s'] for x in refs),round_trip_SD_s=statistics.stdev(x['round_trip_delay_s'] for x in refs),reference_offset_SD_s=statistics.stdev(x['server_minus_host_s'] for x in refs)),
            PF_latched=p['PF_latched'],active_PF_records=p['active_PF_records'],report=p['report'],report_sha256=p['report_sha256'])
        boards[board]=b
        rate=f'{f["ppm"]:+.2f} [{f["bounds_ppm"][0]:+.2f}, {f["bounds_ppm"][1]:+.2f}]' if f.get('available') else 'Pending new-segment checkpoint'
        local=datetime.fromtimestamp(p['time'],timezone.utc).astimezone(ZONE).strftime('%m/%d %H:%M:%S')
        lines.append(f'| {board} | {local} | {p["offset"]:+.3f} [{p["low"]:+.3f}, {p["high"]:+.3f}] | {rate} | {sd*1000:.1f} | {p["trim"]} | {data["recommendation"]} |')
    lines+=['','Recorded PF transitions (minute resolution; a same-minute down/up does not mean zero elapsed outage):']
    for event in analysis['events']:
        down=datetime.fromtimestamp(event['down'],timezone.utc).astimezone(ZONE).isoformat();up=datetime.fromtimestamp(event['up'],timezone.utc).astimezone(ZONE).isoformat()
        lines.append(f'- {event["board"]}: down {down}; up {up}; recorded minute difference {event["minutes"]:g}.')
    if not analysis['events']:lines.append('- None recorded in this campaign.')
    for board,boundary in state.get('segment_boundaries',{}).items():lines+=['',f'{board} segment starts {boundary["UTC"]}: {boundary["reason"]}.']
    unverified=[board for board,data in analysis['boards'].items() if data['latest'].get('trim_verified') is False]
    if unverified:lines+=['',', '.join(unverified)+': latest saved sample carries the last verified trim; it did not read the trim register.']
    if any(data['latest'].get('PF_history_freshly_read') is False for data in analysis['boards'].values()):lines+=['','Native TIME reads the current PF latch; EEPROM PF history is retained and is not freshly scanned by that transport.']
    result=dict(generated_UTC=datetime.now(timezone.utc).isoformat(),boards=boards,events=analysis['events'],SD_method='Sample SD (n-1 divisor) of the nine accepted per-read offset-interval midpoints. Contains RTC one-second quantization and host acquisition variation; not a clock-stability or confidence measure.',trim_applied=False)
    (root/'latest-statistics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (root/'statistics.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result
