"""Pure cases/oracles for documented DBG1 R register edits; no board access.

Saved P is an unmasked byte. RTI forces bits 4/5 on in emulation, and real
hardware resumes only the IRQ-masked P subset. PC range checks occur on C/S/N,
not while editing the saved word. SP has no parser-level lower-bound guard.
"""
import re

FIELDS = ('PC', 'A', 'X', 'Y', 'P', 'SP')
OFFSETS = dict(PC=(0, 1), A=(2,), X=(3,), Y=(4,), P=(5,), SP=(6,))
BYTE_FIELDS = ('A', 'X', 'Y', 'P', 'SP')
ENTRY, RESUME_PC, CAPTURE, TRACE = 0x0400, 0x0413, 0x0500, 0x0600
BASELINE = dict(PC=RESUME_PC, A=0x11, X=0x22, Y=0x33, P=0x34, SP=0xfd)
SAFE_PC_TARGETS = (0x0200, 0x0201, 0x0202, 0x04ff, RESUME_PC, CAPTURE, 0x64fd, 0x64fe, 0x64ff)
UNSAFE_PC_TARGETS = (0, 1, 0x01ff, 0x6500, 0x66ff, 0x6700, 0x7eff, 0x7f00, 0x7fff, 0x8000, 0xffff)
DISPLAY = re.compile(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})')


def context_bytes(value):
    return value['PC'].to_bytes(2, 'little') + bytes(value[key] for key in BYTE_FIELDS)


def context_dict(raw):
    assert len(raw) == 7
    return dict(PC=int.from_bytes(raw[:2], 'little'), **dict(zip(BYTE_FIELDS, raw[2:])))


def parse_display(output):
    if isinstance(output, str):
        output = output.encode('ascii')
    rows = DISPLAY.findall(output)
    assert rows, 'Missing complete saved-register display'
    return dict(zip(FIELDS, (int(value, 16) for value in rows[-1])))


def expected_after(before, case):
    value = dict(before)
    if case['accepted'] and case.get('field'):
        if case['field'] == 'PC_HI':
            value['PC'] = (before['PC'] & 255) | (case['value'] << 8)
        else:
            value[case['field']] = case['value']
    return value


def error_response(output):
    return bool(re.search(rb'(?:^|\r\n)\?\r\n', output))


def case(name, command, field=None, value=None, accepted=True, category='lexical'):
    return dict(name=name, command=command, field=field, value=value, accepted=accepted, category=category)


def parser_cases(exhaustive=True):
    rows = [case('display', 'R', category='display'), case('display-spaces', '  r   ', category='display')]
    values = range(256) if exhaustive else (0, 1, 8, 9, 0x7f, 0x80, 0xfe, 0xff)
    for field in BYTE_FIELDS:
        rows += [case(f'{field}-{value:02X}', f'R {field}={value:02X}', field, value, category='byte-values') for value in values]
    for value in sorted(set((*SAFE_PC_TARGETS, *UNSAFE_PC_TARGETS))):
        rows.append(case(f'PC-{value:04X}', f'R PC={value:04X}', 'PC', value, category='PC-word-boundary'))
    for field in FIELDS:
        value = CAPTURE if field == 'PC' else 0xab
        token = f'{value:04X}' if field == 'PC' else 'AB'
        forms = (f'r {field.lower()}={token.lower()}', f'R{field}={token}', f'R {field} {token}',
                 f' R  {field} = {token} ', f'R {field}{token}', f'R {field}=00AB' if field != 'PC' else 'R PC=0500')
        rows += [case(f'{field}-form-{n}', text, field, value) for n, text in enumerate(forms)]
        for text in ('', '=', 'G0', '$12', '0X12', '+1', '-1', '00000', '12G', '12 34', '=12'):
            rows.append(case(f'{field}-refuse-{text or "missing"}', f'R {field}={text}', accepted=False, category='atomic-refusal'))
    for field in BYTE_FIELDS:
        for text in ('100', '0100', 'FFFF'):
            rows.append(case(f'{field}-wide-{text}', f'R {field}={text}', accepted=False, category='byte-overflow'))
    rows += [case('unknown-register', 'R Q=12', accepted=False, category='atomic-refusal'),
             case('multiple-edits', 'R A=12 X=34', accepted=False, category='atomic-refusal'),
             case('reader-40-printables', 'R A=12' + ' ' * 34, 'A', 0x12, category='reader-boundary'),
             case('reader-41-printables', 'R A=12' + ' ' * 35, accepted=False, category='reader-boundary'),
             case('reader-backspace', 'R A=1G\b2', 'A', 0x12, category='reader-normalization'),
             case('reader-tab-ignored', 'R A=1\t2', 'A', 0x12, category='reader-normalization'),
             case('reader-LF-ignored', 'R A=1\n2', 'A', 0x12, category='reader-normalization'),
             case('reader-cancel', 'R A=12\x03', category='reader-cancel')]
    # Implemented REG_NAMES aliases are characterized, not advertised as ABI.
    rows += [case(f'quirk-C-{v:04X}', f'R C={v:04X}', 'PC', v, category='undocumented-alias') for v in (0, CAPTURE, 0xffff)]
    rows += [case(f'quirk-S-{v:02X}', f'R S={v:02X}', 'SP', v, category='undocumented-alias') for v in (0, 255)]
    rows += [case(f'quirk-question-{v:02X}', f'R ?={v:02X}', 'PC_HI', v, category='undocumented-alias') for v in (0, 255)]
    rows += [case('quirk-question-byte-overflow', 'R ?=100', accepted=False, category='atomic-refusal'),
             case('quirk-S-byte-overflow', 'R S=100', accepted=False, category='atomic-refusal'),
             case('hidden-B-refused', 'R B=12', accepted=False, category='atomic-refusal'),
             case('hidden-BH-refused', 'R BH=12', accepted=False, category='atomic-refusal')]
    assert len({r['name'] for r in rows}) == len(rows)
    return rows


