"""Linked F/I against an unlock-sequence, busy-polling banked flash model.

This checks CPU execution and preservation, not physical flash timing/NMI.
"""
import hashlib
import json

from build_v2 import record, STEM, VERSION
from test_v2_boot import Memory, MPU, OUT, IMAGE, REPORT, SYM, command, hold, run, waiting

W = REPORT['worker']
CASES = []


class FlashMemory(Memory):
    def __init__(self, bank):
        super().__init__(bank)
        self.unlock = 0
        self.events = []
        self.busy = None
        self.cpu = None
        self.fault = None
        self.self_changed = False
        self.resident = bank

    def __getitem__(self, address):
        if self.cpu and (self.busy or self.self_changed):
            assert self.cpu.pc < 0x8000, f'ROM execution during/after mutation: {self.cpu.pc:04X}'
        if isinstance(address, int) and address >= 0x8000 and self.busy:
            bank, target, expected, remaining = self.busy
            assert self.bank == bank
            if remaining:
                if self.fault != 'timeout':
                    self.busy = bank, target, expected, remaining - 1
                return expected ^ 0x80
            self.busy = None
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if address < 0x8000:
            return super().__setitem__(address, value)
        assert self.cpu.pc < 0x8000
        # Program data (including F0) has priority over command decoding.
        if self.unlock == 3:
            old = self.banks[self.bank][address-0x8000]
            assert old & value == value, 'program attempted a 0-to-1 transition'
            self.banks[self.bank][address-0x8000] &= value
            self.mutated('program', address, value)
            if self.fault == 'verify':
                self.banks[self.bank][(address-0x8000) ^ 1] ^= 1
            self.busy = self.bank, address, value, 3
            self.unlock = 0
        elif value == 0xF0 and address == 0xD555:
            self.unlock = 0
            self.busy = None
        elif self.unlock in (0, 4) and address == 0xD555 and value == 0xAA:
            self.unlock += 1
        elif self.unlock in (1, 5) and address == 0xAAAA and value == 0x55:
            self.unlock += 1
        elif self.unlock == 2 and address == 0xD555 and value in (0xA0, 0x80):
            self.unlock = 3 if value == 0xA0 else 4
        elif self.unlock == 6 and value == 0x30:
            start = (address & 0xF000) - 0x8000
            self.banks[self.bank][start:start+4096] = b'\xff' * 4096
            self.mutated('erase', address & 0xF000, 0xFF)
            if self.fault == 'erase_verify':
                self.banks[self.bank][start+17] = 0
            self.busy = self.bank, address, 0xFF, 3
            self.unlock = 0
        else:
            raise AssertionError(f'Bad flash sequence state={self.unlock}: {address:04X}={value:02X}')

    def mutated(self, kind, address, value):
        self.events.append((kind, self.bank, address, value))
        if self.bank == self.resident and address >= 0xF000:
            self.self_changed = True


def boot_flash(bank=0):
    mem = FlashMemory(bank)
    cpu = MPU(memory=mem, pc=SYM['START'])
    mem.cpu = cpu
    hold(cpu)
    return cpu, mem


def send(cpu, data, limit=3000000):
    mem = cpu.memory
    start = len(mem.tx)
    mem.rx.extend(data)
    run(cpu, lambda: waiting(cpu), limit=limit)
    return bytes(mem.tx[start:])


def records(start, data, size=252):
    return b''.join((record('1', start+i, data[i:i+size])+'\r\n').encode()
                    for i in range(0, len(data), size))


def finish(entry=0x8000):
    return (record('9', entry)+'\r\n').encode()


