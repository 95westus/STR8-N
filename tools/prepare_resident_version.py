#!/usr/bin/env python3
"""Prepare the pinned VERSION formatting helpers for resident ASM, offline.

This extracts one exact source slice. It is not a general dialect translator,
does not replace authoritative sources, and opens no device or network API.
"""
import argparse
import json
from pathlib import Path
import re

import prepare_resident_batch as batch
from prepare_resident_batch import ROOT, checked, display, file_info, load, sha
from str8build.formats import crc, read_s19


SOURCE_NAME = 'version/version.asm'
SOURCE_SHA = 'aca00c7fe49a7d4f68da9c32f56f27a92c04f8836dd5323331b18ae16dc3a999'
BODY_SHA = 'e5d6900a166da102a7ce245738c159d9c5c2dd46b58f8a77fd11ae40dc9075b5'
VERSION_SHA = 'd61ce3177f8571d29c158e1c7436fca051f4c8e3be0cdfc96ad90157431d3747'
FIRMWARE_SHA = batch.FIRMWARE_SHA
PHASE7_SHA = '6ca15073dfce5a0b39558f2080e3160cc3194e7479adb1f94a752e2bc08d0fa7'
ORIGIN, BODY_BYTES = 0x6EBB, 35
VERSION_ORIGIN, VERSION_BYTES = 0x6E00, 636
ASSET_ADDRESS, ASSET_BYTES = 0xF800, 2048
ASSET_OFFSET = ORIGIN - VERSION_ORIGIN
BINDINGS = {'VPTR': 0xD0, 'MON_CALL': 0x6F26}
LABELS = {'SLOT_LETTER': 0x6EBB, 'SLOT_CHAR': 0x6EC3, 'MON_PRINT': 0x6EC6,
          'PRINT': 0x6EC9, 'PRINT_NEXT': 0x6ECF, 'PRINT_DONE': 0x6EDD}
ENTRIES = {name: LABELS[name] for name in ('SLOT_LETTER', 'MON_PRINT', 'PRINT')}
SYMBOLS = {**LABELS, **BINDINGS}


def verified_build(build):
    """Reuse Phase 7 checks, then verify the actual complete VERSION link/asset."""
    phase7 = json.loads(checked(ROOT / 'tests/baselines/phase7.json', PHASE7_SHA))
    checked(ROOT / 'tools/prepare_resident_batch.py',
            phase7['implementation']['tools/prepare_resident_batch.py']['sha256'])
    _, _, evidence = batch.verified_build(build)
    source = ROOT / 'src/current' / SOURCE_NAME
    checked(source, SOURCE_SHA)
    stage = build / 's/version'
    checked(stage / 'version.asm', SOURCE_SHA)
    symbols = load(build / 'symbols.json')
    linked_symbols = symbols['version/version']
    map_path = stage / 'version.map'
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', map_path.read_text(), re.M)
    mapped = {name: int(value, 16) for value, name in pairs}
    if len(mapped) != len(pairs) or mapped != linked_symbols:
        raise ValueError('VERSION map disagrees with verified linked symbols')
    if (mapped['_BEG_CODE'] != VERSION_ORIGIN or mapped['_END_CODE'] != VERSION_ORIGIN + VERSION_BYTES
            or mapped['UNNAMED_TEXT'] != ORIGIN + BODY_BYTES
            or any(mapped.get(name) != value for name, value in SYMBOLS.items())):
        raise ValueError('VERSION extent, formatting labels or fixed bindings differ')
    phase6 = json.loads(checked(ROOT / 'tests/baselines/phase6.json', batch.PHASE6_SHA))
    inventory_path = ROOT / 'tests/baselines/phase6-evidence/module-inventory.json'
    inventory = json.loads(checked(inventory_path,
                           phase6['evidence'][display(inventory_path)]['sha256']))
    rows = [row for row in inventory['units'] if row['unit'] == 'version/version']
    if len(rows) != 1 or any(rows[0].get(key) != value for key, value in {
            'source_path': 'src/current/' + SOURCE_NAME,
            'logical_origin': VERSION_ORIGIN,
            'logical_end_exclusive': VERSION_ORIGIN + VERSION_BYTES,
            'linked_body_bytes': VERSION_BYTES, 'linked_body_sha256': VERSION_SHA}.items()):
        raise ValueError('Phase-6 VERSION identity differs')
    s19_path = stage / 'version.s19'
    cells = read_s19(s19_path)
    if set(cells) != set(range(VERSION_ORIGIN, VERSION_ORIGIN + VERSION_BYTES)):
        raise ValueError('VERSION S19 is not the exact complete contiguous linked body')
    version = bytes(cells[address] for address in range(VERSION_ORIGIN, VERSION_ORIGIN + VERSION_BYTES))
    body = version[ASSET_OFFSET:ASSET_OFFSET + BODY_BYTES]
    if sha(version) != VERSION_SHA or len(body) != BODY_BYTES or sha(body) != BODY_SHA:
        raise ValueError('VERSION linked body or formatting slice differs')
    if symbols['core/str8n-v2-vectors'].get('V2V_RAM_PUTC_ENTRY') != 0x7E6D:
        raise ValueError('Existing console entry binding differs')
    asset_path = build / 'payload/version/asset.bin'
    asset = asset_path.read_bytes()
    firmware = (build / 'firmware.bin').read_bytes()
    layout = load(ROOT / 'src/current/layout.json')
    segments = [row for row in layout['segments'] if row[2] == 'version/asset.bin']
    vectors = symbols['core/str8n-v2-vectors']
    vector_tail = b'\xff\xff' + b''.join(vectors[name].to_bytes(2, 'little') for name in
                        ('V2V_NMI', 'V2V_RAM_RESET_ENTRY', 'V2V_IRQ_BRK'))
    offset = 32768 + ASSET_ADDRESS - 0x8000
    if (segments != [[2, ASSET_ADDRESS, 'version/asset.bin', 0, ASSET_BYTES]]
            or len(asset) != ASSET_BYTES or asset[:VERSION_BYTES] != version
            or asset[0x300:0x600] != (build / 'payload/pf-worker/asset.bin').read_bytes()
            or asset[-8:] != vector_tail or crc(asset) != 0
            or firmware[offset:offset + ASSET_BYTES] != asset):
        raise ValueError('VERSION asset, seal, embedded worker, vectors or firmware placement differs')
    for path in (source, stage / 'version.asm', map_path, s19_path, asset_path,
                 ROOT / 'tests/baselines/phase7.json', ROOT / 'tools/prepare_resident_batch.py'):
        evidence[display(path)] = file_info(path.read_bytes())
    return body, dict(SYMBOLS), evidence


