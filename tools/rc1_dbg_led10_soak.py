"""Ten bounded onboard-ASM LED patterns; no port, build or firmware access on import.

The exact rc1 boot establishes PIA DDRA=$FF and CRA=$34. This application
requires CRA's low six bits to remain $34, never selects or changes DDRA/CRA,
and writes only the active-high LED data register ($7FA0) and borrowed RAM.
G releases the resident LED display before entry. Restore is proved inside the
application before BRK $01; the monitor owns its display again after HOLD.

Golden assembled_hex must come from qualification of these exact source lines.
The helper assembles on board and refuses G unless every image byte matches.
Protocol tests are separate from CPU, electrical and visible-observation proof.
"""
import hashlib
import re
import time


ENTRY = 0x0200
META = 0x0600
META_BYTES = 14
WRITE_TRACE = 0x0800
READ_TRACE = 0x0B00
FRAME_COUNT = 630
LED_PORT = 0x7FA0
LED_CRA = 0x7FA1
CRA_SETTING = 0x34
CRA_MASK = 0x3F
NOMINAL_HZ = 8_000_000
NOMINAL_SECONDS = 12.5
HARDWARE_SECONDS_BOUNDS = (10.0, 25.0)
SEEDS = (0x12, 0x25, 0x38, 0x4B)
B3 = b'\r\nB3> '
ASM = b'ASM> '
DBG = b'DBG> '

# Bounds include loop/control overhead and possible branch page-cross penalties.
_PATTERN_DEFINITIONS = (
    ('wigwag', 8, 'slow'), ('gray-code', 256, 'fast'),
    ('binary-counter', 256, 'fast'), ('walking-one', 16, 'medium'),
    ('walking-zero', 16, 'medium'), ('bouncing-dot', 14, 'medium'),
    ('checkerboard', 8, 'medium'), ('fill-drain', 16, 'medium'),
    ('expanding-contracting-pairs', 8, 'medium'), ('lfsr-sparkle', 32, 'medium'),
)
DWELL_CYCLE_BOUNDS = {'slow': (1_300_000, 1_800_000),
                      'fast': (100_000, 150_000), 'medium': (320_000, 450_000)}
PATTERN_NAMES = tuple(name for name, _, _ in _PATTERN_DEFINITIONS)
PATTERN_COUNT = len(PATTERN_NAMES)
PATTERNS = tuple(dict(name=name, frames=frames, dwell_class=dwell,
                     offset=sum(item[1] for item in _PATTERN_DEFINITIONS[:i]),
                     frame_cycle_bounds=list(DWELL_CYCLE_BOUNDS[dwell]))
                 for i, (name, frames, dwell) in enumerate(_PATTERN_DEFINITIONS))
CPU_TOTAL_CYCLE_BOUNDS = tuple(sum(p['frames'] * p['frame_cycle_bounds'][i]
                                 for p in PATTERNS) for i in (0, 1))
CPU_CYCLE_BOUNDS = CPU_TOTAL_CYCLE_BOUNDS
assert PATTERN_COUNT == 10 and sum(p['frames'] for p in PATTERNS) == FRAME_COUNT


def pattern_frames(seed):
    """Exact independently checkable frames for each of ten bounded patterns."""
    assert type(seed) is int and 0 < seed <= 255
    counter = [(seed + i) & 255 for i in range(256)]
    ones = [1 << i for i in range(8)] * 2
    sparkle, state = [], seed
    for _ in range(32):
        sparkle.append(state)
        state = (state >> 1) ^ (0xB8 if state & 1 else 0)
    return [[0xF0, 0x0F] * 4, [n ^ (n >> 1) for n in counter], counter,
            ones, [value ^ 255 for value in ones],
            [1 << i for i in range(8)] + [1 << i for i in range(6, 0, -1)],
            [0xAA, 0x55] * 4,
            [(1 << i) - 1 for i in range(1, 9)] + [(1 << i) - 1 for i in range(7, -1, -1)],
            [0x18, 0x3C, 0x7E, 0xFF, 0x7E, 0x3C, 0x18, 0], sparkle]


