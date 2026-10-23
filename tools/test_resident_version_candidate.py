"""Prove the separate VERSION tail-call candidate offline without installing it."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil

from test_resident_contract import ATTEMPTS, parse_s19, sha
from test_resident_batch import canonical, files, refused
from str8build.formats import crc, read_s19
import prepare_resident_version_candidate as prepare


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_candidate(build, candidate):
    baseline, symbols, _ = prepare.verified_build(build)
    manifest = json.loads((candidate / 'manifest.json').read_text())
    require(manifest['candidate']['id'] == prepare.CANDIDATE_ID, 'Candidate identity differs')
    for directory, inventory in ((candidate, manifest['files']),
                                  (candidate / 'host', manifest['host_reference']['files'])):
        for name, info in inventory.items():
            require(Path(name).name == name, 'Invalid artifact name')
            raw = (directory / name).read_bytes()
            require(len(raw) == info['bytes'] and sha(raw) == info['sha256'], 'Artifact differs: ' + name)
    body = (candidate / 'expected.bin').read_bytes()
    require(len(body) == 636 and sha(body) == prepare.BODY_SHA, 'Candidate body differs')
    require([(i, a, b) for i, (a, b) in enumerate(zip(baseline, body)) if a != b]
            == [(0x25C, 0x20, 0x4C)], 'Reviewed single-byte change differs')
    cells = read_s19(candidate / 'host/version.s19')
    require(cells == dict(enumerate(body, 0x6E00)), 'Independent host link differs')
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$',
                       (candidate / 'host/version.map').read_text(), re.M)
    original = {name: int(value, 16) for value, name in pairs if not name.startswith('_')}
    mapped = {prepare.previous.ALIASES.get(name, name): value for name, value in original.items()}
    require(len(original) == len(mapped) == 64 and mapped == symbols, 'Host symbols differ')
    require(manifest['assembly']['symbols'] == symbols
            and manifest['assembly']['original_symbols'] == original, 'Manifest symbols differ')
    require(manifest['assembly']['executable_entry'] == 0x6E04
            and body[:7] == bytes.fromhex('42 53 01 03 4C 07 6E'), 'Header/entry differs')
    originals = [(ROOT / 'src/current' / name).read_bytes() for name in (
        prepare.previous.SOURCE_NAME, prepare.previous.LINKS_NAME, prepare.previous.BOARD_NAME)]
    lines, records, names, _ = prepare.prepare_source(*originals)
    require((candidate / 'version.asm').read_bytes() == ('\n'.join(lines) + '\n').encode('ascii'),
            'Resident source differs')
    require((candidate / 'version.paste.txt').read_bytes()
            == ('PASTE\r' + '\r'.join(lines) + '\r.\r').encode('ascii'), 'Paste framing differs')
    require((candidate / 'version.records.bin').read_bytes() == records
            and len(records) == 4611 and canonical(records) == records and names == set(symbols),
            'Packed source differs')
    for name, raw in zip((prepare.previous.SOURCE_NAME, prepare.previous.LINKS_NAME,
                          prepare.previous.BOARD_NAME), originals):
        expected = prepare.host_source(raw) if name == prepare.previous.BOARD_NAME else raw
        require((candidate / 'host' / Path(name).name).read_bytes() == expected,
                'Independent host source patch differs')
    asset = (build / 'payload/version/asset.bin').read_bytes()
    firmware = (build / 'firmware.bin').read_bytes()
    require(asset[:636] == baseline and firmware[0xF800:0x10000] == asset
            and crc(asset) == 0 and sha(firmware) == prepare.previous.FIRMWARE_SHA,
            'Current firmware/asset differs')
    substituted = body + asset[636:]
    require(crc(substituted) != 0, 'Candidate unexpectedly retains original asset seal')
    require(not manifest['candidate']['firmware_installable']
            and not manifest['unit']['candidate_is_current_firmware'], 'Candidate packaging scope differs')
    return manifest, baseline, body, symbols, original, cells, records, asset, firmware


def host_checks(build, candidate, out):
    repeated = out / 'r'
    repeated_manifest = prepare.run(build, repeated)
    manifest = json.loads((candidate / 'manifest.json').read_text())
    for name in manifest['files']:
        assert (candidate / name).read_bytes() == (repeated / name).read_bytes()
    assert manifest['assembly'] == repeated_manifest['assembly']
    assert manifest['candidate'] == repeated_manifest['candidate']
    assert read_s19(candidate / 'host/version.s19') == read_s19(repeated / 'host/version.s19')
    before = files(repeated)
    refused(lambda: prepare.run(build, repeated))
    assert files(repeated) == before
    checks = ['deterministic-resident-files-and-host-body', 'existing-output-refused-unchanged']
    originals = [(ROOT / 'src/current' / name).read_bytes() for name in (
        prepare.previous.SOURCE_NAME, prepare.previous.LINKS_NAME, prepare.previous.BOARD_NAME)]
    for index, name in enumerate(('main', 'links', 'board')):
        changed = list(originals)
        changed[index] += b'\n; changed source\n'
        refused(lambda: prepare.prepare_source(*changed))
        checks.append('changed-' + name + '-source-refused')
    scratch = out / 'bad'
    shutil.copytree(candidate, scratch)
    for relative in [*manifest['files'], 'host/version.s19', 'host/version.map']:
        path = scratch / relative
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused(lambda: validate_candidate(build, scratch))
        path.write_bytes(raw)
        checks.append('tampered-' + relative + '-refused')
    validate_candidate(build, scratch)
    shutil.rmtree(scratch)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'candidate', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    parser.add_argument('--mode', choices=('assembly', 'runtime', 'all'), default='all')
    parser.add_argument('--resident', type=Path, help='Completed assembly proof for runtime-only runs')
    args = parser.parse_args()
    build, candidate, out = args.build.resolve(), args.candidate.resolve(), args.out.resolve()
    assert not out.exists() and out.is_relative_to(ROOT) and out != ROOT
    assert not any(out.is_relative_to(ROOT / name) for name in
                   ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws'))
    assert not any(out.is_relative_to(path) or path.is_relative_to(out) for path in (build, candidate))
    manifest, baseline, expected, symbols, original_symbols, cells, records, asset, firmware = \
        validate_candidate(build, candidate)
    receipt = None
    if args.mode == 'runtime':
        assert args.resident is not None, '--resident is required for runtime-only verification'
        args.resident = args.resident.resolve()
        receipt = json.loads((args.resident / 'report.json').read_text())
        assert receipt['passed'] and receipt['assembly_configuration_count'] > 0
        assert receipt['candidate_manifest_sha256'] == sha((candidate / 'manifest.json').read_bytes())
        assert receipt['source_test_sha256'] == sha(Path(__file__).read_bytes())
        assert receipt['preparation_tool_sha256'] == sha(Path(prepare.__file__).read_bytes())
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    checks = host_checks(build, candidate, out) if args.mode in ('assembly', 'all') else []
    os.environ['STR8_SOURCE_BUILD'] = str(build)
    from test_rc1_source_store import Harness
    assembly, runtime = [], []
    for cpu in args.cpu or ('65c02', '65c816-e'):
        for slot in ('A', 'B'):
            for edu in (False, True):
                profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                if args.mode in ('assembly', 'all'):
                    h = Harness(cpu, slot, edu=edu)
                    h.open()
                    h.command_limit = 30000000
                    flash = list(map(bytes, h.m.banks))
                    upper_ram = bytes(h.m.ram[0x6500:0x7B00])
                    transfers = len(h.m.transfers)
                    step = h.cpu.step

                    def guarded_step():
                        assert not 0x0200 <= h.cpu.pc < 0x3300, 'Physical output buffer must never execute'
                        return step()

                    h.cpu.step = guarded_step
                    h.command((candidate / 'version.paste.txt').read_bytes().decode('ascii').rstrip('\r'))
                    assert h.source() == records
                    for _ in range(2):
                        reply = h.command('ASM', contains='OK ')
                        assert 'ORG differs' in reply and 'S 1 AUTO' not in reply
                        assert h.m.ram[0x6306] == 1
                        assert int.from_bytes(h.m.ram[0x6302:0x6304], 'little') == 636
                        assert int.from_bytes(h.m.ram[0x6304:0x6306], 'little') == 0x6E00
                        body = bytes(h.m.ram[0x0200:0x047C])
                        assert body == expected and canonical(h.source()) == records
                        top = int.from_bytes(h.m.ram[h.asm['SYMTOP']:h.asm['SYMTOP'] + 2], 'little')
                        table = bytes(h.m.ram[0x4F00:top])
                        assert len(table) == 64 * 20
                        actual = {table[i:i + 16].rstrip(b'\0').decode('ascii'):
                                  int.from_bytes(table[i + 16:i + 18], 'little')
                                  for i in range(0, len(table), 20)}
                        assert actual == symbols
                        assert {name: actual[resident] for name, resident in
                                manifest['assembly']['original_to_resident_names'].items()} == original_symbols
                    reply = h.command('SYMS')
                    assert all(name in reply for name in symbols)
                    s19_reply = h.command('S19')
                    exported, entry = parse_s19(s19_reply)
                    assert exported == cells and entry == 0x6E00
                    assert bytes(h.m.ram[0x6500:0x7B00]) == upper_ram
                    assert list(map(bytes, h.m.banks)) == flash and not h.m.flash_writes
                    assert len(h.m.transfers) == transfers
                    (out / (profile + '.bin')).write_bytes(body)
                    (out / (profile + '.s19.txt')).write_text(s19_reply, encoding='ascii')
                    save(out / (profile + '-transcript.json'), h.transcripts)
                    assembly.append(dict(cpu=cpu, slot=slot, edu=edu, passed=True, assemblies=2,
                        output_bytes=636, output_sha256=sha(body), origin=0x6E00, executable_entry=0x6E04,
                        symbols=actual, all_original_symbol_values_equal=True, admitted_source_bytes=4611,
                        s19_data_equal=True, s19_entry=entry, modeled_flash_unchanged=True,
                        upper_ram_unchanged=True, candidate_asset_or_firmware_generated=False))
                    print('PASS', profile, 'resident candidate: 636 bytes, 64 unchanged symbols', flush=True)
                    save(out / 'progress.json', dict(assembly=assembly, runtime=runtime, attempts=ATTEMPTS))
                if args.mode in ('runtime', 'all'):
                    from test_resident_version_candidate_runtime import candidate_checks
                    if args.mode == 'runtime':
                        matching = [row for row in receipt['assembly_cases'] if
                                    (row['cpu'], row['slot'], row['edu']) == (cpu, slot, edu)]
                        assert len(matching) == 1 and matching[0]['output_sha256'] == prepare.BODY_SHA
                        body = (args.resident / (profile + '.bin')).read_bytes()
                    assert body == expected and sha(body) == prepare.BODY_SHA
                    result = candidate_checks(Harness, cpu, slot, edu, baseline, body, symbols, symbols)
                    assert result['passed']
                    runtime.append(dict(cpu=cpu, slot=slot, edu=edu, **result))
                    save(out / (profile + '-runtime.json'), result)
                    print('PASS', profile, 'candidate behavior and timing', flush=True)
                    save(out / 'progress.json', dict(assembly=assembly, runtime=runtime, attempts=ATTEMPTS))
    assert not ATTEMPTS
    helpers = ['prepare_resident_batch.py', 'prepare_resident_version.py', 'prepare_resident_version_full.py',
               'test_resident_batch.py', 'test_resident_contract.py', 'test_rc1_source_store.py']
    if args.mode in ('runtime', 'all'):
        helpers += ['test_resident_version_runtime.py', 'test_resident_version_candidate_runtime.py']
    save(out / 'report.json', dict(passed=True, mode=args.mode, candidate_id=prepare.CANDIDATE_ID,
        board_access=False, serial_ports_opened=0, network_attempts=0, hardware_qualified=False,
        resident_output_installed=False, physical_output_executed=False,
        current_firmware_sha256=sha(firmware), current_asset_sha256=sha(asset),
        baseline_body_sha256=sha(baseline), output_sha256=sha(expected), output_bytes=636,
        source_test_sha256=sha(Path(__file__).read_bytes()),
        preparation_tool_sha256=sha(Path(prepare.__file__).read_bytes()),
        candidate_manifest_sha256=sha((candidate / 'manifest.json').read_bytes()),
        resident_input_receipt_sha256=sha((args.resident / 'report.json').read_bytes()) if receipt else None,
        inherited_helpers={name: sha((ROOT / 'tools' / name).read_bytes()) for name in helpers},
        assembly_configuration_count=len(assembly), assembly_cases=assembly,
        runtime_configuration_count=len(runtime), runtime_cases=runtime, host_checks=checks,
        packed_source_bytes=4611, symbol_count=64, attempts=ATTEMPTS,
        model_scope='Actual resident monitor/ASM compilation and differential VERSION CPU execution; '
                    'candidate is a separate RAM body, never packaged or installed'))
    print('PASS VERSION candidate:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
