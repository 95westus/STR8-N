"""Execute the approved2512 ten-erase plan in two bounded checkpoints."""
import argparse
from datetime import datetime,timezone
import json
import re
import sys
import time
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
import trial_flash_transfer_readonly as ro
from serial_test_coordination import drift_pending

t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve

Q=t.ROOT/'output/qualification'
SCOPE=Q/'FLASH-transfer-scope-20261101-r1'
POS=Q/'2512-flash-transfer-positive-20261101-r1'
INS=Q/'2512-flash-transfer-installed-20261101-r2'
MONS=tuple(f'B{n}> '.encode() for n in range(4))


def run(phase,resume_store=False):
    plan=json.loads((SCOPE/'plan.json').read_text())
    approval=json.loads((SCOPE/'approval.json').read_text())
    review=json.loads((SCOPE/'review.json').read_text())
    assert approval['approved'] and approval['board']=='2512' and approval['total_erases']==10
    assert approval['owner_answer']=='Approve reviewed 10-erase trial/install'
    assert t.sha((SCOPE/'review.json').read_bytes())==approval['review_sha256']
    assert t.sha((SCOPE/'plan.json').read_bytes())==approval['plan_sha256']==review['plan_sha256']
    assert t.sha((SCOPE/'review-document.md').read_bytes())==approval['review_document_sha256']
    assert plan['total_erases']==10 and plan['F_writes']==0 and plan['journal_sector_erases']==1
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text())
    golden=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert t.sha(golden)==freeze['sha256'] and len(golden)==4096
    for name,h in freeze['sources'].items():assert t.sha((t.REPO/name).read_bytes())==h
    mf=json.loads((t.ROOT/'BUILD/flash-transfer-g1-r5/manifest.json').read_text())
    assert t.sha((t.ROOT/'BUILD/flash-transfer-g1-r5/manifest.json').read_bytes())==plan['build_manifest_sha256']
    def artifact(name):
        data=(SCOPE/name).read_bytes();assert t.sha(data)==mf['artifacts'][name]['sha256'];return data
    app=artifact('FLASH-S19-RAM.bin');worker=artifact('FLASH-RECORD-6B00.bin');gate=artifact('FLASH-TRANSFER-GATE-7300.bin')
    assert [(x['bank'],x['page']) for x in plan['installation_targets']]==[(1,0xA0),(2,0xE0),(2,0xF0),(3,0xE0)]
    folder=POS if phase=='positive' else INS
    resumed=None
    if resume_store:
        assert phase=='positive'
        resumed=json.loads((POS/'report.json').read_text())
        assert not resumed['passed'] and resumed['scope_plan_sha256']==approval['plan_sha256']
        assert 'actual-large-flash-Store-preserves-source-through66FF' in resumed['checks']
        assert len(resumed['target_erase_requests'])==1 and not resumed.get('native_dense_erase_allowances_consumed')
        assert resumed['target_erase_requests'][0]['label']=='prepare-occupied-A'
        folder=POS/'after-TABLE-prompt-continuation'
    if phase=='install':
        prior=json.loads((POS/'report.json').read_text());assert prior['passed'] and prior['B0_restored'] and prior['port_released']
        start3=(POS/'B3-after.bin').read_bytes()
    else:start3=(SCOPE/'B3-original.bin').read_bytes()
    expected3=start3
    if resume_store:expected3,_=reserve(expected3,2)
    old0=(SCOPE/'B0-original.bin').read_bytes()
    assert old0[0x1000:0x2000]==b'\xff'*4096 and old0[0x2000:0x3000]!=b'\xff'*4096
    next_due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    if time.time()+600>=datetime.fromisoformat(next_due.replace('Z','+00:00')).timestamp():
        raise TimeoutError('Leave ten minutes for RTC; no port opened')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (folder/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    mp=Q/'device-operations/2512.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    r=dict(board='2512',phase=phase,passed=False,checks=[],target_erase_requests=[],F_writes=0,MON_writes=0,
        SRAM_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
        owner_RAM_restored=False,owner_ZP_restored=False,B0_restored=phase=='install',
        scope_plan_sha256=approval['plan_sha256'],automatic_retries=0)
    if resume_store:
        r['checks']=resumed['checks'].copy();r['target_erase_requests']=resumed['target_erase_requests'].copy()
        r['continued_from_host_prompt_mismatch']=str(POS/'host-prompt-mismatch-report.json')
        opaque.durable_file(POS/'host-prompt-mismatch-report.json',(POS/'report.json').read_bytes())
    s=None;marker=None;borrowed=False;ram=zp=prefix=None;origin=None;edu=None;dirty=False;wire=None
    baseline0=None;baseline3=None;completed=False;predicted0=bytearray(old0)
    counts_budget={(0,0x90):2,(0,0xA0):3} if phase=='positive' else {(x['bank'],x['page']):1 for x in plan['installation_targets']}
    used={x:0 for x in counts_budget};native_started=False
    if resume_store:
        ram=(POS/'owner-ram.bin').read_bytes();zp=(POS/'owner-zp.bin').read_bytes()
        assert t.sha(ram)==resumed['RAM_sha256'] and t.sha(zp)==resumed['ZP_sha256']
        used[(0,0xA0)]=1;dirty=True;r['B0_restore_pending']=True
        predicted0[0x2000:0x3000]=b'\xff'*4096
        predicted0[0x1000:0x1018]=b'SR\x01\x3f'+bytes.fromhex('00 4E 00 19')+b'WIDEFL'.ljust(16,b'\0')
        predicted0[0x1018:0x2918]=ram[0x4C00:]
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def durable(name,data):opaque.durable_file(folder/name,data)
    def check(label):r['checks'].append(label);save();print('PASS2512 '+phase+' '+label,flush=True)
    def boundary():
        if drift_pending():raise InterruptedError('RTC priority; restore the temporary target before yielding')
    def cmd(line,tokens=None):
        if tokens==(t.MON,):tokens=MONS
        if tokens is None and s.context in MONS:tokens=MONS
        face=s.command(line,tokens);(folder/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:s.until(MONS+(t.REC,ro.FT,opaque.PROMPT),seconds=8)
        if s.context in (ro.STORE_YES,b'STORE, no erase; type YES> ',b'STORE PROGRAM from original RAM; type YES: '):s.link.send(b'NO\r');s.until(MONS)
        if s.context==ro.YES:s.link.send(b'NO\r');s.until((ro.FT,))
        if s.context in (ro.FT,t.WB,t.CLOCK,b'BM> ',b'SRAM> ',b'WORK> ',b'STORAGE> '):cmd('Q',MONS)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        if s.context in MONS and s.context!=t.MON:cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON,'Unknown state; never reset or retry a flash operation blindly'
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
        assert s.context==t.REC
    def readback():
        if s.context!=d.SERVICE:rec();s.service(reader)
    def writer_ready():
        nonlocal wire
        if s.context!=opaque.PROMPT:
            rec();s.load(writer,t.sha(writer),opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
    def replace(bank,page,before,data,label):
        nonlocal expected3,dirty
        key=(bank,page);assert key in used and used[key]<counts_budget[key]
        assert len(data)==len(before)==4096 and before!=data
        writer_ready();actual=wire.read_sector(bank,page);assert actual==before,(label,'stale target')
        # The already approved native writer owns reservation/rotation. Its
        # exact forecast is checked before any next target is attempted.
        updated,op=reserve(expected3,bank*8+(page-0x80)//16)
        assert not op['journal_sector_erases'] or op['journal_sector_erases']==['B3:C']
        used[key]+=1;r['target_erase_requests'].append(dict(label=label,bank=bank,page=f'{page:02X}',operation=op))
        if bank==0:dirty=True;r['B0_restore_pending']=True
        save();s.context=None
        assert not wire.replace_sector(bank,page,before,data),'Unexpected identical/no-erase completion'
        s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==data
        if bank==3:
            image=bytearray(updated);offset=(page-0x80)*256;image[offset:offset+4096]=data;updated=bytes(image)
        expected3=updated
        (folder/f'{len(r["target_erase_requests"]):02d}-{label}-readback.bin').write_bytes(data)
        if bank==0:
            off=(page-0x80)*256;predicted0[off:off+4096]=data
        check(label)
    def original_owner():
        readback();r.update(s.client.restore_owner(ram,zp));s.context=t.REC;mon()
        if edu!=1:cmd(f'!M 6A20 {edu:02X}')
        r['owner_RAM_restored']=False;r['owner_ZP_restored']=False;save()
    def raw_record(line,reply=None):
        rec();packet=ro.record_packet(worker,line,gate)
        s.link.send(b'L\r');s.until((b'SEND BIN\r\n',),seconds=10)
        for off in range(0,len(packet),16):s.link.send(packet[off:off+16]);time.sleep(.002)
        face=s.until((ro.STORE_YES,t.MON),seconds=40)
        if reply is not None:
            assert s.context==ro.STORE_YES,face
            s.link.send(reply);face+=s.until(MONS,seconds=90)
        else:assert s.context==t.MON,face
        (folder/f'raw-record-{len(r["checks"]):02d}.txt').write_bytes(face);return face
    def source():
        mon()
        return b''.join(s.dump(a,min(a+1023,0x66FF)) for a in range(0x4E00,0x6700,1024))
    def archive_before_rotation():
        readback();actual=s.client.flash(3);assert actual==expected3
        name='B3-before-C-rotation.bin'
        if not (folder/name).exists():durable(name,actual)
        r['history_archive_before_rotation']=str(folder/name);r['history_rows_before_rotation']=t.classify_journal(actual)['valid_records'];save()
    def restore_B0():
        nonlocal dirty
        if not dirty:return
        # Cleanup has its own two approved allowances. Never repeat an erase.
        readback();actual=s.client.flash(0)
        for page in (0x90,0xA0):
            off=(page-0x80)*256;before=actual[off:off+4096];original=old0[off:off+4096]
            if before!=original:
                _,op=reserve(expected3,(page-0x80)//16)
                if op['journal_sector_erases']:archive_before_rotation()
                replace(0,page,before,original,'restore-B0-'+f'{page:02X}')
        readback();actual=s.client.flash(0);assert actual==old0
        durable('B0-restored.bin',actual);dirty=False;r.update(B0_restored=True,B0_restore_pending=False)
        check('exact-original-B0-image-restored')
    save()
    with t.serial_lease('2512-approved-flash-transfer-'+phase,timeout=180):
      boundary()
      due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
      assert time.time()+600<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp(),'RTC window changed while waiting'
      marker=json.loads(mp.read_text())
      if resume_store:
          assert marker['application_RAM_restore_pending'] and marker['block_snapshot'] and marker['flash_transfer_write_pending']
          assert marker['last_flash_transfer_write']==str(POS/'report.json')
      else:assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['monitor_generation']=='0000000D'
      assert marker['current_physical_bank_sha256']['B0']==t.sha(old0)
      assert marker['current_physical_bank_sha256']['B3']==t.sha(start3)
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,'2512');s.link.send(b'\r');s.until(MONS+(t.REC,),seconds=12);origin=t.MON if s.context in MONS else s.context;mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            edu=s.dump(0x6A20,0x6A20)[0]
            if not resume_store:
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                durable('owner-prefix.bin',prefix)
            durable('owner-zp.bin',zp)
            mark(flash_transfer_write_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,
                 flash_transfer_write_pending=True);borrowed=True
            rec();s.service(reader)
            if not resume_store:
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                ram=prefix+memory[len(reader):]
            durable('owner-ram.bin',ram)
            baseline0=s.client.flash(0);baseline3=s.client.flash(3)
            assert baseline0==(bytes(predicted0) if resume_store else old0) and baseline3==expected3
            durable('B0-before.bin',baseline0);durable('B3-before.bin',baseline3)
            assert baseline3[-4096:]==golden
            check('fresh-owner-images-golden-F-and-journal-admitted')
            boundary()
            if phase=='positive':
                if not resume_store:
                    replace(0,0xA0,old0[0x2000:0x3000],b'\xff'*4096,'prepare-occupied-A')
                    original_owner()
                    face=raw_record('STORE 0 9000 4E00 66FF WIDEFL',b'YES\r')
                    assert b'Flash record OK' in face and source()==ram[0x4C00:]
                    check('actual-large-flash-Store-preserves-source-through66FF')
                else:mon()
                assert b'WIDEFL' in cmd('TABLE 0')
                readback();stored=s.client.flash(0)
                h=stored[0x1000:0x1018];payload=stored[0x1018:0x2918]
                assert h==b'SR\x01\x3f'+bytes.fromhex('00 4E 00 19')+b'WIDEFL'.ljust(16,b'\0')
                assert payload==ram[0x4C00:]
                expected0=bytearray(predicted0);expected0[0x1000:0x1018]=h;expected0[0x1018:0x2918]=payload
                assert stored==expected0
                durable('B0-after-Store.bin',stored)
                assert s.client.flash(3)==expected3
                check('TABLE-and-exact-SR01-header-payload-commit')
                mon();face=raw_record('RESTORE 0 WIDEFL L')
                assert b'Flash record OK' in face and source()==ram[0x4C00:]
                check('wide-load-only-flash-Restore-through66FF')
                boundary()
                rec();packet=ro.flash_packet(app,start3);s.load(packet,t.sha(packet),ro.FT)
                cmd('BANK 0');cmd('I 9000 AFFF',(ro.YES,));native_started=True
                for key in ((0,0x90),(0,0xA0)):
                    assert used[key]<counts_budget[key];used[key]+=1
                r['native_dense_erase_allowances_consumed']=2;save()
                s.link.send(b'YES\r');s.until((ro.SEND,),seconds=12)
                data=bytes((i*73+(i>>4)+0xA5)&255 for i in range(8192))
                stream=ro.srec(0,0,b'2512 reviewed dense flash')
                stream+=b''.join(ro.srec(1,0x9000+i,data[i:i+252]) for i in range(0,len(data),252))
                stream+=ro.srec(9,0x9000)
                durable('dense-test.s19',stream);durable('dense-expected.bin',data)
                for i in range(0,len(stream),128):s.link.send(stream[i:i+128]);time.sleep(.002)
                face=s.until((ro.FT,),seconds=120);(folder/'dense-result.txt').write_bytes(face)
                assert b'S19 stopped' not in face and b'OK\r\n' in face,face
                for index in (1,2):expected3,_=reserve(expected3,index)
                cmd('Q',(t.MON,));readback();after0=s.client.flash(0);after3=s.client.flash(3)
                assert after0[0x1000:0x3000]==data and after0[:0x1000]==old0[:0x1000] and after0[0x3000:]==old0[0x3000:]
                assert after3==expected3
                durable('B0-after-dense.bin',after0);durable('B3-after-dense.bin',after3)
                predicted0[:]=after0
                check('two-native-dense-sector-erases-crossing-record-and-exact-readback')
                restore_B0()
                assert t.classify_journal(expected3)['sequence']==1126
                r['positive_implementations_accepted']=True
            else:
                # Install is one short coherent unit: E changes last, after its
                # gate/worker and both FLASH halves have been verified.
                boundary()
                for target in plan['installation_targets']:
                    data=(SCOPE/target['file']).read_bytes();assert t.sha(data)==target['sha256']
                    before=(SCOPE/f"B{target['bank']}-{target['page']:02X}-original.bin").read_bytes()
                    replace(target['bank'],target['page'],before,data,'install-'+target['address'].replace(':','-'))
                assert expected3==(SCOPE/'B3-target.bin').read_bytes()
                original_owner()
                face=cmd('STORE 0 9000 5800 66FF NATIVE',(ro.STORE_YES,))
                s.link.send(b'NO\r');face+=s.until(MONS,seconds=30)
                assert b'Canceled' in face and source()==ram[0x4C00:]
                assert b'REFUSED' in cmd('RESTORE 0 ABSENT L')
                check('installed-flash-source-gate-and-wide-Store-Restore-front-doors')
                cmd('R FLASH',(ro.FT,));assert b'I first last' in cmd('?')
                cmd('BANK 0');cmd('I 9000 AFFF',(ro.YES,));s.link.send(b'YES\r');s.until((ro.SEND,))
                s.link.send(b'\x03');face=s.until((ro.FT,));assert b'S19 stopped $03' in face
                cmd('Q',(t.MON,));check('installed-native-FLASH-I-cancellation')
                from trial_s19_ram import READY
                cmd('S19',(READY,));s.link.send(b'\x03');face=s.until(MONS);assert b'S19 stopped $03' in face
                check('installed-S19-tail-return-to-ROM-after-gate-state-overwrite')
                cmd('MAINT LOAD',(t.WB,));cmd('Q',(t.MON,))
                cmd('AREA 0 9000 9FFF')
                cmd('STORE 0 AUTO 0200 020F AUTOCHK',(b'STORE, no erase; type YES> ',))
                s.link.send(b'NO\r');face=s.until(MONS);assert b'Canceled' in face
                check('installed-AREA-AUTO-session-preserved-through-cache-reload')
                cmd('STORE P 9800 4700 66FF PROGRAMNO',(b'STORE PROGRAM from original RAM; type YES: ',))
                s.link.send(b'NO\r');face=s.until(MONS);assert b'Canceled' in face
                check('installed-PROGRAM-tail-return-and-no-SPI-write')
                assert b'WIDEFL' not in cmd('TABLE 0')
                cmd('R CLOCK',(t.CLOCK,));cmd('TIME');cmd('TRIM');cmd('Q',(t.MON,))
                cmd('R MAINT',(b'BM> ',));cmd('NAME');cmd('Q',(t.MON,))
                cmd('M1');cmd('W');face=cmd('VERSION');assert b'Board: 2512' in face and b'CPU: 65C02' in face
                assert b'STATUS tools unavailable' not in face
                check('installed-existing-CLOCK-MAINT-table-maps-wear-STATUS-retained')
            readback();after0=s.client.flash(0);after3=s.client.flash(3)
            assert after0==old0 and after3==expected3
            assert after3[-4096:]==golden and after3[0x2000:0x4000]==start3[0x2000:0x4000]
            durable('B0-after.bin',after0);durable('B3-after.bin',after3)
            r['NVM_verified']=True;r['final_journal']=t.classify_journal(after3)
            r['final_B3_sha256']=t.sha(after3)
            check('exact-final-B0-journal-boot-settings-F-and-MON-preservation')
            completed=True
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          try:
            if borrowed:
                try:
                    if dirty:
                        # Do not guess erase history after a failed native transfer.
                        # A full, idle readback precedes any approved cleanup.
                        if s.context is None:raise RuntimeError('Unknown flash state; retain recovery guard and original escrow')
                        readback();actual3=s.client.flash(3)
                        if actual3!=expected3:
                            r['unexpected_journal']=t.classify_journal(actual3)
                            raise RuntimeError('Journal differs from checked stage; inspect without automatically retrying a write')
                        restore_B0()
                finally:
                    # Preserve owner RAM even if an idle flash/history discrepancy
                    # prevents automatic target cleanup. Retain its separate guard.
                    if s.context is None:s.until(MONS+(t.REC,ro.FT),seconds=8)
                    readback()
                    if ram is None:
                        memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                    r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                    if origin==t.MON:
                        mon()
                        if edu!=1:cmd(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'] and not dirty
                values=dict(flash_transfer_write_worker_active=False,application_RAM_restore_pending=not(r['owner_RAM_restored'] and r['owner_ZP_restored']),
                    application_ram_restored=r['owner_RAM_restored'] and r['owner_ZP_restored'],
                    block_snapshot=(False if resume_store else marker['block_snapshot']) if restored and completed else True,
                    flash_transfer_write_pending=not completed,last_flash_transfer_write=str(folder/'report.json'))
                if completed:
                    j=r['final_journal'];hashes=marker['current_physical_bank_sha256'].copy()
                    hashes.update(B0=t.sha(old0),B3=t.sha(expected3))
                    if phase=='install':
                        hashes.update({f'B{b}':plan['final_bank_sha256'][f'B{b}'] for b in (1,2)})
                    counts=marker['current_tracked_erase_counts'].copy()
                    for i,value in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
                    for letter,index in zip('ABCDEF',range(26,32)):counts[letter]=j['counts'][index]
                    values.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,current_wear_counts=j['counts'],
                        current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp),
                        flash_transfer_positive_complete=phase=='positive' or marker.get('flash_transfer_positive_complete',False),
                        flash_transfer_installed=phase=='install',final_prompt='B3>' if origin==t.MON else 'REC>')
                mark(**values)
            save()
    r['passed']=completed and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released'] and not dirty
    save();print(('PASS ' if r['passed'] else 'INCOMPLETE ')+'2512 flash transfer '+phase+'; COM4 released',flush=True)
    if resume_store and r['passed']:
        for name in ('B0-after.bin','B3-after.bin'):
            opaque.durable_file(POS/name,(folder/name).read_bytes())
        t.save(POS/'report.json',dict(r,continuation_report=str(folder/'report.json'),original_failed_receipt=str(POS/'host-prompt-mismatch-report.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['positive','install'],required=True);p.add_argument('--resume-store',action='store_true')
    a=p.parse_args();run(a.phase,a.resume_store)
