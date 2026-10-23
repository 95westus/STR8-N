"""Prove the complete resident VERSION command offline, without installing it."""
import argparse
import json
import os
from pathlib import Path
import shutil

from test_resident_contract import ATTEMPTS, parse_s19, sha
from test_resident_batch import canonical, files, refused
from str8build.formats import read_s19
import prepare_resident_version_full as prepare


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def host_checks(build, prepared, out):
    repeated = out / 'repeat-preparation'
    prepare.run(build, repeated)
    assert files(prepared) == files(repeated)
    before = files(repeated)
    refused(lambda: prepare.run(build, repeated))
    assert files(repeated) == before
    checks = ['deterministic-preparation', 'existing-output-refused-unchanged']
    originals = [(ROOT / 'src/current' / name).read_bytes()
                 for name in (prepare.SOURCE_NAME, prepare.LINKS_NAME, prepare.BOARD_NAME)]
    for index, name in enumerate(('main', 'links', 'board')):
        changed = list(originals)
        changed[index] += b'\n; changed source\n'
        refused(lambda: prepare.prepare_source(*changed))
        checks.append('changed-' + name + '-source-refused')
    scratch = out / 'stale-build'
    shutil.copytree(build, scratch)
    corruptions = [
        ('firmware', 'firmware.bin'), ('version-asset', 'payload/version/asset.bin'),
        ('version-s19', 's/version/version.s19'), ('version-map', 's/version/version.map'),
        ('symbol-inventory', 'symbols.json'), ('staged-main', 's/version/version.asm'),
        ('staged-links', 's/version/version-links.inc'), ('staged-board', 's/version/version-board.inc'),
    ]
    for name, relative in corruptions:
        path = scratch / relative
        original = path.read_bytes()
        if name in ('firmware', 'version-asset'):
            changed = bytes([original[0] ^ 1]) + original[1:]
        elif name == 'version-s19':
            changed = original.replace(b'S1', b'S2', 1)
        elif name == 'version-map':
            changed = original.replace(b'00006e00', b'00006e01', 1)
        elif name == 'symbol-inventory':
            symbols = json.loads(original)
            symbols['version/version']['APP_END'] += 1
            changed = json.dumps(symbols).encode('ascii')
        else:
            changed = original + b'\n; changed staged source\n'
        assert changed != original
        path.write_bytes(changed)
        destination = out / ('refused-' + name)
        refused(lambda: prepare.run(scratch, destination))
        assert not destination.exists()
        path.write_bytes(original)
        checks.append('stale-' + name + '-refused-before-output')
    assert len(checks) == 13
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'prepared', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    parser.add_argument('--mode', choices=('assembly', 'runtime', 'all'), default='all',
                        help='Split runs retain explicit scope; default verifies both')
    parser.add_argument('--resident', type=Path,
                        help='Completed assembly output directory, required for a runtime-only run')
    args = parser.parse_args()
    build, prepared, out = args.build.resolve(), args.prepared.resolve(), args.out.resolve()
    assert not out.exists() and out.is_relative_to(ROOT)
    assert not any(out.is_relative_to(ROOT / name) for name in ('src', 'tools', 'tests', 'docs', 'release', 'archive'))
    assert not any(out.is_relative_to(path) or path.is_relative_to(out) for path in (build, prepared))
    manifest = json.loads((prepared / 'manifest.json').read_text())
    resident_receipt = None
    if args.mode == 'runtime':
        assert args.resident is not None, '--resident is required for runtime-only verification'
        args.resident = args.resident.resolve()
        resident_receipt = json.loads((args.resident / 'report.json').read_text())
        assert resident_receipt['passed'] and resident_receipt['assembly_configuration_count'] > 0
        assert resident_receipt['prepared_manifest_sha256'] == sha((prepared / 'manifest.json').read_bytes())
        assert resident_receipt['source_test_sha256'] == sha(Path(__file__).read_bytes())
        assert resident_receipt['preparation_tool_sha256'] == sha((ROOT / 'tools/prepare_resident_version_full.py').read_bytes())
    for name, expected_info in manifest['files'].items():
        raw = (prepared / name).read_bytes()
        assert len(raw) == expected_info['bytes'] and sha(raw) == expected_info['sha256']
    expected, expected_symbols, _ = prepare.verified_build(build)
    cells = read_s19(build / 's/version/version.s19')
    assert set(cells) == set(range(0x6E00, 0x707C))
    assert bytes(cells[a] for a in range(0x6E00, 0x707C)) == expected
    assert expected == (prepared / 'expected.bin').read_bytes()
    assert len(expected) == 636 and sha(expected) == prepare.BODY_SHA
    assert expected_symbols == manifest['assembly']['symbols'] and len(expected_symbols) == 64
    original_symbols = json.loads((build / 'symbols.json').read_text())['version/version']
    original_symbols = {name: value for name, value in original_symbols.items() if not name.startswith('_')}
    assert manifest['assembly']['original_symbols'] == original_symbols
    assert len(set(manifest['assembly']['original_to_resident_names'].values())) == 64
    records = (prepared / 'version.records.bin').read_bytes()
    assert len(records) == 4611 and canonical(records) == records
    assert manifest['assembly']['executable_entry'] == 0x6E04
    assert expected[:7] == bytes.fromhex('42 53 01 03 4C 07 6E')
    asset = (build / 'payload/version/asset.bin').read_bytes()
    firmware = (build / 'firmware.bin').read_bytes()
    assert len(asset) == 2048 and sha(firmware) == prepare.FIRMWARE_SHA
    assert asset[:636] == expected and firmware[0xF800:0xFA7C] == expected
    assert firmware[0xF800:0x10000] == asset
    host_s9 = [line for line in (build / 's/version/version.s19').read_text().splitlines() if line.startswith('S9')]
    assert len(host_s9) == 1 and int.from_bytes(bytes.fromhex(host_s9[0][2:])[1:3], 'big') == 0
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    checks = host_checks(build, prepared, out) if args.mode in ('assembly', 'all') else []
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
                    h.command((prepared / 'version.paste.txt').read_bytes().decode('ascii').rstrip('\r'))
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
                        actual_symbols = {table[i:i + 16].rstrip(b'\0').decode('ascii'):
                                          int.from_bytes(table[i + 16:i + 18], 'little')
                                          for i in range(0, len(table), 20)}
                        assert actual_symbols == expected_symbols
                        restored = {name: actual_symbols[resident]
                                    for name, resident in manifest['assembly']['original_to_resident_names'].items()}
                        assert restored == original_symbols
                    symbol_reply = h.command('SYMS')
                    assert all(name in symbol_reply for name in expected_symbols)
                    exported, entry = parse_s19(h.command('S19'))
                    assert exported == cells and entry == 0x6E00
                    changed_asset, changed_firmware = bytearray(asset), bytearray(firmware)
                    changed_asset[:636] = body
                    changed_firmware[0xF800:0xFA7C] = body
                    assert changed_asset == asset and changed_firmware == firmware
                    assert bytes(h.m.ram[0x6500:0x7B00]) == upper_ram
                    assert list(map(bytes, h.m.banks)) == flash and not h.m.flash_writes
                    assert len(h.m.transfers) == transfers
                    (out / (profile + '.bin')).write_bytes(body)
                    save(out / (profile + '-transcript.json'), h.transcripts)
                    assembly.append(dict(cpu=cpu, slot=slot, edu=edu, passed=True, assemblies=2,
                                         output_bytes=636, output_sha256=sha(body), origin=0x6E00,
                                         executable_entry=0x6E04, symbols=actual_symbols,
                                         all_original_symbol_values_equal=True, admitted_source_bytes=4611,
                                         s19_data_equal=True, s19_entry=entry,
                                         packaged_asset_and_firmware_unchanged=True,
                                         modeled_flash_unchanged=True, upper_ram_unchanged=True))
                    print('PASS', profile, '636 bytes, 64 symbols, full VERSION asset', flush=True)
                    save(out / 'progress.json', dict(assembly=assembly, runtime=runtime, attempts=ATTEMPTS))
                if args.mode in ('runtime', 'all'):
                    from test_resident_version_runtime import runtime_checks
                    if args.mode == 'runtime':
                        matching = [row for row in resident_receipt['assembly_cases']
                                    if (row['cpu'], row['slot'], row['edu']) == (cpu, slot, edu)]
                        assert len(matching) == 1 and matching[0]['output_sha256'] == prepare.BODY_SHA
                        body = (args.resident / (profile + '.bin')).read_bytes()
                    assert body == expected and sha(body) == prepare.BODY_SHA
                    result = runtime_checks(Harness, cpu, slot, edu, expected, body)
                    assert result['passed']
                    runtime.append(dict(cpu=cpu, slot=slot, edu=edu, **result))
                    save(out / (profile + '-runtime.json'), result)
                    print('PASS', profile, 'complete VERSION runtime and journal checks', flush=True)
                    save(out / 'progress.json', dict(assembly=assembly, runtime=runtime, attempts=ATTEMPTS))
    assert not ATTEMPTS
    inherited = ['prepare_resident_batch.py', 'prepare_resident_version.py', 'test_resident_batch.py',
                 'test_resident_contract.py', 'test_rc1_source_store.py']
    if args.mode in ('runtime', 'all'):
        inherited.append('test_resident_version_runtime.py')
    save(out / 'report.json', dict(
        passed=True, mode=args.mode, board_access=False, serial_ports_opened=0, network_attempts=0,
        hardware_qualified=False, resident_output_installed=False, physical_output_executed=False,
        firmware_sha256=sha(firmware), asset_sha256=sha(asset), output_sha256=sha(expected), output_bytes=636,
        source_test_sha256=sha(Path(__file__).read_bytes()),
        preparation_tool_sha256=sha((ROOT / 'tools/prepare_resident_version_full.py').read_bytes()),
        prepared_manifest_sha256=sha((prepared / 'manifest.json').read_bytes()),
        resident_input_receipt_sha256=sha((args.resident / 'report.json').read_bytes()) if resident_receipt else None,
        inherited_helpers={name: sha((ROOT / 'tools' / name).read_bytes()) for name in inherited},
        assembly_configuration_count=len(assembly), assembly_cases=assembly,
        runtime_configuration_count=len(runtime), runtime_cases=runtime,
        host_checks=checks, packed_source_bytes=4611, symbol_count=64, attempts=ATTEMPTS,
        model_scope='Actual linked monitor/ASM for compilation; separate banked-memory models for full VERSION command and board-name routines, with inherited discovery/delay shortcuts'))
    print('PASS complete resident VERSION:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
