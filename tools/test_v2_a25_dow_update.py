"""Check exact-image E-only weekday update in the flash model."""
import json
from pathlib import Path

import build_v2_a25 as a25
import test_v2_a25_boot as model
import test_v2_flash as flash

OUT = a25.ROOT / 'BUILD/board/a25-dow'

def setup(old_e, path):
    cpu, memory = flash.boot_flash(3)
    memory.banks[3][0x6000:0x7000] = old_e
    updater, entry = a25.read_s19(path)
    assert entry == 0x2000
    for address, value in updater.items():
        memory.ram[address] = value
    cpu.pc, cpu.sp = entry, 0xFF
    return cpu, memory

def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    path = Path(manifest['e_updater'])
    old_e = (OUT / 'old-e.bin').read_bytes()
    new_e = (OUT / 'new-e.bin').read_bytes()
    old_f = (OUT / 'expected-f.bin').read_bytes()
    cpu, memory = setup(old_e, path)
    before_b0, before_b2 = bytes(memory.banks[0]), bytes(memory.banks[2])
    model.boot.run(cpu, lambda: b'B3:E exact; TYPE Y to repair>' in memory.tx,
                   limit=2_000_000)
    assert not memory.events
    memory.rx.append(ord('Y'))
    model.boot.run(cpu, lambda: cpu.pc == 0xF004, limit=15_000_000)
    assert bytes(memory.banks[3][0x6000:0x7000]) == new_e
    assert bytes(memory.banks[3][0x7000:]) == old_f
    assert bytes(memory.banks[0]) == before_b0
    assert bytes(memory.banks[2]) == before_b2
    assert all(event[1] == 3 and 0xE000 <= event[2] <= 0xEFFF
               for event in memory.events)
    cpu, memory = setup(old_e, path)
    memory.banks[3][0x6000] ^= 1
    model.boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
    assert b'OLD IMAGE MISMATCH' in memory.tx and not memory.events
    cpu, memory = setup(old_e, path)
    memory.banks[3][0x7000] ^= 1
    model.boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
    assert b'REQUIRED IMAGE MISMATCH' in memory.tx and not memory.events
    cpu, memory = setup(old_e, path)
    model.boot.run(cpu, lambda: b'TYPE Y to repair>' in memory.tx,
                   limit=2_000_000)
    memory.rx.append(ord('N'))
    model.boot.run(cpu, lambda: cpu.pc == 0xF007, limit=100_000)
    assert not memory.events
    print('a25 EDU weekday E update: exact gate, verified E, F/B0/B2 retained PASS')

if __name__ == '__main__':
    main()
