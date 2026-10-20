"""Create a new promotion-held v1g distribution after verified owner STOP.

No ports, workload restart, firmware build, Git mutation or publication occurs.
The prior package, frozen run and source evidence are read-only inputs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
Q = ROOT / 'output/qualification'
IMAGE_SHA = '6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
KIT_SHA = '42ea635525957a3a8199ab627410915f0ced93eb893990dc70802e1142541caf'
BASELINE_SHA = '5db3f89e0bcdd1ec1bd9d1958c6abbc8530977783a2f1bb195bc80220af4913e'
RECOVERY_SHA = 'bf2d178b28bb2a0a0cf7831215f5d70c8a063d0db6dc78fd8d73978008dd1607'
SEGMENT = '2609-post-RTC-recovery-2026-10-18-r1'
R6_NAME = 'rc1-v2-base-utils-led10-asm-dbg1-v1g-continuing-soak-r6-2026-10-20-180714Z'
CLOSURE_SHA = 'b19ab0895b3b6c1b1de1487d61a90a21a51d8b24c2efe1142a3a16e1a8695883'
FINAL_REPORT_SHA = 'fc95e0c13d4317e2a685467367425951b818d2d3bb446fc14915c5b920b86961'
PATTERNS = ['wigwag', 'gray-code', 'binary-counter', 'walking-one', 'walking-zero',
            'bouncing-dot', 'checkerboard', 'fill-drain', 'expanding-contracting-pairs', 'lfsr-sparkle']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def source_name(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), 'Source outside workspace')
    return path.relative_to(ROOT).as_posix()


def verify_gate(path):
    """Bind the owner's final closeout to actual immutable host receipts."""
    closure = read(path)
    require(sha(path) == CLOSURE_SHA, 'Changed independently verified final closeout')
    run = Path(closure['exact_run']).resolve()
    require(run == Q / R6_NAME and Path(path).resolve() == run / 'monitor/final-closeout.json', 'Wrong closure/run')
    require(closure['passed'] and closure['actual_worker_exit_verified'] and closure['owner_requested_stop'], 'Clean exited owner STOP required')
    require(closure['promotion_held'] and not closure['native_debugging'] and not closure['native_applications'], 'Wrong closure scope')
    require(Path(closure['report']).resolve() == run / 'report.json' and sha(closure['report']) == closure['report_sha256'] == FINAL_REPORT_SHA, 'Changed final report')
    require(sha(closure['worker_exit_receipt']) == closure['worker_exit_receipt_sha256'], 'Changed exit receipt')
    report, auth, admission = read(run / 'report.json'), read(run / 'owner-authorization.json'), read(run / 'admission.json')
    require(report['passed'] and report['state'] == 'stopped-cleanly' and report['owner_stop_observed'], 'Worker did not close cleanly')
    require(not report.get('workload_failure') and not report.get('final_checkpoint_failure'), 'Worker failure prevents closeout')
    require(auth['firmware_sha256'] == IMAGE_SHA and auth['package_manifest_sha256'] == KIT_SHA, 'Wrong tested firmware')
    require(sha(auth['baseline_index']) == auth['baseline_index_sha256'] == BASELINE_SHA, 'Immutable RTC baseline changed')
    anchor = Q / '2609-RTC-owner-recovery-2026-10-18-r1/report.json'
    require(sha(anchor) == RECOVERY_SHA and auth['measurement_segment_2609'] == SEGMENT, '2609 recovery anchor changed')
    require(sha(run / 'owner-authorization.json') == admission['owner_authorization_sha256'], 'Changed run authorization')
    protected = {str(Path(path).resolve()): sha(path), str(run / 'report.json'): sha(run / 'report.json'),
                 str(Path(closure['worker_exit_receipt']).resolve()): closure['worker_exit_receipt_sha256'],
                 str(anchor): RECOVERY_SHA, str(run / 'admission.json'): sha(run / 'admission.json')}
    workload = read(run / 'workload-files.json')['files']
    for pins, base in ((admission['source_sha256'], run), (admission['source_evidence_sha256'], None), (workload, run)):
        for name, digest in pins.items():
            source = (base / name).resolve() if base else Path(name).resolve()
            require(sha(source) == digest, 'Changed frozen input: ' + str(source))
            protected[str(source)] = digest
    expected_pins = {'source': len(admission['source_sha256']), 'external': len(admission['source_evidence_sha256']), 'workload': len(workload)}
    require(closure['frozen_pins_verified'] == expected_pins, 'Closure pin counts differ')
    duration = closure['duration']
    for key in ('monitored_seconds', 'active_workload_seconds', 'periodic_checkpoint_seconds'):
        require(duration[key] >= 0 and abs(duration[key] - report[key]) < .01, 'Wrong duration')
    require(abs(duration['active_workload_seconds'] + duration['periodic_checkpoint_seconds'] - duration['monitored_seconds']) < .1, 'Inconsistent active duration')
    require(set(closure['boards']) == set(report['boards']) == {'2604', '2609'}, 'Both boards required')
    for board, value in closure['boards'].items():
        count = report['boards'][board]['passed_cycles']
        require(value['passed_cycles'] == count and count > 0, 'Wrong passed-unit count')
        require(value['LED_frames'] == 630 * count and value['LED_patterns_completed'] == 10 * count and value['breakpoint_hits'] == 16 * count, 'Wrong LED/debugger counts')
        require(all(value[k] for k in ('all_40_ASM_sources_covered', 'full_original_RAM_restored', 'RAM_verified_after_snapshot',
                                       'all_four_bank_flash_unchanged', 'settings_unchanged')), 'Incomplete original RAM/flash/settings restoration')
        require(len(value['flash_sha256']) == 4, 'All four flash banks required')
        require(value['original_RAM_sha256'] == sha(run / f'{board}-before/application-ram.bin'), 'Original RAM binding differs')
        rows = closure['source_cycle_receipts'][board]
        require(len(rows) == count, 'Missing successful cycle receipts')
        for number, entry in enumerate(rows):
            source = Path(entry['path']).resolve()
            require(source == run / board / f'{number:06d}/report.json' and sha(source) == entry['sha256'] and read(source)['passed'], 'Changed/nonpassing cycle receipt')
            protected[str(source)] = entry['sha256']
    require(report['final']['passed'] and report['final'] == read(run / 'checkpoints/final/report.json'), 'Missing final restoration proof')
    periodic = [c for c in report['checkpoints'] if c['label'].startswith('periodic-')]
    require(closure['periodic_checkpoint_count'] == len(periodic), 'Final snapshot cannot substitute for a periodic checkpoint')
    drift = closure['final_drift']
    require(sha(drift['summary']) == drift['summary_sha256'] and read(drift['summary'])['passed'], 'Final drift failed or changed')
    require(report['final']['drift']['summary_sha256'] == drift['summary_sha256'], 'Wrong end-of-soak snapshot')
    require({b['board'] for b in drift['boards']} == {'2604', '2609'}, 'Both final drift measurements required')
    protected[str(Path(drift['summary']).resolve())] = drift['summary_sha256']
    return run, closure, report, auth, admission, protected


