"""Execute linked v2 code with banked flash and FT245/VIA host models.

Requires py65 (same dependency as v1 worker tests). Models logical bank and
console behavior, not electrical timing. Native 816 interrupt execution and
physical reset selection still require hardware qualification.
"""
from collections import deque
from pathlib import Path
import hashlib
import json
import os
import sys

from build_v2 import OUT, ROOT, STEM, VERSION, RESIDENT_START, PUBLIC_CALLS, read_s19, symbols

for directory in reversed([
    *(Path(p) for key in ('STR8_TEST_DEPS', 'PY65_PATH')
      for p in os.environ.get(key, '').split(os.pathsep) if p),
    *sorted((ROOT / 'BUILD').glob('v*/local/test-deps'), reverse=True),
]):
    if (directory / 'py65').is_dir():
        sys.path.insert(0, str(directory))
try:
    from py65.devices.mpu65c02 import MPU
    from py65.disassembler import Disassembler
except ImportError as error:
    raise SystemExit('py65 is required; set STR8_TEST_DEPS to its parent directory') from error

REPORT = json.loads((OUT / 'build.json').read_text())
SYM, VSYM = REPORT['resident'], REPORT['vectors']
IMAGE = (OUT / f'{STEM}-e000-ffff.bin').read_bytes()
PATTERNS = (0xCC, 0xCE, 0xEC, 0xEE)
CASES = []


class Memory:
    def __init__(self, bank):
        self.ram = bytearray([0x5A] * 0x8000)
        self.banks = [bytearray(b'\xff' * 0x8000) for _ in range(4)]
        self.banks[bank][0x6000:] = IMAGE
        self.bank = bank
        self.ram[0x7FEC] = PATTERNS[bank]
        self.ram[0x7FE0] = 0x0C
        self.ram[0x7FE3] = 0
        self.rx, self.tx = deque(), bytearray()
        self.tx_blocked = False
        self.writes = []
        self.bank_changes = []
        self.io_reads = []

    def __getitem__(self, address):
        if isinstance(address, slice):
            return [self[a] for a in range(*address.indices(65536))]
        if 0x7F00 <= address < 0x8000:
            self.io_reads.append(address)
        if address >= 0x8000:
            return self.banks[self.bank][address-0x8000]
        if address == 0x7FE0:
            return (self.ram[address] & ~3) | (0 if self.rx else 2) | 0x20 | int(self.tx_blocked)
        if address == 0x7FE1 and not self.ram[0x7FE3]:
            return self.rx[0] if self.rx else 0
        return self.ram[address]

    def __setitem__(self, address, value):
        value &= 255
        self.writes.append(address)
        if address >= 0x8000:
            raise AssertionError(f'Unexpected flash write B{self.bank}:{address:04X}')
        old = self.ram[address]
        self.ram[address] = value
        if address == 0x7FEC:
            self.bank = (0 if value & 0x0E == 0x0C else 1) | (
                0 if value & 0xE0 == 0xC0 else 2)
            self.bank_changes.append(self.bank)
        elif address == 0x7FE0:
            if not old & 8 and value & 8 and self.rx:
                self.rx.popleft()
        elif address == 0x7FE3 and value == 255 and self.ram[0x7FE0] & 4:
            self.tx.append(self.ram[0x7FE1])


def run(cpu, stop, limit=100000):
    for _ in range(limit):
        if stop():
            return
        cpu.step()
    raise AssertionError(f'Execution limit at B{cpu.memory.bank}:{cpu.pc:04X}')


def waiting(cpu):
    return (cpu.pc in (SYM['V2_GETC'], SYM['V2_GETC_WAIT'])
            and not cpu.memory.rx and not cpu.memory.ram[SYM['V2_RX_COUNT']]
            and not cpu.memory.ram[SYM['V2_CANCEL_REQUEST']])


def hold(cpu):
    run(cpu, lambda: waiting(cpu), limit=300000)


