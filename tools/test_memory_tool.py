"""Host fault tests and actual assembled MEMORY1 65C02/816 CPU-model tests.

SPI/flash are bus models; I2C high-level tests hook the byte primitives. These
tests are not physical-device qualification or electrical timing evidence.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

import memory_tool as m

BUILD = m.ROOT/'BUILD/memory-agent-v1'


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        m.main(['init-test-device', str(self.root/'device')])
        self.device = m.DirectoryDevice(self.root/'device')

    def tearDown(self):
        self.temp.cleanup()

    def test_full_roundtrip_and_partial_selection(self):
        original = {n: m.read_region(self.device, n) for n in m.REGIONS}
        m.backup(self.device, self.root/'backup', list(m.ORDER))
        _, images = m.archive(self.root/'backup')
        for n in m.REGIONS:
            if n == 'spi-mode':
                self.device.write(n, 0, b'\x80')
            else:
                self.device.write(n, 0, b'\x12'*min(32, len(original[n])))
        changes = m.plan(self.device, images)
        receipt = m.apply(self.device, images, changes, self.root/'restore.json')
        self.assertTrue(receipt['complete'])
        for n in original:
            self.assertEqual(m.read_region(self.device, n), original[n])
        self.assertEqual(m.selected('eeprom,flash'), ['flash', 'eeprom'])

    def test_live_banner_spelling_and_wrong_cpu_refusal(self):
        face = b'STR8-N MON B gen 00000010\r\n0.1.0-dev BASE1/PR05 ABI 2\r\nCPU: 65C02\r\n'
        m.admit_monitor_banner(face, '65c02')
        with self.assertRaisesRegex(ValueError, 'CPU'):
            m.admit_monitor_banner(face, '65c816-e')
        with self.assertRaisesRegex(ValueError, 'PR05'):
            m.admit_monitor_banner(face.replace(b'PR05', b'PR04'), '65c02')

    def test_live_dump_ascii_column_and_missing_bytes(self):
        face = b'D 0200 0203\r\r\n0200: 01 02 AB CD |.. AB CD|\r\r\nB3> '
        self.assertEqual(m.parse_monitor_dump(face, 0x200, 0x203), bytes.fromhex('01 02 AB CD'))
        self.assertEqual(m.parse_monitor_dump(b'0200: 01 02 AB CD\r\n', 0x200, 0x203),
                         bytes.fromhex('01 02 AB CD'))
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            m.parse_monitor_dump(face, 0x200, 0x204)

    def test_tamper_and_incomplete_rejected(self):
        m.backup(self.device, self.root/'backup', ['eeprom'])
        image = self.root/'backup/eeprom.bin'
        image.write_bytes(b'\0'*128)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.archive(self.root/'backup')
        image.write_bytes(b'\xff'*128)
        manifest = json.loads((self.root/'backup/manifest.json').read_text())
        manifest['complete'] = False
        m.save(self.root/'backup/manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            m.archive(self.root/'backup')

    def test_foundation_difference_refused_before_any_write(self):
        image = bytearray(m.read_region(self.device, 'flash'))
        image[-1] = 0
        with self.assertRaisesRegex(ValueError, 'Foundation differs'):
            m.plan(self.device, {'flash': bytes(image)})
        self.assertEqual(self.device.read('flash', 0x1ffff, 1), b'\xff')

    def test_pending_receipt_survives_ambiguous_write(self):
        image = bytes(128)
        changes = m.plan(self.device, {'eeprom': image})
        def failed(*args):
            raise TimeoutError('lost reply')
        self.device.write = failed
        with self.assertRaises(TimeoutError):
            m.apply(self.device, {'eeprom': image}, changes, self.root/'receipt.json')
        receipt = json.loads((self.root/'receipt.json').read_text())
        self.assertFalse(receipt['complete'])
        self.assertEqual(receipt['pending']['region'], 'eeprom')
        self.assertEqual(receipt['completed'], [])

    def test_changed_preimage_stops(self):
        changes = m.plan(self.device, {'eeprom': bytes(128)})
        self.device.write('eeprom', 0, b'\x01')
        with self.assertRaisesRegex(ValueError, 'changed since plan'):
            m.apply(self.device, {'eeprom': bytes(128)}, changes, self.root/'receipt.json')

    def test_cpu_chunks_cover_exact_owner_range_buffer_last(self):
        rows = m.chunks('cpu-ram')
        addresses = [a for p, n in rows for a in range(p, p+n)]
        self.assertEqual(sorted(addresses), list(range(25856)))
        self.assertEqual(rows[-1], (0x1e00, 4096))

    def test_staging_buffer_cannot_corrupt_final_ram_restore(self):
        original_ram = bytes((i*11+3)&255 for i in range(25856))
        self.device.write('cpu-ram', 0, original_ram)
        self.device.saved = {'cpu-ram': original_ram,
                             'zero-page': m.read_region(self.device, 'zero-page')}
        read, write = self.device.read, self.device.write
        def staged_read(name, offset, count):
            data = read(name, offset, count)
            if name not in ('cpu-ram', 'zero-page'):
                write('cpu-ram', 0x1e00, data)
            return data
        def staged_write(name, offset, data):
            write('cpu-ram', 0x1e00, data)
            write(name, offset, data)
        self.device.read, self.device.write = staged_read, staged_write
        images = {'flash': m.read_region(self.device, 'flash'), 'eeprom': bytes(128),
                  'zero-page': self.device.saved['zero-page'], 'cpu-ram': original_ram}
        changes = m.plan(self.device, images)
        m.apply(self.device, images, changes, self.root/'staging-receipt.json')
        self.assertEqual(read('cpu-ram', 0, 25856), original_ram)

    def test_wire_refuses_cleanup_after_damaged_reply(self):
        class Port:
            def __init__(self):
                self.writes = []
                self.reply = bytearray(b'\0\x01\0X\0\0')
            def write(self, data):
                self.writes.append(data)
                return len(data)
            def read(self, count):
                data = self.reply[:count]
                del self.reply[:count]
                return data
        port = Port()
        wire = m.Wire(port, pause=0)
        with self.assertRaisesRegex(ValueError, 'CRC mismatch'):
            wire.request(6, count=1)
        count = len(port.writes)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            wire.request(0x7f)
        self.assertEqual(len(port.writes), count)

    def test_known_complete_device_failure_allows_ram_cleanup(self):
        class Port:
            def __init__(self):
                prefix = b'\x02\0\0'
                self.reply = bytearray(prefix+m.crc(prefix))
            def write(self, data):
                return len(data)
            def read(self, count):
                part = self.reply[:count]
                del self.reply[:count]
                return part
        wire = m.Wire(Port(), pause=0)
        with self.assertRaisesRegex(ValueError, 'status 2'):
            wire.request(2, count=1)
        self.assertTrue(wire.synchronized)

    def test_cli_plan_does_not_write_and_load_rejects_oversize(self):
        image = self.root/'eeprom.bin'
        image.write_bytes(bytes(128))
        m.main(['load', '--device-dir', str(self.root/'device'), '--out', str(self.root/'plan'),
                'eeprom', str(image)])
        self.assertEqual(self.device.read('eeprom', 0, 128), b'\xff'*128)
        m.main(['load', '--device-dir', str(self.root/'device'), '--out', str(self.root/'write'),
                '--write', 'eeprom', str(image)])
        self.assertEqual(self.device.read('eeprom', 0, 128), bytes(128))
        image.write_bytes(bytes(129))
        with self.assertRaisesRegex(ValueError, 'does not fit'):
            m.main(['load', '--device-dir', str(self.root/'device'), '--out', str(self.root/'bad'),
                    '--write', 'eeprom', str(image)])
        self.assertFalse((self.root/'bad').exists())

    def test_partial_load_preserves_other_bytes(self):
        image = self.root/'small.bin'
        image.write_bytes(b'LOAD')
        m.main(['load', '--device-dir', str(self.root/'device'), '--out', str(self.root/'partial'),
                '--write', '--offset', '0x7', 'eeprom', str(image)])
        expected = b'\xff'*7+b'LOAD'+b'\xff'*117
        self.assertEqual(self.device.read('eeprom', 0, 128), expected)

    def test_124k_flash_import_keeps_foundation(self):
        image = self.root/'flash-124k.bin'
        data = bytes((i*7)&255 for i in range(124*1024))
        image.write_bytes(data)
        foundation = self.device.read('flash', 124*1024, 4096)
        m.main(['load', '--device-dir', str(self.root/'device'), '--out', str(self.root/'flash-load'),
                '--write', 'flash', str(image)])
        self.assertEqual(self.device.read('flash', 0, 124*1024), data)
        self.assertEqual(self.device.read('flash', 124*1024, 4096), foundation)


class Memory:
    def __init__(self):
        self.ram = bytearray(32768)
        self.ram[0x7fec] = 0xee
        self.bank = 3
        self.flash = [bytearray(((i*17+b*31)&255 for i in range(32768))) for b in range(4)]
        self.spi = bytearray((i*23+7)&255 for i in range(131072))
        self.eeprom = bytearray(range(128))
        self.mode = 0x40
        self.rx, self.tx = deque(), bytearray()
        self.flash_state = 0
        self.erases = []
        self.flash_writes = []
        self.spi_bytes = []
        self.spi_bits = 0
        self.spi_shift = 0
        self.miso = 0

    def __getitem__(self, address):
        if isinstance(address, slice):
            return [self[a] for a in range(*address.indices(65536))]
        assert 0 <= address < 65536
        if address >= 0x8000:
            return self.flash[self.bank][address-0x8000]
        if address == 0x7fe0:
            return (self.ram[address]&~3) | (0 if self.rx else 2)
        if address == 0x7fe1 and not self.ram[0x7fe3]:
            return self.rx[0] if self.rx else 0
        if address == 0x7fc0:
            return (self.ram[address]&~32) | (32 if self.miso else 0)
        return self.ram[address]

    def __setitem__(self, address, value):
        assert 0 <= address < 65536
        value &= 255
        if address >= 0x8000:
            self.flash_writes.append((self.bank, address, value))
            stage = self.flash_state
            if stage == 6:
                self.flash[self.bank][address-0x8000] &= value
                self.flash_state = 0
            elif value == 0xf0:
                self.flash_state = 0
            elif stage == 0 and (address, value) == (0xd555, 0xaa):
                self.flash_state = 1
            elif stage in (1, 4) and (address, value) == (0xaaaa, 0x55):
                self.flash_state += 1
            elif stage == 2 and address == 0xd555 and value in (0x80, 0xa0):
                self.flash_state = 3 if value == 0x80 else 6
            elif stage == 3 and (address, value) == (0xd555, 0xaa):
                self.flash_state = 4
            elif stage == 5 and value == 0x30:
                start = (address-0x8000)&~4095
                self.flash[self.bank][start:start+4096] = b'\xff'*4096
                self.erases.append((self.bank, start))
                self.flash_state = 0
            else:
                raise AssertionError(('unexpected flash sequence', stage, self.bank, hex(address), value))
            return
        old = self.ram[address]
        self.ram[address] = value
        if address == 0x7fec:
            self.bank = (1 if value&2 else 0) | (2 if value&32 else 0)
        elif address == 0x7fe0 and not old&8 and value&8 and self.rx:
            self.rx.popleft()
        elif address == 0x7fe3 and value == 255 and self.ram[0x7fe0]&4:
            self.tx.append(self.ram[0x7fe1])
        elif address == 0x7fc0:
            if old&4 and not value&4:
                self.spi_bytes, self.spi_bits, self.spi_shift = [], 0, 0
            if not value&4 and not old&1 and value&1:
                outgoing = 0
                if self.spi_bytes and self.spi_bytes[0] == 5:
                    outgoing = self.mode
                elif len(self.spi_bytes) >= 4 and self.spi_bytes[0] == 3:
                    a = int.from_bytes(bytes(self.spi_bytes[1:4]), 'big')
                    outgoing = self.spi[a]
                self.miso = bool(outgoing & (128 >> self.spi_bits))
                self.spi_shift = ((self.spi_shift << 1) | bool(value&2))&255
                self.spi_bits += 1
                if self.spi_bits == 8:
                    self.spi_bytes.append(self.spi_shift)
                    self.spi_bits, self.spi_shift = 0, 0
                    if len(self.spi_bytes) == 2 and self.spi_bytes[0] == 1:
                        self.mode = self.spi_bytes[1]
                    if len(self.spi_bytes) == 5 and self.spi_bytes[0] == 2:
                        a = int.from_bytes(bytes(self.spi_bytes[1:4]), 'big')
                        self.spi[a] = self.spi_bytes[4]


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.cpu = MPU(memory=self.memory, pc=0x200)
        self.cpu.pc = 0x200
        self.cpu.p |= self.cpu.INTERRUPT
        manifest = json.loads((BUILD/'manifest.json').read_text())
        image = (BUILD/manifest.get('file', 'memory-agent.bin')).read_bytes()
        self.memory.ram[0x200:0x200+len(image)] = image
        self.symbols = {n: int(v, 16) for v, n in re.findall(
            r'^\s*([0-9a-fA-F]{8})\s+(\w+)\s*$', (BUILD/'source/agent.map').read_text(), re.M)}
        self.i2c_hooks = {self.symbols[n]: n for n in (
            'I2C_INIT', 'I2C_RESTORE', 'I2C_START', 'I2C_STOP', 'I2C_WRITE', 'I2C_READ')}
        self.i2c_address = None
        self.i2c_pointer = 0
        self.i2c_reading = False
        self.run_cpu(lambda: bytes(self.memory.tx).endswith(m.PROMPT))
        if manifest.get('component'):
            self.assertIn(b'STR8-N UTIL MEMORY', self.memory.tx)
        self.memory.tx.clear()

    def run_cpu(self, predicate, limit=12000000):
        for _ in range(limit):
            if predicate():
                return
            hook = self.i2c_hooks.get(self.cpu.pc)
            if hook:
                self.hook_i2c(hook)
            else:
                self.cpu.step()
        self.fail('CPU instruction limit at '+hex(self.cpu.pc))

    def hook_i2c(self, name):
        c = self.cpu
        if name == 'I2C_START':
            self.i2c_address = None
        elif name == 'I2C_WRITE':
            if self.i2c_address is None:
                self.i2c_address = c.a
                self.i2c_reading = c.a == 0xaf
                self.i2c_need_pointer = not self.i2c_reading
                self.assertIn(c.a, (0xae, 0xaf))
            elif self.i2c_need_pointer:
                self.i2c_pointer = c.a
                self.i2c_need_pointer = False
            else:
                self.assertLess(self.i2c_pointer, 128)
                self.memory.eeprom[self.i2c_pointer] = c.a
                self.i2c_pointer += 1
        elif name == 'I2C_READ':
            self.assertLess(self.i2c_pointer, 128)
            c.a = self.memory.eeprom[self.i2c_pointer]
            self.i2c_pointer += 1
        c.p |= c.CARRY
        c.pc = (c.stPopWord()+1)&65535

    def request(self, op, bank=0, address=0, count=0, data=None, corrupt_header=False, corrupt_data=False):
        header = bytes((op, bank))+address.to_bytes(3, 'little')+count.to_bytes(2, 'little')
        checksum = bytearray(m.crc(header))
        if corrupt_header:
            checksum[0] ^= 1
        payload = header+checksum
        if data is not None:
            trailer = bytearray(m.crc(data))
            if corrupt_data:
                trailer[0] ^= 1
            payload += data+trailer
        self.memory.rx.extend(payload)
        self.memory.tx.clear()
        def complete():
            tx = self.memory.tx
            return len(tx) >= 3 and len(tx) == 5+int.from_bytes(tx[1:3], 'little')
        self.run_cpu(complete)
        response = bytes(self.memory.tx)
        self.assertEqual(response[-2:], m.crc(response[:-2]))
        self.assertEqual(self.memory.bank, 3)
        return response[0], response[3:-2]

    def test_flash_all_banks_and_foundation_guard(self):
        original_f = bytes(self.memory.flash[3][-4096:])
        for bank in range(4):
            for address in (0x8000, 0xf000):
                status, data = self.request(1, bank, address, 4096)
                self.assertEqual(status, 0)
                self.assertEqual(data, self.memory.flash[bank][address-0x8000:address-0x7000])
        image = bytes((i*7)&255 for i in range(4096))
        for bank in range(4):
            self.assertEqual(self.request(0x81, bank, 0x8000, 4096, image)[0], 0)
            self.assertEqual(self.memory.flash[bank][:4096], image)
        for address in (0xc000, 0xd000, 0xe000):
            self.assertEqual(self.request(0x81, 3, address, 4096, image)[0], 0)
            self.assertEqual(self.memory.flash[3][address-0x8000:address-0x7000], image)
        erases = len(self.memory.erases)
        self.assertEqual(self.request(0x81, 0, 0x8000, 4096, image)[0], 0)
        self.assertEqual(len(self.memory.erases), erases)
        self.assertNotEqual(self.request(0x81, 3, 0xf000, 4096, image)[0], 0)
        self.assertEqual(self.memory.flash[3][-4096:], original_f)

    def test_ram_and_zero_page_read_write(self):
        data = bytes((i*13)&255 for i in range(4096))
        self.assertEqual(self.request(0x84, address=0x6300, count=1024, data=data[:1024])[0], 0)
        self.assertEqual(self.request(4, address=0x6300, count=1024), (0, data[:1024]))
        self.assertEqual(self.request(0x84, address=0x2000, count=4096, data=data)[0], 0)
        before = bytes(self.memory.ram[0x2000:0x3000])
        self.assertEqual(self.request(4, address=0x6300, count=1024), (0, data[:1024]))
        self.assertEqual(self.memory.ram[0x2000:0x3000], before)
        zp = bytes(range(224))
        self.assertEqual(self.request(0x85, count=224, data=zp)[0], 0)
        self.assertEqual(self.request(5, count=224), (0, zp))
        self.assertNotEqual(self.request(4, address=0x66ff, count=2)[0], 0)
        self.assertNotEqual(self.request(4, address=0x100, count=256)[0], 0)

    def test_spi_read_write_each_mode_and_last_address(self):
        for mode in (0, 0x40, 0x80):
            self.memory.mode = mode
            for address in (0, 0xff, 0xffff, 0x1ff00):
                status, data = self.request(2, address=address, count=256)
                self.assertEqual(status, 0)
                self.assertEqual(data, self.memory.spi[address:address+256])
                image = bytes((v^0xa5) for v in data)
                self.assertEqual(self.request(0x82, address=address, count=256, data=image)[0], 0)
                self.assertEqual(self.memory.spi[address:address+256], image)
            self.assertEqual(self.memory.mode, mode)
            self.assertEqual(self.request(6, count=1), (0, bytes((mode,))))
        self.assertNotEqual(self.request(2, address=0x1ffff, count=2)[0], 0)
        self.assertEqual(self.request(0x86, count=1, data=b'\x40')[0], 0)
        self.assertEqual(self.memory.mode, 0x40)

    def test_eeprom_page_write_and_protected_boundary(self):
        self.assertEqual(self.request(3, count=128), (0, bytes(range(128))))
        for address in range(0, 128, 8):
            data = bytes([address^255])*8
            self.assertEqual(self.request(0x83, address=address, count=8, data=data)[0], 0)
            self.assertEqual(self.request(3, address=address, count=8), (0, data))
        self.assertNotEqual(self.request(0x83, address=7, count=2, data=b'ab')[0], 0)
        self.assertNotEqual(self.request(0x83, address=128, count=1, data=b'a')[0], 0)

    def test_crc_damage_does_not_mutate_flash_or_eeprom(self):
        original = bytes(self.memory.flash[0])
        self.assertNotEqual(self.request(0x81, address=0x8000, count=4096,
                                        data=bytes(4096), corrupt_data=True)[0], 0)
        self.assertEqual(self.memory.flash[0], original)
        self.assertEqual(self.memory.flash_writes, [])
        self.assertNotEqual(self.request(3, count=8, corrupt_header=True)[0], 0)

    def test_wire_talks_to_assembled_agent_and_quits_to_bound_recovery(self):
        test = self
        class Port:
            def write(self, data):
                test.memory.rx.extend(data)
                return len(data)
            def read(self, count):
                test.run_cpu(lambda: len(test.memory.tx) >= count)
                data = bytes(test.memory.tx[:count])
                del test.memory.tx[:count]
                return data
        wire = m.Wire(Port(), pause=0)
        self.assertEqual(wire.request(3, count=128), bytes(range(128)))
        image = b'test1234'
        wire.request(0x83, address=120, count=8, data=image)
        self.assertEqual(wire.request(3, address=120, count=8), image)
        old_nmi = self.memory.ram[0xf4]
        self.assertEqual(old_nmi, 1)
        wire.request(0x7f)
        recovery = json.loads((BUILD/'manifest.json').read_text())['recovery_entry']
        self.run_cpu(lambda: self.cpu.pc == recovery)
        self.assertEqual(self.memory.ram[0xf4], 0)

    def test_busy_spi_pins_refuse_without_touching_gpio(self):
        self.memory.ram[0x7fc2] = 0x0f
        before = bytes(self.memory.spi)
        self.assertNotEqual(self.request(0x82, count=1, data=b'X')[0], 0)
        self.assertEqual(self.memory.ram[0x7fc2], 0x0f)
        self.assertEqual(self.memory.spi, before)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=BUILD)
    parser.add_argument('--deps', type=Path, default=m.ROOT/'tmp/migration-python')
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), default='65c02')
    parser.add_argument('--deps-816', type=Path, default=m.ROOT/'tmp/p1-clean/BUILD/test-deps-816')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--host-only', action='store_true')
    args = parser.parse_args()
    BUILD = args.build
    sys.path.insert(0, str(args.deps))
    if args.cpu == '65c816-e':
        sys.path.insert(0, str(args.deps_816))
        from py65816.devices.mpu65c816 import MPU
    else:
        from py65.devices.mpu65c02 import MPU
    suite = (unittest.defaultTestLoader.loadTestsFromTestCase(HostTests) if args.host_only else
             unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.report:
        m.save(args.report, {'passed': result.wasSuccessful(), 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'cpu': args.cpu,
               'agent_sha256': json.loads((BUILD/'manifest.json').read_text())['sha256'],
               'harness_sha256': m.sha(Path(__file__).read_bytes()),
               'physical_board_access': False, 'hardware_qualification': 'NOT RUN',
               'i2c_model': 'High-level byte primitive hooks; electrical timing not tested'})
    sys.exit(0 if result.wasSuccessful() else 1)
