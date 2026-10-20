"""Execute all documented R edits on exact v1g CPU models; never opens ports.

Existing debugger/console models are extracted as definitions only. A separate
full-peripheral model proves the exact volatile MON A/B prompt-entry shim and
the persistent state it preserves. No firmware builder or old main is run.
"""
import argparse
import ast
import binascii
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('C:/SRC/STR8-N')
FIRMWARE_SHA = '6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
DEBUGGER_MODEL_SHA = '5d8fa244a89c4f322d3a0cf034706228f726d4023b9d0dffb2bb65c71f265348'
FULL_MODEL_SHA = '6150988d3612bd895c073741279ee11e6965c02c201fb9591686edd65a3757c7'
MODEL_816_SHA = 'a94fc4c40f3a252b0c5197252ce0ea35310b6f5ada986c40eae16c649d5bfc02'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def definitions(path, names, namespace):
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    for name in names:
        node = next(n for n in main.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def pure_checks(cases):
    rows = cases.parser_cases()
    assert len(rows) == 1438 and len({r['name'] for r in rows}) == len(rows)
    for field in cases.BYTE_FIELDS:
        values = [r['value'] for r in rows if r['field'] == field and r['category'] == 'byte-values']
        assert values == list(range(256))
    before = dict(PC=0x1234, A=1, X=2, Y=3, P=0x24, SP=0xef)
    assert cases.context_dict(cases.context_bytes(before)) == before
    for row in rows:
        after = cases.expected_after(before, row)
        changed = {k for k in before if before[k] != after[k]}
        target = 'PC' if row['field'] == 'PC_HI' else row['field']
        assert changed <= ({target} if row['accepted'] and target else set())
    image = cases.fixture_cells()
    decoded = {}
    for line in cases.fixture_s19().splitlines():
        raw = bytes.fromhex(line[2:]);assert len(raw) == raw[0] + 1 and sum(raw) & 255 == 255
        if line.startswith('S1'):
            address = int.from_bytes(raw[1:3], 'big')
            decoded.update({address + i: v for i, v in enumerate(raw[3:-1])})
    assert decoded == image and min(image) >= 0x200 and max(image) <= 0x64ff
    assert cases.BASELINE['PC'] == 0x413 and bytes(image[0x411 + n] for n in range(2)) == b'\x00\x01'
    for row in cases.resume_cases(False, True):
        assert row['field'] != 'P' or row['value'] & 4
        assert row['field'] != 'SP' or row['value'] >= 9
        assert len(cases.resume_expected(cases.BASELINE, row)) == 6
    assert len(cases.step_resume_cases()) == 12
    return dict(passed=True, parser_cases=len(rows), exhaustive_byte_fields=list(cases.BYTE_FIELDS),
                all_256_values_each=True, fixture_S19_matches_cells=True,
                independent_context_isolation_oracle=True, hardware_resume_IRQ_masked=True, hardware_resume_SP_at_least_9=True)


def make_debugger_model(build, BaseMPU, is816, cases):
    source = ROOT / 'tools/test_rc1_debugger.py'
    assert sha(source) == DEBUGGER_MODEL_SHA
    report = json.loads((build / 'debugger-build.json').read_text())
    allsy = json.loads((build / 'symbols.json').read_text())
    boot = allsy['core/str8n-v2-boot'];xce, restore = boot['BOOT_XCE'], boot['BOOT_XCE_RESTORE']
    globals_ = dict(BaseMPU=BaseMPU, deque=deque, is816=is816, image=(build / 'firmware.bin').read_bytes(),
        out=build, sy=report['debugger_symbols'], allsy=allsy, transcripts=[],
        detector_native_pcs=(xce + 1, xce + 2, xce + 4, restore - 1, restore))
    # s19 is a module-level pure decoder, extracted separately.
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 's19')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), globals_)
    definitions(source, ('Memory', 'MPU', 'run', 'fixture', 'stopped', 'command'), globals_)
    raw_memory = globals_['Memory']
    class GuardedMemory(raw_memory):
        def __setitem__(self, address, value):
            assert not 0x7fc0 <= address <= 0x7fcf, ('Register case attempted peripheral access', hex(address))
            return super().__setitem__(address, value)
    globals_['Memory'] = GuardedMemory
    def begin(slot):
        cpu, memory = globals_['fixture'](slot)
        for address, value in cases.fixture_cells().items():
            memory.ram[address] = value
        cpu.pc, cpu.p, cpu.sp = cases.ENTRY, 0x24, 0xff
        globals_['run'](cpu, lambda: globals_['stopped'](cpu))
        assert bytes(memory.ram[0x7000:0x7007]) == cases.context_bytes(cases.BASELINE)
        return cpu, memory
    globals_['begin'] = begin
    return globals_


