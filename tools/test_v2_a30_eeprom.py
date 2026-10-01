"""Execute linked a30 EEPROM routines; emulate MCP byte transactions and power cuts."""
import hashlib
import json
import sys
import build_v2_a30 as build

sys.modules['build_v2'] = build
import test_v2_boot as boot

REPORT = json.loads((build.OUT / 'build.json').read_text())
S = REPORT['rtc_symbols']
D = REPORT['display_symbols']


def config(enable=0, bank=0, address=0, delay=10, mode=1):
    data = bytearray([1, enable, bank, address & 255, address >> 8, delay, mode] + [0]*9)
    a = b = 0
    for value in data[:14]:
        a = (a + value) & 255
        b = (b + a) & 255
    data[14:] = bytes([a, b])
    return data


def record(generation=0, **fields):
    data = bytearray([0xA1, generation]) + config(**fields)[1:7] + bytearray(4)
    a = b = 0
    for value in data[1:10]:
        a = (a + value) & 255
        b = (b + a) & 255
    data[10:] = bytes([a, b])
    return data


class PowerCut(Exception):
    pass


class Board(boot.Memory):
    def __init__(self, data=None, present=True):
        super().__init__(3)
        self.eeprom = bytearray(data if data is not None else b'\xff'*128)
        self.present = present
        self.pointer = 0
        self.phase = 0
        self.pending = []
        self.ee_writes = []
        self.cut = None
        self.protected = False
        self.busy = 0
        self.write_busy_polls = 2
        self.busy_forever = False
        self.samples = None
        self.rtc_reads = 0

    def __getitem__(self, addr):
        if addr == 0x7FCF:
            ddr = self.ram[0x7FC3]
            return (self.ram[addr] & ddr) | (0x81 & ~ddr)
        return super().__getitem__(addr)


def ret(cpu):
    cpu.pc = (cpu.stPopWord() + 1) & 65535


class CPU(boot.MPU):
    def step(self):
        m = self.memory
        if self.pc == S['I2START']:
            m.phase = 0
        elif self.pc == S['I2WRITE']:
            ack = m.present
            if m.phase == 0:
                assert self.a in (0xAE, 0xAF), hex(self.a)
                if m.busy or m.busy_forever:
                    ack = False
                    m.busy = max(0, m.busy-1)
                m.phase = 1
            elif m.phase == 1:
                assert self.a < 24, f'Unexpected EEPROM address {self.a:02X}'
                m.pointer = self.a
                m.phase = 2
            else:
                m.pending.append((m.pointer, self.a))
                m.pointer += 1
            self.p = (self.p & ~1) | int(ack)
        elif self.pc == S['I2READ']:
            assert self.y == int(m.pointer == 23), 'Final byte must be NACKed'
            self.a = m.eeprom[m.pointer]
            m.pointer += 1
        elif self.pc == S['I2STOP']:
            for addr, value in m.pending:
                if m.cut == len(m.ee_writes):
                    raise PowerCut
                m.ee_writes.append((addr, value))
                if not m.protected:
                    m.eeprom[addr] = value
                m.busy = m.write_busy_polls
            m.pending.clear()
        elif self.pc == S['RTREAD']:
            if m.samples:
                sample = m.samples[min(m.rtc_reads, len(m.samples)-1)]
                m.ram[S['RTCBUF']:S['RTCBUF']+7] = bytes(sample)
                m.rtc_reads += 1
                self.p |= 1
            else:
                self.p &= ~1
        elif self.pc == S['RTC_WAIT1']:
            self.pc = S['RTC_WAIT2'] + 6
            return
        elif self.pc == REPORT['worker']['V2W_BOOT_DELAY']:
            self.pc = REPORT['worker']['V2W_BOOT_DELAY_DONE']
            return
        else:
            return super().step()
        ret(self)


def machine(data=None, present=True):
    m = Board(data, present)
    cpu = CPU(memory=m, pc=boot.SYM['START'])
    m.cpu = cpu
    boot.hold(cpu)
    return cpu, m


def call(cpu, name, symbols=S):
    cpu.pc = symbols[name]
    cpu.stPushWord(0x3FFF)
    boot.run(cpu, lambda: cpu.pc == 0x4000, limit=1_000_000)
    return bool(cpu.p & 1)


