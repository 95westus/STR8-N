"""Host-only utility packaging and bounded 2512 capture/retirement workflow."""
import argparse
import binascii
import json
import re
import sys
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque

t = d.t
ROOT = t.ROOT
Q = ROOT / 'output/qualification'
MONS = tuple(f'B{n}> '.encode() for n in range(4))
MARK = Q / 'device-operations/2512.json'
sys.path.insert(0, str(t.REPO / 'tools'))
from journal_rotation_plan import reserve
from status_extents import assert_preserved


class Session(d.Session):
    def monitor(self):
        if self.context == t.PB:
            self.link.send(b'Q'); self.until(MONS)
        if self.context in (t.WB, t.CLOCK, d.FT, b'BM> '):
            self.command('Q', MONS)
        if self.context == d.SERVICE:
            self.client.send(b'Q'); self.client.until(t.REC); self.context = t.REC
        if self.context == opaque.PROMPT:
            self.link.send(b'Q\r'); self.link.until(t.REC); self.context = t.REC
        if self.context == t.REC:
            self.command('B', MONS)
        assert self.context in MONS
        if self.context != t.MON:
            self.command('B3', MONS)

    def rec(self):
        if self.context == d.SERVICE:
            self.client.send(b'Q'); self.client.until(t.REC); self.context = t.REC
        elif self.context == opaque.PROMPT:
            self.link.send(b'Q\r'); self.link.until(t.REC); self.context = t.REC
        elif self.context != t.REC:
            self.monitor(); self.command('Q', (t.REC,))


def capture(folder):
    folder.mkdir(exist_ok=False)
    (folder / '.gitignore').write_text('*\n')
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report = dict(board='2512', passed=False, flash_writes=0, SRAM_writes=0,
                  owner_RAM_restored=False, owner_ZP_restored=False)
    s = None; ram = zp = prefix = None; borrowed = False
    def save(): t.save(folder / 'report.json', report)
    def mark(**fields):
        state = json.loads(MARK.read_text()); state.update(fields); t.save(MARK, state)
    save()
    with t.serial_lease('2512-requested-FLASH-MAINT-retirement-capture', timeout=30):
        marker = json.loads(MARK.read_text())
        assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
        assert not marker['block_snapshot']
        assert not any(v for k, v in marker.items() if k.endswith('_worker_active'))
        t.save(folder / 'marker-before.json', marker)
        with (folder / 'serial.jsonl').open('x') as log:
            try:
                s = Session(folder, log, '2512'); s.link.send(b'\r')
                s.until(MONS + (t.REC,), seconds=12); s.monitor()
                face = s.command('VERSION'); (folder / 'VERSION.txt').write_bytes(face)
                assert b'CPU: 65C02' in face and b'BASE1/PR05' in face
                prefix = s.dump(0x200, 0x1ff + len(reader)); zp = s.dump(0, 0xdf)
                opaque.durable_file(folder / 'owner-prefix.bin', prefix)
                opaque.durable_file(folder / 'owner-zp.bin', zp)
                mark(utility_retirement_worker_active=True, application_RAM_restore_pending=True, block_snapshot=True)
                borrowed = True; s.rec(); s.service(reader)
                memory = s.client.read(b'M', 0x6500)
                assert memory[:len(reader)] == reader
                ram = prefix + memory[len(reader):]
                opaque.durable_file(folder / 'owner-ram.bin', ram)
                for bank in range(4):
                    data = s.client.flash(bank)
                    assert t.sha(data) == marker['current_physical_bank_sha256'][f'B{bank}']
                    opaque.durable_file(folder / f'B{bank}-before.bin', data)
                report['journal'] = t.classify_journal((folder / 'B3-before.bin').read_bytes())
                s.client.restore_owner(ram, zp); s.context = t.REC; s.monitor()
                s.command('MAINT LOAD', (t.WB,)); s.mount()
                table = s.command('TABLE P'); (folder / 'PROGRAM-table.txt').write_bytes(table)
                # Use installed SRAM READ for directory inventory. No helper or
                # temporary SPI allocation is needed when neither name exists.
                blocks = bytearray()
                for address in range(0, 0x240, 64):
                    face = s.command(f'SRAM READ 0 {address:04X}')
                    match = re.search(rb'RAW64 ((?:[0-9A-F]{2} ){63}[0-9A-F]{2})', face)
                    assert match, face
                    blocks.extend(bytes.fromhex(match[1].decode()))
                (folder/'PROGRAM-directory.bin').write_bytes(blocks)
                assert all(name not in table for name in (b' FLASH', b' MAINT'))
                report['PROGRAM_inventory'] = 'Primary header and all eight directory slots; no FLASH/MAINT records'
                report['passed'] = True
            finally:
                try:
                    if borrowed:
                        s.rec(); s.service(reader)
                        if ram is None:
                            memory = s.client.read(b'M', 0x6500)
                            assert memory[:len(reader)] == reader
                            ram = prefix + memory[len(reader):]
                        report.update(s.client.restore_owner(ram, zp)); s.context = t.REC
                finally:
                    if s: s.link.close(); report['port_released'] = True
                    if borrowed:
                        restored = report['owner_RAM_restored'] and report['owner_ZP_restored']
                        mark(utility_retirement_worker_active=False, application_RAM_restore_pending=not restored,
                             application_ram_restored=restored, block_snapshot=not restored,
                             last_utility_retirement_capture=str(folder / 'report.json'), final_prompt='REC>')
                    save()
    assert report['passed'] and report['owner_RAM_restored'] and report['owner_ZP_restored']
    print('PASS fresh flash/SPI inventory; owner RAM/ZP restored; COM4 released', flush=True)


