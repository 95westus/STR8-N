"""Exercise a23 S/R/T against the banked flash model."""
import sys
import subprocess
import hashlib
import re
from pathlib import Path

import build_v2_a23 as a23

# Reuse the frozen alpha21 hardware model against the separate a23 artifacts.
sys.modules['build_v2'] = a23
import test_v2_boot as boot
sys.modules['test_v2_boot'] = boot
import test_v2_flash as flash


def a23_step(self):
    if self.pc == boot.REPORT['worker']['V2W_BOOT_DELAY']:
        if self.boot_waits == 0:
            assert self.memory.ram[boot.SYM['V2_CONSOLE']] == 0xFF
        self.boot_waits += 1
        if self.boot_waits == getattr(self.memory, 'host_ready_after_wait', None):
            self.memory.ft245_present = True
        self.processorCycles += 329_000
        self.pc = boot.REPORT['worker']['V2W_BOOT_DELAY_DONE']
        return
    return boot.BaseMPU.step(self)


boot.MPU.step = a23_step


def check_cold_usb_start():
    mem = boot.Memory(3, ft245_present=False)
    mem.host_ready_after_wait = 80
    cpu = boot.MPU(memory=mem, pc=boot.SYM['START'])
    mem.cpu = cpu
    boot.hold(cpu)
    assert cpu.boot_waits == 160
    assert mem.ram[boot.SYM['V2_CONSOLE']] == 0
    assert mem.tx.startswith(b'.' * 81)
    assert b'STR8-N 2.0a23 B3 65C02' in mem.tx
    assert not mem.acia_tx
    warm = boot.Memory(3, ft245_present=True)
    cpu = boot.MPU(memory=warm, pc=boot.SYM['START'])
    warm.cpu = cpu
    boot.hold(cpu)
    assert cpu.boot_waits == 160 and warm.tx.startswith(b'.' * 160)
    acia = boot.Memory(3, ft245_present=False)
    cpu = boot.MPU(memory=acia, pc=boot.SYM['START'])
    acia.cpu = cpu
    boot.hold(cpu)
    assert cpu.boot_waits == 160
    assert acia.ram[boot.SYM['V2_CONSOLE']] == 1
    assert b'STR8-N 2.0a23 B3 65C02' in acia.acia_tx
    assert not acia.tx


