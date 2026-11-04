"""Read-only CLOCK identity comparison; no RAM upload or nonvolatile write."""
import json
import argparse
import time
from pathlib import Path
import install_2512_native_utilities as d
from installer.engine.legacy_transport import Link
from serial.tools.list_ports import comports

t = d.t
OUT = t.ROOT / 'output/qualification/CLOCK-reference-20261031-r1'


def run():
    OUT.mkdir(exist_ok=False)
    (OUT / '.gitignore').write_text('*\n')
    result = dict(flash_writes=0, RAM_uploads=0, RTC_writes=0, boards={})
    with t.serial_lease('CLOCK-readonly-reference', timeout=30):
        for board, port, usb in [('2205','COM3','A10MPUPNA'),
                                 ('2512','COM4','A10MQFLCA'),
                                 ('2609','COM8','A10MPQXCA')]:
            folder = OUT / board
            folder.mkdir()
            record = result['boards'][board] = dict(port=port, passed=False)
            s = link = None
            try:
                assert any(p.device == port and p.serial_number == usb for p in comports())
                with (folder / 'serial.jsonl').open('x') as log:
                    if board == '2205':
                        link = Link(port, log)
                        link.send(b'\r')
                        end = time.monotonic() + 8
                        while not any(p in link.pending for p in (b'B3> ', b'CLOCK> ')):
                            if time.monotonic() >= end:
                                raise TimeoutError(repr(link.pending))
                            link.pending.extend(link.read(max(1, link.serial.in_waiting)))
                        prompt = b'CLOCK> ' if b'CLOCK> ' in link.pending else b'B3> '
                        initial = link.until(prompt, seconds=1)
                        (folder / 'prompt.txt').write_bytes(initial)
                        if prompt == b'CLOCK> ':
                            for cmd in ('HELP', 'TIME', 'STATUS', 'HISTORY', 'STATS'):
                                (folder / (cmd + '.txt')).write_bytes(link.command(cmd, prompt))
                            record.update(active_CLOCK_readonly_reference=True, final_prompt='CLOCK>')
                        else:
                            (folder / 'table.txt').write_bytes(link.command('T'))
                            # Do not execute its automatic battery-policy latch.
                            link.command('B1', b'B1> ')
                            try:
                                body = link.dump(0xB000, 0xDFFF, b'B1> ')
                                (folder / 'CLOCK-record.bin').write_bytes(body)
                            finally:
                                link.command('B3', b'B3> ')
                            known = (t.ROOT / 'release/beta35/clock/storage.bin').read_bytes()
                            record.update(CLOCK_record_sha256=t.sha(body),
                                          exact_b35_CLOCK_1_10=body == known,
                                          final_prompt='B3>')
                    else:
                        s = d.Session(folder, log, board)
                        link = s.link
                        link.send(b'\r')
                        s.until((t.MON, t.REC), seconds=8)
                        original = s.context
                        if original == t.REC:
                            s.command('B', (t.MON,))
                        (folder / 'VERSION.txt').write_bytes(s.command('VERSION'))
                        s.command('B2', (b'B2> ',))
                        header = s.command('D B000 B03F')
                        (folder / 'CLOCK-header.txt').write_bytes(header)
                        s.command('B3', (t.MON,))
                        if original == t.REC:
                            s.command('Q', (t.REC,))
                        record['final_prompt'] = s.context.decode().strip()
                    record['passed'] = True
            except Exception as error:
                record['error'] = repr(error)
            finally:
                if link:
                    link.serial.close()
                record['port_released'] = True
                t.save(OUT / 'report.json', result)
                print(board, json.dumps(record), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.out.resolve()
    run()