def isolation(memory):
    return (bytes(memory.ram[0x200:0x6500]), bytes(memory.ram[0x7100:0x7300]),
            bytes(memory.ram[0x7040:0x7060]), bytes(memory.ram[0x7c30:0x7c80]), bytes(memory.ram[0x7bfc:0x7c00]),
            tuple(bytes(bank) for bank in memory.banks))


def register_matrix(model, cases, exhaustive=True):
    results = []
    run, stopped, command = (model[k] for k in ('run', 'stopped', 'command'))
    for slot in ('A', 'B'):
        cpu, memory = model['begin'](slot)
        for address in (0x0200, 0x0201, 0x0202, 0x0400, 0x0401, cases.RESUME_PC, cases.CAPTURE, 0x64ff):
            command(cpu, f'B {address:04X}')
        assert all(memory.ram[0x7043 + n * 4] for n in range(8)), 'Eight saved breakpoint records required'
        before = dict(cases.BASELINE)
        parser_log, resume_log = hashlib.sha256(), hashlib.sha256()
        parser_rows = cases.parser_cases(exhaustive)
        for row in parser_rows:
            guard = isolation(memory)
            output = command(cpu, row['command'])
            after = cases.context_dict(bytes(memory.ram[0x7000:0x7007]))
            assert after == cases.expected_after(before, row), (slot, row, before, after, output)
            assert cases.error_response(output) == (not row['accepted']), (slot, row, output)
            if row['accepted'] and row['category'] != 'reader-cancel':
                assert cases.parse_display(output) == after
            assert isolation(memory) == guard, ('Parser changed unrelated saved/application state', slot, row)
            assert not memory.writes
            parser_log.update(json.dumps([row['name'], before, after], sort_keys=True).encode())
            before = after
        print('PASS exhaustive register parser', slot, len(parser_rows), flush=True)
        resumes = cases.resume_cases(exhaustive)
        for number, row in enumerate(resumes):
            cpu, memory = model['begin'](slot)
            application_before = bytearray(memory.ram[0x200:0x6500])
            stack_before, zp_before = bytes(memory.ram[0x7100:0x7200]), bytes(memory.ram[0x7200:0x72e0])
            expected = cases.expected_after(cases.BASELINE, row)
            command(cpu, row['command'])
            target = expected['PC']
            memory.rx.extend(b'C\r')
            run(cpu, lambda: cpu.pc == target and memory.bank == 3)
            actual = dict(PC=cpu.pc, A=cpu.a, X=cpu.x, Y=cpu.y, P=cpu.p, SP=cpu.sp)
            assert actual == dict(expected, P=expected['P'] | 0x30), (slot, row, actual, expected)
            if model['is816']:
                assert cpu.mode == 1 and cpu.b == 0xa5 and not cpu.native_detector_steps
            run(cpu, lambda: stopped(cpu))
            trace = bytes(memory.ram[cases.TRACE:cases.TRACE + 6])
            assert trace == cases.resume_expected(cases.BASELINE, row), (slot, row, trace.hex())
            application_before[cases.TRACE - 0x200:cases.TRACE - 0x200 + 6] = trace
            assert bytes(memory.ram[0x200:0x6500]) == application_before, 'Resume modified non-trace application RAM'
            assert bytes(memory.ram[0x7200:0x72e0]) == zp_before
            free = {(trace[4] - n) & 255 for n in range(9)}
            assert all(memory.ram[0x7100 + n] == stack_before[n] for n in range(256) if n not in free), 'Allocated application stack corrupted'
            assert not memory.writes
            resume_log.update(json.dumps([row['name'], actual, trace.hex()], sort_keys=True).encode())
            if number % 256 == 255:
                print('PASS actual register resume', slot, number + 1, flush=True)
        unsafe_count = 0
        for target in cases.UNSAFE_PC_TARGETS:
            for operation in ('C', 'S', 'N'):
                cpu, memory = model['begin'](slot)
                command(cpu, f'R PC={target:04X}')
                guard, context = isolation(memory), bytes(memory.ram[0x7000:0x7007])
                answer = command(cpu, operation)
                assert cases.error_response(answer) and bytes(memory.ram[0x7000:0x7007]) == context
                assert isolation(memory) == guard and not memory.writes
                unsafe_count += 1
        step_log = hashlib.sha256()
        for row in cases.step_resume_cases():
            cpu, memory = model['begin'](slot)
            command(cpu, row['command'])
            answer = command(cpu, row['operation'])
            expected = cases.expected_after(cases.BASELINE, row)
            expected.update(PC=cases.CAPTURE)
            if row['field'] == 'PC':
                expected['SP'] = (expected['SP'] + 2) & 255
            assert not cases.error_response(answer) and cases.context_dict(bytes(memory.ram[0x7000:0x7007])) == expected, (slot, row, answer)
            memory.rx.extend(b'C\r')
            run(cpu, lambda: cpu.pc == cases.CAPTURE and memory.bank == 3)
            assert dict(PC=cpu.pc, A=cpu.a, X=cpu.x, Y=cpu.y, P=cpu.p, SP=cpu.sp) == dict(expected, P=expected['P'] | 0x30)
            run(cpu, lambda: stopped(cpu))
            trace = bytes(memory.ram[cases.TRACE:cases.TRACE + 6])
            assert trace == cases.resume_expected(cases.BASELINE, row) and not memory.writes
            step_log.update(json.dumps([row['name'], expected, trace.hex()], sort_keys=True).encode())
        results.append(dict(slot=slot, passed=True, parser_cases=len(parser_rows), parser_proof_sha256=parser_log.hexdigest(),
            actual_resume_cases=len(resumes), resume_proof_sha256=resume_log.hexdigest(), unsafe_PC_C_S_N_refusals=unsafe_count,
            edited_register_S_N_then_C_cases=12, step_then_resume_proof_sha256=step_log.hexdigest(),
            all_256_A_X_Y_P_SP_values_tested=exhaustive, logical_STACK_ZP_breakpoints_registry_and_application_isolated=True,
            edited_CPU_values_observed_before_first_instruction=True, application_capture_trace_verified=True,
            emulation_status_RTI_forces_bits_4_5=True, native_applications=False, native_debugging=False, flash_write_attempts=0))
    return results


