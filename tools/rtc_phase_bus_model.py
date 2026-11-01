"""Bit-level VIA/I2C model retained from test_v2_rtc.BusMemory.

The phase tests load their own image; no historical service binary is needed.
"""

class BusMemory:
    def __init__(self, *, present=True, stuck=None, rollover=False):
        self.ram = bytearray(65536)
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
