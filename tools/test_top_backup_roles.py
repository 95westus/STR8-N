"""Execute linked backup and recovery paths against modeled flash, never hardware."""
from test_worker_optimization import FlashMemory, MPU, PCR, LED, REL, symbols

for name in ('top-update', 'directory-refresh', 'str8-in65-top-update', 'bank-maint-menu'):
    stem = f'str8n-v1.35-{name}-2000'
    sym = symbols(REL / f'map/{stem}.map')
    mem = FlashMemory(b'')
    mem.ram[PCR] = 0xEE
    # This borrowed flash model requires a red latch; LED behavior is outside
    # this role-routing test and is not inferred from it.
    mem.ram[LED] = 0xF0
    for line in (REL / f's19/{stem}.s19').read_text().splitlines():
        if line.startswith('S1'):
            raw = bytes.fromhex(line[2:])
            at = int.from_bytes(raw[1:3], 'big')
            mem.ram[at:at+len(raw[3:-1])] = raw[3:-1]
    top = (REL / 'bin/str8n-v1.35-bank3-f000-ffff.bin').read_bytes()
    assert top[0xFF0:0xFF3] == bytes((0xFF, 0x2F, 0xFF))
    live_top = bytearray(top)
    live_top[0xFF0:0xFF2] = bytes((0x1E, 0x1F))
    mem.banks[3][0x7000:] = live_top
    mem.ram[sym['TU_META']:sym['TU_META']+64] = live_top[0xFB0:0xFF0]
    # Occupied fixtures ensure the borrowed model's old-byte polling observes
    # erase completion before programming; this is not flash timing proof.
    mem.banks[2][0x7000:] = b'\xA5' * 4096
    untouched = [bytes(mem.banks[i]) for i in (0, 1)]
    cpu = MPU(memory=mem)

    def run(entry, stop, recovery=False):
        cpu.pc, cpu.sp = sym[entry], 0xFF
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
        raise AssertionError((name, 'instruction limit', hex(cpu.pc)))

    run('TU_BACKUP_CONFIRMED', 'TU_BACKUP_SUM_HI_OK')
    assert mem.bank == 2 and bytes(mem.banks[2][0x7000:]) == live_top
    assert mem.mutations and all(bank == 2 and at >= 0xF000 for _, bank, at, _ in mem.mutations)
    backup_mutations = len(mem.mutations)
    run('TU_FINAL_CONFIRMED', 'TU_SUCCESS', recovery=True)
    assert mem.bank == 3 and bytes(mem.banks[3][0x7000:]) == top
    # Model an interrupted target rewrite, then use the actual O recovery path.
    mem.banks[3][0x7000:] = b'\0' * 4096
    run('TU_RECOVERY', 'TU_ARM_SOFT_RESET', recovery=True)
    assert mem.bank == 3 and bytes(mem.banks[3][0x7000:]) == live_top
    assert all(bank == 3 and at >= 0xF000 for _, bank, at, _ in mem.mutations[backup_mutations:])
    assert [bytes(mem.banks[i]) for i in (0, 1)] == untouched
    print(f'{name}: B2:F backup and B3:F recovery PASS; new roles installed; old roles restored; B0/B1 unchanged')
