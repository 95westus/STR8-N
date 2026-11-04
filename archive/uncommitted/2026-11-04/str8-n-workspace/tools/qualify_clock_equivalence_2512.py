"""Compare installed CLOCK with the live 2205 reference; cancel all changes."""
import json
import re
import install_2512_native_utilities as d

t = d.t
CASE = t.ROOT / 'output/qualification/2512-CLOCK-equivalence-20261031-r1'


def run():
    CASE.mkdir(exist_ok=False)
    (CASE / '.gitignore').write_text('*\n')
    r = dict(board='2512', passed=False, checks=[], F_writes=0, flash_writes=0,
             journal_writes=0, SRAM_writes=0, RTC_SET=0, trim_writes=0,
             PF_ACK=0, owner_RAM_restored=False)
    marker_path = t.ROOT / 'output/qualification/device-operations/2512.json'
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    s = None
    borrowed = False
    ram = zp = None
    def save(): t.save(CASE / 'report.json', r)
    def mark(**kw):
        m = json.loads(marker_path.read_text()); m.update(kw); t.save(marker_path, m)
    def check(name):
        r['checks'].append(name); save(); print('PASS ' + name, flush=True)
    def rec():
        if s.context == t.CLOCK: s.command('Q', (t.MON,))
        if s.context == t.MON: s.command('Q', (t.REC,))
        if s.context == d.SERVICE:
            s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC
        assert s.context == t.REC
    save()
    with t.serial_lease('2512-CLOCK-reference-equivalence', timeout=30):
        marker = json.loads(marker_path.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE / 'serial.jsonl').open('x') as log:
            try:
                s = d.Session(CASE, log, '2512'); s.link.send(b'\r')
                s.until((t.MON, t.REC), seconds=12); original = s.context
                if original == t.REC: s.command('B', (t.MON,))
                face = s.command('VERSION')
                slot = re.search(rb'g0000000C / MON ([AB])', face)[1].decode()
                ram, zp = s.owner()
                (CASE / 'owner-ram.bin').write_bytes(ram)
                (CASE / 'owner-zp.bin').write_bytes(zp)
                r.update(owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp))
                mark(clock_equivalence_worker_active=True, application_RAM_restore_pending=True,
                     block_snapshot=True)
                borrowed = True
                rec(); t.transport.recovery_usb(s.link); s.service(reader)
                before = s.client.flash(3)
                (CASE / 'B3-before.bin').write_bytes(before)
                known = (t.ROOT / 'output/qualification/STATUS-install-20261031-r1/2512/B3-after.bin').read_bytes()
                assert before == known, 'Existing stage-zero metadata and installed context must match'
                rec(); s.command(slot, (t.MON,))
                opening = s.command('R CLOCK', (t.CLOCK,))
                (CASE / 'CLOCK-opening.txt').write_bytes(opening)
                assert b'CLOCK 1.10 / BASE1 g1' in opening
                assert b'Board: 2512' in opening and b'Local:' in opening and b'UTC:' in opening
                check('named-CLOCK-1.10-opens-with-rich-summary')
                helptext = s.command('HELP')
                for token in (b'SET ', b'OFFSET ', b'TRIM ', b'ACK', b'ACCEPT EUI', b'CLEAR', b'BATTERY'):
                    assert token in helptext
                for cmd in ('TIME', 'STATUS', 'HISTORY', 'STATS', 'EUI', 'OFFSET', 'BATTERY'):
                    out = s.command(cmd)
                    (CASE / (cmd + '.txt')).write_bytes(out)
                    assert b'Invalid command' not in out and b'Services unavailable' not in out
                    if cmd == 'TIME': assert b'Local:' in out and b'UTC:' in out
                    if cmd == 'STATUS':
                        assert all(x in out for x in (b'Oscillator start:', b'Running:',
                            b'Calendar valid:', b'Backup enabled:', b'Power-fail latched:',
                            b'RTC registers (raw):', b'Trim', b'EUI:'))
                check('2205-query-command-set-and-detailed-status')
                assert b'Invalid command/date' in s.command('SET 2026-02-30 12:00:00')
                for cmd in ('SET 2028-02-29 12:34:56', 'OFFSET +00:00', 'TRIM 1'):
                    out = s.command(cmd, (b'Type YES to confirm: ', t.CLOCK))
                    assert s.context == b'Type YES to confirm: ', cmd
                    out = s.command('NO', (t.CLOCK,))
                    assert b'Canceled' in out, (cmd, out)
                check('invalid-date-refusal-and-SET-OFFSET-TRIM-cancellation')
                s.command('VERSION')
                s.command('Q', (t.MON,))
                assert b'flags $' in s.command('TIME')
                check('VERSION-and-quiet-Q-monitor-return')
                rec(); s.service(reader)
                after = s.client.flash(3)
                assert after == before
                (CASE / 'B3-after.bin').write_bytes(after)
                check('F-boot-wear-metadata-and-provider-byte-identical')
            finally:
                try:
                    if borrowed:
                        if s.context != d.SERVICE: rec(); s.service(reader)
                        r.update(s.client.restore_owner(ram, zp)); s.context = t.REC
                        if original == t.MON: s.command(slot, (t.MON,))
                        r['owner_RAM_restored'] = True
                finally:
                    if s is not None:
                        s.link.close(); r['COM4_released'] = True
                    if borrowed:
                        restored = r['owner_RAM_restored'] and r.get('owner_ZP_restored', False)
                        mark(clock_equivalence_worker_active=False,
                             application_RAM_restore_pending=not restored,
                             application_ram_restored=restored,
                             block_snapshot=marker['block_snapshot'] if restored else True,
                             last_CLOCK_equivalence=str(CASE / 'report.json'))
                    save()
    r['passed'] = len(r['checks']) == 5 and r['owner_RAM_restored']
    save(); print(json.dumps(r, indent=2), flush=True)


if __name__ == '__main__': run()