def frame_values(seed):
    return [value for pattern in pattern_frames(seed) for value in pattern]


def _emit(write_address, read_address, counted_label, delay):
    # X is a bounded frame index; only Y and application scratch are delayed.
    result = ['STA $7FA0', f'STA ${write_address:04X},X', 'LDA $7FA0',
              f'STA ${read_address:04X},X', f'EOR ${write_address:04X},X',
              'ORA $0605', 'STA $0605', 'INC $0606',
              f'BNE {counted_label}', 'INC $0607', counted_label + ':']
    if delay == 'slow':
        result += ['JSR slow']
    elif delay == 'medium':
        result += ['LDA #$00', 'JSR delay']
    else:
        result += ['LDA #$50', 'JSR delay']
    return result


def source_lines(seed):
    """Canonical numbered source accepted by the installed ASM 0.5."""
    assert type(seed) is int and 0 < seed <= 255
    body = ['ORG $0200', 'SEI', 'CLD', 'LDX #$FF', 'TXS',
            'LDX #$0D', 'clear: STZ $0600,X', 'DEX', 'BPL clear',
            f'LDA #${seed:02X}', 'STA $0608',
            'LDA $7FA1', 'STA $060B', 'AND #$3F', 'STA $0602',
            'CMP #$34', 'BEQ ready', 'LDA #$E1', 'STA $0600', 'JMP done',
            'ready: LDA $7FA0', 'STA $0601', 'LDX #$00',
            'wig: TXA', 'AND #$01', 'BEQ red', 'LDA #$0F', 'BRA light',
            'red: LDA #$F0', 'light:']
    body += _emit(WRITE_TRACE, READ_TRACE, 'wc', 'slow')
    body += ['INX', 'CPX #$08', 'BNE wig', 'LDA #$01', 'STA $060A',
             'LDX #$00', 'gray: TXA', 'CLC', f'ADC #${seed:02X}',
             'STA $6042', 'LSR A', 'EOR $6042']
    body += _emit(WRITE_TRACE + 8, READ_TRACE + 8, 'gc', 'fast')
    body += ['INX', 'BNE gray', 'LDA #$02', 'STA $060A', 'LDX #$00',
             'count: TXA', 'CLC', f'ADC #${seed:02X}']
    body += _emit(WRITE_TRACE + 264, READ_TRACE + 264, 'cc', 'fast')
    body += ['INX', 'BNE count', 'LDA #$03', 'STA $060A',
             'LDX #$00', 'extra: LDA extras,X']
    body += _emit(WRITE_TRACE + 520, READ_TRACE + 520, 'ec', 'medium')
    body += ['INX', 'LDY $060A', 'TXA', 'CMP ends,Y', 'BNE enext',
             'INC $060A', 'enext: CPX #$6E', 'BNE extra',
             'LDA $0601', 'STA $7FA0', 'LDA $7FA0', 'STA $0603',
             'EOR $0601', 'STA $0609', 'LDA $7FA1', 'STA $060C',
             'AND #$3F', 'STA $0604', 'EOR $0602', 'BNE crabad',
             'LDA $0609', 'BNE restorebad', 'LDA $0605', 'BNE framebad',
             'LDA $0606', 'CMP #$76', 'BNE framebad',
             'LDA $0607', 'CMP #$02', 'BNE framebad',
             'LDA #$A5', 'STA $0600', 'JMP done',
             'crabad: LDA #$E3', 'BRA failed',
             'restorebad: LDA #$E4', 'BRA failed',
             'framebad: LDA #$E2', 'failed: STA $0600',
             'done: LDA #$00', 'LDX #$00', 'LDY #$00', 'CLC',
             'BRK $01', 'JMP $7E67',
             # Four 256x256 loops give about 165 ms at nominal 8 MHz.
             'slow: LDA #$04', 'STA $6041', 'sl: LDA #$00', 'JSR delay',
             'DEC $6041', 'BNE sl', 'RTS',
             # A=$50: 80x256 gives about 12.9 ms; A=0 wraps to 256.
             'delay: STA $6040', 'outer: LDY #$00',
             'inner: DEY', 'BNE inner', 'DEC $6040', 'BNE outer', 'RTS',
             'ends: BYTE $00,$00,$00,$10,$20,$2E,$36,$46,$4E,$6E']
    extra_frames = frame_values(seed)[520:]
    assert len(extra_frames) == 110
    for index in range(0, len(extra_frames), 16):
        label = 'extras: ' if index == 0 else ''
        body.append(label + 'BYTE ' + ','.join(f'${value:02X}' for value in extra_frames[index:index+16]))
    body.append('END')
    return [f'{10 * (i + 1)} {line}' for i, line in enumerate(body)]


