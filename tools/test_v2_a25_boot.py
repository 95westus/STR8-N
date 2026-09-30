"""Check a25 startup with absent E, absent RTC, and an advancing RTC."""
import json
import sys
import build_v2_a25 as build

sys.modules['build_v2'] = build
import test_v2_boot as boot

REPORT = json.loads((build.OUT / 'build.json').read_text())
RTC = REPORT['rtc_symbols']
ORIGINAL_STEP = boot.MPU.step

class Board(boot.Memory):
    rtc_samples = None
    rtc_reads = 0

    def __getitem__(self, address):
        if address == 0x7FCF and self.rtc_samples is not None:
            ddr = self.ram[0x7FC3]
            return (self.ram[address] & ddr) | (0x81 & ~ddr)
        return super().__getitem__(address)

def step(self):
    if self.pc == boot.REPORT['worker']['V2W_BOOT_DELAY']:
        self.boot_waits += 1
        self.processorCycles += 52_675_519
        self.pc = boot.REPORT['worker']['V2W_BOOT_DELAY_DONE']
        return
    if self.pc == RTC['RTREAD'] and self.memory.rtc_samples is not None:
        sample = self.memory.rtc_samples[min(self.memory.rtc_reads,
                                              len(self.memory.rtc_samples)-1)]
        self.memory.ram[RTC['RTCBUF']:RTC['RTCBUF']+7] = bytes(sample)
        self.memory.rtc_reads += 1
        self.p |= self.CARRY
        self.pc = (self.stPopWord() + 1) & 0xFFFF
        return
    if self.pc == RTC['RTC_WAIT1']:
        self.pc = RTC['RTC_WAIT2'] + 6
        return
    return ORIGINAL_STEP(self)

boot.MPU.step = step

def run(mode):
    memory = Board(3)
    if mode == 'erased':
        memory.banks[3][0x6000:0x6800] = b'\xff' * 0x800
    if mode == 'rtc':
        first = [0x89, 0x54, 0x17, 0x34, 0x30, 0x09, 0x26]
        next_second = first.copy(); next_second[0] = 0x90
        memory.rtc_samples = [first, next_second]
    cpu = boot.MPU(memory=memory, pc=boot.SYM['START'])
    memory.cpu = cpu
    cpu.p |= cpu.DECIMAL
    boot.hold(cpu)
    assert memory.ram[0x7FC3] == 0x5A
    return memory.tx

def main():
    for mode in ('erased', 'absent', 'rtc'):
        output = run(mode)
        heading = b'STR8-N 2.0a25 B3 65C02\r\nABI 65C02 | 816E | 816N-VEC\r\n'
        assert heading in output
        assert output.endswith(b'B3> ')
        if mode == 'rtc':
            assert (heading + b'EDU KIT       DETECTED\r\n'
                    b'  RTC         Wed 26-09-30 17:54:10\r\nB3> ') in output
        elif mode == 'absent':
            assert heading + b'EDU KIT       INCONCLUSIVE\r\nB3> ' in output
        else:
            assert b'EDU KIT' not in output
    import test_v2_flash as flash
    cpu, memory = flash.boot_flash(3)
    original = bytes(range(32))
    memory.ram[0x2000:0x2020] = original
    memory.rx.extend(b'S 3 8FF0 2000 201F TEST\r')
    boot.run(cpu, lambda: boot.waiting(cpu), limit=5_000_000)
    assert b'Done' in memory.tx
    assert memory.banks[3][0x0FF0:0x0FF2] == b'SR'
    memory.ram[0x2000:0x2020] = b'\x00' * 32
    memory.rx.extend(b'R 3 8FF0\r')
    boot.run(cpu, lambda: boot.waiting(cpu), limit=5_000_000)
    assert b'Done' in memory.tx and memory.ram[0x2000:0x2020] == original
    print('a25 startup: erased E, absent RTC, advancing RTC PASS')

if __name__ == '__main__':
    main()
