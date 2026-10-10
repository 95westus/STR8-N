"""Execute the candidate map with installed beta22 services; no board access."""
import os
os.environ['STR8_RTC_BUILD'] = 'BUILD/v2-spi-map'
import json
from test_v2_status import fresh, boot, layout, snapshot, OUT
from test_v2_storage import cmd
from test_v2_sram_store import fast_transfer, k
SYMBOLS = json.loads((OUT / 'maint/manifest.json').read_text())['symbols']


def occupy_erased_sectors(memory):
    # Used untagged sectors exercise the normal renderer without spending most
    # of this storage-state suite scanning 128 KiB of erased flash repeatedly.
    for bank in memory.banks:
        for offset in range(0, 0x8000, 0x1000):
            if bytes(bank[offset:offset+0x1000]) == b'\xff'*0x1000:
                bank[offset] = 0


def allocation(cpu, memory):
    # Execute the actual linked routine without rescanning all flash sectors
    # for every storage-state permutation. End-to-end maps are checked below.
    body = (OUT / json.loads((OUT / 'build.json').read_text())['maintenance_storage_file']).read_bytes()
    count = int.from_bytes(body[6:8], 'little')
    memory.ram[0x2000:0x2000+count] = body[24:24+count]
    memory[0x7FEC] = (memory.ram[0x7FEC] & 0x11) | 0xEE
    start = len(memory.tx)
    sp = cpu.sp
    cpu.stPushWord(0x1ff)
    cpu.pc = SYMBOLS['SPI_MAP_ALLOCATION']
    for _ in range(2000000):
        if cpu.pc == 0x200:
            break
        if getattr(memory, 'fast', False) and cpu.pc == 0x66A6:
            fast_transfer(cpu, memory)
        else:
            cpu.step()
    else:
        raise AssertionError(('allocation timeout', hex(cpu.pc)))
    assert cpu.sp == sp
    return bytes(memory.tx[start:])


def check(cpu, memory, command, expected, no_spi=False):
    before = snapshot(memory)
    window = bytes(range(64))
    memory.ram[0x6400:0x6440] = window
    epoch = memory.ram[0x66AF]
    frames = len(memory.spi.frames)
    out = allocation(cpu, memory) if command is None else cmd(cpu, memory, command)
    assert expected in out, out[-1500:]
    assert snapshot(memory) == before
    assert memory.ram[0x6400:0x6440] == window
    assert memory.ram[0x66AF] == epoch
    if no_spi:
        assert len(memory.spi.frames) == frames
    return out


def main():
    checks = []
    def passed(description):
        checks.append(description)
        print('PASS', description, flush=True)
    cpu, memory = fresh(primary=layout())
    boot(cpu)
    occupy_erased_sectors(memory)
    for units, boundary in ((1, '04000'), (2, '08000'), (3, '0C000'), (4, '10000')):
        if units == 4:
            cpu, memory = fresh(primary=layout())
            boot(cpu)
            occupy_erased_sectors(memory)
        memory.spi.devices[0].data[:64] = layout(units)
        # The 64 KiB split exercises the complete bit-level SPI path.
        memory.fast = units != 4
        for mode in ((1, 2, 3) if units == 4 else (None,)):
            print('CHECK map', mode if mode else 'allocation', units * 16, flush=True)
            out = check(cpu, memory, f'M{mode}\r'.encode() if mode else None,
                        f'playground {boundary}-1FFDF'.encode())
            assert b'SPI SRAM: ON' in out and b'not CPU mapped' in out
            assert b'SPI playground capacity:' in out
            if mode:
                assert b'B3> ' in out
        if units == 4:
            (OUT / 'spi-map-example.txt').write_bytes(out)
        passed(f'{units * 16} KiB programs, exact playground bounds; read-only' + ('; all map views' if units == 4 else ''))
    cpu, memory = fresh(off=True)
    boot(cpu)
    occupy_erased_sectors(memory)
    reclaimed = bytes(memory.ram[0x6500:0x6700])
    for mode in (1,):
        out = check(cpu, memory, f'M{mode}\r'.encode(), b'SPI SRAM: OFF (EDU OFF)', no_spi=True)
        assert b'RAM 0200-66FF program; services inactive' in out
        assert bytes(memory.ram[0x6500:0x6700]) == reclaimed
    passed('OFF maps preserve reclaimed service RAM and perform no SPI transfers')
    cpu, memory = fresh()
    memory.banks[3][0x1000:0x2000] = b'\xff' * 4096
    boot(cpu)
    check(cpu, memory, None, b'SPI SRAM: services absent/incompatible', no_spi=True)
    passed('missing SPI provider reports absent with no SPI transfers')
    cpu, memory = fresh(primary=layout())
    boot(cpu)
    memory.ram[0x66A2] ^= 1
    check(cpu, memory, None, b'SPI SRAM: services absent/incompatible', no_spi=True)
    passed('incompatible SRAM service signature refuses before SPI transfers')
    memory.ram[0x66A2] ^= 1
    bad = layout()
    bad[60] ^= 1
    for primary, secondary, expected in (
        (None, None, b'Allocation uninitialized; playground split unknown'),
        (bad, None, b'Layout invalid'),
        (bytes(64), layout(2), b'Layout needs repair'),
        (layout(version=1), None, b'playground 10000-1FFDF'),
    ):
        memory.spi.devices[0].data[:64] = b'\xff'*64 if primary is None else primary
        memory.spi.devices[0].data[0x240:0x280] = b'\xff'*64 if secondary is None else secondary
        memory.fast = True
        out = check(cpu, memory, None, expected)
        if b'playground 10000' not in expected:
            assert b'SPI programs 00800-' not in out
    passed('uninitialized, invalid, secondary recovery and legacy layouts distinguished without writes')
    cpu, memory = fresh(present=False)
    boot(cpu)
    check(cpu, memory, None, b'Unavailable (hardware/read refused)')
    passed('unavailable hardware/read reports unavailable without a fabricated split')
    cpu, memory = fresh(primary=layout())
    boot(cpu)
    memory.fast = True
    memory.transfer_fault = lambda *args: (0, 12)
    check(cpu, memory, None, b'Unavailable (hardware/read refused)')
    passed('short successful read refuses and restores the entire transfer window')
    cpu, memory = fresh(primary=layout())
    boot(cpu)
    occupy_erased_sectors(memory)
    out = check(cpu, memory, b'R MAINT\rM1\rQ\r', b'playground 10000-1FFDF')
    assert b'BANK MAINT 1.9' in out and b'BM> ' in out and b'B3> ' in out
    passed('MAINT and monitor maps share the same playground display and return normally')
    report = dict(passed=True, checks=checks, boards_flashed=False,
                  maintenance=json.loads((OUT / 'maint/manifest.json').read_text())['program_sha256'])
    (OUT / 'spi-map-test-results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
