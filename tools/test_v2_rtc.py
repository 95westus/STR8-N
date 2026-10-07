"""Exercise the linked RTC machine code with a bit-level I2C/VIA model."""
import calendar
import hashlib
import json
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BUILD/v2-rtc-phase1'
for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS', 'PY65_PATH')
      for p in os.environ.get(key, '').split(os.pathsep) if p),
    *sorted((ROOT / 'BUILD').glob('v*/local/test-deps'), reverse=True),
]):
    if (directory / 'py65').is_dir():
        sys.path.insert(0, str(directory))
from py65.devices.mpu65c02 import MPU


class BusMemory:
    def __init__(self, *, present=True, stuck=None, rollover=False):
        self.ram = bytearray(65536)
        image = (OUT / 'rtc-service.bin').read_bytes()
        self.ram[0x3000:0x3000 + len(image)] = image
        self.regs = bytearray(32)
        self.regs[:9] = bytes([0xD8, 0x59, 0x23, 0x2A, 0x31, 0x12, 0x26, 0, 0])
        self.regs[0x18:0x20] = bytes([0x42, 0x10, 0x06, 0xAA, 0x43, 0x10, 0x06, 0xAA])
        self.present, self.stuck = present, stuck
        self.ddr, self.latch = 0x7E, 0x54
        self.initial_ddr, self.initial_latch = self.ddr, self.latch
        self.slave_low = False
        self.mode = 'idle'
        self.bit = self.value = self.pointer = 0
        self.phase = 'address'
        self.ack = False
        self.after_ack = 'rx'
        self.writes, self.accesses = [], []
        self.read_transactions = 0
        self.rollover = rollover

    def master_levels(self):
        return (~self.ddr | self.latch) & 0x81

    def __getitem__(self, address):
        if isinstance(address, slice):
            return self.ram[address]
        if address == 0x7FC3:
            return self.ddr
        if address == 0x7FCF:
            result = (self.latch & self.ddr) | (0x81 & ~self.ddr)
            if self.slave_low or self.stuck == 'sda':
                result &= ~0x80
            if self.stuck == 'scl':
                result &= ~1
            return result
        return self.ram[address]

    def __setitem__(self, address, value):
        if isinstance(address, slice):
            self.ram[address] = value
            return
        assert address < 0x8000, 'Service wrote flash'
        if address not in (0x7FC3, 0x7FCF):
            assert address < 0x7F00, f'Unexpected hardware write {address:04X}'
            self.ram[address] = value
            return
        old = self.master_levels()
        if address == 0x7FC3:
            self.ddr = value
        else:
            self.latch = value
        new = self.master_levels()
        if self.stuck:
            return
        if old & 1 and new & 1 and (old ^ new) & 0x80:
            if not new & 0x80:
                self.mode, self.phase, self.bit, self.value = 'rx', 'address', 0, 0
                self.slave_low = False
            else:
                self.mode = 'idle'
                self.slave_low = False
            return
        if not old & 1 and new & 1:
            self.rising(bool(new & 0x80))
        elif old & 1 and not new & 1:
            self.falling()

    def rising(self, sda):
        if self.mode == 'rx':
            self.value = (self.value << 1) | int(sda)
            self.bit += 1
            if self.bit == 8:
                value = self.value
                self.ack = self.present
                self.after_ack = 'rx'
                if self.phase == 'address':
                    self.accesses.append(value)
                    self.ack &= value in (0xDE, 0xDF)
                    if value == 0xDF:
                        self.after_ack = 'tx'
                        self.read_transactions += 1
                        if self.rollover and self.read_transactions % 2 == 0:
                            self.regs[0] ^= 1
                    self.phase = 'pointer'
                elif self.phase == 'pointer':
                    self.pointer = value
                    self.phase = 'data'
                    self.ack &= self.pointer < 32
                elif self.ack:
                    assert self.pointer < 32, 'Service accessed SRAM'
                    self.writes.append((self.pointer, value))
                    self.regs[self.pointer] = value
                    if self.pointer == 0:
                        self.regs[3] = (self.regs[3] & ~0x20) | (0x20 if value & 0x80 else 0)
                    if self.pointer == 3:
                        self.regs[3] = (value & ~0x30) | (0x20 if self.regs[0] & 0x80 else 0)
                        self.regs[0x18:0x20] = bytes(8)
                    self.pointer += 1
                self.mode = 'rx-ack-prep'
        elif self.mode == 'rx-ack':
            self.mode = 'rx-ack-done'
        elif self.mode == 'tx':
            self.bit += 1
        elif self.mode == 'tx-ack':
            self.ack = not sda
            self.mode = 'tx-ack-done'

    def falling(self):
        if self.mode == 'rx-ack-prep':
            self.slave_low = self.ack
            self.mode = 'rx-ack'
        elif self.mode == 'rx-ack-done':
            self.slave_low = False
            self.mode = self.after_ack if self.ack else 'idle'
            self.bit = self.value = 0
            if self.mode == 'tx':
                self.slave_low = not bool(self.regs[self.pointer] & 0x80)
        elif self.mode == 'tx':
            if self.bit == 8:
                self.slave_low = False
                self.mode = 'tx-ack'
            else:
                self.slave_low = not bool(self.regs[self.pointer] & (0x80 >> self.bit))
        elif self.mode == 'tx-ack-done':
            self.pointer += 1
            self.bit = 0
            self.mode = 'tx' if self.ack else 'idle'
            self.slave_low = self.ack and not bool(self.regs[self.pointer] & 0x80)


