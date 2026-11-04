"""Fresh relevant-bank capture for the CLOCK update; preserve owner RAM/ZP."""
import json
import re
import install_2512_native_utilities as d

t = d.t
CASE = t.ROOT / 'output/qualification/2609-CLOCK-capture-20261031-r1'


def run():
    CASE.mkdir(exist_ok=False); (CASE / '.gitignore').write_text('*\n')
    path = t.ROOT / 'output/qualification/device-operations/2609.json'
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r = dict(board='2609', passed=False, flash_writes=0, RTC_writes=0,
             SRAM_writes=0, owner_RAM_restored=False, owner_ZP_restored=False)
    def save(): t.save(CASE / 'report.json', r)
    def mark(**kw):
        m = json.loads(path.read_text()); m.update(kw); t.save(path, m)
    def rec():
        if s.context == t.MON: s.command('Q', (t.REC,))
        if s.context == d.SERVICE:
            s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC
        assert s.context == t.REC
    s = None; borrowed = False; save()
    with t.serial_lease('2609-CLOCK-relevant-bank-capture', timeout=30):
        marker = json.loads(path.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE / 'serial.jsonl').open('x') as log:
            try:
                s = d.Session(CASE, log, '2609'); s.link.send(b'\r')
                s.until((t.MON, t.REC), seconds=12); original = s.context
                if original == t.REC: s.command('B', (t.MON,))
                face = s.command('VERSION')
                slot = re.search(rb'g0000000C / MON ([AB])', face)[1].decode()
                ram,zp = s.owner()
                (CASE / 'owner-ram.bin').write_bytes(ram); (CASE / 'owner-zp.bin').write_bytes(zp)
                r.update(owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp))
                mark(clock_capture_worker_active=True, application_RAM_restore_pending=True,
                     block_snapshot=True)
                borrowed = True; rec(); t.transport.recovery_usb(s.link); s.service(reader)
                for bank in (2,3):
                    body = s.client.flash(bank)
                    assert t.sha(body) == marker['current_physical_bank_sha256'][f'B{bank}']
                    (CASE / f'B{bank}-before.bin').write_bytes(body)
                    r[f'B{bank}_sha256'] = t.sha(body)
                b3 = (CASE / 'B3-before.bin').read_bytes()
                assert b3[-4096:] == (t.REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
                r['journal'] = t.classify_journal(b3)
                print('PASS fresh 2609 B2/B3 and frozen F; restoring owner RAM', flush=True)
            finally:
                try:
                    if borrowed:
                        if s.context != d.SERVICE: rec(); s.service(reader)
                        r.update(s.client.restore_owner(ram,zp)); s.context = t.REC
                        if original == t.MON: s.command(slot,(t.MON,))
                        r['owner_RAM_restored'] = True
                finally:
                    if s is not None:
                        s.link.close(); r['COM8_released'] = True
                        r['final_prompt'] = s.context.decode().strip() if s.context else None
                    if borrowed:
                        restored = r['owner_RAM_restored'] and r['owner_ZP_restored']
                        mark(clock_capture_worker_active=False,
                             application_RAM_restore_pending=not restored,
                             application_ram_restored=restored,
                             block_snapshot=marker['block_snapshot'] if restored else True,
                             last_CLOCK_preparation=str(CASE / 'report.json'))
                    save()
    r['passed'] = r['owner_RAM_restored'] and r['owner_ZP_restored'] and 'journal' in r
    save(); print('PASS capture complete; COM8 released', flush=True)


if __name__ == '__main__': run()
