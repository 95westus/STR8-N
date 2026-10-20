"""Derive immutable distribution r7 from r6 for a documentation timing erratum.

The tested firmware, installer and all qualification receipts remain byte exact.
No ports, firmware builds, Git operations or publication occur here.
"""
import argparse
from datetime import datetime, timezone
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
BASE_ARCHIVE_SHA = '9a1cf7b876ea0c4afbb86717eb3fd5093762f2ae82a94aaf16aba2dd8b7b5c1c'
BASE_MANIFEST_SHA = 'ab460475cd4700ff31b489c6985a8eb618f5331d13c2cf482f2fd80ccae0c67a'
ORIGINAL_STAGER_SHA = '52f3b046ee0ca3b05ff3ba77d7bf8ac4a34055eb5bdff2090180d33a4b50dcc9'
BEFORE = 'campaign phase; R6 reached only final drift before owner stop. Any future'
AFTER = 'campaign phase; R6 completed its final checkpoint during owner-stop closure. Any future'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-report', type=Path, required=True)
    parser.add_argument('--docs-overlay', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('original_immutable_r6_stager', HERE / 'stage_soak_closeout.py')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    require, read, sha, save = prior.require, prior.read, prior.sha, prior.save
    require(sha(HERE / 'stage_soak_closeout.py') == ORIGINAL_STAGER_SHA, 'Changed original r6 stager')
    run, closure, report, auth, admission, protected = prior.verify_gate(Q / prior.R6_NAME / 'monitor/final-closeout.json')
    require(read(Q / 'rc1-dbg1-promotion-hold.json')['held'], 'Promotion must stay held')
    base_report = read(args.base_report)
    base = Path(base_report['distribution']).resolve()
    archive_before = Path(base_report['archive']).resolve()
    require(base_report['distribution_revision'] == 6 and base_report['integrity_passed'] and base_report['promotion_held'], 'Wrong prior staging report')
    require(sha(archive_before) == base_report['archive_sha256'] == BASE_ARCHIVE_SHA
            and sha(base / 'package-manifest.json') == base_report['package_manifest_sha256'] == BASE_MANIFEST_SHA, 'Changed immutable r6 package')
    command = [sys.executable, '-B', str(base / 'verify_package.py')]
    check = subprocess.run(command, capture_output=True, text=True)
    require(check.returncode == 0, check.stdout + check.stderr)
    protected.update({str(p): sha(p) for p in base.rglob('*') if p.is_file()})
    for path in (Path(__file__).resolve(), HERE / 'stage_soak_closeout.py', args.base_report.resolve(), archive_before,
                 Path(str(archive_before) + '.sha256')):
        protected[str(path)] = sha(path)
    original_files = read(base / 'package-manifest.json')['files']
    overlay, out, record = args.docs_overlay.resolve(), args.out.resolve(), args.record.resolve()
    archive, checksum = Path(str(out) + '.zip'), Path(str(out) + '.zip.sha256')
    require(out.is_relative_to(ROOT / 'output/release/staging') and record.is_relative_to(Q), 'Unsafe output location')
    require(not any(p.exists() for p in (out, archive, checksum, record / 'package-report.json')), 'Never overwrite an immutable staging result')
    overlay_files = {p.relative_to(overlay).as_posix(): p for p in overlay.rglob('*') if p.is_file()}
    require(set(overlay_files) == set(base_report['documentation_overlay_sha256']), 'Unexpected documentation overlay inventory')
    for name, path in overlay_files.items():
        require(path.suffix == '.md' and name in original_files, 'Erratum overlay may change existing Markdown only')
        protected[str(path)] = sha(path)
    before = (base / 'docs/rc1/OPERATOR_GUIDE.md').read_text(encoding='utf-8')
    after = overlay_files['docs/rc1/OPERATOR_GUIDE.md'].read_text(encoding='utf-8')
    require(before.count(BEFORE) == 1 and after == before.replace(BEFORE, AFTER), 'Unexpected operator timing edit')
    shutil.copytree(base, out)
    for name, path in overlay_files.items():
        shutil.copyfile(path, out / name)
    erratum = dict(passed=True, classification='package-documentation-timing-correction', prior_distribution_revision=6,
        distribution_revision=7, prior_archive_sha256=BASE_ARCHIVE_SHA, prior_manifest_sha256=BASE_MANIFEST_SHA,
        source_closeout_sha256=prior.CLOSURE_SHA, corrected_document='docs/rc1/OPERATOR_GUIDE.md',
        old_sentence_fragment=BEFORE, corrected_sentence_fragment=AFTER,
        other_documentation_changes='distribution revision labels and an explicit erratum note',
        firmware_installer_and_qualification_bytes_unchanged=True, hardware_or_workload_failure=False,
        new_hardware_execution=False, promotion_held=True, native_debugging=False, native_applications=False)
    save(out / 'qualification/documentation-erratum.json', erratum)
    verifier = (base / 'verify_package.py').read_text(encoding='utf-8')
    require(verifier.count("m['distribution_revision']==6") == 1, 'Unexpected prior verifier revision guard')
    verifier = verifier.replace("m['distribution_revision']==6", "m['distribution_revision']==7", 1)
    hook = "    summary=READ(root/'qualification/summary.json');offline=READ(root/'qualification/offline/summary.json')"
    require(verifier.count(hook) == 1, 'Unexpected prior verifier structure')
    verifier = verifier.replace(hook, "    require(SHA(root/'qualification/documentation-erratum.json')=='" + sha(out / 'qualification/documentation-erratum.json') + "','Changed documentation erratum')\n" + hook, 1)
    (out / 'verify_package.py').write_text(verifier, encoding='utf-8')
    sys.path.insert(0, str(ROOT / 'tools'))
    from audit_rc1_dbg_docs import audit
    docs = audit(out, list(out.rglob('*.md')))
    require(docs['passed'], str(docs['errors']))
    save(out / 'qualification/documentation-audit.json', docs)
    allowed = set(overlay_files) | {'verify_package.py', 'qualification/documentation-audit.json'}
    for name, info in original_files.items():
        if name not in allowed:
            require(sha(out / name) == info['sha256'], 'Erratum changed tested bytes: ' + name)
    inventory = {}
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.name in ('package-manifest.json', 'SHA256SUMS.txt'):
            continue
        name = path.relative_to(out).as_posix()
        require(not any(p in ('__pycache__', 'private', 'capture', 'before', 'after') for p in path.relative_to(out).parts)
                and path.suffix not in ('.jsonl', '.pyc', '.zip'), 'Private artifact in package')
        if path.suffix in ('.py', '.md', '.json', '.txt', '.asm'):
            require(not re.search(r'[A-Za-z]:[\\/](?:SRC|Users)[\\/]|/Users/|/home/', path.read_text(encoding='utf-8')), 'Host path leaked: ' + name)
        inventory[name] = dict(bytes=path.stat().st_size, sha256=sha(path))
    manifest = read(base / 'package-manifest.json')
    manifest.update(distribution_revision=7, staged_utc=datetime.now(timezone.utc).isoformat(),
                    documentation_erratum='qualification/documentation-erratum.json',
                    package_markdown_links_checked=docs['links_and_anchors_checked'], files=inventory)
    save(out / 'package-manifest.json', manifest)
    sums = dict(inventory)
    sums['package-manifest.json'] = dict(sha256=sha(out / 'package-manifest.json'))
    (out / 'SHA256SUMS.txt').write_text(''.join(v['sha256'] + '  ' + name + '\n' for name, v in sorted(sums.items())), encoding='ascii')
    check = subprocess.run([sys.executable, '-B', str(out / 'verify_package.py')], capture_output=True, text=True)
    require(check.returncode == 0, check.stdout + check.stderr)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in sorted([*sums, 'SHA256SUMS.txt']):
            info = zipfile.ZipInfo(out.name + '/' + name, date_time=(2026, 10, 20, 0, 0, 0))
            info.create_system, info.external_attr, info.compress_type = 3, 0o100644 << 16, zipfile.ZIP_DEFLATED
            zipped.writestr(info, (out / name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='dbg-r7-extract-', dir=ROOT / 'tmp') as temporary:
        require(Path(temporary).resolve().is_relative_to((ROOT / 'tmp').resolve()), 'Unsafe temporary extraction path')
        with zipfile.ZipFile(archive) as zipped:
            require(zipped.testzip() is None, 'Archive CRC failed')
            zipped.extractall(temporary)
        extracted = subprocess.run([sys.executable, '-B', str(Path(temporary) / out.name / 'verify_package.py')], capture_output=True, text=True)
        require(extracted.returncode == 0, extracted.stdout + extracted.stderr)
    checksum.write_text(sha(archive) + '  ' + archive.name + '\n', encoding='ascii')
    for path, digest in protected.items():
        require(sha(path) == digest, 'Protected evidence changed: ' + path)
    result = dict(base_report)
    result.update(distribution_revision=7, documentation_erratum=True, prior_archive_sha256=BASE_ARCHIVE_SHA,
        archive=str(archive), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size, archive_checksum=str(checksum),
        distribution=str(out), package_manifest_sha256=sha(out / 'package-manifest.json'), files_verified=len(sums) + 1,
        markdown_links_and_anchors_checked=docs['links_and_anchors_checked'], extracted_archive_verified=True,
        protected_files_verified=len(protected), stager_sha256=sha(__file__), prior_stager_sha256=ORIGINAL_STAGER_SHA,
        package_verifier_sha256=sha(out / 'verify_package.py'),
        documentation_overlay_sha256={name: sha(path) for name, path in overlay_files.items()})
    save(record / 'documentation-erratum.json', erratum)
    save(record / 'package-report.json', result)
    save(record / 'staging-pointer.json', dict(run=str(record), package_report=str(record / 'package-report.json'),
        package_report_sha256=sha(record / 'package-report.json'), archive=str(archive), archive_sha256=sha(archive),
        candidate_build='v1g-BRK82-84-edge-fix', distribution_revision=7, offline_qualification_passed=True,
        hardware_qualified=True, soak_qualified=True, soak='owner-stopped-passed', final_drift='passed', promotion_held=True, native_debugging=False))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit('REFUSED: ' + str(error))
