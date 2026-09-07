"""v1.31 binary regressions: message pages, delay contract, actual range parser.

The deliberately limited CPU harness rejects unsupported instructions; it runs
the linked range parser, stubbing only console printing and line acquisition.
It is not a general CPU emulator or a substitute for board timing evidence.
"""
from pathlib import Path
import base64
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'BUILD/v1.31'


def symbols(path):
    return {n: int(a, 16) for a, n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$', path.read_text(), re.M)}


def main():
    sym = symbols(REL / 'map/str8n-v1.31-f000.map')
    worker_sym = symbols(REL / 'map/str8n-v1.31-worker-0200.map')
    image = (REL / 'bin/str8n-v1.31-bank3-f000-ffff.bin').read_bytes()
    mem = bytearray(65536)
    mem[0xF000:] = image
    # Frozen canonical host image, never a board dump. Protect the deliberately
    # unchanged vectors, directory/configuration, and sensitive resident code.
    # The LED slice deliberately changes the packed worker.
    golden = json.loads((ROOT / 'tools/fixtures/resident-521fd0a.json').read_text())
    old = base64.b64decode(golden['image'])
    assert hashlib.sha256(old).hexdigest() == golden['sha256']
    assert image[0xFB0:] == old[0xFB0:]
    for name, length in [('STR8_DELAY_FIXED_A', 15), ('STR8_IVY_ENTRY_NMI', 20),
                         ('STR8_IVY_ENTRY_IRQ_MASTER', 46), ('STR8_REC_ADVANCE_APPLY_POINTERS', 13),
                         ('STR8_CON_INIT', 12),
                         ('STR8_CON_READ_BYTE_NONBLOCK', 31), ('STR8_CON_WRITE_BYTE_BLOCK', 37)]:
        previous, current = golden['symbols'][name] - 0xF000, sym[name] - 0xF000
        assert old[previous:previous + length] == image[current:current + length], name
    new_data = bytearray(image[sym['_BEG_DATA'] - 0xF000:sym['_END_DATA'] - 0xF000])
    old_data = bytearray(old[golden['symbols']['_BEG_DATA'] - 0xF000:golden['symbols']['_END_DATA'] - 0xF000])
    # v1.31 changes only the final identity digit in otherwise frozen resident
    # data. Check that exact transition, then compare every remaining byte.
    version_addr = sym['MSG_ID'] + len(b'\r\nSTR8-N 1.3')
    version_offset = version_addr - sym['_BEG_DATA']
    assert old_data[version_offset] == ord('0')
    assert new_data[version_offset] == ord('1')
    old_data[version_offset] = new_data[version_offset]
    assert new_data == old_data
    assert sym['_END_DATA'] == 0xFD28
    assert sym['STR8_WORKER_STORE'] == 0xFD50
    assert image[0xD28:0xD50] == b'\xff' * 40
    page0 = sym['STR8_PRINT_TXN_PAGE0_X'] - 0xF000
    page1 = sym['STR8_PRINT_TXN_PAGE1_X'] - 0xF000
    assert page1 == page0 + 4
    assert image[page0:page1 + 2] == bytes.fromhex('a0fc8002a0fd')
    # Compact messages use explicit $FC/$FD helpers. A string may cross the
    # boundary; its call must select the page containing its first byte.
    assert sym['MSG_ID'] >> 8 == 0xFC
    assert sym['MSG_JUMP_FAIL'] >> 8 == sym['MSG_RESET'] >> 8 == 0xFD
    assert (sym['MSG_BACKSPACE'] + 2) >> 8 == 0xFD
    assert sym['STR8_REC_OP_PARSE'] == sym['STR8_REC_FORMAT_S19'] == sym['STR8_REC_SOURCE_CONSOLE'] == 1
    assert sym['STR8_REC_SOURCE_BUFFER'] == sym['STR8_REC_DATA_BUF_LO'] == 0
    assert 'STR8_WRITE_HEX_BYTE_A' not in sym
    assert image[0xFF0:] == bytes.fromhex('1e1fffffffffffffffffd2f000f0e6f0')

    # LED slices: raw public console code remains frozen above, while semantic
    # owners publish complete-byte states at explicit boundaries.
    porta = sym['STR8_LED_PIA_PORTA']
    assert porta == 0x7FA0
    quiet = sym['STR8_IN65_EDU_QUIET'] - 0xF000
    assert image[quiet:quiet + 20] == bytes.fromhex(
        'a9308da17fa9ff8da07fa9348da17fa9018da07f')
    loop = sym['STR8_CMD_LOOP'] - 0xF000
    assert image[loop + 3:loop + 18] == bytes.fromhex(
        'a9202ce07fd004a94380011a8da07f')
    line = image[sym['STR8_READ_LINE'] - 0xF000:sym['STR8_TO_UPPER_A'] - 0xF000]
    assert bytes.fromhex('48a9078da07f68') in line
    assert bytes.fromhex('a9018da07f9860') in line
    raw_write = sym['STR8_CON_WRITE_BYTE_BLOCK']
    assert bytes((0x20, raw_write & 255, raw_write >> 8)) in line
    text_read = image[sym['STR8_READ_TEXT_BYTE_BLOCK'] - 0xF000:sym['STR8_TO_UPPER_A'] - 0xF000]
    assert bytes.fromhex('8da07f') not in text_read
    record_activity = sym['STR8_READ_RECORD_ACTIVITY'] - 0xF000
    record_body = sym['STR8_RECORD_SERVICE_BODY']
    assert image[record_activity:record_activity + 8] == bytes((
        0xA9, 0x07, 0x8D, 0xA0, 0x7F,
        0x4C, record_body & 255, record_body >> 8))
    activity = sym['STR8_WRITE_ACTIVITY_A'] - 0xF000
    assert image[activity:activity + 10] == bytes.fromhex(
        '48a90b8da07f684c19f0')
    printer = sym['STR8_PRINT_XY'] - 0xF000
    write_activity = sym['STR8_WRITE_ACTIVITY_A']
    assert bytes((0x20, write_activity & 255, write_activity >> 8)) in image[printer:printer + 24]
    assert bytes((0x4C, write_activity & 255, write_activity >> 8)) in image[printer:printer + 32]
    ram_load = image[sym['STR8_CMD_LOAD_RAM'] - 0xF000:sym['STR8_CMD_INSTALL_PREVIEW'] - 0xF000]
    assert bytes.fromhex('9ca07f6c') in ram_load
    himon_release = bytes.fromhex('9ca07f4c00c0')
    warm = sym['STR8_ENTER_HIMON_WARM'] - 0xF000
    cold = sym['STR8_ENTER_HIMON_COLD'] - 0xF000
    assert himon_release in image[warm:cold]
    assert himon_release in image[cold:sym['STR8_CMD_LOOP'] - 0xF000]

    worker_store = sym['STR8_WORKER_STORE'] - 0xF000
    worker = image[worker_store:0xFB0]
    assert len(worker) == 0x260
    flash_unlock = worker_sym['STR8W_FLASH_UNLOCK'] - 0x0200
    assert worker[flash_unlock:flash_unlock + 10] == bytes.fromhex(
        'a9f08da07fa9aa8d55d5')
    jump = worker_sym['STR8W_JUMP_BANK'] - 0x0200
    staged = worker_sym['STR8W_PROGRAM_STAGED_SECTOR'] - 0x0200
    assert bytes.fromhex('9ca07f6c') in worker[jump:staged]
    select3 = worker_sym['STR8W_SELECT_BANK3']
    restore = bytes((0x08, 0x20, select3 & 0xFF, select3 >> 8,
                     0xA9, 0x01, 0x8D, 0xA0, 0x7F, 0x28))
    body = worker[worker_sym['STR8W_START_BODY'] - 0x0200:jump]
    assert restore in body

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
    assert string_at(sym['MSG_ID']) == b'\r\nSTR8-N 1.31\r\n0-2 C W S: '
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
    print(f'RESIDENT RECLAIM PASS: {checked} compiled message-page calls, {cases} linked parser cases, 40-byte margin')


if __name__ == '__main__':
    main()
