"""Qualify installed RTC/I2C services without clock or flash writes."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time

from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
from serial.tools.list_ports import comports

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--board', required=True, choices=tuple(SERIALS))
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    assert next(p for p in comports() if p.device == args.port).serial_number == SERIALS[args.board]
    plan = json.loads((args.root / 'upgrade/plan.json').read_text())
    out = args.root / 'service-check'
    out.mkdir(exist_ok=False)
    report = dict(board=args.board, port=args.port, clock_written=False,
                  flash_written=False, readings=[])
    with (out / 'serial.jsonl').open('x') as log:
        link = Link(args.port, log)
        try:
            end = time.monotonic() + .3
            while time.monotonic() < end:
                link.read(max(1, link.serial.in_waiting))
            link.command('', b'> ')
            link.command('B3')
            descriptor = link.dump(0x7D04, 0x7D0B)
            assert descriptor == b'SV\x01\x03\x00\x65\xFF\x64'
            assert link.dump(0x6500, 0x6503) == b'RG\x01\x04'
            assert link.dump(0x6510, 0x6513) == b'I2\x01\x01'
            assert link.dump(0x6664, 0x6664) == b'\0', 'Not a fresh reset: first-request test refused'
            assert link.dump(0x7E60, 0x7E63) == b'RA\x01\x0d'
            report['descriptor'] = descriptor.hex()
            report['cold_state_uninitialized'] = True
            if args.board == '2609':
                report['cpu_probe_sha256'] = load(link, ROOT / 'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19')
                (out / 'cpu-state.txt').write_bytes(link.command('G 2400'))
                state = link.dump(0x2500, 0x2507)
                assert state[0] == 1 and state[2:6] == bytes(4)
                report['cpu_entry_state'] = list(state)
            report['client_sha256'] = load(link, ROOT / 'BUILD/v2-rtc-kernel/client/kernel-client.s19')

            def capture(label, entry):
                output = link.command(f'G {entry:04X}')
                (out / f'{label}.txt').write_bytes(output)
                data = link.dump(0x66C0, 0x66FF)
                (out / f'{label}.bin').write_bytes(data)
                item = dict(label=label, status=data[0], flags=data[1],
                            calendar=list(data[2:10]), raw=list(data[11:20]),
                            outage=list(data[20:28]), evidence_valid=data[28],
                            captured_outage=list(data[48:56]))
                assert data[56] == data[58], 'VIA DDRA changed'
                assert (data[57] ^ data[59]) & data[56] == 0, 'Driven VIA output changed'
                assert link.dump(0x6664, 0x6664) == b'\x02', 'HOLD lost initialized state'
                report['readings'].append(item)
                print(args.board, output.decode('ascii').strip(), flush=True)
                return item

            first = capture('first-read', 0x2000)
            time.sleep(1.2)
            second = capture('second-read', 0x2000)
            capture('status', 0x2003)
            if args.board == '2512':
                assert first['status'] in (1, 2) and second['status'] == first['status']
                report['absent_edu_handled'] = True
            else:
                def moment(item):
                    c = item['calendar']
                    return datetime(c[0] + 256*c[1], c[2], c[3], c[5], c[6], c[7])
                assert first['status'] == second['status'] == 0
                assert moment(second) > moment(first), 'RTC did not advance'
                report['clock_advanced'] = True
            banks = link.command('G 200C')
            (out / 'bank-calls.txt').write_bytes(banks)
            assert b'RTC banks preserved' in banks
            report['bank_statuses'] = list(link.dump(0x2450, 0x2453))
            assert report['bank_statuses'] == [second['status']] * 4
            bus = link.command('G 200F')
            (out / 'i2c.txt').write_bytes(bus)
            result = link.dump(0x6658, 0x665B)
            report['i2c_result'] = list(result)
            (out / 'i2c-rtc-registers.bin').write_bytes(link.dump(0x2420, 0x2428))
            if args.board == '2512':
                assert result[0] in (1, 2) and result[1:3] == b'\0\0'
            else:
                assert result[:3] == b'\0\x01\x09'
            service = link.dump(0x6500, 0x66FF)
            for index, command in enumerate(('M 6500 12', 'G 6504', 'I 8000 8FFF', 'F 8000 00')):
                response = link.command(command)
                (out / f'guard-{index}.txt').write_bytes(response)
                assert b'Protected' in response
                assert link.dump(0x6500, 0x66FF) == service
            response = link.command('R MAINT', b'> ')
            (out / 'maint-start.txt').write_bytes(response)
            assert b'BANK MAINT 1.6' in response
            for index, command in enumerate(('E 3 8', 'C R 6400 6401 R 6500', 'M')):
                response = link.command(command, b'> ')
                (out / f'maint-{index}.txt').write_bytes(response)
                if index < 2:
                    assert any(word in response for word in (b'INVALID', b'PROTECTED', b'CANCELED'))
                    assert b'Y?' not in response
                else:
                    assert b'RTC/I2C services' in response and b'6500-66FF services protected' in response
            link.command('Q')
            assert link.dump(0x6500, 0x66FF) == service
            report['maint_relocated_and_guards_passed'] = True
            report['final_flash_hashes'] = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}', prompt)
                data = b''.join(link.dump(a, a+4095, prompt) for a in range(0x8000,0x10000,4096))
                digest = hashlib.sha256(data).hexdigest()
                assert digest == plan['expected_hashes'][bank], f'B{bank} differs from modeled upgrade'
                (out / f'final-b{bank}.bin').write_bytes(data)
                report['final_flash_hashes'].append(digest)
            link.command('B3')
            report.update(passed=True, via_preserved=True, all_banks_preserved=True)
            (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
            print('PASS', args.board, 'installed services, MAINT, guards, and exact four-bank readback', flush=True)
        finally:
            link.serial.close()


if __name__ == '__main__':
    main()
