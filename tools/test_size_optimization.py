"""Execute linked v1.34 against frozen v1.33 behavior with its banner digit updated.

Only console transport, elapsed delay, and the private flash doorway are
stubbed. The tests never access board hardware or modify release artifacts.
"""
from test_conservative_resident import MAPS, OLD, NEW, Run


def message(image, syms, name):
    start = syms[name] - 0xF000
    result = bytearray()
    for byte in image[start:]:
        result.append(byte & 0x7F)
        if byte & 0x80:
            return bytes(result)
    raise AssertionError(('unterminated message', name))


def messages_tests():
    count = 0
    for name in sorted(n for n in MAPS[0] if n.startswith('MSG_')):
        if not 0xF000 <= MAPS[0][name] < MAPS[0]['_END_DATA']:
            continue
        expected = message(OLD, MAPS[0], name)
        for variant, image in enumerate((OLD, NEW)):
            r = Run(variant)
            r.console()
            r.cpu.x, r.cpu.y = r.sym[name] & 255, r.sym[name] >> 8
            r.run('STR8_PRINT_XY')
            assert bytes(r.output) == expected, (variant, name, r.output, expected)
            assert message(image, r.sym, name) == expected
            count += 1
    assert message(NEW, MAPS[1], 'MSG_ID').endswith(message(NEW, MAPS[1], 'MSG_BOOT_PROMPT'))
    for variant in (0, 1):
        r = Run(variant)
        r.console()
        r.run('STR8_PRINT_PROMPT')
        assert bytes(r.output) == message(OLD, MAPS[0], 'MSG_PROMPT')
    print(f'MESSAGE EXECUTION: {count} message cases plus prompt/banner fall-through PASS')


class ReadbackMemory(list):
    def __init__(self, data, fail_address, limit):
        super().__init__(data)
        self.fail_address = fail_address
        self.limit = limit
        self.written = set()

    def __setitem__(self, address, value):
        if isinstance(address, int) and 0x200 <= address < self.limit:
            self.written.add(address)
        super().__setitem__(address, value)

    def __getitem__(self, address):
        value = super().__getitem__(address)
        if isinstance(address, int) and address == self.fail_address and address in self.written:
            return value ^ 0x80
        return value


def copy_tests():
    count = 0
    for variant, image in enumerate((OLD, NEW)):
        syms = MAPS[variant]
        size = syms['STR8_WORKER_SIZE']
        store = syms['STR8_WORKER_STORE']
        expected = image[store - 0xF000:store - 0xF000 + size]
        for failure in (None, *range(size)):
            r = Run(variant)
            r.mem[0x200:0xA00] = [0xA5] * 0x800
            r.mem = ReadbackMemory(r.mem, None if failure is None else 0x200 + failure, 0x200 + size)
            r.cpu.memory = r.mem
            r.run('STR8_COPY_WORKER_TO_RAM')
            copied = size if failure is None else failure + 1
            assert bool(r.cpu.p & 1) == (failure is None), (variant, failure)
            assert bytes(r.mem[0x200:0x200 + copied]) == expected[:copied]
            assert bytes(r.mem[0x200 + copied:0xA00]) == bytes([0xA5]) * (0x800 - copied)
            assert r.mem.written == set(range(0x200, 0x200 + copied))
            offset = size if failure is None else failure
            assert r.cpu.x == (size >> 8) - (offset >> 8)
            assert r.cpu.y == offset & 255
            assert r.mem[0xCD:0xD1] == [store & 255, (store >> 8) + (offset >> 8), 0, 2 + (offset >> 8)]
            count += 1
    print(f'WORKER COPY EXECUTION: {count} success/every-byte verification failures PASS')


def readiness_tests():
    count = 0
    for variant in (0, 1):
        for control in range(256):
            for carry in (0, 1):
                r = Run(variant, control)
                r.mem[0x7FE0] = control
                r.mem[0x7FE1] = 0xA7
                r.mem[0x7FA0] = 0xD3
                r.carry(carry)
                xy = (r.cpu.x, r.cpu.y)
                r.run('STR8_CHAR_READY_SERVICE_ENTRY')
                assert bool(r.cpu.p & 1) == (control & 2 == 0)
                assert (r.cpu.x, r.cpu.y) == xy
                assert (r.mem[0x7FE0], r.mem[0x7FE1], r.mem[0x7FA0]) == (control, 0xA7, 0xD3)
                count += 1
    print(f'CHAR_READY EXECUTION: {count} control/carry cases PASS')


