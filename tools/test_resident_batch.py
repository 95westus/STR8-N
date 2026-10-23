"""Prove the prepared batch gate matches the linked build, offline only."""
import argparse
import json
import os
from pathlib import Path
import shutil

# Reuse the Phase-6 serial/network blockers and checked resident S19 decoder.
from test_resident_contract import ATTEMPTS, parse_s19, sha
from str8build.formats import read_s19
import prepare_resident_batch as prepare


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def files(path):
    return {p.relative_to(path).as_posix(): sha(p.read_bytes())
            for p in path.rglob('*') if p.is_file()}


def refused(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Expected refusal')


def host_checks(build, prepared, out):
    """Independent determinism and stale-input checks in disposable paths."""
    checks = []
    repeat = out / 'repeat-preparation'
    prepare.run(build, repeat)
    assert files(prepared) == files(repeat)
    checks.append('all-five-prepared-files-repeat-byte-identically')
    before = files(repeat)
    refused(lambda: prepare.run(build, repeat))
    assert files(repeat) == before
    checks.append('existing-output-refused-without-mutation')
    raw = (ROOT / 'src/current/batch/batch-gate.asm').read_bytes()
    refused(lambda: prepare.prepare_source(raw.replace(b'        NOP', b'        RTS', 1)))
    checks.append('changed-authoritative-statement-refused')

    # The actual build is never modified. Each corruption affects a scratch copy.
    scratch = out / 'stale-build'
    shutil.copytree(build, scratch)
    corruptions = (
        ('firmware', Path('firmware.bin')),
        ('linked-s19', Path('s/batch/batch-gate.s19')),
        ('linked-map', Path('s/batch/batch-gate.map')),
        ('symbol-inventory', Path('symbols.json')),
    )
    for name, relative in corruptions:
        target = scratch / relative
        original = target.read_bytes()
        if name == 'firmware':
            changed = bytes([original[0] ^ 1]) + original[1:]
        elif name == 'linked-s19':
            changed = original.replace(b'S1', b'S2', 1)
        elif name == 'linked-map':
            changed = original.replace(b'00007c90', b'00007c91', 1)
        else:
            symbols = json.loads(original)
            symbols['batch/batch-gate']['B29_MON'] += 1
            changed = json.dumps(symbols).encode('ascii')
        assert changed != original
        target.write_bytes(changed)
        destination = out / ('refused-' + name)
        refused(lambda: prepare.run(scratch, destination))
        assert not destination.exists()
        target.write_bytes(original)
        checks.append('stale-' + name + '-refused-before-output')
    return checks


def canonical(source):
    result = bytearray(source)
    position = 0
    previous = 0
    while position < len(result):
        assert position + 4 <= len(result)
        number = int.from_bytes(result[position:position + 2], 'little')
        length = result[position + 2]
        assert previous < number <= 65535 and 1 <= length <= 120
        assert position + 4 + length <= len(result)
        assert all(32 <= value <= 126 for value in result[position + 4:position + 4 + length])
        result[position + 3] = 0
        previous = number
        position += 4 + length
    assert position == len(result)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    args = parser.parse_args()
    build, prepared, out = args.build.resolve(), args.prepared.resolve(), args.out.resolve()
    assert not out.exists() and out.is_relative_to(ROOT)
    assert not any(out.is_relative_to(ROOT / name) for name in ('src', 'tools', 'tests', 'docs', 'release', 'archive'))
    assert not out.is_relative_to(build) and not out.is_relative_to(prepared)
    assert not build.is_relative_to(out) and not prepared.is_relative_to(out)
    manifest = json.loads((prepared / 'manifest.json').read_text())
    assert manifest['unit']['source_sha256'] == prepare.SOURCE_SHA
    for name, expected in manifest['files'].items():
        raw = (prepared / name).read_bytes()
        assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256']

    # Decode the fresh host link independently of generated expected.bin.
    cells = read_s19(build / 's/batch/batch-gate.s19')
    assert set(cells) == set(range(0x7C90, 0x7CEC))
    expected = bytes(cells[address] for address in range(0x7C90, 0x7CEC))
    assert len(expected) == 92 and sha(expected) == prepare.BODY_SHA
    assert expected == (prepared / 'expected.bin').read_bytes()
    symbols = json.loads((build / 'symbols.json').read_text())
    expected_symbols = {name: value for name, value in symbols['batch/batch-gate'].items()
                        if not name.startswith('_')}
    assert len(expected_symbols) == 11 and expected_symbols == manifest['assembly']['symbols']
    records = (prepared / 'batch-gate.records.bin').read_bytes()
    assert len(records) == 689 and canonical(records) == records
    assert manifest['admission']['symbol_count'] == 11
    firmware = (build / 'firmware.bin').read_bytes()
    assert sha(firmware) == prepare.FIRMWARE_SHA
    padded = expected + b'\xEA' * 4
    placements = []
    for slot in ('a0', 'b0'):
        address = symbols['core/monitor-' + slot]['B29_GATE_IMAGE']
        assert symbols['core/monitor-' + slot]['B29_GATE_END'] == address + 96
        payload = build / 'payload' / ('str8n-v2-recovery-slot-' + slot + '.bin')
        original = payload.read_bytes()
        offset = address - int(slot, 16) * 256
        assert original[offset:offset + 96] == padded
        replacement = bytearray(original)
        replacement[offset:offset + 96] = padded
        assert replacement == original
        firmware_offset = 2 * 32768 + address - 0x8000
        assert firmware[firmware_offset:firmware_offset + 96] == padded
        placements.append(dict(slot=slot, bank=3, address=address, payload_offset=offset,
                               firmware_offset=firmware_offset, bytes=96))
    assert [p['address'] for p in placements] == [0xAF9F, 0xBF9F]
    assert firmware.count(expected) == 2
    host_s9 = [line for line in (build / 's/batch/batch-gate.s19').read_text().splitlines()
               if line.startswith('S9')]
    assert len(host_s9) == 1 and int.from_bytes(bytes.fromhex(host_s9[0][2:])[1:3], 'big') == 0

    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    checks = host_checks(build, prepared, out)
    os.environ['STR8_SOURCE_BUILD'] = str(build)
    from test_rc1_source_store import Harness
    rows = []
    for cpu in args.cpu or ('65c02', '65c816-e'):
        for slot in ('A', 'B'):
            for edu in (False, True):
                h = Harness(cpu, slot, edu=edu)
                h.open()
                h.command_limit = 30000000
                initial_flash = list(map(bytes, h.m.banks))
                original_gate = bytes(h.m.ram[0x7C90:0x7CF0])
                assert original_gate == padded
                transfers = len(h.m.transfers)
                step = h.cpu.step

                def guarded_step():
                    assert not 0x0200 <= h.cpu.pc < 0x3300, 'Generated output must never execute'
                    return step()

                h.cpu.step = guarded_step
                paste = (prepared / 'batch-gate.paste.txt').read_bytes().decode('ascii').rstrip('\r')
                h.command(paste)
                assert h.source() == records, 'PASTE admission differs from canonical generated records'
                upper_ram = bytes(h.m.ram[0x6500:0x7B00])
                for assembly_pass in range(2):
                    answer = h.command('ASM', contains='OK ')
                    assert 'ORG differs' in answer and 'S 1 AUTO' not in answer
                    assert h.m.ram[0x6306] == 1
                    assert int.from_bytes(h.m.ram[0x6302:0x6304], 'little') == 92
                    assert int.from_bytes(h.m.ram[0x6304:0x6306], 'little') == 0x7C90
                    assert bytes(h.m.ram[0x0200:0x025C]) == expected
                    assert canonical(h.source()) == records
                    top = int.from_bytes(h.m.ram[h.asm['SYMTOP']:h.asm['SYMTOP'] + 2], 'little')
                    table = bytes(h.m.ram[0x4F00:top])
                    assert len(table) == 11 * 20
                    actual_symbols = {table[i:i + 16].rstrip(b'\0').decode('ascii'):
                                      int.from_bytes(table[i + 16:i + 18], 'little')
                                      for i in range(0, len(table), 20)}
                    assert actual_symbols == expected_symbols
                    assert bytes(h.m.ram[0x6500:0x7B00]) == upper_ram
                symbol_reply = h.command('SYMS')
                assert all(name in symbol_reply for name in expected_symbols)
                exported, entry = parse_s19(h.command('S19'))
                assert exported == cells and entry == 0x7C90
                body = bytes(h.m.ram[0x0200:0x025C])
                replacement = bytearray(firmware)
                for placement in placements:
                    start = placement['firmware_offset']
                    replacement[start:start + 96] = body + b'\xEA' * 4
                assert replacement == firmware and sha(replacement) == prepare.FIRMWARE_SHA
                assert list(map(bytes, h.m.banks)) == initial_flash and not h.m.flash_writes
                assert bytes(h.m.ram[0x7C90:0x7CF0]) == original_gate
                assert len(h.m.transfers) == transfers
                profile = f'{cpu}-{slot}-' + ('edu' if edu else 'bare')
                (out / (profile + '.bin')).write_bytes(body)
                save(out / (profile + '-transcript.json'), h.transcripts)
                rows.append(dict(cpu=cpu, slot=slot, edu=edu, passed=True, assembled_twice=True,
                                 output_bytes=92, output_sha256=sha(body), origin=0x7C90,
                                 symbols=actual_symbols, admitted_source_bytes=len(records),
                                 s19_data_equal=True, s19_entry=entry,
                                 packaged_firmware_unchanged=True, generated_gate_executed=False,
                                 modeled_flash_unchanged=True, gate_ram_unchanged=True))
                save(out / 'progress.json', dict(cases=rows, attempts=ATTEMPTS))
                print('PASS', profile, '92 bytes, 11 symbols, S19 and both embedded copies', flush=True)
    assert not ATTEMPTS
    result = dict(passed=True, board_access=False, serial_ports_opened=0, network_attempts=0,
                  hardware_qualified=False, generated_gate_executed=False,
                  firmware_sha256=sha(firmware), output_sha256=sha(expected), output_bytes=92,
                  prepared_manifest_sha256=sha((prepared / 'manifest.json').read_bytes()),
                  source_test_sha256=sha(Path(__file__).read_bytes()),
                  preparation_tool_sha256=sha((ROOT / 'tools/prepare_resident_batch.py').read_bytes()),
                  harness_sha256=sha((ROOT / 'tools/test_rc1_source_store.py').read_bytes()),
                  phase6_helper_sha256=sha((ROOT / 'tools/test_resident_contract.py').read_bytes()),
                  host_checks=checks, case_count=len(rows), cases=rows, placements=placements,
                  packed_source_bytes=len(records), symbol_count=11,
                  prepared_source_lines=manifest['admission']['line_count'],
                  model_scope='Existing monitor/ASM instructions with inherited FT245/discovery/delay model; prepared gate emitted and exported only, never installed or executed',
                  attempts=ATTEMPTS)
    save(out / 'report.json', result)
    print('PASS resident batch gate:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
