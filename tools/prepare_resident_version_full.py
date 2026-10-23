#!/usr/bin/env python3
"""Prepare the pinned complete VERSION command for resident ASM, offline.

This is one reviewed source recipe, not a WDC dialect translator. It reads
verified artifacts and writes only a fresh preparation directory. It invokes
no compiler, subprocess, device or network interface.
"""
import argparse
import json
from pathlib import Path
import re

import prepare_resident_version as previous
from prepare_resident_batch import ROOT, checked, display, file_info, load, sha
from str8build.formats import read_s19


SOURCE_NAME = 'version/version.asm'
SOURCE_SHA = previous.SOURCE_SHA
LINKS_NAME = 'version/version-links.inc'
LINKS_SHA = 'a852a229ebd7969f81c6fa8d289c0d228c769ddb425a11199dde6852f426a6c4'
BOARD_NAME = 'version/version-board.inc'
BOARD_SHA = '14e07f7a951921e5f05227a0c9ed3baaa4250795beb868290da3158e4fdbdaae'
SOURCE_PINS = {SOURCE_NAME: SOURCE_SHA, LINKS_NAME: LINKS_SHA, BOARD_NAME: BOARD_SHA}
PHASE8_SHA = '7f562a626607572733b068e2327719d4f33c5a60daef8f4e1795462d92bad78c'
FIRMWARE_SHA = previous.FIRMWARE_SHA
BODY_SHA = previous.VERSION_SHA
ORIGIN, BODY_BYTES = 0x6E00, 636
ASSET_ADDRESS, ASSET_BYTES = 0xF800, 2048
ENTRY = ORIGIN + 4
ALIASES = {'BOOT_CHOICE_SLOT': 'BOOT_CHOICE', 'BAD_RUNNING_TEXT': 'BAD_RUN_TEXT'}
BINDINGS = {'BOOT_ACTIVE': 0x7D30, 'BOOT_DEST': 0x7D31, 'BOOT_BEST': 0x7DF5,
            'BOOT_SLOT_CHECK': 0xF30D, 'BOOT_SELECT': 0xF2A3, 'BOOT_CHOICE': 0xF1E6,
            'VPTR': 0xD0, 'TZ_PTR': 0xD6}
RESERVATIONS = {'MON_CALL': (0x6F26, 2), 'TZ_SUM': (0x6F28, 2),
                'BN_TEXT': (0x706E, 8), 'BN_SEQ': (0x7076, 4), 'BN_FREE': (0x707A, 2)}
WRAPPERS = ('MODULE VERSION', 'XDEF START', 'XDEF APP_END', 'CODE', 'ENDMOD')
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
STATEMENTS = frozenset(('LDA', 'STA', 'STX', 'STY', 'STZ', 'TAX', 'CMP', 'BEQ', 'BNE', 'BCC', 'BCS',
                       'BRA', 'BPL', 'JMP', 'JSR', 'LDX', 'LDY', 'INY', 'INX',
                       'DEX', 'DEY', 'CPX', 'CPY', 'INC', 'ORA', 'AND', 'EOR',
                       'ASL', 'ROL', 'PHA', 'PLA', 'CLC', 'ADC', 'SEC', 'RTS',
                       'BYTE', 'FILL'))


def verified_build(build):
    """Extend the immutable Phase-8 verifier with complete VERSION source checks."""
    phase8 = json.loads(checked(ROOT / 'tests/baselines/phase8.json', PHASE8_SHA))
    previous_path = ROOT / 'tools/prepare_resident_version.py'
    checked(previous_path, phase8['implementation'][display(previous_path)]['sha256'])
    _, _, evidence = previous.verified_build(build)
    for relative, expected in SOURCE_PINS.items():
        for directory in (ROOT / 'src/current', build / 's'):
            path = directory / relative
            evidence[display(path)] = file_info(checked(path, expected))
    linked = load(build / 'symbols.json')
    host_symbols = linked['version/version']
    symbols = {ALIASES.get(name, name): value for name, value in host_symbols.items()
               if not name.startswith('_')}
    if len(symbols) != 64 or any(symbols.get(name) != value for name, value in BINDINGS.items()):
        raise ValueError('Complete VERSION symbols or explicit ABI bindings differ')
    for original in ('BOOT_ACTIVE', 'BOOT_DEST', 'BOOT_BEST', 'BOOT_SLOT_CHECK', 'BOOT_SELECT', 'BOOT_CHOICE_SLOT'):
        if linked['core/str8n-v2-boot'].get(original) != host_symbols[original]:
            raise ValueError(f'VERSION binding disagrees with the actual bootstrap: {original}')
    cells = read_s19(build / 's/version/version.s19')
    body = bytes(cells[address] for address in range(ORIGIN, ORIGIN + BODY_BYTES))
    if (len(body) != BODY_BYTES or sha(body) != BODY_SHA
            or body[:4] != b'BS\x01\x03' or body[4] != 0x4C
            or int.from_bytes(body[5:7], 'little') != host_symbols['DISPLAY_VERSION']
            or host_symbols['START'] != ORIGIN or host_symbols['APP_END'] != ORIGIN + BODY_BYTES):
        raise ValueError('Complete VERSION body, application header or entry differs')
    for name, (address, count) in RESERVATIONS.items():
        if host_symbols.get(name) != address or bytes(cells[address + i] for i in range(count)) != bytes(count):
            raise ValueError(f'Linked DS reservation is not the reviewed zero-filled span: {name}')
    evidence[display(ROOT / 'tests/baselines/phase8.json')] = file_info(
        checked(ROOT / 'tests/baselines/phase8.json', PHASE8_SHA))
    evidence[display(previous_path)] = file_info(previous_path.read_bytes())
    return body, symbols, evidence


