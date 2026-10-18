"""Execute the complete adapter/engine against a digital VIA/I2C model."""
import hashlib
import json
import unittest

from build_v2_crypto_adapter import OUT, ROOT
from build_v2_crypto_status import crc
from test_v2_crypto_status import packet, RESPONSES, SERIAL
from test_v2_rtc import MPU

TIMINGS = {}


class Bus:
    def __init__(self, *, mhz=8, present=True, rtc_present=True, configured=True,
                 stuck=None, clock_fault=None, responses=None, busy_reads=0,
                 nack_payload=None, wake_reply=None, sleep_nack=False):
        self.meta = json.loads((OUT / 'build.json').read_text())
        self.s = self.meta['symbols']
        self.ram = bytearray(65536)
        image = (OUT / 'crypto-adapter.bin').read_bytes()
        assert hashlib.sha256(image).hexdigest() == self.meta['sha256']
        for path, digest in self.meta['sources'].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
        self.ram[0x2000:0x2000+len(image)] = image
        rtc = (OUT / 'rtc-fixture.bin').read_bytes()
        self.ram[0x3000:0x3000+len(rtc)] = rtc
        self.ram[0x7d04:0x7d0c] = bytes.fromhex('5356010f0065ff64')
        self.ram[0x7d0c] = 0xff
        self.ram[0x7d27] = 1
        gateway = (OUT / 'gateway-fixture.bin').read_bytes()
        self.ram[0x6500:0x6500+len(gateway)] = gateway
        for name, digest in self.meta['fixtures'].items():
            assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest
        self.ram[0x6664] = 3
        self.ram[self.s['CA_MHZ']] = mhz
        self.ram[self.s['CA_ADDRESS']] = 0x60
        self.ram[self.s['CA_ENABLE']] = 0xa5 if configured else 0
        self.ddr, self.latch = 0x7e, 0x54
        self.initial_ddr, self.initial_latch = self.ddr, self.latch
        self.present, self.rtc_present = present, rtc_present
        self.stuck, self.clock_fault = stuck, clock_fault
        self.nack_payload, self.sleep_nack = nack_payload, sleep_nack
        self.responses = list(RESPONSES if responses is None else responses)
        self.wake_reply = bytes.fromhex('04113343') if wake_reply is None else wake_reply
        self.busy_reads, self.poll_left = busy_reads, 0
        self.mhz, self.cpu = max(mhz, 1), None
        self.mode, self.phase = 'idle', 'address'
        self.bit = self.value = self.pointer = 0
        self.slave_low = False
        self.selected, self.ack, self.after_ack = None, False, 'rx'
        self.current = []
        self.addresses, self.commands, self.nacks, self.pin_writes = [], [], [], []
        self.awake, self.pending = False, b''
        self.read_packet = b''
        self.command_index = -1
        self.sleeps, self.wakes = 0, []
        self.starts = self.stops = self.scl_edges = 0
        self.start_cycle = 0
        self.recovery_end = 0
        self.read_cycle = None
        self.wake_release = None
        self.wait_start = None
        self.wait_durations = []
        self.regs = bytearray(32)
        self.regs[:9] = bytes.fromhex('d859232a3112260000')
        self.rtc_pointer = 0
        self.rtc_writes = []
        self.lock_events = []
        self.low_start = None
        self.gateway_attempts = 0
        self.try_gateway = False
        self.inject_nmi = False
        self.injected = False
        self.ram[0xfffa:0xfffc] = bytes.fromhex('0018')
        self.ram[0x1800] = 0x40  # Model NMI handler: RTI, no device access.

    @property
    def cycles(self):
        return self.cpu.processorCycles if self.cpu else 0

    def levels(self):
        return (~self.ddr | self.latch) & 0x81

    def __getitem__(self, a):
        if isinstance(a, slice):
            return self.ram[a]
        if a == 0x7fc3:
            return self.ddr
        if a == 0x7fcf:
            value = (self.latch & self.ddr) | (0x81 & ~self.ddr)
            if self.slave_low or self.stuck == 'sda':
                value &= ~0x80
            fault = self.clock_fault and self.clock_fault(self)
            if self.stuck == 'scl' or fault:
                value &= ~1
            return value
        return self.ram[a]

    def __setitem__(self, a, v):
        if isinstance(a, slice):
            self.ram[a] = v
            return
        if a not in (0x7fc3, 0x7fcf):
            assert a < 0x7f00, f'Unexpected hardware/flash write {a:04X}'
            if a == 0x6660:
                self.lock_events.append(v)
            self.ram[a] = v
            return
        assert self.ram[0x6660] == 1 or self.cpu.pc >= 0x3000, 'VIA access without ownership'
        self.pin_writes.append((self.cycles, a, v))
        old = self.levels()
        if a == 0x7fc3:
            self.ddr = v
        else:
            self.latch = v
        assert not self.ddr & self.latch & 0x81, 'I2C output driven high'
        new = self.levels()
        # Unrelated driven VIA outputs must never glitch.
        assert (self.ddr & 0x7e) == (self.initial_ddr & 0x7e)
        assert self.latch & self.ddr & 0x7e == self.initial_latch & self.initial_ddr & 0x7e
        if self.stuck:
            return
        if old & 1 and new & 1 and (old ^ new) & 0x80:
            if not new & 0x80:
                self.start_cycle, self.scl_edges = self.cycles, 0
                self.starts += 1
                self.mode, self.phase = 'rx', 'address'
                self.bit = self.value = 0
                self.current = []
                self.slave_low = False
            else:
                duration = self.cycles - self.start_cycle
                if not self.scl_edges and duration >= 60 * self.mhz:
                    self.wakes.append(duration)
                    self.awake = self.present
                    self.pending = self.wake_reply
                    self.recovery_end = self.cycles + 20000 * self.mhz
                    self.wake_release = self.cycles
                    self.read_cycle = None
                else:
                    self.finish_write()
                self.stops += 1
                self.mode, self.slave_low = 'idle', False
            return
        if not old & 1 and new & 1:
            self.scl_edges += 1
            self.rising(bool(new & 0x80))
        elif old & 1 and not new & 1:
            self.falling()

    def finish_write(self):
        if self.selected != 0x60 or not self.current:
            return
        if self.current == [1]:
            self.sleeps += 1
            self.awake = False
            self.pending = b''
        elif self.current[0] == 3 and len(self.current) == 8:
            command = bytes(self.current)
            assert crc(command[1:-2]) == command[-2:]
            assert command[2] in (0x30, 0x02), 'Forbidden crypto command'
            assert command[3] == 0, 'Non-public read/mode'
            self.commands.append(command)
            self.command_index += 1
            self.pending = self.responses[self.command_index]
            self.poll_left = self.busy_reads

    def rising(self, sda):
        if self.mode == 'rx':
            self.value = self.value << 1 | int(sda)
            self.bit += 1
            if self.bit != 8:
                return
            value = self.value
            self.after_ack = 'rx'
            if self.phase == 'address':
                self.addresses.append(value)
                self.selected = value >> 1
                self.ack = self.rtc_present if self.selected == 0x6f else (
                    self.selected == 0x60 and self.present and self.awake)
                if value & 1:
                    if self.selected == 0x60:
                        if self.read_cycle is None:
                            self.read_cycle = self.start_cycle
                            assert self.start_cycle >= self.recovery_end, 'Wake recovery too short'
                        if self.poll_left:
                            self.poll_left -= 1
                            self.ack = False
                        self.read_packet = self.pending
                    else:
                        self.read_packet = self.regs[self.rtc_pointer:]
                    self.pointer = 0
                    self.after_ack = 'tx'
                self.phase = 'payload'
            else:
                self.ack = True
                if self.selected == 0x60:
                    if self.nack_payload == (self.command_index + 1, len(self.current)):
                        self.ack = False
                    if self.sleep_nack and value == 1 and not self.current:
                        self.ack = False
                    if self.ack:
                        self.current.append(value)
                elif not self.current:
                    self.rtc_pointer = value
                    self.current.append(value)
                else:
                    self.rtc_writes.append((self.rtc_pointer, value))
                    self.regs[self.rtc_pointer] = value
                    self.rtc_pointer += 1
            self.mode = 'rx-ack-prep'
        elif self.mode == 'rx-ack':
            self.mode = 'rx-ack-done'
        elif self.mode == 'tx':
            self.bit += 1
        elif self.mode == 'tx-ack':
            self.ack = not sda
            self.nacks.append((self.selected, self.pointer, self.ack))
            self.mode = 'tx-ack-done'

    def tx_byte(self):
        return self.read_packet[self.pointer] if self.pointer < len(self.read_packet) else 0xff

    def falling(self):
        if self.mode == 'rx-ack-prep':
            self.slave_low, self.mode = self.ack, 'rx-ack'
        elif self.mode == 'rx-ack-done':
            self.slave_low = False
            self.mode = self.after_ack if self.ack else 'idle'
            self.bit = self.value = 0
            if self.mode == 'tx':
                self.slave_low = not bool(self.tx_byte() & 0x80)
        elif self.mode == 'tx':
            if self.bit == 8:
                self.slave_low, self.mode = False, 'tx-ack'
            else:
                self.slave_low = not bool(self.tx_byte() & (0x80 >> self.bit))
        elif self.mode == 'tx-ack-done':
            self.pointer += 1
            self.bit = 0
            self.mode = 'tx' if self.ack else 'idle'
            self.slave_low = self.ack and not bool(self.tx_byte() & 0x80)

    def byte(self, name):
        return self.ram[self.s[name]]

    def get(self, name, count):
        start = self.s[name]
        return bytes(self.ram[start:start+count])

    def run(self, entry=0x2000, flags=0x28):
        self.cpu = MPU(memory=self, pc=entry)
        self.cpu.p, self.cpu.sp = flags, 0xfd
        self.cpu.stPushWord(0x01ff)
        before = bytes(self.ram)
        for steps in range(2000000):
            if self.cpu.pc == 0x0200:
                break
            if self.try_gateway and self.cpu.pc == self.s['HAL_WAIT']:
                self.gateway_attempt()
            if entry == 0x2000 and self.cpu.pc == self.s['HAL_WAIT']:
                self.wait_start = self.cycles
            if entry == 0x2000 and self.cpu.pc == self.s['HAL_RECEIVE'] and self.wait_start is not None:
                self.wait_durations.append(self.cycles - self.wait_start)
                self.wait_start = None
            if self.inject_nmi and not self.injected and self.cpu.pc == self.s['READ_BYTE']:
                self.cpu.nmi()
                self.injected = True
            self.cpu.step()
        else:
            raise AssertionError(f'Unbounded adapter at {self.cpu.pc:04X}')
        assert self.cpu.sp == 0xfd
        assert self.cpu.p & 0x0c == flags & 0x0c
        assert self.ddr == self.initial_ddr
        assert self.latch & self.ddr == self.initial_latch & self.initial_ddr
        assert not self.rtc_writes
        assert self.ram[:0x100] == before[:0x100]
        assert self.ram[0x6500:0x6660] == before[0x6500:0x6660]
        assert self.ram[0x6661:0x7f00] == before[0x6661:0x7f00]
        assert self.ram[0x8000:] == before[0x8000:]
        return self.cpu.a

    def gateway_attempt(self):
        outer = self.cpu
        pins_before = len(self.pin_writes)
        self.cpu = MPU(memory=self, pc=0x6514)
        self.cpu.sp = 0x7f  # Independent interrupt/task stack for the refusal test.
        self.cpu.stPushWord(0x01ff)
        for _ in range(32):
            if self.cpu.pc == 0x0200:
                break
            self.cpu.step()
        else:
            raise AssertionError('Busy gateway did not refuse promptly')
        assert self.cpu.a == 8
        assert len(self.pin_writes) == pins_before
        assert self.ram[0x6660] == 1
        self.gateway_attempts += 1
        self.cpu = outer


