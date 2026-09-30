"""Check shared bank prompts and F protection against the linked a22 image."""
import hashlib
import json

import test_v2_a22_sr as sr
import test_v2_monitor as monitor


def main():
    # The original monitor suite's boot helper assumes the older one-tick reset.
    # Use the a22 boot model while retaining its command assertions.
    monitor.boot = sr.flash.boot_flash
    checks = []
    for test in (monitor.check_bank_and_display, monitor.check_modify,
                 monitor.check_hex_and_go, monitor.check_nmi_publication,
                 sr.flash.check_f, sr.flash.check_cancellation,
                 sr.flash.check_failures_and_self):
        test()
        checks.append(test.__name__)
        print('PASS:', test.__name__, flush=True)

    # Exercise the shared reader's carry/status result at the risk prompt.
    # Use a nonresident F sector so successful writes return to the prompt.
    for target in range(4):
        for reply in (f'B{target}\r'.encode(), b'N\r',
                      f'B{(target + 1) % 4}\r'.encode(),
                      f'B{target}X\r'.encode(), b'\x03',
                      b'B\x01\r', b'X' * 41 + b'\r'):
            cpu, mem = sr.flash.boot_flash((target + 1) % 4)
            sr.flash.send(cpu, f'B{target}\r'.encode())
            before = bytes(mem.banks[target])
            prompt = sr.flash.send(cpu, b'F FFFF 00\rY\r')
            assert prompt.endswith(f'Type B{target}> '.encode()), prompt
            out = sr.flash.send(cpu, reply)
            assert out.endswith(f'B{target}> '.encode()), out
            if reply == f'B{target}\r'.encode():
                assert b'Done' in out and mem.events, out
                assert bytes(mem.banks[target]) == before[:-1] + b'\x00'
            else:
                assert b'Canceled' in out and not mem.events, out
                assert bytes(mem.banks[target]) == before
    checks.append('risk prompt: all banks, accept, reject, Ctrl-C, invalid and long input')

    cpu, mem = sr.flash.boot_flash(3)
    before = bytes(mem.banks[3])
    for address in (0x7FFF, 0xE000, 0xE800, 0xEFF0, 0xEFFF):
        out = sr.flash.send(cpu, f'F {address:04X} 00\r'.encode())
        assert b'Protected' in out and not mem.events, out
        assert bytes(mem.banks[3]) == before
    checks.append('F RAM and Bank 3 E protection without mutation')
    report = dict(passed=checks, resident_bytes=sr.boot.REPORT['resident_bytes'],
                  image_sha256=hashlib.sha256(sr.boot.IMAGE).hexdigest(),
                  physical_hardware_tested=False)
    (sr.a22.OUT / 'f-size-test-results.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print('PASS: shared F prompts and protection', flush=True)


if __name__ == '__main__':
    main()
