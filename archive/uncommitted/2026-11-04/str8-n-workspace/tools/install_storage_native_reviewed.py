"""Install only the sealed, owner-approved native storage scope; no retries."""
import argparse,json,re,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from serial_test_coordination import drift_pending
t=d.t
SCOPE=t.ROOT/'output/qualification/STORAGE-native-scope-20261101-r3'
MENU=b'STORAGE> ';SM=b'SRAM> ';WORK=b'WORK> ';BM=b'BM> ';YES=b'Type YES: '
MONS=tuple(f'B{n}> '.encode() for n in range(4))

def run(board,out):
    approval=json.loads((SCOPE/'approval.json').read_text())
    assert approval['approved'] and board in approval['boards']
    assert approval['review_sha256']==t.sha((SCOPE/'review.json').read_bytes())
    planfile=SCOPE/board/'plan.json';plan=json.loads(planfile.read_text())
    assert approval['plan_sha256'][board]==t.sha(planfile.read_bytes())
    assert [(v['bank'],v['page']) for v in plan['targets']]==[(1,0xB0),(1,0xC0),(1,0xD0),(3,0x80),(2,0x80),(2,0x90),(3,0xE0)]
    assert plan['image_erases']==7 and plan['F_writes']==0 and plan['journal_sector_erases']==(['B3:D'] if board=='2512' else [])
    schedule=t.ROOT/'output/qualification/rtc-hourly-controller-last.json'
    if schedule.exists():
        next_due=json.loads(schedule.read_text()).get('next_due')
        if next_due and time.time()+600>=datetime.fromisoformat(next_due.replace('Z','+00:00')).timestamp():
            raise TimeoutError('Leave the next ten minutes for RTC collection; no board port opened')
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification');folder.mkdir(exist_ok=False)
    (folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (folder/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    r=dict(board=board,passed=False,checks=[],completed=[],image_erases_requested=0,F_writes=0,
        RTC_setting_writes=0,SRAM_data_writes=0,power_cuts=0,resets=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=prefix=metadata_before=None;edu=None;marker=None
    expected={b:(SCOPE/board/f'B{b}-target.bin').read_bytes() for b in (1,2,3)}
    assert all(t.sha(v)==plan['target_bank_sha256'][f'B{b}'] for b,v in expected.items())
    def save():t.save(folder/'report.json',r)
    def mark(**values):
        m=json.loads(mp.read_text());m.update(values);t.save(mp,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def cmd(line,tokens=None):
        output=s.command(line,tokens);label=re.sub('[^A-Za-z0-9]','_',line)[:42]
        (folder/f'{s.counter:04d}-{label}.txt').write_bytes(output);return output
    def mon():
        if s.context==YES:cmd('NO',(MENU,))
        if s.context in (SM,WORK):cmd('Q',MONS)
        if s.context in (MENU,BM,t.CLOCK,d.FT,t.WB):cmd('Q',MONS)
        if s.context in MONS and s.context!=t.MON:cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON,'Unknown state: do not reset or retry a write blindly'
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
        assert s.context==t.REC
    def metadata():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON');face=cmd('SRAM')
        if b'SSRAM error $01' in face:cmd('SRAM PREP');face=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in face
        chunks=[]
        for address in range(0,0x800,64):
            raw=cmd(f'SRAM READ 0 {address:04X}');match=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',raw);assert match
            chunks.append(bytes.fromhex(match[1].decode()))
        cmd('Q',MONS);mon();return b''.join(chunks)
    save()
    with t.serial_lease(board+'-reviewed-native-storage-install',timeout=600):
      marker=json.loads(mp.read_text())
      assert marker['monitor_generation']=='0000000D' and marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert all(marker['current_physical_bank_sha256'][f'B{b}']==plan['before_bank_sha256'][f'B{b}'] for b in (1,2,3))
      if drift_pending():raise TimeoutError('RTC has priority; no board commands sent')
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            edu=s.dump(0x6A20,0x6A20)[0];prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(storage_native_install_worker_active=True,storage_native_install_pending=True,
                 application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);s.service(reader)
            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            for bank in (1,2,3):
                before=s.client.flash(bank);assert t.sha(before)==plan['before_bank_sha256'][f'B{bank}']
                (folder/f'B{bank}-before.bin').write_bytes(before)
            rec();metadata_before=metadata();(folder/'SPI-metadata-before.bin').write_bytes(metadata_before)
            check('fresh-owner-target-images-history-and-SPI-metadata-admitted')
            if drift_pending():raise TimeoutError('RTC requested priority before first flash write; safe to resume fresh')
            rec();s.load(writer,t.sha(writer),opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
            for target in plan['targets']:
                bank,page=target['bank'],target['page'];before=wire.read_sector(bank,page)
                assert t.sha(before)==target['before_sha256']
                body=(SCOPE/board/target['file']).read_bytes();assert t.sha(body)==target['sha256']
                r['image_erases_requested']+=1;save();s.context=None
                assert not wire.replace_sector(bank,page,before,body)
                s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
                r['completed'].append(target['address']);check('installed-'+target['address'])
            rec();cmd('B',(t.MON,));cmd('APPS')
            # Exercise normal board-loaded routes, not host-supplied app bodies.
            cmd('R SRAM',(SM,));assert b'CLK' in cmd('T')
            cmd('!',(MENU,));cmd('PREP');cmd('S',(SM,));cmd('Q',MONS);mon()
            cmd('B1',(b'B1> ',));cmd('R WORK',(WORK,));assert b'workspace:' in cmd('?')
            cmd('!',(MENU,));cmd('UNLOCK',(YES,));cmd('YES',(MENU,));cmd('LOCK',(MENU,));cmd('W',(WORK,));cmd('Q',MONS)
            assert s.context==b'B1> ';mon();check('installed-SRAM-WORK-Table-capacity-controls-and-selected-bank-Q')
            cmd('R CLOCK',(t.CLOCK,));cmd('TIME');cmd('TRIM');cmd('Q',MONS);mon()
            cmd('R FLASH',(d.FT,));cmd('VERSION');cmd('Q',MONS);mon()
            cmd('R MAINT',(BM,));cmd('NAME');cmd('Q',MONS);mon()
            check('existing-native-CLOCK-FLASH-MAINT-remain-usable')
            for line in ('R SRAM BAD','R WORK BAD'):
                face=cmd(line);assert b'REFUSED: syntax' in face
            face=cmd('BATCH R WORK;VERSION',(t.MON,t.WB));assert b'REFUSED:' in face
            mon();check('native-storage-argument-and-BATCH-refusal')
            after=metadata();(folder/'SPI-metadata-after.bin').write_bytes(after);assert after==metadata_before
            rec();s.service(reader)
            for bank in (1,2,3):
                final=s.client.flash(bank);(folder/f'B{bank}-after.bin').write_bytes(final)
                assert final==expected[bank],f'Exact B{bank} image/history forecast differs; inspect without retry'
            r['NVM_verified']=True;r['final_journal']=t.classify_journal(expected[3])
            check('exact-target-images-journal-boot-settings-and-SPI-preservation')
        finally:
          try:
            if borrowed:
                if s.context!=d.SERVICE:rec();s.service(reader)
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC;r['owner_RAM_restored']=True
                cmd('B',(t.MON,))
                if edu!=1:cmd(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                values=dict(storage_native_install_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored and r.get('NVM_verified') else True,
                    last_storage_native_install=str(folder/'report.json'))
                if r.get('NVM_verified'):
                    hashes=marker['current_physical_bank_sha256'].copy();hashes.update(plan['target_bank_sha256'])
                    counts=marker['current_tracked_erase_counts'].copy()
                    for n,v in enumerate(plan['counts_after']):counts[f'B{n//8}:{n%8+8:X}']=v
                    for letter,index in zip('ABCDEF',range(26,32)):counts[letter]=plan['counts_after'][index]
                    values.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,current_wear_counts=plan['counts_after'],
                        current_journal_sequence=plan['sequence_after'],current_journal_valid_records=plan['records_after'],
                        current_valid_journal_records=plan['records_after'],services_generation='0000000C',workbench_generation='0000000D',
                        storage_generation='00000002',storage_native_install_pending=False,storage_native_installed=True,
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                elif r['image_erases_requested']==0:
                    values.update(block_snapshot=marker['block_snapshot'] if restored else True,storage_native_install_pending=False)
                mark(**values)
            save()
    r['passed']=bool(r.get('NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS '+board+' native SRAM/WORK installed; owner RAM restored; port released',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.board,a.out)
