"""Qualify CLOCK in RAM and optionally save the exact modeled image.

No clock SET is confirmed. RTC control, trim and outage capture are preserved.
--save writes only the backup-bound B2 CLOCK record and normal wear journal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from beta4_migration import Link
from build_v2_clock import OUT
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_rtc_board import load
from serial.tools.list_ports import comports


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--board',required=True,choices=tuple(SERIALS))
    parser.add_argument('--port',required=True)
    parser.add_argument('--save',action='store_true')
    args = parser.parse_args()
    assert next(p for p in comports() if p.device.upper()==args.port.upper()).serial_number==SERIALS[args.board]
    plan = json.loads((args.root/'plan/model-check.json').read_text())
    meta = json.loads((OUT/'build.json').read_text())
    tests = json.loads((OUT/'test-results.json').read_text())
    assert plan['passed'] and tests['passed'] and plan['board']==args.board
    assert plan['sha256']==tests['sha256']==meta['sha256']==sha((OUT/'clock.bin').read_bytes())
    assert plan['s19_sha256']==sha((OUT/'clock.s19').read_bytes())
    out = args.root/'board-check'
    out.mkdir(exist_ok=False)
    report = dict(board=args.board,port=args.port,clock_set_confirmed=False,
        chip_memory_accessed=False,flash_saved=False,sha256=meta['sha256'])
    with (out/'serial.jsonl').open('x') as log:
        link = Link(args.port,log)
        try:
            end = time.monotonic()+.3
            while time.monotonic()<end:
                link.read(max(1,link.serial.in_waiting))
            link.command('',b'> ')
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}',prompt)
                data = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==plan['prior_hashes'][bank], 'Flash changed; no save issued'
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\x00\x65\xFF\x64'
            before = link.dump(0x66C0,0x66FF)
            (out/'before.bin').write_bytes(before)
            if args.board=='2609':
                probe = Path(__file__).resolve().parents[1]/'BUILD/v2-rtc-phase1/816-probe/rtc-816-state.s19'
                report['cpu_probe_sha256'] = load(link,probe)
                (out/'cpu-state.txt').write_bytes(link.command('G 2400'))
                state = link.dump(0x2500,0x2507)
                assert state[0]==1 and state[2:6]==bytes(4)
                report['cpu_entry_state'] = list(state)
            assert load(link,OUT/'clock.s19')==meta['sha256']
            output = link.command('G 2000',b'CLOCK> ')
            (out/'start.txt').write_bytes(output)
            assert b'CLOCK 1.0' in output
            if args.board=='2512':
                assert b'RTC error 01' in output and b'UTC 2026-' not in output
            else:
                assert b'UTC 2026-' in output
            output = link.command('STATUS',b'CLOCK> ')
            (out/'status.txt').write_bytes(output)
            if args.board=='2512':
                assert b'RTC error 01' in output
            else:
                assert b'Running: yes' in output and b'Backup enabled: yes' in output
                assert b'condition: unknown' in output
            output = link.command('SET 2000-01-01 00:00:00',b'CLOCK> ' if args.board=='2512' else b'Type YES to confirm: ')
            (out/'set-prompt.txt').write_bytes(output)
            if args.board=='2512':
                assert b'RTC error 01' in output and b'Type YES' not in output
            else:
                assert b'Requested UTC: 2000-01-01 00:00:00' in output
                output = link.command('NO',b'CLOCK> ')
                (out/'set-cancel.txt').write_bytes(output)
                assert b'Canceled' in output
            output = link.command('SET 2026-02-29 00:00:00',b'CLOCK> ')
            (out/'invalid.txt').write_bytes(output)
            assert b'Invalid command/date' in output and b'Type YES' not in output
            link.send(b'\x03')
            output = link.until(b'CLOCK> ')
            assert b'Canceled' in output
            (out/'control-c.txt').write_bytes(output)
            (out/'help.txt').write_bytes(link.command('HELP',b'CLOCK> '))
            link.command('Q')
            after = link.dump(0x66C0,0x66FF)
            (out/'after.bin').write_bytes(after)
            assert after[41:43]==bytes(2)
            assert after[56]==after[58] and (after[57]^after[59])&after[56]==0
            if args.board!='2512':
                assert after[0]==0 and after[1]&7==7 and int.from_bytes(after[2:4],'little')==2026
                assert after[18:20]==before[18:20], 'Control/trim changed'
                assert after[28]==before[28] and after[48:56]==before[48:56], 'Outage capture changed'
                assert (after[1]^before[1])&0x18==0, 'Powerfail/backup changed'
            report.update(ram_paths_passed=True,invalid_date_rejected=True,
                canceled_set_passed=args.board!='2512',no_edu_handled=args.board=='2512',
                drift_baseline_preserved=True,via_preserved=True)
            if args.save:
                # Reload the pristine artifact: do not save runtime input/state as program bytes.
                assert load(link,OUT/'clock.s19')==meta['sha256']
                output = link.command(plan['command'])
                (out/'save.txt').write_bytes(output)
                assert b'Done' in output
                output = link.command('T 2')
                (out/'table.txt').write_bytes(output)
                assert b'CLOCK' in output
                output = link.command('R 2 CLOCK L')
                (out/'restore-only.txt').write_bytes(output)
                assert b'Done' in output
                assert sha(link.dump(0x2000,meta['end']-1))==meta['sha256']
                output = link.command('R CLOCK',b'CLOCK> ')
                (out/'label-launch.txt').write_bytes(output)
                assert b'CLOCK 1.0' in output
                link.command('QUIT')
                report['flash_saved'] = True
            hashes = []
            expected = plan['expected_hashes'] if args.save else plan['prior_hashes']
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}',prompt)
                data = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert sha(data)==expected[bank],f'Final B{bank} differs from model'
                (out/f'final-b{bank}.bin').write_bytes(data)
                hashes.append(sha(data))
            link.command('B3')
            report.update(passed=True,final_hashes=hashes,stored_label_launch_passed=args.save)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS',args.board,'CLOCK RAM paths, canceled SET, exact save/restore and four-bank readback',flush=True)
        finally:
            link.serial.close()


if __name__=='__main__':
    main()
