"""Bind the post-beta12 read-only NTP measurements to original UTC baselines."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/qualification/rtc-drift-2026-10-07-post-beta12'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    baseline=read(ROOT/'output/qualification/rtc-utc-sync-2026-10-06/baseline-index.json')
    boards=[]
    for b in baseline['boards']:
        for key in ('sync','baseline'):assert sha(Path(b[key+'_report']))==b[key+'_sha256']
        path=OUT/(b['board']+'-retry')/'report.json';r=read(path)
        assert r['passed'] and r['mode']=='read-only drift measurement' and not r['flash_written'] and not r['trim_changed']
        assert 'set_operation' not in r and r['clock_advanced']
        boards.append(dict(board=b['board'],reference_utc=r['baseline_reference_utc'],elapsed_seconds=r['elapsed_seconds'],
            utc_offset_seconds=r['rtc_minus_reference_interval_s'],drift_seconds=r['drift_seconds_interval'],
            drift_ppm=r['drift_ppm_interval'],drift_seconds_per_day=r['drift_seconds_per_day_interval'],report=str(path),report_sha256=sha(path)))
    a,b=boards;assert (a['board'],b['board'])==('2205','2609')
    difference=[a['utc_offset_seconds'][0]-b['utc_offset_seconds'][1],a['utc_offset_seconds'][1]-b['utc_offset_seconds'][0]]
    summary=dict(passed=True,reference='fresh NIST NTP 132.163.96.6; final reference checks passed',clock_set=False,trim_changed=False,powerfail_acknowledged=False,
        original_baselines_preserved=True,boards=boards,board_2205_minus_2609_seconds=difference,comparison_note='UTC offsets sampled sequentially; not a simultaneous subsecond phase measurement')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for r in boards:print(r['board'],'elapsed h',round(r['elapsed_seconds']/3600,3),'UTC offset',r['utc_offset_seconds'],'drift',r['drift_seconds'],'ppm',r['drift_ppm'])
    print('2205 minus 2609 UTC-offset difference',difference)
if __name__=='__main__':main()
