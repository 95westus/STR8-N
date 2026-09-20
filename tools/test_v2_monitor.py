"""Linked-code B/D/M/G checks, including preflight failures and NMI publication.

Uses the boot suite's bank/console model. No board access or flash writes.
"""
import hashlib
import json
import random
import re

from test_v2_boot import OUT, IMAGE, SYM, boot, command, hold, run

CASES = []


def check_bank_and_display():
    for resident in range(4):
        cpu, mem = boot(resident)
        for target in range(4):
            before = len(mem.bank_changes)
            assert f'B{target}'.encode() in command(cpu, f'B{target}\r'.encode())
            assert mem.bank == resident and len(mem.bank_changes) == before
            assert mem.ram[SYM['V2_SELECTED']] == target
            assert mem.ram[SYM['V2_RESIDENT']] == resident
            expected = bytes(range(target*16, target*16+16))
            mem.banks[target][0xFF8:0x1008] = expected
            output = command(cpu, b'D 8FF8 9007\r')
            assert ('8FF8: ' + ' '.join(f'{b:02X}' for b in expected)).encode() in output
            assert mem.bank == resident and mem.bank_changes[-1] == resident
        for line in (b'B', b'B4', b'B-1', b'B00'):
            old = mem.ram[SYM['V2_SELECTED']]
            assert b'Bad bank' in command(cpu, line + b'\r')
            assert mem.ram[SYM['V2_SELECTED']] == old
    cpu, mem = boot(0)
    mem.ram[0x200:0x223] = bytes(range(35))
    output = command(cpu, b'd 0200\r')
    assert b'0200: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F' in output
    assert b'0210:' not in output
    output = command(cpu, b'D 0200 0222\r')
    assert b'0210: 10 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 1E 1F' in output
    assert b'0220: 20 21 22\r\n' in output
    for line in (b'D FFFF FFFF', b'D FFF0 FFFF', b'D FFF0'):
        output = command(cpu, line + b'\r')
        assert b'Bad' not in output and b'0000:' not in output
    assert b'Bad range' in command(cpu, b'D FFF1\r')
    assert b'Bad range' in command(cpu, b'D 220 200\r')
    for line in (b'D 7F00', b'D 7EF8', b'D 7EFF 8000', b'D 0000 FFFF'):
        before = len(mem.io_reads)
        assert b'Protected address' in command(cpu, line + b'\r')
        # Only FT245 handshakes occur; no requested I/O-range read happens.
        assert set(mem.io_reads[before:]) <= {0x7FE0, 0x7FE1, 0x7FE3}
    CASES.append('B selection independent of resident; D selected-bank data, rows, boundaries, I/O preflight')


def check_modify():
    cpu, mem = boot(1)
    rng = random.Random(81602)
    for _ in range(40):
        address = rng.randrange(0x200, 0x68F0)
        values = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 9)))
        line = f'M {address:04X} ' + ' '.join(f'{b:02X}' for b in values)
        output = command(cpu, line.lower().encode() + b'\r')
        assert b'Bad' not in output and b'Protected' not in output
        assert mem.ram[address:address+len(values)] == values
    for address in (0x0000, 0x00DF, 0x0200, 0x68FF, 0x7E00, 0x7E09, 0x7E10, 0x7E19):
        assert b'Protected' not in command(cpu, f'M {address:X} A5\r'.encode())
        assert mem.ram[address] == 0xA5
    for address in (0x00E0, 0x00FF, 0x0100, 0x01FF, 0x6900, 0x7BFF, 0x7C00,
                    0x7D00, 0x7E0A, 0x7E0F, 0x7E1A, 0x7E20, 0x7EFF, 0x7F00, 0x8000, 0xFFFF):
        assert b'Protected address' in command(cpu, f'M {address:04X} 00\r'.encode())
    for address in (0x00DF, 0x68FF, 0x7E09, 0x7E19):
        before = bytes(mem.ram[address:address+2])
        assert b'Protected address' in command(cpu, f'M {address:04X} 00 01\r'.encode())
        assert mem.ram[address:address+2] == before
    before = bytes(mem.ram[0x0200:0x0210])
    for line in (b'M 200 AA GG', b'M 200 AA 100', b'M 200', b'M 200 AA :0',
                 b'M 200 AA 0G', b'M 200 AA /0', b'M 200 AA 00X'):
        assert b'Bad hex' in command(cpu, line + b'\r'), line
        assert mem.ram[0x0200:0x0210] == before
    assert b'Line too long' in command(cpu, b'M 0200 ' + b'00 '*12 + b'\r')
    assert mem.ram[0x0200:0x0210] == before
    CASES.append('M exact writes, full-command preflight, zero-page/workspace/flash guards, pointer exceptions')


