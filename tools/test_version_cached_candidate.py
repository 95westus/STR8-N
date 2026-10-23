"""Assemble, package and verify the separate cached-name VERSION revision offline."""
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile

from test_resident_contract import ATTEMPTS, parse_s19, sha
from test_resident_batch import canonical, files, refused
import version_cached_candidate as candidate


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def receipt(prepared):
    return dict(passed=True, board_access=False, serial_ports_opened=0, network_attempts=0,
        hardware_qualified=False, installation_permitted=False, resident_output_installed=False,
        source_test_sha256=sha(Path(__file__).read_bytes()),
        preparation_tool_sha256=sha(Path(candidate.__file__).read_bytes()),
        prepared_manifest_sha256=sha((prepared / 'manifest.json').read_bytes()),
        output_sha256=candidate.BODY_SHA, attempts=ATTEMPTS)


def assembly_checks(build, prepared, out, cpus):
    data = candidate.validate_prepared(build, prepared)
    expected, symbols, records = data['body'], data['symbols'], data['records']
    assert len(expected) == 636 and len(symbols) == 65 and symbols['BN_SHOW_CACHED'] == 0x7047
    assert canonical(records) == records
    originals = json.loads((build / 'symbols.json').read_text())['version/version']
    aliases = {'BOOT_CHOICE_SLOT': 'BOOT_CHOICE', 'BAD_RUNNING_TEXT': 'BAD_RUN_TEXT'}
    os.environ['STR8_SOURCE_BUILD'] = str(build)
    from test_rc1_source_store import Harness
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for cpu in cpus:
        for slot in ('A', 'B'):
            for edu in (False, True):
                profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                h = Harness(cpu, slot, edu=edu)
                h.open()
                h.command_limit = 30000000
                flash, upper = list(map(bytes, h.m.banks)), bytes(h.m.ram[0x6500:0x7B00])
                transfers = len(h.m.transfers)
                step = h.cpu.step

                def guarded_step():
                    assert not 0x0200 <= h.cpu.pc < 0x3300, 'Assembler output must not execute'
                    return step()

                h.cpu.step = guarded_step
                h.command((prepared / 'version.paste.txt').read_bytes().decode('ascii').rstrip('\r'))
                assert h.source() == records
                for _ in range(2):
                    text = h.command('ASM', contains='OK ')
                    assert 'ORG differs' in text and 'S 1 AUTO' not in text
                    assert h.m.ram[0x6306] == 1
                    assert int.from_bytes(h.m.ram[0x6302:0x6304], 'little') == 636
                    assert int.from_bytes(h.m.ram[0x6304:0x6306], 'little') == 0x6E00
                    body = bytes(h.m.ram[0x0200:0x047C])
                    assert body == expected and canonical(h.source()) == records
                    top = int.from_bytes(h.m.ram[h.asm['SYMTOP']:h.asm['SYMTOP'] + 2], 'little')
                    table = bytes(h.m.ram[0x4F00:top])
                    assert len(table) == 65 * 20
                    actual = {table[i:i + 16].rstrip(b'\0').decode('ascii'):
                              int.from_bytes(table[i + 16:i + 18], 'little')
                              for i in range(0, len(table), 20)}
                    assert actual == symbols
                    assert all(actual[aliases.get(name, name)] == value for name, value in originals.items()
                               if not name.startswith('_'))
                text = h.command('SYMS')
                assert all(name in text for name in symbols)
                export = h.command('S19')
                cells, entry = parse_s19(export)
                assert cells == data['cells'] and entry == 0x6E00
                assert list(map(bytes, h.m.banks)) == flash and not h.m.flash_writes
                assert bytes(h.m.ram[0x6500:0x7B00]) == upper and len(h.m.transfers) == transfers
                (out / (profile + '.bin')).write_bytes(body)
                (out / (profile + '.s19.txt')).write_text(export, encoding='ascii')
                save(out / (profile + '-transcript.json'), h.transcripts)
                rows.append(dict(cpu=cpu, slot=slot, edu=edu, passed=True, assemblies=2,
                    output_bytes=636, output_sha256=sha(body), origin=0x6E00, executable_entry=0x6E04,
                    symbols=actual, s19_data_equal=True, s19_entry=entry,
                    all_original_symbol_values_equal=True, modeled_flash_unchanged=True,
                    upper_ram_unchanged=True, source_records_bytes=len(records)))
                print('PASS', profile, 'resident ASM: 636 bytes, 65 symbols', flush=True)
                save(out / 'progress.json', dict(assembly_cases=rows, attempts=ATTEMPTS))
    assert not ATTEMPTS
    result = dict(**receipt(prepared), mode='assembly', assembly_configuration_count=len(rows),
                  assembly_cases=rows, physical_output_executed=False)
    save(out / 'report.json', result)
    return result


