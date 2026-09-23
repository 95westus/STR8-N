"""Model-check 65C02 probes and audit the assembled 816-native probe."""
import json

from build_v2 import OUT, STEM, read_s19
from test_v2_boot import Memory, MPU, SYM, VSYM, hold, waiting


REPORT = json.loads((OUT / 'build.json').read_text())
PROBE = REPORT['interrupt_probe']
PROBE_PATH = OUT / f'{STEM}-interrupt-probe-2000.s19'
NMI = REPORT['nmi_probe']
NMI_PATH = OUT / f'{STEM}-nmi-probe-2000.s19'
NATIVE = REPORT['native_probe']
NATIVE_PATH = OUT / f'{STEM}-native-probe-2000.s19'


class ProbeMemory(Memory):
    def __init__(self, bank=0):
        super().__init__(bank)
        self.ier = 0
        self.ifr = 0

    def __getitem__(self, address):
        if address == 0x7FCE:
            return 0x80 | self.ier
        if address == 0x7FCD:
            return self.ifr | (0x80 if self.ifr & self.ier else 0)
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if address == 0x7FCE:
            self.writes.append(address)
            if value & 0x80:
                self.ier |= value & 0x7F
            else:
                self.ier &= ~(value & 0x7F)
            return
        if address == 0x7FCD:
            self.writes.append(address)
            self.ifr &= ~(value & 0x7F)
            return
        super().__setitem__(address, value)


def load_probe(memory, path, end):
    image, entry = read_s19(path)
    assert entry == 0x2000 and set(image) == set(range(0x2000, end))
    for address, value in image.items():
        memory.ram[address] = value
    return entry


def run_mode(mode):
    memory = ProbeMemory()
    cpu = MPU(memory=memory, pc=SYM['START'])
    hold(cpu)
    memory.ram[0x7FCB] = 0x0C
    memory.ram[0x7FC6:0x7FC8] = bytes((0x12, 0x34))
    memory.ier = 1 if mode == 'busy' else 0
    entry = load_probe(memory, PROBE_PATH, PROBE['PROBE_END'])
    old_pointers = bytes(memory.ram[0x7E02:0x7E06])
    memory.writes.clear()
    memory.bank_changes.clear()
    start_output = len(memory.tx)
    cpu.pc = entry
    injected = False
    for _ in range(1000000):
        if waiting(cpu):
            break
        if mode == 'success' and not injected and cpu.pc == PROBE['WAIT_IRQ']:
            assert not cpu.p & cpu.INTERRUPT
            memory.ifr |= 0x40
            cpu.irq()
            assert cpu.pc == VSYM['V2V_IRQ_BRK']
            injected = True
        cpu.step()
    else:
        raise AssertionError(f'{mode}: probe did not return to HOLD')
    output = bytes(memory.tx[start_output:])
    assert (b': PASS' in output) == (mode == 'success'), output
    assert (b': FAIL' in output) == (mode == 'timeout'), output
    assert (b'REFUSE:' in output) == (mode == 'busy'), output
    assert memory.ram[0x7E02:0x7E06] == old_pointers
    assert memory.ram[0x7FCB] == 0x0C
    assert memory.ram[0x7FC6:0x7FC8] == bytes((0x12, 0x34))
    assert memory.ier == (1 if mode == 'busy' else 0)
    assert not memory.bank_changes
    print(mode, output.decode('ascii').strip().splitlines()[0])


def run_nmi_mode(mode):
    memory = ProbeMemory()
    cpu = MPU(memory=memory, pc=SYM['START'])
    hold(cpu)
    if mode == 'busy':
        memory.ram[SYM['V2_NMI_HOLD']] = 1
    entry = load_probe(memory, NMI_PATH, NMI['PROBE_END'])
    old_pointer = bytes(memory.ram[0x7E00:0x7E02])
    memory.writes.clear()
    start_output = len(memory.tx)
    cpu.pc = entry
    injected = shortened = False
    for _ in range(1000000):
        if waiting(cpu):
            break
        if cpu.pc == NMI['WAIT_NMI']:
            if mode == 'success' and not injected:
                cpu.nmi()
                assert cpu.pc == VSYM['V2V_NMI']
                injected = True
            elif mode == 'timeout' and not shortened:
                memory.ram[NMI['TIME0']] = 0xFE
                memory.ram[NMI['TIME1']] = 0xFF
                memory.ram[NMI['TIME2']] = 0xFF
                shortened = True
        cpu.step()
    else:
        raise AssertionError(f'NMI {mode}: probe did not return to HOLD')
    output = bytes(memory.tx[start_output:])
    assert (b': PASS' in output) == (mode == 'success'), output
    assert (b': TIMEOUT' in output) == (mode == 'timeout'), output
    assert (b'REFUSE:' in output) == (mode == 'busy'), output
    assert memory.ram[0x7E00:0x7E02] == old_pointer
    assert memory.ram[SYM['V2_NMI_HOLD']] == 0
    assert not memory.bank_changes
    lines = [line for line in output.decode('ascii').splitlines() if line]
    result = next(line for line in lines if line.startswith(('V2 NMI', 'REFUSE:')))
    print('nmi-' + mode, result)


def check_native_probe():
    image, entry = read_s19(NATIVE_PATH)
    assert entry == 0x2000
    assert set(image) == set(range(0x2000, NATIVE['PROBE_END']))
    data = lambda start, end: bytes(image[a] for a in range(start, end))
    # CLC/XCE/SEP #$30 enters native 8-bit mode. SEI/SEC/XCE returns to
    # emulation before monitor calls. Both native handlers end in RTI.
    assert data(NATIVE['ENTER_NATIVE'], NATIVE['ENTER_NATIVE']+5) == b'\x18\xfb\xe2\x30\xa9'
    assert data(NATIVE['NATIVE_DONE'], NATIVE['NATIVE_DONE']+3) == b'\x78\x38\xfb'
    assert data(NATIVE['SAFE'], NATIVE['SAFE']+2) == b'\xa2\x05'
    assert data(NATIVE['CLEANUP']+3, NATIVE['CLEANUP']+5) == b'\xa2\x05'
    assert image[NATIVE['NATIVE_NMI_HANDLER']-1] == 0x40
    assert image[NATIVE['SAVED_POINTERS']-1] == 0x40
    assert b'V2 816N BRK/NMI / A-X-Y / FRAME / RTI: PASS' in data(0x2000, NATIVE['PROBE_END'])
    print('816-native static', 'assembled entry/exit, BRK/NMI handlers and RTI: PASS')


def main():
    for mode in ('success', 'timeout', 'busy'):
        run_mode(mode)
    for mode in ('success', 'timeout', 'busy'):
        run_nmi_mode(mode)
    check_native_probe()
    print('PASS: RAM-only BRK/IRQ/NMI probes, native probe structure, cleanup and refusal paths')


if __name__ == '__main__':
    main()
