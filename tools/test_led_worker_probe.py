"""Execute the linked board probe with modeled flash before using its scratch sector."""
from test_worker_optimization import FlashMemory, MPU, PCR, LED, REL, symbols

stem = 'str8n-v1.34-led-worker-test-2000'
sym = symbols(REL / f'map/{stem}.map')
assert sym['LWT_TARGET_BANK'] == 2 and sym['LWT_TARGET_SECTOR_HI'] == 0x90
records = (REL / f's19/{stem}.s19').read_text().splitlines()
assert records[-1] == 'S9032000DC'

for occupied in (False, True):
    mem = FlashMemory(b'')
    mem.ram[PCR] = 0xEE
    mem.banks[3][0x7000:] = (REL / 'bin/str8n-v1.34-bank3-f000-ffff.bin').read_bytes()
    if occupied:
        mem.banks[2][0x1000] = 0x7F
    before = [bytes(bank) for bank in mem.banks]
    for line in records:
        raw = bytes.fromhex(line[2:])
        assert len(raw) == raw[0] + 1 and sum(raw) & 255 == 255
        if line.startswith('S1'):
            address = int.from_bytes(raw[1:3], 'big')
            assert 0x2000 <= address < 0x3000
            mem.ram[address:address + len(raw[3:-1])] = raw[3:-1]
    cpu = MPU(memory=mem, pc=0x2000)
    output = bytearray()
    for step in range(3_000_000):
        if cpu.pc == sym['LWT_HALT']:
            break
        if cpu.pc in (0xF013, 0xF019, 0xF03E):
            if cpu.pc == 0xF013:
                cpu.a = ord('Y')
            elif cpu.pc == 0xF019:
                output.append(cpu.a)
            else:
                cpu.p &= ~cpu.CARRY
            cpu.pc = cpu.stPopWord() + 1
            continue
        cpu.step()
    else:
        raise AssertionError('probe did not halt')
    assert (b'LED WORKER TEST: PASS' in output) == (not occupied), output
    assert (b'REFUSE: B2:9 NOT ERASED' in output) == occupied, output
    assert [bytes(bank) for bank in mem.banks] == before
    assert mem.bank == 3 and mem.pending is None
    if occupied:
        assert not mem.mutations
    else:
        # The first blank-sector check avoids erase; cleanup erases the pattern.
        assert len(mem.mutations) == 4097
        assert sum(kind == 'erase' for kind, *_ in mem.mutations) == 1
        assert all(bank == 2 and 0x9000 <= address < 0xA000
                   for kind, bank, address, value in mem.mutations)
        assert mem.ram[LED] == 1
    print(('occupied refusal' if occupied else 'program/verify/erase/verify/invalid-write'),
          'PASS; all banks restored; only B2:9 may mutate')