def prepare_source(source_raw):
    """Extract the pinned source span; changed source requires a reviewed recipe."""
    if sha(source_raw) != SOURCE_SHA:
        raise ValueError('Source revision differs; review a new recipe instead of translating it implicitly')
    lines = source_raw.decode('ascii').splitlines()
    starts = [i for i, line in enumerate(lines) if line == 'SLOT_LETTER:']
    ends = [i for i, line in enumerate(lines) if line.startswith('UNNAMED_TEXT DB ')]
    if starts != [96] or ends != [118] or lines[116:118] != ['PRINT_DONE:', '        RTS']:
        raise ValueError('Pinned formatting source bounds differ')
    retained = [line.strip() for line in lines[96:118]]
    prepared = ['VPTR EQU $D0', 'MON_CALL EQU $6F26', 'ORG $6EBB', *retained, 'END']
    mapping = [None, None, None, *range(97, 119), None]
    records = b''.join((i * 10).to_bytes(2, 'little') + bytes([len(line), 0]) + line.encode('ascii')
                       for i, line in enumerate(prepared, 1))
    if (len(prepared) != 26 or len(records) != 371 or max(map(len, prepared)) != 18
            or set(re.findall(r'^([A-Z_]+):', '\n'.join(retained), re.M)) != set(LABELS)):
        raise ValueError('Prepared source admission differs from the reviewed recipe')
    return prepared, records, set(SYMBOLS), [
        {'prepared_physical_line': i, 'prepared_record_line': i * 10,
         'authoritative_source_line': number} for i, number in enumerate(mapping, 1)]


