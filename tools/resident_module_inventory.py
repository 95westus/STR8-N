"""Read-only Phase-6 resident-readiness inventory of a verified current build.

These are lexical size/definition estimates, not translated source or a claim
that WDC source can be pasted into ASM. The CPU capability suite is separate.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/current'
INCLUDE = re.compile(r'^\s*INCLUDE\s+"([^"]+)"', re.I)
EQUATE = re.compile(r'^\s*([A-Za-z_][\w]*)\s*(?:EQU\s+|=\s*)(.*)$', re.I)
LABEL = re.compile(r'^\s*([A-Za-z_][\w]*)\s*:\s*(.*)$')
UNMARKED_LABEL = re.compile(r'^([A-Za-z_][\w]*)(?:\s+(.*))?$')
TOKEN = re.compile(r'[A-Za-z_][\w]*')
WDC_DIRECTIVES = {'MODULE', 'XDEF', 'XREF', 'CODE', 'DATA', 'BSS', 'ENDMOD',
                  'DB', 'DW', 'DS', 'DFB', 'DA', 'HEX', 'IF', 'IFDEF', 'IFNDEF',
                  'ELSE', 'ENDIF', 'MACRO', 'ENDM', 'INCLUDE'}
OPCODES = set(('ADC AND ASL BIT BRA BRK BCC BCS BEQ BMI BNE BPL BVC BVS CLC CLD '
              'CLI CLV CMP CPX CPY DEC DEA DEX DEY EOR INC INA INX INY JMP JSR '
              'LDA LDX LDY LSR NOP ORA PHA PHP PHX PHY PLA PLP PLX PLY ROL ROR '
              'RTI RTS SBC SEC SED SEI STA STP STX STY STZ TAX TAY TRB TSB TSX '
              'TXA TXS TYA WAI ORG BYTE WORD TEXT FILL END').split())
OPCODES.update(f'{operation}{bit}' for operation in ('BBR', 'BBS', 'RMB', 'SMB') for bit in range(8))
UNSUPPORTED_OPERATORS = re.compile(r'[\w)\]]\s*(?:\*|/|<<|>>|&|\||\^)\s*[\w$%(<]')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def clean(line, strings=False):
    """Drop comments, and optionally string contents, respecting quoted ';'."""
    out, quote, escaped = [], None, False
    for char in line:
        if quote:
            if not strings:
                out.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char == ';':
            break
        elif char in ('"', "'"):
            quote = char
            out.append(' ' if strings else char)
        else:
            out.append(char)
    return ''.join(out).strip()


def lines(path):
    return path.read_text(encoding='ascii').splitlines()


def display(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def packed(text):
    return sum(4 + len(line.encode('ascii')) for line in text)


def analyze(entries):
    definitions, labels, references, directives = {}, set(), set(), Counter()
    long_lines, operators, unmarked = [], [], []
    retained = []
    for path, number, raw in entries:
        text = clean(raw)
        if len(raw) > 120:
            long_lines.append({'path': display(path), 'line': number, 'bytes': len(raw)})
        if not text:
            continue
        retained.append(text)
        equate = EQUATE.match(text)
        if equate:
            name, operand = equate.groups()
            definitions[name.upper()] = {'kind': 'equate', 'expression': operand}
        else:
            label = LABEL.match(text)
            if label:
                name, text = label.groups()
                labels.add(name.upper())
                definitions[name.upper()] = {'kind': 'label', 'expression': ''}
            else:
                label = UNMARKED_LABEL.match(clean(raw)) if raw and not raw[0].isspace() else None
                if label and label[1].upper() not in OPCODES | WDC_DIRECTIVES:
                    name, operand = label.groups()
                    labels.add(name.upper())
                    definitions[name.upper()] = {'kind': 'label', 'expression': ''}
                    text = operand or ''
                    unmarked.append({'path': display(path), 'line': number, 'name': name})
            parts = text.split(None, 1)
            operation = parts[0].upper() if parts else ''
            if operation in WDC_DIRECTIVES:
                directives[operation] += 1
            if operation not in {'MODULE', 'XDEF', 'XREF', 'CODE', 'DATA', 'BSS', 'ENDMOD', 'INCLUDE'}:
                references.update(TOKEN.findall(clean(text, strings=True).upper()))
        if UNSUPPORTED_OPERATORS.search(clean(text, strings=True)):
            operators.append({'path': display(path), 'line': number, 'text': text})
    needed = set(labels)
    pending = list(references & definitions.keys())
    while pending:
        name = pending.pop()
        if name in needed:
            continue
        needed.add(name)
        pending.extend((set(TOKEN.findall(clean(definitions[name]['expression'], strings=True).upper()))
                        & definitions.keys()) - needed)
    return {
        'line_count': len(entries),
        'raw_packed_record_bytes': packed([line for _, _, line in entries]),
        'trimmed_commentless_packed_record_estimate': packed(retained),
        'trimmed_commentless_fits_7168': packed(retained) <= 7168,
        'unique_lexical_definitions': len(definitions),
        'lexical_label_definitions': len(labels),
        'lexical_equate_definitions': sum(d['kind'] == 'equate' for d in definitions.values()),
        'pruned_equate_definition_estimate': len(needed),
        'pruned_estimate_fits_256': len(needed) <= 256,
        'definition_names_exceeding_15': sorted(name for name in definitions if len(name) > 15),
        'physical_lines_exceeding_120': long_lines,
        'wdc_directive_occurrences': dict(sorted(directives.items())),
        'unsupported_infix_operator_occurrences': operators,
        'labels_without_colon': unmarked,
    }


def flatten(path, build, stack=()):
    path = path.resolve()
    if not path.is_relative_to(build) or path in stack:
        raise ValueError(f'Outside build or recursive include: {path}')
    entries, dependencies = [], []
    for number, raw in enumerate(lines(path), 1):
        include = INCLUDE.match(clean(raw))
        if include:
            child = (path.parent / include[1]).resolve()
            dependencies.append(child)
            nested, nested_deps = flatten(child, build, stack + (path,))
            entries.extend(nested)
            dependencies.extend(nested_deps)
        else:
            entries.append((path, number, raw))
    return entries, dependencies


def authored_path(path, build):
    relative = path.relative_to(build)
    if relative.parts[0] == 's':
        return SOURCE / Path(*relative.parts[1:])
    if relative.parts[0] == 'source':
        return SOURCE / 'source-store' / Path(*relative.parts[1:])
    if relative.parts[0] == 'debugger':
        return SOURCE / 'debugger' / Path(*relative.parts[1:])
    return None


def dependency(path, build):
    source = authored_path(path, build)
    text = [clean(line) for line in lines(path)]
    text = [line for line in text if line]
    equates = bool(text) and all(EQUATE.match(line) or INCLUDE.match(line) for line in text)
    authored = bool(source and source.is_file() and source.read_bytes() == path.read_bytes())
    return {
        'build_path': display(path),
        'authored_path': display(source) if authored else None,
        'kind': 'fixed_equate_binding' if equates else 'source_include',
        'generated_during_build': not authored,
        'bytes': path.stat().st_size,
        'sha256': digest(path.read_bytes()),
    }


def include_tails(paths):
    findings = []
    for path in paths:
        for number, raw in enumerate(lines(path), 1):
            text = clean(raw)
            include = INCLUDE.match(text)
            if include and text[include.end():].strip():
                findings.append({'path': display(path), 'line': number,
                                 'trailing_text_not_flattened': text[include.end():]})
    return findings


def sanity_checks():
    """Small lexer checks; creates only disposable text fixtures, never code."""
    path = Path('lexer-fixture.asm')

    def scan(*text):
        return analyze([(path, number, line) for number, line in enumerate(text, 1)])

    table = (SOURCE / 'assembler/asm-app.asm').read_text(encoding='ascii')
    table = table.split('OP_TABLE:', 1)[1].split('OP_END:', 1)[0]
    raw = bytes(int(value, 16) for value in re.findall(r'\$([\da-fA-F]{2})\b', table))
    names = {raw[offset:offset + 4].decode('ascii').rstrip('\0')
             for offset in range(0, len(raw), 6)}
    checks = {
        'current_opcode_table_is_complete_six_byte_rows': len(raw) % 6 == 0 and bool(names),
        'current_opcode_names_are_excluded_from_unmarked_labels': names <= OPCODES,
        'column_zero_bit_is_not_a_label': scan('BIT $1234')['unique_lexical_definitions'] == 0,
        'all_current_column_zero_mnemonics_are_not_labels': all(
            scan(name + ' $1234')['unique_lexical_definitions'] == 0 for name in names),
        'colon_label_is_recognized': scan('ENTRY: RTS')['lexical_label_definitions'] == 1,
        'unmarked_data_label_is_recognized': scan('ITEM DB 1')['labels_without_colon'] == [
            {'path': str(path), 'line': 1, 'name': 'ITEM'}],
        'quoted_semicolon_survives_comment_removal': clean(' BYTE "x;y" ;comment') == 'BYTE "x;y"',
        'quoted_character_semicolon_survives_comment_removal': clean(" BYTE ';' ;comment") == "BYTE ';'",
        'string_contents_are_not_symbol_references': scan('UNUSED EQU 1', 'BYTE "UNUSED"')[
            'pruned_equate_definition_estimate'] == 0,
    }
    scratch = (ROOT / 'tmp/p6-inventory').resolve()
    if not scratch.is_relative_to(ROOT):
        raise ValueError('Inventory fixture root escaped workspace')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexer-', dir=scratch) as temporary:
        build = Path(temporary).resolve()
        if not build.is_relative_to(scratch):
            raise ValueError('Inventory fixture directory escaped scratch root')
        main, child = build / 'main.asm', build / 'generated.inc'
        child.write_text('BYTE $12\n', encoding='ascii')
        main.write_text('INCLUDE "generated.inc"\nINCLUDE "generated.inc"\n', encoding='ascii')
        entries, dependencies = flatten(main, build)
        checks['repeated_includes_count_twice'] = len(entries) == 2 and dependencies == [child, child]
        checks['generated_include_is_distinguished_from_authored_source'] = dependency(child, build)[
            'generated_during_build'] is True
        main.write_text('INCLUDE "generated.inc"TAIL EQU $12\n', encoding='ascii')
        entries, dependencies = flatten(main, build)
        checks['fused_include_tail_is_reported_separately'] = (
            [line for _, _, line in entries] == ['BYTE $12']
            and dependencies == [child]
            and include_tails([main])[0]['trailing_text_not_flattened'] == 'TAIL EQU $12')
        main.write_text('INCLUDE "main.asm"\n', encoding='ascii')
        try:
            flatten(main, build)
            checks['recursive_include_is_rejected'] = False
        except ValueError:
            checks['recursive_include_is_rejected'] = True
        main.write_text('INCLUDE "../outside.inc"\n', encoding='ascii')
        try:
            flatten(main, build)
            checks['outside_build_include_is_rejected_before_read'] = False
        except ValueError:
            checks['outside_build_include_is_rejected_before_read'] = True
    if not all(checks.values()):
        raise ValueError(f'Inventory lexer sanity failed: {checks}')
    return {'passed': True, 'opcode_table_unique_mnemonics': len(names), 'checks': checks}


NOTES = {
    'batch/batch-gate': 'Small complete leaf: no includes or data aliases; needs explicit ORG and removal of WDC wrapper directives. Calls fixed service addresses; verify as bytes before execution.',
    'xip/gate': 'Small bank-switch gate; bind only used kernel constants, retain interrupt/status and bank-restoration behavior.',
    'xip/work-stub': 'Small RAM stub; bind only used kernel constants, normalize DB/unmarked label syntax, preserve fixed jump-table offsets.',
    'version/version': 'A formatting helper is a useful first isolated routine. Whole VERSION includes board-name helpers and private boot bindings; its packaged asset also embeds other components.',
    'xip/utilities': 'Composite containing maintenance, SRAM, workspace, EDU, dispatch and source adapter. Its linked 22,312-byte body alone exceeds the resident output window; requires independently linked units or a later streaming builder.',
    'clock/clock': '12,258-byte linked body fits output by only 286 bytes. Source must be split; packaged storage record has a separate envelope and padding.',
    'assembler/asm-app': 'Self-hosting requires splitting large parser/editor/opcode-table source, explicit inter-unit bindings and exact reproduction of host image patches.',
    'core/str8n-v2-boot': 'Embeds freshly assembled worker/vector images plus generated text pool; final recovery sector adds host composition and fixed ABI checks.',
    'core/monitor-a0': 'Generated from monitor-b0 by V2_IMAGE_PAGE substitution; the two slot-specific links and header/checksum composition remain separate obligations.',
    'core/monitor-b0': 'Includes generated batch gate, boot bindings and text IDs; final slot needs header/checksum composition at its fixed address.',
    'migration/rtc-migrator': 'Embeds fresh migration-worker bytes and a generated placeholder migration table; migration input and recovery policy remain outside assembly.',
    'bootstrap/bootstrap-journal': 'Embeds generated initial wear record; firmware writes persistent journals when executed. Phase-6 inventory does not execute it.',
    'source-store/source': 'Version-paired ASM private bindings and flash worker addresses; split source while preserving capsule CRC and guard contracts.',
    'debugger/debugger': 'Private generated ASM/monitor bindings, disassembler and stepping tables must remain version paired; ROM-origin output is a candidate artifact, not in-place execution.',
}


def inventory(build):
    build = build.resolve()
    report = json.loads((build / 'build-report.json').read_text())
    if not report['passed'] or not report['firmware_matches'] or len(report['compiled']) != 29:
        raise ValueError('Expected a verified 29-unit current build')
    for relative, expected in report['source_files'].items():
        if digest((SOURCE / relative).read_bytes()) != expected:
            raise ValueError(f'Authored source differs from build: {relative}')
    rows = []
    for unit in report['compiled']:
        module, name = unit['module'], unit['name']
        stage = build / ({'source-store': 'source', 'debugger': 'debugger'}.get(module, 's/' + module))
        main = stage / (name + '.asm')
        entries, includes = flatten(main, build)
        raw_entries = [(main, n, line) for n, line in enumerate(lines(main), 1)]
        flat = analyze(entries)
        tails = include_tails(sorted(set(includes) | {main}))
        key = module + '/' + name
        map_symbols = re.findall(r'^\s*[0-9a-fA-F]{8} (\w+)\s*$', (stage / (name + '.map')).read_text(), re.M)
        blockers = ['WDC module/export/segment wrapper is not resident ASM syntax',
                    'Fixed link origin must be made explicit; no resident object linker or include loader']
        if flat['trimmed_commentless_packed_record_estimate'] > 7168:
            blockers.append('Flattened trimmed/commentless source estimate exceeds 7,168 packed bytes')
        if flat['pruned_equate_definition_estimate'] > 256:
            blockers.append('Even the lexical estimate with unused EQU definitions removed exceeds 256 definitions')
        if flat['definition_names_exceeding_15']:
            blockers.append('WDC definition identifiers exceed the resident 15-character maximum')
        if flat['physical_lines_exceeding_120']:
            blockers.append('Physical source lines exceed 120 bytes; measure after any future normalization')
        if flat['wdc_directive_occurrences'].keys() & {'DB', 'DW', 'DS', 'DFB', 'DA', 'HEX'}:
            blockers.append('WDC data directives require explicit resident dialect normalization')
        if flat['unsupported_infix_operator_occurrences']:
            blockers.append('WDC infix arithmetic/bitwise expressions need explicit resident-compatible bindings')
        if flat['labels_without_colon']:
            blockers.append('Data labels without colon require explicit resident syntax')
        if unit['bytes'] > 12544:
            blockers.append('Linked body exceeds the 12,544-byte resident output window')
        if tails:
            blockers.append('Fused INCLUDE tail needs explicit review; do not turn trailing text into a new statement without baseline comparison')
        source_main = SOURCE / module / (('monitor-b0' if name == 'monitor-a0' else name) + '.asm')
        rows.append({
            'unit': key,
            'source_path': display(source_main),
            'assembly_path': display(main),
            'logical_origin': unit['start'],
            'logical_end_exclusive': unit['end'],
            'linked_body_bytes': unit['bytes'],
            'linked_body_sha256': unit['sha256'],
            'linked_body_fits_12544': unit['bytes'] <= 12544,
            'raw_main_source': analyze(raw_entries),
            'flattened_source': flat,
            'host_map_symbols_excluding_linker_underscore_names': sum(not name.startswith('_') for name in map_symbols),
            'dependencies': [dependency(path, build) for path in sorted(set(includes))],
            'include_trailing_text_findings': tails,
            'ready_for_unmodified_resident_assembly': False,
            'blockers': blockers,
            'strategy': NOTES.get(key, 'Isolate coherent routines, retain explicit used ABI/import constants, normalize source syntax, and compare assembled bytes before expanding to the complete linked unit.'),
        })
    fixture = SOURCE / 'apps/uchess/uchess.a'
    fixture_entries = [(fixture, n, line) for n, line in enumerate(lines(fixture), 1)]
    return {
        'schema': 1,
        'scope': 'Static read-only inventory; no translation, firmware mutation, device access or execution',
        'board_access': False,
        'serial_ports_opened': 0,
        'build': display(build),
        'build_report_sha256': digest((build / 'build-report.json').read_bytes()),
        'lexer_sanity': sanity_checks(),
        'firmware_sha256': report['firmware_sha256'],
        'limits': {'packed_source_bytes': 7168, 'record_header_bytes': 4,
                   'symbol_records': 256, 'name_bytes': 15, 'physical_line_bytes': 120,
                   'output_buffer_bytes': 12544},
        'measurement_notes': [
            'Raw packed bytes are sum(4 + physical ASCII line bytes), including blank/comment lines, excluding newline terminators; this is an estimate of loading every line, not actual resident import.',
            'Flattening recursively substitutes INCLUDE contents from the verified build staging tree, including generated byte includes. Repeated includes count repeatedly.',
            'Existing provider source has one fused INCLUDE/tail. Excluding the tail from flattened source is an inference from the successful WDC build and its linked symbols (EE_* present, SP_R absent), not a standalone compiler probe. The anomaly is reported separately and authored source is never repaired.',
            'Trimmed/commentless estimate removes blank/comment lines and edge whitespace only; it keeps WDC metadata, names and all equates. It is not generated source and does not establish resident compatibility.',
            'Lexical definition counts include labels and EQUs; host-map symbols are reported separately. Pruned estimate retains every label and only transitively referenced equates; no source pruning or resident-symbol admission is performed.',
            'Long-line/name/operator findings are lexical risks with file/line evidence, not a complete language-compatibility proof.',
            'Linked body bytes come from fresh link start/end, not padded sectors, stored records, relocated gateway copies or the composed bank image.',
            'All 29 linked units have WDC wrappers; no complete unit is accepted unchanged by resident ASM. uchess.a is an existing separate resident-dialect fixture, not one of these linked units.',
        ],
        'summary': {
            'linked_units': len(rows),
            'distinct_authored_main_sources': len({r['source_path'] for r in rows}),
            'unmodified_ready_units': 0,
            'flattened_commentless_source_estimate_over_limit': sum(not r['flattened_source']['trimmed_commentless_fits_7168'] for r in rows),
            'pruned_definition_estimate_over_limit': sum(not r['flattened_source']['pruned_estimate_fits_256'] for r in rows),
            'linked_body_over_output_limit': [r['unit'] for r in rows if not r['linked_body_fits_12544']],
            'phase7_complete_leaf_recommendation': 'batch/batch-gate',
            'phase7_small_routine_recommendation': 'version/version: formatting helper with an explicit binding list',
        },
        'resident_dialect_fixture': {'path': display(fixture), 'sha256': digest(fixture.read_bytes()), 'static': analyze(fixture_entries)},
        'units': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.build)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