def recover(folder):
    """Restore existing escrow only after independently observing idle MON."""
    ram = (folder / 'owner-ram.bin').read_bytes()
    zp = (folder / 'owner-zp.bin').read_bytes()
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    with t.serial_lease('2512-utility-inventory-owner-RAM-recovery', timeout=30):
        with (folder / 'recovery-serial.jsonl').open('x') as log:
            s = Session(folder, log, '2512')
            try:
                s.link.send(b'\r'); s.until(MONS, seconds=12)
                s.monitor(); face = s.command('VERSION')
                assert b'STR8-N MON B  gen 00000010' in face
                s.rec(); s.service(reader)
                assert t.sha(s.client.flash(3)) == json.loads((folder/'marker-before.json').read_text())['current_physical_bank_sha256']['B3']
                result = s.client.restore_owner(ram, zp); s.context = t.REC
                assert result['owner_RAM_restored'] and result['owner_ZP_restored']
                t.save(folder/'recovery.json', result)
                marker = json.loads(MARK.read_text())
                marker.update(utility_retirement_worker_active=False, application_RAM_restore_pending=False,
                              application_ram_restored=True, block_snapshot=False, final_prompt='REC>')
                t.save(MARK, marker)
                print('PASS original RAM/ZP restored after reader refusal; no storage writes', flush=True)
            finally:
                s.link.close()


