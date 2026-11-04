"""Read-only inventory and bank backups of the four connected boards.

No RAM load, execution, flash mutation, SPI operation or RTC operation.
Only monitor dumps and temporary data-bank selections are used. A b15 REC
session can enter its existing MON A and return to REC after the capture.
"""
import argparse
import binascii
import hashlib
import json
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tmp/migration-python')]
from installer.engine.legacy_transport import Link
from installer.common import save
from serial_test_coordination import serial_lease

BOARDS = {'2205': 'A10MPUPNA', '2512': 'A10MQFLCA', '2604': 'A10MQGVHA', '2609': 'A10MPQXCA'}
MON = b'\r\nB3> '
REC = b'REC> '
sha = lambda data: hashlib.sha256(data).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()


def durable(path, data):
    import os
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def describe(banks):
    result = dict(banks=[], monitors=[])
    for number, bank in enumerate(banks):
        result['banks'].append(dict(bank=number, bytes=len(bank), sha256=sha(bank),
            header_hex=bank[:16].hex(), reset_vector=f'{int.from_bytes(bank[-4:-2], "little"):04X}',
            erased_sectors=[f'{n+8:X}' for n in range(8) if bank[n*4096:(n+1)*4096] == b'\xff'*4096]))
    for page in (0xa0, 0xb0):
        body = banks[3][page*256-0x8000:page*256-0x7000]
        valid = (body[:4] == b'MI\x01'+bytes((page,)) and body[31] == 0 and
                 binascii.crc_hqx(body[:18]+body[32:], 65535) == int.from_bytes(body[18:20], 'little'))
        result['monitors'].append(dict(slot=chr(page//16+55), valid=valid,
            generation=f'{int.from_bytes(body[8:12], "little"):08X}', sha256=sha(body)))
    records = []
    for off in range(0x4000, 0x6000, 256):
        row = banks[3][off:off+256]
        if (row[:6] == b'SNBT\x01\x20' and row[255] == 0 and
            binascii.crc_hqx(row[:30], 65535) == int.from_bytes(row[30:32], 'little') and
            binascii.crc_hqx(row[:252], 65535) == int.from_bytes(row[252:254], 'little')):
            records.append((int.from_bytes(row[8:12], 'little'), off+0x8000, row))
    if records:
        seq, address, row = max(records)
        result['boot_record'] = dict(format='SNBT', sequence=seq, address=f'{address:04X}',
            default=chr(row[7]), enabled_mask=f'{row[13]:02X}', entries=[f'{v:X}000' for v in row[14:18]],
            counts=[int.from_bytes(row[64+3*n:67+3*n], 'little') for n in range(32)])
    result['firmware_strings'] = [match.decode('ascii') for match in re.findall(rb'[\x20-\x7e]{8,100}', banks[3])
                                  if any(word in match for word in (b'STR8-N', b'proto b', b'2.0b', b'2.0rc'))][:16]
    return result


def inventory(board, run):
    from serial.tools.list_ports import comports
    run = Path(run).resolve()
    assert run.is_relative_to(ROOT/'output/qualification') and not run.exists()
    run.mkdir(parents=True)
    (run/'.gitignore').write_text('*\n')
    markerpath = ROOT/f'output/qualification/device-operations/{board}.json'
    marker = json.loads(markerpath.read_text())
    assert not any(value for name, value in marker.items() if name.endswith('_worker_active'))
    assert not any(marker.get(name) for name in ('one_shot_collection_active', 'application_RAM_restore_pending',
                                                 'physical_reset_pending', 'owner_application_running', 'power_off_reported'))
    durable(run/'marker-before.json', markerpath.read_bytes())
    state = dict(board=board, usb_serial=BOARDS[board], passed=False, hardware=True,
        started_utc=now(), flash_writes=False, application_RAM_writes=False,
        SPI_accesses=False, RTC_accesses=False, phase='before-port')
    save(run/'report.json', state)
    with serial_lease('inventory-'+board, timeout=30):
        ports = [port for port in comports() if port.serial_number == BOARDS[board]]
        assert len(ports) == 1
        with (run/'serial.jsonl').open('x') as log:
            link = Link(ports[0].device, log)
            context = None
            try:
                initial = bytearray()
                begin = last = time.monotonic()
                while time.monotonic()-last < .5:
                    assert time.monotonic()-begin < 10, 'Continuous output; no commands sent'
                    part = link.read(4096)
                    if part:
                        initial.extend(part)
                        last = time.monotonic()
                assert all(c in (8, 9, 10, 13, 127) or 32 <= c <= 126 for c in initial)
                link.send(b'\r')
                reply = bytearray()
                end = time.monotonic()+8
                while not (reply.endswith(MON) or reply.endswith(REC)):
                    assert time.monotonic() < end, 'Need known idle B3> or REC>; no reset issued'
                    reply.extend(link.read(4096))
                durable(run/'initial-console.txt', bytes(initial)+reply)
                context = 'REC' if reply.endswith(REC) else 'MON'
                if context == 'REC':
                    assert marker.get('monitor_generation') == 0x8000000f
                    durable(run/'enter-MON-A.txt', link.command('A', MON))
                durable(run/'help.txt', link.command('?', MON))
                def dump(first, last, prompt=MON):
                    return b''.join(link.dump(n, min(n+511, last), prompt) for n in range(first, last+1, 512))
                owner = dump(0x200, 0x66ff)
                zp = link.dump(0, 0xdf)
                durable(run/'owner-RAM-before.bin', owner)
                durable(run/'owner-ZP-before.bin', zp)
                control = dump(0x7d00, 0x7d3f)
                durable(run/'resident-status.bin', control)
                durable(run/'config-and-service-bytes.bin', dump(0x7d80, 0x7dff))
                banks = []
                try:
                    for number in range(4):
                        prompt = f'\r\nB{number}> '.encode()
                        link.command(f'B{number}', prompt)
                        data = dump(0x8000, 0xffff, prompt)
                        durable(run/f'bank{number}.bin', data)
                        banks.append(data)
                        print('PASS', board, 'bank', number, 'backed up', sha(data), flush=True)
                    link.command('B0', b'\r\nB0> ')
                    repeat = dump(0x8000, 0xffff, b'\r\nB0> ')
                    durable(run/'bank0-repeat.bin', repeat)
                    assert repeat == banks[0], 'B0 independent backup reads differ'
                finally:
                    link.command('B3', MON)
                after = dump(0x200, 0x66ff)
                low = link.dump(0, 0xdf)
                durable(run/'owner-RAM-after.bin', after)
                durable(run/'owner-ZP-after.bin', low)
                assert owner == after and zp == low, 'RAM changed during read-only inventory'
                state.update(describe(banks), passed=True, initial_context=context,
                    CPU_code=f'{control[1]:02X}', console_code=f'{control[2]:02X}',
                    active_slot_byte=f'{control[0x30]:02X}', B0_twice_read_equal=True,
                    owner_RAM_unchanged=True, owner_ZP_unchanged=True,
                    application_RAM_sha256=sha(owner), phase='captured')
            except BaseException:
                state['failure'] = traceback.format_exc()
                state['phase'] = 'stopped-inspect-console'
                raise
            finally:
                if context == 'REC' and state.get('passed'):
                    durable(run/'return-J3.txt', link.command('J3', b'S=Recovery  A/B=Monitor  0-3=Bank\r\n'))
                    link.send(b'S')
                    durable(run/'final-REC.txt', link.until(REC, 15))
                link.serial.close()
                state.update(port_released=True, finished_utc=now())
                save(run/'report.json', state)
    files = {path.name:dict(bytes=path.stat().st_size, sha256=sha(path.read_bytes()))
             for path in sorted(run.iterdir()) if path.is_file() and path.suffix in ('.bin', '.txt')}
    save(run/'backup-manifest.json', dict(board=board, passed=True, files=files,
        full_flash_reads=1, independent_B0_reads=2, flash_written=False,
        RAM_uploaded=False, SPI_written=False, RTC_written=False, helper_sha256=sha(Path(__file__).read_bytes())))
    current = json.loads(markerpath.read_text())
    current['last_readonly_inventory'] = str(run/'report.json')
    current['last_readonly_bank_backup'] = str(run/'backup-manifest.json')
    save(markerpath, current)
    print('PASS', board, 'inventory and backups complete; RAM preserved; port released', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', choices=tuple(BOARDS), required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    inventory(args.board, args.run)