def boot(bank, reset_pcr=False):
    memory = Memory(bank)
    if reset_pcr:
        assert bank == 3
        memory.ram[0x7FEC] = 0
    cpu = MPU(memory=memory, pc=SYM['START'])
    cpu.p |= cpu.DECIMAL
    hold(cpu)
    assert memory.bank == bank
    assert all(memory.ram[SYM[name]] == bank for name in ('V2_RESIDENT', 'V2_SELECTED', 'V2_TARGET'))
    assert f'STR8-N {VERSION} B{bank}\r\nB{bank}> '.encode() in memory.tx
    assert not memory.bank_changes
    assert memory.ram[:0xE0] == bytes([0x5A])*0xE0
    assert memory.ram[0x0200:0x6900] == bytes([0x5A])*0x6700
    assert not cpu.p & cpu.DECIMAL
    assert cpu.p & cpu.INTERRUPT
    worker_end = REPORT['worker']['V2W_END']
    image_start = SYM['V2_WORKER_IMAGE'] - 0xE000
    assert memory.ram[0x7900:worker_end] == IMAGE[image_start:image_start+worker_end-0x7900]
    assert memory.ram[worker_end:0x7C00] == b'\x5a' * (0x7C00-worker_end)
    for base in (0x7E00, 0x7E10):
        assert memory.ram[base:base+10] == VSYM['V2V_DEFAULT'].to_bytes(2, 'little')*5
    return cpu, memory


def command(cpu, text):
    memory = cpu.memory
    start = len(memory.tx)
    memory.rx.extend(text)
    hold(cpu)
    return bytes(memory.tx[start:])


def check_boot_and_input():
    for bank in range(4):
        cpu, mem = boot(bank)
        for line, expected in [(b'?\r\n', b'C [0|1 0-3 addr delay]'),
                               (b'X\n', b'Bad cmd'),
                               (b'J4\r', b'Bad bank'),
                               (b'J\r', b'Bad bank'),
                               (b'J0X\r', b'Bad bank'),
                               (b'J0' + b'X'*40 + b'\r', b'Long line'),
                               (b'?\x08?\r', b'C [0|1 0-3 addr delay]')]:
            output = command(cpu, line)
            assert expected in output, (line, output)
            assert mem.bank == bank and not mem.bank_changes
        assert b'Bad' not in command(cpu, b'J0\x03\r')
        # Software entry preserves user-owned vector pointers and code.
        mem.ram[0x7E00:0x7E02] = b'\x00\x02'
        before = bytes(mem.ram[0x7E00:0x7F00])
        cpu.pc = SYM['V2_PROMPT_ENTRY']
        hold(cpu)
        assert mem.ram[0x7E00:0x7F00] == before
    boot(3, reset_pcr=True)
    CASES.append('startup in all four overlays, reset-input PCR, line parsing, prompt reentry')


def check_handoffs():
    for resident in range(4):
        for target in range(4):
            cpu, mem = boot(resident)
            # Include non-bank PCR edge bits, which selection must preserve.
            mem.ram[0x7FEC] |= 0x11
            mem.banks[target][0x7FFC:0x7FFE] = b'\x00\x90'
            mem.rx.extend(f'j{target}\r'.encode())
            run(cpu, lambda: cpu.pc == 0x9000 and mem.bank == target)
            assert cpu.sp == 255 and cpu.p & cpu.INTERRUPT and not cpu.p & cpu.DECIMAL
            assert mem.ram[0x7FEC] & 0x11 == 0x11
            assert mem.ram[0x7FA0] == 0
        for vector in (0xFFFF, 0x0000, 0x7FFF):
            cpu, mem = boot(resident)
            target = (resident + 1) % 4
            mem.banks[target][0x7FFC:0x7FFE] = vector.to_bytes(2, 'little')
            output = command(cpu, f'J{target}\r'.encode())
            assert b'Bad vector' in output
            assert mem.bank == resident and mem.bank_changes[-1] == resident
    CASES.append('16 bank handoffs; invalid/erased vectors restore every resident bank')