def check_no_usb_autostart():
    record = bytearray([1, 1, 1, 0, 0, 10, 1] + [0] * 9)
    first = second = 0
    for value in record[:14]:
        first = (first + value) & 255
        second = (second + first) & 255
    record[14:] = bytes((first, second))
    mem = boot.Memory(3, ft245_present=False)
    mem.banks[3][0x6FF0:0x7000] = record
    mem.banks[1][0x7FFC:0x7FFE] = b'\x00\x90'
    cpu = boot.MPU(memory=mem, pc=boot.SYM['START'])
    mem.cpu = cpu
    boot.run(cpu, lambda: cpu.pc == boot.SYM['V2_AUTO_TICK'], limit=3_000_000)
    assert cpu.boot_waits == 0
    assert mem.ram[boot.SYM['V2_CONSOLE']] == 0xFF
    assert mem.ram[boot.SYM['V2_TICKS']] == 10
    assert not mem.tx and not mem.acia_tx
    assert not ({0x7F80, 0x7F81, 0x7F82, 0x7F83} & set(mem.writes))
    start_cycles = cpu.processorCycles
    boot.run(cpu, lambda: cpu.pc == 0x9000, limit=4_000_000)
    window_cycles = cpu.processorCycles - start_cycles
    assert 8_000_000 <= window_cycles <= 8_900_000, window_cycles
    assert mem.bank == 1
    ready = boot.Memory(3, ft245_present=True)
    ready.banks[3][0x6FF0:0x7000] = record
    cpu = boot.MPU(memory=ready, pc=boot.SYM['START'])
    ready.cpu = cpu
    boot.run(cpu, lambda: cpu.pc == boot.SYM['V2_AUTO_TICK'])
    assert cpu.boot_waits == 0 and not ready.tx
    boot.run(cpu, lambda: cpu.pc == boot.SYM['V2_AUTO_TICK']
             and ready.ram[boot.SYM['V2_TICKS']] == 9, limit=500_000)
    assert ready.tx == b'.'
    ready.rx.extend(b'S')
    boot.hold(cpu)
    assert b'Canceled' in ready.tx and b'B3> ' in ready.tx
    late = boot.Memory(3, ft245_present=False)
    late.banks[3][0x6FF0:0x7000] = record
    late.banks[1][0x7FFC:0x7FFE] = b'\x00\x90'
    cpu = boot.MPU(memory=late, pc=boot.SYM['START'])
    late.cpu = cpu
    boot.run(cpu, lambda: cpu.pc == boot.SYM['V2_AUTO_TICK']
             and late.ram[boot.SYM['V2_TICKS']] == 5, limit=3_000_000)
    assert not late.tx and not late.acia_tx
    late.ft245_present = True
    boot.run(cpu, lambda: cpu.pc == 0x9000, limit=3_000_000)
    assert late.tx == b'.....'
    assert late.bank == 1 and not late.acia_tx
    assert not ({0x7F80, 0x7F81, 0x7F82, 0x7F83} & set(late.writes))
    blocked = boot.Memory(3, ft245_present=True)
    blocked.tx_blocked = True
    blocked.banks[3][0x6FF0:0x7000] = record
    blocked.banks[1][0x7FFC:0x7FFE] = b'\x00\x90'
    cpu = boot.MPU(memory=blocked, pc=boot.SYM['START'])
    blocked.cpu = cpu
    boot.run(cpu, lambda: cpu.pc == boot.SYM['V2_AUTO_TICK'])
    assert cpu.boot_waits == 0 and not blocked.tx
    start_cycles = cpu.processorCycles
    boot.run(cpu, lambda: cpu.pc == 0x9000, limit=4_000_000)
    window_cycles = cpu.processorCycles - start_cycles
    assert 8_000_000 <= window_cycles <= 8_900_000, window_cycles
    assert blocked.bank == 1
    assert not blocked.tx


def send(cpu, line):
    return flash.send(cpu, line, limit=15_000_000)


def call_sr(cpu, entry, request=0x2100):
    cpu.sp = 0xFF
    cpu.stPushWord(0x01FF)
    cpu.a, cpu.x = request & 255, request >> 8
    cpu.pc = entry
    boot.run(cpu, lambda: cpu.pc == 0x0200, limit=15_000_000)
    assert cpu.sp == 0xFF
    return bool(cpu.p & cpu.CARRY), cpu.a


