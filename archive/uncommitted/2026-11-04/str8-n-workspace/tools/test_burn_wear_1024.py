"""Offline endpoint and sector-restoration checks; never opens a serial port."""
import binascii
import contextlib
import json
from pathlib import Path
import tempfile
import burn_wear_1024 as burn


def check(initial, request_yield=False):
    with tempfile.TemporaryDirectory(dir=burn.ROOT / 'tmp', prefix='wear-burn-model-') as temporary:
        folder = Path(temporary)
        owner = b'\x12' * 0x6300
        low = b'\xa5' * 0xe0
        banks = [bytearray(b'\xff' * 32768) for _ in range(4)]
        tracked = [1] * 32
        tracked[burn.INDEX] = initial
        config = b'\x00' * 16
        counters = dict(commands=0, confirms=0, erases=0, yields=0)

        def update_journal():
            row = bytearray(b'\xff' * 128)
            row[:8] = b'WC\x01\x00' + (counters['erases'] + 1).to_bytes(4, 'little')
            row[8:24] = config
            row[24:120] = b''.join(v.to_bytes(3, 'little') for v in tracked)
            row[120:122] = binascii.crc_hqx(row[:120], 65535).to_bytes(2, 'little')
            row[127] = 0
            banks[3][0x4000:0x4080] = row

        update_journal()
        for n, data in enumerate(banks):
            (folder / f'before-B{n}.bin').write_bytes(data)
        (folder / 'owner-RAM.bin').write_bytes(owner)
        (folder / 'owner-ZP.bin').write_bytes(low)
        burn.save(folder / 'status.json', dict(phase='ready', current_count=initial,
            initial_count=initial, initial_counts=tracked[:], initial_config_hex=config.hex(),
            runner_sha256=burn.sha(Path(burn.__file__).read_bytes())))

        class FakeLink:
            def __init__(self):
                self.bank = 3
                self.serial = self
                self.is_open = True

            def close(self):
                self.is_open = False

            def command(self, text, prompt=burn.MON):
                if text.startswith('B'):
                    self.bank = int(text[1:])
                return prompt

            def dump(self, first, last, prompt=burn.MON):
                if first == 0:
                    return low
                if first == 0x200:
                    return owner
                return bytes(banks[self.bank][first-0x8000:last-0x8000+1])

            def send(self, data):
                if data.startswith(b'F E000 '):
                    assert self.bank == 0
                    counters['commands'] += 1
                    self.value = int(data.split()[2], 16)
                    self.erases = banks[0][0x6000] != 255
                elif data == b'Y\r':
                    counters['confirms'] += 1
                    if self.erases:
                        tracked[burn.INDEX] += 1
                        counters['erases'] += 1
                        assert tracked[burn.INDEX] <= burn.TARGET
                    banks[0][0x6000] = self.value
                    update_journal()
                else:
                    raise AssertionError(data)

            def until(self, token, seconds=0):
                if token == b' Y?':
                    mode = b'Erase+write' if self.erases else b'Program'
                    return f'E000 00>{self.value:02X}\r\n'.encode() + mode + token
                return b'Done' + token

        def pending():
            if request_yield and counters['confirms'] >= 3 and not counters['yields']:
                counters['yields'] += 1
                return True
            return False

        replacements = dict(serial_lease=lambda *a, **k: contextlib.nullcontext(),
            admitted=lambda: {}, connect=lambda log: FakeLink(), counts=lambda link: tracked[:],
            drift_pending=pending)
        previous = {key: getattr(burn, key) for key in replacements}
        try:
            for key, value in replacements.items():
                setattr(burn, key, value)
            burn.run(folder)
        finally:
            for key, value in previous.items():
                setattr(burn, key, value)
        state = json.loads((folder / 'status.json').read_text())
        assert state['passed'] and state['phase'] == 'complete'
        assert state['current_count'] == 1024
        assert counters['erases'] == 1024-initial
        assert counters['commands'] == counters['confirms']
        assert banks[0][0x6000:0x7000] == b'\xff' * 4096
        assert state['target_reached_wall_seconds'] <= state['wall_seconds']
        assert state['serial_released'] and state['firmware_preserved'] and state['owner_RAM_preserved']
        if request_yield:
            assert counters['yields'] == 1
        print('PASS offline endpoint/restoration', initial, 'to 1024; RTC yield', request_yield)


if __name__ == '__main__':
    check(1023)
    check(1000, request_yield=True)