def line(variant, text, limit, count=1):
    r = Run(variant)
    r.console(text)
    results = []
    for _ in range(count):
        r.cpu.x = limit
        r.run('STR8_READ_LINE')
        results.append((r.cpu.a, bytes(r.mem[0x7B00:0x7B00 + r.cpu.a + 1]), r.mem[0x7DF1]))
    assert r.mem[0x7FA0] == 1
    return results, bytes(r.output), bytes(r.input)


def line_tests():
    cases = [(bytes([value]) + b'\r', limit, 1) for value in range(256) for limit in (1, 2, 5)]
    cases.extend((text, limit, count) for text, limit, count in (
        (b'abc\x08D\x7fe\r', 5, 1), (b'\x08\x7fabcxyz\r', 3, 1),
        (b'a\r\nb\r\nc\n', 5, 3), (b'a\rb\nc\r', 5, 3),
        (b'abc\x08\x08\x08\x08d\r', 3, 1), (b'abcde\x08f\r', 3, 1)))
    for text, limit, count in cases:
        assert line(0, text, limit, count) == line(1, text, limit, count), (text, limit)
    assert line(1, b'abc\x08D\x7fe\r', 5)[0][0][:2] == (3, b'ABE\0')
    assert [item[1] for item in line(1, b'a\r\nb\r\nc\n', 5, 3)[0]] == [b'A\0', b'B\0', b'C\0']
    print(f'LINE EDITOR DIFFERENTIAL: {len(cases)} ASCII/edit/limit/CRLF cases PASS')


def transport(r, data=b''):
    r.console(data)
    def poll():
        if r.input:
            r.cpu.a = r.input.popleft()
            r.carry(True)
        else:
            r.carry(False)
    def delay():
        r.calls.append(('delay', r.cpu.a))
        r.cpu.a = r.cpu.x = r.cpu.y = 0
        r.carry(True)
    r.hook('STR8_CON_READ_BYTE_NONBLOCK', poll)
    r.hook('STR8_CON_FLUSH_RX', lambda: r.calls.append(('flush',)))
    r.hook('STR8_DELAY_FIXED_A', delay)


def startup_tests():
    for signature in ((0, 0), (0x52, 0x53), (0x52, 0), (0, 0x53)):
        for key in (b'', b'0', b'1', b'2', b'c', b'w', b's', b'3', b'x'):
            results = []
            for variant in (0, 1):
                r = Run(variant)
                transport(r, key)
                r.mem[r.sym['STR8_SOFT_RESET_SIG0']] = signature[0]
                r.mem[r.sym['STR8_SOFT_RESET_SIG1']] = signature[1]
                r.run('STR8_STARTUP_DELAY')
                results.append((r.result(), bytes(r.output), r.calls, r.mem[r.sym['STR8_SOFT_RESET_SIG1']]))
            assert results[0] == results[1], (signature, key, results)
            assert results[1][3] == 0
            reset = 'MSG_RST_S' if signature == (0x52, 0x53) else 'MSG_RST_H'
            expected = message(OLD, MAPS[0], reset) + message(OLD, MAPS[0], 'MSG_ID')
            assert results[1][1].startswith(expected)
    for value in range(256):
        results = []
        for variant in (0, 1):
            r = Run(variant)
            transport(r, bytes([value]))
            r.run('STR8_BOOT_KEY_POLL')
            results.append((r.result(), bytes(r.output), bytes(r.input)))
        assert results[0] == results[1], value
        accepted = bytes([value]).upper() in (b'0', b'1', b'2', b'C', b'W', b'S')
        assert bool(results[1][0][1] & 1) == accepted, value
    for cold in (False, True):
        for available in (False, True):
            results = []
            for variant in (0, 1):
                r = Run(variant)
                transport(r)
                signature = bytes([0xA5, 0x5A, 0xC3, 0x3C])
                r.mem[0xC003:0xC007] = signature if available else bytes(4)
                r.mem[0x7EE6:0x7EEA] = [0x91] * 4
                r.run('STR8_ENTER_HIMON_COLD' if cold else 'STR8_ENTER_HIMON_WARM',
                      stop_extra={0xC000, r.sym['STR8_CMD_LOOP']})
                expected = 0xC000 if available else r.sym['STR8_CMD_LOOP']
                assert r.exit_address == expected
                if available:
                    assert bytes(r.mem[0x7EE6:0x7EEA]) == (bytes(4) if cold else signature)
                    assert r.mem[0x7FA0] == 0
                else:
                    assert bytes(r.mem[0x7EE6:0x7EEA]) == bytes([0x91]) * 4
                results.append((bytes(r.output), bytes(r.mem[0x7EE6:0x7EEA]), r.mem[0x7FA0]))
            assert results[0] == results[1]
    print('STARTUP / BOOT KEY / HIMON HANDOFF: 36 reset/key, 256 key-byte, 4 handoff cases PASS')