def check_f():
    for bank in range(4):
        cpu, mem = boot_flash()
        command(cpu, f'B{bank}\r'.encode())
        confirm = b'Y\rB3\r' if bank == 3 else b'Y\r'
        output = send(cpu, b'F 8123 00 F0\r' + confirm)
        assert b'8123 FF>00' in output and b'Program Y?' in output and b'Done' in output, output
        assert mem.banks[bank][0x123:0x125] == b'\x00\xf0'
        assert [e[0] for e in mem.events] == ['program', 'program']
        before = bytes(mem.banks[bank])
        mem.events.clear()
        output = send(cpu, b'F 8123 FF\r' + confirm)
        expected = bytearray(before); expected[0x123] = 255
        assert bytes(mem.banks[bank]) == expected and b'Erase+write' in output
        assert mem.events[0][0] == 'erase' and mem.bank == 0
        mem.events.clear()
        assert b'Done' in send(cpu, b'F 8123 FF\r' + confirm) and not mem.events
        for bad, error in [(b'F 8FFF 00 00\r', b'Sector span'),
                           (b'F FFFF 00 00\r', b'Sector span'),
                           (b'F 7FFF 00\r', b'Protected'),
                           (b'F 8000 GG\r', b'Bad hex'),
                           (b'F 8000 00\rN\r', b'Canceled')]:
            assert error in send(cpu, bad)
            assert not mem.events
    CASES.append('F all banks: direct/no-op/erase edits, neighbor preservation, previews, confirmation and full preflight')


def check_f_boundaries():
    cpu, mem = boot_flash()
    command(cpu, b'B3\r')
    before = bytes(mem.banks[3])
    output = send(cpu, b'F FFFF 00\rY\rB3\r')
    assert b'Bank 3 edit' in output and b'Self edit' not in output
    assert b'May not boot/function' in output and b'Type B3>' in output
    assert mem.banks[3][:-1] == before[:-1] and mem.banks[3][-1] == 0
    output = send(cpu, b'F EFF0 00\rY\rB3\r')
    assert b'Done' in output and mem.banks[3][0x6FF0] == 0
    output = send(cpu, b'F 80FE 01 02 03 04\rY\rB3\r')
    assert b'8101 FF>04' in output and mem.banks[3][0xFE:0x102] == b'\x01\x02\x03\x04'
    # Multi-byte preflight failure and rejected confirmation never write a prefix.
    mem.events.clear()
    for line in (b'F 8000 00 GG\r', b'F 8000 00\rYES\r', b'F 8000 00\rY\x03'):
        send(cpu, line)
        assert not mem.events
    send(cpu, b'F 8000 00\rY\rB2\r')
    assert not mem.events
    # Sector F requires the exact selected bank even outside Bank 3.
    cpu, mem = boot_flash()
    command(cpu, b'B2\r')
    send(cpu, b'F FFFF 00\rY\rB1\r')
    assert not mem.events and mem.banks[2][-1] == 0xFF
    CASES.append('F recovery vectors/FFFF, raw configuration, page crossing, malformed suffix and confirmation rejection')


def check_install():
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    payload = bytes((i*37) & 255 for i in range(8192))
    mem.banks[1][:8192] = b'\x00' * 8192
    output = send(cpu, b'I 8000 9FFF\rY\r' + records(0x8000, payload) + finish(), limit=5000000)
    assert b'Done' in output, output[-200:]
    assert mem.banks[1][:8192] == payload
    assert len([e for e in mem.events if e[0] == 'erase']) == 2
    assert mem.bank == 0 and not mem.ram[SYM['V2_NMI_HOLD']]
    # Configuration bytes are preserved even though the stream covers them.
    for bank in range(4):
        cpu, mem = boot_flash()
        command(cpu, f'B{bank}\r'.encode())
        config = bytes(range(16))
        mem.banks[bank][0x6FF0:0x7000] = config
        payload = b'\x55' * 4096
        output = send(cpu, b'I E000 EFFF\rY\r' + records(0xE000, payload) + finish(0xE000))
        assert b'Done' in output, output[-200:]
        assert mem.banks[bank][0x6000:0x6FF0] == payload[:-16]
        assert mem.banks[bank][0x6FF0:0x7000] == (config if bank == 0 else payload[-16:])
    # Guest top and FFFF are legal; own/recovery top are covered separately.
    cpu, mem = boot_flash()
    command(cpu, b'B2\r')
    output = send(cpu, b'I F000 FFFF\rY\r' + records(0xF000, b'\xA5'*4096) + finish(0xF000))
    assert b'Done' in output and mem.banks[2][0x7000:] == b'\xA5'*4096
    CASES.append('I dense ascending cross-sector records, full-sector verification, guest top/FFFF, configuration preservation')


