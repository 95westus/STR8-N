"""Execute the linked RAM utility against the banked flash/console CPU model."""
import json
import sys

import build_bank_maint_v2 as builder
import build_v2_config as firmware
sys.modules['build_v2'] = firmware
sys.modules['build_v2_a24'] = firmware
import test_v2_a24_console  # FT245 timing model
import test_v2_boot as boot
import test_v2_flash as flash

REPORT = json.loads((builder.OUT / 'manifest.json').read_text())
SYM = REPORT['symbols']
IMAGE, ENTRY = firmware.read_s19(builder.OUT / (builder.NAME + '.s19'))


def start():
    cpu, mem = flash.boot_flash(3)
    for address, value in IMAGE.items():
        mem.ram[address] = value
    cpu.pc = ENTRY
    wait(cpu)
    assert b'BANK MAINT' in mem.tx and b'INVALID' not in mem.tx
    return cpu, mem


def wait(cpu, suffix=b'BM> '):
    mem = cpu.memory
    boot.run(cpu, lambda: cpu.pc == flash.W['V2W_GETC_WAIT'] and not mem.rx
             and bytes(mem.tx).endswith(suffix), limit=12_000_000)


def command(cpu, line, answers=''):
    mem = cpu.memory
    offset = len(mem.tx)
    mem.rx.extend((line + '\r' + answers).encode())
    cpu.step()
    wait(cpu)
    return bytes(mem.tx[offset:])


def pattern(size, seed=0):
    return bytes((i * 37 + (i >> 8) + seed) & 255 for i in range(size))


def editor():
    cpu, mem = start()
    assert b'INVALID' in command(cpu, 'W 1 8')
    command(cpu, 'N 9 00')
    command(cpu, '  P 0 31 32 33 34 35 36 37 38 39')
    assert bytes(mem.ram[0x5000:0x5009]) == b'123456789'
    assert b'29B1' in command(cpu, 'K')
    before = bytes(mem.ram[0x5000:0x6000])
    for line in ('P 0 AA ZZ', 'P 8 AA BB', 'F 0-9 FF', 'N 1001 00'):
        assert b'INVALID' in command(cpu, line), line
        assert bytes(mem.ram[0x5000:0x6000]) == before
    command(cpu, 'F 1-3 AA')
    assert bytes(mem.ram[0x5000:0x5009]) == b'1\xaa\xaa\xaa56789'
    assert b'31 AA AA AA' in command(cpu, 'D 0-3')
    assert b'VERIFIED' in command(cpu, 'W R 1000', 'Y\r')
    assert mem.ram[0x1000:0x1009] == mem.ram[0x5000:0x5009]
    mem.banks[1][:4096] = pattern(4096)
    command(cpu, 'R 1 8')
    assert bytes(mem.ram[0x5000:0x6000]) == pattern(4096)
    command(cpu, 'P FFF 55')
    expected = pattern(4096)[:-1] + b'\x55'
    assert b'VERIFIED' in command(cpu, 'W 0 9', 'Y\r')
    assert bytes(mem.banks[0][4096:8192]) == expected
    assert bytes(mem.ram[0x5000:0x6000]) == expected
    print('PASS editor: load, preflight, patch, fill, display, CRC, RAM/flash write')


def staging():
    cpu, mem = start()
    original = bytes(IMAGE[a] for a in range(ENTRY, SYM['BM_END'])).ljust(8192, b'\xff')
    before = bytes(mem.ram[0x5000:0x6000])
    for invalid in ('S 7', 'S A', 'S 108', 'S 8 junk'):
        assert b'INVALID' in command(cpu, invalid)
        assert bytes(mem.ram[0x5000:0x6000]) == before and not mem.events
    for sector in (8, 9):
        assert b'BUFFER CHANGED' in command(cpu, f'S {sector:X}')
        block = original[(sector-8)*4096:(sector-7)*4096]
        assert bytes(mem.ram[0x5000:0x6000]) == block
        assert mem.ram[SYM['BLEN']] == 0 and mem.ram[SYM['BLEN']+1] == 0x10
        assert b'VERIFIED' in command(cpu, f'W 1 {sector:X}', 'Y\r')
    assert bytes(mem.banks[1][:8192]) == original
    assert bytes(mem.ram[ENTRY:SYM['BM_END']]) == original[:SYM['BM_END']-ENTRY]
    print('PASS built-in staging: exact program blocks, FF padding, B1 archive and invalid inputs')


