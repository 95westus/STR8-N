#!/usr/bin/env python3
"""Prepare the pinned 92-byte batch gate for resident ASM, entirely offline.

This deliberately handles one exact authored source, not the WDC dialect in
general. Generated files are review/test inputs; they never replace src/current.
It invokes no compiler, device interface, subprocess or network API.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from str8build.formats import read_s19


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/current'
SOURCE_NAME = 'batch/batch-gate.asm'
SOURCE_SHA = '48ea32c16b2e6b13124b4836b8b6c2cacdc4a2d97ad13aaea3ab237ee45570e8'
BODY_SHA = '8124f2af31b3b17590ceda5e6cdf56a6592af96899ad013b74db7da3534fb0e5'
FIRMWARE_SHA = 'aef72be59c25f106a4ba5d0d08c0241b5e6adb0471d12d809b5025726e721be6'
PHASE6_SHA = '3c439cc37a3e22e21c8dec68264da38d353eea03ae713e0ae1c8a5a39dc31184'
ORIGIN, BODY_BYTES = 0x7C90, 92
WRAPPERS = ('MODULE BATCH_GATE', 'XDEF B29_GATE_END', 'CODE', 'ENDMOD')
LABEL = re.compile(r'^([A-Z_][A-Z0-9_]*):(?:\s*(.*))?$')
OPERANDS = {
    'JMP': r'(?:B29_[A-Z_]+|\(\$[0-9A-F]{4}\))',
    'JSR': r'(?:B29_[A-Z_]+|\$[0-9A-F]{4})',
    'LDA': r'(?:#[0-9]+|#\$[0-9A-F]{2}|\$[0-9A-F]{4})',
    'STA': r'\$[0-9A-F]{4}',
    'CMP': r'#\$[0-9A-F]{2}', 'ORA': r'#\$[0-9A-F]{2}',
    **{op: r'B29_[A-Z_]+' for op in ('BRA', 'BCS', 'BCC', 'BEQ')},
    **{op: r'' for op in ('NOP', 'RTS', 'PHX', 'PHY', 'PLY', 'PLX', 'PHP', 'PLP')},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii'))


def checked(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f'Pinned file differs: {path}')
    return raw


def file_info(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def display(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def verified_build(build):
    """Check the actual source, firmware, symbol maps and linked body, not flags alone."""
    phase6 = json.loads(checked(ROOT / 'tests/baselines/phase6.json', PHASE6_SHA))
    references = {}
    for name in ('build', 'module-inventory'):
        relative = f'tests/baselines/phase6-evidence/{name}.json'
        references[name] = json.loads(checked(ROOT / relative, phase6['evidence'][relative]['sha256']))
    baseline, inventory = references['build'], references['module-inventory']
    inventory_rows = [row for row in inventory['units'] if row['unit'] == 'batch/batch-gate']
    if len(inventory_rows) != 1:
        raise ValueError('Expected exactly one Phase-6 batch inventory row')
    row = inventory_rows[0]
    if (row['source_path'] != 'src/current/' + SOURCE_NAME or row['logical_origin'] != ORIGIN
            or row['logical_end_exclusive'] != ORIGIN + BODY_BYTES
            or row['linked_body_bytes'] != BODY_BYTES or row['linked_body_sha256'] != BODY_SHA):
        raise ValueError('Phase-6 batch identity differs')
    report_path = build / 'build-report.json'
    report = load(report_path)
    if (report.get('passed') is not True or report.get('firmware_matches') is not True
            or report.get('firmware_sha256') != FIRMWARE_SHA
            or report.get('board_access') is not False
            or len(report.get('compiled', [])) != 29
            or len(report.get('artifacts', {})) != 20
            or not all(report.get('baseline_checks', {}).values())
            or len(report.get('symbol_checks', {})) != 29
            or not all(report['symbol_checks'].values())):
        raise ValueError('Expected a successful offline 29-unit/20-payload current build')
    for key in ('compiled', 'source_files', 'artifacts', 'baseline_checks', 'symbol_checks',
                'layout_sha256', 'build_sources', 'baseline_manifest_sha256',
                'phase1_manifest_sha256', 'phase2_manifest_sha256'):
        if report.get(key) != baseline[key]:
            raise ValueError(f'Build metadata differs from Phase 6: {key}')
    actual_sources = {p.relative_to(SOURCE).as_posix(): sha(p.read_bytes())
                      for p in sorted(SOURCE.rglob('*')) if p.is_file()}
    if actual_sources != report['source_files'] or actual_sources[SOURCE_NAME] != SOURCE_SHA:
        raise ValueError('Authoritative sources differ from the pinned build inventory')
    firmware = checked(build / 'firmware.bin', FIRMWARE_SHA)
    if len(firmware) != 98304:
        raise ValueError('Firmware extent differs')
    for name, expected in report['artifacts'].items():
        raw = (build / 'payload' / name).read_bytes()
        if file_info(raw) != expected:
            raise ValueError(f'Actual linked payload differs: {name}')
    symbols_path = build / 'symbols.json'
    symbols = load(symbols_path)
    meta = load(SOURCE / 'baseline.json')
    if set(symbols) != set(meta['symbol_fingerprints']):
        raise ValueError('Actual linked symbol inventory differs')
    for name, expected in meta['symbol_fingerprints'].items():
        if fingerprint(symbols[name]) != expected:
            raise ValueError(f'Actual linked symbols differ: {name}')
    stage = build / 's/batch'
    checked(stage / 'batch-gate.asm', SOURCE_SHA)
    map_path = stage / 'batch-gate.map'
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', map_path.read_text(), re.M)
    map_symbols = {name: int(value, 16) for value, name in pairs}
    if len(map_symbols) != len(pairs) or map_symbols != symbols['batch/batch-gate']:
        raise ValueError('Batch map disagrees with verified linked symbols')
    if map_symbols['_BEG_CODE'] != ORIGIN or map_symbols['_END_CODE'] != ORIGIN + BODY_BYTES:
        raise ValueError('Batch linked extent differs')
    s19_path = stage / 'batch-gate.s19'
    cells = read_s19(s19_path)
    if set(cells) != set(range(ORIGIN, ORIGIN + BODY_BYTES)):
        raise ValueError('Batch S19 body is not the exact contiguous linked extent')
    body = bytes(cells[address] for address in range(ORIGIN, ORIGIN + BODY_BYTES))
    if sha(body) != BODY_SHA:
        raise ValueError('Actual linked batch bytes differ from Phase 6')
    evidence = {display(path): file_info(path.read_bytes()) for path in
                (report_path, build / 'firmware.bin', symbols_path, map_path, s19_path)}
    return body, {k: v for k, v in map_symbols.items() if not k.startswith('_')}, evidence


def prepare_source(source_raw):
    """Strip exactly four known wrapper lines and retain every remaining statement."""
    if sha(source_raw) != SOURCE_SHA:
        raise ValueError('Source revision differs; review a new recipe instead of translating it implicitly')
    retained, wrappers, definitions, references, mapping = [], [], set(), set(), []
    lines = source_raw.decode('ascii').splitlines()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if line in WRAPPERS:
            wrappers.append((number, line))
            continue
        if not line or any(ord(c) < 32 or ord(c) > 126 for c in line):
            raise ValueError(f'Unexpected blank/control source line {number}')
        match = LABEL.fullmatch(line)
        statement = line
        if match:
            name, statement = match.groups()
            if len(name) > 15 or name.upper() in definitions or name in OPERANDS:
                raise ValueError(f'Invalid or colliding label on line {number}: {name}')
            definitions.add(name.upper())
            statement = statement or ''
        if statement:
            parts = statement.split(None, 1)
            op, operand = parts[0], parts[1] if len(parts) == 2 else ''
            if op not in OPERANDS or re.fullmatch(OPERANDS[op], operand) is None:
                raise ValueError(f'Unsupported statement on source line {number}: {statement}')
            references.update(re.findall(r'B29_[A-Z_]+', operand))
        retained.append(line)
        mapping.append(number)
    if wrappers != [(1, WRAPPERS[0]), (2, WRAPPERS[1]), (3, WRAPPERS[2]), (len(lines), WRAPPERS[3])]:
        raise ValueError('Unexpected WDC wrappers or wrapper order')
    if references - definitions:
        raise ValueError(f'Undeclared source symbols: {sorted(references - definitions)}')
    if len(definitions) != 11:
        raise ValueError('Expected exactly 11 source labels and no imported symbol definitions')
    prepared = ['ORG $7C90', *retained, 'END']
    source_mapping = [None, *mapping, None]
    records = bytearray()
    for index, line in enumerate(prepared, 1):
        raw = line.encode('ascii')
        if not 1 <= len(raw) <= 120 or index * 10 > 65535:
            raise ValueError('Prepared source exceeds line admission limits')
        records.extend((index * 10).to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
    if len(records) > 7168:
        raise ValueError('Prepared source exceeds packed source capacity')
    return prepared, bytes(records), definitions, [
        {'prepared_physical_line': i, 'prepared_record_line': i * 10, 'authoritative_source_line': number}
        for i, number in enumerate(source_mapping, 1)
    ]


def run(build, out):
    build, out = build.resolve(), out.resolve()
    if out.exists():
        raise ValueError('--out must be a new directory; existing outputs are preserved')
    if not out.is_relative_to(ROOT) or out == ROOT:
        raise ValueError('--out must be a fresh directory inside the workspace')
    protected = ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')
    if any(out.is_relative_to(ROOT / name) for name in protected):
        raise ValueError('--out must not be in source, tools, tests, documentation or preserved artifacts')
    if out.is_relative_to(build) or build.is_relative_to(out):
        raise ValueError('--out must be separate from the verified build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        if (ROOT / 'BUILD' / relative.parts[1]).exists():
            raise ValueError('--out must not be nested inside any existing BUILD directory')
    body, symbols, evidence = verified_build(build)
    source_raw = checked(SOURCE / SOURCE_NAME, SOURCE_SHA)
    prepared, records, names, mapping = prepare_source(source_raw)
    if names != set(symbols):
        raise ValueError('Prepared label inventory differs from the verified link')
    files = {
        'batch-gate.asm': ('\n'.join(prepared) + '\n').encode('ascii'),
        'batch-gate.paste.txt': ('PASTE\r' + '\r'.join(prepared) + '\r.\r').encode('ascii'),
        'batch-gate.records.bin': records,
        'expected.bin': body,
    }
    manifest = {
        'schema': 1,
        'unit': {'name': 'batch/batch-gate', 'authoritative_source': 'src/current/' + SOURCE_NAME,
                 'source_sha256': SOURCE_SHA, 'firmware_sha256': FIRMWARE_SHA,
                 'phase6_manifest_sha256': PHASE6_SHA,
                 'generated_source_is_authoritative': False},
        'assembly': {'origin': ORIGIN, 'end_exclusive': ORIGIN + BODY_BYTES,
                     'expected_bytes': BODY_BYTES, 'executable_entry': None,
                     'entries': {k: symbols[k] for k in ('B29_MON', 'B29_CLOCK', 'B29_ERROR', 'B29_APP')},
                     'symbols': symbols, 'exports': {'B29_GATE_END': symbols['B29_GATE_END']},
                     'host_declared_exports': ['B29_GATE_END']},
        'storage': {'kind': 'monitor-embedded RAM-gate image', 'physical_output_start': 0x0200,
                    'ram_destination': ORIGIN, 'ram_reserved_bytes': 96,
                    'enclosing_assets': ['str8n-v2-recovery-slot-a0.bin', 'str8n-v2-recovery-slot-b0.bin'],
                    'firmware_bank': 3,
                    'embedded_rom_addresses': {'monitor_a': 0xAF9F, 'monitor_b': 0xBF9F},
                    'not_a_standalone_rom_image': True},
        'bindings': {'symbolic_imports': {}, 'aliases': {}, 'literal_abi': [
            {'value': 0x7848, 'role': 'V2W_SELECT fixed worker bank-selection service'},
            {'value': 0xD0EA, 'role': 'bank-2 B29_ENGINE provider pre/post service call target'},
            {'value': 0x7EE7, 'role': 'byte written as 1 by B29_ERROR'},
            {'value': 0x7EE8, 'role': 'provider operation ID saved before calls'},
            {'value': 0x7EE9, 'role': 'saved VIA PCR byte'},
            {'value': 0x7EEA, 'role': 'little-endian selected original-reader pointer; provider may select another reader'},
            {'value': 0x7EF4, 'role': 'provider-verified flag, enabled only when equal to $BA'},
            {'value': 0x7FEC, 'role': 'VIA PCR address; its saved bank-control byte is restored'},
        ], 'literal_protocol_values': {'bank': 2, 'clock_operation': 5, 'monitor_operation': 0,
                                       'error_result': 1, 'provider_verified': 0xBA,
                                       'provider_completion_operation_mask': 0x80}},
        'preparation': {'recipe': 'batch-gate-v1-exact-source',
                        'removed_wrappers': list(WRAPPERS),
                        'normalization': 'Strip outer whitespace per retained line; preserve every statement in order and spelling',
                        'added_prefix': 'ORG $7C90', 'added_suffix': 'END',
                        'include_expansion': False, 'symbol_renaming': False,
                        'unsupported_syntax_and_collisions': 'Refuse before creating output',
                        'line_mapping': mapping},
        'admission': {'line_count': len(prepared), 'max_line_bytes': max(map(len, prepared)),
                      'max_name_bytes': max(map(len, names)), 'symbol_count': len(names),
                      'packed_source_bytes': len(records), 'packed_source_start': 0x3300,
                      'packed_source_end_exclusive': 0x3300 + len(records),
                      'record_format': 'little-endian line:u16, length:u8, mode_cache:u8, ASCII text',
                      'first_line': 10, 'line_step': 10, 'canonical_mode_cache': 0,
                      'actual_resident_admission_verified': False},
        'verification': {'expected_output_sha256': BODY_SHA,
                         'expected_bytes_from': display(build / 's/batch/batch-gate.s19'),
                         'verified_build': display(build), 'inputs': evidence,
                         'preparation_only': True, 'resident_byte_comparison_performed': False,
                         'required_next_check': 'Assemble using the unchanged resident engine on both CPU models; compare all 92 bytes and all 11 symbols against the independent linked artifact'},
        'packaging': {'body_bytes': BODY_BYTES, 'embedded_bytes': 96,
                      'trailing_fill': {'bytes': 4, 'value': 0xEA},
                      'generated_include': 's/core/batch-gate.inc', 'header': None,
                      'crc': 'No gate-local CRC; existing monitor slot composition owns header and sealing',
                      's19_entry': 'Resident S9 origin is $7C90; host object-link S9 $0000 is not an executable entry',
                      'no_firmware_or_asset_is_generated': True},
        'execution': {'authorized': False, 'standalone_ram_program': False,
                      'preconditions': 'Existing monitor environment: gate copied to $7C90, worker services and indirect read-line vector initialized, paired bank-2 provider checked; IRQ disabled and decimal clear, 816 E=1 with DP/DBR/PBR zero',
                      'effects': 'Changes banking and gate state; calls provider and selected original reader; stack/flags/register behavior remains that of the exact existing bytes',
                      'physical_output_is_not_execution_address': True,
                      'byte_equivalence_does_not_authorize_execution_or_installation': True,
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