def check_install_rejections():
    for resident in range(4):
        for target in (resident, 3):
            cpu, mem = boot_flash(resident)
            command(cpu, f'B{target}\r'.encode())
            assert b'Protected' in send(cpu, b'I E000 FFFF\r')
            assert not mem.events
    cpu, mem = boot_flash()
    for line in (b'I 8001 8FFF\r', b'I 8000 8FFE\r', b'I 7000 8FFF\r', b'I 9000 8FFF\r'):
        assert b'Bad range' in send(cpu, line)
        assert not mem.events
    command(cpu, b'B1\r')
    for stream, error in ((records(0x8001, b'X'), b'Bad S19'),
                          (records(0x8000, b'X')+finish(), b'Bad S19'),
                          (records(0x8000, b'X')+records(0x8000, b'X'), b'Bad S19'),
                          (records(0x8000, b'X')[:-4]+b'00\r\n', b'Bad checksum'),
                          (b'\x03', b'Canceled')):
        output = send(cpu, b'I 8000 8FFF\rY\r' + stream)
        assert error in output, output
        assert not mem.events
    # Early complete sectors stay committed when a later record fails.
    stream = records(0x8000, b'\x55'*4096) + records(0x9001, b'X')
    output = send(cpu, b'I 8000 9FFF\rY\r' + stream)
    assert b'Bad S19' in output
    assert mem.banks[1][:4096] == b'\x55'*4096
    assert mem.banks[1][4096:8192] == b'\xff'*4096
    CASES.append('I own/recovery protection, alignment/order/checksum/completeness rejection, prior committed sectors retained')


def check_install_image_and_failure():
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    image = (OUT / f'{STEM}-e000-ffff.s19').read_bytes()
    output = send(cpu, b'I E000 FFFF\rY\r' + image)
    assert b'Done' in output and mem.banks[1][0x6000:] == IMAGE
    output = command(cpu, b'J1\r')
    assert f'STR8-N {VERSION} B1'.encode() in output and mem.bank == 1
    output = command(cpu, b'J0\r')
    assert f'STR8-N {VERSION} B0'.encode() in output and mem.bank == 0
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    mem.fault = 'timeout'
    output = send(cpu, b'I 8000 8FFF\rY\r' + records(0x8000, b'\x11'*4096) + finish())
    assert b'Flash timeout' in output and b'Done' not in output
    assert mem.bank == 0 and not mem.busy
    assert len(mem.events) == 1
    CASES.append('I installs the actual alpha image, boots it and returns; I flash failure drains input and restores resident')


def check_cancellation():
    cpu, mem = boot_flash()
    assert b'Canceled' in send(cpu, b'F 8000 00\r\x03') and not mem.events
    # Cancellation while an erase/rewrite is active must restore all neighbors.
    mem.banks[0][:4096] = b'\x33'*4096
    mem.rx.extend(b'F 8123 FF\rY\r')
    run(cpu, lambda: cpu.pc == W['V2W_PROGRAM'], limit=300000)
    assert mem.events[0][0] == 'erase'
    mem.rx.extend(b'\x03')
    run(cpu, lambda: waiting(cpu), limit=2000000)
    expected = bytearray(b'\x33'*4096); expected[0x123] = 255
    assert mem.banks[0][:4096] == expected and b'Canceled' in mem.tx
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    # Supply exactly one sector and inject cancel while it is programmed.
    mem.rx.extend(b'I 8000 9FFF\rY\r' + records(0x8000, b'\x11'*4096))
    run(cpu, lambda: cpu.pc == W['V2W_PROGRAM'], limit=1000000)
    mem.rx.extend(b'\x03')
    run(cpu, lambda: waiting(cpu), limit=2000000)
    assert mem.banks[1][:4096] == b'\x11'*4096
    assert mem.banks[1][4096:8192] == b'\xff'*4096
    assert b'Canceled' in mem.tx and mem.bank == 0
    CASES.append('Ctrl-C before confirmation and during F/I mutation: current sector finishes, next sector untouched')