def main(cold_start_check=check_cold_usb_start):
    cold_start_check()
    check_no_usb_autostart()
    cpu, mem = flash.boot_flash(3)
    original = bytes(range(32))
    mem.ram[0x2000:0x2020] = original
    mem.banks[3][0x0FE0] = 0x12
    mem.banks[3][0x1028] = 0x34
    out = send(cpu, b'S 3 8FF0 2000 201F TEST\r')
    assert b'Done' in out, out
    assert mem.banks[3][0x0FF0:0x0FF2] == b'SR'
    assert mem.banks[3][0x0FF3] == 0x3F
    assert mem.banks[3][0x1008:0x1028] == original
    assert mem.banks[3][0x0FE0] == 0x12 and mem.banks[3][0x1028] == 0x34
    assert not any(event[0] == 'erase' for event in mem.events)
    assert mem.bank == 3

    out = send(cpu, b'T 3\r')
    assert b'8FF0' in out and b'TEST' in out and b'2000-201F' in out, out
    mem.ram[0x2000:0x2020] = b'\x00' * 32
    out = send(cpu, b'R 3 8FF0\r')
    assert b'Done' in out and mem.ram[0x2000:0x2020] == original, out
    before = bytes(mem.banks[3])
    out = send(cpu, b'S 3 8FF0 2000 201F TEST\r')
    assert b'SR error 02' in out and bytes(mem.banks[3]) == before, out

    assert b'Protected' in send(cpu, b'F E800 00\r')
    assert b'Protected' in send(cpu, b'I E000 EFFF\r')
    assert bytes(mem.banks[3]) == before
    out = send(cpu, b'R 3 DFFF\r')
    assert b'SR error 04' in out, out
    mem.ram[0x2000:0x2020] = b'\x00' * 32
    mem.banks[3][0x0FF3] = 0x7F
    out = send(cpu, b'T 3\r')
    assert b'8FF0' in out and b' P ' in out, out
    out = send(cpu, b'R 3 8FF0\r')
    assert b'SR error 04' in out and mem.ram[0x2000:0x2020] == b'\x00' * 32

    cpu, mem = flash.boot_flash(3)
    mem.ram[0x2000:0x2020] = b'SR\x01\x3F' + bytes(range(28))
    mem.banks[2][0x123 + 24 + 31] = 0x00
    out = send(cpu, b'S 2 8123 2000 201F SIXTEENCHARLABEL\r')
    assert b'SR error 02' in out and not mem.events, out
    mem.banks[2][0x123 + 24 + 31] = 0xFF
    out = send(cpu, b'S 2 8123 2000 201F SIXTEENCHARLABEL\r')
    assert b'Done' in out and mem.bank == 3, out
    out = send(cpu, b'T 2\r')
    assert out.count(b'8123') == 1 and b'SIXTEENCHARLABEL' in out, out
    assert b'SR error 01' in send(cpu, b'S 2 8200 0100 0200\r')

    cpu, mem = flash.boot_flash(3)
    mem.ram[0x68FF] = 0xA5
    out = send(cpu, b'S 3 DFE7 68FF 68FF EDGE\r')
    assert b'Done' in out and mem.banks[3][0x5FFF] == 0xA5, out
    before = bytes(mem.banks[3])
    assert b'SR error 01' in send(cpu, b'S 3 DFE8 68FF 68FF\r')
    assert bytes(mem.banks[3]) == before
    mem.ram[0x68FF] = 0
    assert b'Done' in send(cpu, b'R 3 DFE7\r') and mem.ram[0x68FF] == 0xA5

    cpu, mem = flash.boot_flash(3)
    extension = bytes(mem.banks[3][0x6800:0x6F00])
    assert b'Done' in send(cpu, b'C 1 2 9000 0A\rY\r')
    assert b'Done' in send(cpu, b'C 0 3 F000 FF\rY\r')
    assert bytes(mem.banks[3][0x6800:0x6F00]) == extension

    cpu, mem = flash.boot_flash(3)
    mem.ram[0x2100:0x2117] = (bytes((3, 0x00, 0x82, 0x00, 0x20, 0x03, 0x20))
                              + b'API' + b'\x00' * 13)
    mem.ram[0x2000:0x2004] = b'CODE'
    assert call_sr(cpu, 0xE811) == (True, 0)
    mem.ram[0x2000:0x2004] = b'xxxx'
    assert call_sr(cpu, 0xE814) == (True, 0)
    assert mem.ram[0x2000:0x2004] == b'CODE' and mem.bank == 3

    cpu, mem = flash.boot_flash(3)
    mem.banks[3][0x6800:0x6F00] = b'\xff' * 0x700
    assert b'SR unavailable' in send(cpu, b'T 3\r')
    assert b'B3>' in bytes(mem.tx)

    carrier = (a23.ROOT / 'tools/v2-apps/str8n-v2-alpha21-b3-top-update-2000.a').read_text()
    carrier_bytes = bytes(int(value, 16)
                          for line in carrier.splitlines() if line.lstrip().startswith('DB ')
                          for value in re.findall(r'\$([0-9A-F]{2})', line))
    assert len(carrier_bytes) == 0x3000
    frozen_f = carrier_bytes[0x2000:0x3000]
    assert hashlib.sha256(frozen_f).hexdigest() == (
        '3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49')
    print('a23 S/R/T flash-model smoke checks passed')


if __name__ == '__main__':
    main()