def cases():
    return [dict(name=f'led-ten-patterns-{seed:02X}',
                 family='led-ten-patterns', seed=seed,
                 lines=source_lines(seed), expected_frame_hex=bytes(frame_values(seed)).hex(),
                 frame_count=FRAME_COUNT, pattern_count=PATTERN_COUNT,
                 pattern_names=list(PATTERN_NAMES),
                 patterns=[dict(p, frame_cycle_bounds=list(p['frame_cycle_bounds'])) for p in PATTERNS],
                 cpu_total_cycle_bounds=list(CPU_TOTAL_CYCLE_BOUNDS), nominal_hz=NOMINAL_HZ,
                 nominal_seconds=NOMINAL_SECONDS,
                 hardware_seconds_bounds=list(HARDWARE_SECONDS_BOUNDS),
                 native_applications=False, native_debugging=False)
            for seed in SEEDS]


def validate_case(case):
    assert case['seed'] in SEEDS and type(case['seed']) is int
    wanted = next(c for c in cases() if c['seed'] == case['seed'])
    for key, value in wanted.items():
        assert case[key] == value, ('Noncanonical LED case', key)
    expected = bytes.fromhex(case['assembled_hex'])
    assert expected and ENTRY + len(expected) <= META, 'LED code overlaps result RAM'
    assert b'\x00\x01\x4c\x67\x7e' in expected, 'Missing debug/HOLD exit'
    return expected


def check_result(case, metadata, writes, readbacks, *, expected_entry_led=None):
    """Check application-exported values; monitor D intentionally excludes I/O."""
    assert len(metadata) == META_BYTES
    assert metadata[0] == 0xA5, ('LED application refused/failed', metadata.hex())
    assert metadata[1] == metadata[3], ('LED restore differs', metadata.hex())
    if expected_entry_led is not None:
        assert metadata[1] == expected_entry_led, ('Unexpected G-entry display', metadata.hex())
    assert metadata[2] == metadata[4] == CRA_SETTING, 'PIA CRA setting changed'
    assert metadata[11] & CRA_MASK == metadata[12] & CRA_MASK == CRA_SETTING
    assert metadata[5] == metadata[9] == metadata[13] == 0, ('LED mismatch', metadata.hex())
    assert int.from_bytes(metadata[6:8], 'little') == FRAME_COUNT
    assert metadata[8] == case['seed'] and metadata[10] == PATTERN_COUNT
    expected = bytes(frame_values(case['seed']))
    assert writes == expected, 'LED write trace differs from full pattern oracle'
    assert readbacks == expected, 'LED pin readback differs from pattern oracle'
    return dict(passed=True, frames=FRAME_COUNT,
                pattern_count=PATTERN_COUNT, pattern_names=list(PATTERN_NAMES),
                patterns=[dict(name=p['name'], frames=p['frames']) for p in PATTERNS],
                entry_led=metadata[1], restored_led_before_BRK=metadata[3],
                CRA_before=metadata[2], CRA_after=metadata[4],
                CRA_mask=CRA_MASK, CRA_irq_flags_ignored=True,
                boot_established_DDRA_FF_assumption=True,
                original_led_restored_before_BRK=True,
                actual_pin_readback_matches_every_frame=True,
                frame_trace_sha256=hashlib.sha256(expected).hexdigest(),
                metadata_hex=metadata.hex())


