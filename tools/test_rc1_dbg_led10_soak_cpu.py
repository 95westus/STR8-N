"""Qualify ten-pattern bounded onboard-ASM LED sources on exact v1g CPU/peripheral models.

No old builder/main is executed. Four canonical sources are assembled/exported
in each CPU/monitor combination; one complete 630-frame variant executes in
each combination, for sixteen assemblies and four complete executions total.
The two CPU invocations publish separate evidence for a subsequent image join.
"""
import argparse
import ast
import binascii
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace


# This harness is copied into immutable qualification runs before execution.
# Its location must not redefine the workspace, model dependencies or fixtures.
ROOT = Path('C:/SRC/STR8-N')
FULL_MODEL_SHA256 = '6150988d3612bd895c073741279ee11e6965c02c201fb9591686edd65a3757c7'
EXPECTED_FIRMWARE = '6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b'
MODEL_816_SHA256 = 'a94fc4c40f3a252b0c5197252ce0ea35310b6f5ada986c40eae16c649d5bfc02'
EXECUTION_SEEDS = {'65c02': {'A': 0x12, 'B': 0x25},
                   '65c816-e': {'A': 0x38, 'B': 0x4b}}
LED_PORT, LED_CRA = 0x7fa0, 0x7fa1
B3, ASM, DBG = b'\r\nB3> ', b'ASM> ', b'DBG> '
PATTERN_SIZES = (8, 256, 256, 16, 16, 14, 8, 16, 8, 32)
PATTERN_NAMES = ('wigwag', 'gray-code', 'binary-counter', 'walking-one',
                 'walking-zero', 'bouncing-dot', 'checkerboard', 'fill-drain',
                 'expanding-contracting-pairs', 'lfsr-sparkle')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_model_definitions(path, namespace):
    """Extract model definitions from the trusted old main, never its actions."""
    assert sha(path) == FULL_MODEL_SHA256, 'Unexpected parent model source'
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    for name in ('Memory', 'MPU', 'run', 'snapshot'):
        node = next(node for node in main.body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def application_ram_writes(led):
    return ((0x0100, 0x01ff), (led.META, led.META + led.META_BYTES - 1),
            (led.WRITE_TRACE, led.WRITE_TRACE + led.FRAME_COUNT - 1),
            (led.READ_TRACE, led.READ_TRACE + led.FRAME_COUNT - 1),
            (0x6040, 0x6042))


def check_application_write(address, led):
    """Only the LED latch and explicitly allocated application scratch exist."""
    assert address == LED_PORT or any(first <= address <= last for first, last in application_ram_writes(led)), (
        'LED application write outside admitted RAM/LED port', hex(address))


def expected_frames(seed):
    """Independent specification oracle; it never consumes source/table bytes."""
    walking = [1 << bit for bit in range(8)] * 2
    sparkle, state = [], seed
    for _ in range(32):
        sparkle.append(state)
        state = (state >> 1) ^ (0xb8 if state & 1 else 0)
    values = [0xf0, 0x0f] * 4
    values += [((seed + i) & 255) ^ (((seed + i) & 255) >> 1) for i in range(256)]
    values += [(seed + i) & 255 for i in range(256)]
    values += walking + [value ^ 255 for value in walking]
    values += [1 << bit for bit in (*range(8), *range(6, 0, -1))]
    values += [0xaa, 0x55] * 4
    values += [(1 << width) - 1 for width in (*range(1, 9), *range(7, -1, -1))]
    values += [0x18, 0x3c, 0x7e, 0xff, 0x7e, 0x3c, 0x18, 0]
    return bytes(values + sparkle)


def check_source_contract(led):
    assert led.FRAME_COUNT == sum(PATTERN_SIZES) == 630
    assert led.PATTERN_COUNT == len(PATTERN_NAMES) == 10
    assert tuple(led.PATTERN_NAMES) == PATTERN_NAMES
    assert led.LED_PORT == LED_PORT and led.LED_CRA == LED_CRA
    assert led.ENTRY == 0x200 and led.META == 0x600 and led.META_BYTES == 14
    assert led.WRITE_TRACE == 0x800 and led.READ_TRACE == 0xb00
    assert len(led.PATTERNS) == led.PATTERN_COUNT
    offset, lower, upper = 0, 0, 0
    for index, pattern in enumerate(led.PATTERNS):
        assert pattern['name'] == PATTERN_NAMES[index]
        assert pattern['offset'] == offset and pattern['frames'] == PATTERN_SIZES[index]
        low, high = pattern['frame_cycle_bounds']
        expected_class = 'slow' if index == 0 else 'fast' if index < 3 else 'medium'
        assert pattern['dwell_class'] == expected_class
        allowed = {'slow': (1_300_000, 1_800_000), 'fast': (100_000, 150_000),
                   'medium': (320_000, 450_000)}[expected_class]
        assert 0 < allowed[0] <= low <= high <= allowed[1]
        lower += low * pattern['frames']
        upper += high * pattern['frames']
        offset += pattern['frames']
    assert offset == led.FRAME_COUNT
    total_low, total_high = led.CPU_TOTAL_CYCLE_BOUNDS
    assert 0 < total_low <= lower and upper <= total_high <= upper + 1_000_000
    cases = led.cases()
    assert len(cases) == 4 and [case['seed'] for case in cases] == [0x12, 0x25, 0x38, 0x4b]
    assert len({case['name'] for case in cases}) == 4
    for case in cases:
        assert bytes.fromhex(case['expected_frame_hex']) == expected_frames(case['seed'])
        assert case['frame_count'] == led.FRAME_COUNT
    return dict(passed=True, patterns=list(PATTERN_NAMES), frames=offset,
                independent_frame_oracle=True,
                CPU_total_cycle_bounds=[total_low, total_high],
                instruction_bound=total_high // 2 + 65_536,
                RAM_write_ranges=[list(row) for row in application_ram_writes(led)])


def check_led_events(events, expected, entry_latch, total_cycles, led):
    """An independent physical-latch oracle, separate from exported RAM traces."""
    assert len(expected) == led.FRAME_COUNT
    assert [event['address'] for event in events] == [LED_PORT] * (led.FRAME_COUNT + 1)
    assert [event['value'] for event in events] == [*expected, entry_latch], 'Physical LED frame order/restore mismatch'
    intervals = [b['cycles'] - a['cycles'] for a, b in zip(events, events[1:])]
    # The real delay instructions execute without acceleration. Broad bounds
    # allow CPU branch/page differences while excluding missing/skipped delays.
    pattern_proofs = []
    for pattern in led.PATTERNS:
        start, count = pattern['offset'], pattern['frames']
        segment = intervals[start:start+count]
        low, high = pattern['frame_cycle_bounds']
        assert len(segment) == count and all(low <= delay <= high for delay in segment), (
            'Pattern dwell cycles', pattern['name'], min(segment), max(segment), (low, high))
        pattern_proofs.append(dict(name=pattern['name'], offset=start, frames=count,
                                   interval_cycles=[min(segment), max(segment)],
                                   allowed_interval_cycles=[low, high], exact_frame_order=True))
    low, high = led.CPU_TOTAL_CYCLE_BOUNDS
    assert low <= total_cycles <= high, ('LED execution cycle bound', total_cycles, (low, high))
    return dict(passed=True, writes=len(events), frames=led.FRAME_COUNT,
                exact_frame_order=True, entry_latch_restored_before_BRK=True,
                patterns=pattern_proofs, patterns_completed=led.PATTERN_COUNT,
                execution_cycles=total_cycles,
                nominal_seconds_at_8MHz=total_cycles / 8_000_000,
                delay_instructions_accelerated=False)


def decode_export(answer):
    cells, entry = {}, None
    # The console echoes the command "S19". Require complete byte pairs and
    # the minimum count/address/checksum record size before decoding a row.
    rows = re.findall(rb'(?m)^S[019](?:[0-9A-F]{2}){4,}\r?$', answer)
    assert rows, 'ASM emitted no S-record export'
    for line in rows:
        line = line.strip()
        raw = bytes.fromhex(line[2:].decode())
        assert len(raw) == raw[0] + 1 and sum(raw) & 255 == 255
        address = int.from_bytes(raw[1:3], 'big')
        if line.startswith(b'S1'):
            for offset, value in enumerate(raw[3:-1]):
                assert address + offset not in cells, 'Overlapping ASM S-record export'
                cells[address + offset] = value
        elif line.startswith(b'S9'):
            assert entry is None and len(raw) == 4
            entry = address
    assert entry == 0x200 and cells and min(cells) == 0x200
    assert set(cells) == set(range(0x200, max(cells) + 1)), 'Sparse ASM export'
    return bytes(cells[address] for address in sorted(cells))


def self_checks(led):
    """Pure guard checks; no CPU model, firmware execution or board access."""
    checks = 0
    for address in (0x0100, 0x01ff, led.META, led.META+led.META_BYTES-1,
                    led.WRITE_TRACE, led.WRITE_TRACE+led.FRAME_COUNT-1,
                    led.READ_TRACE, led.READ_TRACE+led.FRAME_COUNT-1,
                    0x6040, 0x6042, LED_PORT):
        check_application_write(address, led)
        checks += 1
    for address in (LED_CRA, 0x7fec, 0x7fc0, 0x7fcf, 0x8000, 0x0200, 0x060e,
                    0x0000, 0x6043, led.WRITE_TRACE+led.FRAME_COUNT,
                    led.READ_TRACE+led.FRAME_COUNT, 0x1ffff):
        try:
            check_application_write(address, led)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError(('Guard accepted unexpected address', address))
    # These synthetic events exercise refusal logic only. They are never used
    # as a golden image or execution evidence; those require actual ROM ASM.
    frames = expected_frames(0x12)
    ticks = 0
    events = []
    for index, value in enumerate([*frames, 0x41]):
        events.append(dict(address=LED_PORT, value=value, cycles=ticks))
        if index < led.FRAME_COUNT:
            pattern = next(item for item in led.PATTERNS
                           if item['offset'] <= index < item['offset']+item['frames'])
            low, high = pattern['frame_cycle_bounds']
            ticks += (low + high) // 2
    total = events[-1]['cycles'] + 200
    assert check_led_events(events, frames, 0x41, total, led)['passed']
    checks += 1
    for change in ('value', 'address', 'cycles'):
        bad = [dict(event) for event in events]
        bad[1][change] ^= 1 if change != 'cycles' else 100_000_000
        try:
            check_led_events(bad, frames, 0x41, total, led)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError(('Event guard accepted', change))
    for pattern in led.PATTERNS:
        # Corrupt the first interval in every separate pattern, including the
        # last table phase: aggregate elapsed time alone must not accept it.
        bad = [dict(event) for event in events]
        bad[pattern['offset']+1]['cycles'] = bad[pattern['offset']]['cycles'] + 1
        try:
            check_led_events(bad, frames, 0x41, total, led)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError(('Pattern dwell guard accepted', pattern['name']))
    for bad in (events[:-1], [dict(event) for event in events]):
        if len(bad) == len(events):
            bad[-1]['value'] ^= 1
        try:
            check_led_events(bad, frames, 0x41, total, led)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError('Missing/wrong restore accepted')
    for field, value in (('FRAME_COUNT', 629), ('PATTERN_COUNT', 9),
                         ('WRITE_TRACE', 0x801), ('PATTERN_NAMES', tuple(reversed(PATTERN_NAMES)))):
        mutated = SimpleNamespace(**vars(led))
        setattr(mutated, field, value)
        try:
            check_source_contract(mutated)
        except AssertionError:
            checks += 1
        else:
            raise AssertionError(('Source contract mutation accepted', field))
    def export_row(kind, data):
        raw = bytes([len(data)+3, 2, 0]) + data
        return b'S' + kind + (raw+bytes([(~sum(raw))&255])).hex().upper().encode()
    exported = b'\x78\x00\x01'
    echoed = b'S19\r\n' + export_row(b'1', exported) + b'\r\n' + export_row(b'9', b'') + b'\r\nASM> '
    assert decode_export(echoed) == exported, 'Echoed S19 command misclassified as a record'
    checks += 1
    try:
        decode_export(b'S19\r\nASM> ')
    except AssertionError:
        checks += 1
    else:
        raise AssertionError('Echo alone accepted as an S-record export')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--build', type=Path, default=ROOT/'BUILD/rc1-debugger-v1g')
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'))
    parser.add_argument('--module', type=Path, default=ROOT/'tools/rc1_dbg_led10_soak.py')
    parser.add_argument('--full-model', type=Path, default=ROOT/'tools/test_rc1_dbg_full_soak_cpu.py')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    module = load_source(args.module, 'led10_source_contract_check')
    contract = check_source_contract(module)
    guard_checks = self_checks(module)
    if args.check_only:
        assert sha(args.full_model) == FULL_MODEL_SHA256
        print('PASS', guard_checks, 'pure LED trace/write-allowlist guards and source contract; no CPU or boards')
        return
    assert args.run is not None and args.cpu is not None, '--run and --cpu required for actual model execution'
    assert args.run.resolve().is_relative_to((ROOT/'output/qualification').resolve())
    assert args.run.is_dir(), 'Use a separately prepared qualification directory'
    is816 = args.cpu == '65c816-e'
    suffix = '816' if is816 else '02'
    output = args.run / f'LED-CPU-{suffix}.json'
    cases_output = args.run / f'led-cases-{suffix}.json'
    assert not output.exists() and not cases_output.exists(), 'Never overwrite qualification results'
    pins = {str(path): sha(path) for path in (Path(__file__), args.module, args.full_model)}
    peripheral_names = ('test_v2_rtc.py', 'test_v2_i2c.py', 'test_v2_journal.py', 'test_v2_spi_prototype.py')
    pins.update({str(ROOT/'tools'/name): sha(ROOT/'tools'/name) for name in peripheral_names})
    sys.path[:0] = [str(ROOT/'BUILD/v1.30/local/test-deps'), str(ROOT/'BUILD/test-deps-816'), str(ROOT/'tools')]
    import serial
    import socket
    def forbidden(*unused, **kwargs):
        raise AssertionError('No hardware or network in offline LED qualification')
    serial.Serial = socket.create_connection = socket.socket = forbidden
    if is816:
        from py65816.devices.mpu65c816 import MPU as BaseMPU
        model_sha = sha(sys.modules[BaseMPU.__module__].__file__)
        assert model_sha == MODEL_816_SHA256
    else:
        from py65.devices.mpu65c02 import MPU as BaseMPU
        model_sha = sha(sys.modules[BaseMPU.__module__].__file__)
    helper = load_source(args.full_model, 'frozen_full_model_for_LED')
    led = module
    progress_frames = {1, led.FRAME_COUNT+1}
    for pattern in led.PATTERNS:
        progress_frames.update((pattern['offset']+1, pattern['offset']+pattern['frames']))
        if pattern['frames'] >= 128:
            progress_frames.update(pattern['offset']+part for part in (64, 128, 192))
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    canonical = led.cases()
    assert len(canonical) == 4
    image = (args.build/'firmware.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == EXPECTED_FIRMWARE
    symbols = json.loads((args.build/'symbols.json').read_text())
    boot = symbols['core/str8n-v2-boot']
    xce, restore = boot['BOOT_XCE'], boot['BOOT_XCE_RESTORE']
    detector = (xce+1, xce+2, xce+4, restore-1, restore)
    EEPROM, SPI = helper.peripheral_classes()
    namespace = frozen_model_definitions(args.full_model, dict(
        image=image, metadata=helper.metadata, deque=deque, EEPROM=EEPROM, SPI=SPI,
        BaseMPU=BaseMPU, is816=is816, detector=detector, hashlib=hashlib,
        binascii=binascii))
    OldMemory, OldMPU = namespace['Memory'], namespace['MPU']
    run, persistent_snapshot = namespace['run'], namespace['snapshot']

    class Memory(OldMemory):
        def __init__(self, slot):
            super().__init__(slot)
            self.model_slot = slot
            self.pia_cra, self.pia_ddra, self.pia_latch = 0, 0, 0
            self.pia_writes, self.app_events, self.app_ram_writes = [], [], set()
            self.led_armed = self.led_active = False
            self.led_case = self.led_expected = None
            self.app_start_cycles = self.app_start_steps = None
            self.app_wall_started = None
            self.app_entry_latch = self.app_entry_cra = self.app_entry_ddra = None
            self.app_stop = None

        def __getitem__(self, address):
            if address == LED_CRA:
                return self.pia_cra
            if address == LED_PORT:
                return self.pia_latch if self.pia_cra & 4 else self.pia_ddra
            return super().__getitem__(address)

        def __setitem__(self, address, value):
            if self.led_active:
                check_application_write(address, led)
                if address != LED_PORT:
                    self.app_ram_writes.add(address)
            if address == LED_CRA:
                assert not self.led_active, 'LED application changed CRA'
                self.pia_cra = value & 255
                self.pia_writes.append((address, value & 255))
                return
            if address == LED_PORT:
                value &= 255
                if self.pia_cra & 4:
                    if self.led_active:
                        assert self.pia_ddra == 255 and self.pia_cra & 0x3f == 0x34
                        self.app_events.append(dict(address=address, value=value,
                                                    cycles=self.cpu.processorCycles))
                        count = len(self.app_events)
                        if count in progress_frames:
                            cycles = self.cpu.processorCycles - self.app_start_cycles
                            elapsed = time.monotonic() - self.app_wall_started
                            expected_cycles = led.NOMINAL_SECONDS * led.NOMINAL_HZ
                            eta = max(0, expected_cycles - cycles) * elapsed / cycles if cycles else 0
                            phase = next((pattern['name'] for pattern in led.PATTERNS
                                          if pattern['offset'] < count <= pattern['offset']+pattern['frames']), 'restore')
                            print('LED frame', args.cpu, self.model_slot, phase,
                                  min(count, led.FRAME_COUNT), '/'+str(led.FRAME_COUNT), 'cycles', cycles,
                                  'model_seconds', round(elapsed, 1), 'ETA_seconds', round(eta, 1), flush=True)
                    self.pia_latch = value
                else:
                    assert not self.led_active, 'LED application selected DDRA'
                    self.pia_ddra = value
                self.pia_writes.append((address, value))
                return
            return super().__setitem__(address, value)

    class MPU(OldMPU):
        def step(self):
            m = self.memory
            if m.led_armed and self.pc == 0x200:
                m.led_armed, m.led_active = False, True
                assert m.bank == 3 and m.pia_ddra == 255 and m.pia_cra & 0x3f == 0x34
                assert m.pia_latch == 0, 'G did not release resident LED display'
                m.app_entry_latch, m.app_entry_cra, m.app_entry_ddra = m.pia_latch, m.pia_cra, m.pia_ddra
                m.app_start_cycles, m.app_start_steps = self.processorCycles, m.steps
                m.app_wall_started = time.monotonic()
            if m.led_active:
                assert 0x200 <= self.pc < 0x200 + len(m.led_expected), ('LED escaped qualified application', hex(self.pc))
                assert m.steps - m.app_start_steps <= contract['instruction_bound'], 'LED instruction bound exceeded'
                assert self.processorCycles - m.app_start_cycles <= led.CPU_TOTAL_CYCLE_BOUNDS[1], 'LED CPU cycle bound exceeded'
                if m[self.pc] == 0:
                    assert m[(self.pc+1)&65535] == 1
                    assert m.pia_latch == m.app_entry_latch and m.pia_cra == m.app_entry_cra and m.pia_ddra == m.app_entry_ddra
                    cycles = self.processorCycles - m.app_start_cycles
                    physical = check_led_events(m.app_events, bytes.fromhex(m.led_case['expected_frame_hex']), m.app_entry_latch, cycles, led)
                    m.app_stop = dict(passed=True, PC=self.pc, cycles=cycles, instructions=m.steps-m.app_start_steps,
                                      entry_latch=m.app_entry_latch, restored_latch=m.pia_latch,
                                      CRA_before=m.app_entry_cra, CRA_after=m.pia_cra,
                                      DDRA_before=m.app_entry_ddra, DDRA_after=m.pia_ddra,
                                      physical_frames=physical)
                    m.led_active = False
            return super().step()

    all_images, results, transcripts = {}, [], []
    started = time.monotonic()
    for slot in ('A', 'B'):
        m, cpu = Memory(slot), None
        cpu = MPU(m)
        m.cpu = m.spi.cpu = cpu
        cpu.p = 0x24
        mon = symbols['core/monitor-'+slot.lower()+'0']
        print('LED CPU boot', args.cpu, slot, flush=True)
        run(cpu, lambda: cpu.pc == mon['V2_LINE_BYTE'] and m.tx.endswith(b'B3> '))
        assert m.ram[0x7d30] == (0xa0 if slot == 'A' else 0xb0)
        assert m.pia_cra & 0x3f == 0x34 and m.pia_ddra == 255
        if is816:
            assert cpu.mode == 1 and cpu.native_steps == len(detector)
            cpu.allow_reset, cpu.b = False, 0xa5
        before = persistent_snapshot(m)
        counts = (len(m.bus.writes), len(m.spi.devices[0].writes), len(m.spi.devices[0].mode_writes), len(m.flash_writes))

        class Link:
            def __init__(self):
                self.cursor = len(m.tx)

            def send(self, value):
                m.rx.extend(value)

            def until(self, token, timeout=30):
                run(cpu, lambda: token in m.tx[self.cursor:], limit=contract['instruction_bound']+5_000_000)
                end = m.tx.index(token, self.cursor) + len(token)
                answer = bytes(m.tx[self.cursor:end])
                self.cursor = end
                return answer

            def command(self, text, prompt=B3):
                self.cursor = len(m.tx)
                if text == 'G 0200':
                    m.led_armed = True
                self.send(text.encode()+b'\r')
                answer = self.until(prompt)
                assert answer.endswith(prompt)
                if is816:
                    assert cpu.mode == 1 and cpu.b == 0xa5
                transcripts.append(dict(slot=slot, command=text, prompt=prompt.decode(),
                                        output=answer.decode('ascii', 'replace')))
                return answer

            def dump(self, first, last, prompt=B3):
                answer = self.command(f'D {first:04X} {last:04X}', prompt)
                cells = {}
                for address, body in re.findall(rb'(?m)^([0-9A-F]{4}): ((?:[0-9A-F]{2}(?: |\r?$))+)', answer):
                    cells.update(enumerate(bytes.fromhex(body.decode()), int(address, 16)))
                return bytes(cells[address] for address in range(first, last+1))

        link = Link()
        execute_seed = EXECUTION_SEEDS[args.cpu][slot]
        order = sorted(canonical, key=lambda case: case['seed'] == execute_seed)
        assembled = []
        selected = None
        for assembly_index, case in enumerate(order, 1):
            print('LED10 onboard assembly', args.cpu, slot, str(assembly_index)+'/4', case['name'], 'begin', flush=True)
            assert b'ASM 0.5' in link.command('ASM', ASM)
            link.command('NEW', ASM)
            for line in case['lines']:
                link.command(line, ASM)
            answer = link.command('ASM', ASM)
            match = re.search(rb'OK (\d+) bytes\b', answer)
            assert match, ('LED source failed onboard assembly', case['name'], answer)
            length = int(match[1])
            assert 0 < length <= 0x400
            link.command('DUMP', ASM)
            exported = decode_export(link.command('S19', ASM))
            link.command('QUIT')
            body = link.dump(0x200, 0x200+length-1)
            assert len(exported) == length and body == exported, 'ASM RAM/export image mismatch'
            qualified = dict(case, assembled_hex=body.hex())
            assert led.validate_case(qualified) == body
            if case['name'] in all_images:
                assert all_images[case['name']] == qualified, 'Different image between monitor slots'
            else:
                all_images[case['name']] = qualified
            assembled.append(dict(name=case['name'], seed=case['seed'], bytes=length,
                                  source_sha256=hashlib.sha256(('\n'.join(case['lines'])+'\n').encode()).hexdigest(),
                                  image_sha256=hashlib.sha256(body).hexdigest(), assembled_hex=body.hex(),
                                  exact_RAM_and_S19_export=True))
            assert persistent_snapshot(m) == before
            print('PASS LED10 onboard assembly', args.cpu, slot, str(assembly_index)+'/4', case['name'], 'bytes', length, 'SHA256', hashlib.sha256(body).hexdigest(), flush=True)
            if case['seed'] == execute_seed:
                selected = qualified
        assert selected is not None
        m.led_case, m.led_expected = selected, bytes.fromhex(selected['assembled_hex'])
        print('LED CPU execute', args.cpu, slot, selected['name'], str(led.FRAME_COUNT)+' frames', flush=True)
        console = link.command('G 0200', DBG)
        try:
            assert m.app_stop and m.app_stop['passed']
            context = link.dump(0x7000, 0x7006, DBG)
            pc = int.from_bytes(context[:2], 'little')
            assert m.led_expected[pc-0x200-2:pc-0x200] == b'\x00\x01'
            assert context[2:5] == bytes(3) and not context[5]&1 and context[6] == 255
            metadata_bytes = link.dump(led.META, led.META+led.META_BYTES-1, DBG)
            writes = link.dump(led.WRITE_TRACE, led.WRITE_TRACE+led.FRAME_COUNT-1, DBG)
            readbacks = link.dump(led.READ_TRACE, led.READ_TRACE+led.FRAME_COUNT-1, DBG)
            application = led.check_result(selected, metadata_bytes, writes, readbacks,
                                           expected_entry_led=m.app_entry_latch)
            assert [event['value'] for event in m.app_events[:-1]] == list(writes) == list(readbacks)
        finally:
            link.command('C')
        assert link.dump(0x7bfc, 0x7bff) == bytes(4)
        assert link.dump(0x200, 0x200+len(m.led_expected)-1) == m.led_expected
        assert persistent_snapshot(m) == before, 'LED qualification changed peripheral contents/mode'
        assert counts == (len(m.bus.writes), len(m.spi.devices[0].writes), len(m.spi.devices[0].mode_writes), len(m.flash_writes)), 'Peripheral write transaction during LED workload'
        assert m.pia_cra & 0x3f == 0x34 and m.pia_ddra == 255
        row = dict(passed=True, CPU=args.cpu, slot=slot, assembled_cases=assembled,
                   executed_case=selected['name'], executed_seed=execute_seed,
                   application=application, physical_state=m.app_stop,
                   physical_LED_write_events=m.app_events,
                   application_RAM_write_addresses=sorted(m.app_ram_writes),
                   application_hardware_write_addresses=[LED_PORT], application_CRA_writes=0,
                   persistent_snapshot_before=before, persistent_snapshot_after=persistent_snapshot(m),
                   peripheral_data_or_mode_write_transactions=0, context_hex=context.hex(),
                   HOLD_cleanup=dict(lifecycle_hex='00000000', registry_valid=False),
                   program_bytes_unchanged=True,
                   E=1 if is816 else None, native_applications=False, native_debugging=False,
                   reset_detector_native_steps=cpu.native_steps if is816 else 0)
        results.append(row)
        print('PASS LED', args.cpu, 'MON', slot, 'four assemblies, full 630-frame physical execution', flush=True)
    assert all(sha(Path(path)) == digest for path, digest in pins.items()), 'Qualification sources changed during execution'
    qualified_cases = [all_images[case['name']] for case in canonical]
    proof = dict(passed=True, CPU=args.cpu, results=results,
                 source_pins=pins, firmware_sha256=EXPECTED_FIRMWARE, model_sha256=model_sha,
                 distinct_sources=4, onboard_assemblies=8, full_LED_executions=2,
                 frames_per_execution=led.FRAME_COUNT, cross_monitor_image_equality=True,
                 cross_CPU_image_equality='Requires exact join with the other CPU receipt; not claimed here.',
                 approved_execution_matrix=EXECUTION_SEEDS,
                 timing_instructions_accelerated=False, pure_guard_checks=guard_checks,
                 pattern_names=list(led.PATTERN_NAMES), patterns_per_execution=led.PATTERN_COUNT,
                 source_contract=contract,
                 qualification_seconds=time.monotonic()-started,
                 board_access=False, network_access=False,
                 electrical_timing_qualified=False, native_applications=False, native_debugging=False)
    cases_output.write_text(json.dumps(qualified_cases, indent=2)+'\n')
    output.write_text(json.dumps(proof, indent=2)+'\n')
    output.with_name(output.stem+'-transcripts.json').write_text(json.dumps(transcripts, indent=2)+'\n')
    print('PASS LED CPU proof', output, flush=True)


if __name__ == '__main__':
    main()
