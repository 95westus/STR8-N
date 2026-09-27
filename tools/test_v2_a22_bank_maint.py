"""Exercise the v2 RAM maintenance copy/erase guards in the banked flash model."""
import sys
import build_v2_a22 as a22

sys.modules['build_v2'] = a22
import test_v2_a22_sr as sr


def main():
    image, entry = a22.read_s19(a22.OUT / 'str8n-v2-bank-maint-2000.s19')
    sym = a22.symbols(a22.OUT / 'asm/str8n-v2-bank-maint-2000.map')
    assert entry == sym['START'] == 0x2000
    cpu, mem = sr.flash.boot_flash(3)
    for address, value in image.items():
        mem.ram[address] = value
    mem.banks[1][0x0000:0x0010] = bytes(range(16))
    before_b3 = bytes(mem.banks[3])
    cpu.pc = entry
    mem.rx.extend(b'C10Y')
    sr.boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
                b'VERIFIED' in mem.tx, limit=25_000_000)
    assert mem.banks[0] == mem.banks[1]
    assert mem.banks[3] == before_b3
    assert mem.bank == 3
    assert not any(event[1] == 3 for event in mem.events)
    # Refuse a used destination before any additional mutation.
    count = len(mem.events)
    mem.rx.extend(b'C10')
    sr.boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
                b'DESTINATION NOT ERASED' in mem.tx, limit=2_000_000)
    assert len(mem.events) == count
    cpu, erase_mem = sr.flash.boot_flash(3)
    for address, value in image.items():
        erase_mem.ram[address] = value
    erase_mem.banks[0][0] = 0
    cpu.pc = entry
    erase_mem.rx.extend(b'E08Y')
    try:
        sr.boot.run(cpu, lambda: cpu.pc == sym['BM_MENU'] and
                    b'VERIFIED' in erase_mem.tx, limit=1_000_000)
    except AssertionError:
        raise AssertionError((hex(cpu.pc), bytes(erase_mem.tx)[-200:],
                              list(erase_mem.rx), erase_mem.events[-3:]))
    assert erase_mem.banks[0][:4096] == b'\xff' * 4096
    assert erase_mem.banks[3] == before_b3
    print('PASS: v2 RAM bank maintenance copy, occupied refusal, erase, B3 protection')


if __name__ == '__main__':
    main()