def boot_tests():
    count = 0
    for available in (False, True):
        for software in (False, True):
            for key in (b'', b's', b'c', b'w', b'0', b'1', b'2'):
                results = []
                for variant in (0, 1):
                    r = Run(variant)
                    transport(r, key)
                    r.mem[0xC003:0xC007] = b'\xA5\x5A\xC3\x3C' if available else bytes(4)
                    if software:
                        r.mem[r.sym['STR8_SOFT_RESET_SIG0']] = 0x52
                        r.mem[r.sym['STR8_SOFT_RESET_SIG1']] = 0x53
                    r.hook('STR8_JUMP_BANK_LAUNCH', lambda: r.calls.append(('launch', r.mem[0x7DF2])))
                    r.run('START', stop_extra={0xC000, r.sym['STR8_CMD_LOOP']})
                    handoff = available and key in (b'', b'c', b'w')
                    assert r.exit_address == (0xC000 if handoff else r.sym['STR8_CMD_LOOP'])
                    assert [call for call in r.calls if call[0] == 'launch'] == \
                           ([('launch', int(key))] if key in (b'0', b'1', b'2') else [])
                    assert bytes(r.mem[0x7EED:0x7EF0]) == b'IVY'
                    assert r.mem[r.sym['STR8_SOFT_RESET_SIG1']] == 0
                    results.append((bytes(r.output), r.calls, bytes(r.mem[0x7EE6:0x7EEA]),
                                    r.mem[0x7FA0], bool(r.cpu.p & r.cpu.DECIMAL)))
                assert results[0] == results[1], (available, software, key, results)
                count += 1
    print(f'RESET THROUGH SELECTOR/HANDOFF: {count} cases PASS (bank-switch doorway stubbed)')


def preflight(variant, bank, state, range_text, inputs):
    r = Run(variant)
    r.console(str(bank).encode() + b'\r' + range_text + b'\r' + inputs)
    base = 0xFFB0 + 16 * bank
    row = bytearray([0xFF] * 16)
    if state != 'empty':
        row[12] = 0xFE if state in ('unsealed', 'sealed') else 0xFC
        if state != 'unsealed':
            row[0] = 0x42
            row[4:9] = b'ABCDE'
            row[9] = 0xFE
    if state == 'invalid':
        row[12] = 0xFD
    r.mem[base:base + 16] = row
    r.hook('STR8_I_PRINT_SUMMARY', lambda: r.calls.append(('summary',)))
    r.run('STR8_CMD_INSTALL_PREVIEW')
    return bytes(r.mem[0x90:0xA3]), bytes(r.output), r.calls, bytes(r.mem[base:base + 16])


