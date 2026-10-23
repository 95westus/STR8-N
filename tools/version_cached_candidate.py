#!/usr/bin/env python3
"""Prepare and package the separate cached-board-name VERSION candidate offline.

Only fresh output directories are written. Current sources, prior evidence,
firmware images and installer profiles remain untouched; no board is accessed.
"""
import argparse
from copy import deepcopy
import importlib
import json
from pathlib import Path
import re
import subprocess

import package_version_firmware_candidate as prior
import prepare_resident_version_candidate as phase10
from str8build.formats import crc, read_s19, sha
from str8build.images import version_asset


ROOT = prior.ROOT
PHASE11 = 'tests/baselines/phase11.json'
PHASE11_SHA = 'b47d7c1c0c800d27874f88f81e332322925eb056cfd05c7b5bfb5c5485163c6f'
CANDIDATE_ID = 'version-cached-name-fw-v2'
BODY_BYTES, ORIGIN, ENTRY = 636, 0x6E00, 0x6E04
BODY_SHA = '4c5f5a2a638fc66b17b847101cafcb04c908125ab0e8343789ccabcf36f79ac2'
ASSET_SHA = '7d766c7f885bb0b1fc76f77b91985b1670f42d03d7ea4ff28433fa364039b702'
FIRMWARE_SHA = 'c78b0c93fa47011b2fe56075d21aaaba6a4e2928ecaf819b46efb9cab90b493a'
EXPECTED_BODY_DIFF = [(0x5F, 0x3F, 0x47), (0x25C, 0x20, 0x4C)]
EXPECTED_DIFF = [(0xF85F, 0x3F, 0x47), (0xFA5C, 0x20, 0x4C),
                 (0xFFF6, 0x86, 0xC5), (0xFFF7, 0x43, 0x24)]
require, load, info, display = prior.require, prior.load, prior.file_info, prior.display


def verified_base(build):
    phase11 = json.loads(prior.checked(PHASE11, PHASE11_SHA))
    require(phase11['complete'] and phase11['phase'] == 11 and not phase11['board_access'],
            'Expected the completed offline Phase-11 package proof')
    for inventory in (phase11['implementation'], phase11['evidence']):
        for relative, expected in inventory.items():
            prior.checked(relative, expected)
    preservation = load(ROOT / phase11['preservation']['receipt'])
    require(preservation['passed'] and preservation['all_sha256_unchanged'],
            'Phase-11 preservation proof differs')
    for relative, expected in preservation['before_sha256'].items():
        prior.checked(relative, expected)
    data = prior.verified_inputs(build)
    data['phase11'] = phase11
    return data


