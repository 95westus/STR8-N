"""Bounded native-console inventory only; no loads, jumps, resets or writes."""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tmp/migration-python')]
from installer.engine.legacy_transport import Link
from serial_test_coordination import serial_lease
from serial.tools.list_ports import comports

BOARDS = {'2205': 'A10MPUPNA', '2512': 'A10MQFLCA',
          '2604': 'A10MQGVHA', '2609': 'A10MPQXCA'}
utc = lambda: datetime.now(timezone.utc).isoformat()


def main(folder):
    folder = folder.resolve()
    assert folder.is_relative_to(ROOT / 'output/qualification')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / '.gitignore').write_text('*\n')
    rows = []
    for board, usb in BOARDS.items():
        row = dict(board=board, usb_serial=usb, started_utc=utc(), passed=False,
                   flash_writes=False, RAM_loads=False, RTC_accesses=False,
                   SPI_accesses=False, resets=False, bank_selections=False)
        rows.append(row)
        link = None
        try:
            with serial_lease('console-inventory-' + board, timeout=5):
                marker = json.loads((ROOT / 'output/qualification/device-operations' /
                                     (board + '.json')).read_text())
                assert not any(marker.get(k) for k in (
                    'application_RAM_restore_pending', 'one_shot_collection_active',
                    'physical_reset_pending', 'owner_application_running', 'power_off_reported'))
                assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
                ports = [p for p in comports() if p.serial_number == usb]
                assert len(ports) == 1, 'Need exactly one matching USB serial'
                row['port'] = ports[0].device
                with (folder / (board + '-serial.jsonl')).open('x') as log:
                    try:
                        link = Link(row['port'], log)
                        initial = bytearray()
                        deadline = time.monotonic() + .6
                        while time.monotonic() < deadline:
                            initial.extend(link.read(4096))
                        assert all(c in (8, 9, 10, 13, 127) or 32 <= c <= 126 for c in initial), 'Non-console traffic'
                        assert b'SEND BIN' not in initial and b'type YES' not in initial, 'Transfer/confirmation active'
                        # CR requests a fresh prompt. Never issue Ctrl-C or RESET.
                        link.send(b'\r')
                        reply = bytearray()
                        deadline = time.monotonic() + 5
                        prompt = None
                        while time.monotonic() < deadline:
                            reply.extend(link.read(4096))
                            match = re.search(rb'(?:\r?\nB[0-3]> |REC> )$', reply)
                            if match:
                                prompt = match[0]
                                break
                        (folder / (board + '-initial.txt')).write_bytes(initial + reply)
                        assert prompt, 'No admitted idle prompt; no further command sent'
                        row['initial_prompt'] = prompt.decode().strip()
                        commands = ['?']
                        if row['initial_prompt'] == 'B3>':
                            commands += ['M1', 'W', 'D A000 A03F', 'D B000 B03F']
                        row['commands'] = commands
                        for index, command in enumerate(commands):
                            link.send(command.encode('ascii') + b'\r')
                            output = link.until(prompt, seconds=12)
                            (folder / f'{board}-{index:02d}.txt').write_bytes(output)
                        row.update(passed=True, final_prompt=row['initial_prompt'])
                    finally:
                        if link is not None:
                            link.serial.close()
                            row['port_released'] = not link.serial.is_open
        except Exception as error:
            row['error'] = repr(error)
        row['finished_utc'] = utc()
        (folder / 'summary.json').write_text(json.dumps(dict(boards=rows), indent=2) + '\n')
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    main(parser.parse_args().folder)
