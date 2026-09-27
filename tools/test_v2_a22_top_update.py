"""Run the exact-a21 to a22 B3:F updater and B2:F recovery in the flash model."""
import sys
import argparse

import build_v2_a22 as a22
sys.modules['build_v2'] = a22
from test_worker_optimization import FlashMemory, MPU, PCR, LED, symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair', action='store_true',
                        help='exercise the exact installed-a22 to corrected-a22 updater')
    parser.add_argument('--dot', action='store_true',
                        help='exercise the exact paired a22 autostart-dot update')
    args = parser.parse_args()
    candidate = (a22.OUT / f'{a22.STEM}-f000-ffff.bin').read_bytes()
    if args.dot:
        updater_root = a22.ROOT / 'BUILD/v2-alpha22-dot-update'
        old = (updater_root / 'old-f.bin').read_bytes()
        updater_name = 'str8n-v2-alpha22-dot-f-update-2000'
    elif args.repair:
        old = (a22.ROOT / 'output/qualification/board-com3-a22-sr-2026-09-26/'
               'bank3-ef-after-a22.bin').read_bytes()[-4096:]
        candidate = (a22.ROOT / 'output/qualification/'
                     'board-com3-a22-cold-start-repair-2026-09-26/'
                     'b3-ef-final.bin').read_bytes()[-4096:]
        updater_root = a22.ROOT / 'BUILD/v2-alpha22-reset-fix'
        updater_name = 'str8n-v2-alpha22-cold-start-repair-2000'
    else:
        old = (a22.ROOT / 'BUILD/v2-alpha21/str8n-v2-alpha21-e000-ffff.bin').read_bytes()[-4096:]
        updater_root = a22.OUT
        updater_name = f'{a22.STEM}-b3-top-update-2000'
    updater_path = updater_root / f'{updater_name}.s19'
    updater, entry = a22.read_s19(updater_path)
    sym = symbols(updater_root / 'asm' / f'{updater_name}.map')
    assert entry == 0x2000
    assert bytes(updater[a] for a in range(0x4000, 0x5000)) == candidate
    assert bytes(updater[a] for a in range(0x5000, 0x6000)) == old
    mem = FlashMemory(b'')
    mem.ram[PCR], mem.ram[LED] = 0xEE, 0x01
    for address, value in updater.items():
        mem.ram[address] = value
    mem.banks[3][0x7000:] = old
    mem.banks[2][0x7000:] = b'\xa5' * 4096
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
    print('PASS: exact old F gate, B2:F backup, a22 F install, recovery, mismatch rejection'
          + (' (dot update)' if args.dot else
             ' (cold-start repair)' if args.repair else ' (initial install)'))


if __name__ == '__main__':
    main()
