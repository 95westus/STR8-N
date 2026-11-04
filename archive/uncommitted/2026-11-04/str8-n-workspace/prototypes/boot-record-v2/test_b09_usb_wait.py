"""Measure b09's complete silent USB wait with actual linked instructions."""
import argparse
import hashlib
import json
from pathlib import Path
import test_boot_startup as timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--cpu', choices=('65c02','65c816-e'), required=True)
    args = parser.parse_args(); build = args.build.resolve()
    report = json.loads((build/'prototype-report.json').read_bytes())
    assert report['banner'] == '2.0proto b09'
    timing.core.GENERATION = report['experimental_generation']
    h = timing.StartupMachine(build, args.cpu)
    checks = timing.check_instruction_timing(type(h.c))
    h.run(lambda: h.c.pc == h.b['BOOT_STARTUP'])
    timing.seed_software(h)
    initial_RAM = bytes(h.m.ram)
    h.m.rx.extend(b'SAB0123\r\n'*32)
    h.m.acia_rx.extend(b'S')
    begin = h.c.processorCycles
    h.run(lambda: h.c.pc == h.b['BOOT_USB_WAIT_DONE'])
    cycles = h.c.processorCycles-begin
    assert 15_980_000 <= cycles <= 16_020_000, cycles
    assert not h.m.tx and not h.m.acia_tx and not h.m.consumed and not h.m.input_reads
    assert bytes(h.m.rx) == b'SAB0123\r\n'*32 and bytes(h.m.acia_rx) == b'S'
    assert initial_RAM[0xf8:0x100] == bytes(h.m.ram[0xf8:0x100])
    h.preserved()
    result = dict(passed=True, cpu=args.cpu, cycles=cycles, seconds_at_8MHz=cycles/8_000_000,
        actual_linked_instructions=True, accelerated_instructions=False,
        no_output_or_input_access=True, application_RAM_and_flash_unchanged=True,
        hardware=False, serial_access=False, instruction_timing_checks=checks,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        F_sha256=hashlib.sha256((build/'payload/f-offline-component.bin').read_bytes()).hexdigest())
    (build/f'b09-usb-wait-{args.cpu}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
