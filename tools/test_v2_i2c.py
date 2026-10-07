"""Exercise public shared-I2C machine code with RTC and a second slave model."""
import hashlib
import json

from test_v2_rtc_split import Memory, META, OUT, call


class Devices(Memory):
    def __init__(self, *, rtc_present=True, nack_data=None, nack_read_address=False,
                 stretch=False, **kwargs):
        super().__init__(**kwargs)
        self.rtc_regs = self.regs
        self.other_regs = bytearray(range(256))
        self.devices = {0x3C: self.other_regs}
        if rtc_present:
            self.devices[0x6F] = self.rtc_regs
        self.selected = None
        self.nack_data = nack_data
        self.nack_read_address = nack_read_address
        self.stretch = stretch
        self.data_received = 0
        self.starts = self.stops = 0

    def __getitem__(self, address):
        value = super().__getitem__(address)
        if address == 0x7FCF and self.stretch and self.mode != 'idle':
            return value & ~1
        return value

    def __setitem__(self, address, value):
        old = self.master_levels() if address in (0x7FC3, 0x7FCF) else None
        super().__setitem__(address, value)
        if old is not None:
            new = self.master_levels()
            if old & 1 and new & 1 and (old ^ new) & 0x80:
                if new & 0x80:
                    self.stops += 1
                else:
                    self.starts += 1

    def rising(self, sda):
        if self.mode != 'rx':
            return super().rising(sda)
        self.value = self.value << 1 | int(sda)
        self.bit += 1
        if self.bit != 8:
            return
        value = self.value
        self.ack = self.selected in self.devices
        self.after_ack = 'rx'
        if self.phase == 'address':
            self.accesses.append(value)
            self.selected = value >> 1
            self.ack = self.selected in self.devices
            if self.ack:
                self.regs = self.devices[self.selected]
            if value & 1:
                self.ack &= not self.nack_read_address
                self.after_ack = 'tx'
                self.read_transactions += 1
            self.phase = 'pointer'
            self.data_received = 0
        elif self.phase == 'pointer':
            self.pointer = value
            self.phase = 'data'
            self.data_received += 1
            self.ack &= self.nack_data != self.data_received
            if self.ack:
                self.ack &= self.pointer < len(self.regs)
        else:
            self.data_received += 1
            self.ack &= self.nack_data != self.data_received
            if self.ack:
                assert self.pointer < len(self.regs)
                self.writes.append((self.selected, self.pointer, value))
                self.regs[self.pointer] = value
                if self.selected == 0x6F and self.pointer == 0:
                    self.regs[3] = self.regs[3] & ~0x20 | (0x20 if value & 0x80 else 0)
                if self.selected == 0x6F and self.pointer == 3:
                    self.regs[3] = value & ~0x30 | (0x20 if self.regs[0] & 0x80 else 0)
                    self.regs[0x18:0x20] = bytes(8)
                self.pointer = (self.pointer + 1) % len(self.regs)
        self.mode = 'rx-ack-prep'

    def falling(self):
        if self.mode == 'tx-ack-done' and self.selected == 0x3C:
            self.pointer = (self.pointer + 1) & 255
            self.bit = 0
            self.mode = 'tx' if self.ack else 'idle'
            self.slave_low = self.ack and not bool(self.regs[self.pointer] & 0x80)
            return
        super().falling()


def request(m, addr=0x3C, write=b'', read=0, flags=1, wp=0x20FE, rp=0x22FE):
    if 0x0200 <= wp and wp + len(write) <= 0x6500:
        m.ram[wp:wp+len(write)] = write
    m.ram[0x6650:0x6658] = bytes([addr, flags, wp & 255, wp >> 8, len(write),
                                 rp & 255, rp >> 8, read])


def transfer(m, error=0, **options):
    call(m, entry=0x6514, expected=error, **options)
    assert m.ram[0x6658] == error
    return tuple(m.ram[0x6659:0x665C])