def call(memory, entry=0x3004, flags=0x20, expected=None, limit=2000000):
    cpu = MPU(memory=memory, pc=entry)
    cpu.p = flags
    cpu.sp = 0xFD
    cpu.stPushWord(0x01FF)
    for steps in range(limit):
        if cpu.pc == 0x0200:
            break
        cpu.step()
    else:
        raise AssertionError(f'Unbounded service call at {cpu.pc:04X}')
    assert cpu.p & 0x0C == flags & 0x0C, 'I/D flags not restored'
    assert memory.ddr == memory.initial_ddr, 'VIA DDRA not restored'
    assert memory.latch & memory.ddr == memory.initial_latch & memory.ddr, 'Driven VIA outputs changed'
    assert all(a in (0xDE, 0xDF) for a in memory.accesses), 'EEPROM address accessed'
    if expected is not None:
        assert cpu.a == expected, (cpu.a, expected, hex(cpu.pc))
        assert bool(cpu.p & 1) == (expected == 0), 'Carry/status mismatch'
    return cpu.a, steps


def bcd(number):
    return number // 10 * 16 + number % 10


def request(memory, year=2026, month=10, day=6, hour=12, minute=34, second=56):
    memory.ram[0x3F20:0x3F28] = bytes([year & 255, year >> 8, month, day, 2, hour, minute, second])
    memory.ram[0x3F29:0x3F2B] = b'ST'


