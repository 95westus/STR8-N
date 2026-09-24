"""Check the clean B3 image and execute its guarded top updater in the flash model."""
from pathlib import Path

from build_v2 import OUT, STEM, read_s19
from test_worker_optimization import FlashMemory, MPU, PCR, LED, symbols


def main():
    full = (OUT / f'{STEM}-8000-ffff.bin').read_bytes()
    ef = (OUT / f'{STEM}-e000-ffff.bin').read_bytes()
    assert len(full) == 0x8000
    assert full[:0x6000] == b'\xff' * 0x6000
    assert full[0x6000:] == ef
    assert full[0x7000:0x7004] == b'SN\x02\x00'
    assert full[-4:-2] == b'\x04\xf0'

    updater_path = OUT / f'{STEM}-b3-top-update-2000.s19'
    updater, entry = read_s19(updater_path)
    assert entry == 0x2000
    sym = symbols(OUT / 'asm' / f'{STEM}-b3-top-update-2000.map')
    top = ef[-4096:]
    assert bytes(updater[a] for a in range(0x4000, 0x5000)) == top
    linked = bytes(updater[a] for a in sorted(updater))
    for text in (b'STR8-N 2.0a13 B3 INSTALL', b'TYPE STR8-N 2.0a13> ',
                 b'STR8-N 2.0a13 VERIFIED; RESET', b'STR8-N 2.0A13\0'):
        assert text in linked

    mem = FlashMemory(b'')
    mem.ram[PCR], mem.ram[LED] = 0xEE, 0xF0
    for address, value in updater.items():
        mem.ram[address] = value
    old_top = bytes((i * 29 + 7) & 255 for i in range(4096))
    mem.banks[3][0x7000:] = old_top
    mem.banks[2][0x7000:] = b'\xa5' * 4096
    untouched = [bytes(mem.banks[i]) for i in (0, 1)]
    cpu = MPU(memory=mem)

    def run(start, stop, recovery=False):
        cpu.pc, cpu.sp = sym[start], 0xFF
        for _ in range(2_000_000):
            if cpu.pc == sym[stop]:
                return
            assert 0x2000 <= cpu.pc < 0x5000, hex(cpu.pc)
            if recovery and cpu.pc in (sym['TU_PUTS'], sym['TU_READ_LINE']):
                if cpu.pc == sym['TU_READ_LINE']:
                    mem.ram[sym['TU_INPUT']:sym['TU_INPUT']+2] = b'O\0'
                cpu.pc = (cpu.stPopWord()+1) & 0xFFFF
            else:
                cpu.step()
        raise AssertionError(('instruction limit', hex(cpu.pc)))

    run('TU_BACKUP_CONFIRMED', 'TU_BACKUP_SUM_HI_OK')
    assert mem.bank == 2 and bytes(mem.banks[2][0x7000:]) == old_top
    backup_count = len(mem.mutations)
    run('TU_FINAL_CONFIRMED', 'TU_SUCCESS', recovery=True)
    assert mem.bank == 3 and bytes(mem.banks[3][0x7000:]) == top

    mem.banks[3][0x7000:] = b'\0' * 4096
    run('TU_RECOVERY', 'TU_ARM_SOFT_RESET', recovery=True)
    assert mem.bank == 3 and bytes(mem.banks[3][0x7000:]) == old_top
    assert all(bank == 3 and address >= 0xF000
               for _, bank, address, _ in mem.mutations[backup_count:])
    assert [bytes(mem.banks[i]) for i in (0, 1)] == untouched
    print('PASS: clean B3 image, B2:F backup, V2 top install/verify, old-top recovery; B0/B1 untouched')


if __name__ == '__main__':
    main()
