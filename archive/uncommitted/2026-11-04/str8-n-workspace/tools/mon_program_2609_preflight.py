"""Read-only PROGRAM scope capture for the installed, released MON preview.

No flash/journal/SRAM-data/RTC-setting writes. Owner RAM/ZP is escrowed and
restored using the existing qualified authority, with the RTC serial lease.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mon_features_2609_ram as t
import rtc_monb8_2609 as qualified
from program_format import inspect

KIT = (t.KIT / 'dist/mon-g8-tools-preview1-final/verified-extraction/'
       'STR8N-MON-g8-tools-preview1')
utc = lambda: datetime.now(timezone.utc).isoformat()


def run(folder):
    folder = folder.resolve()
    assert folder.is_relative_to(ROOT / 'output/qualification')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / '.gitignore').write_text('*\n')
    report = dict(board='2609', port='COM8', usb_serial='A10MPQXCA',
                  CPU='65C816 emulation', started_utc=utc(), passed=False,
                  flash_writes=0, journal_writes=0, boot_setting_writes=0,
                  SRAM_data_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0,
                  power_cuts=0, firmware_builds=0, owner_RAM_restored=False)
    link = None
    context = None
    client = None
    borrowed = False
    marker = None
    counter = 0

    def save():
        t.save(folder / 'report.json', report)

    def mark(**fields):
        current = json.loads(t.MARK.read_text())
        current.update(fields)
        t.save(t.MARK, current)

    def until(tokens, seconds=40):
        nonlocal context
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = [(link.pending.find(p), p) for p in tokens if p in link.pending]
            if found:
                offset, context = min(found, key=lambda item: item[0])
                end = offset + len(context)
                body = bytes(link.pending[:end])
                del link.pending[:end]
                return body
            link.pending.extend(link.read(max(1, link.serial.in_waiting)))
        context = None
        raise TimeoutError('Expected prompt absent: ' + repr(bytes(link.pending[-200:])))

    def command(text, tokens=None):
        nonlocal counter
        target = tokens or (context,)
        assert target and all(p for p in target)
        link.send(text.encode('ascii') + b'\r')
        out = until(target)
        counter += 1
        if not text.startswith('SRAM READ '):
            (folder / f'{counter:04d}-command.txt').write_bytes(out)
        return out

    def service():
        nonlocal context, client, borrowed
        assert context == t.REC
        t.recovery.PROMPT = b'RAM SERVICE BASE1> '
        client = t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(link), timeout=60)
        borrowed = True
        context = None
        client.load(reader, t.live.READBACK_SHA256, REC_observed=True)
        context = t.recovery.PROMPT

    def banks(prefix):
        assert context == b'RAM SERVICE BASE1> '
        for bank in range(4):
            for repeat in (1, 2):
                body = client.flash(bank)
                assert t.sha(body) == bank_hashes[bank], f'Changed B{bank}'
                (folder / f'{prefix}-B{bank}-pass{repeat}.bin').write_bytes(body)

    def capture_sram(repeat):
        result = bytearray()
        with (folder / f'SRAM-pass{repeat}-console.txt').open('wb') as capture:
            for address in range(0, 131072, 64):
                out = command(f'SRAM READ {address >> 16} {address & 0xffff:04X}')
                capture.write(out)
                matches = re.findall(rb'RAW64 ((?:[0-9A-F]{2} ){64})', out)
                assert len(matches) == 1, 'No exact RAW64 reply: ' + repr(out[-300:])
                block = bytes.fromhex(matches[0].decode())
                assert len(block) == 64
                result.extend(block)
                if len(result) % 16384 == 0:
                    print(f'2609 SRAM pass {repeat}: {len(result)}/131072 bytes', flush=True)
                    report.update(SRAM_pass=repeat, SRAM_bytes=len(result))
                    save()
        (folder / f'SRAM-pass{repeat}-131072.bin').write_bytes(result)
        return bytes(result)

    save()
    try:
        with t.serial_lease('2609-PROGRAM-readonly-scope', timeout=30):
            marker, receipt, meta, bodies, _, _, _, bank_hashes = qualified.inputs()
            ram, zp = bodies['owner-ram.bin'], bodies['owner-zp.bin']
            reader = (KIT / 'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
            assert t.sha(reader) == t.live.READBACK_SHA256
            t.save(folder / 'marker-before.json', marker)
            t.save(folder / 'escrow-authority.json', meta)
            report.update(source_receipt=str(receipt), source_receipt_sha256=t.sha(receipt.read_bytes()),
                          bank_sha256=bank_hashes, owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp),
                          READBACK_sha256=t.sha(reader), extracted_preview=str(KIT))
            save()
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    link = t.transport.RecoveryLink('COM8', log, usb_serial='A10MPQXCA')
                    link.send(b'\r')
                    until((t.REC,), seconds=5)
                    t.transport.recovery_usb(link)
                    mark(program_preflight_worker_active=True, application_RAM_restore_pending=True,
                         block_snapshot=True)
                    service()
                    a, b = client.read(b'M', 0x6500), client.read(b'M', 0x6500)
                    z, zz = client.read(b'Z', 0xe0), client.read(b'Z', 0xe0)
                    assert a == b and z == zz == zp
                    assert a[:len(reader)] == reader and a[len(reader):] == ram[len(reader):]
                    (folder / 'owner-ram.bin').write_bytes(ram)
                    (folder / 'owner-zp.bin').write_bytes(zp)
                    banks('before')
                    client.restore_owner(ram, zp)
                    context = t.REC
                    banner = command('B', (t.MON,))
                    assert b'g00000008 / MON B' in banner and b'CPU $16' in banner
                    tools = command('MAINT LOAD', (t.WB, t.MON))
                    assert context == t.WB and b'WORKBENCH WB2 g00000005' in tools
                    command('EDU ON')
                    status = command('SRAM')
                    if b'SSRAM error $01' in status:
                        assert b'Disabled CB flags acknowledged' in command('SRAM PREP')
                        status = command('SRAM')
                    assert b'SSRAM PROGRAM:' in status
                    table = command('T P')
                    (folder / 'PROGRAM-table.txt').write_bytes(table)
                    first, second = capture_sram(1), capture_sram(2)
                    assert first == second, 'Full SRAM reads differ; no write scope admitted'
                    layout = inspect(first)
                    assert all(r.get('payload_CRC_valid', True) for r in layout['records'])
                    t.save(folder / 'PROGRAM-layout.json', layout)
                    report.update(SRAM_sha256=t.sha(first), full_SRAM_double_read_equal=True,
                                  PROGRAM_format=layout['format'], PROGRAM_boundary=layout['boundary'],
                                  free_slots=[s['slot'] for s in layout['free_slots']],
                                  free_pages=layout['free_pages'], live_records=len(layout['records']))
                    command('Q', (t.MON,))
                    command('Q', (t.REC,))
                    service()
                    banks('after')
                finally:
                    try:
                        if borrowed:
                            if context == t.WB:
                                command('Q', (t.MON,))
                            if context == t.MON:
                                command('Q', (t.REC,))
                            if context == t.REC:
                                service()
                            if context != b'RAM SERVICE BASE1> ':
                                raise RuntimeError('No restoration prompt; keep power on and inspect')
                            report.update(client.restore_owner(ram, zp))
                            report['owner_RAM_restored'] = True
                            context = t.REC
                    finally:
                        if link is not None:
                            link.close()
                            report['COM8_released'] = True
                        if marker is not None:
                            restored = report['owner_RAM_restored'] if borrowed else True
                            mark(program_preflight_worker_active=False,
                                 application_RAM_restore_pending=not restored,
                                 application_ram_restored=restored,
                                 block_snapshot=marker['block_snapshot'] if restored else True,
                                 last_PROGRAM_readonly_preflight=str(folder / 'report.json'))
                        report['final_context'] = context.decode() if context else None
                        save()
            assert report['full_SRAM_double_read_equal'] and report['owner_RAM_restored']
            report.update(passed=True, finished_utc=utc(), phase='READONLY_SCOPE_CAPTURE_PASSED')
            save()
            print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=utc())
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    run(parser.parse_args().folder)