def main():
    checked = []
    m = BusMemory()
    call(m, expected=0)
    assert m.ram[0x3F02:0x3F0A] == bytes([0xEA, 7, 12, 31, 2, 23, 59, 58])
    assert m.ram[0x3F01] == 0x37
    assert not m.writes
    checked.append('bit-level positive read, decoded calendar, VIA and I/D preservation')
    for flags in (0x20, 0x24, 0x28, 0x2C):
        call(BusMemory(), flags=flags, expected=0)
    for options, error in [({'present': False}, 2), ({'stuck': 'sda'}, 1), ({'stuck': 'scl'}, 1), ({'rollover': True}, 7)]:
        m = BusMemory(**options)
        call(m, expected=error)
        assert not m.writes
    checked.append('absent device, both stuck lines, bounded unstable snapshot')
    # A clock held low only after initialization exercises bounded clock waits.
    m = BusMemory()
    symbols = json.loads((OUT / 'build.json').read_text())['images']['rtc-service']['symbols']
    original = m.__class__.__getitem__
    class Stretch(BusMemory):
        def __getitem__(self, address):
            if address == 0x7FCF and self.mode != 'idle':
                return original(self, address) & ~1
            return original(self, address)
    call(Stretch(), expected=3)
    checked.append('clock timeout during transaction')
    for year in (2000, 2001, 2024, 2047, 2048, 2099):
        for month in range(1, 13):
            m = BusMemory()
            day = calendar.monthrange(year, month)[1]
            m.regs[4:7] = bytes([bcd(day), bcd(month), bcd(year % 100)])
            call(m, expected=0)
            assert int.from_bytes(m.ram[0x3F02:0x3F04], 'little') == year
            m.regs[4] = bcd(day + 1)
            call(m, expected=4)
    for value in (0x1A, 0x60, 0x7F):
        m = BusMemory(); m.regs[0] = 0x80 | value
        call(m, expected=4)
    for hour, binary in [(0x52, 0), (0x72, 12), (0x61, 13), (0x51, 11)]:
        m = BusMemory(); m.regs[2] = hour
        call(m, expected=0)
        assert m.ram[0x3F07] == binary
    m = BusMemory(); m.regs[0] &= 0x7F; m.regs[3] &= ~0x20
    call(m, expected=4); call(m, entry=0x3007, expected=0)
    checked.append('calendar bounds, leap years, century range, BCD, 12/24h, stopped-clock status')
    m = BusMemory(); m.regs[3] |= 0x10
    evidence = bytes(m.regs[0x18:0x20])
    call(m, expected=0)
    assert m.regs[3] & 0x10 and not m.writes
    assert m.ram[0x3F30:0x3F38] == evidence
    call(m, entry=0x300D, expected=6)
    assert not m.writes
    m.ram[0x3F29:0x3F2B] = b'PA'
    call(m, entry=0x300D, expected=0)
    assert not m.regs[3] & 0x10 and m.regs[3] & 8
    assert m.ram[0x3F30:0x3F38] == evidence
    assert m.writes == [(3, 0x0A)]
    assert m.ram[0x3F29:0x3F2B] == bytes(2)
    checked.append('power-fail read has no side effects; explicit ACK captures evidence and retains backup enable')
    for year in (2000, 2047, 2048, 2099):
        m = BusMemory(); m.regs[3] |= 0x10
        request(m, year=year)
        call(m, entry=0x300A, expected=0)
        assert m.regs[:7] == bytes([0xD6, 0x34, 0x12, 0x2A, 0x06, 0x10, bcd(year % 100)])
        assert m.ram[0x3F30:0x3F38] != bytes(8)
        assert all(a <= 6 for a, v in m.writes)
    for changes in [dict(year=1999), dict(year=2100), dict(month=0), dict(month=13), dict(day=0), dict(day=32), dict(hour=24), dict(minute=60), dict(second=60), dict(year=2001, month=2, day=29)]:
        m = BusMemory(); request(m, **changes)
        call(m, entry=0x300A, expected=4)
        assert not m.writes
    m = BusMemory(); request(m); m.regs[7] = 0x10
    call(m, entry=0x300A, expected=5); assert not m.writes
    m = BusMemory(); call(m, entry=0x300A, expected=6); assert not m.accesses
    m = BusMemory(); m.ram[symbols['BUSY']] = 1
    call(m, expected=8); assert not m.accesses
    checked.append('guarded SET, full-year boundaries, request validation, alarm refusal, reentrancy refusal')
    result = dict(passed=True, service_sha256=hashlib.sha256((OUT / 'rtc-service.bin').read_bytes()).hexdigest(),
                  checks=checked, positive_i2c_transactions_emulated=True, physical_hardware_tested=False)
    (OUT / 'test-results.json').write_text(json.dumps(result, indent=2) + '\n')
    for item in checked:
        print('PASS', item)


if __name__ == '__main__':
    main()
