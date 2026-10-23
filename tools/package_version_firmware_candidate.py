#!/usr/bin/env python3
"""Package the proven resident VERSION body as a separate offline firmware candidate.

This reads immutable Phase-10 evidence and a verified current build. It writes
only a fresh package directory; it neither modifies current firmware nor
creates an installer/profile or accesses a board, serial port or network.
"""
import argparse
import importlib
import io
import json
from pathlib import Path
import re
import zipfile

from str8build.formats import crc, sha
from str8build.images import version_asset


ROOT = Path(__file__).resolve().parents[1]
PHASE10 = 'tests/baselines/phase10.json'
PHASE10_SHA = '8ba890a425721430d76c3e2dc7cc7ac8eea9eae1854dee56fffe3f06b261027c'
EVIDENCE = ROOT / 'tests/baselines/phase10-evidence'
CANDIDATE_ID = 'version-board-newline-tailcall-fw-v1'
BODY_SHA = '04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7'
ASSET_SHA = '45eff91880623ee643feb329791d8691e9b9f4d21340b6748dbc205866597d7c'
FIRMWARE_SHA = '4761393a3de28a1b3de76f96bf507857e40a0fd281066ae64dad31ec52f8b95d'
BASELINE_SHA = 'aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6'
ASSET_OFFSET, ASSET_BYTES, BODY_BYTES = 0xF800, 2048, 636
EXPECTED_DIFF = [(0xFA5C, 0x20, 0x4C), (0xFFF6, 0x86, 0xCF), (0xFFF7, 0x43, 0x2E)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_info(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def display(path):
    return path.relative_to(ROOT).as_posix()


def checked(relative, expected):
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), 'Input path escapes the workspace')
    raw = path.read_bytes()
    if isinstance(expected, str):
        require(sha(raw) == expected, 'Pinned file differs: ' + relative)
    else:
        require(file_info(raw) == expected, 'Pinned artifact differs: ' + relative)
    return raw


