"""Preserving beta32 soak for USB-identified 2512; runs until STOP exists.

Flash, external SRAM and EEPROM are read-only. Only ordinary CPU RAM is
staged; the explicit 0200-02FF pattern test restores its durable backup.
Never use the beta25 R/S/T soak's B2 scratch sectors with native utilities.
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import traceback

from atomic_json import publish
from beta4_migration import Link
from qualify_v2_spi_install import load_image, read_application_s19
from qualify_v2_spi_storage import memory_request
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease, drift_pending

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'output/qualification/beta32-2026-10-16/2512'
BUILD = ROOT / 'BUILD/v2-beta32-candidate'
CLIENT = ROOT / 'BUILD/v2-spi-resident/hardware-client/client.s19'
EEPROM = ROOT / 'BUILD/v2-eeprom-inventory/probe.s19'
BUILD_HASH = 'cf900395e0fde8ab5ea519b30483ab27b2f847b53755361b6f42799d74a3c052'
CLIENT_HASH = 'e892f3175bb315b2be8db4a94317e41569f50a22de3f067eb74170595593c4fc'
EEPROM_HASH = 'afded41e146341f4ab28fb82cf03934d91a3e7dc7fcc466bff03a70506a98621'
PROMPT = b'\r\nB3> '
GROUPS = ([f'flash-{i}' for i in range(4)] +
          [f'sram-{i}' for i in range(16)] +
          ['eeprom', 'clock', 'monitor', 'apps', 'batch', 'ram', 'reset'])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def audit():
    assert sha((BUILD / 'build.json').read_bytes()) == BUILD_HASH
    hardware = read_json(REFERENCE / 'hardware-qualification.json')
    assert hardware['passed'] and hardware['board'] == '2512'
    assert hardware['build_sha256'] == BUILD_HASH and hardware['wear_peak_verified']
    for name, digest in hardware['evidence'].items():
        assert sha((REFERENCE / name).read_bytes()) == digest, name
    plan = read_json(REFERENCE / 'upgrade/plan.json')
    verified = read_json(REFERENCE / 'upgrade/post-reset-report.json')
    assert verified['passed'] and plan['expected_hashes'] == verified['expected_hashes']
    assert plan['build_sha256'] == BUILD_HASH
    for bank, digest in enumerate(plan['expected_hashes']):
        assert sha((REFERENCE / f'upgrade/post-reset-b{bank}.bin').read_bytes()) == digest
    sram = (REFERENCE / 'retained/sram-final/array-0.bin').read_bytes()
    assert len(sram) == 131072
    assert sha(sram) == read_json(REFERENCE / 'retained/sram-final/report.json')['sha256']
    for image, digest in ((CLIENT, CLIENT_HASH), (EEPROM, EEPROM_HASH)):
        cells, _ = read_application_s19(image)
        assert sha(bytes(cells[a] for a in range(min(cells), max(cells) + 1))) == digest
    return plan, sram


def guards(link):
    assert link.dump(0x7D04, 0x7D0B) == b'SV\x01\x0f\0\x65\xff\x64', 'EDU ABI changed'
    assert link.dump(0x7D27, 0x7D28) == b'\x01\0', 'EDU profile changed'
    assert link.dump(0x7D30, 0x7D30) == b'\xb0', 'Active monitor changed'
    assert link.dump(0x66AE, 0x66AE) == b'\x01', 'SRAM write protection changed'


def normalized(data):
    return data.replace(b'\r\n', b'\n').strip()


def rtc_epoch(raw):
    def bcd(value):
        assert value & 15 <= 9 and value >> 4 <= 9, 'Invalid RTC BCD'
        return (value >> 4) * 10 + (value & 15)
    assert not raw[2] & 0x40, 'Unexpected RTC hour mode'
    date = datetime.datetime(2000 + bcd(raw[6]), bcd(raw[5] & 0x1F), bcd(raw[4] & 0x3F),
                             bcd(raw[2] & 0x3F), bcd(raw[1] & 0x7F), bcd(raw[0] & 0x7F),
                             tzinfo=datetime.timezone.utc)
    return date.timestamp()


def clock(link, out):
    link.command('SRAM', b'SRAM> ')
    assert b'CLOCK 1.9' in link.command('G CLK', b'CLOCK> ')
    try:
        status = link.command('STATUS', b'CLOCK> ')
        raw = bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)', status)[1].decode())
        assert raw[7:9] == b'\x80\x0c', 'RTC control/trim changed'
        assert b'Running: yes' in status and b'Backup enabled: yes' in status
        (out / 'status.txt').write_bytes(status)
        for command, name in [('HISTORY', 'history'), ('EUI', 'eui')]:
            reply = link.command(command, b'CLOCK> ')
            (out / (name + '.txt')).write_bytes(reply)
            assert normalized(reply) == normalized((REFERENCE / f'retained/devices-after/{name}.txt').read_bytes()), name + ' changed'
        link.command('BATTERY', b'CLOCK> ')
        return dict(control=raw[7], trim=raw[8], history_identity_preserved=True, rtc_epoch=rtc_epoch(raw))
    finally:
        link.command('Q')


def batch(link, commands):
    assert len(commands) <= 34 and '\r' not in commands and '\n' not in commands
    reply = link.command('BATCH ' + commands, b'BATCH done')
    reply += link.until(PROMPT)
    assert b'BATCH stopped' not in reply and b'BATCH canceled' not in reply, reply
    return reply


def batch_checks(link, out):
    text = batch(link, 'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
    assert all(title in text for title in (b'MAINT 2.4', b'SRAM 1.4', b'WORK 1.4', b'EDU 1.4'))
    text += batch(link, 'SRAM;G CLK;STATUS;Q')
    assert b'CLOCK 1.9' in text and b'Running: yes' in text
    error = link.command('BATCH SRAM;BOGUS;Q', b'BATCH stopped: command failed')
    error += link.until(b'SRAM> ')
    assert not error.endswith(PROMPT), 'Queued Q ran after error'
    link.command('Q')
    escape = link.command('BATCH MAINT;NAME Z30CHECK;Q', b'Type YES: ')
    link.send(b'\x1b')
    escape += link.until(b'BATCH canceled') + link.until(b'BM> ')
    link.command('Q')
    link.command('R MAINT', b'BM> ')
    link.command('NAME Z30CHECK', b'Type YES: ')
    refused = link.command('NO', b'BM> ')
    link.command('Q')
    for name, data in [('done', text), ('error', error), ('escape', escape), ('name-refused', refused)]:
        (out / (name + '.txt')).write_bytes(data)
    return dict(native_aliases=True, saved_clk=True, error_stops=True, esc_cancels=True, name_refused=True)


def restore_patterns(link, out, iteration):
    address = 0x0200
    original = link.dump(address, address + 255)
    assert original == link.dump(address, address + 255), 'RAM backup unstable'
    state = dict(address=address, bytes=256, original_hex=original.hex(), needs_restore=True)
    publish(out / 'restore-state.json', state)
    patterns = [bytes([value]) * 256 for value in (0, 255, 0xAA, 0x55)]
    patterns += [bytes([1 << bit]) * 256 for bit in range(8)]
    patterns += [bytes((i + iteration) & 255 for i in range(256))]
    try:
        for pattern in patterns:
            link.write_ram(address, pattern)
            assert link.dump(address, address + 255) == pattern, 'RAM pattern mismatch'
    finally:
        link.write_ram(address, original)
        assert link.dump(address, address + 255) == original, 'RAM RESTORATION FAILED'
        publish(out / 'restore-state.json', dict(state, needs_restore=False, restored=True))
    return dict(bytes=256, patterns=len(patterns), restored=True, original_sha256=sha(original))


def unit(link, group, out, plan, sram, iteration):
    if group.startswith('flash-'):
        bank = int(group.split('-')[1])
        prompt = f'\r\nB{bank}> '.encode()
        link.command(f'B{bank}', prompt)
        try:
            data = b''.join(link.dump(a, a + 4095, prompt) for a in range(0x8000, 0x10000, 4096))
        finally:
            link.command('B3')
        assert sha(data) == plan['expected_hashes'][bank], f'Flash B{bank} changed'
        return dict(bytes=len(data), sha256=sha(data), unchanged=True)
    if group.startswith('sram-'):
        block = int(group.split('-')[1])
        assert load_image(link, CLIENT) == CLIENT_HASH
        link.write_ram(0x3E20, b'\x01\x03\0')
        link.write_ram(0x3E00, memory_request(1, block * 8192))
        link.command('G 2003')
        reply = link.dump(0x3E10, 0x3E38)
        assert reply[8:10] == b'\0\x40' and reply[0x23] == reply[0x24], 'SRAM read failed/bank not restored'
        data = link.dump(0x4000, 0x5FFF)
        assert data == sram[block * 8192:(block + 1) * 8192], f'SRAM block {block} changed'
        return dict(address=block * 8192, bytes=len(data), sha256=sha(data), unchanged=True, written=False)
    if group == 'eeprom':
        assert load_image(link, EEPROM) == EEPROM_HASH
        images = []
        for _ in range(2):
            link.command('G 2000')
            data = link.dump(0x2400, 0x2494)
            assert data[0x90] == 0 and data[0x91] == data[0x92] and (data[0x93] ^ data[0x94]) & data[0x91] == 0
            images.append(data[:137])
        assert images[0] == images[1] == (REFERENCE / 'retained/devices-after/eeprom-0.bin').read_bytes()[:137], 'EEPROM changed'
        return dict(bytes=137, repeated_read=True, sha256=sha(images[0]), unchanged=True, written=False)
    if group == 'clock':
        return clock(link, out)
    if group == 'monitor':
        for command in ('VERSION', 'TIME', 'APPS', 'T', 'M1', 'W', 'C'):
            reply = link.command(command)
            (out / (command + '.txt')).write_bytes(reply)
            assert b'FLASH: wear check' not in reply, 'Boot message repeated on ordinary return'
            if command == 'VERSION':
                assert b'2.0b32' in reply and b'Board: 2512' in reply
                assert b'MONITOR A gen 00000028 VALID' in reply and b'MONITOR B gen 0000002C VALID default' in reply
            if command == 'TIME':
                assert b'(-05:00)' in reply, 'Offset changed'
            if command == 'APPS':
                assert all(n + b' FLASH B2' in reply for n in (b'MAINT', b'SRAM', b'WORK', b'EDU'))
        return dict(queries=7)
    if group == 'apps':
        for name, prompt in [('MAINT', b'BM> '), ('SRAM', b'SRAM> '), ('WORK', b'WORK> '), ('EDU', b'EDU> ')]:
            reply = link.command(('R ' if iteration % 2 else '') + name, prompt)
            assert name.encode() in reply
            reply += link.command('T' if name == 'SRAM' else '?', prompt)
            reply += link.command('Q')
            (out / (name + '.txt')).write_bytes(reply)
        return dict(utilities=4, launch_mode='R compatibility' if iteration % 2 else 'bare aliases')
    if group == 'batch':
        return batch_checks(link, out)
    if group == 'ram':
        return restore_patterns(link, out, iteration)
    if group == 'reset':
        text = link.command('J3')
        (out / 'boot.txt').write_bytes(text)
        assert b'STR8-N 2.0b32' in text and b'MONITOR B gen 0000002C VALID default' in text
        assert text.count(b'FLASH: wear check ') == 1
        assert ('FLASH: wear check ' + plan['expected_wear_status']).encode() in text
        assert plan['expected_wear_peak'].encode() in text
        return dict(j3=True, peak_count=plan['wear_peak_count'], peak_bank=plan['wear_peak_bank'], peak_sector=plan['wear_peak_sector'])
    raise ValueError(group)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--cycles', type=int, default=0, help='0 = until STOP; positive = bounded smoke run')
    args = parser.parse_args()
    assert args.cycles >= 0
    plan, sram = audit()
    args.root.mkdir(parents=True, exist_ok=False)
    state = dict(board='2512', serial=SERIALS['2512'], pid=os.getpid(), started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 passed_units=0, completed_cycles=0, groups=GROUPS, duration='until STOP' if args.cycles == 0 else args.cycles,
                 build_sha256=BUILD_HASH, flash_hashes=plan['expected_hashes'], sram_sha256=sha(sram),
                 flash_sram_eeprom_writes=False, source_sha256=sha(Path(__file__).read_bytes()))
    publish(args.root / 'config.json', state)

    def status(phase, **extra):
        state.update(state=phase, updated=time.time(), **extra)
        publish(args.root / 'status.json', state)

    assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001), 'Cannot inhibit idle sleep'
    try:
        while not args.cycles or state['completed_cycles'] < args.cycles:
            for group in GROUPS:
                while True:
                    if (args.root / 'STOP').exists():
                        status('stopped-by-request', group=None)
                        return
                    if drift_pending():
                        status('yielding-to-drift', group=group)
                        time.sleep(2)
                        continue
                    try:
                        with serial_lease('beta32-enhanced-soak-2512', timeout=2):
                            from serial.tools.list_ports import comports
                            import serial
                            port = next((p.device for p in comports() if p.serial_number == SERIALS['2512']), None)
                            if port is None:
                                status('waiting-for-board', group=group)
                                time.sleep(2)
                                continue
                            log_path = args.root / f"{state['passed_units']:06d}-{group}.jsonl"
                            with log_path.open('a') as log:
                                try:
                                    link = Link(port, log)
                                except serial.SerialException as error:
                                    status('waiting-for-serial-port', group=group, serial_error=str(error))
                                    time.sleep(2)
                                    continue
                                try:
                                    status('running', group=group, port=port)
                                    out = args.root / f"{state['passed_units']:06d}-{group}"
                                    out.mkdir(exist_ok=False)
                                    establish_b3(link)
                                    guards(link)
                                    result = unit(link, group, out, plan, sram, state['completed_cycles'])
                                    guards(link)
                                    if group == 'clock':
                                        if 'last_rtc_epoch' in state:
                                            assert result['rtc_epoch'] > state['last_rtc_epoch'], 'RTC stopped or moved backward between cycles'
                                        state['last_rtc_epoch'] = result['rtc_epoch']
                                    publish(out / 'report.json', dict(passed=True, result=result, finished=time.time()))
                                finally:
                                    link.serial.close()
                            break
                    except TimeoutError as error:
                        # A lease timeout happens before a port is opened; protocol
                        # timeouts must stop instead of creating a false retry pass.
                        if str(error) not in ('Serial lease unavailable; no board port opened', 'Drift request has priority; retry soak later'):
                            raise
                        status('waiting-for-serial-lease', group=group)
                state['passed_units'] += 1
                status('running')
                print('PASS', state['passed_units'], group, flush=True)
            state['completed_cycles'] += 1
            status('running', group=None)
            # Short idle gaps allow other approved serial jobs and STOP checks.
            for _ in range(15):
                if (args.root / 'STOP').exists():
                    break
                time.sleep(2)
        status('completed', group=None)
    except Exception:
        status('stopped-on-failure', error=traceback.format_exc())
        raise
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
