"""Regression checks for load-only restoration and the physical RAM wrapper."""
import tempfile
import unittest
from unittest.mock import patch

from beta4_migration import s19
from build_v2_crypto_adapter import ROOT
from qualify_v2_crypto_board import load_only, wrapper
from test_v2_crypto_adapter import Bus, MPU
import build_v2_rtc_split as split


class LoadOnlyLink:
    def __init__(self, payload, mismatch=False):
        self.payload, self.mismatch, self.sent = payload, mismatch, []

    def command(self, command, prompt):
        self.sent.append(command.encode())

    def send(self, data):
        self.sent.append(data)

    def until(self, prompt):
        return prompt

    def dump(self, first, last):
        assert first == 0x2000 and last == 0x2000 + len(self.payload) - 1
        return bytes(len(self.payload)) if self.mismatch else self.payload

    def monitor_load(self, path):
        raise AssertionError('Auto-executing loader must never be used')


class QualificationTests(unittest.TestCase):
    def test_restoration_never_executes_saved_ram(self):
        # A saved image beginning with STP is data and must remain unexecuted.
        payload = b'\xdb' + bytes(range(32))
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            path = ROOT / folder / 'saved.s19'
            path.write_bytes(s19(dict(enumerate(payload, 0x2000)), 0x2000))
            for mismatch in (False, True):
                link = LoadOnlyLink(payload, mismatch)
                with patch('qualify_v2_crypto_board.time.sleep'):
                    if mismatch:
                        with self.assertRaises(AssertionError):
                            load_only(link, path)
                    else:
                        load_only(link, path)
                self.assertFalse(any(line.startswith(b'G ') for line in link.sent))
                self.assertTrue(any(line.startswith(b'S9') for line in link.sent))

    def test_wrapper_revalidates_and_checks_rtc_coexistence(self):
        split.OUT = ROOT / 'BUILD/v2-crypto-wrapper-model'
        split.main()

        class SharedBus(Bus):
            def __setitem__(self, address, value):
                if address == 0x7fec:
                    assert value == 0xee
                    self.ram[address] = value
                else:
                    super().__setitem__(address, value)

        b = SharedBus()
        b.ram[0x7fec] = 0xee
        provider = (split.OUT / 'provider.bin').read_bytes()
        b.ram[0x8000:0x8000+len(provider)] = provider
        b.ram[0x6500:0x6700] = (split.OUT / 'gateway.bin').read_bytes()
        b.ram[0x6664] = 2  # Same code-unverified state observed after HOLD.
        # Substitute a return sentinel for HOLD, leaving the wrapper body intact.
        code = wrapper()[:-3] + b'\x60\xea\xea'
        b.ram[0x2800:0x2800+len(code)] = code
        b.cpu = MPU(memory=b, pc=0x2800)
        b.cpu.p, b.cpu.sp = 0x28, 0xfd
        b.cpu.stPushWord(0x01ff)
        for _ in range(2000000):
            if b.cpu.pc == 0x200:
                break
            b.cpu.step()
        else:
            self.fail('Wrapper timeout')
        snapshot = b.ram[0x2a00:0x2a0d]
        self.assertEqual(snapshot[5], 0)
        self.assertEqual(snapshot[11:13], b'\0\0')
        self.assertEqual(b.byte('VALID'), 7)
        self.assertEqual(snapshot[0], snapshot[6])
        self.assertEqual(snapshot[2], snapshot[8])
        self.assertEqual(snapshot[3], snapshot[9])
        self.assertEqual((snapshot[1] ^ snapshot[7]) & snapshot[0], 0)
        self.assertEqual(snapshot[4] & 12, snapshot[10] & 12)
        self.assertEqual(b.ram[0x2a30:0x2a39], b.ram[0x2a40:0x2a49])
        self.assertEqual(b.ram[0x6660], 0)
        self.assertEqual(b.rtc_writes, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