def plan(folder, source):
    """Remove utility bodies, retaining shared transfer and STATUS services."""
    folder.mkdir(exist_ok=False); (folder/'.gitignore').write_text('*\n')
    before = {b: (source/f'B{b}-before.bin').read_bytes() for b in range(4)}
    marker = json.loads((source/'marker-before.json').read_text())
    assert all(t.sha(v) == marker['current_physical_bank_sha256'][f'B{b}'] for b,v in before.items())
    images = {b: bytearray(v) for b,v in before.items()}
    assert before[1][:8] == b'RP\x01\x02PR05'
    assert before[2][0x6000:0x6008] == b'RP\x01\x01PR05'
    assert t.sha(before[0][:4096]) == marker['FLASH_installed']['sha256']
    images[0][:4096] = b'\xff'*4096
    images[1][:0x3000] = b'\xff'*0x3000
    base = ROOT/'BUILD/storage-installed-auto-r2'
    mf = json.loads((base/'manifest.json').read_text())
    def seal(data, length):
        data = data.ljust(length-2, b'\xff')
        return data+binascii.crc_hqx(data,65535).to_bytes(2,'big')
    # These are shared MON STORE/RESTORE/S19 services, not utility bodies.
    for name, offset, used, length in (
        ('FLASH-GATE-7300.bin',0x2380,0x259a-0x2300,1024),
        ('FLASH-RECORD-6B00.bin',0x27c0,0x729e-0x6b00,2048)):
        raw = (base/name).read_bytes()
        assert t.sha(raw) == mf['artifacts'][name]['sha256']
        assert before[1][offset:offset+used] == raw[:used]
        images[1][offset:offset+length] = seal(raw[:used],length)
    images[2][0x6000:0x7a50] = b'\xff'*0x1a50
    # Remove the obsolete FLASH seal/footer; STATUS ends immediately before it.
    images[2][0x7ffa:] = b'\xff'*6
    service=bytearray(before[3][0x6000:0x7000])
    for old,new in (
        (b'R CLOCK/FLASH/MAINT; EDU SRAM WORK',b'R CLOCK; FLASH/MAINT: RAM BIN'),
        (b'B1:8-A MAINT,B-D SRAM; B2 tools.',b'B1:A xfer,B-D SRAM; B2 tools.')):
        assert service.count(old)==1 and len(new)<=len(old)
        service=service.replace(old,new.ljust(len(old),b' '))
    service[-2:]=binascii.crc_hqx(service[:-2],65535).to_bytes(2,'big')
    assert binascii.crc_hqx(service,65535)==0
    images[3][0x6000:0x7000]=service
    assert_preserved(before[2], bytes(images[2]))
    assert images[0][4096:] == before[0][4096:]
    assert images[1][0x3000:] == before[1][0x3000:]
    assert images[2][:0x6000] == before[2][:0x6000]
    state = before[3]; targets=[]; operations=[]
    for bank,page in ((0,0x80),(1,0x80),(1,0x90),(1,0xa0),(2,0xe0),(2,0xf0),(3,0xe0)):
        off = (page-0x80)*256
        old = before[bank][off:off+4096]; new = bytes(images[bank][off:off+4096])
        assert old != new
        name = f'B{bank}-{page:02X}-target.bin'; (folder/name).write_bytes(new)
        (folder/f'B{bank}-{page:02X}-original.bin').write_bytes(old)
        state,op = reserve(state,bank*8+(page-0x80)//16); operations.append(op)
        if bank==3:
            revised=bytearray(state);revised[off:off+4096]=new;state=bytes(revised)
        targets.append(dict(bank=bank,page=page,file=name,address=f'B{bank}:{page:02X}00',
                            before_sha256=t.sha(old),sha256=t.sha(new)))
    images[3] = bytearray(state)
    prior=t.classify_journal(before[3]); after=t.classify_journal(state)
    for key in ('default','enabled_mask','entries','unknown_mask'):
        assert prior[key] == after[key]
    for b,data in images.items(): (folder/f'B{b}-target.bin').write_bytes(data)
    result=dict(board='2512',source=str(source),authorization='User requested removal of FLASH and MAINT from any storage on 2512',
                targets=targets,operations=operations,component_erases=7,
                journal_erases=sum(len(op['journal_sector_erases']) for op in operations),
                fully_reclaimed_sectors=['B0:8','B1:8','B1:9','B2:E'],fully_reclaimed_bytes=16384,
                retained_shared_services={'B1:A':'MON transfer gate and record worker; dense FLASH fragments removed',
                                          'B2:F':'STATUS FA50-FFF9'},
                before_bank_sha256={f'B{b}':t.sha(v) for b,v in before.items()},
                after_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},
                journal_before=prior,journal_after=after,F_writes=0,MON_writes=0,
                SPI_writes=0,other_boards_accessed=[])
    t.save(folder/'plan.json',result)
    print('PLANNED seven component erases (including APPS/map text) +', result['journal_erases'], 'journal erases; 16 KB fully reclaimed',flush=True)


