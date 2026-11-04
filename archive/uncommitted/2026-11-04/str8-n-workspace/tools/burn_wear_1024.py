"""Bounded 2604 B0:E wear burn; native F accounts/verifies every erase.

Each leased burst ends with the original erased sector and B3 prompt, so RTC
collectors can borrow the board. STOP ends after safe sector restoration.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tmp/migration-python')]
from installer.engine.legacy_transport import Link
from installer.common import save
from serial_test_coordination import serial_lease, drift_pending
from serial.tools.list_ports import comports

MARK = ROOT / 'output/qualification/device-operations/2604.json'
MON = b'\r\nB3> '
B0 = b'\r\nB0> '
TARGET = 1024
INDEX = 6  # B0:E, outside 2604's B0:8-D source arena and bank vectors.
sha = lambda b: hashlib.sha256(b).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def admitted():
    marker = json.loads(MARK.read_text())
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('block_snapshot', 'application_RAM_restore_pending',
        'physical_reset_pending', 'owner_application_running', 'power_off_reported'))
    assert marker['monitor_generation'] == 52
    return marker


def port():
    ports = [p for p in comports() if p.serial_number == 'A10MQGVHA']
    assert len(ports) == 1
    return ports[0].device


def connect(log):
    link = Link(port(), log)
    try:
        link.send(b'\r')
        link.until(MON, seconds=8)
        return link
    except BaseException:
        link.serial.close()
        raise


def counts(link):
    raw = link.command('W')
    rows = re.findall(rb'B([0-3]):([89A-F]) ([0-9A-F]{6})', raw)
    assert len(rows) == 32, raw
    result = [None] * 32
    for bank, sector, value in rows:
        result[int(bank) * 8 + int(sector, 16) - 8] = int(value, 16)
    assert None not in result
    return result


def journal(data):
    valid = []
    for off in range(0x4000, 0x6000, 128):
        row = data[off:off + 128]
        if (row[:4] == b'WC\x01\x00' and row[127] == 0 and
                binascii.crc_hqx(row[:120], 65535) == int.from_bytes(row[120:122], 'little')):
            valid.append((int.from_bytes(row[4:8], 'little'), row))
    assert valid, 'No valid committed wear journal'
    return max(valid, key=lambda r: r[0])


def capture(link, folder, prefix):
    banks = []
    try:
        for bank in range(4):
            prompt = f'\r\nB{bank}> '.encode()
            link.command(f'B{bank}', prompt)
            data = link.dump(0x8000, 0xffff, prompt)
            (folder / f'{prefix}-B{bank}.bin').write_bytes(data)
            banks.append(data)
    finally:
        link.command('B3', MON)
    return banks


def preflight(folder):
    assert folder.is_relative_to(ROOT / 'output/qualification')
    if folder.exists():
        prior = json.loads((folder / 'status.json').read_text())
        assert prior['phase'] == 'preflight' and not (folder / 'marker-before.json').exists()
    else:
        folder.mkdir(parents=True, exist_ok=False)
        (folder / '.gitignore').write_text('*\n')
    state = dict(board='2604', usb_serial='A10MQGVHA', sector='B0:E000-EFFF',
        target_decimal=TARGET, target_hex='000400', phase='preflight', passed=False,
        authorization='perhaps on any board that has a low wear counted sector we begin a burn fast as we can, to see how long it takes to get to 1024 (deciminal). yield for time collection',
        started_utc=utc(), runner_sha256=sha(Path(__file__).read_bytes()),
        RTC_collection_has_priority=True, resets=False, RTC_writes=False)
    save(folder / 'status.json', state)
    with serial_lease('wear-burn-preflight-2604', timeout=600):
        save(folder / 'marker-before.json', admitted())
        with (folder / 'preflight-serial.jsonl').open('x') as log:
            link = connect(log)
            try:
                grid = link.command('M1')
                (folder / 'map-before.txt').write_bytes(grid)
                assert b'B0 .  .  .  .  .  .  .  . ' in grid
                assert b'Reserved: B0:8-D;' in grid
                before_counts = counts(link)
                assert before_counts[INDEX] < TARGET
                banks = capture(link, folder, 'before')
                assert banks[0][0x6000:0x7000] == b'\xff' * 4096
                seq, row = journal(banks[3])
                assert [int.from_bytes(row[24 + n * 3:27 + n * 3], 'little') for n in range(32)] == before_counts
                owner = link.dump(0x200, 0x64ff)
                assert owner == link.dump(0x200, 0x64ff), 'Unstable owner RAM'
                (folder / 'owner-RAM.bin').write_bytes(owner)
                low = link.dump(0, 0xdf)
                (folder / 'owner-ZP.bin').write_bytes(low)
                state.update(phase='ready', initial_count=before_counts[INDEX],
                    current_count=before_counts[INDEX], initial_counts=before_counts,
                    initial_sequence=seq, initial_config_hex=row[8:24].hex(),
                    flash_before_sha256=[sha(b) for b in banks], owner_RAM_sha256=sha(owner),
                    serial_released=True, preflight_finished_utc=utc())
            finally:
                link.serial.close()
    save(folder / 'status.json', state)
    print(json.dumps(state), flush=True)


def run(folder, max_bursts=0):
    state = json.loads((folder / 'status.json').read_text())
    assert state['phase'] == 'ready' and state['runner_sha256'] == sha(Path(__file__).read_bytes())
    expected = state['current_count']
    total_start = state.get('burn_start_perf_counter', time.perf_counter())
    active_seconds = state.get('active_burst_seconds', 0.0)
    owner = (folder / 'owner-RAM.bin').read_bytes()
    low = (folder / 'owner-ZP.bin').read_bytes()
    state.update(phase='starting', pid=os.getpid(),
        burn_start_perf_counter=total_start, burn_started_utc=state.get('burn_started_utc', utc()),
        verified_bursts=state.get('verified_bursts', 0),
        erase_attempts_added=expected-state['initial_count'], serial_released=True)
    save(folder / 'status.json', state)
    def checkpoint(phase, **kw):
        state.update(phase=phase, updated_utc=utc(), wall_seconds=time.perf_counter()-total_start,
            active_burst_seconds=active_seconds, **kw)
        save(folder / 'status.json', state)
    try:
        while expected < TARGET and not (folder / 'STOP').exists():
            if max_bursts and state['verified_bursts'] >= max_bursts:
                checkpoint('ready', serial_released=True)
                return
            if drift_pending():
                checkpoint('yielding-to-RTC', serial_released=True)
                time.sleep(.2)
                continue
            try:
                with serial_lease('wear-burn-2604', timeout=2):
                    admitted()
                    burst_start = time.perf_counter()
                    dirty = False
                    with (folder / 'burn-serial.jsonl').open('a') as log:
                        link = connect(log)
                        try:
                            observed = counts(link)
                            assert observed[INDEX] == expected, 'Scratch count changed outside burn'
                            link.command('B0', B0)
                            assert link.dump(0xe000, 0xe00f, B0) == b'\xff' * 16
                            operations = 0
                            while True:
                                finish = dirty and (expected >= TARGET-1 or operations >= 16 or
                                    time.perf_counter()-burst_start >= 6 or drift_pending() or (folder / 'STOP').exists())
                                value = 255 if finish else (0x55 if operations % 2 else 0xaa)
                                will_erase = dirty
                                before = expected
                                link.send(f'F E000 {value:02X}\r'.encode())
                                preview = link.until(b' Y?', seconds=8)
                                assert f'E000 '.encode() in preview and f'>{value:02X}'.encode() in preview
                                assert (b'Erase+write' in preview) == will_erase, preview
                                assert not will_erase or expected < TARGET
                                checkpoint('burning', current_count=expected, serial_released=False,
                                    pending_erase=will_erase, pending_byte=f'{value:02X}')
                                link.send(b'Y\r')
                                result = link.until(B0, seconds=15)
                                assert b'Done' in result and not any(x in result for x in (b'Failed', b'timeout', b'Verify', b'Protected'))
                                completed_at = time.perf_counter()
                                if will_erase:
                                    expected += 1
                                if expected == TARGET:
                                    state.update(target_reached_wall_seconds=completed_at-total_start,
                                        target_reached_utc=utc())
                                dirty = value != 255
                                operations += 1
                                with (folder / 'timings.jsonl').open('a') as timing:
                                    timing.write(json.dumps(dict(UTC=utc(), count=expected,
                                        count_before=before, counted_erase=will_erase,
                                        wall_seconds=completed_at-total_start, value=value))+'\n')
                                if not dirty:
                                    assert link.dump(0xe000, 0xefff, B0) == b'\xff' * 4096
                                    break
                            link.command('B3', MON)
                            observed = counts(link)
                            assert observed[INDEX] == expected
                            for i, (a, b) in enumerate(zip(state['initial_counts'], observed)):
                                if i not in (INDEX, 28, 29):
                                    assert a == b, ('Unplanned sector erase', i, a, b)
                            if state['verified_bursts'] == 0:
                                assert link.dump(0x200, 0x64ff) == owner
                                assert link.dump(0, 0xdf) == low
                            state['verified_bursts'] += 1
                            active_seconds += time.perf_counter()-burst_start
                            checkpoint('between-bursts', current_count=expected,
                                erase_attempts_added=expected-state['initial_count'],
                                scratch_restored=True, pending_erase=False)
                            print('PASS', expected, '/', TARGET, 'burst', state['verified_bursts'], flush=True)
                        finally:
                            # On ambiguous failure stop; never issue an uncounted retry.
                            if not dirty:
                                try:
                                    link.command('B3', MON)
                                except Exception:
                                    pass
                            link.serial.close()
                            state['serial_released'] = not link.serial.is_open
            except TimeoutError as exc:
                if str(exc) not in ('Serial lease unavailable; no board port opened',
                    'Drift request has priority; retry soak later'):
                    raise
                checkpoint('yielding-to-RTC', serial_released=True)
                continue
            checkpoint('between-bursts', serial_released=True)
        checkpoint('final-verification', serial_released=True)
        with serial_lease('wear-burn-final-2604', timeout=45):
            with (folder / 'final-serial.jsonl').open('x') as log:
                link = connect(log)
                try:
                    banks = capture(link, folder, 'after')
                    before = [(folder / f'before-B{b}.bin').read_bytes() for b in range(4)]
                    assert banks[:3] == before[:3]
                    assert banks[3][:0x4000] == before[3][:0x4000]
                    assert banks[3][0x6000:] == before[3][0x6000:]
                    seq, row = journal(banks[3])
                    assert row[8:24].hex() == state['initial_config_hex']
                    final_counts = counts(link)
                    assert final_counts[INDEX] == expected <= TARGET
                    assert link.dump(0x200, 0x64ff) == owner
                    assert link.dump(0, 0xdf) == low
                    checkpoint('complete' if expected == TARGET else 'stopped',
                        passed=expected == TARGET, current_count=expected, final_counts=final_counts,
                        final_sequence=seq, flash_after_sha256=[sha(b) for b in banks],
                        firmware_preserved=True, boot_config_preserved=True, owner_RAM_preserved=True,
                        owner_ZP_preserved=True, scratch_restored=True,
                        journal_erase_increments={f'B3:{s:X}': final_counts[24+s-8]-state['initial_counts'][24+s-8] for s in (12,13)},
                        finished_utc=utc())
                finally:
                    link.serial.close()
        checkpoint(state['phase'], serial_released=True)
    except BaseException:
        checkpoint('failed-inspect-evidence', passed=False, failure=traceback.format_exc())
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--preflight', action='store_true')
    p.add_argument('--max-bursts', type=int, default=0)
    a = p.parse_args()
    folder = a.folder.resolve()
    assert folder.is_relative_to(ROOT / 'output/qualification')
    if a.preflight:
        preflight(folder)
    else:
        run(folder, a.max_bursts)