def installer_tests():
    count = 0
    for bank in range(4):
        for state in ('empty', 'unsealed', 'sealed', 'complete', 'invalid'):
            for full in (False, True):
                range_text = (b'8-E' if bank == 3 else b'8-F') if full else b'C-E'
                for inputs in (b'AB\rHELLO\r', b'Q\r', b'AB\rBAD?\r'):
                    old = preflight(0, bank, state, range_text, inputs)
                    new = preflight(1, bank, state, range_text, inputs)
                    assert old == new, (bank, state, full, inputs, old, new)
                    valid = state != 'invalid' and (state not in ('unsealed', 'sealed') or full)
                    valid &= state not in ('empty', 'unsealed') or inputs == b'AB\rHELLO\r'
                    assert bool(new[2]) == valid, (bank, state, full, inputs)
                    count += 1
    for bank in range(4):
        for offset in range(16):
            expected = 0xFFB0 + bank * 16 + offset
            for variant in (0, 1):
                r = Run(variant)
                r.mem[0x90] = bank
                r.cpu.a = offset
                r.run('STR8_I_SET_DIR_ADDRESS_A')
                assert r.mem[0xCD:0xCF] == [expected & 255, expected >> 8]
                assert r.mem[0x7E9E:0x7EA0] == [expected & 255, expected >> 8]
    for mask in range(256):
        for current in (0, 1, 0x55, 0xAA, 0xFF):
            results = []
            for variant in (0, 1):
                r = Run(variant)
                r.mem[0x90], r.mem[0x98], r.mem[0xFFDD] = 2, 5, current
                r.cpu.a = mask
                def write():
                    r.calls.append((r.mem[0x7E9E] | r.mem[0x7E9F] << 8,
                                    r.mem[0x7EA0], r.mem[0x7B00]))
                    r.cpu.a = 0
                    r.carry(True)
                r.hook('STR8_DIR_WRITE_BYTES', write)
                r.run('STR8_I_WRITE_JOURNAL_MASK_A')
                results.append(r.calls)
            assert results[0] == results[1] == [(0xFFDD, 1, current & ~(1 << (mask & 7)))]
    print(f'INSTALLER EXECUTION: {count} preflight, 64 pointer, 1280 mask/current-byte cases PASS')


def interrupt_tests():
    count = 0
    for variant in (0, 1):
        for route in ('nmi', 'irq', 'brk'):
            for signature in (b'IVY', b'XVY', b'IXY', b'IVX'):
                for target in (0, 0x3000):
                    r = Run(variant, target)
                    r.mem[0x7EED:0x7EF0] = signature
                    for index, vector in enumerate((0x7EFA, 0x7EFC, 0x7EFE)):
                        handler = target + index * 0x10 if target else 0
                        r.mem[vector:vector + 2] = [handler & 255, handler >> 8]
                        address = 0x3000 + index * 0x10
                        r.mem[address:address + 4] = [0xEE, index, 0x40, 0x40]  # INC route counter; RTI
                    r.cpu.pc = 0x2000
                    r.cpu.sp = 0xFF
                    r.cpu.p = 0x21
                    r.cpu.a, r.cpu.x, r.cpu.y = 0x57, 0xA2, 0x39
                    if route == 'nmi':
                        r.cpu.nmi()
                    elif route == 'irq':
                        r.cpu.irq()
                    else:
                        r.mem[0x2000:0x2002] = [0, 0xEA]
                        r.cpu.step()
                    endpoint = 0x2002 if route == 'brk' else 0x2000
                    for _ in range(100):
                        if r.cpu.pc == endpoint:
                            break
                        r.cpu.step()
                    else:
                        raise AssertionError(('interrupt did not return', variant, route))
                    assert (r.cpu.a, r.cpu.x, r.cpu.y, r.cpu.sp) == (0x57, 0xA2, 0x39, 0xFF)
                    assert r.cpu.p & 0xCF == 0x21 & 0xCF
                    expected = [0, 0, 0]
                    expected[{'nmi': 0, 'brk': 1, 'irq': 2}[route]] = int(signature == b'IVY' and target != 0)
                    assert r.mem[0x4000:0x4003] == expected, (variant, route, signature, target)
                    count += 1
    print(f'REAL NMI / IRQ / BRK DISPATCH: {count} signature/vector cases PASS')


if __name__ == '__main__':
    messages_tests()
    copy_tests()
    readiness_tests()
    line_tests()
    startup_tests()
    boot_tests()
    installer_tests()
    interrupt_tests()
