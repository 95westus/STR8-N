"""Exercise board-2609 exact-image B3:E updater against the flash model."""
import argparse
from pathlib import Path
import sys

import build_v2_a24 as firmware

sys.modules['build_v2'] = firmware
import test_v2_a24_console  # patches the FT245-only startup delay in the model
import test_v2_boot as boot
import test_v2_flash as flash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('updater_s19', type=Path)
    parser.add_argument('staged_e', type=Path)
    args = parser.parse_args()
    new = args.staged_e.read_bytes()
    updater, entry = firmware.read_s19(args.updater_s19)
    assert len(new) == 4096 and entry == 0x2000

    def setup(mismatch=False):
        cpu, memory = flash.boot_flash(3)
        memory.banks[3][0x6000:0x7000] = bytes(4096)
        if mismatch:
            memory.banks[3][0x6800] = 1
        for address, value in updater.items():
            memory.ram[address] = value
        cpu.pc, cpu.sp = entry, 0xFF
        return cpu, memory

    cpu, memory = setup()
    before_b0 = bytes(memory.banks[0])
    before_b2 = bytes(memory.banks[2])
    before_f = bytes(memory.banks[3][0x7000:])
    boot.run(cpu, lambda: b'TYPE Y to repair>' in memory.tx, limit=2_000_000)
    assert not memory.events
    memory.rx.append(ord('Y'))
    boot.run(cpu, lambda: cpu.pc == 0xF004, limit=15_000_000)
    assert bytes(memory.banks[3][0x6000:0x7000]) == new
    assert bytes(memory.banks[3][0x7000:]) == before_f
    assert bytes(memory.banks[0]) == before_b0
    assert bytes(memory.banks[2]) == before_b2
    assert any(event[0] == 'erase' and event[1:3] == (3, 0xE000)
               for event in memory.events)
    assert all(event[1] == 3 and 0xE000 <= event[2] <= 0xEFFF
               for event in memory.events)
    cpu, memory = setup(mismatch=True)
    boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
    assert b'OLD IMAGE MISMATCH' in memory.tx and not memory.events
    cpu, memory = setup()
    boot.run(cpu, lambda: b'TYPE Y to repair>' in memory.tx, limit=2_000_000)
    memory.rx.append(ord('N'))
    boot.run(cpu, lambda: cpu.pc == 0xF007, limit=100_000)
    assert not memory.events
    print('PASS: exact old E gate, verified B3:E install, mismatch/cancel refusal, B0/B2/F unchanged')


if __name__ == '__main__':
    main()