def drift_summary(raw, add_source):
    """Public measurement values and source hashes; no private RAM or logs."""
    summary_path = Path(raw['summary'])
    require(sha(summary_path) == raw['summary_sha256'], 'Changed drift summary')
    summary = read(summary_path)
    require(summary['passed'] and summary['ports_released'] and not any(summary[k] for k in ('clock_set', 'trim_changed', 'flash_written')), 'Unsafe drift collection')
    add_source(summary_path)
    boards = []
    for value in summary['boards']:
        measurement_path = Path(value['report'])
        require(sha(measurement_path) == value['report_sha256'], 'Changed drift measurement')
        measurement = read(measurement_path)
        require(measurement['passed'] and value['application_ram_restored'], 'Drift RAM preservation failed')
        add_source(measurement_path)
        anchor = Path(measurement['compared_baseline'])
        baseline = read(Q / 'rtc-four-board-snapshot-2026-10-17-031840Z/baseline-index.json')
        expected_anchor = RECOVERY_SHA if value['board'] == '2609' else next(v['baseline_sha256'] for v in baseline['boards'] if v['board'] == value['board'])
        require(sha(anchor) == expected_anchor, 'Changed drift comparison anchor')
        add_source(anchor)
        row = {k: value[k] for k in ('board', 'reference_utc', 'offset_seconds', 'offset_bounds_seconds', 'elapsed_seconds')}
        row.update(measurement_sha256=value['report_sha256'], trim_steps=value['trim_steps'], control_register=value['control_register'],
                   drift_ppm_interval=measurement['drift_ppm_interval'], drift_seconds_per_day_interval=measurement['drift_seconds_per_day_interval'],
                   comparison_anchor=source_name(measurement['compared_baseline']),
                   comparison_anchor_reference_utc=read(measurement['compared_baseline'])['baseline_reference_utc'])
        if value['board'] == '2609':
            require(value['measurement_segment'] == SEGMENT and value['original_baseline_replaced'] is False and sha(value['comparison_anchor']) == RECOVERY_SHA, 'Wrong recovery segment')
            row.update(measurement_segment=SEGMENT, original_baseline_replaced=False)
        boards.append(row)
    return dict(passed=True, source_summary_sha256=raw['summary_sha256'], boards=boards,
                baseline_preserved=True, baseline_sha256=BASELINE_SHA, recovery_anchor_sha256=RECOVERY_SHA,
                clocks_trim_flash_unchanged=True, both_RAMs_preserved=True,
                rates_compare_recorded_anchors_not_checkpoint_interval=True)


