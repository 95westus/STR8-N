#!/usr/bin/env python3
"""Build an offline resident-development kit and review file-only captures.

No serial or board interface is imported. Generated lessons and captured drafts
never replace authoritative sources, firmware, installer profiles or evidence.
"""
import argparse
from copy import deepcopy
import difflib
import hashlib
import importlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'tests/baselines/phase11r2.json'
BASELINE_SHA = '62fbba34391e37b5d0845b455b2cfdb7b1645d47838029ce310393f48158d8de'
PREPARED = ROOT / 'tests/baselines/phase11r2-evidence/prepared'
FAST_SHA = '4c5f5a2a638fc66b17b847101cafcb04c908125ab0e8343789ccabcf36f79ac2'
CONTROL_SHA = '04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7'
NAMES = ('hello-a', 'hello-b', 'version-fast', 'version-control')
_CACHE = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def info(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def json_bytes(value):
    return (json.dumps(value, indent=2) + '\n').encode('utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def display(path):
    return path.relative_to(ROOT).as_posix()


def checked(relative, expected):
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), 'Input path escapes the workspace')
    raw = path.read_bytes()
    require((sha(raw) == expected if isinstance(expected, str) else info(raw) == expected),
            'Frozen input differs: ' + relative)
    return raw


def validate_out(build, out):
    build, out = build.resolve(), out.resolve()
    require(not out.exists() and out != ROOT and out.is_relative_to(ROOT),
            'Output must be a new directory inside the workspace')
    require(not any(out.is_relative_to(ROOT / name) for name in
            ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')),
            'Output must not be inside sources or preserved artifacts')
    require(not out.is_relative_to(build) and not build.is_relative_to(out),
            'Output must be separate from the verified build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        require(not (ROOT / 'BUILD' / relative.parts[1]).exists(),
                'Output must not be nested in an existing BUILD directory')


def _signatures(paths, build):
    files = set(paths)
    files.update(path for directory in (ROOT / 'src/current', build)
                 for path in directory.rglob('*') if path.is_file())
    return {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in files}


def _version(build):
    """Hash frozen evidence; reuse expensive prior validation while inputs are stable."""
    frozen = json.loads(checked(BASELINE, BASELINE_SHA))
    for inventory in (frozen['implementation'], frozen['evidence']):
        for relative, expected in inventory.items():
            checked(relative, expected)
    preservation = load(ROOT / frozen['preservation']['receipt'])
    require(frozen['complete'] and frozen['revision'] == 2 and preservation['passed']
            and preservation['all_sha256_unchanged'], 'Frozen revision proof is incomplete')
    paths = [(ROOT / relative).resolve() for relative in preservation['before_sha256']]
    signature = _signatures(paths, build)
    cached = _CACHE.get(str(build))
    if cached and cached['signature'] == signature:
        return deepcopy(cached['data'])
    for relative, expected in preservation['before_sha256'].items():
        checked(relative, expected)
    for phase, expected in frozen['phase_baseline_sha256'].items():
        checked('tests/baselines/phase' + phase + '.json', expected)
    recipe = importlib.import_module('version_cached_candidate')
    data = recipe.validate_prepared(build, PREPARED)
    require(sha(data['body']) == FAST_SHA and len(data['symbols']) == 65
            and data['symbols']['BN_SHOW_CACHED'] == 0x7047, 'Frozen VERSION preparation differs')
    data['frozen_manifest'] = frozen
    _CACHE[str(build)] = dict(signature=signature, data=deepcopy(data))
    return data


def _pack(numbered):
    records, previous = bytearray(), 0
    for number, text in numbered:
        raw = text.encode('ascii')
        require(previous < number <= 65535 and 1 <= len(raw) <= 120
                and all(32 <= char <= 126 for char in raw), 'Invalid numbered source record')
        records.extend(number.to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
        previous = number
    require(numbered and len(records) <= 7168, 'Source is empty or exceeds packed source capacity')
    return bytes(records)


def _lanes(build):
    data = _version(build)
    lanes = {}
    for name, char in (('hello-a', 0x41), ('hello-b', 0x42)):
        lines = ['BASE EQU $0200', 'PUTC EQU $7E6D', 'HOLD EQU $7E67', f'CHAR EQU ${char:02X}',
                 'ORG BASE', 'START: SEI', 'CLD', 'LDA #CHAR', 'BRK $01', 'JSR PUTC',
                 'BRK $02', 'JMP HOLD', 'END']
        lanes[name] = dict(lines=lines, origin=0x0200, entry=0x0200,
            expected=bytes.fromhex(f'78 D8 A9 {char:02X} 00 01 20 6D 7E 00 02 4C 67 7E'),
            symbols={'BASE': 0x200, 'PUTC': 0x7E6D, 'HOLD': 0x7E67, 'CHAR': char, 'START': 0x200},
            line_mapping=[dict(prepared_record_line=i * 10, lesson_line=i, authoritative_source=None,
                               authoritative_source_line=None) for i in range(1, 14)])
    fast_lines = (PREPARED / 'version.asm').read_text(encoding='ascii').splitlines()
    require(len(fast_lines) == 304 and fast_lines[51] == 'JSR BN_SHOW_CACHED',
            'Frozen VERSION lesson source differs')
    for name in ('version-fast', 'version-control'):
        lines = list(fast_lines)
        body = data['body']
        mapping = deepcopy(data['manifest']['preparation']['line_mapping'])
        if name == 'version-control':
            lines[51] = 'JSR BN_SHOW'
            body = data['resident_body']
            mapping[51]['lesson_change'] = 'Control calls the existing BN_SHOW; private cached label remains'
        require(sha(body) == (FAST_SHA if name == 'version-fast' else CONTROL_SHA),
                'VERSION lesson body identity differs')
        lanes[name] = dict(lines=lines, expected=body, origin=0x6E00, entry=0x6E04,
                           symbols=deepcopy(data['symbols']), line_mapping=mapping)
    for lane in lanes.values():
        lane['numbered'] = [(i * 10, line) for i, line in enumerate(lane['lines'], 1)]
        lane['records'] = _pack(lane['numbered'])
        lane['paste'] = ('PASTE\r' + '\r'.join(lane['lines']) + '\r.\r').encode('ascii')
    return lanes


def _session():
    return dict(schema=1, board_access_performed=False, flash_operations_allowed=False,
        automatic_transmission=False, current_firmware_required=True,
        contexts={'monitor': 'B3> ', 'assembler': 'ASM> ', 'debugger': 'DBG> '},
        import_steps=[dict(context='monitor', command='ASM', next='assembler'),
            dict(context='assembler', command='NEW', next='assembler'),
            dict(context='assembler', input_file='LANE/source.paste.txt', next='assembler',
                 condition='Send only after ASM> ; PASTE appends, so NEW must precede a replacement'),
            *[dict(context='assembler', command=command, next='assembler')
              for command in ('ASM', 'LIST', 'LST', 'SYMS', 'S19')]],
        hello_debug_steps=[dict(context='assembler', command='QUIT', next='monitor'),
            dict(context='monitor', command='G 0200', next='debugger', expected_pc=0x0206),
            dict(context='debugger', command='R', next='debugger', guest_instructions_executed=0),
            dict(context='debugger', command='U 0206 03', next='debugger', guest_instructions_executed=0,
                 expected_instructions=['JSR $7E6D', 'BRK $02', 'JMP $7E67']),
            dict(context='debugger', command='N', next='debugger', expected_pc=0x0209,
                 expected_output='A for hello-a, B for hello-b'),
            dict(context='debugger', command='C', next='debugger', expected_pc=0x020B),
            dict(context='debugger', command='C', next='monitor', expected_transfer='JMP $7E67 HOLD')],
        branches={'unexpected_prompt': 'Stop sending commands and identify the current context',
            'fresh_ASM': 'ASM reentry clears the document; restore saved numbered lines or NEW then PASTE',
            'edit_A_to_B': 'At ASM> after restoring hello-a, enter 40 CHAR EQU $42; then ASM and capture again',
            'numbered_replay': 'Numbered source preserves IDs; PASTE renumbers by tens and appends',
            'version_execution': 'VERSION origin $6E00 differs from output buffer $0200; kit compiles/captures it and does not issue a run/load/flash command',
            'capture': 'Save one complete LIST response and one complete S19 response, including final ASM> prompt',
            'persistence': 'No flash save or installer command belongs to this session'})


def _kit(build):
    lanes = _lanes(build)
    files = {'session-commands.json': json_bytes(_session())}
    metadata = {}
    for name, lane in lanes.items():
        prefix = name + '/'
        files.update({prefix + 'source.asm': ('\n'.join(lane['lines']) + '\n').encode('ascii'),
            prefix + 'source.numbered.txt': ''.join(f'{number} {text}\n' for number, text in lane['numbered']).encode('ascii'),
            prefix + 'source.paste.txt': lane['paste'], prefix + 'records.bin': lane['records'],
            prefix + 'expected.bin': lane['expected'], prefix + 'symbols.json': json_bytes(lane['symbols'])})
        metadata[name] = dict(origin=lane['origin'], entry=lane['entry'], line_count=len(lane['lines']),
            packed_source_bytes=len(lane['records']), body_bytes=len(lane['expected']),
            body_sha256=sha(lane['expected']), symbols=lane['symbols'],
            source_provenance=('Authored RAM lesson' if name.startswith('hello') else
                'Frozen Phase-11r2 prepared source; control reverts only numbered line 520'))
    manifest = dict(schema=1, name='resident-board-development-offline', baseline_build=display(build),
        board_access=False, serial_ports_opened=0, network_attempts=0, installation_permitted=False,
        current_firmware_changed=False, authoritative_source_changed=False,
        frozen_manifest=BASELINE, frozen_manifest_sha256=BASELINE_SHA,
        implementation={display(Path(__file__).resolve()): info(Path(__file__).read_bytes())},
        source_retention='ASM reentry clears source; retain complete host LIST capture before leaving',
        capture_policy='Generic LIST captures have no completeness marker; only explicit known-source rehearsal expectations establish completeness',
        lanes=metadata, files={name: info(raw) for name, raw in sorted(files.items())})
    files['manifest.json'] = json_bytes(manifest)
    return lanes, manifest, files


def _write(out, files):
    out.mkdir(parents=True)
    for name, raw in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)


def build_kit(build, out):
    build, out = build.resolve(), out.resolve()
    validate_out(build, out)
    _, manifest, files = _kit(build)
    _write(out, files)
    return manifest


def load_kit(path):
    path = path.resolve()
    claimed = load(path / 'manifest.json')
    build = (ROOT / claimed['baseline_build']).resolve()
    require(build.is_relative_to(ROOT), 'Kit baseline build escapes workspace')
    lanes, manifest, files = _kit(build)
    require({p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()} == set(files),
            'Kit file inventory differs')
    for name, raw in files.items():
        require((path / name).read_bytes() == raw, 'Kit artifact differs: ' + name)
    return dict(lanes=lanes, manifest=manifest)


def _response(raw, command, limit):
    require(isinstance(raw, bytes) and 0 < len(raw) <= limit, 'Capture is empty or exceeds its bound')
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('Capture must be ASCII') from error
    require(all(char in '\r\n' or 32 <= ord(char) <= 126 for char in text), 'Capture contains a control byte')
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if lines[-1] == '':
        lines.pop()
    require(lines and lines[-1] == 'ASM> ', 'Capture must end at the complete ASM> prompt')
    lines = [line for line in lines[:-1] if line != '']
    if lines and lines[0] == command:
        lines.pop(0)
    return lines


def parse_list(raw):
    numbered = []
    for line in _response(raw, 'LIST', 65536):
        match = re.fullmatch(r'([1-9][0-9]{0,4}) (.+)', line)
        require(match is not None, 'LIST capture contains a non-record line')
        numbered.append((int(match[1]), match[2]))
    return numbered, _pack(numbered)


def parse_export(raw, origin):
    cells, entry, next_address = {}, None, origin
    for line in _response(raw, 'S19', 131072):
        require(entry is None and re.fullmatch(r'S[19][0-9A-F]+', line) is not None,
                'S19 capture contains an unsupported or post-entry record')
        require(len(line[2:]) % 2 == 0, 'S19 record has an odd hex length')
        record = bytes.fromhex(line[2:])
        require(len(record) >= 4 and len(record) == record[0] + 1 and sum(record) & 255 == 255,
                'S19 count/checksum differs')
        address = int.from_bytes(record[1:3], 'big')
        if line[1] == '9':
            require(record[0] == 3 and address == origin, 'S9 must contain the assembly origin')
            entry = address
        else:
            data = record[3:-1]
            require(1 <= len(data) <= 16 and address == next_address
                    and address + len(data) <= 65536 and len(cells) + len(data) <= 12544,
                    'S1 data must be ordered, contiguous, within bounds and at most 16 bytes')
            cells.update(enumerate(data, address))
            next_address += len(data)
    require(cells and entry == origin, 'S19 capture is missing data or its final S9')
    return cells, entry


def collect(kitpath, base_name, list_path, s19_path, out, expect_name=None):
    kitpath, list_path, s19_path, out = (path.resolve() for path in (kitpath, list_path, s19_path, out))
    kit = load_kit(kitpath)
    require(base_name in kit['lanes'] and (expect_name is None or expect_name in kit['lanes']),
            'Unknown base or expected lesson')
    build = ROOT / kit['manifest']['baseline_build']
    validate_out(build, out)
    require(not out.is_relative_to(kitpath) and not kitpath.is_relative_to(out),
            'Capture output must be separate from the kit')
    require(list_path.stat().st_size <= 65536 and s19_path.stat().st_size <= 131072,
            'Capture input exceeds its bound')
    list_raw, s19_raw = list_path.read_bytes(), s19_path.read_bytes()
    numbered, records = parse_list(list_raw)
    base = kit['lanes'][base_name]
    cells, origin = parse_export(s19_raw, base['origin'])
    body = bytes(cells[address] for address in sorted(cells))
    verified = expect_name is not None
    if verified:
        expected = kit['lanes'][expect_name]
        require(records == expected['records'] and body == expected['expected'] and origin == expected['origin'],
                'Capture does not exactly match the explicit rehearsal expectation')
    numbered_text = ''.join(f'{number} {text}\n' for number, text in numbered)
    base_text = ''.join(f'{number} {text}\n' for number, text in base['numbered'])
    source_diff = ''.join(difflib.unified_diff(base_text.splitlines(keepends=True),
        numbered_text.splitlines(keepends=True), fromfile=base_name + '/source.numbered.txt', tofile='capture/source.numbered.txt'))
    clean_s19 = '\n'.join(_response(s19_raw, 'S19', 131072)) + '\n'
    files = {'source.asm': ('\n'.join(text for _, text in numbered) + '\n').encode('ascii'),
        'source.numbered.txt': numbered_text.encode('ascii'), 'records.bin': records,
        'resident.bin': body, 'resident.s19': clean_s19.encode('ascii'),
        'source.diff': source_diff.encode('ascii'), 'raw-list.txt': list_raw, 'raw-s19.txt': s19_raw}
    mapping = {item['prepared_record_line']: item for item in base['line_mapping']}
    review = dict(schema=1, base_name=base_name, expected_name=expect_name,
        source_complete_verified=verified, source_binary_equivalence=verified,
        review_required=not verified, promotion_requires_review=True, installation_permitted=False,
        board_access=False, serial_ports_opened=0, network_attempts=0,
        authoritative_source_written=False, firmware_generated=False, automatic_reverse_mapping=False,
        completeness=('Entire source and binary equal the explicit known rehearsal lesson' if verified else
            'Unverified draft: LIST has no completion count/checksum; cancellation can return a normal prompt'),
        source_record_count=len(numbered), packed_source_bytes=len(records), origin=origin,
        executable_entry=(kit['lanes'][expect_name]['entry'] if verified else None),
        base_executable_entry_hint=base['entry'], binary_bytes=len(body), binary_sha256=sha(body),
        raw_inputs={'LIST': info(list_raw), 'S19': info(s19_raw)},
        kit_manifest_sha256=sha((kitpath / 'manifest.json').read_bytes()),
        line_provenance=[dict(record_line=number, source_text=text, base_mapping=mapping.get(number),
                              edited_from_base=dict(base['numbered']).get(number) != text)
                         for number, text in numbered],
        files={name: info(raw) for name, raw in sorted(files.items())})
    _write(out, {**files, 'review.json': json_bytes(review)})
    return review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--build', type=Path, required=True)
    prepare.add_argument('--out', type=Path, required=True)
    check = sub.add_parser('check')
    check.add_argument('--kit', type=Path, required=True)
    capture = sub.add_parser('collect')
    capture.add_argument('--kit', type=Path, required=True)
    capture.add_argument('--base', choices=NAMES, required=True)
    capture.add_argument('--expect', choices=NAMES)
    capture.add_argument('--list', dest='list_path', type=Path, required=True)
    capture.add_argument('--s19', type=Path, required=True)
    capture.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            result = build_kit(args.build, args.out)
        elif args.action == 'check':
            result = load_kit(args.kit)['manifest']
        else:
            result = collect(args.kit, args.base, args.list_path, args.s19, args.out, args.expect)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(dict(action=args.action, board_access=False,
                          installation_permitted=False, passed=True), indent=2))
    return result


if __name__ == '__main__':
    main()
