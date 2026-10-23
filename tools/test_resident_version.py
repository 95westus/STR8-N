"""Verify resident VERSION formatting bytes and isolated behavior, offline."""
import argparse
import json
import os
from pathlib import Path
import shutil

from test_resident_contract import ATTEMPTS, parse_s19, sha
from test_resident_batch import canonical, files, refused
from str8build.formats import read_s19
import prepare_resident_version as prepare


ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def host_checks(build, prepared, out):
    repeat = out / 'repeat-preparation'
    prepare.run(build, repeat)
    assert files(prepared) == files(repeat)
    before = files(repeat)
    refused(lambda: prepare.run(build, repeat))
    assert files(repeat) == before
    raw = (ROOT / 'src/current/version/version.asm').read_bytes()
    refused(lambda: prepare.prepare_source(raw.replace(b'SLOT_LETTER:', b'OTHER_SLOT:', 1)))
    checks = ['deterministic-preparation', 'existing-output-refused-unchanged', 'changed-source-refused']
    scratch = out / 'stale-build'
    shutil.copytree(build, scratch)
    for name, relative in (
        ('firmware', 'firmware.bin'), ('version-asset', 'payload/version/asset.bin'),
        ('version-s19', 's/version/version.s19'), ('version-map', 's/version/version.map'),
        ('symbol-inventory', 'symbols.json'), ('staged-source', 's/version/version.asm'),
    ):
        path = scratch / relative
        original = path.read_bytes()
        if name in ('firmware', 'version-asset'):
            changed = bytes([original[0] ^ 1]) + original[1:]
        elif name == 'version-s19':
            changed = original.replace(b'S1', b'S2', 1)
        elif name == 'version-map':
            changed = original.replace(b'00006ebb', b'00006ebc', 1)
        elif name == 'staged-source':
            changed = original.replace(b'SLOT_LETTER:', b'OTHER_SLOT:', 1)
        else:
            symbols = json.loads(original)
            symbols['version/version']['PRINT'] += 1
            changed = json.dumps(symbols).encode('ascii')
        assert changed != original
        path.write_bytes(changed)
        destination = out / ('refused-' + name)
        refused(lambda: prepare.run(scratch, destination))
        assert not destination.exists()
        path.write_bytes(original)
        checks.append('stale-' + name + '-refused-before-output')
    return checks


def execute(body, cpu_class, cpu_name, entry, *, a=0, x=0, y=0, pointer=None, text=b'', dispatch=None):
    """Isolated RAM fixture: only PUTC and an indirect formatter are ABI stubs."""
    memory = bytearray(65536)
    memory[prepare.ORIGIN:prepare.ORIGIN + 35] = body
    if pointer is not None:
        assert b'\0' not in text and pointer + len(text) < 0x6000
        memory[pointer:pointer + len(text) + 1] = text + b'\0'
        x, y = pointer & 255, pointer >> 8
    if dispatch is not None:
        memory[0x6F26:0x6F28] = dispatch.to_bytes(2, 'little')
    cpu = cpu_class(memory=memory, pc=entry)
    cpu.pc, cpu.p, cpu.sp = entry, 0x24, 255
    cpu.a, cpu.x, cpu.y = a, x, y
    if cpu_name == '65c816-e':
        cpu.mode, cpu.b = 1, 0xA5
        cpu.dpr = cpu.dbr = cpu.pbr = 0
    original = bytes(memory)
    sentinel = 0x7B00
    cpu.stPushWord(sentinel - 1)
    output, targets, trace = bytearray(), [], []
    for _ in range(100000):
        if cpu.pc == sentinel:
            break
        trace.append([cpu.pc, cpu.a, cpu.x, cpu.y, cpu.sp, cpu.p])
        if cpu.pc == 0x7E6D:
            output.append(cpu.a & 255)
            cpu.pc = (cpu.stPopWord() + 1) & 65535
        elif dispatch is not None and cpu.pc == dispatch:
            targets.append(dict(target=dispatch, a=cpu.a, x=cpu.x, y=cpu.y))
            cpu.pc = (cpu.stPopWord() + 1) & 65535
        else:
            assert prepare.ORIGIN <= cpu.pc < prepare.ORIGIN + 35, 'Unexpected fixture execution'
            cpu.step()
        if cpu_name == '65c816-e':
            assert cpu.mode == 1 and cpu.b == 0xA5 and (cpu.dpr, cpu.dbr, cpu.pbr) == (0, 0, 0)
    else:
        raise AssertionError('Formatting fixture did not return')
    assert cpu.sp == 255 and cpu.pc == sentinel
    changes = [i for i, (old, new) in enumerate(zip(original, memory)) if old != new]
    assert all(0x100 <= address < 0x200 or address in (0xD0, 0xD1) for address in changes)
    assert memory[prepare.ORIGIN:prepare.ORIGIN + 35] == body
    return dict(output_hex=output.hex(), dispatches=targets,
                final=dict(a=cpu.a, x=cpu.x, y=cpu.y, sp=cpu.sp, p=cpu.p),
                pointer=int.from_bytes(memory[0xD0:0xD2], 'little'),
                steps=len(trace), trace_sha256=sha(json.dumps(trace).encode('ascii')),
                ram_changes_sha256=sha(bytes(memory[i] for i in changes)),
                ram_changed_addresses=changes)