def prepare_source(main_raw, links_raw, board_raw):
    """Reuse pinned Phase-10 preparation, then add one private cached entry."""
    lines, _, names, mapping = phase10.prepare_source(main_raw, links_raw, board_raw)
    calls = [i for i, line in enumerate(lines) if line == 'JSR BN_SHOW']
    entries = [i for i, line in enumerate(lines) if line == 'LDX #<BN_LABEL']
    require(calls == [51] and entries == [281]
            and lines[278:282] == ['JSR BN_READ', 'LDA BN_LENGTH', 'BEQ BN_SHOW_DONE', 'LDX #<BN_LABEL'],
            'Reviewed cached-entry source bounds differ')
    lines[calls[0]] = 'JSR BN_SHOW_CACHED'
    mapping[calls[0]]['candidate_patch'] = CANDIDATE_ID
    lines.insert(entries[0], 'BN_SHOW_CACHED:')
    mapping.insert(entries[0], dict(authoritative_source='src/current/' + phase10.previous.BOARD_NAME,
                   authoritative_source_line=161, candidate_added_label=True, candidate_patch=CANDIDATE_ID))
    names.add('BN_SHOW_CACHED')
    records = bytearray()
    for number, (line, source) in enumerate(zip(lines, mapping), 1):
        raw = line.encode('ascii')
        require(1 <= len(raw) <= 120 and all(32 <= char <= 126 for char in raw),
                'Candidate line violates resident admission')
        records.extend((number * 10).to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
        source.update(prepared_physical_line=number, prepared_record_line=number * 10)
    require(len(lines) == 304 and len(records) == 4637 and len(names) == 65,
            'Candidate admission extent differs')
    return lines, bytes(records), names, mapping


def host_sources(originals):
    prepare_source(*(originals[name] for name in
                   (phase10.previous.SOURCE_NAME, phase10.previous.LINKS_NAME, phase10.previous.BOARD_NAME)))
    result = dict(originals)
    main = result[phase10.previous.SOURCE_NAME].splitlines(keepends=True)
    require(main[50].strip() == b'JSR BN_SHOW', 'Reviewed host main call differs')
    main[50] = main[50].replace(b'BN_SHOW', b'BN_SHOW_CACHED')
    result[phase10.previous.SOURCE_NAME] = b''.join(main)
    board = phase10.host_source(result[phase10.previous.BOARD_NAME]).splitlines(keepends=True)
    require(board[160].strip() == b'LDX #<BN_LABEL', 'Reviewed host cached-entry position differs')
    newline = b'\r\n' if board[160].endswith(b'\r\n') else b'\n'
    board.insert(160, b'BN_SHOW_CACHED:' + newline)
    result[phase10.previous.BOARD_NAME] = b''.join(board)
    return result


def originals():
    return {name: prior.checked('src/current/' + name, pin)
            for name, pin in phase10.previous.SOURCE_PINS.items()}


def validate_out(build, out):
    prior.validate_out(build.resolve(), out.resolve())


def prepare(build, out):
    build, out = build.resolve(), out.resolve()
    validate_out(build, out)
    require(len(str(out / 'host')) <= 70, 'Use a short output path for the legacy WDC tools')
    data = verified_base(build)
    source = originals()
    lines, records, names, mapping = prepare_source(*(source[name] for name in
                        (phase10.previous.SOURCE_NAME, phase10.previous.LINKS_NAME, phase10.previous.BOARD_NAME)))
    assembler, linker = phase10.toolchain(build)
    host = out / 'host'
    host.mkdir(parents=True)
    for name, raw in host_sources(source).items():
        (host / Path(name).name).write_bytes(raw)
    commands = [[assembler, '-G', '-L', '-S', '-W', '-I', str(host), 'version.asm'],
                [linker, '-g', '-s', '-t', '-c6E00', '-hm19', '-j', '-o', 'version.s19', 'version.obj']]
    log = []
    for command in commands:
        result = subprocess.run(command, cwd=host, capture_output=True, text=True)
        log.append(dict(command=command, returncode=result.returncode,
                        stdout=result.stdout, stderr=result.stderr))
        (host / 'version.log.json').write_bytes(prior.json_bytes(log))
        require(result.returncode == 0, 'Independent WDC reference failed; inspect host/version.log.json')
    cells = read_s19(host / 'version.s19')
    require(set(cells) == set(range(ORIGIN, ORIGIN + BODY_BYTES)), 'Host body extent differs')
    body = bytes(cells[address] for address in range(ORIGIN, ORIGIN + BODY_BYTES))
    require(sha(body) == BODY_SHA, 'Independent host body differs from reviewed candidate')
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', (host / 'version.map').read_text(), re.M)
    original_symbols = {name: int(value, 16) for value, name in pairs if not name.startswith('_')}
    symbols = {phase10.previous.ALIASES.get(name, name): value for name, value in original_symbols.items()}
    require(symbols == {**data['version_symbols'], 'BN_SHOW_CACHED': 0x7047} and names == set(symbols),
            'Candidate must preserve all old symbols and add only the cached entry')
    files = {'version.asm': ('\n'.join(lines) + '\n').encode('ascii'),
             'version.paste.txt': ('PASTE\r' + '\r'.join(lines) + '\r.\r').encode('ascii'),
             'version.records.bin': records, 'expected.bin': body}
    manifest = deepcopy(data['prepared_manifest'])
    manifest['unit'].update(candidate_id=CANDIDATE_ID, phase11_manifest_sha256=PHASE11_SHA,
                            generated_source_is_authoritative=False)
    manifest['assembly'].update(symbols=symbols, original_symbols=original_symbols,
        original_to_resident_names={name: phase10.previous.ALIASES.get(name, name) for name in original_symbols})
    manifest['preparation'].update(recipe=CANDIDATE_ID, line_mapping=mapping)
    manifest['admission'].update(line_count=304, packed_source_bytes=len(records),
        packed_source_end_exclusive=0x3300 + len(records), symbol_count=65)
    manifest['verification'].update(expected_output_sha256=BODY_SHA,
        expected_bytes_from='host/version.s19', verified_build=display(build),
        required_next_check='Actual resident ASM and sealed-ROM runtime proof')
    manifest['candidate'].update(id=CANDIDATE_ID, objective='Reuse the already validated board-name cache for command display',
        candidate_sha256=BODY_SHA, unchanged_symbol_count=64, added_symbols={'BN_SHOW_CACHED': 0x7047},
        baseline_preparation='tests/baselines/phase10-evidence/prepared/baseline/manifest.json',
        changed_bytes=[dict(offset=i, address=ORIGIN + i, baseline=a, candidate=b) for i, a, b in EXPECTED_BODY_DIFF],
        reviewed_patch={'main_source': 'src/current/' + phase10.previous.SOURCE_NAME, 'main_line': 51,
            'main_before': 'JSR BN_SHOW', 'main_after': 'JSR BN_SHOW_CACHED',
            'board_source': 'src/current/' + phase10.previous.BOARD_NAME,
            'added_label_before_line': 161, 'new_private_entry': 0x7047,
            'retained_phase10_tail_call_line': 171},
        cached_entry_precondition='BN_READ has populated BN_TEXT/BN_LENGTH; BN_LENGTH is nonzero; the board-name journal remains stable with no interleaved writer, including NMI/user code',
        direct_bn_show_entry_preserved=True,
        timing_claim='One redundant board-name scan is skipped by the full command; runtime measurement required')
    manifest['execution']['preconditions'] += '; stable board-name journal with no interleaved writer between the first read and cached display, including NMI/user code; disabling IRQ alone does not establish this'
    manifest['host_reference']['files'] = {path.name: info(path.read_bytes())
                                         for path in sorted(host.iterdir()) if path.is_file()}
    manifest['files'] = {name: info(raw) for name, raw in files.items()}
    for name, raw in files.items():
        (out / name).write_bytes(raw)
    (out / 'manifest.json').write_bytes(prior.json_bytes(manifest))
    _validate_prepared(data, out)
    return manifest


def _validate_prepared(data, prepared):
    manifest = load(prepared / 'manifest.json')
    require(manifest['candidate']['id'] == CANDIDATE_ID
            and manifest['unit']['phase11_manifest_sha256'] == PHASE11_SHA,
            'Prepared candidate identity differs')
    for directory, inventory in ((prepared, manifest['files']),
                                  (prepared / 'host', manifest['host_reference']['files'])):
        for name, expected in inventory.items():
            require(Path(name).name == name and info((directory / name).read_bytes()) == expected,
                    'Prepared artifact differs: ' + name)
    source = originals()
    lines, records, names, _ = prepare_source(*(source[name] for name in
                        (phase10.previous.SOURCE_NAME, phase10.previous.LINKS_NAME, phase10.previous.BOARD_NAME)))
    require((prepared / 'version.asm').read_bytes() == ('\n'.join(lines) + '\n').encode('ascii')
            and (prepared / 'version.paste.txt').read_bytes() == ('PASTE\r' + '\r'.join(lines) + '\r.\r').encode('ascii')
            and (prepared / 'version.records.bin').read_bytes() == records, 'Prepared resident source differs')
    for name, raw in host_sources(source).items():
        require((prepared / 'host' / Path(name).name).read_bytes() == raw, 'Independent host source differs')
    body = (prepared / 'expected.bin').read_bytes()
    cells = read_s19(prepared / 'host/version.s19')
    require(len(body) == BODY_BYTES and sha(body) == BODY_SHA and cells == dict(enumerate(body, ORIGIN))
            and [(i, a, b) for i, (a, b) in enumerate(zip(data['baseline_body'], body)) if a != b] == EXPECTED_BODY_DIFF,
            'Reviewed candidate body differs')
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', (prepared / 'host/version.map').read_text(), re.M)
    original_symbols = {name: int(value, 16) for value, name in pairs if not name.startswith('_')}
    symbols = {phase10.previous.ALIASES.get(name, name): value for name, value in original_symbols.items()}
    require(len(original_symbols) == len(symbols) == 65 and symbols == {**data['version_symbols'], 'BN_SHOW_CACHED': 0x7047}
            and manifest['assembly']['symbols'] == symbols and manifest['assembly']['original_symbols'] == original_symbols
            and names == set(symbols), 'Prepared candidate symbols differ')
    return {**data, 'body': body, 'cells': cells, 'symbols': symbols,
            'original_symbols': original_symbols, 'records': records, 'manifest': manifest}


def validate_prepared(build, prepared):
    return _validate_prepared(verified_base(build.resolve()), prepared.resolve())


def _package_data(build, prepared, assembly_dirs):
    data = validate_prepared(build, prepared)
    tester = ROOT / 'tools/test_version_cached_candidate.py'
    profiles, receipts, artifacts, body, resident_s19 = set(), {}, {}, None, None
    parser = importlib.import_module('test_resident_contract').parse_s19
    for directory in sorted(assembly_dirs):
        directory = directory.resolve()
        receipt = load(directory / 'report.json')
        require(receipt['passed'] and receipt['mode'] in ('assembly', 'all')
                and not receipt['board_access'] and receipt['serial_ports_opened'] == 0
                and receipt['network_attempts'] == 0 and not receipt['attempts']
                and receipt['source_test_sha256'] == sha(tester.read_bytes())
                and receipt['preparation_tool_sha256'] == sha(Path(__file__).read_bytes())
                and receipt['prepared_manifest_sha256'] == sha((prepared / 'manifest.json').read_bytes())
                and receipt['output_sha256'] == BODY_SHA
                and receipt['assembly_configuration_count'] == len(receipt['assembly_cases']),
                'Actual resident assembly receipt differs')
        receipts[display(directory / 'report.json')] = info((directory / 'report.json').read_bytes())
        for row in receipt['assembly_cases']:
            profile = (row['cpu'], row['slot'], row['edu'])
            require(profile not in profiles and row['passed'] and row['assemblies'] == 2
                    and row['output_bytes'] == BODY_BYTES and row['output_sha256'] == BODY_SHA
                    and row['origin'] == ORIGIN and row['executable_entry'] == ENTRY
                    and row['symbols'] == data['symbols'] and row['s19_data_equal']
                    and row['s19_entry'] == ORIGIN and row['modeled_flash_unchanged'] and row['upper_ram_unchanged'],
                    'Resident assembly profile differs')
            profiles.add(profile)
            name = row['cpu'] + '-' + row['slot'] + '-' + ('edu' if row['edu'] else 'bare')
            actual = (directory / (name + '.bin')).read_bytes()
            exported = (directory / (name + '.s19.txt')).read_text(encoding='ascii')
            for suffix in ('.bin', '.s19.txt', '-transcript.json'):
                path = directory / (name + suffix)
                artifacts[display(path)] = info(path.read_bytes())
            cells, origin = parser(exported)
            raw_s19 = ('\n'.join(line for line in exported.splitlines()
                                 if re.fullmatch(r'S[19][0-9A-F]{8,}', line)) + '\n').encode('ascii')
            require(actual == data['body'] and cells == data['cells'] and origin == ORIGIN,
                    'Resident-produced body/export differs')
            require(body is None or (body == actual and resident_s19 == raw_s19),
                    'Resident profile outputs disagree')
            body, resident_s19 = actual, raw_s19
    require(profiles == {(cpu, slot, edu) for cpu in ('65c02', '65c816-e')
                         for slot in ('A', 'B') for edu in (False, True)}, 'All eight resident profiles are required')
    asset = bytes(version_asset(body, (build / 'payload/pf-worker/asset.bin').read_bytes(), data['vectors']))
    firmware = bytearray(data['baseline_firmware'])
    firmware[0xF800:0x10000] = asset
    firmware = bytes(firmware)
    require(sha(asset) == ASSET_SHA and crc(asset) == 0 and sha(firmware) == FIRMWARE_SHA
            and [(i, a, b) for i, (a, b) in enumerate(zip(data['baseline_firmware'], firmware)) if a != b] == EXPECTED_DIFF,
            'Resealed firmware differs from reviewed four-byte change')
    symbols = load(build / 'symbols.json')
    symbols['version/version']['BN_SHOW_CACHED'] = 0x7047
    files = {'firmware.bin': firmware, 'version/asset.bin': asset, 'version/resident.bin': body,
             'version/resident.s19': resident_s19, 'symbols.json': prior.json_bytes(symbols)}
    for bank in (1, 2, 3):
        files['banks/bank' + str(bank) + '.bin'] = firmware[(bank - 1) * 32768:bank * 32768]
    manifest = dict(schema=1, candidate_id=CANDIDATE_ID, installation_permitted=False,
        hardware_qualified=False, board_access=False, serial_ports_opened=0, network_attempts=0,
        current_firmware_replaced=False, installer_or_profile_created=False,
        identity=dict(version='2.0rc1', generation=50, boot_compatibility=1145194289,
                      bank_order=[1, 2, 3], image_bytes=98304, candidate_is_current_firmware=False),
        baseline_firmware_sha256=prior.BASELINE_SHA, candidate_firmware_sha256=FIRMWARE_SHA,
        candidate_asset_sha256=ASSET_SHA, resident_body_sha256=BODY_SHA,
        version=dict(bank=2, rom_address=0xF800, asset_bytes=2048, body_origin=ORIGIN,
                     body_bytes=BODY_BYTES, executable_entry=ENTRY, seal_patch_offset=0x7F6,
                     seal_patch_hex='C524', crc16_ccitt=0, all_64_old_symbols_unchanged=True,
                     private_symbols={'BN_SHOW_CACHED': 0x7047}, cached_entry_requires_nonzero_validated_name=True,
                     stable_journal_without_interleaved_writer_required=True),
        changes=[dict(firmware_offset=i, bank=2, address=i, baseline=a, candidate=b) for i, a, b in EXPECTED_DIFF],
        provenance=dict(phase11_manifest=PHASE11, phase11_manifest_sha256=PHASE11_SHA,
            prepared_manifest=display(prepared / 'manifest.json'), prepared_manifest_sha256=sha((prepared / 'manifest.json').read_bytes()),
            assembly_receipts=receipts, resident_artifacts=artifacts,
            resident_assembly_profiles=8, resident_assemblies=16,
            baseline_build=display(build)),
        implementation={display(Path(__file__).resolve()): info(Path(__file__).read_bytes())},
        files={name: info(raw) for name, raw in sorted(files.items())},
        archive=dict(path='candidate.zip', compression='stored', fixed_timestamp='1980-01-01T00:00:00',
                     sorted_members=True, excludes_itself=True))
    return files, manifest


def package(build, prepared, assembly_dirs, out):
    build, prepared, out = build.resolve(), prepared.resolve(), out.resolve()
    validate_out(build, out)
    require(not any(out.is_relative_to(path.resolve()) or path.resolve().is_relative_to(out)
                    for path in [prepared, *assembly_dirs]), 'Package must be separate from proof inputs')
    files, manifest = _package_data(build, prepared, assembly_dirs)
    files['candidate-manifest.json'] = prior.json_bytes(manifest)
    files['candidate.zip'] = prior.archive_bytes(files)
    out.mkdir(parents=True)
    for name, raw in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    return manifest


def validate_package(build, prepared, assembly_dirs, package):
    files, manifest = _package_data(build.resolve(), prepared.resolve(), assembly_dirs)
    files['candidate-manifest.json'] = prior.json_bytes(manifest)
    files['candidate.zip'] = prior.archive_bytes(files)
    require({path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()} == set(files),
            'Package file inventory differs')
    for name, raw in files.items():
        require((package / name).read_bytes() == raw, 'Package differs: ' + name)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'package', 'check'))
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--assembly', type=Path, action='append')
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            result = prepare(args.build, args.out)
        else:
            require(args.prepared is not None and args.assembly, '--prepared and --assembly are required')
            result = (package(args.build, args.prepared, args.assembly, args.out) if args.action == 'package'
                      else validate_package(args.build, args.prepared, args.assembly, args.out))
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(dict(candidate=CANDIDATE_ID, action=args.action, output=display(args.out.resolve()),
                          board_access=False, installation_permitted=False), indent=2))
    return result


if __name__ == '__main__':
    main()
