"""2609 feature readiness: RAM only, guarded HOLD restoration, no storage commit."""
import argparse
import hashlib
import json
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'release/str8nf-v0.2.0'
sys.path[:0] = [str(ROOT / 'tools'), str(KIT / 'tools'),
                str(KIT / 'migration-host'), str(ROOT / 'tmp/migration-python')]
import rtc_base1_2609 as baseline
import nf_provision_live as transport
import nf_migrate_live as live
import nf_recovery as recovery
from serial_test_coordination import serial_lease
from installer.common import save

REC, MON, WB = b'REC> ', b'B3> ', b'WORKBENCH> '
MARK = ROOT / 'output/qualification/device-operations/2609.json'
SVC = KIT / 'monitors/candidates/services-g00000003-r5'
utc = lambda: datetime.now(timezone.utc).isoformat()
sha = lambda b: hashlib.sha256(b).hexdigest()


def inputs():
    result = baseline.inputs()
    manifest = json.loads((SVC / 'manifest.json').read_text())
    selected = {}
    for variant in ('RAM trial composite', 'Full tool RAM packet'):
        name, info = next((n, i) for n, i in manifest['artifacts'].items()
                          if i['variant'] == variant)
        body = (SVC / name).read_bytes()
        assert sha(body) == info['sha256'] and len(body) == info['bytes']
        selected[variant] = (name, body, info['sha256'])
    return result, selected


