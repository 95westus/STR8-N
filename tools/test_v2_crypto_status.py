"""Execute linked 65C02 status code with scripted HAL; never accesses a board."""
import hashlib
import json
import unittest

from build_v2_crypto_status import OUT, SOURCE, commands, crc
from test_v2_rtc import MPU


def packet(data):
    body = bytes((len(data) + 3,)) + bytes(data)
    return body + crc(body)


REV = bytes.fromhex('00006002')
SERIAL = bytes.fromhex('0123456789abcdefee')
RESPONSES = [packet(REV), packet(SERIAL[:4]), packet(SERIAL[4:8]),
             packet(SERIAL[8:] + b'\x00\x00\x00'), packet(b'\x00\x00\x00\x55')]


class Run:
    def __init__(self, *, check=0, claim=0, wake=0, wake_packet=None,
                 responses=None, receive_errors=None, send_errors=None,
                 wait_error=0, cleanup=0, flags=0x28, default_hal=False,
                 previous=None):
        self.meta = json.loads((OUT / 'build.json').read_text())
        image = (OUT / 'crypto-status.bin').read_bytes()
        assert hashlib.sha256(image).hexdigest() == self.meta['sha256']
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == self.meta['source_sha256']
        self.s = self.meta['symbols']
        self.memory = bytearray(previous) if previous is not None else bytearray([0xa5] * 65536)
        if previous is None:
            self.memory[0x2000:0x2000+len(image)] = image
        self.cpu = MPU(memory=self.memory, pc=0x2000)
        self.cpu.p, self.cpu.sp = flags, 0xfd
        self.cpu.stPushWord(0x01ff)
        self.events, self.sent = [], []
        self.responses = list(RESPONSES if responses is None else responses)
        self.wake_packet = bytes.fromhex('04113343') if wake_packet is None else wake_packet
        self.receive_errors, self.send_errors = receive_errors or {}, send_errors or {}
        self.command = -1
        self.reads = {}
        hooks = {self.s[n]: n for n in (
            'HAL_CHECK', 'HAL_CLAIM', 'HAL_WAKE', 'HAL_SEND', 'HAL_RECEIVE',
            'HAL_WAIT', 'HAL_SLEEP', 'HAL_RELEASE')}
        fixed = dict(HAL_CHECK=check, HAL_CLAIM=claim, HAL_WAKE=wake,
                     HAL_WAIT=wait_error, HAL_SLEEP=cleanup, HAL_RELEASE=0)
        self.minimum_sp = self.cpu.sp
        for steps in range(100000):
            self.minimum_sp = min(self.minimum_sp, self.cpu.sp)
            if self.cpu.pc == 0x0200:
                break
            name = hooks.get(self.cpu.pc)
            if name and not default_hal:
                self.events.append(name)
                status = fixed.get(name, 0)
                if name == 'HAL_SEND':
                    self.command += 1
                    self.sent.append(self.get('TXBUF', 8))
                    status = self.send_errors.get(self.command, 0)
                if name == 'HAL_RECEIVE':
                    self.reads[self.command] = self.reads.get(self.command, 0) + 1
                    error = self.receive_errors.get(self.command, 0)
                    status = error(self.reads[self.command]) if callable(error) else error
                    if not status:
                        data = self.wake_packet if self.command < 0 else self.responses[self.command]
                        # Script a broken HAL length too, but never write beyond RX capacity.
                        self.memory[self.s['RXLEN']] = len(data)
                        start = self.s['RXBUF']
                        self.memory[start:start+min(7, len(data))] = data[:7]
                self.cpu.a = status
                # Scramble scratch registers/flags; the caller must not rely on them.
                self.cpu.x, self.cpu.y, self.cpu.p = 0x76, 0x93, 0x24
                self.cpu.pc = self.cpu.stPopWord() + 1
            else:
                self.cpu.step()
        else:
            raise AssertionError('Unbounded engine execution')
        self.steps = steps
        assert self.cpu.sp == 0xfd
        assert self.cpu.p & 0x0c == flags & 0x0c, 'I/D flags not preserved'
        # No zero page, I/O, flash, descriptor, gateway or unrelated RAM writes.
        assert self.memory[:0x100] == bytes([0xa5] * 0x100)
        assert self.memory[0x3000:] == bytes([0xa5] * (65536-0x3000))

    def get(self, name, count=1):
        start = self.s[name]
        return bytes(self.memory[start:start+count])

    def byte(self, name):
        return self.get(name)[0]


