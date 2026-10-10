"""Qualify beta23 pending EDU notices, J3 activation and reclaimed RAM."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--board', required=True, choices=tuple(SERIALS))
    p.add_argument('--port', required=True)
    a = p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    assert json.loads((a.root/'installed-check/report.json').read_text())['passed']
    plan = json.loads((a.root/'upgrade/plan.json').read_text()); assert plan['version']=='2.0b23'
    out = a.root/'reset-notice-check'; out.mkdir(exist_ok=False)
    original_off = plan['saved_edu']==0xA5
    checks = []; report = dict(passed=False, board=a.board, checks=checks, clock_set=False, trim_changed=False)
    with (out/'serial.jsonl').open('x') as log:
        link = Link(a.port, log)
        try:
            time.sleep(.3); link.command('', b'> '); link.command('B3')
            def command(text, prompt=b'\r\nB3> ', label=None):
                data = link.command(text, prompt)
                if label: (out/(label+'.txt')).write_bytes(data)
                return data
            def state(off):
                assert link.dump(0x7D04,0x7D0B)==(b'SV\x01\0\0\0\xff\x66' if off else b'SV\x01\x0f\0\x65\xff\x64')
                assert link.dump(0x7D27,0x7D27)==bytes([2 if off else 1])
            state(original_off)
            for turn, target_off in enumerate((not original_off, original_off), 1):
                active_off = not target_off; active = b'OFF' if active_off else b'ON'; target = b'OFF' if target_off else b'ON'
                command('R EDU', b'EDU> ')
                clean = command('?', b'EDU> ', f'clean-{turn}')
                assert b'RESET required:' not in clean
                command(target.decode(), b'Apply after RESET? [y/N]: ')
                canceled = command('N', b'EDU> ', f'cancel-{turn}')
                assert b'Saved; RESET required.' not in canceled
                command(target.decode(), b'Apply after RESET? [y/N]: ')
                saved = command('Y', b'EDU> ', f'saved-{turn}')
                assert b'Saved; RESET required.' in saved
                pending = command('?', b'EDU> ', f'pending-{turn}')
                assert b'EDU '+active+b'\r\nRESET required: '+target in pending
                command('Q'); state(active_off)
                quiet = command('M1', label=f'monitor-return-{turn}')
                assert b'STR8-N ' not in quiet and b'RTCC:' not in quiet
                command('R EDU', b'EDU> ')
                assert b'RESET required: '+target in command('?', b'EDU> ', f'returned-pending-{turn}')
                command('Q'); state(active_off)
                boot = command('J3', b'Enter default [3s]: ')
                link.send(b'\r'); boot += link.until(b'\r\nB3> ')
                (out/f'activation-{turn}.txt').write_bytes(boot)
                assert b'STR8-N 2.0b23' in boot; state(target_off)
                command('R EDU', b'EDU> ')
                assert b'RESET required:' not in command('?', b'EDU> ', f'cleared-{turn}')
                command('Q')
                if target_off:
                    prior = link.dump(0x6500,0x66FF)
                    pattern = bytes((i*19+7)&255 for i in range(512))
                    link.write_ram(0x6500,pattern)
                    assert link.dump(0x6500,0x66FF)==pattern
                    link.write_ram(0x6500,prior)
                    checks.append('OFF reclaimed 512-byte service RAM edit/read/restore')
            state(original_off)
            probes = ROOT/'BUILD/v2-board-regression'
            load_image(link,probes/'abi.s19')
            assert b'RAM ABI: PASS' in command('G 2000', label='abi')
            handlers = link.dump(0x7E00,0x7E1B)
            load_image(link,probes/'irq.s19')
            assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in command('G 2000', label='irq')
            assert link.dump(0x7E00,0x7E1B)==handlers
            checks.extend(['Both canceled/confirmed mode directions, saved/pending notices and quiet-return persistence',
                           'J3 cold activation and pending-notice clearance, original saved mode restored',
                           'RAM ABI and BRK/VIA1 IRQ with vector restoration'])
            hashes = []
            for bank in range(4):
                prompt = f'\r\nB{bank}> '.encode(); link.command(f'B{bank}',prompt)
                data = b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                expected = (a.root/f'upgrade/expected-b{bank}.bin').read_bytes()
                if bank==3:
                    assert data[:0x4000]==expected[:0x4000] and data[0x5000:]==expected[0x5000:]
                    report['configuration_journal_append_hex']=data[0x4000:0x5000].hex()
                else: assert data==expected
                (out/f'b{bank}.bin').write_bytes(data); hashes.append(hashlib.sha256(data).hexdigest())
            link.command('B3')
            report.update(passed=True, final_flash_hashes=hashes, original_mode_restored=True,
                          configuration_changes=2, physical_nmi_pending=True, repeated_physical_reset_pending=True)
        except Exception as e:
            report['error']=repr(e); raise
        finally:
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n'); link.serial.close()
    print('PASS',a.board,'beta23 EDU notices, J3, reclaimed RAM and ABI/IRQ')


if __name__=='__main__': main()