def resume_cases(exhaustive=True, hardware=False):
    values = range(256) if exhaustive else (0, 1, 8, 9, 0x7f, 0x80, 0xfe, 0xff)
    rows = []
    for field in BYTE_FIELDS:
        selected = values
        if hardware and field == 'P':
            selected = (0x24, 0x25, 0x34, 0xa5, 0xff)  # IRQ remains masked.
        if hardware and field == 'SP':
            selected = (9, 0x7f, 0x80, 0xfe, 0xff)  # reserve the documented entry scratch.
        rows += [case(f'resume-{field}-{value:02X}', f'R {field}={value:02X}', field, value, category='actual-resume') for value in selected]
    rows += [case(f'resume-PC-{value:04X}', f'R PC={value:04X}', 'PC', value, category='actual-resume') for value in SAFE_PC_TARGETS]
    return rows


def step_resume_cases():
    rows = []
    for operation in ('S', 'N'):
        for field in FIELDS:
            value = 0x0200 if field == 'PC' else 0x25 if field == 'P' else 0x80
            token = f'{value:04X}' if field == 'PC' else f'{value:02X}'
            row = case(f'step-{operation}-{field}', f'R {field}={token}', field, value, category='step-then-resume')
            row['operation'] = operation
            rows.append(row)
    return rows


def resume_expected(before, row):
    result = expected_after(before, row)
    # RTI restores a page-one emulation frame and canonicalizes the B/constant bits.
    result['P'] |= 0x30
    if result['PC'] not in (RESUME_PC, CAPTURE):
        assert result['PC'] in SAFE_PC_TARGETS
        result['SP'] = (result['SP'] + 2) & 255  # the boundary target is one-byte RTS.
    return bytes((result['A'], result['X'], result['Y'], result['P'], result['SP'], 0xa5))


def fixture_cells():
    # The two allocated bytes above SP hold $04FF for safe one-byte RTS targets,
    # including the final permitted application byte $64FF. No instruction
    # fetch crosses the application boundary during a valid PC-resume test.
    initial = bytes.fromhex('78 D8 A2 FF 9A A9 04 48 A9 FF 48 A9 11 A2 22 A0 33 00 01 4C 00 05')
    capture = bytes.fromhex('8D 00 06 8E 01 06 8C 02 06 08 68 8D 03 06 BA 8E 04 06 A9 A5 8D 05 06 00 02 4C 67 7E')
    cells = {ENTRY + i: value for i, value in enumerate(initial)}
    cells.update({CAPTURE + i: value for i, value in enumerate(capture)})
    cells.update({TRACE + i: 0 for i in range(6)})
    cells.update({pc: 0x60 for pc in SAFE_PC_TARGETS if pc not in (RESUME_PC, CAPTURE)})
    return cells


def fixture_s19():
    def record(kind, address, data):
        raw = bytes((len(data) + 3, address >> 8, address & 255)) + data
        return 'S' + kind + (raw + bytes((~sum(raw) & 255,))).hex().upper()
    cells = fixture_cells()
    lines, pending, start, last = [], bytearray(), None, None
    for address, value in sorted(cells.items()):
        if pending and (address != last + 1 or len(pending) == 24):
            lines.append(record('1', start, bytes(pending)));pending.clear()
        if not pending:
            start = address
        pending.append(value);last = address
    if pending:
        lines.append(record('1', start, bytes(pending)))
    return '\n'.join([*lines, record('9', ENTRY, b'')]) + '\n'
