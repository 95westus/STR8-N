"""Read the proposed BM flash-test sector through the existing monitor only."""
import argparse
import json
import re
from pathlib import Path
import install_2512_native_utilities as d

t = d.t


def run(board, folder):
    folder = Path(folder).resolve()
    assert folder.is_relative_to(t.ROOT / 'output/qualification')
    folder.mkdir(exist_ok=False)
    (folder / '.gitignore').write_text('*\n')
    marker = json.loads((t.ROOT / f'output/qualification/device-operations/{board}.json').read_text())
    assert not marker['application_RAM_restore_pending']
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    r = dict(board=board, passed=False, flash_writes=0, owner_RAM_writes=0,
             RTC_writes=0, SRAM_writes=0, port_released=False)
    with t.serial_lease(board + '-BANK-MAINT-target-readonly', timeout=30):
        with (folder / 'serial.jsonl').open('x') as log:
            s = None
            try:
                s = d.Session(folder, log, board)
                s.link.send(b'\r')
                s.until((t.MON, t.REC, b'B0> '), seconds=12)
                original = s.context
                if original == t.REC:
                    s.command('B', (t.MON,))
                elif original == b'B0> ':
                    s.command('B3', (t.MON,))
                assert b'g0000000C / MON B' in s.command('VERSION')
                s.command('B0', (b'B0> ',))
                output = s.command('D 9000 9FFF')
                cells = {}
                for line in output.decode('ascii').splitlines():
                    row = re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})', line.strip())
                    if row:
                        cells.update((int(row[1], 16) + i, b) for i, b in enumerate(bytes.fromhex(row[2])))
                assert all(a in cells for a in range(0x9000, 0xA000))
                body = bytes(cells[a] for a in range(0x9000, 0xA000))
                assert len(body) == 4096
                (folder / 'B0-9000-before.bin').write_bytes(body)
                r.update(sha256=t.sha(body), blank=body == b'\xff' * 4096)
                r['passed'] = True
                print('PASS ' + board + ' exact B0:9 read-only capture', flush=True)
            finally:
                try:
                    if s is not None and s.context in (t.MON, b'B0> '):
                        s.command('B3', (t.MON,))
                        if original == t.REC:
                            s.command('Q', (t.REC,))
                finally:
                    if s is not None:
                        s.link.close()
                        r['port_released'] = True
                    t.save(folder / 'report.json', r)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board', choices=['2512', '2609'], required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    run(a.board, a.out)