def main():
    for name in ('provider', 'gateway'):
        assert hashlib.sha256((OUT / f'{name}.bin').read_bytes()).hexdigest() == META[f'{name}_sha256']
    checks = []
    for bank in range(4):
        m = Devices(caller_bank=bank, rtc_present=False)
        assert m.ram[0x6510:0x6514] == b'I2\x01\x01'
        request(m, write=b'\x10\xAA\xBB')
        assert transfer(m, flags=0x28)[:2] == (3, 0)
        assert m.other_regs[0x10:0x12] == b'\xAA\xBB'
        request(m, write=b'\x10', read=4)
        assert transfer(m, inject_nmi=True)[:2] == (1, 4)
        assert m.ram[0x22FE:0x2302] == b'\xAA\xBB\x12\x13'
        assert all(v >> 1 == 0x3C for v in m.accesses)
    checks.append('second device works with RTC absent, all caller banks, page-crossing buffers and NMI')
    for mode in (0, 1):
        m = Devices(); request(m, write=b'\x30', read=3, flags=mode)
        assert transfer(m)[:2] == (1, 3)
        assert m.ram[0x22FE:0x2301] == b'\x30\x31\x32'
        assert m.starts == 2 and m.stops == (2 if mode == 0 else 1)
    m = Devices(); m.pointer = 0x40; request(m, read=4)
    assert transfer(m)[:2] == (0, 4)
    assert m.ram[0x22FE:0x2302] == b'\x40\x41\x42\x43'
    m = Devices(); request(m, write=b'\xC0', read=64, rp=0x64C0)
    assert transfer(m)[:2] == (1, 64)
    assert m.ram[0x64C0:0x6500] == bytes(range(0xC0, 0x100))
    checks.append('write/read/combined transfers, repeated START or STOP/start, 64-byte upper RAM boundary')
    m = Devices(nack_data=3); request(m, write=b'\x10\xAA\xBB')
    assert transfer(m, 2) == (2, 0, 2)
    assert m.other_regs[0x10:0x12] == b'\xAA\x11'
    m = Devices(nack_read_address=True); request(m, write=b'\x10', read=4)
    assert transfer(m, 2) == (1, 0, 3)
    m = Devices(); request(m, addr=0x3D, write=b'\0')
    assert transfer(m, 2) == (0, 0, 1)
    m = Devices(stretch=True); request(m, write=b'\0', read=1)
    assert transfer(m, 3) == (0, 0, 1)
    checks.append('address/data NACK, partial write counts, read-address failure and bounded clock timeout')
    invalid = [dict(addr=0), dict(addr=0x78), dict(flags=2), dict(write=b'', read=0),
               dict(write=bytes(65)), dict(read=65), dict(wp=0x100),
               dict(wp=0x64FF, write=b'12'), dict(rp=0x6500), dict(rp=0x7F00)]
    for change in invalid:
        m = Devices()
        args = dict(write=b'\0', read=1); args.update(change)
        request(m, **args)
        assert transfer(m, 9) == (0, 0, 0)
        assert not m.accesses
    checks.append('invalid addresses/flags/empty requests/counts and protected, stack or I/O buffer ranges rejected')
    for write, read, mode in [(b'\0\x80', 0, 1), (b'\x20', 1, 1), (b'\x1F', 2, 1), (b'\0', 1, 0), (b'', 1, 1)]:
        m = Devices(); request(m, addr=0x6F, write=write, read=read, flags=mode)
        assert transfer(m, 6) == (0, 0, 0)
        assert not m.accesses
    m = Devices(); request(m, addr=0x57, write=b'\0', read=1)
    assert transfer(m, 6) == (0, 0, 0) and not m.accesses
    m = Devices(); m.rtc_regs[3] |= 0x10
    before = bytes(m.rtc_regs); request(m, addr=0x6F, write=b'\0', read=9)
    assert transfer(m)[:2] == (1, 9)
    assert m.ram[0x22FE:0x2307] == before[:9] and bytes(m.rtc_regs) == before
    checks.append('managed RTC writes/memory denied; permitted RTC register read preserves outage evidence')
    m = Devices(); m.rtc_regs[3] |= 0x10
    request(m, write=b'\x10', read=2)
    transfer(m)
    call(m, expected=0)
    assert m.rtc_regs[3] & 0x10 and m.ram[0x66DC] == 1
    request(m, write=b'\x20', read=2)
    assert transfer(m)[:2] == (1, 2)
    assert m.ram[0x22FE:0x2300] == b'\x20\x21'
    checks.append('I2C-first activation and alternating RTC/other-device calls share state without consuming outage')
    m = Devices(); request(m, write=b'\0', read=1)
    m.ram[0x6660] = 1
    call(m, entry=0x6514, expected=8)
    assert not m.accesses and not m.mapping_events
    m = Devices(); m.banks[3][0] = 255
    m.ram[0x6659:0x665C] = b'\xFF' * 3
    request(m, write=b'\0', read=1)
    assert transfer(m, 0x80) == (0, 0, 0)
    checks.append('shared busy guard and unavailable extension leave no false partial progress')
    report = dict(passed=True, checks=checks, provider_sha256=META['provider_sha256'],
                  gateway_sha256=META['gateway_sha256'], physical_hardware_tested=False,
                  second_slave_is_a_model=True)
    (OUT / 'i2c-test-results.json').write_text(json.dumps(report, indent=2) + '\n')
    for item in checks:
        print('PASS', item)


if __name__ == '__main__':
    main()