def check_vectors():
    cpu, mem = boot(0)
    for original_sp in (0xFF, 0x03, 0x02, 0x01, 0x00):
        for is_brk in (False, True):
            cpu.sp = original_sp
            cpu.a, cpu.x, cpu.y = 0xA5, 0x39, 0xC7
            cpu.stPushWord(0x2345)
            status = 0x30 if is_brk else 0x20
            cpu.stPush(status)
            sp_at_entry = cpu.sp
            mem.ram[0x7E02:0x7E06] = b'\x00\x02\x00\x03'
            cpu.pc = VSYM['V2V_IRQ_BRK']
            target = 0x0200 if is_brk else 0x0300
            run(cpu, lambda: cpu.pc == target)
            assert (cpu.a, cpu.x, cpu.y, cpu.sp) == (0xA5, 0x39, 0xC7, sp_at_entry)
            assert cpu.stPop() == status
            assert cpu.stPopWord() == 0x2345
    for name, slot in [('V2V_NATIVE_COP', 0x7E10), ('V2V_NATIVE_BRK', 0x7E12),
                       ('V2V_NATIVE_ABORT', 0x7E14), ('V2V_NATIVE_NMI', 0x7E16),
                       ('V2V_NATIVE_IRQ', 0x7E18)]:
        addr = VSYM[name]
        assert bytes(mem[addr:addr+3]) == b'\x6c' + slot.to_bytes(2, 'little')
    CASES.append('IRQ/BRK register/frame preservation including stack wrap; native stub encoding')


def check_image_and_instructions():
    memory, entry = read_s19(OUT / f'{STEM}-e000-ffff.s19')
    assert entry == SYM['START'] and set(memory) == set(range(0xE000, 0x10000))
    assert bytes(memory[a] for a in range(0xF000, 0xF004)) == b'SN\x02\x00'
    assert SYM['START'] == RESIDENT_START + 4 and SYM['V2_PROMPT_ENTRY'] == RESIDENT_START + 7
    for index, (public, label, target) in enumerate(PUBLIC_CALLS):
        address = RESIDENT_START + 4 + 3*index
        assert SYM[public] == SYM[label] == address
        assert bytes(memory[a] for a in range(address, address+3)) == b'\x4c' + SYM[target].to_bytes(2, 'little')
    assert bytes(memory[a] for a in range(0xE000, 0x10000)) == IMAGE
    assert bytes(memory[a] for a in range(0xEFF0, 0xF000)) == b'\xff'*16
    assert SYM['V2_END'] <= 0xFE00
    assert bytes(memory[a] for a in range(0xFE00, 0xFF00)) == b'\xff'*256
    assert bytes(memory[a] for a in range(SYM['V2_END'], 0xFFE0)) == b'\xff' * (0xFFE0-SYM['V2_END'])
    for address in (0xFFE0, 0xFFE2, 0xFFEC, 0xFFF0, 0xFFF2, 0xFFF6):
        assert bytes(memory[a] for a in range(address, address+2)) == b'\xff\xff'
    cpu, mem = boot(3)
    dis = Disassembler(cpu)
    worker = REPORT['worker']
    for start, end in [(SYM['START'], SYM['V2_COMMAND_KEYS']),
                       (0x7900, worker['V2W_BITS']),
                       (worker['V2W_BEGIN'], worker['V2W_OK_TEXT']),
                       (worker['V2W_GETC'], worker['V2W_END']),
                       (0x7E20, VSYM['V2V_END'])]:
        pc = start
        while pc < end:
            length, instruction = dis.instruction_at(pc)
            mnemonic = instruction.split()[0]
            assert mnemonic != '???' and not mnemonic.startswith(('RMB', 'SMB', 'BBR', 'BBS'))
            pc += length
        assert pc == end
    CASES.append('dense S19, disabled config, reserved vectors, common-instruction audit')