def behavior_checks(expected, actual, cpu_class, cpu_name, cells, symbols):
    rows = []

    def pair(name, entry, **values):
        host = execute(expected, cpu_class, cpu_name, entry, **values)
        resident = execute(actual, cpu_class, cpu_name, entry, **values)
        assert host == resident, name
        rows.append(dict(name=name, passed=True, host_resident_equal=True, **resident))
        return resident

    for value in range(256):
        result = pair(f'slot-{value:02x}', prepare.ENTRIES['SLOT_LETTER'], a=value, x=0x37, y=0x59)
        assert bytes.fromhex(result['output_hex']) == (b'A' if value < 0xB0 else b'B')
        assert result['final']['x'] == 0x37 and result['final']['y'] == 0x59
    strings = [('empty', 0x4000, b''), ('page-crossing', 0x40FC, b'PAGE-CROSS\r\n'),
               ('high-bit-bytes', 0x4100, bytes([0x80, 0xFE, 0xFF, 0x41]))]
    for length in (255, 256, 257, 513):
        strings.append((f'length-{length}', 0x40F0, bytes(33 + i % 90 for i in range(length))))
    for name in ('UNNAMED_TEXT', 'RUNNING_TEXT', 'GEN_TEXT', 'BAD_RUNNING_TEXT'):
        address = symbols[name]
        data = bytearray()
        while cells[address]:
            data.append(cells[address])
            address += 1
        strings.append(('version-' + name.lower(), 0x4207, bytes(data)))
    for name, pointer, text in strings:
        result = pair(name, prepare.ENTRIES['PRINT'], pointer=pointer, text=text)
        assert bytes.fromhex(result['output_hex']) == text
        assert result['pointer'] == pointer + (len(text) // 256) * 256
        assert result['final']['a'] == 0 and result['final']['x'] == pointer & 255
        assert result['final']['y'] == len(text) % 256
    for target in (0x6810, 0x6900):
        result = pair(f'indirect-{target:04x}', prepare.ENTRIES['MON_PRINT'],
                      a=0x5A, x=0x17, y=0xC3, dispatch=target)
        assert result['dispatches'] == [dict(target=target, a=0x5A, x=0x17, y=0xC3)]
        assert result['output_hex'] == ''
        assert (result['final']['a'], result['final']['x'], result['final']['y']) == (0x5A, 0x17, 0xC3)
    assert len(rows) == 269
    return dict(cpu=cpu_name, passed=True, case_count=len(rows), host_and_resident_executions=2 * len(rows),
                scope='Isolated helper machine code with PUTC/indirect-formatter ABI stubs; no live monitor, bootstrap or storage execution',
                cases=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'prepared', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), action='append')
    args = parser.parse_args()
    build, prepared, out = args.build.resolve(), args.prepared.resolve(), args.out.resolve()
    assert not out.exists() and out.is_relative_to(ROOT)
    assert not any(out.is_relative_to(ROOT / name) for name in ('src', 'tools', 'tests', 'docs', 'release', 'archive'))
    assert not any(out.is_relative_to(path) or path.is_relative_to(out) for path in (build, prepared))
    manifest = json.loads((prepared / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        raw = (prepared / name).read_bytes()
        assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256']
    cells = read_s19(build / 's/version/version.s19')
    assert set(cells) == set(range(0x6E00, 0x707C))
    expected = bytes(cells[address] for address in range(0x6EBB, 0x6EDE))
    assert len(expected) == 35 and sha(expected) == prepare.BODY_SHA
    assert (prepared / 'expected.bin').read_bytes() == expected
    symbols = json.loads((build / 'symbols.json').read_text())['version/version']
    expected_symbols = {name: symbols[name] for name in prepare.SYMBOLS}
    assert expected_symbols == manifest['assembly']['symbols']
    records = (prepared / 'version-format.records.bin').read_bytes()
    assert len(records) == 371 and canonical(records) == records
    asset = (build / 'payload/version/asset.bin').read_bytes()
    firmware = (build / 'firmware.bin').read_bytes()
    assert len(asset) == 2048 and sha(firmware) == prepare.FIRMWARE_SHA
    assert asset[0xBB:0xDE] == expected and firmware[0xF8BB:0xF8DE] == expected
    assert firmware[0xF800:0x10000] == asset
    host_s9 = [line for line in (build / 's/version/version.s19').read_text().splitlines() if line.startswith('S9')]
    assert len(host_s9) == 1 and int.from_bytes(bytes.fromhex(host_s9[0][2:])[1:3], 'big') == 0
    out.mkdir(parents=True)
    (out / '.gitignore').write_text('*\n')
    checks = host_checks(build, prepared, out)
    os.environ['STR8_SOURCE_BUILD'] = str(build)
    from test_rc1_source_store import Harness
    rows, behavior = [], []
    for cpu_name in args.cpu or ('65c02', '65c816-e'):
        for slot in ('A', 'B'):
            for edu in (False, True):
                h = Harness(cpu_name, slot, edu=edu)
                h.open()
                h.command_limit = 30000000
                flash = list(map(bytes, h.m.banks))
                transfers = len(h.m.transfers)
                upper_ram = bytes(h.m.ram[0x6500:0x7B00])
                step = h.cpu.step

                def guarded_step():
                    assert not 0x0200 <= h.cpu.pc < 0x3300, 'Physical output buffer must never execute'
                    return step()

                h.cpu.step = guarded_step
                h.command((prepared / 'version-format.paste.txt').read_bytes().decode('ascii').rstrip('\r'))
                assert h.source() == records
                for _ in range(2):
                    reply = h.command('ASM', contains='OK ')
                    assert 'ORG differs' in reply and 'S 1 AUTO' not in reply
                    assert h.m.ram[0x6306] == 1
                    assert int.from_bytes(h.m.ram[0x6302:0x6304], 'little') == 35
                    assert int.from_bytes(h.m.ram[0x6304:0x6306], 'little') == 0x6EBB
                    body = bytes(h.m.ram[0x0200:0x0223])
                    assert body == expected and canonical(h.source()) == records
                    top = int.from_bytes(h.m.ram[h.asm['SYMTOP']:h.asm['SYMTOP'] + 2], 'little')
                    table = bytes(h.m.ram[0x4F00:top])
                    assert len(table) == 8 * 20
                    actual_symbols = {table[i:i + 16].rstrip(b'\0').decode('ascii'):
                                      int.from_bytes(table[i + 16:i + 18], 'little') for i in range(0, len(table), 20)}
                    assert actual_symbols == expected_symbols
                symbol_reply = h.command('SYMS')
                assert all(name in symbol_reply for name in expected_symbols)
                exported, entry = parse_s19(h.command('S19'))
                assert exported == dict(enumerate(expected, 0x6EBB)) and entry == 0x6EBB
                changed_asset, changed_firmware = bytearray(asset), bytearray(firmware)
                changed_asset[0xBB:0xDE] = body
                changed_firmware[0xF8BB:0xF8DE] = body
                assert changed_asset == asset and changed_firmware == firmware
                assert bytes(h.m.ram[0x6500:0x7B00]) == upper_ram
                assert list(map(bytes, h.m.banks)) == flash and not h.m.flash_writes
                assert len(h.m.transfers) == transfers
                profile = f'{cpu_name}-{slot}-' + ('edu' if edu else 'bare')
                (out / (profile + '.bin')).write_bytes(body)
                save(out / (profile + '-transcript.json'), h.transcripts)
                rows.append(dict(cpu=cpu_name, slot=slot, edu=edu, passed=True, assembled_twice=True,
                                 output_bytes=35, output_sha256=sha(body), origin=0x6EBB,
                                 symbols=actual_symbols, admitted_source_bytes=371, s19_data_equal=True,
                                 s19_entry=entry, packaged_asset_and_firmware_unchanged=True,
                                 modeled_flash_unchanged=True, upper_ram_unchanged=True))
                save(out / 'progress.json', dict(cases=rows, attempts=ATTEMPTS))
                print('PASS', profile, '35 bytes, 8 symbols, export and VERSION asset', flush=True)
                if slot == 'A' and not edu:
                    behavior.append(behavior_checks(expected, body, type(h.cpu), cpu_name, cells, symbols))
                    save(out / ('behavior-' + cpu_name + '.json'), behavior[-1])
                    print('PASS', cpu_name, '269 host/resident formatter behavior pairs with ABI stubs', flush=True)
    assert not ATTEMPTS
    save(out / 'report.json', dict(
        passed=True, board_access=False, serial_ports_opened=0, network_attempts=0,
        hardware_qualified=False, resident_output_installed=False, physical_output_executed=False,
        isolated_helper_model_execution=True, firmware_sha256=sha(firmware), asset_sha256=sha(asset),
        output_bytes=35, output_sha256=sha(expected), packed_source_bytes=371, symbol_count=8,
        source_test_sha256=sha(Path(__file__).read_bytes()),
        preparation_tool_sha256=sha((ROOT / 'tools/prepare_resident_version.py').read_bytes()),
        prepared_manifest_sha256=sha((prepared / 'manifest.json').read_bytes()),
        inherited_helpers={name: sha((ROOT / 'tools' / name).read_bytes()) for name in
                           ('prepare_resident_batch.py', 'test_resident_batch.py', 'test_resident_contract.py', 'test_rc1_source_store.py')},
        host_checks=checks, case_count=len(rows), cases=rows,
        behavior=[dict(cpu=value['cpu'], cases=value['case_count'], executions=value['host_and_resident_executions'],
                       scope=value['scope']) for value in behavior], attempts=ATTEMPTS,
        model_scope='Existing ASM/monitor CPU models for assembly; separate RAM CPU fixtures for three formatting entries with PUTC and indirect-dispatch ABI stubs; no full VERSION or hardware qualification'))
    print('PASS resident VERSION formatting:', out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
