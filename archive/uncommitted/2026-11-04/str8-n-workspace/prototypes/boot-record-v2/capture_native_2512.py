"""Repeated read-only 2512 native-SNBT escrow. Serial access is CLI-only.

This helper does not write flash/RAM, reset the board, launch an application,
or change the device-operation marker. The shared lease covers every read.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'tools'), str(HERE)]
from installer.common import inventory, safe, save
from installer.engine import runtime as r, legacy_transport as wire
from installer import workflow
import board_2512 as previous
from deployment_plan import snbt_records

BOARD, USB = '2512', 'A10MQFLCA'
RAM_BYTES = 0x6300


def validate(folder, *, allow_synthetic=False):
    folder = Path(folder).resolve()
    identity = r.read(folder / 'capture.json')
    r.require(identity.get('schema') == 2 and identity.get('journal_format') == 'SNBT1/256'
              and identity.get('board') == BOARD and identity.get('usb_serial') == USB
              and identity.get('repeat_verified') is True, 'Native capture identity differs')
    r.require(allow_synthetic or (identity.get('hardware_capture') is True
                                and identity.get('synthetic_model_fixture') is False),
              'A repeated physical native capture is required')
    for name, info in identity['files'].items():
        body = safe(folder, name).read_bytes()
        r.require(len(body) == info['bytes'] and r.sha(body) == info['sha256'], 'Capture member changed: ' + name)
    banks = []
    for n in range(4):
        first, repeat = [(folder / f'b{n}{suffix}.bin').read_bytes() for suffix in ('', '-repeat')]
        r.require(len(first) == 32768 and first == repeat, 'Different repeated native bank')
        banks.append(first)
    ram = (folder / 'application-ram.bin').read_bytes()
    r.require(len(ram) == RAM_BYTES and ram == (folder / 'application-ram-repeat.bin').read_bytes(),
              'Different repeated owner RAM')
    r.require((folder / 'restore-application-ram.s19').read_bytes()
              == wire.s19(dict(enumerate(ram, 0x200)), 0x200), 'RAM restore image differs')
    rows = snbt_records(banks)
    r.require(rows, 'Native journal missing')
    latest = max(rows)[2]
    r.require(latest[32:48][14:] == wire.config_sum(latest[32:48]), 'Native config checksum differs')
    r.require(identity['bank_sha256'] == r.hashes(banks)
              and identity['application_ram_sha256'] == r.sha(ram), 'Capture hash map differs')
    return identity, banks


def write(folder, banks, ram, *, synthetic=False, evidence=None):
    folder = Path(folder)
    r.require(not folder.exists(), 'Use a fresh capture directory')
    folder.mkdir(parents=True)
    (folder / '.gitignore').write_text('*\n')
    r.valid_banks(banks)
    for n, body in enumerate(banks):
        for suffix in ('', '-repeat'):
            (folder / f'b{n}{suffix}.bin').write_bytes(body)
    for name in ('application-ram.bin', 'application-ram-repeat.bin'):
        (folder / name).write_bytes(ram)
    (folder / 'restore-application-ram.s19').write_bytes(wire.s19(dict(enumerate(ram, 0x200)), 0x200))
    identity = dict(schema=2, board=BOARD, usb_serial=USB, journal_format='SNBT1/256',
                    repeat_verified=True, hardware_capture=not synthetic, synthetic_model_fixture=synthetic,
                    bank_sha256=r.hashes(banks), application_ram_sha256=r.sha(ram),
                    captured_utc=previous.now(), source_evidence=evidence, files=inventory(folder))
    save(folder / 'capture.json', identity)
    validate(folder, allow_synthetic=synthetic)
    return identity


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-plan', type=Path, default=ROOT / 'tmp/pr03-bench-agent-plan-candidate')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--authorization', type=Path, required=True)
    p.add_argument('--coordination', type=Path, default=previous.DEFAULT_COORDINATION)
    p.add_argument('--marker', type=Path, default=ROOT / 'output/qualification/device-operations/2512.json')
    args = p.parse_args()
    args.run, args.plan = args.run.resolve(), args.source_plan.resolve()
    args.stage, args.campaign_receipt = 'capture-native', None
    auth = r.read(args.authorization)
    r.require(auth.get('owner_authorized') is True and auth.get('action') == 'capture-native-bench-source'
              and (auth.get('board'), auth.get('usb_serial')) == (BOARD, USB)
              and auth.get('other_boards_authorized') is False
              and auth.get('RTC_campaign_resume_authorized') is False, 'Explicit read-only capture scope required')
    r.require(not args.run.exists(), 'Use a fresh capture run directory')
    args.run.mkdir(parents=True)
    (args.run / '.gitignore').write_text('*\n')
    expected = [(args.plan / f'expected-b{n}.bin').read_bytes() for n in range(4)]
    with previous.live_link(args, pending=False) as (link, marker):
        r.require(marker['firmware'] == '2.0proto b04' and marker['monitor_generation'] == 0x80000004
                  and marker['current_firmware_profile'] == 'experimental-bench-core'
                  and marker['current_physical_bank_sha256'] == dict(zip(('B0', 'B1', 'B2', 'B3'), r.hashes(expected))),
                  'Marker differs from completed b04 physical bank binding')
        r.require(link.command('').endswith(previous.MON_PROMPT)
                  and link.dump(0x7d01, 0x7d01) == b'\x02'
                  and link.dump(0x7d30, 0x7d30) == b'\xb0', 'Expected idle b04 65C02 MON B')
        first = workflow.flash(link)
        ram = workflow.read_range(link, 0x200, 0x64ff)
        second = workflow.flash(link)
        ram_second = workflow.read_range(link, 0x200, 0x64ff)
        r.require(first == second == expected, 'Repeated source differs from completed b04 source')
        r.require(ram == ram_second and len(ram) == RAM_BYTES, 'Repeated source RAM differs')
        rows = snbt_records(first)
        cfg = max(rows)[2][32:48]
        r.require(cfg[1] == 0 and cfg[8] == 0xb0 and int.from_bytes(cfg[9:13], 'little') == 0x80000004,
                  'Expected disabled-autostart b04 saved MON B native configuration')
        identity = write(args.run / 'capture', first, ram,
                         evidence=dict(source_plan=str(args.plan), marker=marker,
                                       authorization_sha256=r.sha(args.authorization.read_bytes()),
                                       live_USB_serial=USB, CPU_byte='02', active_monitor='B',
                                       commands_read_only=True, flash_written=False, RAM_written=False))
        save(args.run / 'capture-report.json', dict(passed=True, board=BOARD, serial_released_on_exit=True,
             captured_utc=previous.now(), capture_json_sha256=r.sha((args.run / 'capture/capture.json').read_bytes()),
             source_sha256=identity['bank_sha256'], application_ram_sha256=identity['application_ram_sha256'],
             flash_written=False, RAM_written=False, reset_requested=False))
    print('PASS read-only repeated b04 native capture; serial released', args.run / 'capture', flush=True)


if __name__ == '__main__':
    main()