def qualification(run, closure, report, auth, admission):
    sources = {}
    def add_source(path):
        key = source_name(path)
        sources[key] = dict(bytes=Path(path).stat().st_size, sha256=sha(path))
        return key
    for path in (run / 'monitor/final-closeout.json', run / 'report.json', run / 'admission.json', run / 'owner-authorization.json',
                 Path(closure['worker_exit_receipt'])):
        add_source(path)
    history, checkpoint_rows, current = [], [], run
    seen = set()
    while current not in seen:
        seen.add(current)
        current_auth, result = read(current / 'owner-authorization.json'), read(current / 'report.json')
        add_source(current / 'owner-authorization.json')
        add_source(current / 'report.json')
        row = dict(source_run=current.name, source_report_sha256=sha(current / 'report.json'), candidate=current_auth['candidate'],
                   state=result['state'], passed=result['passed'], authorized_hours=current_auth.get('hours'),
                   run_until_owner_stop=current_auth.get('run_until_owner_stop', False),
                   monitored_seconds=result['monitored_seconds'], active_workload_seconds=result.get('active_workload_seconds'),
                   passed_cycles={b: v['passed_cycles'] for b, v in result['boards'].items()},
                   workload_scope=result.get('workload', 'rc1/ASM/DBG1 fixed or varying-source predecessor'),
                   LED_frames_per_unit=current_auth.get('LED_frames_per_unit', 0),
                   LED_pattern_count=current_auth.get('LED_pattern_count', 3 if current_auth.get('LED_frames_per_unit') == 520 else 0),
                   owner_stop_observed=result.get('owner_stop_observed', False),
                   workload_or_harness_failure_recorded=bool(result.get('workload_failure')),
                   completed_fixed_duration=result.get('completed_authorized_duration'),
                   qualifies_current_ten_pattern_scope=current == run,
                   native_applications=False, native_debugging=False, promotion_held=True)
        if 'continuing-soak-r2-' in current.name:
            row['failure_classification'] = 'fixture-byte-normalization admission abort before first workload cycle'
        elif current.name == 'rc1-asm-dbg1-v1g-continuing-soak-2026-10-20-015328Z':
            row['failure_classification'] = 'test-harness physical-registry-ID-zero assertion; lifecycle invalidation rule corrected later'
        elif current_auth.get('hours') == 3:
            row['qualification_limit'] = 'owner-stopped before fixed duration; never a three-hour pass'
        final_boards = result.get('final', {}).get('boards', result.get('final', {}))
        row['both_original_RAMs_safely_restored'] = set(final_boards) == {'2604', '2609'} and all(
            b.get('passed') and b.get('RAM_restored_host_verified') and b.get('RAM_verified_after_snapshot') for b in final_boards.values())
        history.append(row)
        for entry in result.get('checkpoints', []):
            path = Path(entry['receipt'])
            require(sha(path) == entry['sha256'], 'Changed historical checkpoint')
            cp = read(path)
            add_source(path)
            value = dict(source_run=current.name, label=entry['label'], passed=cp['passed'],
                         source_receipt_sha256=entry['sha256'],
                         both_full_original_RAMs_restored=all(v.get('RAM_restored_host_verified') for v in cp['boards'].values()),
                         both_full_original_RAMs_reread_after_snapshot=all(v.get('RAM_verified_after_snapshot') for v in cp['boards'].values()))
            if cp.get('drift', {}).get('passed'):
                value['drift'] = drift_summary(cp['drift'], add_source)
            checkpoint_rows.append(value)
        if result.get('final_drift_snapshot', {}).get('passed'):
            checkpoint_rows.append(dict(source_run=current.name, label='final',
                receipt_kind='fixed-run-final-restoration-and-snapshot-not-a-periodic-checkpoint',
                passed=row['both_original_RAMs_safely_restored'], source_receipt_sha256=sha(current / 'report.json'),
                both_full_original_RAMs_restored=all(v['RAM_restored_host_verified'] for v in final_boards.values()),
                both_full_original_RAMs_reread_after_snapshot=all(v['RAM_verified_after_snapshot'] for v in final_boards.values()),
                drift=drift_summary(result['final_drift_snapshot'], add_source)))
        previous = current_auth.get('previous_run')
        if not previous:
            break
        current = Path(previous).resolve()
        require(current.is_relative_to(Q), 'Historical source escapes qualification directory')
    for board, rows in closure['source_cycle_receipts'].items():
        for value in rows:
            add_source(value['path'])
    final = drift_summary(report['final']['drift'], add_source)
    boards = {board: dict(value, runtime='65C02' if board == '2604' else '65C816 E=1',
                         native_debugging=False, native_applications=False) for board, value in closure['boards'].items()}
    summary = dict(passed=True, candidate_build='v1g-BRK82-84-edge-fix', firmware_sha256=IMAGE_SHA, package_manifest_sha256=KIT_SHA,
                   source_run=run.name, source_closure_sha256=sha(run / 'monitor/final-closeout.json'),
                   source_report_sha256=sha(run / 'report.json'), actual_worker_exit_verified=True, owner_requested_stop=True,
                   owner_stopped_continuation_passed=True, completed_fixed_duration_claimed=False,
                   duration=closure['duration'], boards=boards, LED_frames_per_unit=630, LED_pattern_count=10, LED_pattern_names=PATTERNS,
                   periodic_checkpoint_count=closure['periodic_checkpoint_count'], final_snapshot_is_periodic_checkpoint=False,
                   final_drift=final, frozen_pins_verified=closure['frozen_pins_verified'],
                   workload_failures=0, restoration_failures=0, inherited_results_substitute_for_current_run=False,
                   promotion_held=True, release_qualification_passed=False, native_debugging=False, native_applications=False)
    elapsed = lambda first, last: (datetime.fromisoformat(last.replace('Z', '+00:00')) - datetime.fromisoformat(first.replace('Z', '+00:00'))).total_seconds()
    summary['worker_timing'] = dict(started_utc=report['started_utc'], finished_utc=report['finished_utc'],
        total_wall_seconds=elapsed(report['started_utc'], report['finished_utc']),
        final_checkpoint_started_utc=report['final']['started_utc'], final_checkpoint_finished_utc=report['final']['finished_utc'],
        final_checkpoint_seconds=elapsed(report['final']['started_utc'], report['final']['finished_utc']),
        monitored_duration_excludes_final_checkpoint=True)
    offline = dict(passed=True, source_admission_sha256=sha(run / 'admission.json'), newly_executed_offline_tests=admission['newly_executed_offline_tests'],
                   new_LED_CPU_assemblies=admission['new_LED_CPU_assemblies'], new_LED_CPU_executions=admission['new_LED_CPU_executions'],
                   inherited_full_utility_CPU_model_units=admission['inherited_full_utility_CPU_model_units'],
                   inherited_isolated_ASM_CPU_executions=admission['inherited_isolated_ASM_CPU_executions'],
                   review_only_join_checks_not_added_to_qualification_counts=True, CPU_models={})
    for suffix in ('02', '816'):
        path = run / f'LED-CPU-{suffix}.json'
        proof = read(path)
        add_source(path)
        offline['CPU_models'][suffix] = dict(passed=proof['passed'], source_receipt_sha256=sha(path), CPU=proof['CPU'],
            onboard_assemblies=proof['onboard_assemblies'], full_LED_executions=proof['full_LED_executions'],
            patterns_per_execution=proof['patterns_per_execution'], frames_per_execution=proof['frames_per_execution'],
            executions=[dict(slot=v['slot'], seed=v['executed_seed'], name=v['executed_case'], cycles=v['physical_state']['cycles'],
                             original_LED_restored_before_BRK=v['physical_state']['physical_frames']['entry_latch_restored_before_BRK']) for v in proof['results']])
    histories = {}
    for name in ('offline-LED-qualification-history.json', 'inherited-LED3-qualification.json', 'inherited-broader-qualification.json', 'offline-qualification-history.json'):
        path = run / name
        add_source(path)
        histories[name] = dict(source_sha256=sha(path), scope='separate frozen qualification/development history; not a hardware workload failure')
    offline['frozen_history_sources'] = histories
    evidence = dict(source_run=run.name, source_closure_sha256=summary['source_closure_sha256'], source_report_sha256=summary['source_report_sha256'],
                    source_worker_exit_sha256=closure['worker_exit_receipt_sha256'], sources=sources,
                    current_successful_cycle_receipts={b: [dict(source=source_name(v['path']), sha256=v['sha256']) for v in rows] for b, rows in closure['source_cycle_receipts'].items()},
                    private_backups_or_serial_logs_exported=False, board_access_during_packaging=False)
    evidence['frozen_input_sha256'] = dict(
        source={source_name(run / name): digest for name, digest in admission['source_sha256'].items()},
        external={source_name(name): digest for name, digest in admission['source_evidence_sha256'].items()},
        workload={source_name(run / name): digest for name, digest in read(run / 'workload-files.json')['files'].items()})
    return summary, history, checkpoint_rows, offline, evidence