def trial(folder):
    import devtools_2512_session as ds
    import trial_flash_transfer_readonly as ro
    package = ROOT/'firmware/ram-tools/flash-g2'
    mf=json.loads((package/'manifest.json').read_text()); packet=(package/'FLASH.bin').read_bytes()
    assert t.sha(packet)==mf['sha256']
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,
           RTC_SET=0,trim_writes=0,PF_ACK=0,owner_RAM_restored=False,owner_ZP_restored=False)
    with ds.escrow(folder,r,'2512-requested-standalone-FLASH-RAM-trial',window=30,cache_first=0x6b00,cache_end=0x77ff) as x:
        s=x.s
        x.wb(); table=x.cmd('TABLE P');(folder/'PROGRAM-table.txt').write_bytes(table)
        assert b' FLASH' not in table and b' MAINT' not in table
        directory=bytearray()
        for address in range(0,0x240,64): directory.extend(x.raw(address))
        (folder/'PROGRAM-directory.bin').write_bytes(directory)
        r['checks'].append('all-PROGRAM-directory-slots-no-FLASH-or-MAINT')
        x.rec();s.load(packet,t.sha(packet),ro.FT)
        assert b'FLASH g2' in x.cmd('VERSION')
        assert b'I first last' in x.cmd('?')
        x.cmd('BANK 0');x.cmd('READ 8000');view=x.cmd('VIEW 000');assert b'0000' in view
        assert b'REFUSED' in x.cmd('I 9001 9FFF')
        x.cmd('I 9000 9FFF',(ro.YES,));assert b'Canceled' in x.cmd('NO',(ro.FT,))
        r['checks'].append('standalone-FLASH-version-help-read-dense-library-guards-and-NO')
        x.cmd('Q',MONS+(t.REC,));x.mon()
        assert b'STR8-N MON B  gen 00000010' in x.cmd('VERSION')
        r['checks'].append('Q-through-public-F-reset-returns-saved-MON-B')
        # Compare every flash bank after the trial, including journal bytes.
        x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
        for b in range(4):
            body=s.client.flash(b);assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}']
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC
        r['checks'].append('all-four-flash-banks-exact-no-writes')
    r['passed']=all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released')) and len(r['checks'])==4
    t.save(folder/'report.json',r);assert r['passed']
    print('PASS standalone FLASH and PROGRAM inventory; all flash unchanged; RAM/ZP/cache restored',flush=True)