def segments(line):
    """Split quoted and unquoted text without treating quoted semicolons as comments."""
    result, start, index = [], 0, 0
    while index < len(line):
        char = line[index]
        if char == ';':
            result.append((False, line[start:index]))
            return result
        if char not in ('"', "'"):
            index += 1
            continue
        result.append((False, line[start:index]))
        quote, quoted_start = char, index
        index += 1
        while index < len(line):
            if line[index] == '\\':
                index += 2
                continue
            if line[index] == quote:
                index += 1
                break
            index += 1
        else:
            raise ValueError('Unterminated string or character literal')
        result.append((True, line[quoted_start:index]))
        start = index
    result.append((False, line[start:]))
    return result


def prepare_source(source_raw, links_raw, board_raw):
    """Flatten only two pinned includes; keep all internal labels as actual labels."""
    originals = {SOURCE_NAME: source_raw, LINKS_NAME: links_raw, BOARD_NAME: board_raw}
    for name, raw in originals.items():
        if sha(raw) != SOURCE_PINS[name]:
            raise ValueError(f'Source revision differs; review a new recipe: {name}')
    flattened, includes = [], []
    for number, raw in enumerate(source_raw.decode('ascii').splitlines(), 1):
        line = ''.join(text for _, text in segments(raw)).strip()
        match = re.fullmatch(r'INCLUDE "(version-(?:links|board)\.inc)"', line)
        if match:
            relative = 'version/' + match[1]
            includes.append((number, relative))
            for child_number, child_raw in enumerate(originals[relative].decode('ascii').splitlines(), 1):
                flattened.append((relative, child_number, child_raw))
        else:
            flattened.append((SOURCE_NAME, number, raw))
    if includes != [(5, LINKS_NAME), (126, BOARD_NAME)]:
        raise ValueError('Unexpected include names, positions or order')
    prepared, mapping = ['ORG $6E00'], [None]
    wrappers, reservations, definitions, imports = [], {}, {}, {}
    for name, number, raw in flattened:
        parts = segments(raw)
        line = ''.join(text for _, text in parts).strip()
        if not line:
            continue
        if line in WRAPPERS:
            wrappers.append(line)
            continue
        if 'INCLUDE' in IDENTIFIER.findall(''.join(text for quoted, text in parts if not quoted)):
            raise ValueError('Nested or unreviewed INCLUDE')
        line = ''.join(text if quoted else IDENTIFIER.sub(
            lambda match: ALIASES.get(match[0].upper(), match[0]), text)
            for quoted, text in parts).strip()
        equ = re.fullmatch(r'([A-Z_][A-Z0-9_]*)\s+EQU\s+\$([0-9A-F]+)', line)
        label = re.match(r'^([A-Z_][A-Z0-9_]*):(?:\s*(.*))?$', line)
        data = re.fullmatch(r'([A-Z_][A-Z0-9_]*)\s+(DB|DS)\s+(.+)', line)
        if equ:
            symbol, value = equ[1], int(equ[2], 16)
            imports[symbol] = value
            statement = ''
        elif data:
            symbol, directive, operand = data.groups()
            if directive == 'DS':
                if symbol not in RESERVATIONS or operand != str(RESERVATIONS[symbol][1]):
                    raise ValueError('Unreviewed DS reservation')
                reservations[symbol] = int(operand)
                statement = 'FILL ' + operand + ',0'
            else:
                statement = 'BYTE ' + operand
            line = symbol + ': ' + statement
        elif label:
            symbol, statement = label[1], label[2] or ''
            if statement.startswith('DB '):
                statement = 'BYTE ' + statement[3:]
                line = symbol + ': ' + statement
        else:
            symbol, statement = None, line
        if symbol:
            folded = symbol.upper()
            if len(symbol) > 15 or folded in definitions or folded in STATEMENTS:
                raise ValueError(f'Invalid or colliding prepared symbol: {symbol}')
            definitions[folded] = (name, number)
        if statement and statement.split(None, 1)[0] not in STATEMENTS:
            raise ValueError(f'Unexpected statement in reviewed recipe: {statement}')
        prepared.append(line)
        mapping.append({'authoritative_source': 'src/current/' + name,
                        'authoritative_source_line': number})
    if (tuple(wrappers) != WRAPPERS or imports != BINDINGS or len(definitions) != 64
            or reservations != {name: count for name, (_, count) in RESERVATIONS.items()}):
        raise ValueError('Prepared wrappers, bindings, reservations or symbol inventory differ')
    prepared.append('END')
    mapping.append(None)
    records = bytearray()
    for index, line in enumerate(prepared, 1):
        raw = line.encode('ascii')
        if not 1 <= len(raw) <= 120 or any(c < 32 or c > 126 for c in raw) or index * 10 > 65535:
            raise ValueError('Prepared source exceeds record admission limits')
        records.extend((index * 10).to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
    if len(records) > 7168:
        raise ValueError('Prepared source exceeds packed source capacity')
    return prepared, bytes(records), set(definitions), [
        {'prepared_physical_line': index, 'prepared_record_line': index * 10,
         'authoritative_source': item['authoritative_source'] if item else None,
         'authoritative_source_line': item['authoritative_source_line'] if item else None}
        for index, item in enumerate(mapping, 1)]


def run(build, out):
    build, out = build.resolve(), out.resolve()
    protected = ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')
    if out.exists() or out == ROOT or not out.is_relative_to(ROOT):
        raise ValueError('--out must be a new directory inside the workspace')
    if any(out.is_relative_to(ROOT / name) for name in protected):
        raise ValueError('--out must not be inside sources, tools, documentation or preserved artifacts')
    if out.is_relative_to(build) or build.is_relative_to(out):
        raise ValueError('--out must be separate from the verified build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        if (ROOT / 'BUILD' / relative.parts[1]).exists():
            raise ValueError('--out must not be nested inside an existing BUILD directory')
    body, symbols, evidence = verified_build(build)
    originals = {name: checked(ROOT / 'src/current' / name, pin) for name, pin in SOURCE_PINS.items()}
    prepared, records, names, mapping = prepare_source(
        originals[SOURCE_NAME], originals[LINKS_NAME], originals[BOARD_NAME])
    if names != set(symbols):
        raise ValueError('Prepared symbol inventory differs from verified link')
    original_symbols = {original: symbols[ALIASES.get(original, original)] for original in
                        load(build / 'symbols.json')['version/version'] if not original.startswith('_')}
    files = {'version.asm': ('\n'.join(prepared) + '\n').encode('ascii'),
             'version.paste.txt': ('PASTE\r' + '\r'.join(prepared) + '\r.\r').encode('ascii'),
             'version.records.bin': records, 'expected.bin': body}
    manifest = {
        'schema': 1,
        'unit': {'name': 'version/version', 'authoritative_source': 'src/current/' + SOURCE_NAME,
                 'source_sha256': SOURCE_SHA,
                 'authoritative_sources': {'src/current/' + name: file_info(raw) for name, raw in originals.items()},
                 'firmware_sha256': FIRMWARE_SHA, 'phase8_manifest_sha256': PHASE8_SHA,
                 'generated_source_is_authoritative': False},
        'assembly': {'origin': ORIGIN, 'end_exclusive': ORIGIN + BODY_BYTES, 'expected_bytes': BODY_BYTES,
                     'executable_entry': ENTRY, 'entries': {'application_entry': ENTRY},
                     'symbols': symbols, 'original_symbols': original_symbols,
                     'original_to_resident_names': {name: ALIASES.get(name, name) for name in original_symbols},
                     'exports': {name: symbols[name] for name in ('START', 'APP_END')},
                     'host_declared_exports': ['START', 'APP_END']},
        'storage': {'kind': 'VERSION RAM application body inside sealed ROM asset',
                    'physical_output_start': 0x0200, 'ram_destination': ORIGIN,
                    'enclosing_asset': 'version/asset.bin', 'enclosing_asset_bytes': ASSET_BYTES,
                    'firmware_bank': 2, 'asset_rom_address': ASSET_ADDRESS, 'asset_offset': 0,
                    'firmware_offset': 32768 + ASSET_ADDRESS - 0x8000,
                    'not_a_standalone_rom_image': True},
        'bindings': {'symbolic_imports': BINDINGS, 'aliases': ALIASES,
                     'binding_roles': {'BOOT_ACTIVE': 'bootstrap running/default monitor slot byte',
                                       'BOOT_DEST': 'bootstrap slot validation input',
                                       'BOOT_BEST': 'bootstrap selected default slot byte',
                                       'BOOT_SLOT_CHECK': 'bootstrap validation routine, carry set means valid',
                                       'BOOT_SELECT': 'bootstrap current preference/validity selection routine',
                                       'BOOT_CHOICE': 'BOOT_CHOICE_SLOT bootstrap slot-line formatter',
                                       'VPTR': 'borrowed monitor zero-page string pointer $D0/$D1',
                                       'TZ_PTR': 'borrowed monitor zero-page source pointer $D6/$D7'},
                     'literal_abi': [{'value': 0x7E6D, 'role': 'monitor console byte output'},
                                     {'value': 0x7E7C, 'role': 'monitor hexadecimal byte output'},
                                     {'value': 0x7E7F, 'role': 'monitor newline output'},
                                     {'value': 0x7D00, 'role': 'monitor hardware identity board value'},
                                     {'value': 0x7D01, 'role': 'monitor hardware identity CPU value'},
                                     {'value': 0x7FEC, 'role': 'VIA PCR read/write bank-control byte'},
                                     {'value': 0x9C00, 'role': 'start of bank-selected board-name record area'},
                                     {'value': 0xA000, 'role': 'exclusive end of board-name record area'}]},
        'preparation': {'recipe': 'version-full-v1-exact-three-source-flattening',
                        'removed_wrappers': list(WRAPPERS),
                        'normalization': 'Flatten only the two pinned includes in original order; strip comments and outer whitespace; colonize data labels; DB becomes BYTE; exact linked zero-filled DS becomes FILL count,0',
                        'added_prefix': 'ORG $6E00', 'added_suffix': 'END',
                        'include_expansion': [LINKS_NAME, BOARD_NAME], 'symbol_renaming': ALIASES,
                        'alias_scope': 'Case-insensitive complete identifier tokens outside strings and character literals',
                        'internal_label_addresses_substituted': False,
                        'reservations': {name: {'logical_address': address, 'bytes': count, 'verified_fill': 0}
                                         for name, (address, count) in RESERVATIONS.items()},
                        'changed_sources_or_unsupported_syntax': 'Refuse before creating output', 'line_mapping': mapping},
        'admission': {'line_count': len(prepared), 'max_line_bytes': max(map(len, prepared)),
                      'max_name_bytes': max(map(len, names)), 'symbol_count': len(names),
                      'packed_source_bytes': len(records), 'packed_source_start': 0x3300,
                      'packed_source_end_exclusive': 0x3300 + len(records),
                      'record_format': 'little-endian line:u16, length:u8, mode_cache:u8, ASCII text',
                      'first_line': 10, 'line_step': 10, 'canonical_mode_cache': 0,
                      'actual_resident_admission_verified': False},
        'verification': {'expected_output_sha256': BODY_SHA,
                         'expected_bytes_from': display(build / 's/version/version.s19'),
                         'verified_build': display(build), 'inputs': evidence,
                         'preparation_only': True, 'resident_byte_comparison_performed': False,
                         'required_next_check': 'Actual resident PASTE/ASM and comparison of all 636 bytes and all 64 symbols across both CPU models'},
        'packaging': {'body_bytes': BODY_BYTES, 'added_padding_bytes': 0,
                      'application_header': {'magic_ascii': 'BS', 'bytes': 4, 'version': 1, 'type': 3},
                      'preserve': ['asset fill', 'embedded power-fail worker', 'vector tail', 'CRC seal patch'],
                      's19_entry': 'Resident S9 origin $6E00 and host S9 $0000 are not application entry $6E04',
                      'replacement_rule': 'Compare in-memory body substitution against the complete original asset and firmware',
                      'no_firmware_or_asset_is_generated': True},
        'execution': {'hardware_execution_authorized': False, 'standalone_ram_program': False,
                      'model_execution_requires_separate_fixture': True,
                      'preconditions': 'Initialized monitor and bootstrap services at pinned addresses; complete code at $6E00, entry $6E04; borrowed monitor ZP/state and bank mappings available; IRQ disabled, decimal clear, 816 E=1 with DP/DBR/PBR zero',
                      'effects': 'Console output; borrowed $D0/$D1/$D6/$D7 and $E0/$E1 pointers; VERSION working data; bootstrap scratch/choice state; VIA PCR bank switch with saved-byte restoration in BN_READ',
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