def build_verifier(base, out, bindings):
    source = (base / 'verify_package.py').read_text(encoding='utf-8')
    old = "m['distribution_revision']==5"
    require(old in source, 'Unexpected base verifier')
    source = source.replace(old, "m['distribution_revision']==6", 1)
    source = source.replace("m['hardware_qualified'] and not m['soak_qualified']", "m['hardware_qualified'] and m['soak_qualified']", 1)
    begin = source.index("    pending=READ(root/'qualification/soak/pending.json')")
    end = source.index('    return hw', begin)
    source = source[:begin] + "    verify_soak(root,summary)\n" + source[end:]
    source = source.replace("soak='running-not-qualified',final_drift='pending'", "soak='owner-stopped-passed',final_drift='passed'", 1)
    helper = (HERE / 'package-closed/verify_soak.inc').read_text(encoding='utf-8').replace('__SOAK_BINDINGS__', repr(bindings))
    source = source.replace("if __name__=='__main__':", helper + "\nif __name__=='__main__':", 1)
    (out / 'verify_package.py').write_text(source, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--docs-overlay', type=Path, required=True)
    args = parser.parse_args()
    run, closure, report, auth, admission, protected = verify_gate(args.closure)
    protected[str(Path(__file__).resolve())] = sha(__file__)
    protected[str(HERE / 'package-closed/verify_soak.inc')] = sha(HERE / 'package-closed/verify_soak.inc')
    protected[str(Q / 'rc1-dbg1-v1g-staging-current.json')] = sha(Q / 'rc1-dbg1-v1g-staging-current.json')
    pointer = read(Q / 'rc1-dbg1-v1g-staging-current.json')
    require(pointer['distribution_revision'] == 5 and pointer['promotion_held'], 'Expected immutable r5 staging input')
    base_report = read(pointer['package_report'])
    require(sha(pointer['package_report']) == pointer['package_report_sha256'] and sha(pointer['archive']) == pointer['archive_sha256'], 'Changed prior staging evidence')
    base = Path(base_report['distribution']).resolve()
    require(read(base / 'package-manifest.json')['distribution_revision'] == 5, 'Wrong prior distribution')
    out, record = args.out.resolve(), args.record.resolve()
    archive, checksum = Path(str(out) + '.zip'), Path(str(out) + '.zip.sha256')
    require(out.is_relative_to(ROOT / 'output/release/staging') and record.is_relative_to(Q), 'Output paths outside authorized staging workspace')
    require(not out.exists() and not archive.exists() and not checksum.exists() and not (record / 'package-report.json').exists(), 'Never overwrite a distribution/receipt')
    require(read(Q / 'rc1-dbg1-promotion-hold.json')['held'], 'Promotion must remain held')
    result = subprocess.run([sys.executable, '-B', str(base / 'verify_package.py')], capture_output=True, text=True)
    require(result.returncode == 0, 'Prior package failed verification: ' + result.stdout + result.stderr)
    immutable = {p.relative_to(base).as_posix(): sha(p) for p in base.rglob('*') if p.is_file()}
    protected.update({str(base / name): digest for name, digest in immutable.items()})
    protected.update({str(Path(pointer['archive'])): pointer['archive_sha256'], str(Path(pointer['package_report'])): pointer['package_report_sha256']})
    save(record / 'protected-inputs-before.json', protected)
    shutil.copytree(base, out, ignore=shutil.ignore_patterns('__pycache__'))
    overlay = args.docs_overlay.resolve()
    require(overlay.is_dir(), 'Reviewed package documentation overlay required')
    for path in sorted(overlay.rglob('*')):
        if path.is_file():
            relative = path.relative_to(overlay)
            require(path.suffix == '.md' and relative.parts[0] in ('README.md', 'INSTALL_ROLLBACK.md', 'docs', 'release'), 'Overlay may contain package Markdown only')
            protected[str(path)] = sha(path)
            destination = out / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    (out / 'qualification/soak/pending.json').unlink()
    summary, history, checkpoints, offline, evidence = qualification(run, closure, report, auth, admission)
    protected.update({str(ROOT / name): value['sha256'] for name, value in evidence['sources'].items()})
    for name, value in [('summary.json', summary), ('history.json', history), ('drift-checkpoints.json', checkpoints), ('offline.json', offline), ('source-evidence.json', evidence)]:
        save(out / 'qualification/soak' / name, value)
    diagnostic = out / 'diagnostics/led10'
    diagnostic.mkdir(parents=True)
    for path in sorted((run / 'led-sources').glob('*.asm')):
        shutil.copyfile(path, diagnostic / path.name)
    shutil.copyfile(run / 'LED-cases.json', diagnostic / 'cases.json')
    top = read(out / 'qualification/summary.json')
    top.update(soak_state='owner-stopped-passed', owner_stopped_continuation_passed=True, final_drift_snapshot_passed=True,
               three_hour_soak_passed=None, six_hour_soak_passed=None, pending=['explicit-promotion-decision'])
    save(out / 'qualification/summary.json', top)
    bindings = {p.relative_to(out).as_posix(): sha(p) for p in (out / 'qualification/soak').glob('*.json')}
    bindings.update({p.relative_to(out).as_posix(): sha(p) for p in diagnostic.iterdir() if p.is_file()})
    build_verifier(base, out, bindings)
    for name, digest in immutable.items():
        if name.startswith(('firmware/', 'install/', 'source/debugger/')):
            require(sha(out / name) == digest, 'Tested firmware/installer/source bytes changed')
    # Tested manual examples retain their original exact-source bindings.
    for path in (out / 'qualification/offline').glob('debugger-test*-manuals.json'):
        for name, digest in read(path)['manual_sources_sha256'].items():
            require(sha(out / 'docs/rc1' / name) == digest, 'Tested manual must remain byte-exact: ' + name)
    sys.path.insert(0, str(ROOT / 'tools'))
    from audit_rc1_dbg_docs import audit
    docs = audit(out, list(out.rglob('*.md')))
    require(docs['passed'], 'Package documentation links failed: ' + str(docs['errors']))
    save(out / 'qualification/documentation-audit.json', docs)
    files = {}
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.name in ('package-manifest.json', 'SHA256SUMS.txt'):
            continue
        name = path.relative_to(out).as_posix()
        require(not any(part in ('__pycache__', 'private', 'capture', 'before', 'after') for part in path.relative_to(out).parts) and path.suffix not in ('.jsonl', '.pyc', '.zip'), 'Private/cache artifact included')
        if path.suffix in ('.py', '.md', '.json', '.txt', '.asm'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/', path.read_text(encoding='utf-8')), 'Host path leaked: ' + name)
        files[name] = dict(bytes=path.stat().st_size, sha256=sha(path))
    manifest = read(base / 'package-manifest.json')
    manifest.update(distribution_revision=6, soak_qualified=True, soak_scope='owner-stopped-R6-ten-pattern-continuation',
                    final_drift_passed=True, promotion_held=True, staged_utc=datetime.now(timezone.utc).isoformat(),
                    package_markdown_links_checked=docs['links_and_anchors_checked'], files=files)
    save(out / 'package-manifest.json', manifest)
    sums = dict(files)
    sums['package-manifest.json'] = dict(bytes=(out / 'package-manifest.json').stat().st_size, sha256=sha(out / 'package-manifest.json'))
    (out / 'SHA256SUMS.txt').write_text(''.join(v['sha256'] + '  ' + k + '\n' for k, v in sorted(sums.items())), encoding='ascii')
    check = subprocess.run([sys.executable, '-B', str(out / 'verify_package.py')], capture_output=True, text=True)
    require(check.returncode == 0, check.stdout + check.stderr)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in sorted([*sums, 'SHA256SUMS.txt']):
            info = zipfile.ZipInfo(out.name + '/' + name, date_time=(2026, 10, 20, 0, 0, 0))
            info.create_system, info.external_attr, info.compress_type = 3, 0o100644 << 16, zipfile.ZIP_DEFLATED
            zipped.writestr(info, (out / name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='dbg-v1g-r6-extract-', dir=ROOT / 'tmp') as folder:
        with zipfile.ZipFile(archive) as zipped:
            require(zipped.testzip() is None, 'Archive CRC failure')
            zipped.extractall(folder)
        extracted = subprocess.run([sys.executable, '-B', str(Path(folder) / out.name / 'verify_package.py')], capture_output=True, text=True)
        require(extracted.returncode == 0, extracted.stdout + extracted.stderr)
    checksum.write_text(sha(archive) + '  ' + archive.name + '\n', encoding='ascii')
    for path, digest in protected.items():
        require(sha(path) == digest, 'Protected input changed during staging: ' + path)
    result = dict(integrity_passed=True, hardware_requalification_passed=True, soak_qualified=True,
                  soak='owner-stopped-passed', final_drift='passed', promotion_held=True, release_qualification_passed=False,
                  firmware_sha256=IMAGE_SHA, tested_kit_manifest_sha256=KIT_SHA, distribution_revision=6,
                  source_final_closeout_sha256=sha(args.closure), archive=str(archive), archive_sha256=sha(archive),
                  archive_bytes=archive.stat().st_size, archive_checksum=str(checksum), distribution=str(out),
                  package_manifest_sha256=sha(out / 'package-manifest.json'), files_verified=len(sums) + 1,
                  markdown_links_and_anchors_checked=docs['links_and_anchors_checked'], extracted_archive_verified=True,
                  protected_files_verified=len(protected), board_access=False, native_debugging=False, native_applications_tested=False)
    result.update(stager_sha256=sha(__file__), semantic_verifier_template_sha256=sha(HERE / 'package-closed/verify_soak.inc'),
                  package_verifier_sha256=sha(out / 'verify_package.py'),
                  documentation_overlay_sha256={p.relative_to(overlay).as_posix(): sha(p) for p in overlay.rglob('*.md')})
    save(record / 'package-report.json', result)
    save(record / 'staging-pointer.json', dict(run=str(record), package_report=str(record / 'package-report.json'),
         package_report_sha256=sha(record / 'package-report.json'), archive=str(archive), archive_sha256=sha(archive),
         candidate_build='v1g-BRK82-84-edge-fix', distribution_revision=6, offline_qualification_passed=True,
         hardware_qualified=True, soak_qualified=True, soak='owner-stopped-passed', final_drift='passed', promotion_held=True, native_debugging=False))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit('REFUSED: ' + str(error))
