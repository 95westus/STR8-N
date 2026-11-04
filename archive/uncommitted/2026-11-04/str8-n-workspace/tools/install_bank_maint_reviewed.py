"""Execute only the owner-approved two-board BANK MAINT plan; no retries/F writes."""
import argparse
import binascii
import json
from pathlib import Path
import re
import install_2512_native_utilities as d
import nf_opaque as opaque

t = d.t
SCOPE = t.ROOT / 'output/qualification/BANK-MAINT-scope-20261031-r1'
BM = b'BM> '
CONFIRM = b'WRITE? TYPE Y> '


def run(board, folder):
    planpath = SCOPE / board / 'plan.json'
    plan = json.loads(planpath.read_text())
    approval = json.loads((SCOPE / 'approval.json').read_text())
    assert approval['approved'] and approval['human_answer'] == 'Approve both reviewed installs and tests'
    assert approval['review_sha256'] == t.sha((SCOPE / 'review.json').read_bytes())
    assert approval['plan_sha256'][board] == t.sha(planpath.read_bytes())
    assert plan['image_erases'] == 7 and plan['C_D_erases'] == plan['F_writes'] == 0
    assert plan['total_erases'] == (8 if board == '2512' else 9)
    expected = [(1,0x80),(1,0x90),(1,0xA0),(2,0x80),(2,0x90),(3,0xE0),(3,0x80)]
    assert [(x['bank'],x['page']) for x in plan['targets']] == expected
    folder = Path(folder).resolve()
    assert folder.is_relative_to(t.ROOT / 'output/qualification')
    folder.mkdir(exist_ok=False); (folder / '.gitignore').write_text('*\n')
    (folder / 'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (folder / 'approval.json').write_bytes((SCOPE / 'approval.json').read_bytes())
    markerpath = t.ROOT / f'output/qualification/device-operations/{board}.json'
    reader = (t.REPO / 'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer = (t.REPO / 'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    frozen = (t.REPO / 'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    images = {n:(SCOPE / board / f'B{n}-image-target.bin').read_bytes() for n in (1,2,3)}
    for n, body in images.items():assert t.sha(body) == plan['target_bank_sha256'][f'B{n}']
    old9 = (SCOPE / board / 'B0-9000-before.bin').read_bytes()
    assert t.sha(old9) == plan['fixture_before_sha256']
    r = dict(board=board,passed=False,checks=[],completed=[],image_erases_requested=0,
             fixture_erase_commands=0,F_writes=0,C_D_erases=0,RTC_writes=0,
             SRAM_data_writes=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s = None; borrowed = False; ram = zp = prefix = None
    def save():t.save(folder / 'report.json', r)
    def mark(**kw):
        m=json.loads(markerpath.read_text()); m.update(kw); t.save(markerpath,m)
    def check(label):
        r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def rec():
        if s.context == CONFIRM:s.command('NO',(BM,))
        if s.context == b'Type YES: ':s.command('NO',(BM,))
        if s.context == BM:s.command('Q',(t.MON,))
        if s.context in (t.CLOCK,d.FT,t.WB):s.command('Q',(t.MON,))
        if s.context == t.MON:s.command('Q',(t.REC,))
        if s.context == d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context == opaque.PROMPT:
            s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        assert s.context == t.REC,'Unknown board state: no blind recovery or flash retry'
    def cmd(text,tokens=None):
        out=s.command(text,tokens)
        label=re.sub(r'[^A-Za-z0-9_-]','_',text.split()[0])
        (folder / f'{s.counter:04d}-{label}.txt').write_bytes(out)
        return out
    def write(text):
        assert s.context == BM
        out=cmd(text,(CONFIRM,BM));assert s.context == CONFIRM,(text,out)
        if text == 'E 0 9':r['fixture_erase_commands']+=1;save()
        out=cmd('Y',(BM,));assert b'VERIFIED' in out,(text,out)
    def crc():
        out=cmd('K');m=re.search(rb'CRC16-CCITT-FALSE ([0-9A-F]{4})',out);assert m,out
        return int(m[1],16)
    save()
    with t.serial_lease(board+'-approved-BANK-MAINT-install',timeout=30):
        marker=json.loads(markerpath.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        for name,digest in plan['before_bank_sha256'].items():
            assert marker['current_physical_bank_sha256'][name] == digest
        with (folder / 'serial.jsonl').open('x') as log:
            try:
                s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context == t.REC:cmd('B',(t.MON,))
                assert b'g0000000C / MON B' in cmd('VERSION')
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (folder / 'owner-prefix.bin').write_bytes(prefix);(folder / 'owner-zp.bin').write_bytes(zp)
                mark(bank_maint_install_worker_active=True,bank_maint_installation_pending=True,
                     application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                mem=s.client.read(b'M',0x6500)
                assert mem[:len(reader)] == reader and s.client.read(b'Z',0xE0) == zp
                ram=prefix+mem[len(reader):];(folder / 'owner-ram.bin').write_bytes(ram)
                old3=s.client.flash(3)
                assert t.sha(old3) == plan['before_bank_sha256']['B3'] and old3[-4096:] == frozen
                (folder / 'B3-before.bin').write_bytes(old3)
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
                check('fresh-owner-escrow-journal-and-golden-F-admission')
                rec();s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
                assert wire.read_sector(0,0x90) == old9
                for item in plan['targets']:
                    prior=wire.read_sector(item['bank'],item['page'])
                    assert t.sha(prior) == item['before_sha256']
                    body=(SCOPE / board / item['file']).read_bytes();assert t.sha(body) == item['sha256']
                    (folder / f"old-B{item['bank']}-{item['page']:02X}00.bin").write_bytes(prior)
                    r['image_erases_requested']+=1;save();s.context=None
                    assert not wire.replace_sector(item['bank'],item['page'],prior,body)
                    s.context=opaque.PROMPT
                    assert wire.read_sector(item['bank'],item['page']) == body
                    r['completed'].append(f"B{item['bank']}:{item['address']}");check('installed-'+r['completed'][-1])
                rec();cmd('B',(t.MON,))
                assert b'Board: '+board.encode() in cmd('VERSION')
                assert b'MAINT B1:8000' in cmd('APPS')
                face=cmd('R MAINT',(BM,t.MON,t.REC))
                assert s.context == BM and b'BANK MAINT 2.4' in face,face
                assert b'Copy RAM or flash' in cmd('?')
                assert b'BANK MAINT 2.4' in cmd('VERSION')
                assert b'DEFAULT=B' in cmd('BOOT')
                rows=cmd('TABLE')
                assert b'B1:8000 2000-42FC 22FD C MAINT' in rows,rows
                assert b'B2:B000 2000-4FD4 2FD5 C CLOCK' in rows
                cmd('T 1');check('cold-R-MAINT-real-menu-VERSION-BOOT-and-TABLE')
                # Preserve the exact original fixture in user RAM; independent
                # editor, staging and journal scratch must never damage it.
                cmd('R 0 9000-9FFF');assert crc() == binascii.crc_hqx(old9,65535)
                write('W R 0200')
                mark(bank_maint_fixture_restore_pending=True)
                if board == '2609':write('E 0 9')
                cmd('N 10 A5');write('W R 1300')
                write('C R 1300-130F 0 9000')
                assert b'MATCH' in cmd('V R 1300-130F 0 9000')
                cmd('R 0 9000-9FFF');cmd('P 20 5A')
                desired=bytearray(b'\xff'*4096);desired[:16]=b'\xA5'*16;desired[32]=0x5A
                assert crc() == binascii.crc_hqx(desired,65535)
                write('W 0 9000')
                cmd('R 0 9000-9FFF');assert crc() == binascii.crc_hqx(desired,65535)
                assert b'A5 A5 A5' in cmd('D 0-2F')
                assert b'MATCH' in cmd('V R 1300-130F 0 9000')
                # 2512: one explicit erase restores FF. 2609: one automatic
                # rewrite erase restores the original occupied WDC sector.
                if board == '2512':write('E 0 9')
                else:
                    cmd('R R 0200-11FF');assert crc() == binascii.crc_hqx(old9,65535)
                    write('W 0 9000')
                cmd('R 0 9000-9FFF');assert crc() == binascii.crc_hqx(old9,65535)
                assert b'MATCH' in cmd('V R 0200-11FF 0 9000')
                check('native-flash-copy-compare-4K-editor-erase-and-exact-fixture-restore')
                for text in ('NAME CLEAR','NAME '+board):
                    cmd(text,(b'Type YES: ',));out=cmd('YES',(BM,))
                    assert b'REFUSED' not in out and b'FAIL' not in out,out
                assert b'Board: '+board.encode() in cmd('NAME')
                check('confirmed-NAME-clear-and-original-name-restored')
                cmd('Q',(t.MON,))
                assert s.dump(0,0xDF) == zp
                out=cmd('BATCH R MAINT;N 10 A5;K;Q',(t.MON,BM,t.REC))
                if s.context == BM:
                    out+=s.until((t.MON,),seconds=30)
                assert s.context == t.MON and b'BATCH done' in out,out
                check('BATCH-native-MAINT-and-quiet-Q-preserve-monitor')
                for name,prompt in (('CLOCK',t.CLOCK),('FLASH',d.FT)):
                    face=cmd('R '+name,(prompt,t.MON,t.REC));assert s.context == prompt,face
                    cmd('VERSION');cmd('Q',(t.MON,))
                cmd('MAINT',(t.WB,));cmd('T');cmd('Q',(t.MON,))
                for text in ('VERSION','TIME','APPS','M1','W'):cmd(text)
                check('CLOCK-FLASH-WORKBENCH-PROGRAM-and-status-routes-retained')
                rec();s.service(reader)
                for bank in (1,2):
                    actual=s.client.flash(bank);assert actual == images[bank]
                    (folder / f'B{bank}-after.bin').write_bytes(actual)
                final3=s.client.flash(3);(folder / 'B3-after.bin').write_bytes(final3)
                j=t.classify_journal(final3)
                assert j['counts'] == plan['counts_after'] and j['sequence'] == plan['sequence_after']
                assert j['valid_records'] == plan['records_after']
                for key in ('default','enabled_mask','entries','unknown_mask'):
                    assert j[key] == t.classify_journal(old3)[key]
                # Preserve every byte of every existing C/D row, plus all
                # metadata/provider/MON/F bytes outside the two BN append rows.
                masked=bytearray(final3);expected3=bytearray(images[3])
                for address in plan['reserved_append_pages']:
                    off=int(address,16)-0x8000
                    assert old3[off:off+256] == b'\xff'*256
                    masked[off:off+256]=expected3[off:off+256]
                for address in plan['naming_slots']:
                    off=int(address,16)-0x8000;row=final3[off:off+32]
                    assert row[:2] == b'BN' and row[31] == 0
                    assert binascii.crc_hqx(row[:28],65535) == int.from_bytes(row[28:30],'little')
                    masked[off:off+32]=expected3[off:off+32]
                assert masked == expected3 and final3[-4096:] == frozen
                r.update(NVM_verified=True,final_journal=j,
                         final_bank_sha256={'B1':t.sha(images[1]),'B2':t.sha(images[2]),'B3':t.sha(final3)})
                check('exact-images-old-history-metadata-boot-policy-and-F-preserved')
                rec();s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=90,trace=log)
                assert wire.read_sector(0,0x90) == old9
                r['fixture_verified_exact']=True;mark(bank_maint_fixture_restore_pending=False)
                rec();s.service(reader)
            finally:
                try:
                    if borrowed:
                        if s.context != d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            mem=s.client.read(b'M',0x6500);assert mem[:len(reader)] == reader
                            ram=prefix+mem[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        r['owner_RAM_restored']=True
                        cmd('B',(t.MON,))
                finally:
                    if s is not None:s.link.close();r['port_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields=dict(bank_maint_install_worker_active=False,application_RAM_restore_pending=not restored,
                                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                                    last_BANK_MAINT_install=str(folder / 'report.json'))
                        if r.get('NVM_verified'):
                            hashes=marker['current_physical_bank_sha256'].copy();hashes.update(r['final_bank_sha256'])
                            counts=marker['current_tracked_erase_counts'].copy()
                            for n,count in enumerate(plan['counts_after']):counts[f'B{n//8}:{n%8+8:X}']=count
                            for letter,index in zip('ABCDEF',range(26,32)):counts[letter]=plan['counts_after'][index]
                            fields.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,
                                current_wear_counts=plan['counts_after'],current_journal_sequence=plan['sequence_after'],
                                current_journal_valid_records=plan['records_after'],current_valid_journal_records=plan['records_after'],
                                services_generation='0000000B',workbench_generation='0000000C',final_prompt='B3>',
                                bank_maint_installation_pending=False,bank_maint_installed=True,
                                current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                        mark(**fields)
                    save()
    r['passed']=bool(r.get('NVM_verified') and r.get('fixture_verified_exact') and
                     r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'],r
    print('PASS '+board+' installed BANK MAINT; owner RAM/ZP restored; port released',flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.board,a.out)