def check_hex_and_go():
    cpu, mem = boot(2)
    for text in (b'', b' ', b'-1', b'10000', b'0x200', b'$200', b'020G', b':', b'@', b'['):
        for op in (b'D', b'M', b'G'):
            output = command(cpu, op + b' ' + text + b'\r')
            assert b'Bad hex' in output, (op, text, output)
    for line in (b'G 200 300', b'D 200 300 400'):
        assert b'Bad hex' in command(cpu, line + b'\r')
    for address in (0xE0, 0x100, 0x6900, 0x7E20, 0x7F00):
        assert b'Protected address' in command(cpu, f'G {address:X}\r'.encode())
    for resident in range(4):
        for target in range(4):
            for address in (0x0200, 0x9000):
                cpu, mem = boot(resident)
                command(cpu, f'B{target}\r'.encode())
                ram = bytes(mem.ram[0x0200:0x6900])
                vectors = bytes(mem.ram[0x7E00:0x7F00])
                mem.rx.extend(f'G {address:04X}\r'.encode())
                run(cpu, lambda: mem.bank == target and cpu.pc == address)
                assert cpu.sp == 255 and cpu.p & cpu.INTERRUPT and not cpu.p & cpu.DECIMAL
                assert mem.ram[0x0200:0x6900] == ram
                assert mem.ram[0x7E00:0x7F00] == vectors
                assert mem.ram[0x7FA0] == 0
    cpu, mem = boot(1)
    mem.ram[0x7E02:0x7E04] = b'\x00\x02'
    assert b'STR8-N' in command(cpu, b'G F003\r')
    assert mem.ram[0x7E02:0x7E04] == b'\x00\x02'
    CASES.append('shared hex rejection; 32 G bank/RAM/flash handoffs; G F003 preserves installed pointers')


def check_nmi_publication():
    cpu, mem = boot(0)
    mem.ram[0x7E00:0x7E02] = b'\x34\x02'
    mem.rx.extend(b'M 7E00 78 04\r')
    # Stop between pointer-byte writes, when a torn address would be $0278.
    run(cpu, lambda: cpu.pc == SYM['V2_M_WRITE'] and cpu.y == 1)
    assert mem.ram[0x7E00:0x7E02] == b'\x78\x02'
    assert mem.ram[SYM['V2_NMI_HOLD']] == 1
    before = (cpu.a, cpu.x, cpu.y, cpu.sp, cpu.p)
    resume = cpu.pc
    cpu.nmi()
    run(cpu, lambda: cpu.pc == resume)
    assert (cpu.a, cpu.x, cpu.y, cpu.sp) == before[:4]
    # py65 normalizes the unused status bit during RTI.
    assert cpu.p & 0xCF == before[4] & 0xCF
    hold(cpu)
    assert mem.ram[0x7E00:0x7E02] == b'\x78\x04'
    assert mem.ram[SYM['V2_NMI_HOLD']] == 0
    cpu.nmi()
    run(cpu, lambda: cpu.pc == 0x0478)
    CASES.append('NMI during pointer publication cannot follow torn address; dispatch restored after M')