def verified_inputs(build):
    """Return verified baseline/candidate bytes and their immutable provenance."""
    build = build.resolve()
    phase10 = json.loads(checked(PHASE10, PHASE10_SHA))
    require(phase10['complete'] and phase10['phase'] == 10 and not phase10['board_access']
            and phase10['verification']['resident_assemblies'] == 16,
            'Expected completed offline Phase-10 resident proof')
    for inventory in (phase10['implementation'], phase10['evidence']):
        for relative, info in inventory.items():
            checked(relative, info)
    for phase, pin in phase10['phase_baseline_sha256'].items():
        checked('tests/baselines/phase' + phase + '.json', pin)
    preservation = load(ROOT / phase10['preservation']['receipt'])
    require(preservation['passed'] and preservation['all_sha256_unchanged']
            and len(preservation['before_sha256']) == phase10['preservation']['protected_file_count'],
            'Prior preservation receipt differs')
    for relative, pin in preservation['before_sha256'].items():
        checked(relative, pin)
    source_inventory = {display(path): file_info(path.read_bytes())
                        for path in sorted((ROOT / 'src/current').rglob('*')) if path.is_file()}
    require(source_inventory == preservation['source_inventory'],
            'Current authoritative source inventory differs')

    predecessor = importlib.import_module('test_resident_version_candidate')
    prepared = ROOT / phase10['candidate_manifest']
    result = predecessor.validate_candidate(build, prepared.parent)
    manifest, baseline_body, expected_body, version_symbols, _, cells, _, baseline_asset, baseline_firmware = result
    body = checked(display(EVIDENCE / 'resident.bin'), phase10['evidence'][display(EVIDENCE / 'resident.bin')])
    resident_s19 = checked(display(EVIDENCE / 'resident.s19'), phase10['evidence'][display(EVIDENCE / 'resident.s19')])
    parsed, entry = predecessor.parse_s19(resident_s19.decode('ascii'))
    require(len(body) == BODY_BYTES and sha(body) == BODY_SHA and body == expected_body
            and parsed == cells == dict(enumerate(body, 0x6E00)) and entry == 0x6E00,
            'Phase-10 resident-produced body/export differs')
    profiles = set()
    for cpu in ('65c02', '65c816-e'):
        assembly = load(EVIDENCE / ('assembly-' + cpu + '.json'))
        runtime = load(EVIDENCE / ('runtime-' + cpu + '.json'))
        for receipt in (assembly, runtime):
            require(receipt['passed'] and receipt['candidate_id'] == manifest['candidate']['id']
                    and receipt['output_sha256'] == BODY_SHA and not receipt['attempts']
                    and not receipt['board_access'] and receipt['serial_ports_opened'] == 0
                    and receipt['network_attempts'] == 0
                    and receipt['candidate_manifest_sha256'] == sha(prepared.read_bytes()),
                    'Phase-10 proof receipt differs')
            require(receipt['source_test_sha256'] == sha(Path(predecessor.__file__).read_bytes())
                    and receipt['preparation_tool_sha256'] == sha(Path(predecessor.prepare.__file__).read_bytes()),
                    'Phase-10 proof implementation differs')
            for name, pin in receipt['inherited_helpers'].items():
                checked('tools/' + name, pin)
        require(assembly['mode'] == 'assembly' and assembly['assembly_configuration_count'] == 4
                and runtime['mode'] == 'runtime' and runtime['runtime_configuration_count'] == 4
                and runtime['resident_input_receipt_sha256'] == sha((EVIDENCE / ('assembly-' + cpu + '.json')).read_bytes()),
                'Phase-10 assembly/runtime receipt chain differs')
        for row in assembly['assembly_cases']:
            profile = (row['cpu'], row['slot'], row['edu'])
            require(profile not in profiles and row['cpu'] == cpu and row['passed']
                    and row['assemblies'] == 2 and row['output_sha256'] == BODY_SHA
                    and row['symbols'] == version_symbols and row['s19_data_equal'],
                    'Phase-10 resident assembly coverage differs')
            profiles.add(profile)
            name = cpu + '-' + row['slot'] + '-' + ('edu' if row['edu'] else 'bare')
            require((EVIDENCE / ('transcripts/' + name + '.bin')).read_bytes() == body,
                    'Phase-10 resident assembly bytes differ')
            transcript = (EVIDENCE / ('transcripts/' + name + '.s19.txt')).read_text(encoding='ascii')
            exported, origin = predecessor.parse_s19(transcript)
            raw_export = ('\n'.join(line for line in transcript.splitlines()
                                    if re.fullmatch(r'S[19][0-9A-F]{8,}', line)) + '\n').encode('ascii')
            require(exported == cells and origin == entry and raw_export == resident_s19,
                    'Phase-10 resident S19 provenance differs')
    require(profiles == {(cpu, slot, edu) for cpu in ('65c02', '65c816-e')
                         for slot in ('A', 'B') for edu in (False, True)},
            'Phase-10 resident profile matrix is incomplete')

    symbols_raw = (build / 'symbols.json').read_bytes()
    symbols = json.loads(symbols_raw)
    vectors = symbols['core/str8n-v2-vectors']
    powerfail = (build / 'payload/pf-worker/asset.bin').read_bytes()
    require(bytes(version_asset(baseline_body, powerfail, vectors)) == baseline_asset,
            'Current VERSION asset cannot be reproduced by the existing packager')
    asset = bytes(version_asset(body, powerfail, vectors))
    firmware = bytearray(baseline_firmware)
    firmware[ASSET_OFFSET:ASSET_OFFSET + ASSET_BYTES] = asset
    firmware = bytes(firmware)
    require(len(baseline_firmware) == len(firmware) == 98304
            and sha(baseline_firmware) == BASELINE_SHA and len(asset) == ASSET_BYTES
            and crc(asset) == 0 and sha(asset) == ASSET_SHA and sha(firmware) == FIRMWARE_SHA,
            'Resealed asset or candidate firmware identity differs')
    differences = [(i, old, new) for i, (old, new) in enumerate(zip(baseline_firmware, firmware)) if old != new]
    require(differences == EXPECTED_DIFF, 'Candidate must change only the reviewed opcode and two seal bytes')
    require(asset[:BODY_BYTES] == body and asset[0x300:0x600] == powerfail
            and asset[-8:] == baseline_asset[-8:]
            and asset[0x7F6:0x7F8] == bytes.fromhex('CF2E'),
            'VERSION worker, vector tail, body or CRC patch differs')
    layout = load(ROOT / 'src/current/layout.json')
    require((layout['version'], layout['generation'], layout['boot_compatibility'])
            == ('2.0rc1', 50, 1145194289), 'Current identity/compatibility differs')
    files = {'firmware.bin': firmware, 'version/asset.bin': asset,
             'version/resident.bin': body, 'version/resident.s19': resident_s19,
             'symbols.json': symbols_raw}
    for bank in (1, 2, 3):
        files['banks/bank' + str(bank) + '.bin'] = firmware[(bank - 1) * 32768:bank * 32768]
    return dict(phase10=phase10, prepared_manifest=manifest, baseline_body=baseline_body,
                resident_body=body, resident_s19=resident_s19, baseline_asset=baseline_asset,
                candidate_asset=asset, baseline_firmware=baseline_firmware, candidate_firmware=firmware,
                symbols=symbols, version_symbols=version_symbols, vectors=vectors, files=files,
                provenance=dict(phase10_manifest=PHASE10, phase10_manifest_sha256=PHASE10_SHA,
                    phase10_evidence_files_checked=len(phase10['evidence']),
                    phase10_implementation_files_checked=len(phase10['implementation']),
                    preserved_files_checked=len(preservation['before_sha256']),
                    phase1_through_phase9_sha256=phase10['phase_baseline_sha256'],
                    resident_body='tests/baselines/phase10-evidence/resident.bin',
                    resident_s19='tests/baselines/phase10-evidence/resident.s19',
                    resident_assembly_profiles=8, resident_assemblies=16,
                    baseline_build=display(build), baseline_build_report=file_info((build / 'build-report.json').read_bytes())))