class AdapterTests(unittest.TestCase):
    def test_complete_wire_success(self):
        b = Bus()
        self.assertEqual(b.run(), 0)
        self.assertEqual(b.byte('VALID'), 7)
        self.assertEqual(b.get('SERIAL', 9), SERIAL)
        self.assertEqual(b.get('LOCKS', 2), b'\x00\x55')
        self.assertEqual(len(b.commands), 5)
        self.assertEqual(b.sleeps, 1)
        self.assertEqual(b.lock_events, [1, 0])
        self.assertEqual(b.ram[0x6660], 0)
        self.assertTrue(all(a in (0xc0, 0xc1) for a in b.addresses))
        self.assertEqual([n for n in b.nacks if not n[2]],
                         [(0x60, 3, False)] + [(0x60, 6, False)] * 5)

    def test_documented_608b_revision(self):
        b = Bus(responses=[packet(bytes.fromhex('00006003'))] + RESPONSES[1:])
        self.assertEqual(b.run(), 0)
        self.assertEqual(b.byte('VALID'), 7)
        self.assertEqual(b.get('REVISION', 4), bytes.fromhex('00006003'))
        self.assertEqual(b.get('SERIAL', 9), SERIAL)

    def test_default_and_discovery_refusals(self):
        cases = [(None, None, 2), (0x7d27, 0, 1), (0x7d27, 2, 2),
                 (0x7d04, 0, 2), (0x7d07, 1, 2), (0x7d08, 1, 2),
                 (0x7d09, 0, 2), (0x7d0b, 0x66, 2), (0x7d0c, 0, 2),
                 (0x6510, 0, 2), (0x6664, 0, 2), (0x6660, 1, 3),
                 (0x6669, 1, 3)]
        for address, value, expected in cases:
            b = Bus(configured=address is not None)
            if address is not None:
                b.ram[address] = value
            self.assertEqual(b.run(), expected)
            self.assertEqual(b.pin_writes, [])
            self.assertEqual(b.lock_events, [])

    def test_bad_target_and_clock(self):
        for name, values in (('CA_ADDRESS', [0, 7, 0x57, 0x6f, 0x78, 0xff]),
                             ('CA_MHZ', [0, 3, 16])):
            for value in values:
                b = Bus()
                b.ram[b.s[name]] = value
                self.assertEqual(b.run(), 2)
                self.assertEqual(b.pin_writes, [])

    def test_absent_stuck_and_driven_pins(self):
        b = Bus(present=False)
        self.assertEqual(b.run(), 4)
        self.assertEqual(len(b.wakes), 1)
        self.assertEqual(b.commands, [])
        for line in ('sda', 'scl'):
            b = Bus(stuck=line)
            self.assertEqual(b.run(), 5)
            self.assertEqual(b.pin_writes, [])
            self.assertEqual(b.ram[0x6660], 0)
        b = Bus()
        b.ddr |= 1
        b.initial_ddr = b.ddr
        self.assertEqual(b.run(), 5)
        self.assertEqual(b.pin_writes, [])

    def test_read_address_nack_polling(self):
        for busy_reads in (7, 8):
            b = Bus(busy_reads=busy_reads)
            self.assertEqual(b.run(), 0 if busy_reads == 7 else 4)
            if busy_reads == 7:
                self.assertEqual(b.byte('VALID'), 7)
            else:
                self.assertEqual(b.byte('VALID'), 0)
                self.assertEqual(len(b.commands), 1)

    def test_malformed_and_crc_packets(self):
        for response in (b'\x00', b'\xff', b'\x08', b'\x07' + bytes(6)):
            b = Bus(responses=[response])
            self.assertEqual(b.run(), 6)
            self.assertEqual(len(b.commands), 1)
            self.assertEqual(b.sleeps, 1)
            self.assertEqual(b.ram[0x6660], 0)

    def test_payload_nack_aborts_later_commands(self):
        b = Bus(nack_payload=(1, 3))
        self.assertEqual(b.run(), 0)  # revision identified, fields explicitly fail
        self.assertEqual(b.byte('VALID'), 1)
        self.assertEqual(b.get('FIELD_ERRORS', 4), bytes([5] * 4))
        self.assertEqual(len(b.commands), 1)
        self.assertEqual(b.byte('CA_FAULT_CODE'), 2)
        self.assertEqual(b.byte('CA_FAULT_PHASE'), 2)
        self.assertEqual(b.sleeps, 1)

    def test_clock_and_stop_faults(self):
        b = Bus(clock_fault=lambda m: m.mode != 'idle')
        self.assertEqual(b.run(), 5)
        self.assertEqual(b.byte('CA_FAULT_CODE'), 3)
        self.assertEqual(b.byte('CA_STOP_ERROR'), 3)
        self.assertEqual(b.ram[0x6660], 0)
        b = Bus(present=False, clock_fault=lambda m:
                m.selected == 0x60 and m.mode == 'idle')
        self.assertEqual(b.run(), 5)  # NACK plus failed STOP is never retryable.
        self.assertEqual(b.byte('CA_FAULT_CODE'), 2)
        self.assertEqual(b.byte('CA_FAULT_PHASE'), 3)
        self.assertEqual(b.byte('CA_STOP_ERROR'), 3)

    def test_shared_gateway_refuses_during_ownership(self):
        b = Bus()
        b.try_gateway = True
        b.inject_nmi = True
        self.assertEqual(b.run(), 0)
        self.assertEqual(b.gateway_attempts, 5)
        self.assertTrue(b.injected)
        self.assertEqual(b.lock_events, [1, 0])

    def test_sleep_error_is_separate(self):
        b = Bus(sleep_nack=True)
        self.assertEqual(b.run(), 0)
        self.assertEqual(b.byte('VALID'), 7)
        self.assertEqual(b.byte('CLEANUP_ERROR'), 5)
        self.assertEqual(b.ram[0x6660], 0)

    def test_clock_profiles_and_flags(self):
        for mhz in (1, 2, 4, 8):
            for flags in (0x20, 0x24, 0x28, 0x2c):
                b = Bus(mhz=mhz)
                self.assertEqual(b.run(flags=flags), 0)
                self.assertEqual(b.byte('VALID'), 7)
                self.assertGreaterEqual(b.wakes[0] / mhz, 60)
                self.assertGreaterEqual((b.read_cycle - b.wake_release) / mhz, 20000)
                self.assertGreaterEqual(min(b.wait_durations) / mhz, 5000)
                TIMINGS.setdefault(mhz, {}).update(
                    wake_low_us=b.wakes[0] / mhz,
                    recovery_us=(b.read_cycle-b.wake_release) / mhz,
                    min_poll_delay_us=min(b.wait_durations) / mhz,
                    success_ms=b.cycles / mhz / 1000)

    def test_bounded_total_time(self):
        for mhz in (1, 2, 4, 8):
            b = Bus(mhz=mhz, busy_reads=7)
            self.assertEqual(b.run(), 0)
            # Ideal-bus scenario with every command ready on its eighth poll;
            # not a claim about arbitrary clock stretching or NMI latency.
            self.assertLess(b.cycles / mhz / 1000, 500)
            TIMINGS.setdefault(mhz, {})['last_poll_success_ms'] = b.cycles / mhz / 1000

    def test_diagnostics_reset_on_refusal(self):
        b = Bus(present=False)
        self.assertEqual(b.run(), 4)
        self.assertEqual(b.byte('CA_FAULT_CODE'), 2)
        prior_pins = list(b.pin_writes)
        b.ram[b.s['CA_ENABLE']] = 0
        self.assertEqual(b.run(), 2)
        self.assertEqual(b.byte('CA_FAULT_CODE'), 0)
        self.assertEqual(b.byte('CA_STOP_ERROR'), 0)
        self.assertEqual(b.pin_writes, prior_pins)

    def test_rtc_coexistence(self):
        b = Bus()
        regs = bytes(b.regs)
        self.assertEqual(b.run(), 0)
        self.assertEqual(b.run(entry=0x3004), 0)
        self.assertEqual(bytes(b.regs), regs)
        b.command_index = -1
        b.read_cycle = None
        self.assertEqual(b.run(), 0)
        self.assertEqual(bytes(b.regs), regs)
        b = Bus(rtc_present=False)
        self.assertEqual(b.run(), 0)
        b = Bus(present=False)
        self.assertEqual(b.run(), 4)
        self.assertEqual(b.run(entry=0x3004), 0)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests))
    meta = json.loads((OUT / 'build.json').read_text())
    (OUT / 'test-results.json').write_text(json.dumps(dict(
        passed=result.wasSuccessful(), tests=result.testsRun, sha256=meta['sha256'],
        hardware_tested=False, electrical_timing_emulated=False,
        timing_model='py65 instruction cycles, ideal digital edges, no analog timing',
        timings_by_mhz=TIMINGS,
        transport='linked adapter and engine, digital VIA/I2C model'), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
