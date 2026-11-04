"""Install only the approved2512 three-sector correction; never retry an erase."""
import json,re,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
import trial_flash_transfer_readonly as ro
from serial_test_coordination import drift_pending

t=d.t;Q=t.ROOT/'output/qualification'
SCOPE=Q/'FLASH-status-correction-scope-20261101-r1'
OUT=Q/'2512-flash-status-corrected-20261101-r1'
MONS=tuple(f'B{n}> '.encode() for n in range(4))
AUTO=b'STORE, no erase; type YES> '
PROGRAM=b'STORE PROGRAM from original RAM; type YES: '


def run():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve three-erase correction'
    assert a['plan_sha256']==t.sha((SCOPE/'plan.json').read_bytes())
    assert a['review_sha256']==t.sha((SCOPE/'review.json').read_bytes())
    assert a['review_document_sha256']==t.sha((SCOPE/'review-document.md').read_bytes())
    assert p['total_erases']==3 and p['journal_sector_erases']==p['F_writes']==0
    assert [(x['bank'],x['page']) for x in p['targets']]==[(1,0xA0),(2,0xE0),(2,0xF0)]
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());f=(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert t.sha(f)==freeze['sha256'] and all(t.sha((t.REPO/n).read_bytes())==v for n,v in freeze['sources'].items())
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    if time.time()+300>=datetime.fromisoformat(due.replace('Z','+00:00')).timestamp():raise TimeoutError('Leave five minutes for RTC; no port opened')
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,F_writes=0,MON_writes=0,
      C_D_erases=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
      owner_RAM_restored=False,owner_ZP_restored=False,automatic_retries=0)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json';s=None;ram=zp=prefix=None;borrowed=False;marker=None
    expected3=(SCOPE/'B3-target.bin').read_bytes();old0=(SCOPE/'B0-original.bin').read_bytes()
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        if tokens is None and s.context in MONS:tokens=MONS
        if tokens==(t.MON,):tokens=MONS
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:s.until(MONS+(t.REC,ro.FT,opaque.PROMPT),seconds=8)
        if s.context in (ro.STORE_YES,AUTO,PROGRAM):s.link.send(b'NO\r');s.until(MONS)
        if s.context==ro.YES:s.link.send(b'NO\r');s.until((ro.FT,))
        if s.context in (ro.FT,t.WB,t.CLOCK,b'BM> '):cmd('Q',MONS)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        if s.context in MONS and s.context!=t.MON:cmd('B3',MONS)
        if s.context==t.REC:cmd('B',MONS)
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def readback():
        if s.context!=d.SERVICE:rec();s.service(reader)
    def check(n):r['checks'].append(n);save();print('PASS2512 correction '+n,flush=True)
    save()
    with t.serial_lease('2512-approved-three-sector-STATUS-AUTO-correction',timeout=180):
      if drift_pending():raise InterruptedError('RTC priority; no board commands sent')
      next_due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
      assert time.time()+300<datetime.fromisoformat(next_due.replace('Z','+00:00')).timestamp()
      marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['flash_status_correction_pending'] and marker['STATUS_runtime_unavailable']
      assert marker['current_physical_bank_sha256']==p['before_bank_sha256']
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until(MONS+(t.REC,),seconds=12);mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(flash_status_correction_write_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            b0=s.client.flash(0);b3=s.client.flash(3)
            assert b0==old0 and t.sha(b3)==p['before_bank_sha256']['B3'] and b3[-4096:]==f
            opaque.durable_file(OUT/'B0-before.bin',b0);opaque.durable_file(OUT/'B3-before.bin',b3)
            check('fresh-owner-B0-history-and-golden-F-admitted')
            if drift_pending():raise InterruptedError('RTC priority before first erase')
            rec();s.load(writer,t.sha(writer),opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
            for target in p['targets']:
                bank,page=target['bank'],target['page'];before=wire.read_sector(bank,page)
                assert t.sha(before)==target['before_sha256']
                body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
                r['erase_requests']+=1;save();s.context=None
                assert not wire.replace_sector(bank,page,before,body)
                s.context=opaque.PROMPT;actual=wire.read_sector(bank,page);assert actual==body
                (OUT/f'B{bank}-{page:02X}-after.bin').write_bytes(actual);r['completed'].append(target['address']);check('installed-'+target['address'])
            rec();mon();face=cmd('VERSION')
            assert b'CPU: 65C02' in face and b'Board: 2512' in face and b'PROGRAM payload' in face and b'WORKSPACE' in face
            assert b'Battery:' in face and b'FLASH:' in face and b'RTCC:' in face and b'unavailable' not in face
            assert re.search(rb'trim \$[0-9A-F]{2} ctrl \$[0-9A-F]{2}',cmd('TIME'))
            check('rich-STATUS-board-CPU-EDU-SRAM-clock-battery-wear-restored')
            cmd('R FLASH',(ro.FT,));assert b'FLASH g2' in cmd('VERSION')
            cmd('BANK 0');cmd('I 9000 9FFF',(ro.YES,));s.link.send(b'YES\r');s.until((ro.SEND,),seconds=12)
            s.link.send(b'\x03');assert b'S19 stopped $03' in s.until((ro.FT,))
            cmd('Q',MONS);check('actual-ROM-fragment-library-load-and-dense-I-Ctrl-C')
            # An all-FF completion must change neither the verified blank sector
            # nor any journal row. It exercises full installed sector staging.
            readback();assert s.client.flash(0)==old0 and old0[0x1000:0x2000]==b'\xff'*4096
            before_noop=s.client.flash(3);assert before_noop==expected3
            mon();cmd('R FLASH',(ro.FT,));cmd('BANK 0');cmd('I 9000 9FFF',(ro.YES,))
            s.link.send(b'YES\r');s.until((ro.SEND,),seconds=12)
            stream=ro.srec(0,0,b'No-change installed dense acceptance')
            stream+=b''.join(ro.srec(1,0x9000+i,b'\xff'*min(252,4096-i)) for i in range(0,4096,252))
            stream+=ro.srec(9,0x9000)
            for off in range(0,len(stream),128):s.link.send(stream[off:off+128]);time.sleep(.002)
            face=s.until((ro.FT,),seconds=90);assert b'OK\r\n' in face and b'S19 stopped' not in face
            cmd('Q',MONS);readback();assert s.client.flash(0)==old0 and s.client.flash(3)==before_noop
            r['dense_noop_sector_writes']=0;check('complete-installed-dense-all-FF-pass-B0-and-journal-unchanged')
            s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            cmd('STORE 0 9000 5800 66FF CORRNO',(ro.STORE_YES,));s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS)
            assert b'REFUSED' in cmd('RESTORE 0 ABSENT L')
            check('board-loaded-wide-front-NO-and-Restore-lookup')
            cmd('MAINT LOAD',(t.WB,));cmd('Q',MONS);assert b'AREA updated' in cmd('AREA 0 9000 9FFF')
            face=cmd('STORE 0 AUTO 0200 020F AUTOCHK',(AUTO,));assert b'Target B0:9000' in face
            s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS)
            check('installed-AUTO-retains-AREA-after-SP-only-reload')
            cmd('STORE P 9800 4700 66FF PROGRAMNO',(PROGRAM,));s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS)
            from trial_s19_ram import READY
            cmd('S19',(READY,));s.link.send(b'\x03');assert b'S19 stopped $03' in s.until(MONS)
            check('PROGRAM-and-S19-tail-returns-retained-without-SPI-write')
            cmd('TABLE 0');cmd('R MAINT',(b'BM> ',));cmd('NAME');cmd('Q',MONS)
            cmd('R CLOCK',(t.CLOCK,));cmd('TIME');cmd('TRIM');cmd('Q',MONS);cmd('M1');cmd('W');mon()
            assert b'CPU: 65C02' in cmd('VERSION');check('existing-table-MAINT-CLOCK-maps-wear-remain-usable')
            readback();final0=s.client.flash(0);final3=s.client.flash(3)
            assert final0==old0 and final3==expected3
            opaque.durable_file(OUT/'B0-after.bin',final0);opaque.durable_file(OUT/'B3-after.bin',final3)
            assert final3[:0x4000]==b3[:0x4000] and final3[0x6000:]==b3[0x6000:]
            r['NVM_verified']=True;r['final_journal']=t.classify_journal(final3);check('exact-B0-F-MON-settings-and-all21-old-rows-preserved')
        finally:
          try:
            if borrowed:
                readback()
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];complete=restored and r.get('NVM_verified',False)
                values=dict(flash_status_correction_write_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=not complete,flash_status_correction_pending=not complete,final_prompt='REC>',last_flash_status_correction=str(OUT/'report.json'))
                if complete:
                    counts=marker['current_tracked_erase_counts'].copy()
                    for i,v in enumerate(p['counts_after']):counts[f'B{i//8}:{i%8+8:X}']=v
                    for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['counts_after'][i]
                    values.update(current_physical_bank_sha256=p['after_bank_sha256'],current_tracked_erase_counts=counts,current_wear_counts=p['counts_after'],
                        current_journal_sequence=1133,current_journal_valid_records=24,current_valid_journal_records=24,
                        status_installation_complete=True,STATUS_runtime_unavailable=False,flash_AUTO_AREA_regression=False,
                        flash_transfer_qualification_pending=False,flash_transfer_write_pending=False,flash_transfer_installed=True,
                        status_admission_hold_reason=None,current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp),
                        FLASH_revision='shared-dense-r4',flash_record_revision='BOOT-hex-r4',flash_gate_revision='AUTO-SP-only-r4')
                mark(**values)
            save()
    r['passed']=r.get('NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    save();assert r['passed'];print('PASS2512 STATUS/AUTO correction installed; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