def static_checks(build, prepared, assemblies, packaged, out):
    original = candidate.validate_prepared(build, prepared)
    repeated = out / 'prep'
    candidate.prepare(build, repeated)
    repeated_data = candidate.validate_prepared(build, repeated)
    assert all((prepared / name).read_bytes() == (repeated / name).read_bytes()
               for name in ('version.asm', 'version.paste.txt', 'version.records.bin', 'expected.bin'))
    assert original['symbols'] == repeated_data['symbols'] and original['cells'] == repeated_data['cells']
    checks = ['deterministic-resident-source-records-host-body-and-symbols']
    prior = files(repeated)
    refused(lambda: candidate.prepare(build, repeated))
    assert files(repeated) == prior
    checks.append('existing-preparation-refused-unchanged')
    scratch = out / 'bad-prep'
    shutil.copytree(prepared, scratch)
    for relative in ('version.asm', 'version.paste.txt', 'version.records.bin', 'expected.bin',
                     'host/version.s19', 'host/version.map'):
        path = scratch / relative
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused(lambda: candidate.validate_prepared(build, scratch))
        path.write_bytes(raw)
        checks.append('tampered-prepared-' + relative + '-refused')
    repeated_package = out / 'pkg'
    candidate.package(build, prepared, assemblies, repeated_package)
    assert files(packaged) == files(repeated_package)
    checks.append('deterministic-entire-package-including-zip')
    prior = files(repeated_package)
    refused(lambda: candidate.package(build, prepared, assemblies, repeated_package))
    assert files(repeated_package) == prior
    checks.append('existing-package-refused-unchanged')
    scratch = out / 'bad-pkg'
    shutil.copytree(packaged, scratch)
    for relative in files(scratch):
        path = scratch / relative
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused(lambda: candidate.validate_package(build, prepared, assemblies, scratch))
        path.write_bytes(raw)
        checks.append('tampered-package-' + relative + '-refused')
    (scratch / 'extra.bin').write_bytes(b'unexpected')
    refused(lambda: candidate.validate_package(build, prepared, assemblies, scratch))
    (scratch / 'extra.bin').unlink()
    checks.append('unexpected-package-member-refused')
    with zipfile.ZipFile(packaged / 'candidate.zip') as archive:
        assert archive.testzip() is None
        assert all(archive.read(name) == (packaged / name).read_bytes() for name in archive.namelist())
    checks.append('archive-content-equals-loose-package')
    from installer import package as installer_package
    from installer.common import REGISTRY
    assert candidate.CANDIDATE_ID not in REGISTRY['candidates']
    for identity in (candidate.CANDIDATE_ID, 'asm-dev'):
        destination = out / ('refused-' + identity)
        images = {identity: packaged / 'firmware.bin', 'release-r9': build / 'firmware.bin'}
        refused(lambda: installer_package.create(destination, identity, images))
        assert not destination.exists()
        checks.append('installer-refuses-' + identity + '-identity-before-output')
    candidate.validate_package(build, prepared, assemblies, scratch)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'prepared', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=('assembly', 'package', 'runtime', 'all'), default='all')
    parser.add_argument('--package', type=Path)
    parser.add_argument('--assembly', type=Path, action='append', default=[])
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    args = parser.parse_args()
    build, prepared, out = args.build.resolve(), args.prepared.resolve(), args.out.resolve()
    candidate.validate_out(build, out)
    assert not (out.is_relative_to(prepared) or prepared.is_relative_to(out))
    packaged = args.package.resolve() if args.package else None
    if args.mode != 'assembly':
        assert packaged is not None, '--package is required'
        assert not (out.is_relative_to(packaged) or packaged.is_relative_to(out))
    data = candidate.validate_prepared(build, prepared)
    cpus = args.cpu or ('65c02', '65c816-e')
    if args.mode == 'assembly':
        assembly_checks(build, prepared, out, cpus)
        print('PASS resident revision:', out / 'report.json', flush=True)
        return
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    assemblies = [path.resolve() for path in args.assembly]
    if args.mode == 'all':
        assert not assemblies and set(cpus) == {'65c02', '65c816-e'}
        assembly_checks(build, prepared, out / 'assembly', cpus)
        assemblies = [out / 'assembly']
    assert assemblies, '--assembly is required for package/runtime split runs'
    if args.mode in ('package', 'all'):
        candidate.package(build, prepared, assemblies, packaged)
    manifest = candidate.validate_package(build, prepared, assemblies, packaged)
    checks = static_checks(build, prepared, assemblies, packaged, out) if args.mode in ('package', 'all') else []
    rows = []
    if args.mode in ('runtime', 'all'):
        os.environ['STR8_SOURCE_BUILD'] = str(build)
        from test_rc1_source_store import Harness
        from test_version_cached_runtime import cached_checks
        for cpu in cpus:
            for slot in ('A', 'B'):
                for edu in (False, True):
                    profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                    result = cached_checks(Harness, cpu, slot, edu, data['baseline_firmware'],
                        (packaged / 'firmware.bin').read_bytes(), data['baseline_body'],
                        (packaged / 'version/resident.bin').read_bytes(), data['symbols'])
                    assert result['passed']
                    rows.append(dict(cpu=cpu, slot=slot, edu=edu, **result))
                    save(out / (profile + '-runtime.json'), result)
                    save(out / 'progress.json', dict(runtime=rows, attempts=ATTEMPTS))
                    print('PASS', profile, 'functional equivalence and end-to-end improvement', flush=True)
    assert not ATTEMPTS
    helpers = ['version_cached_candidate.py', 'test_rc1_source_store.py', 'test_resident_contract.py']
    if args.mode in ('runtime', 'all'):
        helpers += ['test_version_cached_runtime.py', 'test_resident_version_runtime.py',
                    'test_resident_version_candidate_runtime.py']
    save(out / 'report.json', dict(**receipt(prepared), mode=args.mode,
        candidate_id=candidate.CANDIDATE_ID, package_manifest_sha256=sha((packaged / 'candidate-manifest.json').read_bytes()),
        package_zip_sha256=sha((packaged / 'candidate.zip').read_bytes()),
        firmware_sha256=sha((packaged / 'firmware.bin').read_bytes()),
        assembly_receipts={str(path): sha((path / 'report.json').read_bytes()) for path in assemblies},
        helper_sha256={name: sha((ROOT / 'tools' / name).read_bytes()) for name in helpers},
        static_checks=checks, runtime_configuration_count=len(rows), runtime_cases=rows,
        application_ram_substituted=False, model_scope='Actual ROM loader and VERSION execution, selected '
        'monitor initialization and inherited discovery/delay shortcuts; stable journal with no interleaved writer'))
    print('PASS cached VERSION revision:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
