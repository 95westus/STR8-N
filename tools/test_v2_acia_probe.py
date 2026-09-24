"""Execute the RAM-only direct W65C51N diagnostic in the host model."""
import hashlib
import json

from build_v2 import OUT, STEM, read_s19
from test_v2_boot import MPU, boot, hold, run, waiting


def main():
    path = OUT / f'{STEM}-acia-test-2000.s19'
    image, entry = read_s19(path)
    assert entry == 0x2000 and set(image) == set(range(0x2000, max(image)+1))

    cpu, mem = boot(0, ft245_present=True)
    for address, value in image.items():
        mem.ram[address] = value
    mem.acia_tx.clear()
    mem.acia_tx_cycles.clear()
    mem.tx.clear()
    cpu.pc = entry

    banner = b'ACIA 19200 8N1 - TYPE; Q EXITS\r\n'
    run(cpu, lambda: banner in mem.acia_tx, limit=300000)
    assert mem.acia_resets == 1
    assert mem.ram[0x7F83] == 0x1F and mem.ram[0x7F82] == 0x0B
    assert b'ACIA RX MONITOR; SEND Q' in mem.tx
    assert all(b-a >= 4167 for a, b in zip(mem.acia_tx_cycles, mem.acia_tx_cycles[1:]))

    start = len(mem.acia_tx)
    run(cpu, lambda: b'ACIA STATUS $00\r\n' in mem.tx, limit=9000000)
    mem.acia_rx.extend(b'Hi\r')
    run(cpu, lambda: b'Hi\r\n' in mem.acia_tx[start:], limit=300000)
    assert b'ACIA RX $48\r\nACIA RX $69\r\nACIA RX $0D\r\n' in mem.tx

    mem.acia_rx.extend(b'q')
    run(cpu, lambda: waiting(cpu), limit=800000)
    assert bytes(mem.acia_tx).endswith(b'\r\nACIA EXIT\r\n')
    assert b'STR8-N 2.0a13 B0 65C02' in mem.tx

    (OUT / 'acia-probe-test-results.json').write_text(json.dumps({
        'passed': ['direct ACIA init/banner, timed TX, FT245 RX reports, echo, Q return through HOLD'],
        's19_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')
    print('PASS: direct ACIA init/banner, timed TX, FT245 RX reports, echo, Q return through HOLD')


if __name__ == '__main__':
    main()