def execute(folder, source):
    import devtools_2512_session as ds
    import trial_flash_transfer_readonly as ro
    p=json.loads((source/'plan.json').read_text())
    proof=Q/'2512-loadable-FLASH-trial-20261102-r1/report.json'
    assert json.loads(proof.read_text())['passed']
    assert p['board']=='2512' and len(p['targets'])==7 and p['journal_erases']==1
    assert all((target['bank'],target['page']) not in ((3,0xa0),(3,0xb0),(3,0xc0),(3,0xd0),(3,0xf0)) for target in p['targets'])
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    package=ROOT/'firmware/ram-tools/flash-g2'
    packet=(package/'FLASH.bin').read_bytes();mf=json.loads((package/'manifest.json').read_text());assert t.sha(packet)==mf['sha256']
    before={b:(Path(p['source'])/f'B{b}-before.bin').read_bytes() for b in range(4)}
    r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,automatic_retries=0,
           F_writes=0,MON_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
           owner_RAM_restored=False,owner_ZP_restored=False,plan_sha256=t.sha((source/'plan.json').read_bytes()))
    try:
      with ds.escrow(folder,r,'2512-user-requested-FLASH-MAINT-retirement',window=180,cache_first=0x6b00,cache_end=0x77ff,lease_timeout=300) as x:
        s=x.s;t.save(folder/'plan.json',p)
        (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
        assert x.original['current_physical_bank_sha256']==p['before_bank_sha256']
        for b in range(4):
            actual=s.client.flash(b);assert actual==before[b]
            opaque.durable_file(folder/f'B{b}-before.bin',actual)
        # Establish both replacement tools before removing resident copies.
        maint=(package/'MAINT-RO.bin').read_bytes();assert t.sha(maint)==mf['MAINT_RO_sha256']
        x.rec();s.load(maint,t.sha(maint),b'MAINT RO> ')
        assert b'No write' in x.cmd('?')
        x.cmd('Q',MONS+(t.REC,));x.mon();r['host_MAINT_preflight']=True
        r['write_phase_started']=True;x.save()
        x.mark(utility_retirement_pending=True,utility_retirement_write_worker_active=True)
        x.rec();s.load(writer,t.sha(writer),opaque.PROMPT)
        wire=opaque.Wire(s.link.serial,timeout=90,progress=lambda line: print(line,flush=True))
        for target in p['targets']:
            bank,page=target['bank'],target['page']
            old=wire.read_sector(bank,page);assert t.sha(old)==target['before_sha256']
            body=(source/target['file']).read_bytes();assert t.sha(body)==target['sha256']
            r['erase_requests']+=1;x.save();s.context=None
            assert not wire.replace_sector(bank,page,old,body)
            s.context=opaque.PROMPT
            actual=wire.read_sector(bank,page);assert actual==body
            opaque.durable_file(folder/f'B{bank}-{page:02X}-after.bin',actual)
            r['completed'].append(target['address']);x.save()
            print('VERIFIED removal '+target['address'],flush=True)
        x.rec();s.service(reader)
        for b in range(4):
            actual=s.client.flash(b)
            assert t.sha(actual)==p['after_bank_sha256'][f'B{b}']
            opaque.durable_file(folder/f'B{b}-after.bin',actual)
        x.expected_b3_sha256=p['after_bank_sha256']['B3']
        r['NVM_verified']=True;r['checks'].append('all-four-banks-exact-including-planned-journal-rotation')
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC;x.mon()
        face=x.cmd('VERSION');assert b'Board: 2512' in face and b'Battery:' in face and b'unavailable' not in face
        apps=x.cmd('APPS');assert b'FLASH/MAINT: RAM BIN' in apps
        assert b'B1:A xfer' in x.cmd('M2')
        r['checks'].append('STATUS-and-component-advertisements-correct')
        # Shared MON transfer services remain callable after utility retirement.
        x.cmd('STORE 0 9000 5800 66FF RETIRENO',(ro.STORE_YES,))
        s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS)
        from trial_s19_ram import READY
        x.cmd('S19',(READY,));s.link.send(b'\x03');assert b'S19 stopped $03' in s.until(MONS)
        r['checks'].append('shared-STORE-NO-and-S19-Ctrl-C-retained')
        x.wb();table=x.cmd('TABLE P');assert b' FLASH' not in table and b' MAINT' not in table
        directory=bytearray()
        for address in range(0,0x240,64):directory.extend(x.raw(address))
        assert bytes(directory)==(proof.parent/'PROGRAM-directory.bin').read_bytes()
        (folder/'PROGRAM-directory-after.bin').write_bytes(directory)
        r['checks'].append('all-PROGRAM-directory-bytes-unchanged-no-utility-records')
        x.rec();s.load(packet,t.sha(packet),ro.FT)
        assert b'FLASH g2' in x.cmd('VERSION')
        x.cmd('BANK 0');x.cmd('READ 8000');assert b'FF FF FF FF' in x.cmd('VIEW 000')
        x.cmd('I 9000 9FFF',(ro.YES,));assert b'Canceled' in x.cmd('NO',(ro.FT,))
        x.cmd('Q',MONS+(t.REC,));x.mon()
        r['checks'].append('standalone-FLASH-works-after-all-stored-copies-removed')
        # Verify the read-only maintenance BIN remains loadable from the host.
        maint=(package/'MAINT-RO.bin').read_bytes();assert t.sha(maint)==mf['MAINT_RO_sha256']
        x.rec();s.load(maint,t.sha(maint),b'MAINT RO> ')
        assert b'No write' in x.cmd('?')
        x.cmd('Q',MONS+(t.REC,));x.mon()
        r['checks'].append('host-MAINT-RO-still-loadable')
        x.rec();s.service(reader)
        for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC
      r['passed']=r.get('NVM_verified') and len(r['checks'])==6 and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
      assert r['passed']
    finally:
      if folder.exists():
        t.save(folder/'report.json',r)
      if r.get('write_phase_started'):
        marker=json.loads(MARK.read_text())
        marker.update(utility_retirement_write_worker_active=False,utility_retirement_pending=not r['passed'],block_snapshot=not r['passed'])
        if r['passed']:
            counts=marker['current_tracked_erase_counts'].copy()
            for i,value in enumerate(p['journal_after']['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
            for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['journal_after']['counts'][i]
            marker.update(current_physical_bank_sha256=p['after_bank_sha256'],current_tracked_erase_counts=counts,
                          current_wear_counts=p['journal_after']['counts'],current_journal_sequence=p['journal_after']['sequence'],
                          current_journal_valid_records=p['journal_after']['valid_records'],current_valid_journal_records=p['journal_after']['valid_records'],
                          FLASH_installed=False,bank_maint_installed=False,flash_utility_installed=False,
                          FLASH_residency='Host-loaded RAM BIN',MAINT_residency='Host-loaded RAM BIN',
                          shared_MON_transfer_services_retained=True,last_utility_retirement=str(folder/'report.json'),
                          utility_removal_policy_other_boards='Apply when each board is next migrated; not performed here')
        t.save(MARK,marker)
    print('PASS FLASH/MAINT retired; 16 KB fully reclaimed; shared services retained; RAM/ZP/cache restored',flush=True)


def verified_inventory(p, complete, receipt):
    marker=json.loads(MARK.read_text());counts=marker['current_tracked_erase_counts'].copy()
    for i,value in enumerate(p['journal_after']['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
    for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['journal_after']['counts'][i]
    marker.update(current_physical_bank_sha256=p['after_bank_sha256'],current_tracked_erase_counts=counts,
                  current_wear_counts=p['journal_after']['counts'],current_journal_sequence=p['journal_after']['sequence'],
                  current_journal_valid_records=p['journal_after']['valid_records'],current_valid_journal_records=p['journal_after']['valid_records'],
                  FLASH_installed=False,bank_maint_installed=False,flash_utility_installed=False,
                  FLASH_residency='Host-loaded RAM BIN',MAINT_residency='Host-loaded RAM BIN',
                  shared_MON_transfer_services_retained=True,last_utility_retirement=str(receipt),
                  utility_removal_policy_other_boards='Apply when each board is next migrated; not performed here',
                  utility_retirement_write_worker_active=False,utility_retirement_pending=not complete,block_snapshot=not complete)
    t.save(MARK,marker)


def verify(folder, source):
    """Continue functional checks after exact completed retirement; no erases."""
    import devtools_2512_session as ds
    import trial_flash_transfer_readonly as ro
    p=json.loads((source/'plan.json').read_text())
    installed=Q/'2512-utility-retired-20261102-r2'
    prior=json.loads((installed/'report.json').read_text())
    assert prior['NVM_verified'] and prior['erase_requests']==7 and len(prior['completed'])==7
    assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['provider_cache_restored']
    for b in range(4):assert t.sha((installed/f'B{b}-after.bin').read_bytes())==p['after_bank_sha256'][f'B{b}']
    with t.serial_lease('2512-record-already-verified-retirement-state',timeout=30):
        marker=json.loads(MARK.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        assert marker['current_physical_bank_sha256'] in (p['before_bank_sha256'],p['after_bank_sha256'])
        verified_inventory(p,False,installed/'report.json')
    package=ROOT/'firmware/ram-tools/flash-g2';mf=json.loads((package/'manifest.json').read_text())
    packet=(package/'FLASH.bin').read_bytes();assert t.sha(packet)==mf['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,
           component_erases_already_completed=7,journal_erases_already_completed=1,
           original_write_receipt=str(installed/'report.json'),plan_sha256=t.sha((source/'plan.json').read_bytes()))
    with ds.escrow(folder,r,'2512-retirement-final-readonly-functional-checks',window=180,cache_first=0x6b00,cache_end=0x77ff,lease_timeout=300) as x:
        s=x.s
        for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
        r['checks'].append('all-four-banks-exact-including-planned-journal-rotation')
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC;x.mon()
        face=x.cmd('VERSION');assert b'Board: 2512' in face and b'Battery:' in face and b'unavailable' not in face
        assert b'FLASH/MAINT: RAM BIN' in x.cmd('APPS')
        assert b'B1:A xfer' in x.cmd('M2')
        r['checks'].append('STATUS-and-component-advertisements-correct')
        x.cmd('STORE 0 9000 5800 66FF RETIRENO',(ro.STORE_YES,))
        s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS)
        from trial_s19_ram import READY
        x.cmd('S19',(READY,));s.link.send(b'\x03');assert b'S19 stopped $03' in s.until(MONS)
        r['checks'].append('shared-STORE-NO-and-S19-Ctrl-C-retained')
        x.wb();table=x.cmd('TABLE P');assert b' FLASH' not in table and b' MAINT' not in table
        directory=bytearray()
        for address in range(0,0x240,64):directory.extend(x.raw(address))
        assert bytes(directory)==(Q/'2512-loadable-FLASH-trial-20261102-r1/PROGRAM-directory.bin').read_bytes()
        (folder/'PROGRAM-directory-after.bin').write_bytes(directory)
        r['checks'].append('all-PROGRAM-directory-bytes-unchanged-no-utility-records')
        x.rec();s.load(packet,t.sha(packet),ro.FT)
        assert b'FLASH g2' in x.cmd('VERSION')
        x.cmd('BANK 0');x.cmd('READ 8000');assert b'FF FF FF FF' in x.cmd('VIEW 000')
        x.cmd('I 9000 9FFF',(ro.YES,));assert b'Canceled' in x.cmd('NO',(ro.FT,))
        x.cmd('Q',MONS+(t.REC,));x.mon()
        r['checks'].append('standalone-FLASH-works-after-all-stored-copies-removed')
        maint=(package/'MAINT-RO.bin').read_bytes();assert t.sha(maint)==mf['MAINT_RO_sha256']
        x.rec();s.load(maint,t.sha(maint),b'MAINT RO> ')
        assert b'No write' in x.cmd('?')
        x.cmd('Q',MONS+(t.REC,));x.mon();r['checks'].append('host-MAINT-RO-still-loadable')
        x.rec();s.service(reader)
        for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
        s.client.restore_owner(x.ram,x.zp);s.context=t.REC
    r['passed']=len(r['checks'])==6 and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
    t.save(folder/'report.json',r);assert r['passed']
    with t.serial_lease('2512-retirement-closeout',timeout=30):verified_inventory(p,True,folder/'report.json')
    print('PASS final retirement checks; no additional erases; RAM/ZP/cache restored; COM4 released',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['capture', 'recover', 'plan', 'trial', 'execute', 'verify'])
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--source', type=Path)
    a = p.parse_args()
    if a.action in ('plan','execute','verify'): globals()[a.action](a.out.resolve(), a.source.resolve())
    else: globals()[a.action](a.out.resolve())