def check_v135_roundtrip():
    release = ROOT / 'BUILD/v1.35'
    for relative in ('bin/str8n-v1.35-bank3-f000-ffff.bin', 'map/str8n-v1.35-f000.map'):
        if not (release / relative).is_file():
            raise SystemExit('v1.35 baseline artifacts required for roundtrip: run make programmer-bin')
    v1image = (release / 'bin/str8n-v1.35-bank3-f000-ffff.bin').read_bytes()
    v1 = symbols(release / 'map/str8n-v1.35-f000.map')
    for bank in range(3):
        mem = Memory(bank)
        mem.banks[3][0x7000:] = v1image
        # Model a COMPLETE row produced by v1.35 installation, not a v2 record.
        row = bytearray(b'\xff'*16)
        row[0], row[4:9], row[9], row[12] = 1, b'V2---', 0xFE, 0xFC
        offset = 0x7FB0 + bank*16
        mem.banks[3][offset:offset+16] = row
        original_flash = [bytes(b) for b in mem.banks]
        mem.bank = 3
        mem.ram[0x7FEC] = PATTERNS[3]
        mem.ram[v1['STR8_JUMP_BANK']] = bank
        cpu = MPU(memory=mem, pc=v1['STR8_JUMP_BANK_LAUNCH'])
        cpu.sp = 255
        hold(cpu)
        assert mem.bank == bank and mem.ram[0x7D00] == bank
        assert f'STR8-N {VERSION} B{bank}'.encode() in mem.tx
        # Real v2 J3 and real v1 reset startup. Skip only long calibrated delay.
        mem.rx.extend(b'J3\rS')
        for _ in range(300000):
            if mem.bank == 3 and cpu.pc == v1['STR8_READ_LINE']:
                break
            if mem.bank == 3 and cpu.pc == v1['STR8_DELAY_FIXED_A']:
                cpu.pc = (cpu.stPopWord() + 1) & 65535
            else:
                cpu.step()
        else:
            raise AssertionError(f'v1 roundtrip failed at {cpu.pc:04X}')
        assert b'STR8-N 1.35' in mem.tx
        assert [bytes(b) for b in mem.banks] == original_flash
    CASES.append('actual v1.35 gated J0/J1/J2 into v2 and v2 J3 back to v1 prompt (delays bypassed)')


def check_compact_messages():
    messages = json.loads((ROOT / 'src/v2/str8n-v2-text.json').read_text())
    cpu, mem = boot(0)
    for index, message in enumerate(messages):
        start = len(mem.tx)
        cpu.sp = 255
        cpu.stPushWord(0x01FF)
        cpu.x = index
        cpu.pc = SYM['V2_PRINT']
        run(cpu, lambda: cpu.pc == 0x0200)
        expected = message['text'].replace('{version}', VERSION).encode('ascii')
        if index < SYM['V2_BAD_PREFIX']:
            expected = expected[4:]  # V2_MESSAGE emits the shared prefix.
        assert mem.tx[start:] == expected, (index, message)
        assert cpu.x == index and cpu.sp == 255
    cpu, mem = boot(0)
    output = command(cpu, b'B1\rB\rJ\r?X\r?\r')
    assert output.count(b'Bad bank') == 2
    assert b'Bad cmd' in output and b'J0-J3 boot  ? help' in output
    assert mem.bank == 0 and mem.ram[SYM['V2_SELECTED']] == 1
    CASES.append('all packed messages print exactly across page boundaries; stale bank suffixes and table dispatch stay safe')


def main():
    for test in (check_boot_and_input, check_handoffs, check_vectors,
                 check_image_and_instructions, check_v135_roundtrip, check_compact_messages):
        test()
        print('PASS:', CASES[-1])
    (OUT / 'test-results.json').write_text(json.dumps({
        'passed': CASES, 'image_sha256': hashlib.sha256(IMAGE).hexdigest(),
        'physical_hardware_tested': False, 'native_816_execution_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
