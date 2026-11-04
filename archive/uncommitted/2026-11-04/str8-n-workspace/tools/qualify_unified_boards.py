"""Verify both existing boards against the unified build with preserving RAM trials.

No flash-programming or CONFIG-setting command exists in this workflow.
Only a fixed-range owner RAM restore is sent to the binary readback service.
Private receipts and captures stay outside the standalone public project.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'prototypes/boot-record-v2'), str(ROOT/'tools'),
                str(ROOT/'tmp/migration-python')]
import board_ram_config_2512 as io

PROJECT = ROOT/'bootstrap-opaque'
BUILD = PROJECT/'firmware'
USB = {'2512': 'A10MQFLCA', '2609': 'A10MPQXCA'}
APP_COMMANDS = {'CONFIG': ('?', 'B', 'C', 'W'),
                'MAINT': ('?', 'M 1', 'M 3', 'R 3 F000 F00F', 'K', 'V 3 F000 F00F 3 F000')}
MAINT = b'MAINT RO> '


def log_name(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    assert name and name not in ('.', '..')
    return name


def admit():
    result = subprocess.run([sys.executable, '-B', str(PROJECT/'tools/verify_system.py')],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    profiles = io.read(PROJECT/'profiles.json')
    info = io.read(BUILD/'system-manifest.json')
    sy = io.read(BUILD/'system-symbols.json')
    all_artifacts = dict(io.read(BUILD/'manifest.json')['artifacts'], **info['artifacts'])
    assert len(all_artifacts) == 18
    for name, value in all_artifacts.items():
        assert io.sha((BUILD/'payload'/name).read_bytes()) == value['sha256']
    assert APP_COMMANDS['CONFIG'] == ('?', 'B', 'C', 'W')
    assert APP_COMMANDS['MAINT'][-1] == 'V 3 F000 F00F 3 F000'
    return profiles, sy, all_artifacts


def verify_components(banks, profile):
    assert len(banks) == 4 and all(len(data) == 32768 for data in banks)
    for target, name in profile['installed_components'].items():
        bank, sector = int(target[1]), int(target[3], 16)
        offset = (sector-8)*4096
        assert banks[bank][offset:offset+4096] == (BUILD/'payload'/name).read_bytes(), target+' differs from unified build'
    return io.latest(banks)


def settings_text(row):
    text = b'DEFAULT='+row[7:8]+b'\r\n'
    for bank in range(4):
        text += (f'B{bank} '+('ON  ' if row[13] & 1 << bank else 'OFF ')+
                 f'ENTRY={row[14+bank]:X}000\r\n').encode()
    return text


def sync(link):
    data = bytearray()
    begin = last = time.monotonic()
    while time.monotonic()-last < .5:
        assert time.monotonic()-begin < 10, 'Continuous serial output; no commands issued'
        part = link.read(4096)
        if part:
            data.extend(part)
            last = time.monotonic()
    assert all(c in (8, 9, 10, 13, 127) or 32 <= c <= 126 for c in data)
    link.send(b'\r')
    reply = bytearray()
    end = time.monotonic()+8
    while not (reply.endswith(io.MON) or reply.endswith(io.REC)):
        assert time.monotonic() < end, 'Need a known idle B3> or REC> prompt'
        reply.extend(link.read(4096))
    return bytes(data)+reply, 'REC' if reply.endswith(io.REC) else 'MON'


def run(board, run):
    profiles, symbols, artifacts = admit()
    profile = profiles['boards'][board]
    run = Path(run).resolve()
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists()
    run.mkdir(parents=True)
    (run/'.gitignore').write_text('*\n')
    markerpath = ROOT/f'output/qualification/device-operations/{board}.json'
    state = dict(passed=False, hardware=True, board=board, phase='before-port',
                 RAM_pending=False, flash_writes=0, setting_writes=0,
                 SRAM_accesses=0, RTC_accesses=0, started_utc=io.now())
    io.save(run/'authorization.json', dict(user_text='merge the 2 aspects into a signle unified codebase on 2609 and 2512',
        action='Verify existing installed components; run same CONFIG/MAINT read-only; restore owner RAM',
        board=board, USB=USB[board], new_flash_writes=False, saved_setting_writes=False))
    marker = io.read(markerpath)
    assert marker['board'] == board and marker['MON_A_present'] and marker['MON_B_present']
    assert marker['monitor_generation'] == 0x8000000f
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('physical_reset_pending', 'owner_application_running',
        'application_RAM_restore_pending', 'one_shot_collection_active', 'power_off_reported'))
    io.durable(run/'marker-before.json', markerpath.read_bytes())

    def checkpoint(phase):
        state.update(phase=phase, updated_utc=io.now())
        io.save(run/'report.json', state)
        current = io.read(markerpath)
        current.update(unified_verification_worker_active=state.get('port_open', False),
                       unified_verification_run=str(run),
                       application_RAM_restore_pending=state['RAM_pending'])
        if state['RAM_pending']:
            current['block_snapshot'] = True
        elif state['passed']:
            current['block_snapshot'] = marker.get('block_snapshot', False)
        io.save(markerpath, current)

    from serial.tools.list_ports import comports
    with io.serial_lease('unified-'+board, timeout=30):
        assert io.read(markerpath) == marker
        ports = [p for p in comports() if p.serial_number == USB[board]]
        assert len(ports) == 1, 'Unique board USB identity required'
        with (run/'serial.jsonl').open('x') as log:
            link = io.Link(ports[0].device, log)
            state['port_open'] = True
            console = (run/'console-log.txt').open('x', encoding='ascii', newline='')
            def record(name, data):
                io.durable(run/log_name(name), data)
                console.write(data.decode('ascii'))
                console.flush()
                return data
            def command(text, prompt=io.MON, name=None):
                return record(name or text.replace(' ', '-')+'.txt', link.command(text, prompt))
            def load(name, prompt):
                body = (BUILD/'payload'/name).read_bytes()
                assert io.sha(body) == artifacts[name]['sha256']
                command('C1', io.REC, 'C1-before-'+name+'.txt')
                assert command('L', b'SEND BIN\r\n', name+'-L.txt') == b'L\r\nSEND BIN\r\n'
                for n in range(0, len(body), 64):
                    link.send(body[n:n+64])
                    time.sleep(.01)
                return record(name+'-startup.txt', link.until(prompt, 30))
            def recovery(text='J3', name='return-REC.txt'):
                command(text, io.CHOICES, name+'-choices')
                link.send(b'S')
                return record(name, link.until(io.REC, 15))
            def select_monitor(slot='B', name='MON.txt'):
                return command(slot, io.MON, name)
            def read_flash(label):
                result = None
                for repeat in (1, 2):
                    banks = []
                    for n in range(4):
                        raw = io.service_read(link, b'F'+bytes((n,)), 32768)
                        io.durable(run/f'{label}-r{repeat}-b{n}.bin', raw)
                        banks.append(raw)
                    if result is None:
                        result = banks
                    else:
                        assert result == banks, 'Independent full reads differ'
                    print('PASS', board, label, 'full flash read', repeat, flush=True)
                return result
            try:
                initial, context = sync(link)
                record('initial.txt', initial)
                state['initial_context'] = context
                if context == 'REC':
                    select_monitor('A', 'initial-MON-A.txt')
                page = link.dump(0x7d30, 0x7d30)[0]
                assert page in (0xa0, 0xb0)
                flavor = profile['monitor_flavor']
                mon = (BUILD/f'payload/STR8N-F-MON-{flavor}-{page >> 4:X}.bin').read_bytes()
                assert io.dump(link, 0xf000, 0xffff) == (BUILD/'payload/STR8N-F-BOOT-4096.bin').read_bytes()
                assert io.dump(link, page*256, page*256+4095) == mon
                for label, address, length in (('BOOT_WORKER_IMAGE', 0x7800, 1000),
                                               ('BOOT_VECTOR_IMAGE', 0x7e20, 196)):
                    offset = symbols['boot'][label]-0xf000
                    assert io.dump(link, address, address+length-1) == (BUILD/'payload/STR8N-F-BOOT-4096.bin').read_bytes()[offset:offset+length]
                state['initial_monitor'] = chr(page//16+55)
                original = [link.dump(0x2000, 0x200c) for _ in range(2)]
                assert original[0] == original[1]
                io.durable(run/'shim-original.bin', original[0])
                state['RAM_pending'] = True
                checkpoint('before-FT-only-shim')
                prompt = symbols[f'monitor-{flavor.lower()}-{page:02x}']['V2_PROMPT']
                shim = bytes.fromhex('78D8A9018D027D20797E4C')+prompt.to_bytes(2, 'little')
                io.upload(link, 0x2000, shim)
                command('G 2000', io.MON, 'FT-only.txt')
                ram = [io.dump(link, 0x200, 0x64ff) for _ in range(2)]
                zp = [link.dump(0, 0xdf) for _ in range(2)]
                assert ram[0] == ram[1] and zp[0] == zp[1]
                owner = bytearray(ram[0])
                owner[0x1e00:0x1e0d] = original[0]
                owner = bytes(owner)
                io.durable(run/'owner-RAM.bin', owner)
                io.durable(run/'owner-ZP.bin', zp[0])
                io.upload(link, 0x2000, original[0])
                assert io.dump(link, 0x200, 0x64ff) == owner
                print('PASS', board, 'fresh owner RAM/ZP escrow; exact F/MON/RAM services admitted', flush=True)
                recovery(name='before-reader-REC.txt')
                assert load('STR8N-F-READBACK-RAM.bin', io.SVC) == io.SVC
                before = read_flash('before')
                row = verify_components(before, profile)
                io.durable(run/'saved-record.bin', row)
                assert io.service_read(link, b'Z', 0xe0) == zp[0]
                link.send(b'Q')
                record('reader-Q.txt', link.until(io.REC))
                state.update(installed_components_match=True, before_sha256=list(map(io.sha, before)))
                state.update(journal_sequence=int.from_bytes(row[8:12], 'little'),
                             saved_default=chr(row[7]), enabled_mask=f'{row[13]:02X}')
                checkpoint('profile-and-source-verified')
                print('PASS', board, 'installed layout matches unified components; default', chr(row[7]), flush=True)

                startup = load('STR8N-F-CONFIG-RAM.bin', io.CFG)
                assert b'STR8 RAM CONFIG / b15 F' in startup
                for text in APP_COMMANDS['CONFIG']:
                    reply = command(text, io.CFG, 'CONFIG-'+text+'.txt')
                    if text in ('B', 'C'):
                        assert reply == text.encode()+b'\r\n'+settings_text(row)+io.CFG
                    if text == 'W':
                        for n in range(32):
                            count = int.from_bytes(row[64+3*n:67+3*n], 'little')
                            assert f'B{n//8}:{n%8+8:X} {count:06X}\r\n'.encode() in reply
                recovery('Q', 'CONFIG-return-REC.txt')
                select_monitor('B', 'CONFIG-check-MON.txt')
                config = bytearray((BUILD/'payload/STR8N-F-CONFIG-RAM.bin').read_bytes())
                config[symbols['config']['CONFIG_ROW']-0x200] = 4
                observed = io.dump(link, 0x200, 0x200+len(config)-1)
                io.durable(run/'CONFIG-executed-RAM.bin', observed)
                assert observed == config
                recovery(name='after-CONFIG-REC.txt')
                print('PASS', board, 'common CONFIG inspection and independent executed-RAM check', flush=True)
                checkpoint('common-CONFIG-verified')

                assert b'READ ONLY' in load('STR8N-F-MAINT-RO-RAM.bin', MAINT)
                for index, text in enumerate(APP_COMMANDS['MAINT']):
                    reply = command(text, MAINT, f'MAINT-{index}.txt')
                    if text == 'M 1':
                        assert b'BANK 8 9 A B C D E F' in reply
                    elif text == 'R 3 F000 F00F':
                        assert b'BUFFER LOADED' in reply
                    elif text == 'K':
                        assert f'CRC16={io.crc(before[3][-4096:-4080]):04X}'.encode() in reply
                    elif text.startswith('V '):
                        assert b'MATCH' in reply
                recovery('Q', 'MAINT-return-REC.txt')
                select_monitor('B', 'MAINT-check-MON.txt')
                immutable = symbols['maint']['MA_IMM_END']-0x200
                observed = io.dump(link, 0x200, 0x200+immutable-1)
                io.durable(run/'MAINT-executed-immutable-RAM.bin', observed)
                assert observed == (BUILD/'payload/STR8N-F-MAINT-RO-RAM.bin').read_bytes()[:immutable]
                recovery(name='after-MAINT-REC.txt')
                print('PASS', board, 'common MAINT map/read/CRC/compare and independent code check', flush=True)
                checkpoint('common-MAINT-verified')

                assert load('STR8N-F-READBACK-RAM.bin', io.SVC) == io.SVC
                after = read_flash('after')
                assert before == after
                assert verify_components(after, profile) == row
                packet = owner+io.crc(owner).to_bytes(2, 'little')
                link.send(b'W')
                for n in range(0, len(packet), 64):
                    link.send(packet[n:n+64])
                    time.sleep(.01)
                assert link.until(io.SVC, 30) == io.SVC
                for repeat in (1, 2):
                    observed = io.service_read(link, b'M', 0x6300)
                    low = io.service_read(link, b'Z', 0xe0)
                    io.durable(run/f'restored-RAM-r{repeat}.bin', observed)
                    io.durable(run/f'restored-ZP-r{repeat}.bin', low)
                    assert observed == owner and low == zp[0]
                link.send(b'Q')
                record('restore-Q-REC.txt', link.until(io.REC))
                select_monitor(state['initial_monitor'], 'final-MON.txt')
                observed = io.dump(link, 0x200, 0x64ff)
                low = link.dump(0, 0xdf)
                io.durable(run/'final-MON-RAM.bin', observed)
                io.durable(run/'final-MON-ZP.bin', low)
                assert observed == owner and low == zp[0]
                if context == 'REC':
                    recovery(name='final-REC.txt')
                state.update(passed=True, RAM_pending=False, flash_unchanged=True,
                    boot_policy_and_wear_unchanged=True, owner_RAM_restored=True,
                    owner_ZP_preserved=True, final_context=context,
                    CONFIG_shared_BIN_sha256=artifacts['STR8N-F-CONFIG-RAM.bin']['sha256'],
                    MAINT_shared_BIN_sha256=artifacts['STR8N-F-MAINT-RO-RAM.bin']['sha256'],
                    system_manifest_sha256=io.sha((BUILD/'system-manifest.json').read_bytes()),
                    helper_sha256=io.sha(Path(__file__).read_bytes()))
                checkpoint('completed')
                print('PASS', board, 'unified source and shared RAM tools verified; flash/settings/wear/RAM preserved', flush=True)
            except BaseException:
                state['failure'] = traceback.format_exc()
                checkpoint('stopped-preserve-escrow')
                raise
            finally:
                link.serial.close()
                console.close()
                state.update(port_open=False, port_released=True, finished_utc=io.now())
                checkpoint('completed' if state['passed'] else 'stopped-preserve-escrow')
    current = io.read(markerpath)
    current.update(unified_codebase_verified=True, last_unified_verification=str(run/'report.json'),
                   unified_source=str(PROJECT), application_RAM_restore_verified=True,
                   current_physical_bank_sha256=dict(zip(('B0','B1','B2','B3'), state['before_sha256'])))
    io.save(markerpath, current)


def restore_interrupted(board, run):
    """Close out the retained CONFIG logging failure before a clean retry."""
    admit()
    run = Path(run).resolve()
    state = io.read(run/'report.json')
    original_marker = io.read(run/'marker-before.json')
    assert board == '2512' and state['board'] == board and not state['passed']
    assert state['RAM_pending'] and 'CONFIG-?.txt.pending' in state['failure']
    owner = (run/'owner-RAM.bin').read_bytes()
    zp = (run/'owner-ZP.bin').read_bytes()
    assert len(owner) == 0x6300 and len(zp) == 0xe0
    source = [(run/f'before-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert source == [(run/f'before-r2-b{n}.bin').read_bytes() for n in range(4)]
    markerpath = ROOT/f'output/qualification/device-operations/{board}.json'
    marker = io.read(markerpath)
    assert marker['application_RAM_restore_pending'] and marker['unified_verification_run'] == str(run)
    io.durable(run/'failed-report-before-restoration.json', (run/'report.json').read_bytes())
    from serial.tools.list_ports import comports
    with io.serial_lease('unified-'+board+'-RAM-restoration', timeout=30):
        ports = [p for p in comports() if p.serial_number == USB[board]]
        assert len(ports) == 1
        with (run/'serial-restoration.jsonl').open('x') as log:
            link = io.Link(ports[0].device, log)
            try:
                link.send(b'\r')
                assert link.until(io.CFG).endswith(io.CFG)
                io.restart_S(link, b'Q\r')
                assert link.command('C1', io.REC) == b'C1\r\nREC> '
                io.raw_load(link, (BUILD/'payload/STR8N-F-READBACK-RAM.bin').read_bytes(), io.SVC)
                for n in range(4):
                    raw = io.service_read(link, b'F'+bytes((n,)), 32768)
                    io.durable(run/f'recovery-b{n}.bin', raw)
                    assert raw == source[n]
                packet = owner+io.crc(owner).to_bytes(2, 'little')
                link.send(b'W')
                for offset in range(0, len(packet), 64):
                    link.send(packet[offset:offset+64])
                    time.sleep(.01)
                assert link.until(io.SVC, 30) == io.SVC
                for repeat in (1, 2):
                    raw = io.service_read(link, b'M', 0x6300)
                    low = io.service_read(link, b'Z', 0xe0)
                    io.durable(run/f'recovery-owner-RAM-r{repeat}.bin', raw)
                    io.durable(run/f'recovery-owner-ZP-r{repeat}.bin', low)
                    assert raw == owner and low == zp
                link.send(b'Q')
                link.until(io.REC)
                link.command('B', io.MON)
                assert io.dump(link, 0x200, 0x64ff) == owner and link.dump(0, 0xdf) == zp
            finally:
                link.serial.close()
    state.update(RAM_pending=False, owner_RAM_restored=True, owner_ZP_preserved=True,
                 flash_unchanged=True, port_open=False, port_released=True,
                 recovery_completed=True, phase='logging-failure-restored-before-retry')
    io.save(run/'report.json', state)
    marker.update(application_RAM_restore_pending=False, application_RAM_restore_verified=True,
                  unified_verification_worker_active=False, block_snapshot=original_marker.get('block_snapshot', False))
    io.save(markerpath, marker)
    print('PASS interrupted 2512 check restored original RAM/ZP; every flash byte unchanged; MON B; port closed', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board', choices=tuple(USB))
    p.add_argument('--run', type=Path)
    p.add_argument('--admit-only', action='store_true')
    p.add_argument('--restore-interrupted', action='store_true')
    a = p.parse_args()
    if a.admit_only:
        admit()
        print('PASS unified source/build/profile and read-only command admission; no port opened')
    elif a.restore_interrupted:
        assert a.board and a.run
        restore_interrupted(a.board, a.run)
    else:
        assert a.board and a.run
        run(a.board, a.run)
