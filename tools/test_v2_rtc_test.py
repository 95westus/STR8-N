"""Execute the assembled probe with RTC/console boundary models.

Real bus routines run for absent/stuck bus cases. Positive cases inject
register snapshots at RTREAD; these do not qualify physical I2C timing.
"""
import json
import os
import sys
from pathlib import Path
from build_v2_rtc_test import OUT, NAME
for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS', 'PY65_PATH')
      for p in os.environ.get(key, '').split(os.pathsep) if p),
    *sorted((OUT.parent).glob('v*/local/test-deps'), reverse=True),
]):
    if (directory / 'py65').is_dir():
        sys.path.insert(0, str(directory))
from py65.devices.mpu65c02 import MPU

REPORT = json.loads((OUT / 'build.json').read_text())
S = REPORT['symbols']
IMAGE = (OUT / (NAME + '.bin')).read_bytes()

class Memory(list):
    def __init__(self, pins=0x81):
        super().__init__([0] * 65536)
        self.pins = pins
        self.writes = []
        self[0x2000:0x2000 + len(IMAGE)] = IMAGE
        self[0x7E60:0x7E64] = b'RA\x01\x0d'
        self[0x7FC3] = 0x36
        self[0x7FCF] = 0x24

    def __getitem__(self, key):
        if key == 0x7FCF:
            ddr = super().__getitem__(0x7FC3)
            return (super().__getitem__(key) & ddr) | (self.pins & ~ddr)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.writes.append((key, value))
        super().__setitem__(key, value)

def ret(cpu):
    cpu.pc = (cpu.stPopWord() + 1) & 65535

def run(samples=None, pins=0x81, byte_bus=False):
    mem = Memory(pins)
    cpu = MPU(memory=mem, pc=0x2000)
    output = bytearray()
    reads = 0
    transmitted, acknowledgements = [], []
    byte_index = 0
    for _ in range(100_000):
        if cpu.pc == 0x7E67:
            break
        if cpu.pc == 0x7E6D:
            output.append(cpu.a)
            ret(cpu)
        elif cpu.pc == 0x7E7C:
            output.extend(f'{cpu.a:02X}'.encode())
            ret(cpu)
        elif cpu.pc == 0x7E7F:
            output.extend(b'\r\n')
            ret(cpu)
        elif byte_bus and cpu.pc == S['I2WRITE']:
            transmitted.append(cpu.a)
            cpu.p |= 1
            ret(cpu)
        elif byte_bus and cpu.pc == S['I2READ']:
            sample = samples[min(reads, len(samples) - 1)]
            acknowledgements.append(cpu.y)
            cpu.a = sample[byte_index]
            byte_index += 1
            if byte_index == 7:
                byte_index = 0
                reads += 1
            ret(cpu)
        elif cpu.pc == S['RTREAD'] and samples is not None and not byte_bus:
            sample = samples[min(reads, len(samples) - 1)]
            mem[S['RTCBUF']:S['RTCBUF']+7] = sample
            reads += 1
            cpu.p |= 1
            ret(cpu)
        elif cpu.pc == S['WAIT1']:
            # Skip the fixed delay, leaving the bounded poll count intact.
            cpu.pc = S['WAIT2'] + 6
        else:
            cpu.step()
    else:
        raise AssertionError('probe did not return within bound')
    assert mem[0x7FC3] == 0x36
    assert mem[0x7FCF] & 0x36 == 0x24
    assert all(a < 0x7000 or a in (0x7FC3, 0x7FCF, 0x7E60, 0x7E61,
                                  0x7E62, 0x7E63) for a, _ in mem.writes)
    if byte_bus:
        assert transmitted == [0xDE, 0, 0xDF] * reads
        assert acknowledgements == [0, 0, 0, 0, 0, 0, 1] * reads
    return output.decode(), reads

def main():
    good = [0x89, 0x35, 0x14, 0x23, 0x30, 0x09, 0x26]
    next_second = [0x90, *good[1:]]
    out, _ = run([good, next_second])
    assert '26-09-30  TIME 14:35:09' in out and 'EDU detected' in out
    assert 'EDU detected' in run([good, next_second], byte_bus=True)[0]
    out, count = run([good])
    assert 'inconclusive' in out and count == 81
    for field, value in [(0, 0), (1, 0x6A), (2, 0x24), (3, 0),
                         (4, 0), (4, 0x31), (5, 0), (5, 0x1A), (6, 0xFA)]:
        invalid = good.copy()
        invalid[field] = value
        out, count = run([invalid])
        assert 'inconclusive' in out and 'EDU detected' not in out
    for hour in (0x41, 0x52, 0x61, 0x72):
        a = good.copy(); a[2] = hour
        b = a.copy(); b[0] = 0x90
        out, _ = run([a, b])
        assert 'EDU detected' in out and ('AM' in out or 'PM' in out)
    for year, accepted in [(0x24, True), (0x26, False), (0x00, True)]:
        a = good.copy(); a[4:7] = [0x29, 0x02, year]
        b = a.copy(); b[0] = 0x90
        out, _ = run([a, b])
        assert ('EDU detected' in out) == accepted
    a = good.copy(); a[0] = 0xD9
    b = good.copy(); b[0] = 0x80; b[1] = 0x36
    assert 'EDU detected' in run([a, b])[0]
    assert 'inconclusive' in run([[0]*7])[0]
    assert 'inconclusive' in run([[255]*7])[0]
    for pins, error in [(0x81, '02'), (0, '01'), (0x80, '01'), (1, '01')]:
        assert f'error ${error}' in run(pins=pins)[0]
    print('RTC probe: validation, 12/24h, rollover, stopped, absent and stuck bus PASS')
    (OUT / 'test-results.json').write_text(json.dumps({
        'sha256': REPORT['sha256'], 'host_checks_passed': True,
        'physical_hardware_tested': False,
        'positive_i2c_transactions_emulated': False,
    }, indent=2) + '\n')

if __name__ == '__main__':
    main()
