"""Read-only A/B software-RESET qualification of installed optional services."""
import argparse
import json
from pathlib import Path
import time

from beta4_migration import Link
from qualify_v2_rtc_board import load

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    out = args.root / 'slot-check'
    out.mkdir(exist_ok=False)
    build = json.loads((ROOT / 'BUILD/v2-rtc-kernel/build.json').read_text())
    checks = []
    with (out / 'serial.jsonl').open('x') as log:
        link = Link(args.port, log)
        try:
            end = time.monotonic() + .3
            while time.monotonic() < end:
                link.read(max(1, link.serial.in_waiting))
            link.command('', b'> ')
            for slot in ('A', 'B', 'A'):
                link.command('G F004', b'Enter default [3s]: ')
                link.send(slot.encode())
                output = link.until(b'\r\nB3> ')
                (out / f'slot-{len(checks)}-{slot}.txt').write_bytes(output)
                active = link.dump(build['boot']['BOOT_ACTIVE'], build['boot']['BOOT_ACTIVE'])
                assert active == bytes((0xA0 if slot == 'A' else 0xB0,))
                assert link.dump(0x7D04, 0x7D0B) == b'SV\x01\x03\x00\x65\xFF\x64'
                assert link.dump(0x6664, 0x6664) == b'\0'
                load(link, ROOT / 'BUILD/v2-rtc-kernel/client/kernel-client.s19')
                output = link.command('G 2000')
                (out / f'read-{len(checks)}-{slot}.txt').write_bytes(output)
                status = link.dump(0x66C0, 0x66C0)[0]
                assert status == (1 if args.root.name == '2512' else 0)
                checks.append(dict(slot=slot, clock_status=status, reset_cleared_private_state=True))
                print('PASS', args.root.name, slot, 'software RESET, discovery, first clock request', flush=True)
            (out / 'report.json').write_text(json.dumps(dict(passed=True, checks=checks, flash_written=False), indent=2)+'\n')
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
