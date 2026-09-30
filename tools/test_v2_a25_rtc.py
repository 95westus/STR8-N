"""Run linked a25 RTC code with positive snapshots and absent-bus paths."""
import json
import os
import sys
from pathlib import Path

import build_v2_a25 as build
for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS', 'PY65_PATH')
      for p in os.environ.get(key, '').split(os.pathsep) if p),
    *sorted((build.ROOT / 'BUILD').glob('v*/local/test-deps'), reverse=True),
]):
    if (directory / 'py65').is_dir():
        sys.path.insert(0, str(directory))
from py65.devices.mpu65c02 import MPU

REPORT = json.loads((build.OUT / 'build.json').read_text())
S = REPORT['rtc_symbols']
IMAGE = (build.OUT / f'{build.STEM}-e000-ffff.bin').read_bytes()

class Memory(list):
    def __init__(self, pins):
        super().__init__([0] * 65536)
        super().__setitem__(slice(0xE000, 0x10000), IMAGE)
        super().__setitem__(slice(0x7E60, 0x7E64), b'RA\x01\x0d')
        super().__setitem__(0x7FC3, 0x36)
        super().__setitem__(0x7FCF, 0x24)
        self.pins = pins
        self.writes = []

    def __getitem__(self, address):
        if address == 0x7FCF:
            ddr = super().__getitem__(0x7FC3)
            return (super().__getitem__(address) & ddr) | (self.pins & ~ddr)
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if isinstance(address, int):
            self.writes.append((address, value))
            if address >= 0xE000:
                raise AssertionError(f'ROM write: {address:04X}')
        super().__setitem__(address, value)

def ret(cpu):
    cpu.pc = (cpu.stPopWord() + 1) & 0xFFFF

def run(samples=None, pins=0x81):
    memory = Memory(pins)
    cpu = MPU(memory=memory, pc=S['RTC_ENTRY'])
    cpu.stPushWord(0x3FFF)
    output = bytearray()
    reads = 0
    for _ in range(125_000):
        if cpu.pc == 0x4000:
            break
        if cpu.pc == 0x7E6D:
            output.append(cpu.a)
            ret(cpu)
        elif cpu.pc == 0x7E7F:
            output.extend(b'\r\n')
            ret(cpu)
        elif cpu.pc == S['RTREAD'] and samples is not None:
            sample = samples[min(reads, len(samples)-1)]
            memory[S['RTCBUF']:S['RTCBUF']+7] = sample
            cpu.p |= 1
            reads += 1
            ret(cpu)
        elif cpu.pc == S['RTC_WAIT1']:
            cpu.pc = S['RTC_WAIT2'] + 6
        else:
            cpu.step()
    else:
        raise AssertionError('RTC extension did not return')
    assert memory[0x7FC3] == 0x36
    assert memory[0x7FCF] & 0x36 == 0x24
    return output.decode(), reads

def main():
    good = [0x89, 0x54, 0x17, 0x34, 0x30, 0x09, 0x26]
    advanced = good.copy(); advanced[0] = 0x90
    assert run([good, advanced])[0] == (
        '\r\nEDU KIT       DETECTED\r\n  RTC         Wed 26-09-30 17:54:10')
    assert run([good])[0] == '\r\nEDU KIT       INCONCLUSIVE'
    invalid = good.copy(); invalid[4] = 0
    assert run([invalid])[0] == '\r\nEDU KIT       INCONCLUSIVE'
    bad_dow = good.copy(); bad_dow[3] &= 0xF8
    assert run([bad_dow, advanced])[0] == '\r\nEDU KIT       INCONCLUSIVE'
    stopped = good.copy(); stopped[3] &= ~0x20
    assert run([stopped])[0] == '\r\nEDU KIT       INCONCLUSIVE'
    for hour, expected in [(0x41, '01'), (0x52, '00'),
                           (0x61, '13'), (0x72, '12')]:
        sample = good.copy(); sample[2] = hour
        next_sample = sample.copy(); next_sample[0] = 0x90
        assert f'  RTC         Wed 26-09-30 {expected}:54:10' in run([sample, next_sample])[0]
    leap = good.copy(); leap[3] = 0x35; leap[4:7] = [0x29, 0x02, 0x24]
    leap_next = leap.copy(); leap_next[0] = 0x90
    assert '  RTC         Thu 24-02-29' in run([leap, leap_next])[0]
    for dow, name in enumerate(('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'), 1):
        sample = good.copy(); sample[3] = (sample[3] & 0xF8) | dow
        next_sample = sample.copy(); next_sample[0] = 0x90
        assert f'  RTC         {name} 26-09-30' in run([sample, next_sample])[0]
    assert run(pins=0x81)[0] == '\r\nEDU KIT       INCONCLUSIVE'  # NACK
    for pins in (0, 0x80, 1):
        assert run(pins=pins)[0] == '\r\nEDU KIT       INCONCLUSIVE'
    print('a25 RTC extension: display, 12/24h, invalid, stopped, absent bus PASS')

if __name__ == '__main__':
    main()