def manifest_for(data):
    return dict(schema=1, candidate_id=CANDIDATE_ID,
        purpose='Separate offline firmware package containing the Phase-10 resident VERSION optimization',
        installation_permitted=False, hardware_qualified=False, board_access=False,
        serial_ports_opened=0, network_attempts=0, installer_or_profile_created=False,
        current_firmware_replaced=False, runtime_execution_performed_by_this_tool=False,
        identity=dict(version='2.0rc1', generation=50, boot_compatibility=1145194289,
                      bank_order=[1, 2, 3], image_bytes=98304,
                      candidate_is_current_firmware=False),
        baseline_firmware_sha256=BASELINE_SHA, candidate_firmware_sha256=FIRMWARE_SHA,
        candidate_asset_sha256=ASSET_SHA, resident_body_sha256=BODY_SHA,
        version=dict(bank=2, rom_address=0xF800, asset_bytes=2048,
                     body_origin=0x6E00, body_bytes=BODY_BYTES, executable_entry=0x6E04,
                     seal_patch_offset=0x7F6, seal_patch_hex='CF2E', crc16_ccitt=0,
                     embedded_powerfail_worker_unchanged=True, vector_tail_unchanged=True,
                     all_64_symbol_values_unchanged=True),
        changes=[dict(firmware_offset=offset, bank=2, address=offset - 32768 + 0x8000,
                      baseline=old, candidate=new) for offset, old, new in EXPECTED_DIFF],
        unchanged=dict(bank1=True, bank3=True, all_other_firmware_bytes=True,
                       current_sources=True, installers=True, identity=True, compatibility=True),
        provenance=data['provenance'],
        implementation={display(Path(__file__).resolve()): file_info(Path(__file__).read_bytes())},
        archive=dict(path='candidate.zip', compression='stored', timestamp='1980-01-01T00:00:00',
                     sorted_members=True, includes='candidate-manifest.json and every files entry; excludes itself'),
        files={name: file_info(raw) for name, raw in sorted(data['files'].items())})


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode('utf-8')


def archive_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, raw)
    return stream.getvalue()


def validate_out(build, out):
    require(not out.exists() and out != ROOT and out.is_relative_to(ROOT),
            '--out must be a new directory inside the workspace')
    require(not any(out.is_relative_to(ROOT / name) for name in
            ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')),
            '--out must not be inside sources or preserved artifacts')
    require(not out.is_relative_to(build) and not build.is_relative_to(out),
            '--out must be separate from the verified current build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        require(not (ROOT / 'BUILD' / relative.parts[1]).exists(),
                '--out must not be nested inside an existing BUILD directory')


def validate_package(build, package):
    """Re-derive all inputs; refuse altered bytes, manifest, inventory or ZIP."""
    data = verified_inputs(build.resolve())
    expected = manifest_for(data)
    files = {**data['files'], 'candidate-manifest.json': json_bytes(expected)}
    files['candidate.zip'] = archive_bytes(files)
    actual_names = {path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()}
    require(actual_names == set(files), 'Candidate package file inventory differs')
    for name, raw in files.items():
        require((package / name).read_bytes() == raw, 'Candidate package differs: ' + name)
    return expected


def run(build, out):
    build, out = build.resolve(), out.resolve()
    validate_out(build, out)
    data = verified_inputs(build)
    manifest = manifest_for(data)
    files = {**data['files'], 'candidate-manifest.json': json_bytes(manifest)}
    files['candidate.zip'] = archive_bytes(files)
    out.mkdir(parents=True)
    for name, raw in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    validate_package(build, out)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = run(args.build, args.out)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(dict(candidate=manifest['candidate_id'], output=display(args.out.resolve()),
                          firmware_sha256=FIRMWARE_SHA, installation_permitted=False,
                          board_access=False), indent=2))


if __name__ == '__main__':
    main()
