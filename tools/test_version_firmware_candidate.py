"""Verify the separate optimized VERSION firmware package entirely offline."""
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile

from test_resident_contract import ATTEMPTS, sha
from test_resident_batch import files, refused
import package_version_firmware_candidate as package


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def host_checks(build, prepared, out):
    repeated = out / 'repeat'
    package.run(build, repeated)
    assert files(prepared) == files(repeated), 'Package must reproduce byte for byte, including ZIP'
    before = files(repeated)
    refused(lambda: package.run(build, repeated))
    assert files(repeated) == before
    checks = ['deterministic-package-manifest-and-zip', 'existing-output-refused-unchanged']
    scratch = out / 'tampered'
    shutil.copytree(prepared, scratch)
    for relative in files(scratch):
        path = scratch / relative
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused(lambda: package.validate_package(build, scratch))
        path.write_bytes(raw)
        checks.append('tampered-' + relative + '-refused')
    (scratch / 'extra.bin').write_bytes(b'unexpected')
    refused(lambda: package.validate_package(build, scratch))
    (scratch / 'extra.bin').unlink()
    checks.append('unexpected-package-member-refused')
    manifest_path = scratch / 'candidate-manifest.json'
    original_manifest = manifest_path.read_bytes()
    changed_manifest = json.loads(original_manifest)
    changed_manifest['installation_permitted'] = True
    save(manifest_path, changed_manifest)
    refused(lambda: package.validate_package(build, scratch))
    manifest_path.write_bytes(original_manifest)
    checks.append('changed-installation-scope-refused')
    package.validate_package(build, scratch)
    archive = out / 'extracted'
    archive.mkdir()
    with zipfile.ZipFile(prepared / 'candidate.zip') as source:
        assert source.testzip() is None
        for member in source.infolist():
            destination = (archive / member.filename).resolve()
            assert destination.is_relative_to(archive.resolve()) and not member.is_dir()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read(member))
            assert destination.read_bytes() == (prepared / member.filename).read_bytes()
    checks.append('archive-members-and-bytes-equal-loose-package')
    stale = out / 'stale'
    shutil.copytree(build, stale)
    image_path = stale / 'firmware.bin'
    image = bytearray(image_path.read_bytes())
    image[0] ^= 1
    image_path.write_bytes(image)
    destination = out / 'refused-build'
    refused(lambda: package.run(stale, destination))
    assert not destination.exists()
    checks.append('changed-baseline-firmware-refused-before-output')
    from installer import package as installer_package
    from installer.common import REGISTRY
    assert package.CANDIDATE_ID not in REGISTRY['candidates']
    destination = out / 'unregistered-kit'
    refused(lambda: installer_package.create(destination, package.CANDIDATE_ID,
        {package.CANDIDATE_ID: prepared / 'firmware.bin', 'asm-dev': build / 'firmware.bin'}))
    assert not destination.exists()
    checks.append('existing-installer-refuses-unregistered-candidate-before-output')
    destination = out / 'relabeled-kit'
    refused(lambda: installer_package.create(destination, 'asm-dev',
        {'asm-dev': prepared / 'firmware.bin', 'release-r9': build / 'firmware.bin'}))
    assert not destination.exists()
    checks.append('existing-installer-refuses-new-bytes-under-current-identity-before-output')
    for protected in (ROOT / 'src/current', ROOT / 'release', ROOT / 'tests', build, prepared):
        refused(lambda: package.run(build, protected))
    checks.append('protected-and-input-output-paths-refused')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'package', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=('static', 'runtime', 'all'), default='all')
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    args = parser.parse_args()
    build, prepared, out = args.build.resolve(), args.package.resolve(), args.out.resolve()
    assert out.is_relative_to(ROOT) and out != ROOT and not out.exists()
    assert not any(out.is_relative_to(ROOT / part) for part in
        ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws'))
    assert not any(out.is_relative_to(path) or path.is_relative_to(out) for path in (build, prepared))
    manifest = package.validate_package(build, prepared)
    inputs = package.verified_inputs(build)
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    checks = host_checks(build, prepared, out) if args.mode in ('static', 'all') else []
    runtime = []
    if args.mode in ('runtime', 'all'):
        os.environ['STR8_SOURCE_BUILD'] = str(build)
        from test_rc1_source_store import Harness
        from test_version_firmware_candidate_runtime import packaged_checks
        for cpu in args.cpu or ('65c02', '65c816-e'):
            for slot in ('A', 'B'):
                for edu in (False, True):
                    profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                    result = packaged_checks(Harness, cpu, slot, edu,
                        inputs['baseline_firmware'], (prepared / 'firmware.bin').read_bytes(),
                        inputs['baseline_body'], (prepared / 'version/resident.bin').read_bytes(),
                        inputs['version_symbols'])
                    assert result['passed']
                    runtime.append(dict(cpu=cpu, slot=slot, edu=edu, **result))
                    save(out / (profile + '-runtime.json'), result)
                    save(out / 'progress.json', dict(runtime=runtime, attempts=ATTEMPTS))
                    print('PASS', profile, 'packaged loader and VERSION', flush=True)
    assert not ATTEMPTS
    helpers = ['package_version_firmware_candidate.py', 'test_resident_contract.py',
               'test_resident_batch.py', 'test_rc1_source_store.py']
    if args.mode in ('runtime', 'all'):
        helpers += ['test_version_firmware_candidate_runtime.py', 'test_resident_version_runtime.py',
                    'test_resident_version_candidate_runtime.py']
    save(out / 'report.json', dict(passed=True, mode=args.mode, board_access=False,
        serial_ports_opened=0, network_attempts=0, hardware_qualified=False,
        installation_permitted=False, resident_output_installed=False, ram_substitution=False,
        candidate_id=package.CANDIDATE_ID,
        package_manifest_sha256=sha((prepared / 'candidate-manifest.json').read_bytes()),
        package_zip_sha256=sha((prepared / 'candidate.zip').read_bytes()),
        firmware_sha256=sha((prepared / 'firmware.bin').read_bytes()),
        source_test_sha256=sha(Path(__file__).read_bytes()),
        helper_sha256={name: sha((ROOT / 'tools' / name).read_bytes()) for name in helpers},
        inherited_phase10_baseline_sha256=sha((ROOT / 'tests/baselines/phase10.json').read_bytes()),
        static_checks=checks, runtime_configuration_count=len(runtime), runtime_cases=runtime,
        model_scope='Actual packaged ROM assets loaded and validated by linked monitor instructions; '
                    'no candidate RAM substitution, hardware discovery/delay shortcuts retained; '
                    'monitor-slot initialization rather than physical cold-reset qualification', attempts=ATTEMPTS))
    print('PASS optimized VERSION firmware package:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
