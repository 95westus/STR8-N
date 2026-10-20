"""Verify the closed-soak distribution and reject resealed false qualification.

Uses copied files in a disposable workspace directory; never opens a board port.
The package verifier is loaded from the original package before any mutation.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modify(root, name, change):
    path = root / name
    value = read(path)
    change(value)
    save(path, value)


def reseal(root):
    """An attacker may recompute public checksums; frozen proof pins still bind."""
    manifest = read(root / 'package-manifest.json')
    manifest['files'] = {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
                         for p in sorted(root.rglob('*')) if p.is_file()
                         and p.name not in ('package-manifest.json', 'SHA256SUMS.txt')}
    save(root / 'package-manifest.json', manifest)
    inventory = dict(manifest['files'])
    inventory['package-manifest.json'] = dict(sha256=sha(root / 'package-manifest.json'))
    (root / 'SHA256SUMS.txt').write_text(''.join(value['sha256'] + '  ' + name + '\n'
                                              for name, value in sorted(inventory.items())), encoding='ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    spec = importlib.util.spec_from_file_location('immutable_closed_package_verifier', package / 'verify_package.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    result = verifier.verify(package)
    assert result['integrity_passed'] and result['soak'] == 'owner-stopped-passed' and result['final_drift'] == 'passed'
    checks = [dict(name='original-package', passed=True)]
    manifest = lambda field, value: lambda root: modify(root, 'package-manifest.json', lambda m: m.__setitem__(field, value))
    top = lambda field, value: lambda root: modify(root, 'qualification/summary.json', lambda m: m.__setitem__(field, value))
    closed = lambda field, value: lambda root: modify(root, 'qualification/soak/summary.json', lambda m: m.__setitem__(field, value))
    cases = [
        ('release-promotion', manifest('promotion_held', False)),
        ('native-debugging', manifest('native_debugging', True)),
        ('native-application', manifest('native_applications_tested', True)),
        ('soak-not-qualified', manifest('soak_qualified', False)),
        ('revision-regression', manifest('distribution_revision', 5)),
        ('manifest-missing-final-drift', manifest('final_drift_passed', False)),
        ('false-fixed-three-hour-pass', top('three_hour_soak_passed', True)),
        ('false-fixed-six-hour-pass', top('six_hour_soak_passed', True)),
        ('missing-final-drift', top('final_drift_snapshot_passed', False)),
        ('premature-release', top('release_qualification_passed', True)),
        ('missing-promotion-hold', top('pending', [])),
        ('changed-unit-count', lambda r: modify(r, 'qualification/soak/summary.json', lambda m: m['boards']['2604'].__setitem__('passed_cycles', 62))),
        ('unrestored-original-RAM', lambda r: modify(r, 'qualification/soak/summary.json', lambda m: m['boards']['2609'].__setitem__('full_original_RAM_restored', False))),
        ('changed-drift-baseline', lambda r: modify(r, 'qualification/soak/summary.json', lambda m: m['final_drift'].__setitem__('baseline_sha256', '0' * 64))),
        ('final-as-periodic-snapshot', closed('periodic_checkpoint_count', 1)),
        ('native-soak-claim', closed('native_debugging', True)),
        ('prior-run-substitution', closed('inherited_results_substitute_for_current_run', True)),
        ('changed-offline-count', lambda r: modify(r, 'qualification/soak/offline.json', lambda m: m.__setitem__('newly_executed_offline_tests', 109))),
        ('changed-source-evidence', lambda r: modify(r, 'qualification/soak/source-evidence.json', lambda m: m.__setitem__('source_worker_exit_sha256', '0' * 64))),
        ('changed-led-source', lambda r: (r / 'diagnostics/led10/led-ten-patterns-12.asm').write_text('; changed\n', encoding='utf-8')),
        ('changed-tested-firmware', lambda r: (r / 'firmware/debugger-a000.bin').write_bytes(bytes(4096))),
        ('changed-tested-manual', lambda r: (r / 'docs/rc1/ASM_GUIDE.md').write_text('changed\n', encoding='utf-8')),
        ('private-extra-file', lambda r: (r / 'private-application-ram.bin').write_bytes(b'private')),
    ]
    with tempfile.TemporaryDirectory(prefix='dbg-closed-package-tests-', dir=ROOT / 'tmp') as temporary:
        trial = Path(temporary) / 'package'
        for name, mutate in cases:
            shutil.copytree(package, trial)
            try:
                mutate(trial)
                # Extra-file refusal tests the original inventory instead of granting admission.
                if name != 'private-extra-file':
                    reseal(trial)
                try:
                    verifier.verify(trial)
                except (ValueError, KeyError, OSError) as error:
                    checks.append(dict(name=name, passed=True, refused=str(error)))
                else:
                    raise AssertionError('Accepted forged package: ' + name)
            finally:
                assert Path(temporary).resolve().is_relative_to((ROOT / 'tmp').resolve()), 'Temporary root escaped workspace'
                assert trial.resolve().is_relative_to(Path(temporary).resolve()), 'Recursive cleanup escaped temporary root'
                shutil.rmtree(trial)
    report = dict(passed=True, checks=checks, check_count=len(checks), package_manifest_sha256=sha(package / 'package-manifest.json'),
                  verifier_sha256=sha(package / 'verify_package.py'), board_access=False, native_debugging=False,
                  promotion_held=True, mutation_scope='disposable copies only')
    if args.out:
        assert not args.out.exists(), 'Do not overwrite a test receipt'
        args.out.parent.mkdir(parents=True, exist_ok=True)
        save(args.out, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
