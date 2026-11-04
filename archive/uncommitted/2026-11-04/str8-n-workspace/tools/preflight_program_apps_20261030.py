"""Fresh no-storage-write admission for 2512 PROGRAM and 2609 AP/02 trials."""
import argparse
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t


class Session(t.Session):
    def __init__(self, folder, log, board):
        self.folder, self.context, self.counter = folder, None, 0
        self.board = board
        port, usb = ('COM4', 'A10MQFLCA') if board == '2512' else ('COM8', 'A10MPQXCA')
        self.link = t.transport.RecoveryLink(port, log, usb_serial=usb)
        self.client = None

    def monitor(self):
        if self.context == t.PB:
            self.link.send(b'Q'); self.until((t.MON,))
        if self.context == t.CLOCK: self.command('Q', (t.MON,))
        if self.context == t.WB: self.command('Q', (t.MON,))
        if self.context == t.REC:
            face = self.command('B', (t.MON,))
            cpu = b'CPU $02' if self.board == '2512' else b'CPU $16'
            assert b'g00000008 / MON B' in face and cpu in face
        assert self.context == t.MON


def run(board, folder):
    folder = folder.resolve()
    assert folder.is_relative_to(t.ROOT / 'output/qualification') and not folder.exists()
    marker_path = t.ROOT / f'output/qualification/device-operations/{board}.json'
    original = t.MON if board == '2512' else t.REC
    port = 'COM4' if board == '2512' else 'COM8'
    report = dict(board=board, CPU='65C02' if board == '2512' else '65C816 emulation',
        passed=False, started_utc=t.utc(), flash_writes=0, journal_writes=0, SRAM_data_writes=0,
        WORKSPACE_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0, power_cuts=0,
        firmware_builds=0, owner_RAM_restored=False, original_context=original.decode())
    folder.mkdir(parents=True); (folder / '.gitignore').write_text('*\n')
    (folder / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    s = None; borrowed = False; marker = None; ram = zp = None
    def save(): t.save(folder / 'report.json', report)
    def mark(**fields):
        m = json.loads(marker_path.read_text()); m.update(fields); t.save(marker_path, m)
    def check(label):
        report.setdefault('checks', []).append(label); save(); print('PASS ' + label, flush=True)
    save()
    try:
        with t.serial_lease(board + '-PROGRAM-APPS-readonly-admission', timeout=30):
            marker = json.loads(marker_path.read_text())
            assert not marker['block_snapshot'] and marker['application_ram_restored']
            assert not marker['application_RAM_restore_pending']
            assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
            hashes = [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
            reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
            assert t.sha(reader) == t.live.READBACK_SHA256
            if board == '2609':
                import rtc_monb8_2609 as qualified
                admission = qualified.inputs()
                assert admission[-1] == hashes
                authority_ram, authority_zp = admission[3]['owner-ram.bin'], admission[3]['owner-zp.bin']
                t.save(folder / 'escrow-authority.json', admission[2])
            else:
                _, _, _, fixture = t.inputs()
            t.save(folder / 'marker-before.json', marker)
            report['bank_sha256'] = hashes
            with (folder / 'serial.jsonl').open('x') as log:
                try:
                    s = Session(folder, log, board)
                    s.link.send(b'\r'); s.until((original,), seconds=12)
                    s.monitor()
                    face = s.command('V')
                    assert b'g00000008 / MON B' in face
                    ram, zp = s.owner(); assert s.owner() == (ram, zp)
                    if board == '2609': assert (ram, zp) == (authority_ram, authority_zp)
                    (folder / 'owner-ram.bin').write_bytes(ram); (folder / 'owner-zp.bin').write_bytes(zp)
                    report.update(owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp), native_prehelper_double_escrow=True)
                    check('fresh-native-owner-RAM-ZP-double-escrow')
                    mark(feature_preflight_worker_active=True, application_RAM_restore_pending=True, block_snapshot=True)
                    borrowed = True
                    s.rec(); t.transport.recovery_usb(s.link); s.service(reader)
                    assert s.client.read(b'M', 0x6500) == reader + ram[len(reader):]
                    assert s.client.read(b'Z', 0xe0) == zp
                    s.read_banks('before', hashes)
                    journal = t.classify_journal((folder / 'before-pass1-B3.bin').read_bytes())
                    t.save(folder / 'journal.json', journal); report['journal'] = journal
                    check('all-four-flash-banks-double-admitted')
                    if board == '2512':
                        s.client.restore_owner(ram, zp); s.context = t.REC; s.monitor()
                        out = s.command('MAINT LOAD', (t.WB, t.MON))
                        assert s.context == t.WB and b'WORKBENCH WB2 g00000005' in out
                        s.mount()
                        table = s.command('T P'); (folder / 'PROGRAM-table.txt').write_bytes(table)
                        data = s.sram(fixture, 'SRAM-fresh')
                        old = (t.ROOT / 'output/qualification/2512-services-g4-RAM-20261030-r2/SRAM-after-131072.bin').read_bytes()
                        assert data == old, 'Live SRAM changed; do not admit stale test targets'
                        layout = t.inspect_sram(data)
                        assert all(r.get('payload_CRC_valid', True) for r in layout['records'])
                        t.save(folder / 'PROGRAM-layout.json', layout)
                        report.update(full_SRAM_fresh_equal_latest_preserved=True, SRAM_sha256=t.sha(data),
                            PROGRAM_format=layout['format'], PROGRAM_boundary=layout['boundary'])
                        check('fresh-complete-SRAM-matches-latest-preserved-image')
                        s.rec(); s.service(reader)
                    s.read_banks('after', hashes)
                    report['all_flash_banks_unchanged'] = True
                finally:
                    try:
                        if borrowed:
                            if s.context != b'RAM SERVICE BASE1> ': s.rec(); s.service(reader)
                            restored = s.client.restore_owner(ram, zp)
                            report.update({k:v for k,v in restored.items() if k not in ('owner_RAM_restored','owner_ZP_restored')})
                            s.context = t.REC; s.monitor(); assert s.owner() == (ram, zp)
                            report.update(owner_RAM_restored=True, owner_ZP_restored=True)
                        if s is not None and original == t.REC: s.rec()
                    finally:
                        if s is not None:
                            s.link.close(); report[port + '_released'] = True
                            report['final_context'] = s.context.decode() if s.context else None
                        if marker is not None:
                            restored = report['owner_RAM_restored'] if borrowed else True
                            mark(feature_preflight_worker_active=False, application_RAM_restore_pending=not restored,
                                application_ram_restored=restored, block_snapshot=marker['block_snapshot'] if restored else True,
                                last_feature_readonly_preflight=str(folder / 'report.json'))
                        save()
        assert report['owner_RAM_restored'] and report['all_flash_banks_unchanged']
        report.update(passed=True, phase='READONLY_ADMISSION_PASSED', finished_utc=t.utc()); save()
        print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        report.update(error=repr(error), finished_utc=t.utc()); save(); raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', choices=['2512','2609'], required=True)
    parser.add_argument('--folder', type=Path, required=True)
    args=parser.parse_args(); run(args.board, args.folder)