def run(build, out):
    build, out = build.resolve(), out.resolve()
    protected = ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')
    if out.exists() or out == ROOT or not out.is_relative_to(ROOT):
        raise ValueError('--out must be a new directory inside the workspace')
    if any(out.is_relative_to(ROOT / name) for name in protected):
        raise ValueError('--out must not be inside source, tools, documentation or preserved artifacts')
    if out.is_relative_to(build) or build.is_relative_to(out):
        raise ValueError('--out must be separate from the verified build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        if (ROOT / 'BUILD' / relative.parts[1]).exists():
            raise ValueError('--out must not be nested inside an existing BUILD directory')
    body, symbols, evidence = verified_build(build)
    prepared, records, names, mapping = prepare_source(checked(ROOT / 'src/current' / SOURCE_NAME, SOURCE_SHA))
    if names != set(symbols):
        raise ValueError('Prepared symbol inventory differs from verified link')
    files = {'version-format.asm': ('\n'.join(prepared) + '\n').encode('ascii'),
             'version-format.paste.txt': ('PASTE\r' + '\r'.join(prepared) + '\r.\r').encode('ascii'),
             'version-format.records.bin': records, 'expected.bin': body}
    manifest = {
        'schema': 1,
        'unit': {'name': 'version/format', 'authoritative_source': 'src/current/' + SOURCE_NAME,
                 'source_sha256': SOURCE_SHA, 'authoritative_source_lines': [97, 118],
                 'firmware_sha256': FIRMWARE_SHA, 'phase7_manifest_sha256': PHASE7_SHA,
                 'generated_source_is_authoritative': False},
        'assembly': {'origin': ORIGIN, 'end_exclusive': ORIGIN + BODY_BYTES,
                     'expected_bytes': BODY_BYTES, 'executable_entry': None, 'entries': ENTRIES,
                     'symbols': symbols, 'exports': {}, 'host_declared_exports': [],
                     'selected_internal_labels': list(LABELS)},
        'storage': {'kind': 'slice of VERSION RAM application inside sealed ROM asset',
                    'physical_output_start': 0x0200, 'ram_destination': ORIGIN,
                    'enclosing_asset': 'version/asset.bin', 'enclosing_asset_bytes': ASSET_BYTES,
                    'enclosing_body_origin': VERSION_ORIGIN, 'enclosing_body_bytes': VERSION_BYTES,
                    'firmware_bank': 2, 'asset_rom_address': ASSET_ADDRESS,
                    'asset_offset': ASSET_OFFSET, 'slice_rom_address': ASSET_ADDRESS + ASSET_OFFSET,
                    'firmware_offset': 32768 + ASSET_ADDRESS - 0x8000 + ASSET_OFFSET,
                    'not_a_standalone_rom_image': True},
        'bindings': {'symbolic_imports': BINDINGS, 'aliases': {},
                     'binding_roles': {'VPTR': 'VERSION borrows monitor zero-page pointer $D0/$D1',
                                       'MON_CALL': 'existing VERSION indirect monitor formatter pointer'},
                     'literal_abi': [{'value': 0x7E6D, 'symbol': 'V2V_RAM_PUTC_ENTRY',
                                      'role': 'initialized monitor console output service'}]},
        'preparation': {'recipe': 'version-format-v1-exact-source-slice',
                        'normalization': 'Strip outer whitespace; retain all 22 original lines in order and spelling',
                        'added_prefix': prepared[:3], 'added_suffix': 'END',
                        'include_expansion': False, 'symbol_renaming': False,
                        'changed_source_or_bounds': 'Refuse before creating output', 'line_mapping': mapping},
        'admission': {'line_count': len(prepared), 'max_line_bytes': max(map(len, prepared)),
                      'max_name_bytes': max(map(len, names)), 'symbol_count': len(names),
                      'packed_source_bytes': len(records), 'packed_source_start': 0x3300,
                      'packed_source_end_exclusive': 0x3300 + len(records),
                      'record_format': 'little-endian line:u16, length:u8, mode_cache:u8, ASCII text',
                      'first_line': 10, 'line_step': 10, 'canonical_mode_cache': 0,
                      'actual_resident_admission_verified': False},
        'verification': {'expected_output_sha256': BODY_SHA, 'whole_version_body_sha256': VERSION_SHA,
                         'expected_bytes_from': display(build / 's/version/version.s19'),
                         'verified_build': display(build), 'inputs': evidence,
                         'preparation_only': True, 'resident_byte_comparison_performed': False,
                         'required_next_check': 'Actual resident PASTE/ASM and comparison of all 35 bytes and eight symbol values on both CPU models'},
        'packaging': {'body_bytes': BODY_BYTES, 'added_padding_bytes': 0,
                      'preserve': ['other VERSION code/data', 'asset fill', 'embedded power-fail worker',
                                   'vector tail', 'CRC seal patch'],
                      's19_entry': 'Resident S9 origin $6EBB; whole host VERSION S9 $0000 is not a helper entry',
                      'replacement_rule': 'Compare in-memory slice substitution against the complete original asset and firmware',
                      'no_firmware_or_asset_is_generated': True},
        'execution': {'hardware_execution_authorized': False, 'standalone_ram_program': False,
                      'model_execution_requires_separate_fixture': True,
                      'preconditions': 'Existing monitor console service initialized; code at original logical addresses; VPTR and MON_CALL application state available; IRQ disabled, decimal clear, 816 E=1 with DP/DBR/PBR zero',
                      'effects': 'PRINT modifies VPTR/Y/A and emits console bytes; SLOT_LETTER emits one byte; MON_PRINT dispatches through initialized MON_CALL',
                      'physical_output_is_not_execution_address': True,
                      'byte_equivalence_does_not_authorize_hardware_execution_or_installation': True,
                      'board_access': False, 'serial_ports_opened': 0, 'network_attempts': 0},
        'files': {name: file_info(raw) for name, raw in files.items()},
    }
    out.mkdir(parents=True)
    for name, raw in files.items():
        with (out / name).open('xb') as stream:
            stream.write(raw)
    with (out / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.build, args.out)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({'prepared': result['unit']['name'], 'output': display(args.out.resolve()),
                      'admission': result['admission'], 'board_access': False}, indent=2))


if __name__ == '__main__':
    main()
