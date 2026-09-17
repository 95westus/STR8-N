"""Run linked maintenance startup with stale worker modes and every entry bank."""
from test_worker_optimization import FlashMemory, MPU, PCR, PATTERNS, REL, symbols

count = 0
for suffix in ('bank-maint', 'bank-maint-menu', 'str8-in65-bank-maint'):
    stem = f'str8n-v1.35-{suffix}-2000'
    sym = symbols(REL / f'map/{stem}.map')
    records = (REL / f's19/{stem}.s19').read_text().splitlines()
    for roles in ((0x1E, 0x1F), (0xFF, 0x2F)):
        for pattern in PATTERNS:
            for extra in (0, 0x11):
                for mode in (*range(8), 0xFF):
                    mem = FlashMemory(b'')
                    mem.ram[PCR] = pattern | extra
                    mem.ram[0x7DF0] = mode
                    mem.banks[3][0x7FF0:0x7FF2] = bytes(roles)
                    before = [bytes(bank) for bank in mem.banks]
                    for line in records:
                        if line.startswith('S1'):
                            raw = bytes.fromhex(line[2:])
                            address = int.from_bytes(raw[1:3], 'big')
                            mem.ram[address:address + len(raw[3:-1])] = raw[3:-1]
                    cpu = MPU(memory=mem, pc=sym['BM_MAIN'])
                    cpu.sp = 0xFF
                    for step in range(10000):
                        if cpu.pc == sym['BM_PUTS']:
                            break
                        assert not 0x200 <= cpu.pc < 0xA00, 'startup dispatched stale private worker'
                        cpu.step()
                    else:
                        raise AssertionError('startup did not reach menu output')
                    assert mem.ram[0x7C30] == roles[0] and mem.ram[0x7C32] == roles[1]
                    assert mem.ram[PCR] == pattern | extra
                    assert not mem.commands and not mem.mutations
                    assert [bytes(bank) for bank in mem.banks] == before
                    count += 1
print(f'BANK MAINT ROLE STARTUP: {count} linked cases PASS; roles read from B3, entry bank restored, no worker dispatch or flash writes')
