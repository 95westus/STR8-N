"""v1.30 binary regressions: message pages, delay contract, actual range parser.

The deliberately limited CPU harness rejects unsupported instructions; it runs
the linked range parser, stubbing only console printing and line acquisition.
It is not a general CPU emulator or a substitute for board timing evidence.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'BUILD/v1.30'


def symbols(path):
    return {n: int(a, 16) for a, n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$', path.read_text(), re.M)}


def main():
    sym = symbols(REL / 'map/str8n-v1.30-f000.map')
    image = (REL / 'bin/str8n-v1.30-bank3-f000-ffff.bin').read_bytes()
    mem = bytearray(65536)
    mem[0xF000:] = image
    assert sym['_END_DATA'] == 0xFD16
    assert image[0xD16:0xD5C] == b'\xff' * 70
    assert 'STR8_WRITE_HEX_BYTE_A' not in sym
    assert image[0xFF0:] == bytes.fromhex('1e1fffffffffffffffffd2f000f0e6f0')

    # Verify every emitted LDX #<MSG followed by a compact print-helper call.
    # Listing addresses are section-relative; opcodes/operands come from BIN.
    pending = None
    checked = 0
    for line in (ROOT / 'BUILD/lst/str8n.lst').read_text().splitlines():
        row = re.match(r'\s*\d+ 00:([0-9A-F]{4}): [0-9A-F]{2} ', line)
        if not row:
            continue
        addr = 0xF000 + int(row[1], 16)
        msg = re.search(r'LDX\s+#<(MSG_\w+)', line)
        if msg:
            pending = msg[1]
            assert mem[addr] == 0xA2 and mem[addr + 1] == sym[pending] & 255
        helper = re.search(r'(?:JSR|JMP|BRA)\s+(STR8_PRINT_TXN_PAGE[01]_X)', line)
        if helper:
            assert pending is not None, line
            entry = sym[helper[1]]
            assert mem[entry] == 0xA0
            assert mem[entry + 1] == sym[pending] >> 8, (pending, helper[1])
            if mem[addr] in (0x20, 0x4C):
                target = mem[addr + 1] | mem[addr + 2] << 8
            else:
                delta = mem[addr + 1]
                target = addr + 2 + (delta if delta < 128 else delta - 256)
            assert target == entry
            checked += 1
            pending = None
    assert checked >= 20
    # STR8_PRINT_PROMPT falls through into page 0 without an explicit call.
    assert sym['MSG_PROMPT'] >> 8 == mem[sym['STR8_PRINT_TXN_PAGE0_X'] + 1]

    def string_at(address):
        out = bytearray()
        for value in mem[address:]:
            out.append(value & 127)
            if value & 128:
                return bytes(out)
        raise AssertionError('unterminated string')
    assert string_at(sym['MSG_ID']) == b'\r\nSTR8-N 1.30\r\n0-2 C W S: '
    assert string_at(sym['MSG_JUMP_B']) == b'\r\nJ B'
    assert string_at(sym['MSG_JUMP_FAIL']) == b'J FAIL\r\n'

    delay = sym['STR8_DELAY_FIXED_A']
    assert mem[delay:delay + 15] == bytes.fromhex('a2b6a0f888d0fdcad0f83ad0f33860')
    for offset in (5, 8, 11):
        dest = delay + offset + 2 + mem[delay + offset + 1] - 256
        assert (delay + offset + 2) >> 8 == dest >> 8
    for count in (0x23, 0x49, 0x6A):
        cycles = count * (182 * (5 * 248 + 6) + 6) + 7
        print(f'DELAY A=${count:02X}: {cycles} cycles / {cycles / 8_000_000:.6f}s at 8 MHz')

    def run_range(bank, text):
        m = bytearray(mem)
        m[0x90] = bank
        m[0xA3] = 0x5A  # removed count must remain untouched
        a = x = 0
        carry = zero = False
        pc = sym['STR8_I_READ_RANGE']
        stack = []
        for _ in range(300):
            op = m[pc]
            pc += 1
            if op == 0x20:
                target = m[pc] | m[pc + 1] << 8
                pc += 2
                if target == sym['STR8_PRINT_TXN_PAGE0_X']:
                    continue
                if target == sym['STR8_READ_LINE']:
                    m[0x7B00:0x7B00 + len(text)] = text
                    a = len(text)
                    continue
                stack.append(pc)
                pc = target
            elif op == 0x60:
                if stack:
                    pc = stack.pop()
                else:
                    assert m[0xA3] == 0x5A
                    return carry, m[0xA1], m[0xA2]
            elif op in (0x90, 0xB0, 0xD0, 0xF0):
                delta = m[pc]
                pc += 1
                take = {0x90: not carry, 0xB0: carry, 0xD0: not zero, 0xF0: zero}[op]
                if take:
                    pc += delta if delta < 128 else delta - 256
            elif op in (0x18, 0x38):
                carry = op == 0x38
            elif op in (0x3A, 0x1A, 0x0A):
                if op == 0x0A:
                    carry = bool(a & 128)
                a = (a - 1 if op == 0x3A else a + 1 if op == 0x1A else a << 1) & 255
                zero = a == 0
            elif op == 0xAA:
                x = a
                zero = x == 0
            elif op == 0x85:
                m[m[pc]] = a
                pc += 1
            elif op in (0xA2, 0xA6, 0xA5, 0xAD, 0xBD, 0xC9, 0xC5, 0xE0, 0x29, 0xE9):
                value = m[pc]
                pc += 1
                if op in (0xA6, 0xA5, 0xC5):
                    value = m[value]
                elif op in (0xAD, 0xBD):
                    address = value | m[pc] << 8
                    pc += 1
                    value = m[address + (x if op == 0xBD else 0)]
                if op in (0xA2, 0xA6):
                    x = value
                    zero = x == 0
                elif op in (0xC9, 0xC5, 0xE0):
                    lhs = x if op == 0xE0 else a
                    carry, zero = lhs >= value, lhs == value
                else:
                    if op == 0xE9:
                        total = a - value - (not carry)
                        a, carry = total & 255, total >= 0
                    else:
                        a = a & value if op == 0x29 else value
                    zero = a == 0
            else:
                raise AssertionError(f'unsupported opcode ${op:02X} at ${pc - 1:04X}')
        raise AssertionError('range parser did not return')

    cases = 0
    for bank in range(4):
        for start in range(16):
            for end in range(16):
                text = f'{start:X}-{end:X}'.encode()
                result = run_range(bank, text)
                valid = 8 <= start <= end and (bank != 3 or end < 15)
                assert result[0] == valid, (bank, text, result)
                if valid:
                    assert result[1:] == (start << 4, ((end + 1) << 4) & 255)
                cases += 1
        for value in range(128):
            text = bytes([value])
            nibble = chr(value).upper()
            valid = nibble in '89ABCDEF' and (bank != 3 or nibble != 'F')
            result = run_range(bank, text)
            assert result[0] == valid, (bank, text, result)
            cases += 1
        for text in (b'', b'CC', b'C--E', b'C/E', b'G-F', b'8-G'):
            assert not run_range(bank, text)[0], text
            cases += 1
    print(f'RESIDENT RECLAIM PASS: {checked} compiled message-page calls, {cases} linked parser cases, 70-byte margin')


if __name__ == '__main__':
    main()
