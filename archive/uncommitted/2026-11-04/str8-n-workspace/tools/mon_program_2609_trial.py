"""Run only an explicitly approved, hash-bound 2609 temporary PROGRAM trial."""
import argparse
import binascii
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mon_program_2609_preflight as base
import mon_features_2609_ram as t
import rtc_monb8_2609 as qualified

BENCH = b'PB> '


class Session:
    def __init__(self, folder, log, reader, plan, scope):
        self.folder, self.reader, self.plan, self.scope = folder, reader, plan, scope
        self.link = t.transport.RecoveryLink('COM8', log, usb_serial='A10MPQXCA')
        self.context, self.client, self.n = None, None, 0

    def until(self, tokens, seconds=50):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            found = [(self.link.pending.find(x), x) for x in tokens if x in self.link.pending]
            if found:
                start, self.context = min(found, key=lambda item: item[0])
                end_index = start + len(self.context)
                body = bytes(self.link.pending[:end_index])
                del self.link.pending[:end_index]
                return body
            self.link.pending.extend(self.link.read(max(1, self.link.serial.in_waiting)))
        self.context = None
        raise TimeoutError(repr(bytes(self.link.pending[-250:])))

    def command(self, text, tokens=None):
        tokens = tokens or (self.context,)
        assert all(tokens)
        self.link.send(text.encode('ascii') + b'\r')
        body = self.until(tokens)
        self.n += 1
        if not text.startswith('SRAM READ '):
            (self.folder / f'{self.n:04d}.txt').write_bytes(body)
        return body

    def monitor(self):
        if self.context == t.WB:
            self.command('Q', (t.MON,))
        if self.context == BENCH:
            # Bench Q is an immediate single-byte command, without EOL.
            # A trailing CR would become an extra blank MON command/prompt
            # and could be mistaken for the following MAINT LOAD response.
            self.link.send(b'Q')
            out = self.until((t.MON,))
            self.n += 1
            (self.folder / f'{self.n:04d}-bench-Q.txt').write_bytes(out)
        if self.context == t.REC:
            banner = self.command('B', (t.MON,))
            assert b'g00000008 / MON B' in banner and b'CPU $16' in banner
        assert self.context == t.MON

    def recovery(self):
        self.monitor()
        self.command('Q', (t.REC,))

    def workbench(self):
        self.monitor()
        out = self.command('MAINT LOAD', (t.WB, t.MON))
        assert self.context == t.WB and b'WORKBENCH WB2 g00000005' in out
        self.command('EDU ON')
        out = self.command('SRAM')
        if b'SSRAM error $01' in out:
            assert b'Disabled CB flags acknowledged' in self.command('SRAM PREP')
            out = self.command('SRAM')
        assert b'SSRAM PROGRAM:' in out

    def load(self, body, digest, prompt):
        assert self.context == t.REC and t.sha(body) == digest
        t.recovery.PROMPT = prompt
        self.client = t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(self.link), timeout=60)
        self.context = None
        self.client.load(body, digest, REC_observed=True)
        self.context = prompt

    def service(self):
        self.load(self.reader, t.live.READBACK_SHA256, b'RAM SERVICE BASE1> ')

    def bench(self):
        # Reload the published provider before executing the guarded restorer.
        self.workbench()
        self.recovery()
        info = self.plan['restorer']
        self.load((self.scope / info['filename']).read_bytes(), info['sha256'], BENCH)

    def block(self, address, body):
        assert self.context == BENCH and len(body) == 64
        assert f'{address:04X}' in self.plan['allowed_64_byte_writes']
        fields = bytes([0, address >> 8, address & 255])
        crc = binascii.crc_hqx(fields + body, 65535)
        out = self.command('W' + fields.hex().upper() + body.hex().upper() + f'{crc:04X}')
        # A hexadecimal CRC may itself end in Ehh. The exact positive CRC
        # acknowledgement distinguishes success from a separate Ehh reply.
        assert f'O{crc:04X}\r\n'.encode() in out

    def raw(self, address):
        assert self.context == t.WB
        out = self.command(f'SRAM READ {address >> 16} {address & 65535:04X}')
        matches = re.findall(rb'RAW64 ((?:[0-9A-F]{2} ){64})', out)
        assert len(matches) == 1
        return bytes.fromhex(matches[0].decode())

    def full_sram(self, label):
        # The guarded bench streams CRC-framed reads without rechecking the
        # entire provider CRC for each 64-byte native command. It verifies
        # Foundation/provider identity once on entry; READ never uses WRITE.
        self.bench()
        body = bytearray()
        for address in range(0, 131072, 64):
            fields = bytes([address >> 16, (address >> 8) & 255, address & 255])
            out = self.command('R' + fields.hex().upper())
            frames = re.findall(rb'D([0-9A-F]{138})\r?\n', out)
            assert len(frames) == 1
            packet = bytes.fromhex(frames[0].decode())
            assert packet[:3] == fields and len(packet) == 69
            assert binascii.crc_hqx(packet[:-2], 65535) == int.from_bytes(packet[-2:], 'big')
            body.extend(packet[3:-2])
            if len(body) % 16384 == 0:
                print(f'{label}: {len(body)}/131072 bytes', flush=True)
        (self.folder / f'{label}-131072.bin').write_bytes(body)
        self.workbench()
        return bytes(body)

    def memory(self, address, body):
        self.monitor()
        for offset in range(0, len(body), 8):
            self.command(f'M {address + offset:04X} ' + body[offset:offset + 8].hex(' ').upper())

    def dump(self, address, length):
        self.monitor()
        out = self.command(f'D {address:04X} {address + length - 1:04X}')
        cells = {}
        for line in out.decode().splitlines():
            match = re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})', line.strip())
            if match:
                cells.update((int(match[1], 16) + i, b) for i, b in enumerate(bytes.fromhex(match[2])))
        return bytes(cells[a] for a in range(address, address + length))


