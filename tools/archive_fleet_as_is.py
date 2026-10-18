"""Capture all connected STR8-N boards without changing persistent device data.

Temporary read clients occupy application RAM only. Its original contents are
saved twice before staging and restored with a load-only S-record in finally.
Raw archives belong in ignored output, never in Git.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

from serial.tools.list_ports import comports
from beta4_migration import Link, s19
from qualify_v2_spi_install import load_image, write
from qualify_v2_spi_storage import memory_request
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease

ROOT = Path(__file__).resolve().parents[1]
SPI = ROOT / 'BUILD/v2-spi-resident/hardware-client'
RAW = ROOT / 'BUILD/board-state-reader'
APP_FIRST, APP_LAST = 0x0200, 0x64FF


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def qualified(directory, image):
    receipt = json.loads((directory / 'test-results.json').read_text())
    assert receipt['passed'] and sha((directory / image).read_bytes()) == receipt['sha256']
    return receipt


def capture(board, port, out):
    out.mkdir(exist_ok=False)
    report = dict(board=board, usb_serial=SERIALS[board], port=port, started_utc=now(),
                  passed=False, application_ram_restored=False, persistent_data_written=False,
                  reset=False, clock_set=False, trim_changed=False, soak_started=False)
    save_json(out / 'report.json', report)
    link = None
    original = None
    staged = False

    def note(message):
        print(board, message, flush=True)
        report['progress'] = message
        save_json(out / 'report.json', report)

    def dump(first, last):
        blocks = []
        for address in range(first, last + 1, 4096):
            blocks.append(link.dump(address, min(address + 4095, last)))
        return b''.join(blocks)

    def flash(pass_number):
        banks = []
        for bank in range(4):
            prompt = f'\r\nB{bank}> '.encode()
            link.command(f'B{bank}', prompt)
            image = b''.join(link.dump(a, a + 4095, prompt) for a in range(0x8000, 0x10000, 4096))
            (out / f'flash-{pass_number}-b{bank}.bin').write_bytes(image)
            banks.append(image)
            note(f'flash pass {pass_number}, bank {bank} saved')
        link.command('B3')
        image = b''.join(banks)
        (out / f'flash-{pass_number}-full.bin').write_bytes(image)
        return image

    def retained(pass_number):
        load_image(link, RAW / 'reader.s19')
        data = {}
        requests = [('eeprom', 0xAE, 0, 128), ('eeprom-protected', 0xAE, 0xF0, 8),
                    ('eeprom-status', 0xAE, 0xFF, 1), ('rtc-registers', 0xDE, 0, 32),
                    ('rtc-sram', 0xDE, 0x20, 64)]
        diagnostics = []
        for name, device, offset, count in requests:
            began = now()
            write(link, 0x2F00, bytes((device, offset, count)))
            reply = link.command('G 2000')
            status = link.dump(0x2F10, 0x2F15)
            assert status[0] == 0 and status[5] == count, (name, status.hex(), reply)
            assert status[1] == status[2], ('VIA DDRA changed', status.hex())
            assert status[3] & 0x7E == status[4] & 0x7E, ('VIA other pins changed', status.hex())
            data[name] = link.dump(0x3000, 0x3000 + count - 1)
            (out / f'{name}-{pass_number}.bin').write_bytes(data[name])
            diagnostics.append(dict(name=name, started_utc=began, finished_utc=now(),
                                    status_hex=status.hex(), device_address_7bit=device >> 1,
                                    offset=offset, count=count))
        save_json(out / f'retained-{pass_number}.json', diagnostics)
        note(f'EEPROM, RTC registers and RTC SRAM pass {pass_number} saved')
        return data

    def restore_ram():
        nonlocal staged
        restore = out / 'restore-application-ram.s19'
        # Deliberately load only: G would execute arbitrary original RAM.
        link.command('L', b'S19')
        for row in restore.read_bytes().splitlines():
            link.send(row + b'\r\n')
            time.sleep(.04)
        reply = link.until(b'\r\nB3> ')
        assert not any(error in reply for error in (b'Bad', b'Protected', b'Wrap', b'Error')), reply
        restored = dump(APP_FIRST, APP_LAST)
        (out / 'application-ram-restored.bin').write_bytes(restored)
        assert restored == original, 'Original application RAM restoration mismatch'
        report['application_ram_restored'] = True
        staged = False
        save_json(out / 'restore-needed.json', dict(needed=False, verified_utc=now(), sha256=sha(restored)))
        note('original application RAM restored and verified')

    with (out / 'serial.jsonl').open('x', encoding='utf-8') as log:
        try:
            assert next(p for p in comports() if p.device == port).serial_number == SERIALS[board]
            link = Link(port, log)
            report['synchronization'] = establish_b3(link)
            descriptor = link.dump(0x7D04, 0x7D0B)
            (out / 'resident-descriptor.bin').write_bytes(descriptor)
            assert descriptor == b'SV\x01\x0f\x00\x65\xff\x64', 'EDU ON application boundary required'
            # No I/O reads at 7Fxx. Monitor-owned/ZP/stack bytes change during
            # commands, so this diagnostic snapshot is explicitly non-atomic.
            (out / 'cpu-0000-7eff-diagnostic.bin').write_bytes(dump(0, 0x7EFF))
            original = dump(APP_FIRST, APP_LAST)
            (out / 'application-ram-original.bin').write_bytes(original)
            repeated = dump(APP_FIRST, APP_LAST)
            (out / 'application-ram-repeat.bin').write_bytes(repeated)
            assert original == repeated, 'Application RAM not stable; no client staged'
            (out / 'restore-application-ram.s19').write_bytes(s19(dict(enumerate(original, APP_FIRST)), APP_FIRST))
            note('original application RAM saved twice; restore image ready')
            initial_flash = flash(1)
            save_json(out / 'restore-needed.json', dict(needed=True, created_utc=now(),
                      first=APP_FIRST, last=APP_LAST, original_sha256=sha(original),
                      instructions='Load restore-application-ram.s19 at B3 prompt using L; DO NOT execute G. Verify all 0200-64FF bytes.'))
            staged = True
            for command in ('VERSION', 'T', 'APPS'):
                (out / f'inventory-{command.lower()}.txt').write_bytes(link.command(command))
            first_retained = retained(1)
            load_image(link, SPI / 'client.s19')
            arrays = []
            for copy in (1, 2):
                array = bytearray()
                with (out / f'spi-sram-{copy}.bin').open('xb') as raw:
                    for block in range(16):
                        write(link, 0x3E20, b'\x01\x03\x00')
                        write(link, 0x3E00, memory_request(1, block * 8192))
                        link.command('G 2003')
                        result = link.dump(0x3E10, 0x3E38)
                        assert result[8:10] == b'\x00\x40' and result[0x23] == result[0x24], result.hex()
                        image = link.dump(0x4000, 0x5FFF)
                        raw.write(image)
                        raw.flush()
                        array.extend(image)
                        note(f'SPI SRAM pass {copy}, block {block + 1}/16 saved')
                arrays.append(bytes(array))
            assert arrays[0] == arrays[1], 'SPI SRAM repeat mismatch'
            second_retained = retained(2)
            for name in ('eeprom', 'eeprom-protected', 'eeprom-status', 'rtc-sram'):
                assert first_retained[name] == second_retained[name], name + ' changed'
            # Exclude live time fields only. Configuration, trim, alarms and
            # recorded power-fail timestamps must remain byte-identical.
            assert first_retained['rtc-registers'][7:] == second_retained['rtc-registers'][7:], 'RTC settings/history changed'
            report['rtc_weekday_status_before'] = first_retained['rtc-registers'][3]
            report['rtc_weekday_status_after'] = second_retained['rtc-registers'][3]
            assert first_retained['rtc-registers'][3] & 0x38 == second_retained['rtc-registers'][3] & 0x38, 'RTC backup/PF status changed'
            assert flash(2) == initial_flash, 'Flash changed during capture'
            report.update(capture_complete=True, flash_repeat_verified=True, spi_sram_repeat_verified=True,
                          eeprom_repeat_verified=True, rtc_sram_repeat_verified=True,
                          rtc_configuration_history_preserved=True)
        except Exception as error:
            report['error'] = repr(error)
            report['traceback'] = traceback.format_exc()
            note('CAPTURE ERROR: ' + repr(error))
        finally:
            if staged and original is not None and link is not None:
                try:
                    restore_ram()
                except Exception as error:
                    report['restoration_error'] = repr(error)
                    report['restoration_traceback'] = traceback.format_exc()
                    note('RESTORATION NEEDS ATTENTION: ' + repr(error))
            if link is not None:
                link.serial.close()
            report.update(finished_utc=now(), passed=bool(report.get('capture_complete') and report['application_ram_restored']))
            report['files'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
                               for p in sorted(out.iterdir()) if p.is_file() and p.name not in ('report.json', 'report.json.new', 'serial.jsonl')}
            report['limitations'] = [
                'Live capture: RTC time advances; CPU registers/execution position and monitor scratch RAM are not a resumable CPU checkpoint.',
                '7Fxx peripheral registers are not bulk-read because reads can have side effects.',
                'ATECC private keys are non-exportable; no crypto key/provisioning commands issued.',
                'RAM-only clients read retained data; SPI mode may temporarily change and is restored by the qualified driver.'
            ]
            save_json(out / 'report.json', report)
    print(board, 'PASS' if report['passed'] else 'INCOMPLETE', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to(ROOT / 'output'), 'Raw backups must stay in ignored output'
    qualified(SPI, 'client.bin')
    qualified(RAW, 'reader.bin')
    out.mkdir(parents=True, exist_ok=False)
    (out / '.gitignore').write_text('*\n')
    ports = {p.serial_number: p.device for p in comports()}
    save_json(out / 'usb-inventory.json', ports)
    summary = dict(started_utc=now(), requested_boards=list(SERIALS), passed=False, boards={})
    save_json(out / 'manifest.json', summary)
    with serial_lease('fleet-as-is-backup', priority=True):
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {}
            for board, serial in SERIALS.items():
                if serial in ports:
                    jobs[pool.submit(capture, board, ports[serial], out / board)] = board
                else:
                    summary['boards'][board] = dict(passed=False, error='USB identity not connected', usb_serial=serial)
            for job in as_completed(jobs):
                board = jobs[job]
                try:
                    result = job.result()
                    summary['boards'][board] = dict(passed=result['passed'], report=f'{board}/report.json',
                                                   application_ram_restored=result['application_ram_restored'], error=result.get('error'))
                except Exception as error:
                    summary['boards'][board] = dict(passed=False, error=repr(error))
                save_json(out / 'manifest.json', summary)
    summary.update(finished_utc=now(), passed=all(b['passed'] for b in summary['boards'].values()) and len(summary['boards']) == 4)
    save_json(out / 'manifest.json', summary)
    hashes = {str(p.relative_to(out)).replace('\\', '/'): sha(p.read_bytes())
              for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'sha256.json'}
    save_json(out / 'sha256.json', hashes)
    print(json.dumps(summary, indent=2), flush=True)
    raise SystemExit(0 if summary['passed'] else 1)


if __name__ == '__main__':
    main()
