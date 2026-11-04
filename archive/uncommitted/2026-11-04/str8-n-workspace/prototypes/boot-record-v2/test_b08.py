"""Offline linked CPU regression and recovery bank/selection checks, both CPUs."""
import argparse
import json
from pathlib import Path

import test_b07 as previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--selection-only', action='store_true', help='Reuse exact already-passed core component hashes')
    args = parser.parse_args(); build = args.build.resolve()
    manifest = json.loads((build / 'prototype-report.json').read_bytes())
    assert manifest['banner'] == '2.0proto b08' and manifest['experimental_generation'] == 0x80000008
    assert manifest['startup_sequence']['countdown_seconds'] == 6
    assert manifest['startup_countdown']['seconds_at_8MHz'] == 6
    core, adaptation = previous.load_core()
    if not args.selection_only:
        core.main()
    old = json.loads((build / 'cpu-tests.json').read_bytes())
    assert old['passed'] and old['checks'] == 352 and old['failures'] == 0
    assert all(core.sha((build/'payload'/name).read_bytes()) == digest
               for name, digest in old['component_hashes'].items())
    core.GENERATION = manifest['experimental_generation']
    rows = []

    def passed(cpu, case, **details):
        rows.append(dict(cpu=cpu, case=case, passed=True, **details))

    for cpu in ('65c02', '65c816-e'):
        for port in (1, 2):
            for ending in (b'\r', b'\n', b'\r\n'):
                for bank in range(4):
                    h = core.Machine(build, cpu, [(0xc000, core.record())], opaque=True)
                    application = bytes(h.m.ram[0x200:0x6500])
                    owner_zp = bytes(h.m.ram[:0xe0])
                    h.recovery()
                    # FT writes precede their paced ACIA mirror. Reach the
                    # next input call before measuring a new command's text.
                    h.run(lambda: h.c.pc == h.b['BOOT_B08_READ_LINE'])
                    h.port_command(port, b'C' + bytes([ord('0')+port]) + b'\r')
                    h.run(lambda: h.c.pc == h.b['BOOT_B08_READ_LINE'])
                    n = len(h.m.tx if port == 1 else h.m.acia_tx)
                    (h.m.rx if port == 1 else h.m.acia_rx).extend(str(bank).encode() + ending)
                    h.run(lambda: h.m.bank == bank and h.c.pc == 0x8000)
                    output = bytes((h.m.tx if port == 1 else h.m.acia_tx)[n:])
                    assert output.startswith(str(bank).encode()+b'\r\n'), (cpu,port,ending,bank,repr(output))
                    assert h.c.sp == 255 and not h.m.events
                    assert bytes(h.m.ram[0x200:0x6500]) == application
                    assert bytes(h.m.ram[:0xe0]) == owner_zp
                    assert h.m.banks[3][0x2000:0x4000] == b'\xff'*8192, 'MON unexpectedly present'
                    passed(cpu, f'recovery-bank-{bank}-port-{port}-{ending.hex()}', MON_absent=True)
            for key in (b'S', b's', b'\x03'):
                h = core.Machine(build, cpu, [(0xc000, core.record())], opaque=True)
                h.run(lambda: h.c.pc == h.b['BR_WINDOW'])
                n = len(h.m.tx if port == 1 else h.m.acia_tx)
                (h.m.rx if port == 1 else h.m.acia_rx).extend(key)
                h.run(lambda: bytes(h.m.tx if port == 1 else h.m.acia_tx).endswith(b'REC> '))
                output = bytes((h.m.tx if port == 1 else h.m.acia_tx)[n:])
                assert output.startswith(b'\r\nRecovery L/R/D/V A/B 0-3 C1/2/3\r\n'), output
                assert not h.m.events
                passed(cpu, f'chooser-CRLF-{key.hex()}-port-{port}')
        for name, record in [('disabled-bank-0', core.record(mask=14)),
                             ('bad-bank-3-page-C', core.record(pages=(8,8,8,12))),
                             ('bad-bank-3-page-D', core.record(pages=(8,8,8,13)))]:
            h = core.Machine(build, cpu, [(0xc000, record)], opaque=True)
            h.recovery(); key = b'0' if name.startswith('disabled') else b'3'
            out = h.command(key+b'\r')
            assert h.m.bank == 3 and b'Recovery ' in out and not h.m.events
            passed(cpu, name)
        h = core.Machine(build, cpu, [(0xc000, core.record())], opaque=True)
        h.recovery()
        prompt_stack = h.c.sp
        h.m.banks[3][0x4000:0x4100] = core.record(seq=2, mask=14)
        for _ in range(8):
            out = h.command(b'0\r')
            assert b'Recovery ' in out and h.c.sp == prompt_stack and not h.m.events
        passed(cpu, 'fresh-record-recheck-and-repeated-refusal-no-stack-leak')
        for bad in (b'00\r', b'0junk\r', b'4\r'):
            h = core.Machine(build, cpu, [(0xc000, core.record())], opaque=True)
            h.recovery(); out = h.command(bad)
            assert b'REFUSED: command' in out and not h.m.events
            passed(cpu, 'exact-bank-line-' + bad.hex())
    report = dict(passed=True, checks=old['checks']+len(rows), failures=0,
        baseline_regression_groups=old['checks'], new_selection_groups=len(rows),
        exact_core_regression_receipt_reused=args.selection_only,
        hardware=False, serial_access=False, device_or_network_attempts=core.ATTEMPTS,
        cases=rows, baseline_report_sha256=core.sha((build/'cpu-tests.json').read_bytes()),
        checker_sha256=core.sha(Path(__file__).read_bytes()),
        prototype_report_sha256=core.sha((build/'prototype-report.json').read_bytes()),
        frozen_b07_checker_adaptation=adaptation)
    core.save(build/'b08-selection-tests.json', report)
    print('PASS b08 groups',report['checks'],'new',len(rows),flush=True)


if __name__ == '__main__':
    main()
