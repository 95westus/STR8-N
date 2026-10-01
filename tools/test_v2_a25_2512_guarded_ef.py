"""Exercise board-2512 alpha21-to-alpha25 exact-image E/F updaters in the flash model."""
import sys
import re
from pathlib import Path

import build_v2_a24 as old
sys.modules['build_v2'] = old
import test_v2_a24_console  # FT245 startup model
import test_v2_boot as boot
import test_v2_flash as flash

OUT = old.ROOT / 'BUILD/board/a25-2512'
E = OUT / 'str8n-v2-alpha25-board2512-e-install-2000.s19'
F = OUT / 'str8n-v2-alpha25-board2512-f-install-2000.s19'

def load(cpu, memory, path):
    image, entry = old.read_s19(path)
    assert entry == 0x2000 and max(image) < 0x6900
    for address, value in image.items():
        memory.ram[address] = value
    cpu.pc, cpu.sp = entry, 0xFF

def setup(e_image):
    cpu, memory = flash.boot_flash(3)
    memory.banks[3][0x6000:0x7000] = e_image
    memory.banks[3][0x7000:] = (OUT / 'old-f.bin').read_bytes()
    worker_source = old.ROOT / 'output/qualification/v2-alpha21-2026-09-24/candidate/asm/worker-image.inc'
    worker = bytes(int(h, 16) for h in re.findall(r'\$([0-9A-F]{2})', worker_source.read_text()))
    assert len(worker) == 765
    memory.ram[0x7900:0x7900+len(worker)] = worker
    vector_source = old.ROOT / 'output/qualification/v2-alpha21-2026-09-24/candidate/asm/vectors-image.inc'
    vectors = bytes(int(h, 16) for h in re.findall(r'\$([0-9A-F]{2})', vector_source.read_text()))
    memory.ram[0x7E20:0x7E20+len(vectors)] = vectors
    return cpu, memory

def confirm(cpu, memory, phase):
    prompt = b'B3:E exact; TYPE Y to repair>' if phase == 'e' else b'B3:F exact; TYPE Y to update>'
    boot.run(cpu, lambda: prompt in memory.tx, limit=20_000_000)
    assert not memory.events
    memory.rx.append(ord('Y'))
    boot.run(cpu, lambda: cpu.pc == 0xF004, limit=18_000_000)

def main():
    old_e = (OUT / 'old-e.bin').read_bytes()
    old_f = (OUT / 'old-f.bin').read_bytes()
    new_e = (OUT / 'new-e.bin').read_bytes()
    new_f = (OUT / 'new-f.bin').read_bytes()
    cpu, memory = setup(old_e)
    before_b0, before_b2 = bytes(memory.banks[0]), bytes(memory.banks[2])
    load(cpu, memory, E)
    confirm(cpu, memory, 'e')
    assert bytes(memory.banks[3][0x6000:0x7000]) == new_e
    assert bytes(memory.banks[3][0x7000:]) == old_f
    assert all(event[1] == 3 and 0xE000 <= event[2] <= 0xEFFF for event in memory.events)
    load(cpu, memory, F)
    memory.events.clear()
    confirm(cpu, memory, 'f')
    assert bytes(memory.banks[3][0x6000:0x7000]) == new_e
    assert bytes(memory.banks[3][0x7000:]) == new_f
    assert all(event[1] == 3 and 0xF000 <= event[2] <= 0xFFFF for event in memory.events)
    assert bytes(memory.banks[0]) == before_b0
    assert bytes(memory.banks[2]) == before_b2

    for phase, path, current_e, change_addr, message in (
        ('e', E, old_e, 0x6000, b'OLD IMAGE MISMATCH'),
        ('f', F, old_e, None, b'REQUIRED IMAGE MISMATCH'),
        ('f', F, new_e, 0x7000, b'OLD IMAGE MISMATCH'),
    ):
        cpu, memory = setup(current_e)
        if change_addr is not None:
            memory.banks[3][change_addr] ^= 1
        load(cpu, memory, path)
        boot.run(cpu, lambda: cpu.pc == 0xF007, limit=20_000_000)
        assert message in memory.tx and not memory.events, phase

    for phase, path, current_e in (('e', E, old_e), ('f', F, new_e)):
        cpu, memory = setup(current_e)
        load(cpu, memory, path)
        prompt = b'TYPE Y to repair>' if phase == 'e' else b'TYPE Y to update>'
        boot.run(cpu, lambda: prompt in memory.tx, limit=20_000_000)
        memory.rx.append(ord('N'))
        boot.run(cpu, lambda: cpu.pc == 0xF007, limit=100_000)
        assert not memory.events
    cpu, memory = setup(new_e)
    load(cpu, memory, F)
    boot.run(cpu, lambda: b'TYPE Y to update>' in memory.tx, limit=20_000_000)
    memory.fault = 'erase_verify'
    memory.rx.append(ord('Y'))
    boot.run(cpu, lambda: b'B3:F UPDATE FAILED' in memory.tx, limit=8_000_000)
    assert cpu.pc < 0x8000 and b'B3:F UPDATE FAILED' in memory.tx
    print('a25 board 2512 guarded E/F: exact preimages, order, verified writes, cancel/refusal PASS')

if __name__ == '__main__':
    main()