def read(data, expected, present=True):
    cpu, m = machine(data, present)
    ok = call(cpu, 'EE_READ')
    assert m.ram[S['EE_STATE']] == expected, (m.ram[S['EE_STATE']], expected)
    assert ok == (expected >= 3)
    assert not m.ee_writes
    return cpu, m


def main():
    cases = []
    blank = bytearray(b'\xff'*128)
    read(blank, 0, False)
    read(blank, 1)
    bad = blank.copy(); bad[0] = 0
    read(bad, 2)
    data = blank.copy(); data[:12] = record(255, bank=1)
    cpu, m = read(data, 3)
    assert m.ram[0x7D82] == 1
    data[12:24] = record(0, bank=2)
    cpu, m = read(data, 3)
    assert m.ram[0x7D82] == 2
    data[13] ^= 1
    cpu, m = read(data, 4)
    assert m.ram[0x7D82] == 1
    cases.append('empty, unavailable, invalid, recovery and generation wrap')

    for field in range(12):
        for bit in range(8):
            damaged = blank.copy(); damaged[:12] = record(9)
            damaged[field] ^= 1 << bit
            read(damaged, 2)
    for fields in (dict(enable=2), dict(bank=4), dict(delay=9), dict(mode=2),
                   dict(mode=0, address=0x7F00)):
        damaged = blank.copy(); damaged[:12] = record(**fields)
        read(damaged, 2)
    ambiguous = blank.copy(); ambiguous[:12] = record(0)
    ambiguous[12:24] = record(128)
    read(ambiguous, 2)
    ambiguous[12:24] = record(0, bank=1)
    read(ambiguous, 2)
    ambiguous[12:24] = record(0)
    read(ambiguous, 3)
    cases.append('all single-bit corruptions, range checks, ambiguous generations')

    cpu, m = machine()
    m.ram[0x7D80:0x7D90] = config(bank=2, delay=255)
    before = [bytes(b) for b in m.banks]
    assert call(cpu, 'EE_SAVE')
    assert m.eeprom[:12] == record(bank=2, delay=255)
    assert m.eeprom[24:] == blank[24:]
    assert [bytes(b) for b in m.banks] == before
    writes = len(m.ee_writes)
    assert writes == 13
    assert call(cpu, 'EE_SAVE') and len(m.ee_writes) == writes
    m.ram[0x7D80:0x7D90] = config(bank=3)
    assert call(cpu, 'EE_SAVE')
    assert m.eeprom[12:24] == record(1, bank=3)
    old = m.eeprom.copy()
    cases.append('save/readback, alternating slots, unchanged saves, no flash writes')

    for cut in range(13):
        cpu, m = machine(old)
        m.cut = cut
        m.ram[0x7D80:0x7D90] = config(bank=1)
        try:
            call(cpu, 'EE_SAVE')
            raise AssertionError('Expected power interruption')
        except PowerCut:
            pass
        # Discard all CPU/RAM state, preserving only EEPROM.
        cpu2, m2 = machine(m.eeprom)
        assert call(cpu2, 'EE_READ')
        assert m2.ram[0x7D82] == 3
        assert m2.eeprom[12:24] == old[12:24]
        # A torn byte may retain an arbitrary value. Only the old or fully
        # verified new record may be selected after restart.
        address = m.pending[0][0]
        for torn in (0, 0xFF, 0xA1):
            damaged = m.eeprom.copy(); damaged[address] = torn
            cpu3, m3 = machine(damaged)
            assert call(cpu3, 'EE_READ')
            assert m3.ram[0x7D82] in ((1, 3) if cut == 12 else (3,))
    cases.append('cold restart after interruption at every EEPROM write boundary')

    cpu, m = machine(old); m.protected = True
    m.ram[0x7D80:0x7D90] = config(bank=1)
    assert not call(cpu, 'EE_SAVE') and m.eeprom == old
    cpu, m = machine(old); m.busy_forever = True
    assert not call(cpu, 'EE_READ')
    cpu, m = machine(old); m.write_busy_polls = 300
    m.ram[0x7D80:0x7D90] = config(bank=1)
    assert not call(cpu, 'EE_SAVE')
    assert len(m.ee_writes) == 1 and m.eeprom[12:24] == old[12:24]
    assert m.ram[0x7FC3] == 0x5A
    cases.append('write protection and unavailable device fail closed')

    for fields, target, delay in ((dict(bank=0), b'B0 RESET VECTOR', b'1.0 SEC'),
                                  (dict(bank=2, mode=0, address=0xC000, delay=255),
                                   b'B2 $C000', b'25.5 SEC')):
        data = blank.copy(); data[:12] = record(**fields)
        cpu, m = machine(data)
        assert b'    EEPROM    $57  VALID\r\n      AUTOSTART    DISABLED' in m.tx
        assert b'      TARGET       ' + target in m.tx
        assert b'      DELAY        ' + delay in m.tx
    cases.append('aligned settings, fixed/vector targets and decimal delay')

    cpu, m = machine()
    before = [bytes(b) for b in m.banks]
    boot.command(cpu, b'B2\r')
    output = boot.command(cpu, b'C 0 1 V 0A\rY\r')
    assert b'Done' in output, output
    assert m.eeprom[:12] == record(bank=1)
    assert m.ram[boot.SYM['V2_SELECTED']] == 2 and m.bank == 3
    assert [bytes(b) for b in m.banks] == before
    writes = len(m.ee_writes)
    assert b'C 00 01 V 0A' in boot.command(cpu, b'C\r')
    assert len(m.ee_writes) == writes
    boot.command(cpu, b'C 1 0 C000 14\rN\r')
    assert len(m.ee_writes) == writes
    boot.command(cpu, b'C 0 1 V 0A\rY\r')
    assert len(m.ee_writes) == writes
    cases.append('C command confirmation, cancellation, selected-bank preservation and no-op save')

    for present in (True, False):
        data = blank.copy(); data[:12] = record(enable=1, bank=1)
        m = Board(data)
        m.ft245_present = present
        m.banks[1][0x7FFC:0x7FFE] = b'\x00\x90'
        cpu = CPU(memory=m, pc=boot.SYM['START']); m.cpu = cpu
        boot.run(cpu, lambda: m.bank == 1 and cpu.pc == 0x9000, limit=7_000_000)
        assert not m.ee_writes and not m.acia_tx
    m = Board(data); m.rx.extend(b'S')
    cpu = CPU(memory=m, pc=boot.SYM['START']); m.cpu = cpu
    boot.hold(cpu)
    assert m.bank == 3 and b'AUTOSTART    ENABLED' in m.tx
    cases.append('EEPROM autostart with/without USB and S hold')

    cpu, m = machine()
    m.samples = [[0x89, 0x54, 0x17, 0x34, 0x30, 0x09, 0x26],
                 [0x90, 0x54, 0x17, 0x34, 0x30, 0x09, 0x26]]
    m.tx.clear()
    assert call(cpu, 'RTC_ENTRY') is not None
    assert (b'EDU KIT       DETECTED\r\n'
            b'I2C           READY  VIA1 @ $7FC0\r\n  MCP79XXX\r\n'
            b'    RTC       $6F  Wed 26-09-30 17:54:10\r\n'
            b'    SRAM      $6F  64 BYTES\r\n'
            b'    EEPROM    $57  EMPTY\r\n      SETTINGS     NONE') in m.tx
    assert not m.ee_writes
    cases.append('RTC and EEPROM statuses are independently detected')

    for descriptor in (b'\xff'*4, b'RT\x01\x00'):
        m = Board(data)
        m.banks[3][0x6000:0x6004] = descriptor
        cpu = CPU(memory=m, pc=boot.SYM['START']); m.cpu = cpu
        boot.hold(cpu)
        assert m.bank == 3 and not m.ee_writes
        assert b'EDU KIT' not in m.tx
        assert b'EEPROM unavailable' in boot.command(cpu, b'C 0 0 V 0A\r')
    cases.append('absent or alpha25 E extension disables EEPROM calls and autostart')
    receipt = dict(version=build.VERSION, passed=cases,
                   image_sha256=hashlib.sha256(boot.IMAGE).hexdigest(),
                   physical_hardware_tested=False)
    (build.OUT / 'eeprom-test-results.json').write_text(json.dumps(receipt, indent=2)+'\n')
    for case in cases:
        print('PASS:', case)


if __name__ == '__main__':
    main()
