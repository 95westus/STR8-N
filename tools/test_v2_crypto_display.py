"""Execute the console client and adapter with digital I2C and shared services."""
import hashlib
import json
import unittest

from build_v2_crypto_display import OUT, SOURCE
from build_v2_crypto_adapter import ROOT
from test_v2_crypto_adapter import Bus, MPU
from test_v2_crypto_status import RESPONSES, packet
import build_v2_rtc_split as split


class DisplayBus(Bus):
    def __getitem__(self, address):
        if isinstance(address, int) and 0x6500 <= address < 0x6700:
            self.service_reads.append(address)
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if address == 0x7fec:
            assert value == 0xee
            self.ram[address] = value
        else:
            super().__setitem__(address, value)


def display(edu_off=False, bad_descriptor=False, **options):
    b = DisplayBus(**options)
    b.service_reads = []
    meta = json.loads((OUT / 'build.json').read_text())
    image = (OUT / 'crypto-display.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == meta['sha256']
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == meta['source_sha256']
    b.ram[0x2000:0x2000+len(image)] = image
    b.ram[b.s['CA_ENABLE']] = 0xa5
    b.ram[b.s['CA_ADDRESS']] = 0x60
    b.ram[b.s['CA_MHZ']] = 8
    provider = (split.OUT / 'provider.bin').read_bytes()
    b.ram[0x8000:0x8000+len(provider)] = provider
    b.ram[0x6500:0x6700] = (split.OUT / 'gateway.bin').read_bytes()
    b.ram[0x6664] = 2
    b.ram[0x7fec] = 0xee
    if edu_off:
        b.ram[0x7d27] = 0
        b.ram[0x6500:0x6700] = b'\x5a' * 512
    if bad_descriptor:
        b.ram[0x7d04] = 0
    if options.get('configured') is False:
        b.ram[b.s['CA_ENABLE']] = 0
    b.cpu = MPU(memory=b, pc=0x2800)
    b.cpu.sp = 0xff
    output = bytearray()
    for _ in range(2000000):
        if b.cpu.pc == 0x7e67:
            break
        if b.cpu.pc == 0x7e6d:
            output.append(b.cpu.a)
            b.cpu.pc = b.cpu.stPopWord() + 1
        else:
            b.cpu.step()
    else:
        raise AssertionError('Unbounded console client')
    assert b.cpu.sp == 0xff
    if not edu_off:
        assert b.ram[0x6660] == 0
    assert b.ddr == b.initial_ddr
    assert b.latch & b.ddr == b.initial_latch & b.initial_ddr
    assert not b.rtc_writes
    return output.decode('ascii'), b


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        split.OUT = ROOT / 'BUILD/v2-crypto-display/shared-fixture'
        split.main()

    def test_a_and_b(self):
        for revision, part in ((b'\0\0\x60\x02', 'ATECC608A'),
                               (b'\0\0\x60\x03', 'ATECC608B')):
            text, b = display(responses=[packet(revision)] + RESPONSES[1:])
            self.assertIn('Status:        Present\r\n', text)
            self.assertIn('Device:        ' + part, text)
            self.assertIn('Serial:        0123456789ABCDEFEE', text)
            self.assertIn('Configuration: UNLOCKED', text)
            self.assertIn('Data/OTP:      LOCKED', text)
            self.assertIn('Cleanup:       OK', text)
            self.assertNotIn('Field errors:', text)
            self.assertEqual(b.byte('VALID'), 7)

    def test_unavailable_and_absent(self):
        text, _ = display(configured=False)
        self.assertIn('Service unavailable', text)
        self.assertIn('Serial:        unknown', text)
        text, _ = display(present=False)
        self.assertIn('Status:        Not responding', text)
        self.assertNotIn('not fitted', text.lower())

    def test_unknown_revision(self):
        text, b = display(responses=[packet(bytes.fromhex('00006004'))])
        self.assertIn('Unrecognized device', text)
        self.assertIn('Revision:      00 00 60 04', text)
        self.assertIn('Serial:        unknown', text)
        self.assertEqual(len(b.commands), 1)

    def test_disabled_and_bad_discovery_touch_no_bus(self):
        text, b = display(edu_off=True)
        self.assertIn('Disabled (EDU OFF)', text)
        self.assertEqual(b.service_reads, [])
        self.assertEqual(b.ram[0x6500:0x6700], b'\x5a' * 512)
        self.assertEqual(b.pin_writes, [])
        text, b = display(bad_descriptor=True)
        self.assertIn('Service unavailable', text)
        self.assertEqual(b.service_reads, [])
        self.assertEqual(b.pin_writes, [])

    def test_partial_fields_and_cleanup(self):
        text, _ = display(nack_payload=(1, 3))
        self.assertIn('Status:        Present', text)
        self.assertIn('Serial:        unknown', text)
        self.assertIn('Field errors:  05 05 05 05', text)
        text, _ = display(sleep_nack=True)
        self.assertIn('Cleanup:       Bus error', text)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DisplayTests))
    meta = json.loads((OUT / 'build.json').read_text())
    (OUT / 'test-results.json').write_text(json.dumps(dict(
        passed=result.wasSuccessful(), tests=result.testsRun,
        sha256=meta['sha256'], hardware_tested=False), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