def volatile_slot_shims(build, BaseMPU, is816):
    source = ROOT / 'tools/test_rc1_dbg_full_soak_cpu.py'
    assert sha(source) == FULL_MODEL_SHA
    full = load(source, 'full_peripheral_model_definitions')
    EEPROM, SPI = full.peripheral_classes()
    symbols = json.loads((build / 'symbols.json').read_text());boot = symbols['core/str8n-v2-boot']
    xce, restore = boot['BOOT_XCE'], boot['BOOT_XCE_RESTORE']
    space = dict(BaseMPU=BaseMPU, deque=deque, is816=is816, image=(build / 'firmware.bin').read_bytes(),
        metadata=full.metadata, EEPROM=EEPROM, SPI=SPI, hashlib=hashlib, binascii=binascii,
        detector=(xce + 1, xce + 2, xce + 4, restore - 1, restore))
    definitions(source, ('Memory', 'MPU', 'run', 'snapshot'), space)
    memory = space['Memory']('A');cpu = space['MPU'](memory)
    memory.cpu = memory.spi.cpu = cpu;cpu.p = 0x24
    run = space['run'];mon = symbols['core/monitor-a0']
    run(cpu, lambda: cpu.pc == mon['V2_LINE_BYTE'] and memory.tx.endswith(b'B3> '))
    if is816:
        assert cpu.mode == 1 and cpu.native_steps == len(space['detector'])
        cpu.allow_reset = False;cpu.b = 0xa5
    before = space['snapshot'](memory)
    results, current = [], 'A'
    for slot in ('A', 'B', 'B', 'A'):
        assert bytes(memory.ram[0x7bfc:0x7c00]) == bytes(4), 'Prompt slot shim requires inactive lifecycle'
        target = symbols['core/monitor-' + slot.lower() + '0']['V2_PROMPT_ENTRY']
        assert target == (0xa087 if slot == 'A' else 0xb087)
        shim = bytes((0x78, 0xd8, 0x4c, target & 255, target >> 8))
        memory.ram[0x2000:0x2005] = shim
        old_tx = len(memory.tx)
        counts = (len(memory.bus.writes), len(memory.spi.devices[0].writes), len(memory.spi.devices[0].mode_writes), len(memory.flash_writes))
        original = memory.spi.devices[0].data[0x1ffff]
        native_steps = cpu.native_steps
        memory.rx.extend(b'G 2000\r')
        run(cpu, lambda: not memory.rx and cpu.pc == symbols['core/monitor-' + slot.lower() + '0']['V2_LINE_BYTE']
            and len(memory.tx) > old_tx and memory.tx.endswith(b'B3> '))
        assert memory.ram[0x7d30] == (0xa0 if slot == 'A' else 0xb0)
        assert space['snapshot'](memory) == before, 'Volatile prompt entry mutated persistent state'
        assert len(memory.bus.writes) == counts[0] and len(memory.spi.devices[0].mode_writes) == counts[2]
        assert len(memory.flash_writes) == counts[3] == 0
        probes = full.probe_pairs(memory.spi.devices[0].writes[counts[1]:], original)
        assert bytes(memory.ram[0x2000:0x2005]) == shim
        assert cpu.native_steps == native_steps
        if is816:
            assert cpu.mode == 1 and cpu.b == 0xa5 and (cpu.pbr, cpu.dbr, cpu.dpr) == (0, 0, 0)
        results.append(dict(passed=True, source_slot=current, target_slot=slot, entry=target, shim_hex=shim.hex(),
            BOOT_ACTIVE=memory.ram[0x7d30], persistent_state_unchanged=True, flash_write_attempts=0, I2C_writes=0,
            SPI_mode_writes=0, reserved_SRAM_toggle_restore_pairs=probes, hidden_B_preserved=is816,
            shim_native_steps=0, native_applications=False, native_debugging=False))
        current = slot
    return dict(passed=True, results=results, persistent_snapshot_before=before,
                persistent_snapshot_after=space['snapshot'](memory), reset_detector_native_steps=cpu.native_steps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--build', type=Path, default=ROOT / 'BUILD/rc1-debugger-v1g')
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), default='65c02')
    parser.add_argument('--module', type=Path, default=ROOT / 'tools/rc1_dbg_register_edits.py')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--development-subset', action='store_true')
    args = parser.parse_args()
    inputs = [Path(__file__), args.module,
        *(ROOT / 'tools' / name for name in ('test_rc1_debugger.py', 'test_rc1_dbg_full_soak_cpu.py',
            'test_v2_rtc.py', 'test_v2_i2c.py', 'test_v2_journal.py', 'test_v2_spi_prototype.py')),
        *(args.build / name for name in ('firmware.bin', 'symbols.json', 'debugger-build.json',
            's/core/str8n-v2-worker.s19', 's/core/str8n-v2-vectors.s19', 's/batch/batch-gate.s19'))]
    source_pins = {str(p.resolve()): sha(p) for p in inputs}
    cases = load(args.module, 'register_edit_cases')
    pure = pure_checks(cases)
    if args.check_only:
        print(json.dumps(pure, indent=2));return
    assert args.run and args.run.resolve().is_relative_to((ROOT / 'output/qualification').resolve())
    destination = args.run / ('register-edits-CPU-816.json' if args.cpu == '65c816-e' else 'register-edits-CPU-02.json')
    assert not destination.exists(), 'Never overwrite qualification evidence'
    sys.path[:0] = [str(ROOT / 'BUILD/v1.30/local/test-deps'), str(ROOT / 'BUILD/test-deps-816'), str(ROOT / 'tools')]
    def forbidden(*a, **kw):
        raise AssertionError('No serial or network access in CPU qualification')
    try:
        import serial
    except ModuleNotFoundError:
        serial = None  # No serial dependency is needed by a pure CPU model.
    if serial is not None:
        serial.Serial = forbidden
    socket.socket = forbidden;socket.create_connection = forbidden
    is816 = args.cpu == '65c816-e'
    if is816:
        from py65816.devices.mpu65c816 import MPU as BaseMPU
        assert sha(sys.modules[BaseMPU.__module__].__file__) == MODEL_816_SHA
    else:
        from py65.devices.mpu65c02 import MPU as BaseMPU
    source_pins[str(Path(sys.modules[BaseMPU.__module__].__file__).resolve())] = sha(sys.modules[BaseMPU.__module__].__file__)
    assert sha(args.build / 'firmware.bin') == FIRMWARE_SHA
    model = make_debugger_model(args.build, BaseMPU, is816, cases)
    started = time.monotonic()
    results = register_matrix(model, cases, not args.development_subset)
    shims = volatile_slot_shims(args.build, BaseMPU, is816)
    for path, digest in source_pins.items():
        assert sha(path) == digest, 'Source changed during qualification'
    result = dict(passed=True, CPU=args.cpu, pure_checks=pure, results=results, volatile_monitor_shims=shims,
        firmware_sha256=FIRMWARE_SHA, model_sha256=sha(sys.modules[BaseMPU.__module__].__file__),
        source_pins=source_pins, symbols_sha256=sha(args.build / 'symbols.json'),
        exhaustive=not args.development_subset, elapsed_seconds=time.monotonic() - started,
        parser_cases=sum(v['parser_cases'] for v in results), actual_resume_cases=sum(v['actual_resume_cases'] for v in results),
        unsafe_PC_resume_refusals=sum(v['unsafe_PC_C_S_N_refusals'] for v in results),
        edited_register_step_then_resume_cases=sum(v['edited_register_S_N_then_C_cases'] for v in results),
        board_access=False, network_access=False, native_applications=False, native_debugging=False,
        hardware_IRQ_masking_policy='all P bytes modeled without IRQ injection; real-board resume subset keeps I=1')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in ('results', 'volatile_monitor_shims', 'source_pins')}, indent=2))


if __name__ == '__main__':
    main()
