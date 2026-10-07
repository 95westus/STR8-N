"""Qualify banner/clock utility after physical RESET; never SET RTC time."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from serial.tools.list_ports import comports
from build_v2_rtc_banner import OUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--board',required=True,choices=tuple(SERIALS))
    parser.add_argument('--port',required=True)
    args = parser.parse_args()
    assert next(p for p in comports() if p.device.upper()==args.port.upper()).serial_number==SERIALS[args.board]
    plan = json.loads((args.root/'upgrade/plan.json').read_text())
    meta = json.loads((OUT/'build.json').read_text())
    out = args.root/'banner-check'
    out.mkdir(exist_ok=False)
    report = dict(board=args.board,port=args.port,clock_written=False,flash_written=False,slots=[])
    with (out/'serial.jsonl').open('x') as log:
        link = Link(args.port,log)
        try:
            end = time.monotonic()+.3
            while time.monotonic()<end:
                link.read(max(1,link.serial.in_waiting))
            link.command('',b'> ')
            link.command('B3')
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x03\x00\x65\xFF\x64'
            assert link.dump(0x7D0F,0x7D10)==b'\x07\x89'

            def check_banner(output):
                assert b'STR8-N 2.0b6 B3' in output
                if args.board=='2512':
                    assert b'816N-VEC\r\nRTC unavailable\r\nB3>' in output
                else:
                    assert b'816N-VEC\r\nUTC 2026-' in output
                data = link.dump(0x66C0,0x66FF)
                assert data[0]==(1 if args.board=='2512' else 0)
                assert data[56]==data[58] and (data[57]^data[59])&data[56]==0
                assert data[41:43]==bytes(2)
                return data

            for index,slot in enumerate(('A','B','A')):
                link.command('G F004',b'Enter default [3s]: ')
                link.send(slot.encode())
                output = link.until(b'\r\nB3> ')
                (out/f'slot-{index}-{slot}.txt').write_bytes(output)
                data = check_banner(output)
                assert link.dump(meta['boot']['BOOT_ACTIVE'],meta['boot']['BOOT_ACTIVE'])==bytes((0xA0 if slot=='A' else 0xB0,))
                (out/f'slot-{index}-{slot}.bin').write_bytes(data)
                report['slots'].append(dict(slot=slot,status=data[0],flags=data[1],calendar=list(data[2:10])))
            output = link.command('R CLOCK',b'CLOCK> ')
            (out/'clock.txt').write_bytes(output)
            assert b'CLOCK 1.0' in output
            output = link.command('STATUS',b'CLOCK> ')
            (out/'clock-status.txt').write_bytes(output)
            if args.board!='2512':
                assert b'Running: yes' in output
            output = link.command('Q')
            (out/'clock-return.txt').write_bytes(output)
            after = check_banner(output)
            if args.board!='2512':
                before = (args.root/'prior/rtc-current.bin').read_bytes()
                assert after[18:20]==before[18:20], 'Control/trim changed'
                assert (after[1]^before[1])&0x10==0, 'Backup enable changed'
                if before[1]&8:
                    assert after[1]&8, 'Previously latched powerfail was cleared'
                report.update(powerfail_before=bool(before[1]&8),powerfail_after=bool(after[1]&8),
                    new_powerfail_observed=not bool(before[1]&8) and bool(after[1]&8),
                    observed_outage=list(after[20:28]),captured_outage=list(after[48:56]))
                (out/'rtc-after-return.bin').write_bytes(after)
                assert int.from_bytes(after[2:4],'little')==2026
            # Normal prompts do not trigger a new READ. Reserved RAM/flash stay protected.
            snapshot = link.dump(0x66C0,0x66FF)
            for index,command in enumerate(('M 6500 12','G 6504','F 8000 00','I 8000 8FFF')):
                output = link.command(command)
                (out/f'guard-{index}.txt').write_bytes(output)
                assert b'Protected' in output and b'UTC ' not in output and b'RTC unavailable' not in output
                assert link.dump(0x66C0,0x66FF)==snapshot
            output = link.command('R MAINT',b'> ')
            assert b'BANK MAINT 1.6' in output
            (out/'maint.txt').write_bytes(output)
            output = link.command('Q')
            maintained = check_banner(output)
            if args.board!='2512' and after[1]&8:
                assert maintained[1]&8 and maintained[20:28]==after[20:28]
                assert maintained[28] and maintained[48:56]==after[48:56]
            (out/'maint-return.txt').write_bytes(output)
            report['final_hashes'] = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode()
                link.command(f'B{bank}',prompt)
                data = b''.join(link.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                digest = hashlib.sha256(data).hexdigest()
                assert digest==plan['expected_hashes'][bank],f'B{bank} differs from modeled update'
                (out/f'final-b{bank}.bin').write_bytes(data)
                report['final_hashes'].append(digest)
            link.command('B3')
            report.update(passed=True,via_preserved=True,clock_maint_compatible=True,
                ordinary_prompts_do_not_poll=True,drift_baseline_preserved=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            reset_file = args.root/'upgrade/install/reset-pending.json'
            reset = json.loads(reset_file.read_text())
            reset.update(physical_reset_pending=False,physical_reset_confirmed_by_user=True,
                post_reset_qualification='banner-check/report.json')
            reset_file.write_text(json.dumps(reset,indent=2)+'\n')
            print('PASS',args.board,'UTC/status banner, both slots, CLOCK/MAINT, guards and exact four-bank readback')
        finally:
            link.serial.close()


if __name__=='__main__':
    main()
