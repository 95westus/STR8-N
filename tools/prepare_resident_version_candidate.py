#!/usr/bin/env python3
"""Prepare one separate VERSION tail-call candidate and its offline WDC reference.

The exact Phase-9 source recipe remains immutable. This applies one reviewed
tail-call rewrite in a fresh output directory; it emits no asset, firmware or
installer, and opens no device or network interface.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess

import prepare_resident_version_full as previous
from prepare_resident_batch import ROOT, checked, display, file_info, load, sha
from str8build.formats import read_s19


CANDIDATE_ID = 'version-board-newline-tailcall-v1'
PHASE9_SHA = '264407133f2b131a59bc3b6e1e8c2310485a84019bf628f399c0468a1d2bd5dc'
ORIGIN, BODY_BYTES, BASELINE_BYTES, ENTRY = 0x6E00, 636, 636, 0x6E04
BODY_SHA = '04adfbaf52e8e36ece214c2ccfccab9fdcaf24a3623ca48bb3b22a77f443b2d7'
OLD_LINES = ['JSR $7E7F', 'BN_SHOW_DONE:']
NEW_LINES = ['JMP $7E7F', 'BN_SHOW_DONE:']


def verified_build(build):
    """Check unchanged Phase 9, its preparer and the complete pinned build."""
    phase9_path = ROOT / 'tests/baselines/phase9.json'
    phase9 = json.loads(checked(phase9_path, PHASE9_SHA))
    tool = ROOT / 'tools/prepare_resident_version_full.py'
    checked(tool, phase9['implementation'][display(tool)]['sha256'])
    body, symbols, evidence = previous.verified_build(build)
    evidence[display(phase9_path)] = file_info(phase9_path.read_bytes())
    evidence[display(tool)] = file_info(tool.read_bytes())
    return body, symbols, evidence


def prepare_source(main_raw, links_raw, board_raw):
    """Apply only the reviewed final board-name newline tail call."""
    lines, _, names, mapping = previous.prepare_source(main_raw, links_raw, board_raw)
    matches = [i for i in range(len(lines) - 1) if lines[i:i + 2] == OLD_LINES]
    if matches != [291] or lines[293] != 'RTS':
        raise ValueError('Reviewed resident tail-call sequence differs')
    index = matches[0]
    lines[index:index + 2] = NEW_LINES
    mapping[index]['candidate_patch'] = CANDIDATE_ID
    records = bytearray()
    for number, (line, source) in enumerate(zip(lines, mapping), 1):
        raw = line.encode('ascii')
        if not 1 <= len(raw) <= 120 or any(c < 32 or c > 126 for c in raw):
            raise ValueError('Candidate line exceeds resident admission limits')
        records.extend((number * 10).to_bytes(2, 'little') + bytes([len(raw), 0]) + raw)
        source['prepared_physical_line'] = number
        source['prepared_record_line'] = number * 10
    if len(lines) != 303 or len(records) != 4611 or len(names) != 64:
        raise ValueError('Candidate source extent differs')
    return lines, bytes(records), names, mapping


def host_source(raw):
    """Keep the pinned board include bytes except for the same exact tail call."""
    if sha(raw) != previous.BOARD_SHA:
        raise ValueError('Pinned host board include differs')
    lines = raw.splitlines(keepends=True)
    if [line.strip().decode('ascii') for line in lines[170:173]] != [*OLD_LINES, 'RTS']:
        raise ValueError('Reviewed host tail-call sequence differs')
    lines[170] = lines[170].replace(b'JSR $7E7F', b'JMP $7E7F')
    return b''.join(lines)


def toolchain(build):
    pins = load(build / 'build-report.json')['toolchain']
    result = []
    for name in ('wdc02as', 'wdcln'):
        executable = shutil.which(name)
        if not executable:
            raise ValueError('Install the separately provided WDC02AS and WDCLN on PATH')
        path = Path(executable).resolve()
        matches = [pin for original, pin in pins.items()
                   if Path(original).name.casefold() == path.name.casefold()]
        if len(matches) != 1:
            raise ValueError('WDC executable is absent from the verified build toolchain')
        checked(path, matches[0])
        result.append(str(path))
    return result


def validate_out(build, out):
    protected = ('src', 'tools', 'tests', 'docs', 'release', 'archive', '.git', '.agents', '.codex', '.aws')
    if out.exists() or out == ROOT or not out.is_relative_to(ROOT):
        raise ValueError('--out must be a new directory inside the workspace')
    if any(out.is_relative_to(ROOT / name) for name in protected):
        raise ValueError('--out must not be inside sources or preserved artifacts')
    if out.is_relative_to(build) or build.is_relative_to(out):
        raise ValueError('--out must be separate from the verified build')
    relative = out.relative_to(ROOT)
    if relative.parts[0].casefold() == 'build' and len(relative.parts) > 1:
        if (ROOT / 'BUILD' / relative.parts[1]).exists():
            raise ValueError('--out must not be nested inside an existing BUILD directory')
    if len(str(out / 'host')) > 70:
        raise ValueError('Use a short --out path for the legacy WDC tools')


def run(build, out):
    build, out = build.resolve(), out.resolve()
    validate_out(build, out)
    baseline_body, baseline_symbols, evidence = verified_build(build)
    assembler, linker = toolchain(build)
    originals = {name: checked(ROOT / 'src/current' / name, pin)
                 for name, pin in previous.SOURCE_PINS.items()}
    lines, records, names, mapping = prepare_source(*(originals[name] for name in
                            (previous.SOURCE_NAME, previous.LINKS_NAME, previous.BOARD_NAME)))
    manifest = deepcopy(previous.run(build, out / 'baseline'))
    host = out / 'host'
    host.mkdir()
    for name, raw in originals.items():
        (host / Path(name).name).write_bytes(host_source(raw) if name == previous.BOARD_NAME else raw)
    commands = [[assembler, '-G', '-L', '-S', '-W', '-I', str(host), 'version.asm'],
                [linker, '-g', '-s', '-t', '-c6E00', '-hm19', '-j', '-o', 'version.s19', 'version.obj']]
    log = []
    for command in commands:
        result = subprocess.run(command, cwd=host, capture_output=True, text=True)
        log.append(dict(command=command, returncode=result.returncode,
                        stdout=result.stdout, stderr=result.stderr))
        (host / 'version.log.json').write_text(json.dumps(log, indent=2) + '\n', encoding='utf-8')
        if result.returncode:
            raise ValueError('Offline candidate WDC reference failed; inspect host/version.log.json')
    pairs = re.findall(r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$',
                       (host / 'version.map').read_text(), re.M)
    host_symbols = {name: int(value, 16) for value, name in pairs}
    if len(host_symbols) != len(pairs):
        raise ValueError('Candidate WDC map contains duplicate symbols')
    original_symbols = {name: value for name, value in host_symbols.items() if not name.startswith('_')}
    symbols = {previous.ALIASES.get(name, name): value for name, value in original_symbols.items()}
    if symbols != baseline_symbols or names != set(symbols):
        raise ValueError('Candidate host symbols must all remain equal to the baseline')
    cells = read_s19(host / 'version.s19')
    if set(cells) != set(range(ORIGIN, ORIGIN + BODY_BYTES)) or host_symbols['APP_END'] != ORIGIN + BODY_BYTES:
        raise ValueError('Candidate WDC link is not the exact contiguous 636-byte body')
    body = bytes(cells[address] for address in range(ORIGIN, ORIGIN + BODY_BYTES))
    differences = [(i, old, new) for i, (old, new) in enumerate(zip(baseline_body, body)) if old != new]
    if sha(body) != BODY_SHA or differences != [(0x25C, 0x20, 0x4C)]:
        raise ValueError('Candidate must differ only at $705C: JSR opcode $20 to JMP $4C')
    files = {'version.asm': ('\n'.join(lines) + '\n').encode('ascii'),
             'version.paste.txt': ('PASTE\r' + '\r'.join(lines) + '\r.\r').encode('ascii'),
             'version.records.bin': records, 'expected.bin': body}
    manifest['unit'].update(name='version/version-candidate', candidate_id=CANDIDATE_ID,
                            phase9_manifest_sha256=PHASE9_SHA, candidate_is_current_firmware=False)
    manifest['assembly'].update(end_exclusive=ORIGIN + BODY_BYTES, expected_bytes=BODY_BYTES,
                                symbols=symbols, original_symbols=original_symbols,
                                exports={name: symbols[name] for name in ('START', 'APP_END')})
    manifest['preparation'].update(recipe=CANDIDATE_ID, line_mapping=mapping)
    for name, reservation in manifest['preparation']['reservations'].items():
        reservation['logical_address'] = symbols[name]
    manifest['admission'].update(line_count=len(lines), packed_source_bytes=len(records),
                                 packed_source_end_exclusive=0x3300 + len(records),
                                 max_line_bytes=max(map(len, lines)))
    manifest['verification'].update(expected_output_sha256=BODY_SHA,
        expected_bytes_from='host/version.s19', inputs=evidence,
        required_next_check='Resident PASTE/ASM byte/symbol equivalence and differential behavior against unchanged current VERSION')
    manifest['storage'].update(kind='Separate VERSION RAM body candidate; enclosing current asset is reference only',
                               candidate_stored_in_enclosing_asset=False)
    manifest['packaging'].update(body_bytes=BODY_BYTES,
        preserve=['No asset or firmware is generated; current assets, vectors, worker and seal remain untouched'],
        replacement_rule='Candidate is a separate RAM body only; current asset/firmware byte identity is not claimed')
    manifest['candidate'] = dict(id=CANDIDATE_ID, objective='Use a tail call for the final named-board newline',
        reviewed_patch={'authoritative_source': 'src/current/' + previous.BOARD_NAME,
                        'source_lines': [171, 172], 'before': OLD_LINES, 'after': NEW_LINES},
        baseline_bytes=BASELINE_BYTES, candidate_bytes=BODY_BYTES, saved_bytes=0,
        baseline_sha256=sha(baseline_body), candidate_sha256=BODY_SHA,
        baseline_preparation='baseline/manifest.json', baseline_symbols=baseline_symbols,
        relocated_symbols={}, unchanged_symbol_count=64,
        changed_bytes=[{'offset': offset, 'address': ORIGIN + offset, 'baseline': old, 'candidate': new}
                       for offset, old, new in differences],
        tail_call={'address': 0x705C, 'service': 0x7E7F, 'empty_name_exit_retained': 'BN_SHOW_DONE',
                   'named_display_saved_cycles': 9, 'named_display_saved_instructions': 1,
                   'newline_pending_return_bytes_saved': 2, 'empty_name_path_changed': False,
                   'newline_scope': 'Two fewer pending return bytes during the final newline only; whole-command peak stack use is not claimed'},
        timing_claim='Named-board display removes one JSR/RTS pair in favor of JMP; zero-name path is unchanged',
        firmware_installable=False, hardware_execution_authorized=False)
    manifest['host_reference'] = dict(compiler='WDC02AS', linker='WDCLN', independent_host_source='host/version.asm',
        source_patch_applied_before_host_assembly=True, resident_output_not_used_for_host_reference=True,
        toolchain={display(Path(path)): file_info(Path(path).read_bytes()) for path in (assembler, linker)},
        files={path.name: file_info(path.read_bytes()) for path in sorted(host.iterdir()) if path.is_file()})
    manifest['files'] = {name: file_info(raw) for name, raw in files.items()}
    for name, raw in files.items():
        (out / name).write_bytes(raw)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
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
    print(json.dumps(dict(candidate=CANDIDATE_ID, output=display(args.out.resolve()),
                          admission=manifest['admission'], bytes=BODY_BYTES, board_access=False), indent=2))


if __name__ == '__main__':
    main()
