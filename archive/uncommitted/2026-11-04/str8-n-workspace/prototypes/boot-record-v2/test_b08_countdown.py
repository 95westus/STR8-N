"""Execute the complete six-second countdown with corrected linked CPU timing.

USB wait and drain are not skipped and mislabeled as measured here: this
test explicitly enters the chooser after a real BOOT_SELECT call. Their code
is separately compared byte-for-byte with the qualified b07 implementation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import test_boot_startup as timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02', '65c816-e'), required=True)
    args = parser.parse_args(); build = args.build.resolve()
    report = json.loads((build/'prototype-report.json').read_bytes())
    timing.core.GENERATION = report['experimental_generation']
    instruction_checks = timing.check_instruction_timing(
        timing.core.CPU02 if args.cpu == '65c02' else timing.core.CPU816)
    h = timing.StartupMachine(build, args.cpu)
    h.call(h.b['BOOT_SELECT'])
    h.c.pc = h.b['BOOT_START_CHOICES'] + 3
    h.run(lambda: h.c.pc == h.b['BR_COUNTDOWN'])
    assert h.m.ram[h.b['BR_TICKS']] == 6
    h.timer_start = h.c.processorCycles
    started = time.monotonic()
    h.run(lambda: h.c.pc == h.b['BR_DEFAULT'], limit=30_000_000)
    ports = {}
    for port in (1, 2):
        assert h.output(port) == b'6 5 4 3 2 1 0\r\n', (port,h.output(port))
        digits = [(cycle, byte) for cycle, byte in h.writes(port)
                  if cycle >= h.timer_start and byte in b'6543210']
        assert bytes(byte for _,byte in digits) == b'6543210'
        offsets = [cycle - digits[0][0] for cycle,_ in digits]
        assert all(abs(cycles - index*8_000_000) <= 96_000 for index,cycles in enumerate(offsets)), offsets
        ports[str(port)] = dict(offsets_cycles=offsets,
            six_to_zero_seconds_at_8MHz=offsets[-1]/8_000_000)
    h.preserved()
    result = dict(passed=True, cpu=args.cpu, countdown_seconds=6,
        ports=ports, total_phase_cycles=h.c.processorCycles-h.timer_start,
        accelerated_instructions=False, actual_FT245_and_paced_ACIA_paths=True,
        instruction_timing_checks=instruction_checks,
        scope='Chooser only after actual BOOT_SELECT; no fresh USB wait/drain timing claim',
        owner_RAM_and_flash_unchanged=True, hardware=False, serial_access=False,
        device_or_network_attempts=timing.core.ATTEMPTS,
        elapsed_seconds=time.monotonic()-started,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        F_sha256=hashlib.sha256((build/'payload/f-offline-component.bin').read_bytes()).hexdigest())
    (build/('b08-countdown-'+args.cpu+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cpu=args.cpu,ports=ports)),flush=True)


if __name__ == '__main__':
    main()