class StatusTests(unittest.TestCase):
    def test_crc_known_vectors(self):
        self.assertEqual(crc(bytes.fromhex('0411')), bytes.fromhex('3343'))
        self.assertEqual(crc(bytes.fromhex('0730000000')), bytes.fromhex('035d'))

    def test_success_and_flags(self):
        for flags in (0x20, 0x24, 0x28, 0x2c):
            r = Run(flags=flags)
            self.assertEqual(r.byte('RESULT'), 0)
            self.assertEqual(r.byte('VALID'), 7)
            self.assertEqual(r.get('REVISION', 4), REV)
            self.assertEqual(r.get('SERIAL', 9), SERIAL)
            self.assertEqual(r.get('LOCKS', 2), b'\x00\x55')
            self.assertEqual(r.get('FIELD_ERRORS', 4), bytes(4))
            self.assertEqual(r.sent, list(commands()))
            self.assertEqual(r.events[-2:], ['HAL_SLEEP', 'HAL_RELEASE'])

    def test_repeat_clears_prior_results(self):
        first = Run(cleanup=5)
        second = Run(previous=first.memory, check=1)
        self.assertEqual(second.byte('RESULT'), 1)
        self.assertEqual(second.byte('VALID'), 0)
        self.assertEqual(second.byte('CLEANUP_ERROR'), 0)
        self.assertEqual(second.get('REVISION', 4), bytes(4))
        self.assertEqual(second.get('SERIAL', 9), bytes(9))
        self.assertEqual(second.get('LOCKS', 2), b'\xff\xff')
        self.assertEqual(second.get('FIELD_ERRORS', 4), b'\xff' * 4)

    def test_each_revision_packet_bit_is_checked(self):
        for bit in range(56):
            damaged = bytearray(RESPONSES[0])
            damaged[bit // 8] ^= 1 << (bit % 8)
            r = Run(responses=[damaged])
            self.assertEqual(r.byte('RESULT'), 6, f'Unchecked bit {bit}')
            self.assertEqual(r.byte('VALID'), 0)

    def test_only_expected_read_commands(self):
        packets = list(commands())
        self.assertEqual(packets[0], bytes.fromhex('030730000000035d'))
        self.assertEqual([p[1:6] for p in packets[1:]], [
            bytes((7, 2, 0, word, 0)) for word in (0, 2, 3, 21)])

    def test_refusal_has_no_cleanup_or_bus(self):
        for options, status, events in ((dict(check=1), 1, ['HAL_CHECK']),
                                       (dict(check=2), 2, ['HAL_CHECK']),
                                       (dict(claim=3), 3, ['HAL_CHECK', 'HAL_CLAIM'])):
            r = Run(**options)
            self.assertEqual(r.byte('RESULT'), status)
            self.assertEqual(r.events, events)
            self.assertEqual(r.byte('VALID'), 0)
        self.assertEqual(Run(default_hal=True).byte('RESULT'), 2)

    def test_wake_failures_and_cleanup(self):
        for options, expected in ((dict(wake=5), 5),
                                  (dict(receive_errors={-1: 4}), 4),
                                  (dict(wake_packet=b'\x04\x11\x00\x00'), 6),
                                  (dict(wake_packet=packet(b'\x00')), 6),
                                  (dict(wake_packet=b''), 6),
                                  (dict(wake_packet=b'\xff' * 8), 6)):
            r = Run(**options, cleanup=5)
            self.assertEqual(r.byte('RESULT'), expected)
            self.assertEqual(r.byte('CLEANUP_ERROR'), 5)
            self.assertEqual(r.sent, [])
            self.assertEqual(r.events[-2:], ['HAL_SLEEP', 'HAL_RELEASE'])

    def test_bad_revision_and_device_status(self):
        for response, expected in ((packet(bytes.fromhex('00006004')), 8),
                                   (packet(b'\x0f'), 7), (packet(b'\x00'), 7),
                                   (b'\x07' + bytes(6), 6), (b'\x07', 6)):
            r = Run(responses=[response])
            self.assertEqual(r.byte('RESULT'), expected)
            self.assertEqual(r.byte('VALID'), 0)
            self.assertEqual(len(r.sent), 1)

    def test_documented_608b_revision(self):
        revision = bytes.fromhex('00006003')
        r = Run(responses=[packet(revision)] + RESPONSES[1:])
        self.assertEqual(r.byte('RESULT'), 0)
        self.assertEqual(r.byte('VALID'), 7)
        self.assertEqual(r.get('REVISION', 4), revision)

    def test_partial_fields_and_invalid_locks(self):
        for command in (1, 2, 3, 4):
            r = Run(receive_errors={command: 5})
            self.assertEqual(r.byte('RESULT'), 0)
            self.assertEqual(r.get('FIELD_ERRORS', 4)[command-1], 5)
            self.assertEqual(r.byte('VALID'), 3 if command == 4 else 5)
            if command != 4:
                self.assertEqual(r.get('SERIAL', 9), bytes(9))
            self.assertEqual(len(r.sent), 5)
        responses = RESPONSES[:-1] + [packet(b'\x00\x00\x01\x00')]
        r = Run(responses=responses)
        self.assertEqual(r.byte('VALID'), 3)
        self.assertEqual(r.get('FIELD_ERRORS', 4)[3], 6)

    def test_polling_is_bounded(self):
        r = Run(receive_errors={0: 4})
        self.assertEqual(r.byte('RESULT'), 4)
        self.assertEqual(r.reads[0], 8)
        r = Run(receive_errors={0: lambda attempt: 4 if attempt < 8 else 0})
        self.assertEqual(r.byte('VALID'), 7)
        self.assertEqual(r.reads[0], 8)

    def test_send_wait_and_cleanup_errors(self):
        for options in (dict(send_errors={0: 5}), dict(wait_error=5)):
            r = Run(**options)
            self.assertEqual(r.byte('RESULT'), 5)
            self.assertEqual(r.events[-2:], ['HAL_SLEEP', 'HAL_RELEASE'])
        r = Run(cleanup=5)
        self.assertEqual(r.byte('VALID'), 7)
        self.assertEqual(r.byte('CLEANUP_ERROR'), 5)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StatusTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    meta = json.loads((OUT / 'build.json').read_text())
    (OUT / 'test-results.json').write_text(json.dumps(dict(
        passed=result.wasSuccessful(), tests=result.testsRun,
        sha256=meta['sha256'], hardware_tested=False, electrical_timing_emulated=False,
        transport='scripted HAL; no physical adapter'), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