def run(folder):
    authority, packets = inputs()
    marker, receipt, meta, bodies, _, _, reader, hashes = authority
    folder = folder.resolve()
    assert folder.is_relative_to(ROOT / 'output/qualification')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / '.gitignore').write_text('*\n')
    save(folder / 'marker-before.json', marker)
    save(folder / 'escrow-authority.json', meta)
    report = dict(board='2609', port='COM8', usb_serial='A10MPQXCA',
                  CPU='65C816 emulation', started_utc=utc(), passed=False,
                  flash_writes=0, journal_writes=0, boot_setting_writes=0,
                  SRAM_data_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0,
                  firmware_builds=0, owner_RAM_restored=False,
                  HOLD_restored=False, checks=[], phase='prepared',
                  packets={n: dict(filename=p[0], sha256=p[2]) for n, p in packets.items()},
                  prefix_authority=meta['prefix_authority'])
    original_ram, original_zp = bodies['owner-ram.bin'], bodies['owner-zp.bin']
    link = None
    context = None
    borrowed = False
    hold_original = None
    hook_pending = False
    counter = 0

    def checkpoint():
        save(folder / 'report.json', report)

    def mark(**changes):
        current = json.loads(MARK.read_text())
        current.update(changes)
        save(MARK, current)

    def record(label, data):
        nonlocal counter
        counter += 1
        (folder / f'{counter:03d}-{label}.txt').write_bytes(data)
        return data

    def until_any(tokens, seconds=25):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = [(link.pending.find(token), token) for token in tokens
                     if token in link.pending]
            if found:
                start, token = min(found, key=lambda item: item[0])
                end = start + len(token)
                data = bytes(link.pending[:end])
                del link.pending[:end]
                return data, token
            link.pending.extend(link.read(max(1, link.serial.in_waiting)))
        raise TimeoutError('No admitted prompt: ' + repr(bytes(link.pending[-180:])))

    def command(text, prompt=None, seconds=25):
        target = prompt or context
        assert target == WB or re.fullmatch(rb'B[0-3]> ', target)
        link.send(text.encode('ascii') + b'\r')
        data, _ = until_any((target,), seconds=seconds)
        return record('command', data)

    def dump(first, last):
        out = command(f'D {first:04X} {last:04X}', MON)
        cells = {}
        for line in out.decode('ascii').splitlines():
            match = re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})', line.strip())
            if match:
                cells.update((int(match[1], 16) + i, b)
                             for i, b in enumerate(bytes.fromhex(match[2])))
        assert all(a in cells for a in range(first, last + 1)), 'Incomplete native dump'
        return bytes(cells[a] for a in range(first, last + 1))

    def load_packet(which, prompt):
        nonlocal context, borrowed
        assert context == REC
        name, body, digest = packets[which]
        recovery.PROMPT = prompt
        client = recovery.RecoveryClient(live.LoggedRecoveryStream(link), timeout=60)
        borrowed = True
        context = None
        client.load(body, digest, REC_observed=True)
        context = prompt
        report['phase'] = name
        checkpoint()

    def quit_to_rec():
        nonlocal context
        assert context in (MON, WB)
        if context == WB:
            assert hook_pending, 'Workbench HOLD must be safely bound before Q'
        link.send(b'Q\r')
        context = None
        data, _ = until_any((REC,), seconds=15)
        record('Q-REC', data)
        context = REC

    def restore_hold():
        nonlocal hook_pending
        if not hook_pending:
            return
        if context == WB:
            quit_to_rec()
        if context == REC:
            load_packet('RAM trial composite', MON)
        assert context == MON and hold_original is not None
        command('!M 7E68 ' + ' '.join(f'{b:02X}' for b in hold_original[1:]))
        assert dump(0x7e67, 0x7e69) == hold_original
        hook_pending = False
        report['HOLD_restored'] = True
        checkpoint()

    def readback():
        nonlocal context, borrowed
        assert context == REC
        recovery.PROMPT = b'RAM SERVICE BASE1> '
        client = recovery.RecoveryClient(live.LoggedRecoveryStream(link), timeout=60)
        borrowed = True
        context = None
        client.load(reader, live.READBACK_SHA256, REC_observed=True)
        context = recovery.PROMPT
        return client

    checkpoint()
    try:
      with serial_lease('2609-MON-feature-RAM', timeout=30):
        inputs()
        with (folder / 'serial.jsonl').open('x', encoding='utf-8') as log:
          try:
            link = transport.RecoveryLink('COM8', log, usb_serial='A10MPQXCA')
            link.send(b'\r')
            record('initial-REC', link.until(REC, seconds=10))
            context = REC
            transport.recovery_usb(link)
            mark(feature_readiness_worker_active=True, application_RAM_restore_pending=True,
                 block_snapshot=True)
            client = readback()
            first, repeat = client.read(b'M', recovery.RAM_BYTES), client.read(b'M', recovery.RAM_BYTES)
            zp, zp_repeat = client.read(b'Z', recovery.ZP_BYTES), client.read(b'Z', recovery.ZP_BYTES)
            # Retain freshly observed tail/ZP even if admission then refuses;
            # never restore a stale whole-RAM snapshot over a changed tail.
            declared_ram, declared_zp = original_ram, original_zp
            original_ram = declared_ram[:len(reader)] + first[len(reader):]
            original_zp = zp
            assert first == repeat and zp == zp_repeat == declared_zp
            assert first[:len(reader)] == reader
            assert first[len(reader):] == declared_ram[len(reader):], 'Changed escrow authority'
            (folder / 'owner-ram.bin').write_bytes(original_ram)
            (folder / 'owner-zp.bin').write_bytes(original_zp)
            for number in (1, 2):
                for bank in (3, 0, 1, 2):
                    data = client.flash(bank)
                    assert sha(data) == hashes[bank]
                    (folder / f'before-{number}-b{bank}.bin').write_bytes(data)
            client.restore_owner(original_ram, original_zp)
            context = REC
            report['checks'].append('fresh-bank-and-owner-authority-admission')
            checkpoint()

            load_packet('RAM trial composite', MON)
            assert b'CPU $16' in command('V')
            command('?')
            old = dump(0x3000, 0x3007)
            command('M 3000 12 34 56 78')
            assert dump(0x3000, 0x3003) == bytes.fromhex('12 34 56 78')
            command('!M 3004 9A BC DE F0')
            assert dump(0x3004, 0x3007) == bytes.fromhex('9A BC DE F0')
            command('M 3000 ' + ' '.join(f'{b:02X}' for b in old))
            assert dump(0x3000, 0x3007) == old
            for address in ('C000', 'D000', 'F000'):
                assert b'REFUSED' in command('!M ' + address + ' FF')
            command('B0', b'B0> ')
            command('D 8000 800F', b'B0> ')
            command('B3', MON)
            times = [command('TIME') for _ in range(2)]
            report['native_TIME_valid'] = all(re.search(rb'20\d\d-\d\d-\d\d', x) for x in times)
            for text in ('M1', 'W'):
                command(text)
            apps = command('APPS')
            assert b'NF30TEST' not in apps, 'Do not launch an existing owner app'
            command('APP NF30TEST')
            report['checks'].append('MON-g8-services-g3-816E-D-M-force-guards-map-wear-APPS')
            hold_original = dump(0x7e67, 0x7e69)
            assert hold_original[0] == 0x4c
            report['original_HOLD_jump_hex'] = hold_original.hex()
            # Only a volatile public-RAM JMP operand; F stays byte-identical.
            hook_pending = True
            command('!M 7E68 AF F2')
            assert dump(0x7e67, 0x7e69) == bytes.fromhex('4C AF F2')
            checkpoint()
            quit_to_rec()

            load_packet('Full tool RAM packet', WB)
            help_text = command('?')
            assert b'S bank|P' in help_text
            command('EDU ON')
            sram = command('SRAM')
            # PREP itself checks IER/PCR/ACR/DDRB before reading ORB. A busy
            # owner is refused in that command; never bypass its guard.
            if b'SSRAM error $01' in sram:
                prepared = command('SRAM PREP')
                report['disabled_CB_flags_PREP'] = prepared.decode('ascii', errors='replace')
                assert b'Disabled CB flags acknowledged; no SPI clocks' in prepared
                sram = command('SRAM')
            table = command('T P')
            command('WORK')
            batch = command('BATCH T;T')
            report['BATCH_normal_reply'] = batch.decode('ascii', errors='replace')
            command('BATCH T;;T')
            # No run or Restore of a retained owner record. Unique test name
            # is only used after confirming it is absent from the live table.
            name = 'NF30TEST'
            assert name.encode() not in table
            command('R P ' + name + ' L')
            link.send(('S P AUTO 3000 3007 ' + name + '\r').encode())
            preview, token = until_any((b'type YES> ', WB))
            record('PROGRAM-AUTO-preview', preview)
            report['PROGRAM_AUTO_reached_confirmation'] = token != WB
            if token != WB:
                link.send(b'NO\r')
                data, _ = until_any((WB,), seconds=25)
                canceled = record('PROGRAM-AUTO-NO', data)
                assert b'Canceled; no record written' in canceled
            report['SRAM_reply'] = sram.decode('ascii', errors='replace')
            report['PROGRAM_table_reply'] = table.decode('ascii', errors='replace')
            report['PROGRAM_readiness_passed'] = (b'SSRAM PROGRAM:' in sram
                and b'P:slot/kind#seq' in table
                and b'BATCH stopped' not in batch
                and report['PROGRAM_AUTO_reached_confirmation'])
            report['checks'].append('WB2-g5-SP1-help-read-only-and-cancel-only-816E')
            quit_to_rec()
            restore_hold()
            quit_to_rec()

            client = readback()
            for bank in (3, 0, 1, 2):
                data = client.flash(bank)
                (folder / f'after-b{bank}.bin').write_bytes(data)
                assert data == (folder / f'before-1-b{bank}.bin').read_bytes()
            report['all_flash_banks_unchanged'] = True
            report['checks'].append('all-images-boot-wear-F-unchanged')
            checkpoint()
          finally:
            try:
                if link is not None and borrowed:
                    restore_hold()
                    if context in (MON, WB):
                        quit_to_rec()
                    if context == REC:
                        client = readback()
                    if context == b'RAM SERVICE BASE1> ':
                        report.update(client.restore_owner(original_ram, original_zp))
                        report['owner_RAM_restored'] = True
                        context = REC
                    else:
                        raise RuntimeError('No admitted restoration prompt; preserve power and escrow')
            finally:
                if link is not None:
                    link.close()
                    report['port_released'] = True
                restored = report['owner_RAM_restored'] and not hook_pending
                mark(feature_readiness_worker_active=False,
                     application_RAM_restore_pending=borrowed and not restored,
                     application_ram_restored=restored if borrowed else marker['application_ram_restored'],
                     block_snapshot=marker['block_snapshot'] if restored or not borrowed else True,
                     last_MON_feature_RAM_trial=str(folder / 'report.json'))
                report['final_context'] = context.decode(errors='replace') if context else None
                checkpoint()
      assert report['owner_RAM_restored'] and report['HOLD_restored']
      assert report.get('all_flash_banks_unchanged') and report['port_released']
      report.update(passed=True, phase='closed', finished_utc=utc())
      checkpoint()
      print(json.dumps(report, indent=2))
    except BaseException as error:
      report.update(error=repr(error), traceback=traceback.format_exc(), finished_utc=utc())
      checkpoint()
      raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    run(args.folder)
