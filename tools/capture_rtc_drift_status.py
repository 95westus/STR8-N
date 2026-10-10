"""Archive read-only TIME, CLOCK STATUS, TRIM and EUI checks for drift plots."""
import argparse
import json
from pathlib import Path
import re
import time

from beta4_migration import Link
from rtc_boards import SERIALS
from serial.tools.list_ports import comports


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--baseline-index', type=Path, help='Verify current trim against this calibrated baseline index')
    args = p.parse_args()
    baseline_index = json.loads(args.baseline_index.read_text()) if args.baseline_index else {}
    baseline_boards = ({b['board']: b for b in baseline_index['boards']}
                       if args.baseline_index else {})
    expected_steps = ({board: b.get('trim_steps', 0) for board, b in baseline_boards.items()}
                      if args.baseline_index else {'2205': 0, '2609': 0})
    ports = {p.serial_number: p.device for p in comports()}
    excluded = baseline_index.get('excluded_boards', [])
    if '2512' in excluded:
        out = args.root/'2512';out.mkdir(parents=True,exist_ok=True)
        (out/'status-check.json').write_text(json.dumps(dict(passed=True,board='2512',rtc_available=False,
            excluded_from_campaign=True,hardware_checked=False,reason='User excluded: no fitted EDU/RTC',
            clock_set=False,trim_changed=False),indent=2)+'\n')
    for board in dict.fromkeys((() if '2512' in excluded else ('2512',)) + tuple(expected_steps)):
        port = ports[SERIALS[board]]
        out = args.root / board
        out.mkdir(parents=True, exist_ok=True)
        with (out / 'status-serial.jsonl').open('a') as log:
            link = Link(port, log)
            try:
                end = time.monotonic() + .3
                while time.monotonic() < end:
                    link.read(max(1, link.serial.in_waiting))
                initial = link.command('', b'> ')
                if b'CLOCK>' in initial or b'BM>' in initial:
                    link.command('Q')
                link.command('B3')
                if board in expected_steps:
                    descriptor=link.dump(0x7D04,0x7D0B)
                    active=link.dump(0x7D27,0x7D27)[0]
                    if not (active==1 and descriptor[:3]==b'SV\x01' and descriptor[3]&1 and descriptor[4:]==b'\0\x65\xff\x64'):
                        failure=dict(passed=False,board=board,edu_mode='OFF' if active==2 else 'invalid',
                            active_edu_latch=active,service_descriptor_hex=descriptor.hex(),reason='EDU ON and RTC service required before drift sampling')
                        (out/'status-check.json').write_text(json.dumps(failure,indent=2)+'\n')
                        raise RuntimeError(f'{board}: EDU must be ON with RTC service available; no drift measurement taken')
                output = link.command('TIME')
                (out / 'time-status.txt').write_bytes(output)
                report = dict(board=board, port=port, rtc_available=board in expected_steps,
                              clock_set=False, trim_changed=False)
                if board == '2512' and board not in expected_steps:
                    descriptor = link.dump(0x7D04, 0x7D0B)
                    if descriptor == b'SV\x01\0\0\0\xff\x66':
                        assert b'RTCC: unavailable' in output
                        report['edu_mode'] = 'OFF'
                    else:
                        assert descriptor in (b'SV\x01\x03\0\x65\xff\x64',
                                              b'SV\x01\x0f\0\x65\xff\x64')
                        assert b'RTCC: Time unavailable' in output
                        report['edu_mode'] = 'ON'
                    report['service_descriptor_hex'] = descriptor.hex()
                else:
                    report.update(edu_mode='ON',active_edu_latch=active,service_descriptor_hex=descriptor.hex())
                    assert re.search(rb'RTCC: UTC (?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', output)
                    start = link.command('R CLOCK', b'CLOCK> ')
                    (out / 'clock-start.txt').write_bytes(start)
                    status = link.command('STATUS', b'CLOCK> ')
                    (out / 'clock-status.txt').write_bytes(status)
                    trim = link.command('TRIM', b'CLOCK> ')
                    (out / 'trim-status.txt').write_bytes(trim)
                    identity = link.command('EUI', b'CLOCK> ')
                    (out / 'eui-status.txt').write_bytes(identity)
                    assert b'Running: yes' in status and b'Backup enabled: yes' in status
                    raw = bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)', status)[1].decode())
                    steps = expected_steps[board]
                    expected_raw = abs(steps) | (0x80 if steps > 0 else 0)
                    control = baseline_boards.get(board, {}).get('control_register', 0x80)
                    assert not control & 0x7F, 'Coarse/alarm/output owner is outside normal drift analysis'
                    assert raw[7:9] == bytes([control, expected_raw]), 'Control/trim differs from baseline; inspect before plotting'
                    eui = re.search(rb'EUI ([0-9A-F:]{17})', identity)[1].decode()
                    bound = b', unbound' not in identity
                    expected = baseline_boards.get(board, {})
                    assert b', changed' not in identity
                    assert bound == expected.get('identity_bound', True), 'Identity binding state differs from baseline'
                    if 'eui' in expected: assert eui == expected['eui'], 'Factory identity differs from baseline'
                    report.update(trim_register=raw[8], trim_steps=steps, control_register=raw[7],
                                  identity_matches=True, identity_bound=bound, eui=eui)
                    link.command('Q')
                report['passed'] = True
                (out / 'status-check.json').write_text(json.dumps(report, indent=2) + '\n')
                print('PASS status', board, report, flush=True)
            finally:
                link.serial.close()


if __name__ == '__main__':
    main()