def led_unit(link, transport, case, *, check_timing=True):
    """Onboard ASM and exact image gate, bounded application, BRK then HOLD.

    The surrounding owner holds the serial lease, validates exact firmware and
    CPU-mode admission, and restores full original application RAM at closure.
    Model callers disable wall timing and independently verify CPU cycle bounds.
    """
    expected = validate_case(case)
    transcript = bytearray()
    def command(text, prompt=B3):
        answer = link.command(text, prompt)
        assert answer.endswith(prompt), ('Unexpected LED unit prompt', text, answer[-120:])
        transcript.extend(answer)
        return answer
    assert b'ASM 0.5' in command('ASM', ASM)
    command('NEW', ASM)
    for line in case['lines']:
        command(line, ASM)
    answer = command('ASM', ASM)
    assert re.search(rb'OK ' + str(len(expected)).encode() + rb' bytes\b', answer)
    command('DUMP', ASM)
    command('S19', ASM)
    command('QUIT')
    before = transport.read_range(link, ENTRY, ENTRY + len(expected) - 1, B3)
    assert before == expected, 'LED ASM differs from CPU-qualified bytes; G refused'
    started = time.monotonic()
    console = command('G 0200', DBG)
    elapsed = time.monotonic() - started
    try:
        context = link.dump(0x7000, 0x7006, DBG)
        assert len(context) == 7
        pc = int.from_bytes(context[:2], 'little')
        assert ENTRY + 2 <= pc <= ENTRY + len(expected)
        assert expected[pc - ENTRY - 2:pc - ENTRY] == b'\x00\x01', 'Unexpected LED debug stop'
        assert context[2:5] == bytes(3) and not context[5] & 1 and context[6] == 255
        metadata = transport.read_range(link, META, META + META_BYTES - 1, DBG)
        writes = transport.read_range(link, WRITE_TRACE, WRITE_TRACE + FRAME_COUNT - 1, DBG)
        readbacks = transport.read_range(link, READ_TRACE, READ_TRACE + FRAME_COUNT - 1, DBG)
        proof = check_result(case, metadata, writes, readbacks, expected_entry_led=0)
        if check_timing:
            assert HARDWARE_SECONDS_BOUNDS[0] <= elapsed <= HARDWARE_SECONDS_BOUNDS[1], (
                'LED elapsed time outside admitted bounds', elapsed)
    finally:
        # Only issue C after the known DBG prompt. Never guess another context.
        command('C')
    lifecycle = link.dump(0x7BFC, 0x7BFF)
    assert lifecycle == bytes(4), 'HOLD lifecycle/registry invalidation failed'
    assert transport.read_range(link, ENTRY, ENTRY + len(expected) - 1, B3) == expected
    proof.update(name=case['name'], family=case['family'], seed=case['seed'],
                 source_sha256=hashlib.sha256(('\n'.join(case['lines']) + '\n').encode()).hexdigest(),
                 image_sha256=hashlib.sha256(expected).hexdigest(), bytes=len(expected),
                 exact_model_image_verified_before_execution=True,
                 context_hex=context.hex(), elapsed_seconds=elapsed,
                 wall_timing_checked=check_timing,
                 nominal_hz=NOMINAL_HZ, nominal_seconds=NOMINAL_SECONDS,
                 hardware_seconds_bounds=list(HARDWARE_SECONDS_BOUNDS),
                 HOLD_cleanup=dict(lifecycle_hex=lifecycle.hex(), registry_valid=False),
                 program_bytes_unchanged=True, final_context='B3',
                 native_applications=False, native_debugging=False)
    return proof, bytes(transcript)
