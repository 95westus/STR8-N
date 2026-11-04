"""Read-only MON bank-selection recovery after stopping a read-only dump.

No RAM load or execution, reset, flash/config command, or other-board port.
"""
import argparse
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as pf
from host import quiet_capture


def monitor_bank(raw):
    match = re.search(rb'\r\nB([0-3])> $', raw)
    pf.board.r.require(match is not None, 'A completed ordinary MON prompt is required')
    return int(match[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--authorization', required=True, type=Path)
    parser.add_argument('--marker', type=Path, default=pf.MARKER)
    parser.add_argument('--coordination', type=Path, default=pf.board.DEFAULT_COORDINATION)
    args = parser.parse_args(); args.run = args.run.resolve(); args.stage = 'normalize-selection'
    pf.auth_check(pf.board.r.read(args.authorization))
    pf.board.r.require(not args.run.exists(), 'Use a fresh private normalization run')
    args.run.mkdir(parents=True); (args.run / '.gitignore').write_text('*\n')
    original_marker = args.marker.read_bytes()
    with pf.link_for(args, raw_watch=True) as (link, marker):
        old = quiet_capture(link, seconds=1, maximum=8)
        link.send(b'\r')
        prompt = quiet_capture(link, seconds=1, maximum=8)
        selected = monitor_bank(prompt)
        reply = link.command('B3')
        pf.board.r.require(reply.endswith(pf.board.MON_PROMPT), 'B3 selection did not return MON')
        pf.identity(link)
        pf.atomic(args.run / 'normalization-stream.bin', old + prompt + reply)
    pf.board.r.require(args.marker.read_bytes() == original_marker, 'Read-only marker changed')
    pf.save(args.run / 'normalization.json', dict(passed=True, prior_selected_bank=selected,
        selected_bank=3, serial_released=True, marker_unchanged=True,
        owner_RAM_written=False, RAM_executed=False, flash_written=False,
        commands=['CR', 'B3', 'CR', 'D 7D01 7D02', 'D 7D30 7D30']))
    print('PASS ordinary MON selection restored to B3; no RAM execution or flash writes', flush=True)


if __name__ == '__main__':
    main()
