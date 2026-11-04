"""Prepared native utility installer. Default reviews the plan without a port.

--execute additionally requires a separately recorded human approval bound to
the exact plan hash. No reset, retry erase, F writer or RTC-setting command.
"""
import argparse
import json
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque

t = d.t
SCOPE = t.ROOT / 'output/qualification/2609-CLOCK-native-scope-20261031-r1'
CASE = t.ROOT / 'output/qualification/2609-CLOCK-native-install-20261031-r1'


def inputs():
    plan = json.loads((SCOPE / 'plan.json').read_text())
    assert plan['board'] == '2609' and plan['image_erases'] == 11 and plan['total_erases'] == 12
    expected = [(3,0x80),(3,0x90),(2,0x80),(2,0x90),(2,0xA0),(3,0xE0),
                (2,0xB0),(2,0xC0),(2,0xD0),(2,0xE0),(2,0xF0)]
    assert [(i['bank'],i['page']) for i in plan['targets']] == expected
    assert len(set(expected)) == 11 and (3,0xF0) not in expected
    for item in plan['targets']:
        body = (SCOPE / item['file']).read_bytes()
        assert len(body) == 4096 and t.sha(body) == item['sha256']
    freeze = json.loads((t.REPO / 'F_FREEZE.json').read_text())
    assert plan['F_sha256'] == freeze['sha256']
    for name,digest in freeze['sources'].items():
        assert t.sha((t.REPO / name).read_bytes()) == digest
    return plan


