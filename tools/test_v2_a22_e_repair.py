"""Execute the exact-image B3:E repair against the flash model."""
import argparse
from pathlib import Path

import test_v2_a22_sr as sr


a22, boot, flash = sr.a22, sr.boot, sr.flash
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dot', action='store_true',
                    help='exercise the paired autostart-dot E update')
args = parser.parse_args()
OUT = ROOT / ('BUILD/v2-alpha22-dot-update' if args.dot else
              'BUILD/v2-alpha22-e-repair')
OLD = (OUT / 'old-e.bin').read_bytes()
NEW = (OUT / 'candidate-e.bin').read_bytes()
UPDATER, ENTRY = a22.read_s19(OUT / ('str8n-v2-alpha22-dot-e-update-2000.s19'
                                      if args.dot else
                                      'str8n-v2-alpha22-e-repair-2000.s19'))


def setup(mismatch=False):
    cpu, mem = flash.boot_flash(3)
    mem.banks[3][0x6000:0x7000] = OLD
    if mismatch:
        mem.banks[3][0x6800] ^= 1
    for address, value in UPDATER.items():
        mem.ram[address] = value
    cpu.pc, cpu.sp = ENTRY, 0xFF
    return cpu, mem


def main():
    assert ENTRY == 0x2000
    cpu, mem = setup()
    start = len(mem.tx)
    boot.run(cpu, lambda: b'TYPE Y to repair>' in mem.tx[start:], limit=2_000_000)
    assert not mem.events
    mem.rx.append(ord('Y'))
    boot.run(cpu, lambda: cpu.pc == 0xF004, limit=15_000_000)
    assert bytes(mem.banks[3][0x6000:0x7000]) == NEW
    assert any(event[0] == 'erase' and event[1:3] == (3, 0xE000)
               for event in mem.events)
    assert all(event[1] == 3 and 0xE000 <= event[2] <= 0xEFFF
               for event in mem.events)
    cpu, mem = setup(mismatch=True)
    boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
    assert b'OLD IMAGE MISMATCH' in mem.tx and not mem.events
    cpu, mem = setup()
    boot.run(cpu, lambda: b'TYPE Y to repair>' in mem.tx, limit=2_000_000)
    mem.rx.append(ord('N'))
    boot.run(cpu, lambda: cpu.pc == 0xF007, limit=100_000)
    assert not mem.events
    print('PASS: exact old E preflight, confirmed repair, preserved sector, mismatch/cancel guards')


if __name__ == '__main__':
    main()