def check_failures_and_self():
    for fault, text in [('timeout', b'Flash timeout'), ('verify', b'Bad verify'), ('erase_verify', b'Bad verify')]:
        cpu, mem = boot_flash()
        command(cpu, b'B1\r')
        mem.fault = fault
        if fault == 'erase_verify':
            mem.banks[1][0] = 0
            line = b'F 8000 FF\rY\r'
        elif fault == 'verify':
            # Damage an earlier, already-visited byte; only the final sweep
            # can detect this after the programmed byte polls successfully.
            line = b'F 8001 00\rY\r'
        else:
            line = b'F 8000 00\rY\r'
        output = send(cpu, line, limit=3000000)
        assert text in output, output
        assert mem.bank == 0 and not mem.busy and not mem.ram[SYM['V2_NMI_HOLD']]
    # An erase defect that already matches the desired image need not abort.
    # All differing bytes must still be programmable, and the whole result exact.
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    mem.banks[1][:4096] = b'\x00' * 4096
    mem.fault = 'erase_verify'
    output = send(cpu, b'F 8000 FF\rY\r')
    assert b'Done' in output
    assert mem.banks[1][:4096] == b'\xff' + b'\x00' * 4095
    for resident in range(4):
        for value in (0, 255):
            cpu, mem = boot_flash(resident)
            mem.rx.extend(f'F {SYM["START"]:04X} {value:02X}\rY\rB{resident}\r'.encode())
            run(cpu, lambda: cpu.pc == W['V2W_RESET_WAIT'], limit=2000000)
            assert b'Self edit' in mem.tx and b'May not boot/function' in mem.tx
            assert b'OK; press Y to soft reset' in mem.tx
            assert mem.banks[resident][SYM['START']-0x8000] == value
            assert mem.bank == resident and cpu.pc < 0x8000
    cpu, mem = boot_flash()
    mem.fault = 'timeout'
    mem.rx.extend(f'F {SYM["START"]:04X} 00\rY\rB0\r'.encode())
    run(cpu, lambda: cpu.pc == W['V2W_RESET_WAIT'], limit=3000000)
    assert b'Flash fail; press Y to soft reset' in mem.tx
    # A harmless no-op self edit proves the RAM-only prompt can initiate a
    # CPU-level reset and return through the newly written fixed F000 entry.
    cpu, mem = boot_flash(1)
    safe = SYM['V2_END']
    mem.rx.extend(f'F {safe:04X} FF\rY\rB1\r'.encode())
    run(cpu, lambda: cpu.pc == W['V2W_RESET_WAIT'], limit=2000000)
    mem.rx.extend(b'Y')
    run(cpu, lambda: waiting(cpu), limit=1000000)
    assert mem.tx.count(f'STR8-N {VERSION} B1'.encode()) == 2
    assert bytes(mem.tx).endswith(b'B1> ')
    cpu, mem = boot_flash()
    command(cpu, b'B1\r')
    mem.banks[1][0] = 0
    mem.fault = 'timeout'
    output = send(cpu, b'F 8000 FF\rY\r', limit=6000000)
    assert b'Flash timeout' in output and mem.bank == 0 and not mem.busy
    CASES.append('bounded timeout/verify failures, bank restoration; risky confirmations and RAM-only self-edit soft reset')


def main():
    for test in (check_f, check_f_boundaries, check_install, check_install_rejections,
                 check_install_image_and_failure, check_cancellation, check_failures_and_self):
        test()
        print('PASS:', CASES[-1], flush=True)
    (OUT / 'flash-test-results.json').write_text(json.dumps({
        'passed': CASES, 'image_sha256': hashlib.sha256(IMAGE).hexdigest(),
        'physical_hardware_tested': False,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
