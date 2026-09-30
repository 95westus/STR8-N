"""Execute the linked unified WDCMON installer on a W65C02 opcode model.

The flash and FT245 devices are logical models. This complements, but does not
replace, the physical W65C02SXB and manual W65C816SXB board tests.
"""

from __future__ import annotations

import hashlib
import json
import sys

import build_v2_a24 as a24

sys.modules['build_v2'] = a24

from test_v2_flash import FlashMemory, MPU  # noqa: E402


INSTALLER = a24.ROOT / 'BUILD/v2-alpha24-wdcmon-ram/str8n-v2-alpha24-wdcmonv2-install-2000.s19'
MAP = INSTALLER.with_suffix('.map')
TOP = a24.OUT / f'{a24.STEM}-f000-ffff.bin'
INSTALLER_SHA256 = '66bd1030c2f48444826f03562886fc4828d4047f36d4ba42d1e5f8e5396cbebe'


class InstallerMemory(FlashMemory):
    def __init__(self, stock: bytes):
        super().__init__(3)
        self.banks[3][:] = stock
        self.banks[1][:] = b'\xa5' * 0x8000
        self.banks[2][:] = b'\x5a' * 0x8000
        self.id_mode = False

    def __getitem__(self, address):
        if isinstance(address, int) and self.id_mode and address in (0x8000, 0x8001):
            return 0xBF if address == 0x8000 else 0xB5
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if address == 0xD555 and value == 0x90 and self.unlock == 2:
            self.id_mode = True
            self.unlock = 0
            return
        if self.id_mode and address == 0x8000 and value == 0xF0:
            self.id_mode = False
            return
        super().__setitem__(address, value)


class W65C02(MPU):
    def step(self):
        # WDC specifies $FB as a one-byte NOP. py65 models this reserved byte
        # as a two-byte instruction, so correct only that behavior here.
        if self.pc == 0x2001 and self.memory[self.pc] == 0xFB:
            self.pc = (self.pc + 1) & 0xFFFF
            self.processorCycles += 1
            return self
        return super().step()


def fixture():
    linked, entry = a24.read_s19(INSTALLER)
    assert entry == 0x2000 and min(linked) == 0x2000
    assert hashlib.sha256(INSTALLER.read_bytes()).hexdigest() == INSTALLER_SHA256
    assert bytes(linked[address] for address in range(0x2000, 0x2003)) == b'\x38\xfb\x78'
    symbols = a24.symbols(MAP)
    stock = bytearray(b'\xff' * 0x8000)
    for sector in range(8):
        stock[sector * 0x1000 + 0x123] = 0x31 + sector
        stock[sector * 0x1000 + 0xFFE] = 0x80 + sector
    stock[0x7FFC:0x7FFE] = b'\x18\xf8'
    memory = InstallerMemory(bytes(stock))
    for address, value in linked.items():
        memory.ram[address] = value
    cpu = W65C02(memory=memory, pc=entry)
    memory.cpu = cpu
    cpu.p &= ~cpu.INTERRUPT
    return cpu, memory, bytes(stock), symbols


def run(cpu, stop, limit=45_000_000):
    for _ in range(limit):
        if stop():
            return
        assert 0x2000 <= cpu.pc < 0x3000, hex(cpu.pc)
        cpu.step()
    raise AssertionError(f'installer instruction limit at ${cpu.pc:04X}')


def check_success():
    cpu, memory, stock, symbols = fixture()
    top = TOP.read_bytes()
    assert len(top) == 4096
    untouched = [bytes(memory.banks[index]) for index in (1, 2)]
    memory.rx.extend(b'COPY B3 TO B0\r' + top + b'INSTALL STR8-N 2.0A24\r')
    run(cpu, lambda: cpu.pc == symbols['W2I_V2_RESET_WAIT'])
    assert bytes(memory.banks[0]) == stock
    assert bytes(memory.banks[3][:0x7000]) == stock[:0x7000]
    assert bytes(memory.banks[3][0x7000:]) == top
    assert [bytes(memory.banks[index]) for index in (1, 2)] == untouched
    assert all(bank in (0, 3) and (bank == 0 or address >= 0xF000)
               for _, bank, address, _ in memory.events)
    assert b'B0 == ORIGINAL B3 VERIFIED' in memory.tx
    assert b'MIGRATION VERIFIED; PRESS PHYSICAL RESET' in memory.tx
    assert not memory.rx and memory.bank == 3
    print('PASS: 65C02 SEC/$FB entry, B3->B0 copy, exact F install, B1/B2 preserved')


def check_occupied_b0():
    cpu, memory, stock, _ = fixture()
    memory.banks[0][0x1234] = 0x00
    before = [bytes(bank) for bank in memory.banks]
    run(cpu, lambda: b'HALTED IN RAM' in memory.tx)
    assert b'REFUSE: B0 USED AND DIFFERENT' in memory.tx
    assert not memory.events and [bytes(bank) for bank in memory.banks] == before
    assert bytes(memory.banks[3]) == stock
    print('PASS: occupied different B0 refused before flash mutation')


def check_bad_candidate():
    cpu, memory, stock, _ = fixture()
    bad = bytearray(TOP.read_bytes())
    bad[0x123] ^= 1
    memory.rx.extend(b'COPY B3 TO B0\r' + bad)
    run(cpu, lambda: b'HALTED IN RAM' in memory.tx)
    assert (b'RECEIVED STR8-N TOP CHECK FAILED' in memory.tx
            and b'B0 == ORIGINAL B3 VERIFIED' in memory.tx)
    assert bytes(memory.banks[0]) == stock
    assert bytes(memory.banks[3]) == stock
    assert all(bank == 0 for _, bank, _, _ in memory.events)
    print('PASS: altered candidate refused before B3:F mutation')


def main():
    check_success()
    check_occupied_b0()
    check_bad_candidate()
    report = {
        'version': a24.VERSION,
        'cpu_model': 'W65C02S ($FB one-byte NOP)',
        'installer_s19_sha256': INSTALLER_SHA256,
        'physical_hardware_tested': False,
        'cases': ['success', 'occupied_b0_refusal', 'bad_candidate_refusal'],
    }
    (a24.OUT / 'wdcmon-65c02-test.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
