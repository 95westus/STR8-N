"""Exercise alpha24 bank maintenance with and without the optional S/R sector."""
import sys

import build_v2_a24 as a24
sys.modules['build_v2'] = a24
import test_v2_a24_console  # installs the alpha24 boot-delay model
import test_v2_boot as boot
import test_v2_flash as flash


def check(sr_present):
    image, entry = a24.read_s19(a24.OUT / 'str8n-v2-bank-maint-2000.s19')
    sym = a24.symbols(a24.OUT / 'asm/str8n-v2-bank-maint-2000.map')
    assert entry == sym['START'] == 0x2000

    def setup():
        cpu, mem = flash.boot_flash(3)
        if not sr_present:
            mem.banks[3][0x6800:0x6F00] = b'\xff' * 0x700
        for address, value in image.items():
            mem.ram[address] = value
        cpu.pc = entry
        return cpu, mem

    cpu, mem = setup()
    mem.banks[1][:16] = bytes(range(16))
    before_b3 = bytes(mem.banks[3])
    mem.rx.extend(b'C10Y')
    boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
             b'VERIFIED' in mem.tx, limit=25_000_000)
    assert mem.banks[0] == mem.banks[1]
    assert mem.banks[3] == before_b3 and mem.bank == 3
    assert not any(event[1] == 3 for event in mem.events)

    count = len(mem.events)
    mem.rx.extend(b'C10')
    boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
             b'DESTINATION NOT ERASED' in mem.tx, limit=2_000_000)
    assert len(mem.events) == count

    cpu, mem = setup()
    before_b3 = bytes(mem.banks[3])
    mem.banks[0][0] = 0
    mem.rx.extend(b'E08Y')
    boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
             b'VERIFIED' in mem.tx, limit=1_000_000)
    assert mem.banks[0][:4096] == b'\xff' * 4096
    assert mem.banks[3] == before_b3
    print(f'PASS: bank maintenance copy/refusal/erase, B3 protected, S/R={sr_present}')


def main():
    check(True)
    check(False)


if __name__ == '__main__':
    main()
