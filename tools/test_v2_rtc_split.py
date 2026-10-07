"""Execute the extension split in a banked flash/I2C model; no board access."""
import hashlib
import json
from pathlib import Path

from test_v2_rtc import BusMemory, MPU

OUT = Path(__file__).resolve().parents[1] / 'BUILD/v2-rtc-phase2-split'
META = json.loads((OUT / 'build.json').read_text())


class Memory(BusMemory):
    def __init__(self, caller_bank=0, **options):
        super().__init__(**options)
        self.bank = caller_bank
        self.pcr = (0xCC, 0xCE, 0xEC, 0xEE)[caller_bank] | 0x11
        self.banks = [bytearray([255] * 32768) for _ in range(4)]
        provider = (OUT / 'provider.bin').read_bytes()
        offset = META['provider_address'] - 0x8000
        self.banks[3][offset:offset+len(provider)] = provider
        self.ram[0x6500:0x6700] = (OUT / 'gateway.bin').read_bytes()
        # All modeled banks have valid NMI vectors; prototype handler is RAM.
        for bank in self.banks:
            bank[0x7FFA:0x7FFC] = bytes([0x20, 0x7E])
        self.ram[0x7E20:0x7E23] = bytes([0x6C, 0, 0x7E])
        self.ram[0x7E00:0x7E02] = bytes([0, 0x27])
        self.ram[0x2700:0x2709] = bytes.fromhex('48 AD EC 7F 8D 00 26 68 40')
        self.mapping_events = []
        self.cpu = None

    def __getitem__(self, a):
        if isinstance(a, int):
            if a >= 0x8000:
                return self.banks[self.bank][a-0x8000]
            if a == 0x7FEC:
                return self.pcr
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if a == 0x7FEC:
            assert self.cpu.pc < 0x8000, 'Bank switch executed from flash'
            self.pcr = v
            self.bank = (0xCC, 0xCE, 0xEC, 0xEE).index(v & 0xEE)
            self.mapping_events.append(self.bank)
            return
        super().__setitem__(a, v)


def call(mem, entry=0x6504, expected=0, flags=0x20, inject_nmi=False):
    original_pcr = mem.pcr
    cpu = mem.cpu = MPU(memory=mem, pc=entry)
    cpu.p, cpu.sp = flags, 0xFD
    cpu.stPushWord(0x01FF)
    crc_reads, injected = 0, False
    for steps in range(2000000):
        if cpu.pc == 0x0200:
            break
        if cpu.pc == META['gateway_symbols']['FLASH_READ']:
            crc_reads += 1
        if inject_nmi and not injected and cpu.pc == META['provider_symbols']['READ_BIT']:
            cpu.nmi()
            injected = True
        cpu.step()
    else:
        raise AssertionError(f'Unbounded call at {cpu.pc:04X}')
    assert cpu.a == expected and bool(cpu.p & 1) == (expected == 0), (cpu.a, expected)
    assert cpu.p & 0x0C == flags & 0x0C and cpu.sp == 0xFD
    assert mem.pcr == original_pcr, 'Caller bank/control bits changed'
    assert mem.ddr == mem.initial_ddr
    assert mem.latch & mem.ddr == mem.initial_latch & mem.ddr
    if inject_nmi:
        assert injected and mem.ram[0x2600] & 0xEE == 0xEE
    return crc_reads, steps


def main():
    for name in ('provider', 'gateway'):
        assert hashlib.sha256((OUT / f'{name}.bin').read_bytes()).hexdigest() == META[f'{name}_sha256']
    checks = []
    measurements = []
    for bank in range(4):
        m = Memory(bank)
        cold, cold_steps = call(m, flags=0x28, inject_nmi=True)
        warm, warm_steps = call(m, flags=0x24)
        assert cold == META['provider_bytes'] and warm == 0
        assert m.ram[0x66C2:0x66CA] == bytes([0xEA, 7, 12, 31, 2, 23, 59, 58])
        assert not m.writes
        measurements.append(dict(bank=bank, first_call_steps=cold_steps, warm_call_steps=warm_steps))
    checks.append('all four caller banks, first-request CRC, cached calls, I/D/stack/VIA preservation')
    checks.append('RAM NMI handler injected during flash execution; return and caller bank preserved')
    m = Memory(present=False); call(m, expected=2); assert not m.writes
    m = Memory(stuck='scl'); call(m, expected=1)
    m = Memory(); m.banks[3][0] = 255
    call(m, expected=0x80); assert not m.accesses
    m = Memory(); m.banks[3][0x100] ^= 1
    call(m, expected=0x81); assert not m.accesses
    m = Memory(); m.ram[0x7E01] = 0x90
    call(m, expected=0x82); assert not m.mapping_events
    m = Memory(3); m.ram[0x7E01] = 0x90
    m.banks[3][0x1000:0x1009] = bytes.fromhex('48 AD EC 7F 8D 00 26 68 40')
    call(m, inject_nmi=True)
    checks.append('absent hardware, stuck bus, missing/corrupt extension, unsafe flash NMI handler refusal')
    m = Memory(); m.regs[3] |= 0x10
    event = bytes(m.regs[0x18:0x20])
    m.ram[0x66E9:0x66EB] = b'PA'
    call(m, entry=0x650D)
    assert m.ram[0x66F0:0x66F8] == event and m.ram[0x66DC] == 1
    assert not m.regs[3] & 0x10
    m = Memory()
    m.ram[0x66E0:0x66E8] = bytes([0xEA, 7, 10, 6, 2, 12, 34, 56])
    m.ram[0x66E9:0x66EB] = b'ST'
    call(m, entry=0x650A)
    assert m.regs[:7] == bytes([0xD6, 0x34, 0x12, 0x2A, 6, 0x10, 0x26])
    checks.append('first-call SET/ACK inputs survive lazy initialization and preserve outage capture')
    m = Memory(); call(m)
    m.banks[3][0x100] ^= 1
    # Integration must invalidate cached registration before an extension update.
    m.ram[0x6664] = 0
    call(m, expected=0x81)
    checks.append('explicit registration invalidation detects subsequent extension corruption')
    report = dict(passed=True, checks=checks, measurements=measurements,
                  provider_sha256=META['provider_sha256'], gateway_sha256=META['gateway_sha256'],
                  physical_hardware_tested=False, monitor_integrated=False)
    (OUT / 'test-results.json').write_text(json.dumps(report, indent=2) + '\n')
    for item in checks:
        print('PASS', item)


if __name__ == '__main__':
    main()