def check_review_regressions():
    cpu, mem = boot(0)
    for bad in (0x00, 0x01, 0x02, 0x0B, 0x1B, 0x80, 0xFF):
        before = mem.ram[0x0200]
        assert b'Bad input' in command(cpu, b'M 0200 A' + bytes([bad]) + b'A\r')
        assert mem.ram[0x0200] == before
    assert b'Bad' not in command(cpu, b'M\t0200\t12\t34\r')
    assert mem.ram[0x0200:0x0202] == b'\x12\x34'
    # Reads around the snapshot destination must not corrupt successive rows.
    expected = bytes(range(48))
    mem.ram[0x7C70:0x7CA0] = expected
    output = command(cpu, b'D 7C70 7C9F\r')
    for offset in (0, 16, 32):
        line = f'{0x7C70+offset:04X}: ' + ' '.join(f'{b:02X}' for b in expected[offset:offset+16])
        assert line.encode() in output
    assert mem.ram[0x7C70:0x7CA0] == expected
    output = command(cpu, b'D 7C7F 7C8E\r')
    assert ('7C7F: ' + ' '.join(f'{b:02X}' for b in expected[15:31])).encode() in output
    # Application scratch can be dirty on prompt reentry; vectors still survive.
    mem.ram[SYM['V2_NMI_HOLD']] = 1
    pointers = bytes(mem.ram[0x7E00:0x7E1A])
    command(cpu, b'G F003\r')
    assert mem.ram[SYM['V2_NMI_HOLD']] == 0
    assert mem.ram[0x7E00:0x7E1A] == pointers
    exact = b'M 0200 01 02 03 04 05 06 07 08  '
    assert len(exact) == 32
    assert b'Bad' not in command(cpu, exact + b'\r')
    before = bytes(mem.ram[0x0200:0x0208])
    assert b'Line too long' in command(cpu, exact + b' \r')
    assert mem.ram[0x0200:0x0208] == before
    command(cpu, b'M 02FE AA BB CC DD\r')
    assert mem.ram[0x02FE:0x0302] == b'\xAA\xBB\xCC\xDD'
    CASES.append('review regressions: rejected corrupt input, tabs, overlapping display buffer, dirty NMI gate, line limit')


def check_full_flash_display():
    cpu, mem = boot(0)
    expected = bytes((i*37 + (i >> 8)) & 255 for i in range(32768))
    mem.banks[1][:] = expected
    command(cpu, b'B1\r')
    begin = len(mem.tx)
    mem.rx.extend(b'D 8000 FFFF\r')
    run(cpu, lambda: cpu.pc == SYM['V2_GETC'] and not mem.rx, limit=4000000)
    rows = re.findall(rb'^([0-9A-F]{4}): ([0-9A-F ]+)\r?$', bytes(mem.tx[begin:]), re.M)
    assert len(rows) == 2048
    assert [int(addr, 16) for addr, _ in rows] == list(range(0x8000, 0x10000, 16))
    assert b''.join(bytes.fromhex(data.decode()) for _, data in rows) == expected
    assert mem.bank == 0 and mem.ram[SYM['V2_SELECTED']] == 1
    CASES.append('full 32 KiB selected-flash dump terminates at FFFF with exact data and resident restored')


def check_all_modify_addresses():
    cpu, mem = boot(0)
    allowed = set(range(0xE0)) | set(range(0x200, 0x6900)) | set(range(0x7E00, 0x7E0A)) | set(range(0x7E10, 0x7E1A))
    for address in range(65536):
        mem.ram[SYM['V2_ADDR']:SYM['V2_ADDR']+2] = address.to_bytes(2, 'little')
        cpu.sp = 255
        cpu.stPushWord(0x01FF)
        cpu.pc = SYM['V2_MODIFIABLE_ADDRESS']
        run(cpu, lambda: cpu.pc == 0x0200, limit=50)
        assert bool(cpu.p & cpu.CARRY) == (address in allowed), f'{address:04X}'
    CASES.append('exhaustive M address policy across all 65,536 addresses')


def main():
    for test in (check_bank_and_display, check_modify, check_hex_and_go, check_nmi_publication,
                 check_review_regressions, check_all_modify_addresses, check_full_flash_display):
        test()
        print('PASS:', CASES[-1])
    (OUT / 'monitor-test-results.json').write_text(json.dumps({
        'passed': CASES, 'image_sha256': hashlib.sha256(IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
