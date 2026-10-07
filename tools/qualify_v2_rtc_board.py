"""Load verified RTC service/client into RAM and capture board evidence.

Default operation reads only. Clock setting and outage acknowledgment require
explicit options. No flash operations, SRAM/EEPROM operations, alarm programming,
physical reset, or power cycling are issued.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from beta4_migration import Link, read_s19

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'BUILD/v2-rtc-phase1'


def load(link, path):
    cells, entry = read_s19(path)
    assert min(cells) >= 0x2000 and max(cells) <= 0x3FFF
    link.command('L', b'S19')
    for line in path.read_bytes().splitlines():
        link.send(line + b'\r\n')
        time.sleep(.04)
    link.until(b'\r\nB3> ')
    actual = link.dump(min(cells), max(cells))
    expected = bytes(cells[a] for a in range(min(cells), max(cells) + 1))
    if actual != expected:
        raise IOError('RAM readback mismatch: execution refused')
    return hashlib.sha256(actual).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--board', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--set-current-utc', action='store_true')
    parser.add_argument('--ack-powerfail', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    build = json.loads((BUILD / 'build.json').read_text())
    tests = json.loads((BUILD / 'test-results.json').read_text())
    assert tests['passed']
    assert tests['service_sha256'] == build['images']['rtc-service']['sha256']
    for name, meta in build['images'].items():
        assert hashlib.sha256((BUILD / f'{name}.bin').read_bytes()).hexdigest() == meta['sha256']
    report = dict(board=args.board, port=args.port, mode='read-only', flash_written=False,
                  memory_implemented=False, images={}, readings=[])
    with (args.out / 'serial.jsonl').open('x', encoding='utf-8') as log:
        link = Link(args.port, log)
        try:
            stop = time.monotonic() + .3
            while time.monotonic() < stop:
                link.read(max(1, link.serial.in_waiting))
            link.command('', b'> ')
            link.command('B3')
            assert link.dump(0x7E60, 0x7E63) == b'RA\x01\x0d'
            report['images']['rtc-client'] = load(link, BUILD / 'rtc-client.s19')
            # Exercise optional software discovery before installing the driver.
            link.command('M 3000 00 00 00 00')
            missing = link.command('G 2000')
            (args.out / 'no-service.txt').write_bytes(missing)
            assert b'RTC service unavailable' in missing
            report['service_absence_handled'] = True
            report['images']['rtc-service'] = load(link, BUILD / 'rtc-service.s19')

            def reading(label, entry=0x2000):
                output = link.command(f'G {entry:04X}')
                (args.out / f'{label}.txt').write_bytes(output)
                data = link.dump(0x3F00, 0x3F3B)
                (args.out / f'{label}.bin').write_bytes(data)
                fields = list(data[2:10])
                item = dict(label=label, status=data[0], flags=data[1],
                            year=int.from_bytes(data[2:4], 'little'),
                            calendar=fields, raw=list(data[11:20]),
                            outage=list(data[20:28]), evidence_valid=data[28],
                            captured_outage=list(data[48:56]))
                item['via_before'] = list(data[56:58])
                item['via_after'] = list(data[58:60])
                assert data[56] == data[58], 'VIA DDRA changed'
                assert (data[57] ^ data[59]) & data[56] == 0, 'Driven VIA output changed'
                report['readings'].append(item)
                print(args.board, output.decode('ascii', 'backslashreplace').strip(), flush=True)
                (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
                return item

            reading('initial')
            time.sleep(1.2)
            reading('repeat')
            if args.set_current_utc:
                # Existing raw RTC/outage evidence is on disk before this write.
                now = datetime.now(timezone.utc)
                fields = [now.year & 255, now.year >> 8, now.month, now.day,
                          now.isoweekday(), now.hour, now.minute, now.second]
                link.command('M 3F20 ' + ' '.join(f'{v:02X}' for v in fields))
                link.command('M 3F29 53 54')
                report['mode'] = 'explicit clock set UTC'
                report['requested_utc'] = now.isoformat()
                item = reading('set', 0x2003)
                if item['status']:
                    raise IOError(f'RTC SET failed: {item["status"]}; inspect evidence before retry')
                # Cold crystal startup may take longer than the first sample.
                # Require an advancing successful READ within a finite bound.
                def moment(sample):
                    c = sample['calendar']
                    return datetime(c[0] + 256*c[1], c[2], c[3], c[5], c[6], c[7],
                                    tzinfo=timezone.utc)
                if not item['flags'] & 4:
                    raise IOError('SET readback calendar invalid; inspect before retry')
                set_time = moment(item)
                for attempt in range(10):
                    time.sleep(1.2)
                    label = 'after-set' if attempt == 0 else f'after-set-{attempt+1}'
                    sample = reading(label)
                    if sample['status'] == 0 and moment(sample) > set_time:
                        report['clock_advanced_after_set'] = True
                        break
                    if sample['status'] not in (0, 4):
                        raise IOError(f'Clock verification transport error: {sample["status"]}')
                else:
                    raise IOError('Clock did not become usable and advance within bounded startup checks')
            if args.ack_powerfail:
                link.command('M 3F29 50 41')
                report['ack_requested'] = True
                item = reading('ack', 0x2006)
                if item['status']:
                    raise IOError(f'RTC ACK failed: {item["status"]}')
            banks = link.command('G 2009')
            (args.out / 'bank-calls.txt').write_bytes(banks)
            assert b'RTC calls B0-B3: bank preserved' in banks
            report['bank_calls'] = list(link.dump(0x3F3C, 0x3F3F))
            assert report['bank_calls'] == [report['readings'][-1]['status']] * 4
            report.update(via_ddra_preserved=True, driven_via_outputs_preserved=True,
                          completed=True)
            (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
