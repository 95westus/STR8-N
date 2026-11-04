"""2512 services-g4/WB5 RAM qualification and fresh backups; no storage writes.

The installed ROM MON supplies fresh pre-helper owner RAM/ZP escrow. An
ordinary RAM call bridge invokes the exact unmodified services-g4 RAM image.
The private PB fixture is used only for CRC-framed READs, never its W command.
"""
import argparse
import binascii
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'release/str8nf-v0.2.0'
sys.path[:0] = [str(ROOT / 'tools'), str(REPO / 'tools'),
                str(REPO / 'migration-host'), str(ROOT / 'tmp/migration-python')]
import nf_provision_live as transport
import nf_migrate_live as live
import nf_recovery as recovery
from serial_test_coordination import serial_lease
from program_format import inspect as inspect_sram
from nf_migrate import classify_journal

REC, MON, WB, PB, CLOCK = b'REC> ', b'B3> ', b'WORKBENCH> ', b'PB> ', b'CLOCK> '
MARK = ROOT / 'output/qualification/device-operations/2512.json'
SVC = REPO / 'monitors/candidates/services-g00000004'
PB_DIR = ROOT / 'output/qualification/2609-PROGRAM-positive-scope-20261030-r1'
sha = lambda body: hashlib.sha256(body).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def inputs():
    marker = json.loads(MARK.read_text())
    assert marker['board'] == '2512' and marker['monitor_generation'] == '00000008'
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not marker['block_snapshot'] and not marker.get('physical_reset_pending')
    assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
    freeze = json.loads((REPO / 'F_FREEZE.json').read_text())
    assert marker['current_F_sha256'] == freeze['sha256']
    assert sha((REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == freeze['sha256']
    manifest = json.loads((SVC / 'manifest.json').read_text())
    packets = {}
    for variant in ('RAM', 'Full tool RAM packet'):
        name, info = next((n, i) for n, i in manifest['artifacts'].items() if i['variant'] == variant)
        body = (SVC / name).read_bytes()
        assert sha(body) == info['sha256'] and len(body) == info['bytes']
        packets[variant] = (body, info)
    assert packets['RAM'][1]['origin'] == '2000'
    pb_plan = json.loads((PB_DIR / 'plan.json').read_text())
    fixture = (PB_DIR / pb_plan['restorer']['filename']).read_bytes()
    assert sha(fixture) == '5dadab107c2663f6b75b8b2267b0ca480c3dcda854219b1635063cad68ff68a1'
    assert binascii.crc_hqx(fixture, 65535) == 0 and pb_plan['F_sha256'] == freeze['sha256']
    return marker, manifest, packets, fixture


class Session:
    def __init__(self, folder, log):
        self.folder, self.context, self.counter = folder, None, 0
        self.link = transport.RecoveryLink('COM4', log, usb_serial='A10MQFLCA')
        self.client = None

    def until(self, tokens, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = [(self.link.pending.find(t), t) for t in tokens if t in self.link.pending]
            if found:
                offset, self.context = min(found, key=lambda item: item[0])
                count = offset + len(self.context)
                body = bytes(self.link.pending[:count])
                del self.link.pending[:count]
                return body
            self.link.pending.extend(self.link.read(max(1, self.link.serial.in_waiting)))
        self.context = None
        raise TimeoutError(repr(bytes(self.link.pending[-250:])))

    def command(self, text, tokens=None, label=None):
        assert self.context is not None
        target = tokens or (self.context,)
        self.link.send(text.encode('ascii') + b'\r')
        out = self.until(target)
        self.counter += 1
        if label or not (text.startswith('M ') or text.startswith('D ')):
            (self.folder / f'{self.counter:04d}-{label or "command"}.txt').write_bytes(out)
        return out

    def monitor(self):
        if self.context == PB:
            # PB Q is immediate and must not leave a CR for MON to consume.
            self.link.send(b'Q')
            self.until((MON,))
        if self.context == CLOCK:
            self.command('Q', (MON,))
        if self.context == WB:
            self.command('Q', (MON,))
        if self.context == REC:
            out = self.command('B', (MON,))
            assert b'g00000008 / MON B' in out
        assert self.context == MON

    def rec(self):
        self.monitor()
        self.command('Q', (REC,))

    def dump(self, first, last):
        assert self.context == MON
        out = self.command(f'D {first:04X} {last:04X}')
        cells = {}
        for line in out.decode('ascii').splitlines():
            match = re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})', line.strip())
            if match:
                cells.update((int(match[1], 16) + i, b) for i, b in enumerate(bytes.fromhex(match[2])))
        assert all(a in cells for a in range(first, last + 1)), 'Incomplete native Dump'
        return bytes(cells[a] for a in range(first, last + 1))

    def owner(self):
        return (b''.join(self.dump(a, min(a + 2047, 0x66ff)) for a in range(0x200, 0x6700, 2048)),
                self.dump(0, 0xdf))

    def modify(self, address, body):
        assert self.context == MON and 0x200 <= address and address + len(body) <= 0x6700
        for offset in range(0, len(body), 8):
            self.command(f'M {address + offset:04X} ' + body[offset:offset + 8].hex(' ').upper())

    def load(self, body, digest, prompt):
        assert self.context == REC and sha(body) == digest
        recovery.PROMPT = prompt
        self.client = recovery.RecoveryClient(live.LoggedRecoveryStream(self.link), timeout=60)
        self.context = None
        self.client.load(body, digest, REC_observed=True)
        self.context = prompt

    def service(self, reader):
        self.load(reader, live.READBACK_SHA256, b'RAM SERVICE BASE1> ')

    def read_banks(self, label, hashes):
        for repeat in (1, 2):
            for bank in range(4):
                body = self.client.flash(bank)
                assert sha(body) == hashes[bank], f'Changed B{bank}'
                (self.folder / f'{label}-pass{repeat}-B{bank}.bin').write_bytes(body)

    def rpc(self, line, tokens=(MON,)):
        self.monitor()
        assert len(line) <= 40
        self.modify(0x3100, line.encode('ascii') + b'\0')
        self.modify(0x3130, b'\xff\xff')
        # A=bank3, X/Y=line3100; declared caller floor0200. Call the exact
        # unmodified RAM dispatcher at2008, capture status/A, then public HOLD.
        bridge = bytes.fromhex('78 D8 A2 FF 9A A9 02 8D FF 69 A9 03 A2 00 A0 31 '
                               '20 08 20 8D 31 31 08 68 8D 30 31 4C 67 7E')
        self.modify(0x3000, bridge)
        return self.command('G 3000', tokens, label='RPC-' + re.sub('[^A-Z0-9]', '-', line))

    def mount(self):
        assert self.context == WB
        self.command('EDU ON')
        result = self.command('SRAM')
        if b'SSRAM error $01' in result:
            assert b'Disabled CB flags acknowledged; no SPI clocks' in self.command('SRAM PREP')
            result = self.command('SRAM')
        assert b'SSRAM PROGRAM:' in result
        return result

    def sram(self, fixture, label):
        assert self.context == WB
        self.rec()
        self.load(fixture, sha(fixture), PB)
        body = bytearray()
        for address in range(0, 131072, 64):
            fields = bytes([address >> 16, (address >> 8) & 255, address & 255])
            self.link.send(b'R' + fields.hex().upper().encode() + b'\r')
            out = self.until((PB,))
            matches = re.findall(rb'D([0-9A-F]{138})\r?\n', out)
            assert len(matches) == 1
            frame = bytes.fromhex(matches[0].decode())
            assert len(frame) == 69 and frame[:3] == fields
            assert binascii.crc_hqx(frame[:-2], 65535) == int.from_bytes(frame[-2:], 'big')
            body.extend(frame[3:-2])
            if len(body) % 32768 == 0:
                print(f'{label}: {len(body)}/131072 bytes', flush=True)
        (self.folder / f'{label}-131072.bin').write_bytes(body)
        self.monitor()
        return bytes(body)


def run(folder):
    folder = folder.resolve()
    assert folder.is_relative_to(ROOT / 'output/qualification') and not folder.exists()
    folder.mkdir(parents=True)
    (folder / '.gitignore').write_text('*\n')
    report = dict(board='2512', CPU='65C02', port='COM4', usb_serial='A10MQFLCA',
                  passed=False, started_utc=utc(), flash_writes=0, journal_writes=0,
                  SRAM_data_writes=0, WORKSPACE_writes=0, RTC_SET=0, trim_writes=0,
                  PF_ACK=0, power_cuts=0, firmware_builds=0, original_context=MON.decode(),
                  owner_RAM_restored=False, checks=[], matched_flash_reload_qualified=False)
    session = None
    borrowed = False
    marker = None
    ram = zp = None
    def checkpoint():
        save(folder / 'report.json', report)
    def mark(**fields):
        current = json.loads(MARK.read_text())
        current.update(fields)
        save(MARK, current)
    def checked(label):
        report['checks'].append(label)
        checkpoint()
        print('PASS ' + label, flush=True)
    checkpoint()
    try:
        with serial_lease('2512-services-g4-RAM-qualification', timeout=30):
            marker, manifest, packets, fixture = inputs()
            hashes = [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
            reader = (REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
            assert sha(reader) == live.READBACK_SHA256
            save(folder / 'marker-before.json', marker)
            report.update(source_manifest=str(SVC / 'manifest.json'),
                          source_manifest_sha256=sha((SVC / 'manifest.json').read_bytes()),
                          service_RAM_sha256=packets['RAM'][1]['sha256'],
                          tools_RAM_sha256=packets['Full tool RAM packet'][1]['sha256'],
                          before_bank_sha256=hashes, read_only_fixture_sha256=sha(fixture))
            checkpoint()
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    session = Session(folder, log)
                    session.link.send(b'\r')
                    session.until((MON,), seconds=10)
                    ident = session.command('V')
                    assert b'g00000008 / MON B' in ident and b'CPU $02' in ident
                    ram, zp = session.owner()
                    assert (ram, zp) == session.owner(), 'Fresh owner double capture differs'
                    (folder / 'owner-ram.bin').write_bytes(ram)
                    (folder / 'owner-zp.bin').write_bytes(zp)
                    report.update(RAM_sha256=sha(ram), ZP_sha256=sha(zp), fresh_prehelper_owner_escrow=True)
                    checked('native-prehelper-owner-RAM-ZP-double-capture')
                    mark(services_g4_RAM_worker_active=True, application_RAM_restore_pending=True,
                         block_snapshot=True)
                    borrowed = True
                    session.rec()
                    transport.recovery_usb(session.link)
                    session.service(reader)
                    seen = session.client.read(b'M', 0x6500)
                    assert seen[:len(reader)] == reader and seen[len(reader):] == ram[len(reader):]
                    assert session.client.read(b'Z', 0xe0) == zp
                    session.read_banks('before', hashes)
                    journal = classify_journal((folder / 'before-pass1-B3.bin').read_bytes())
                    assert journal['sequence'] == 1028 and journal['valid_records'] == 31
                    save(folder / 'before-journal.json', journal)
                    session.client.restore_owner(ram, zp)
                    session.context = REC
                    checked('fresh-four-bank-double-backup-and-original-journal')
                    body, info = packets['Full tool RAM packet']
                    session.load(body, info['sha256'], WB)
                    assert b'S bank|P addr|AUTO' in session.command('?')
                    session.mount()
                    table = session.command('T P')
                    assert b'P:slot/kind#seq' in table and b'NF2512G4' not in table
                    session.command('WORK')
                    first = session.sram(fixture, 'SRAM-before')
                    layout = inspect_sram(first)
                    assert all(r.get('payload_CRC_valid', True) for r in layout['records'])
                    save(folder / 'PROGRAM-layout.json', layout)
                    checked('WB5-SP1-help-mount-table-and-full-SRAM-backup')

                    # Preserve the published dispatcher exactly; the call bridge
                    # is separate ordinary RAM, not a patch to its loader/data.
                    body, info = packets['RAM']
                    session.modify(0x2000, body)
                    assert session.dump(0x2000, 0x2fff) == body
                    for line in ('M1', 'M2', 'M3', 'W', 'APPS', 'APP NF2512G4'):
                        out = session.rpc(line)
                        assert b'Services absent/invalid' not in out
                        if line.startswith('APP '):
                            assert b'REFUSED' in out
                    checked('unmodified-g4-RAM-map-wear-APPS-and-missing-app-refusal')

                    for line in ('MAINT LOAD', '  MAINT LOAD  '):
                        out = session.rpc(line)
                        assert b'REFUSED: bundle/header/CRC failed; workbench not called' in out
                        assert b'Load flash WB2/PROGRAM:' in out
                        copied = session.dump(0x6840, 0x6868).split(b'\0', 1)[0]
                        assert copied.strip() == b'MAINT', 'LOAD option was not consumed'
                        assert session.dump(0x682e, 0x682e) == b'\x02'
                    out = session.rpc('MAINT LOAD X')
                    assert b'Load flash WB2/PROGRAM:' not in out
                    assert not (session.dump(0x3130, 0x3130)[0] & 1)
                    checked('g4-LOAD-consumed-old-bundle-refused-and-bad-argument-preflight')

                    for line in ('MAINT', 'FLASH'):
                        out = session.rpc(line, (WB, MON))
                        assert session.context == WB and b'WORKBENCH WB2 g00000005' in out
                        session.command('?')
                        session.monitor()
                    out = session.rpc('CLOCK', (CLOCK, MON))
                    assert session.context == CLOCK and re.search(rb'20\d\d-\d\d-\d\d', out)
                    session.command('R')
                    session.monitor()
                    checked('g4-cached-MAINT-FLASH-CLOCK-dispatch-and-public-return')

                    session.rpc('MAINT', (WB, MON))
                    assert session.context == WB
                    session.mount()
                    table = session.command('T P')
                    assert b'NF2512G4' not in table
                    assert b'BATCH done' in session.command('BATCH T;T')
                    assert b'BATCH done' not in session.command('BATCH T;;T')
                    session.command('R P NF2512G4 L')
                    out = session.command('S P AUTO 3000 3007 NF2512G4', (b'type YES> ', WB))
                    assert session.context == b'type YES> ' and b'Target PROGRAM' in out
                    assert b'Canceled; no record written' in session.command('NO', (WB,))
                    checked('WB5-SP1-BATCH-lookup-AUTO-preview-NO')
                    second = session.sram(fixture, 'SRAM-after')
                    assert first == second
                    report.update(all_131072_SRAM_bytes_unchanged=True, SRAM_sha256=sha(first),
                                  PROGRAM_format=layout['format'], PROGRAM_boundary=layout['boundary'])
                    assert session.dump(0x2000, 0x2fff) == packets['RAM'][0]
                    checked('full-SRAM-equality-and-dispatcher-image-unchanged')
                    session.rec()
                    session.service(reader)
                    session.read_banks('after', hashes)
                    report['all_flash_banks_unchanged'] = True
                    checked('all-images-boot-wear-F-double-verified-unchanged')
                finally:
                    try:
                        if borrowed:
                            if session.context == b'type YES> ':
                                session.command('NO', (WB,))
                            if session.context != b'RAM SERVICE BASE1> ':
                                session.rec()
                                session.service(reader)
                            report.update(session.client.restore_owner(ram, zp))
                            session.context = REC
                            session.monitor()
                            assert session.owner() == (ram, zp), 'Final native owner readback differs'
                            report.update(owner_RAM_restored=True, owner_ZP_restored=True,
                                          original_MON_B_context_restored=True)
                    finally:
                        if session is not None:
                            session.link.close()
                            report['COM4_released'] = True
                            report['final_context'] = session.context.decode() if session.context else None
                        if marker is not None:
                            restored = report['owner_RAM_restored'] if borrowed else True
                            mark(services_g4_RAM_worker_active=False,
                                 application_RAM_restore_pending=not restored,
                                 application_ram_restored=restored,
                                 block_snapshot=marker['block_snapshot'] if restored else True,
                                 last_services_g4_RAM_qualification=str(folder / 'report.json'))
                        checkpoint()
            assert report['owner_RAM_restored'] and report['all_flash_banks_unchanged']
            assert report['all_131072_SRAM_bytes_unchanged']
            report.update(passed=True, phase='G4_RAM_65C02_PASSED_NOT_INSTALLED', finished_utc=utc(),
                          actual_matched_flash_load='Pending separately reviewed installation')
            checkpoint()
            print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=utc())
        checkpoint()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    run(parser.parse_args().folder)