def copies():
    cpu, mem = start()
    mem.ram[0x1000:0x1100] = pattern(256)
    assert b'VERIFIED' in command(cpu, 'C R 1000-10FF R 1200', 'Y\r')
    assert bytes(mem.ram[0x1200:0x1300]) == pattern(256)
    before = bytes(mem.banks[1])
    assert b'VERIFIED' in command(cpu, 'C R 1000-10FF 1 8F80', 'Y\r')
    assert bytes(mem.banks[1]) == before[:0xF80] + pattern(256) + before[0x1080:]
    assert b'VERIFIED' in command(cpu, 'C 1 8F80-907F R 1400', 'Y\r')
    assert bytes(mem.ram[0x1400:0x1500]) == pattern(256)
    assert b'VERIFIED' in command(cpu, 'C 1 8-9 0 A', 'Y\r')
    assert mem.banks[0][0x2000:0x4000] == mem.banks[1][:0x2000]
    assert b'MATCH' in command(cpu, 'V 1 8-9 0 A')
    mem.banks[0][0x2010] ^= 1
    assert b'DIFFERENT' in command(cpu, 'V 1 8-9 0 A')
    for source, target in ((0x1000, 0x1001), (0x1001, 0x1000)):
        mem.ram[0x1000:0x1300] = pattern(768)
        expected = bytes(mem.ram[source:source+512])
        command(cpu, f'C R {source:X}-{source+511:X} R {target:X}', 'Y\r')
        assert bytes(mem.ram[target:target+512]) == expected
    for source, target in ((0x8100, 0x8180), (0x8180, 0x8100)):
        mem.banks[1][:0x4000] = pattern(0x4000)
        before = bytes(mem.banks[1])
        expected = bytearray(before)
        expected[target-0x8000:target-0x8000+0x2800] = before[source-0x8000:source-0x8000+0x2800]
        command(cpu, f'C 1 {source:X}-{source+0x27FF:X} 1 {target:X}', 'Y\r')
        assert bytes(mem.banks[1]) == expected
    print('PASS copies: all four directions, partial sector preservation, overlapping ranges')


def safeguards():
    cpu, mem = start()
    before = [bytes(b) for b in mem.banks]
    for line in ('E 4 8', 'E 1 7', 'E 1 F-8', 'E 1 8-F junk',
                 'C 1 8-F 0 9', 'C R 1FF-200 1 8', 'C R 2000 1 8',
                 'C 1 8 R 5000', 'C R 68FF-6900 1 8', 'C 1 7FFF 0 8'):
        assert b'INVALID' in command(cpu, line), line
        assert not mem.events
    assert b'CANCELED' in command(cpu, 'E 3 F', 'N\r')
    assert b'CANCELED' in command(cpu, 'E 3 F', 'Y\rNO\r')
    assert [bytes(b) for b in mem.banks] == before and not mem.events
    command(cpu, 'N 1 00')
    assert b'CANCELED' in command(cpu, 'W 3 F', 'Y\rN\r')
    assert b'CANCELED' in command(cpu, 'C 2 F 3 F', 'Y\rN\r')
    assert not mem.events
    assert b'VERIFIED' in command(cpu, 'E 3 F', 'Y\rB3F\r')
    assert bytes(mem.banks[3][0x7000:]) == b'\xff' * 4096
    assert b'J bank' in command(cpu, 'Q')
    assert cpu.pc < 0x8000
    assert [bytes(b) for b in mem.banks[:3]] == before[:3]
    print('PASS protection: invalid ranges, both B3:F confirmations, RAM hold after resident erase')