def run(scope, approval, folder):
    scope, approval, folder = scope.resolve(), approval.resolve(), folder.resolve()
    plan = json.loads((scope / 'plan.json').read_text())
    auth = json.loads(approval.read_text())
    assert auth['board'] == '2609' and auth['approved'] is True
    assert auth['plan_sha256'] == t.sha((scope / 'plan.json').read_bytes())
    assert auth['owner_answer'] and auth['temporary_PROGRAM_writes'] is True
    assert plan['driver_sha256'] == t.sha(Path(__file__).read_bytes())
    assert plan['temporary_byte_scope'] == 1280 and plan['flash_writes'] == plan['journal_writes'] == 0
    assert plan['allowed_64_byte_writes'] == ['0040', '0080', '00C0', '0100'] + [f'{a:04X}' for a in range(0xc000, 0xc400, 64)]
    capture = Path(plan['capture'])
    snapshot = (capture / 'SRAM-pass1-131072.bin').read_bytes()
    assert t.sha(snapshot) == plan['SRAM_sha256']
    assert t.sha((capture / 'report.json').read_bytes()) == plan['capture_report_sha256']
    fixtures = {n: (scope / f'PROGRAM-{n}-23.bin').read_bytes() for n in ('OK', 'UP')}
    assert {n: t.sha(b) for n, b in fixtures.items()} == plan['fixture_sha256']
    assert folder.is_relative_to(ROOT / 'output/qualification') and not folder.exists()
    folder.mkdir(parents=True)
    (folder / '.gitignore').write_text('*\n')
    t.save(folder / 'approval.json', auth)
    report = dict(board='2609', CPU='65C816 emulation', passed=False, started_utc=base.utc(),
                  plan_sha256=auth['plan_sha256'], flash_writes=0, journal_writes=0,
                  RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0,
                  SRAM_restore_pending=False, owner_RAM_restored=False, checks=[])
    session = None
    borrowed = False
    marker = None

    def save():
        t.save(folder / 'report.json', report)

    def mark(**fields):
        current = json.loads(t.MARK.read_text())
        current.update(fields)
        t.save(t.MARK, current)

    def check(name):
        report['checks'].append(name)
        save()
        print('PASS ' + name, flush=True)

    def store(name, source, target):
        session.memory(source, fixtures['UP' if source == 0x3020 else 'OK'])
        session.workbench()
        out = session.command(f'S P {target} {source:04X} {source + 22:04X} {name}',
                              (b'type YES> ', t.WB))
        assert session.context == b'type YES> '
        expected = int(target, 16) if target != 'AUTO' else (0xc000 + len(report['stores']) * 256)
        assert f'Target PROGRAM ${expected:04X}'.encode() in out
        report['SRAM_restore_pending'] = True
        save()
        mark(PROGRAM_SRAM_restore_pending=True)
        result = session.command('YES', (t.WB,))
        assert b'Stored PROGRAM; CRC verified; commit last' in result
        report['stores'].append(dict(name=name, source=f'{source:04X}', target=f'{expected:04X}'))
        check('store-' + name + '-' + f'{expected:04X}')

    def restore_sram():
        session.bench()
        for address_text in plan['allowed_64_byte_writes']:
            address = int(address_text, 16)
            body = (scope / f'original-{address:04X}.bin').read_bytes()
            assert body == snapshot[address:address + 64]
            session.block(address, body)
        session.workbench()
        assert session.full_sram('SRAM-restored') == snapshot
        report['SRAM_restore_pending'] = False
        report['all_131072_SRAM_bytes_restored'] = True
        mark(PROGRAM_SRAM_restore_pending=False)
        check('full-SRAM-restore-compare')

    save()
    try:
        with t.serial_lease('2609-approved-PROGRAM-trial', timeout=30):
            marker, _, _, bodies, _, _, _, bank_hashes = qualified.inputs()
            assert bank_hashes == plan['source_bank_sha256']
            ram, zp = bodies['owner-ram.bin'], bodies['owner-zp.bin']
            reader = (base.KIT / 'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
            t.save(folder / 'marker-before.json', marker)
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    session = Session(folder, log, reader, plan, scope)
                    session.link.send(b'\r')
                    session.until((t.REC,), seconds=5)
                    t.transport.recovery_usb(session.link)
                    borrowed = True
                    mark(program_trial_worker_active=True, application_RAM_restore_pending=True,
                         block_snapshot=True)
                    session.service()
                    a, b = session.client.read(b'M', 0x6500), session.client.read(b'M', 0x6500)
                    assert a == b and a[:len(reader)] == reader and a[len(reader):] == ram[len(reader):]
                    assert session.client.read(b'Z', 0xe0) == zp == session.client.read(b'Z', 0xe0)
                    for bank in range(4):
                        assert t.sha(session.client.flash(bank)) == bank_hashes[bank]
                    session.client.restore_owner(ram, zp)
                    session.context = t.REC
                    session.workbench()
                    assert session.full_sram('SRAM-fresh-before') == snapshot
                    check('fresh-complete-SRAM-matches-approved-capture')
                    initial_table = session.command('T P')
                    assert b'NF30' not in initial_table
                    report['stores'] = []
                    session.memory(0x3000, fixtures['OK'])
                    session.workbench()
                    preview = session.command('S P AUTO 3000 3016 NF30PROGRAM_LONG', (b'type YES> ', t.WB))
                    assert session.context == b'type YES> ' and b'Target PROGRAM $C000' in preview
                    assert b'Canceled; no record written' in session.command('NO', (t.WB,))
                    for address in [0x40, 0x80, 0xc0, 0x100] + list(range(0xc000, 0xc400, 64)):
                        assert session.raw(address) == snapshot[address:address + 64]
                    check('AUTO-preview-NO-no-write')
                    store('NF30PROGRAM_LONG', 0x3000, 'AUTO')
                    store('NF30P', 0x3000, 'AUTO')
                    store('NF30P', 0x3020, 'AUTO')
                    store('NF30EX', 0x3000, 'C300')
                    assert b'SSRAM error $43' in session.command('S P AUTO 3000 3016 NF30EXTRA')
                    check('directory-full-refused')
                    assert b'NF30PROGRAM_LONG' in session.command('T P')
                    assert b'NF30P' in session.command('T')
                    session.memory(0x3020, bytes([0xaa]) * 23)
                    session.workbench()
                    assert b'Loaded PROGRAM; payload CRC verified' in session.command('R P NF30P L')
                    assert session.dump(0x3020, 23) == fixtures['UP']
                    check('latest-version-load-only-exact')
                    session.workbench()
                    out = session.command('R P NF30P', (t.MON,))
                    assert b'UP\r\n' in out and b'CPU $16' in out
                    check('positive-PROGRAM-run-public-HOLD-return')
                    session.workbench()
                    good = session.raw(0xc200)
                    assert good[:23] == fixtures['UP']
                    damaged = bytes([good[0] ^ 1]) + good[1:]
                    session.bench()
                    session.block(0xc200, damaged)
                    session.memory(0x3020, bytes([0xa5]) * 23)
                    session.workbench()
                    assert b'SSRAM error $45' in session.command('R P NF30P L')
                    assert session.dump(0x3020, 23) == bytes([0xa5]) * 23
                    check('payload-CRC-refused-before-owner-copy')
                    session.bench()
                    session.block(0xc200, good)
                    session.workbench()
                    assert b'Loaded PROGRAM; payload CRC verified' in session.command('R P NF30P L')
                    assert session.dump(0x3020, 23) == fixtures['UP']
                    check('CRC-repaired-restore')
                finally:
                    try:
                        if borrowed and session.context == b'type YES> ':
                            session.command('NO', (t.WB,))
                        if report['SRAM_restore_pending']:
                            restore_sram()
                        if borrowed:
                            if session.context != b'RAM SERVICE BASE1> ':
                                session.recovery()
                                session.service()
                            for bank in range(4):
                                body = session.client.flash(bank)
                                assert t.sha(body) == bank_hashes[bank]
                                (folder / f'final-B{bank}.bin').write_bytes(body)
                            report.update(session.client.restore_owner(ram, zp))
                            report['owner_RAM_restored'] = True
                            session.context = t.REC
                    finally:
                        if session is not None:
                            session.link.close()
                            report['COM8_released'] = True
                            report['final_context'] = session.context.decode() if session.context else None
                        if marker is not None:
                            restored = report['owner_RAM_restored'] if borrowed else True
                            good = restored and not report['SRAM_restore_pending']
                            mark(program_trial_worker_active=False,
                                 application_RAM_restore_pending=not restored,
                                 application_ram_restored=restored,
                                 PROGRAM_SRAM_restore_pending=report['SRAM_restore_pending'],
                                 block_snapshot=marker['block_snapshot'] if good else True,
                                 last_PROGRAM_positive_trial=str(folder / 'report.json'))
                        save()
            assert report['all_131072_SRAM_bytes_restored'] and report['owner_RAM_restored']
            report.update(passed=True, phase='PROGRAM_816E_PASSED', finished_utc=base.utc())
            save()
            print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=base.utc())
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--folder', type=Path, required=True)
    a = parser.parse_args()
    run(a.scope, a.approval, a.folder)
