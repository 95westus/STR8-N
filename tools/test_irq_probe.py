"""Check linked IRQ probe success, timeout, and busy refusal before board use.

VIA registers are modeled; only board execution establishes hardware IRQ wiring.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'BUILD/v1.30/local/test-deps'))
from py65.devices.mpu65c02 import MPU

REL = ROOT / 'BUILD/v1.35'
STEM = 'str8n-v1.35-irq-test-2000'
symbols = {n: int(a, 16) for a, n in re.findall(
    r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
    (REL / f'map/{STEM}.map').read_text(), re.M)}

records = (REL / f's19/{STEM}.s19').read_text().splitlines()
assert records[-1] == 'S9032000DC', 'probe must execute at $2000'
for line in records:
    raw = bytes.fromhex(line[2:])
    assert len(raw) == raw[0] + 1 and sum(raw) & 255 == 255
    if line.startswith('S1'):
        address = int.from_bytes(raw[1:3], 'big')
        assert 0x2000 <= address and address + len(raw[3:-1]) <= 0x7B00


class Memory(list):
    def __init__(self):
        super().__init__([0] * 65536)
        self.writes = set()

    def __setitem__(self, address, value):
        if isinstance(address, int):
            self.writes.add(address)
        super().__setitem__(address, value)


for mode in ('irq', 'timeout', 'busy'):
    memory = Memory()
    memory[0xF000:] = (REL / 'bin/str8n-v1.35-bank3-f000-ffff.bin').read_bytes()
    for line in (REL / f's19/{STEM}.s19').read_text().splitlines():
        if line.startswith('S1'):
            raw = bytes.fromhex(line[2:])
            assert sum(raw) & 255 == 255
            address = int.from_bytes(raw[1:3], 'big')
            memory[address:address + len(raw[3:-1])] = raw[3:-1]
    memory[0x7EED:0x7EF0] = b'IVY'
    memory[0x7EFE:0x7F00] = bytes((0xE2, 0xF0))
    memory[0x7FCB] = 0x0C
    memory[0x7FC6:0x7FC8] = bytes((0x12, 0x34))
    memory[0x7FCE] = 0x80 | (1 if mode == 'busy' else 0)
    memory.writes.clear()
    cpu = MPU(memory=memory, pc=0x2000)
    output = bytearray()
    injected = False
    for step in range(400000):
        if cpu.pc == 0xF000:
            break
        if cpu.pc == 0xF019:
            output.append(cpu.a)
            cpu.pc = cpu.stPopWord() + 1
            continue
        if mode == 'irq' and not injected and cpu.pc == symbols['WAIT_IRQ']:
            memory[0x7FCD] = 0xC0
            cpu.irq()
            assert cpu.pc == 0xF0E3
            injected = True
        cpu.step()
    else:
        raise AssertionError(('probe did not return', mode))
    assert (b': PASS' in output) == (mode == 'irq'), output
    assert (b': FAIL' in output) == (mode == 'timeout'), output
    assert (b'REFUSE:' in output) == (mode == 'busy'), output
    assert memory[0x7EFE:0x7F00] == [0xE2, 0xF0]
    assert memory[0x7FCB] == 0x0C
    assert memory[0x7FC6:0x7FC8] == [0x12, 0x34]
    assert 0x7FEC not in memory.writes
    assert not any(address >= 0x8000 for address in memory.writes)
    print(mode, output.decode().strip(), 'cleanup/no flash or bank-latch writes PASS')