def run(execute=False):
    plan = inputs()
    if not execute:
        print('PREPARED ONLY: 2609, 11 utility erases + one C rotation; F writes0; no port opened.')
        print('Exact plan SHA256: ' + t.sha((SCOPE / 'plan.json').read_bytes()))
        return
    approval = json.loads((SCOPE / 'approval.json').read_text())
    assert approval['approved'] is True and approval['human_answer']
    assert approval['plan_sha256'] == t.sha((SCOPE / 'plan.json').read_bytes())
    CASE.mkdir(exist_ok=False); (CASE / '.gitignore').write_text('*\n')
    (CASE / 'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    t.save(CASE / 'approval.json',approval)
    marker_path = t.ROOT / 'output/qualification/device-operations/2609.json'
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer = (t.REPO / 'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    r = dict(board='2609', passed=False, image_erase_requests=0, completed=[], checks=[],
        F_writes=0, RTC_SET=0, trim_writes=0, PF_ACK=0, SRAM_writes=0,
        power_cuts=0, owner_RAM_restored=False, owner_ZP_restored=False)
    def save(): t.save(CASE / 'report.json',r)
    def mark(**kw):
        m = json.loads(marker_path.read_text()); m.update(kw); t.save(marker_path,m)
    def check(name):
        r['checks'].append(name); save(); print('PASS ' + name,flush=True)
    def rec():
        if s.context == opaque.PROMPT:
            s.link.send(b'Q\r'); s.link.until(t.REC); s.context = t.REC
        elif s.context == d.SERVICE:
            s.client.send(b'Q'); s.client.until(t.REC); s.context = t.REC
        elif s.context in (d.FT,t.CLOCK,t.WB): s.command('Q',(t.MON,)); s.command('Q',(t.REC,))
        elif s.context == t.MON: s.command('Q',(t.REC,))
        assert s.context == t.REC, 'Unknown execution state; no blind recovery command'
    s = None; borrowed = False; ram = zp = None; save()
    with t.serial_lease('2609-approved-CLOCK-native-install',timeout=30):
        marker = json.loads(marker_path.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (CASE / 'serial.jsonl').open('x') as log:
            try:
                s = d.Session(CASE,log,'2609'); s.link.send(b'\r'); s.until((t.MON,t.REC),seconds=12)
                if s.context == t.REC: s.command('B',(t.MON,))
                assert b'g0000000C / MON ' in s.command('VERSION')
                ram,zp = s.owner()
                opaque.durable_file(CASE / 'owner-ram.bin',ram)
                opaque.durable_file(CASE / 'owner-zp.bin',zp)
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
                mark(clock_install_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed = True; rec(); t.transport.recovery_usb(s.link); s.service(reader)
                old2 = s.client.flash(2); old3 = s.client.flash(3)
                assert t.sha(old2) == plan['before_B2_sha256'] and t.sha(old3) == plan['before_B3_sha256']
                opaque.durable_file(CASE / 'B2-before.bin',old2)
                opaque.durable_file(CASE / 'B3-before.bin',old3)
                check('fresh-owner-escrow-and-exact-reviewed-B2-B3-admission')
                rec(); s.load(writer,t.sha(writer),opaque.PROMPT)
                wire = opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x: print(x,flush=True))
                for item in plan['targets']:
                    before = wire.read_sector(item['bank'],item['page'])
                    assert t.sha(before) == item['before_sha256']
                    after = (SCOPE / item['file']).read_bytes()
                    r['image_erase_requests'] += 1; save(); s.context = None
                    assert not wire.replace_sector(item['bank'],item['page'],before,after)
                    s.context = opaque.PROMPT
                    assert wire.read_sector(item['bank'],item['page']) == after
                    r['completed'].append(dict(bank=item['bank'],address=item['address'],sha256=t.sha(after)))
                    check('installed-B' + str(item['bank']) + ':' + item['address'])
                rec(); s.command('B',(t.MON,))
                assert b'STATUS tools unavailable' not in s.command('VERSION')
                assert b'flags $' in s.command('TIME')
                catalogue = s.command('APPS')
                assert b'CLOCK B2:B000' in catalogue and b'FLASH B2:E000' in catalogue
                for cmd in ('M1','W'): s.command(cmd)
                opening = s.command('R CLOCK',(t.CLOCK,))
                assert b'CLOCK 1.10 / BASE1 g1' in opening and b'UTC:' in opening
                for cmd in ('HELP','TIME','STATUS','HISTORY','STATS','EUI'):
                    out = s.command(cmd)
                    assert b'Invalid command' not in out and b'Services unavailable' not in out
                    if cmd == 'STATUS':
                        assert all(x in out for x in (b'Running:',b'RTC registers (raw):',b'Trim',b'EUI:'))
                assert b'Invalid command/date' in s.command('SET 2026-02-30 12:00:00')
                for cmd in ('SET 2028-02-29 12:34:56','OFFSET +01:00','TRIM 1'):
                    s.command(cmd,(b'Type YES to confirm: ',t.CLOCK))
                    assert s.context == b'Type YES to confirm: ',cmd
                    assert b'Canceled' in s.command('NO',(t.CLOCK,))
                s.command('VERSION'); s.command('Q',(t.MON,))
                check('installed-full-CLOCK-reference-queries-cancelled-settings-and-Q')
                s.command('R FLASH',(d.FT,)); s.command('VERSION'); s.command('BANK 0')
                s.command('READ 8000'); s.command('VIEW 000')
                assert b'DEFAULT=S' in s.command('BOOT')
                s.command('BANK 3')
                for cmd in ('BYTE C000 00','ERASE D000','READ F000'):
                    assert b'REFUSED' in s.command(cmd)
                s.command('Q',(t.MON,)); check('matching-FLASH-BOOT-readonly-and-protection-on-816')
                rec(); s.service(reader)
                after2 = s.client.flash(2); after3 = s.client.flash(3)
                assert t.sha(after2) == plan['final_B2_sha256']
                expected3 = (SCOPE / 'B3-image-target.bin').read_bytes()
                assert after3[:0x4000] == expected3[:0x4000]
                assert after3[0x6000:] == expected3[0x6000:]
                assert after3[0x5000:0x5900] == old3[0x5000:0x5900]
                j = t.classify_journal(after3)
                assert j['sequence'] == plan['sequence_after'] and j['valid_records'] == plan['records_after']
                assert j['counts'] == plan['counts_after']
                for key in ('default','enabled_mask','entries','unknown_mask'): assert j[key] == plan[key]
                opaque.durable_file(CASE / 'B2-after.bin',after2)
                opaque.durable_file(CASE / 'B3-after.bin',after3)
                r.update(journal=j,NVM_verified=True,final_B2_sha256=t.sha(after2),final_B3_sha256=t.sha(after3))
                check('exact-images-golden-F-preserved-D-history-policy-and-carried-wear')
            finally:
                try:
                    if borrowed:
                        if s.context != d.SERVICE: rec(); s.service(reader)
                        r.update(s.client.restore_owner(ram,zp)); s.context = t.REC
                        r['owner_RAM_restored'] = True
                finally:
                    if s is not None: s.link.close(); r['COM8_released'] = True
                    if borrowed:
                        restored = r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields = dict(clock_install_worker_active=False,
                            application_RAM_restore_pending=not restored,application_ram_restored=restored,
                            block_snapshot=marker['block_snapshot'] if restored else True,
                            last_CLOCK_native_install=str(CASE / 'report.json'))
                        if r.get('NVM_verified'):
                            hashes = marker['current_physical_bank_sha256'].copy()
                            hashes.update(B2=r['final_B2_sha256'],B3=r['final_B3_sha256'])
                            fields.update(current_physical_bank_sha256=hashes,service_generation='00000009',
                                native_utility_profile='CLOCK1.10/FLASHg1r16/WB2gB/SP1g2',
                                final_prompt='REC>',clock_native_installation_complete=restored)
                            counts = marker.get('current_tracked_erase_counts',{}).copy()
                            for bank in range(4):
                                for sector in range(8): counts[f'B{bank}:{sector+8:X}'] = j['counts'][bank*8+sector]
                            for letter,index in zip('ABCDEF',range(26,32)): counts[letter] = j['counts'][index]
                            fields['current_tracked_erase_counts'] = counts
                        mark(**fields)
                    save()
    r['passed'] = r.get('NVM_verified',False) and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save(); print(json.dumps(r,indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    run(parser.parse_args().execute)
