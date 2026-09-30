"""Test the exact installed a22 to a24 F updater and B2:F recovery."""
import sys
import argparse
from pathlib import Path

import build_v2_a24 as a24
sys.modules['build_v2'] = a24
from test_worker_optimization import FlashMemory, MPU, PCR, LED, symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board_root', type=Path)
    args = parser.parse_args()
    candidate = (a24.OUT / f'{a24.STEM}-f000-ffff.bin').read_bytes()
    updater_root = args.board_root
    old = (a24.ROOT / 'BUILD/v2-alpha23/str8n-v2-alpha23-f000-ffff.bin').read_bytes()
    updater_name = 'str8n-v2-alpha24-b3-top-update-2000'
    updater_path = updater_root / f'{updater_name}.s19'
    updater, entry = a24.read_s19(updater_path)
    sym = symbols(updater_root / 'asm' / f'{updater_name}.map')
    assert entry == 0x2000
    assert bytes(updater[a] for a in range(0x4000, 0x5000)) == candidate
    assert bytes(updater[a] for a in range(0x5000, 0x6000)) == old
    mem = FlashMemory(b'')
    mem.ram[PCR], mem.ram[LED] = 0xEE, 0x01
    for address, value in updater.items():
        mem.ram[address] = value
    mem.banks[3][0x7000:] = old
    mem.banks[2][0x7000:] = b'\xff' * 4096
    cpu = MPU(memory=mem)

    def run(start, stop, recovery=False):
        cpu.pc, cpu.sp = sym[start], 0xFF
        for _ in range(3_000_000):
            if cpu.pc == sym[stop]:
                return
            assert 0x2000 <= cpu.pc < 0x4000, hex(cpu.pc)
            if recovery and cpu.pc in (sym['TU_PUTS'], sym['TU_READ_LINE']):
                if cpu.pc == sym['TU_READ_LINE']:
                    mem.ram[sym['TU_INPUT']:sym['TU_INPUT']+2] = b'O\0'
                cpu.pc = (cpu.stPopWord()+1) & 0xFFFF
            else:
                cpu.step()
        raise AssertionError(('instruction limit', hex(cpu.pc)))

    run('START', 'TU_PF_SUM_LO_OK')
    run('TU_BACKUP_CONFIRMED', 'TU_BACKUP_SUM_HI_OK')
    assert bytes(mem.banks[2][0x7000:]) == old
    backup_count = len(mem.mutations)
    run('TU_FINAL_CONFIRMED', 'TU_SUCCESS', recovery=True)
    assert bytes(mem.banks[3][0x7000:]) == candidate
    mem.banks[3][0x7000:] = b'\0' * 4096
    run('TU_RECOVERY', 'TU_ARM_SOFT_RESET', recovery=True)
    assert bytes(mem.banks[3][0x7000:]) == old
    assert all(bank == 3 and address >= 0xF000
               for _, bank, address, _ in mem.mutations[backup_count:])

    occupied = FlashMemory(b'')
    occupied.ram[PCR], occupied.ram[LED] = 0xEE, 0x01
    for address, value in updater.items():
        occupied.ram[address] = value
    occupied.banks[3][0x7000:] = old
    occupied.banks[2][0x7000:] = b'\xff' * 4096
    occupied.banks[2][0x7000] = 0x00
    blocked_cpu = MPU(memory=occupied)
    blocked_cpu.pc, blocked_cpu.sp = sym['START'], 0xFF
    for _ in range(300_000):
        if blocked_cpu.pc == sym['TU_PREFLIGHT_FAIL']:
            break
        blocked_cpu.step()
    else:
        raise AssertionError('occupied B2:F did not fail preflight')
    assert not occupied.mutations

    mem = FlashMemory(b'')
    mem.ram[PCR], mem.ram[LED] = 0xEE, 0x01
    for address, value in updater.items():
        mem.ram[address] = value
    mem.banks[3][0x7000:] = old
    mem.banks[3][0x7020] ^= 1
    cpu = MPU(memory=mem)
    cpu.pc, cpu.sp = sym['START'], 0xFF
    for _ in range(200_000):
        if cpu.pc == sym['TU_PREFLIGHT_FAIL']:
            break
        cpu.step()
    else:
        raise AssertionError('mismatched old F did not fail preflight')
    assert not mem.mutations
    print('PASS: old F gate, erased B2:F gate, backup, install, recovery, mismatch rejection')


if __name__ == '__main__':
    main()