def erase_and_faults():
    for bank in range(4):
        cpu, mem = start()
        mem.banks[bank][:] = pattern(0x8000)
        command(cpu, f'E {bank} 8-F', 'Y\r' + ('B3F\r' if bank == 3 else ''))
        assert bytes(mem.banks[bank]) == b'\xff' * 0x8000
    for fault in ('timeout', 'verify', 'erase_verify'):
        cpu, mem = start()
        mem.banks[1][:0x2000] = bytes(0x2000)
        mem.banks[0][:0x2000] = b'\xaa' * 8192
        mem.fault = fault
        assert b'FAILED' in command(cpu, 'C 0 8-9 1 8', 'Y\r'), fault
        assert bytes(mem.banks[1][0x1000:0x2000]) == bytes(4096)
        assert cpu.pc < 0x8000
    print('PASS erase B0-B3 8-F; timeout/program/erase faults stop before next sector')


def control_paths():
    cpu, mem = start()
    before = [bytes(b) for b in mem.banks]
    output = command(cpu, 'M')
    assert all(f'B{bank}:'.encode() in output for bank in range(4))
    assert [bytes(b) for b in mem.banks] == before and not mem.events
    assert b'CANCELED' in command(cpu, 'E 1 8' + ' ' * 400)
    assert not mem.events
    mem.rx.extend(b'E 3 E-F\r')
    wait(cpu, b'WRITE? TYPE Y> ')
    assert not mem.events
    mem.rx.extend(b'Y\r')
    wait(cpu, b'TYPE B3F> ')
    assert not mem.events
    mem.rx.extend(b'N\r')
    wait(cpu)
    # Cancel after a verified sector, before the next sector is staged.
    mem.banks[1][:0x3000] = bytes(0x3000)
    mem.rx.extend(b'E 1 8-A\rY\r')
    boot.run(cpu, lambda: cpu.pc == SYM['COPY_SECTOR'] and bool(mem.events), limit=4_000_000)
    mem.rx.append(3)
    wait(cpu)
    assert bytes(mem.banks[1][:4096]) == b'\xff' * 4096
    assert bytes(mem.banks[1][4096:0x3000]) == bytes(8192)
    assert b'CANCELED' in mem.tx
    # Complete both confirmations for a resident F copy and remain in RAM.
    mem.banks[2][0x7000:] = pattern(4096)
    assert b'VERIFIED' in command(cpu, 'C 2 F 3 F', 'Y\rB3F\r')
    assert mem.banks[3][0x7000:] == mem.banks[2][0x7000:]
    assert b'J bank' in command(cpu, 'Q')
    # Boot refuses erased vectors; valid handoff uses the selected reset vector.
    mem.banks[1][0x7FFC:0x7FFE] = b'\xff\xff'
    assert b'INVALID' in command(cpu, 'J 1')
    mem.banks[2][0x7FFC:0x7FFE] = b'\x00\x90'
    mem.rx.extend(b'J 2\r')
    boot.run(cpu, lambda: cpu.pc == 0x9000, limit=200_000)
    assert mem.bank == 2 and cpu.sp == 0xFF
    cpu, mem = start()
    mem.rx.extend(b'Q\r')
    boot.run(cpu, lambda: cpu.pc == 0xF007, limit=200_000)
    assert mem.bank == 3
    print('PASS map, overflow, confirmation stages, between-sector cancel, resident F copy, Q/J')


def main():
    staging()
    editor()
    copies()
    safeguards()
    erase_and_faults()
    control_paths()
    (builder.OUT / 'test-results.json').write_text(json.dumps(dict(
        passed=True, s19_sha256=REPORT['s19_sha256'], hardware_tested=False), indent=2)+'\n')


if __name__ == '__main__':
    main()
