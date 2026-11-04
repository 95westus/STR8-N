"""Approved2512 BOOT/CLOCK positives, guarded cleanup; F/time/EEPROM excluded."""
import json,re,time
from pathlib import Path
import install_startup_traditional_2512 as previous
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=previous.t;d=previous.d;Q=previous.Q
SCOPE=Q/'2512-BOOT-CLOCK-scope-20261101-r2'
OUT=Q/'2512-BOOT-CLOCK-positive-20261101-r1'
B0=b'B0> ';YES=b'Type YES to confirm: ';EYES=b'Remember this EUI in flash? Type YES: ';BYES=b'Type YES: '

def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve reviewed three-erase BOOT/CLOCK trial'
    for name,key in [('plan.json','plan_sha256'),('review.json','review_sha256'),('review-document.md','review_document_sha256')]:
        assert t.sha((SCOPE/name).read_bytes())==a[key]
    assert p['total_erases']==3 and p['total_journal_appends']==9 and p['metadata_appends']==3
    assert p['F_writes']==p['MON_A_B_writes']==p['RTC_SET']==p['trim_writes']==p['EEPROM_writes']==p['resets']==0
    assert p['sequence_after']==1177 and p['records_after']==20
    frozen=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==frozen['sha256']==p['F_sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in frozen['sources'].items())
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in p['source_sha256'].items())
    return p

def await_window():
    printed=False
    while True:
        try:previous.base.window(300);return
        except AssertionError:
            if not printed:print('WAIT RTC: no serial port opened; collection keeps priority',flush=True);printed=True
            time.sleep(1)

def run():
    p=approved();await_window()
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    original3=(SCOPE/'B3-original.bin').read_bytes();original9=(SCOPE/'B3-9000-original.bin').read_bytes()
    expected3=(SCOPE/'B3-expected-final.bin').read_bytes();fixture=(SCOPE/'B0-9000-fixture.bin').read_bytes()
    original0=(SCOPE/'B0-9000-original.bin').read_bytes();expected_meta=(SCOPE/'B3-9000-trial-metadata.bin').read_bytes()
    ee_original=(SCOPE/'EEPROM-00-7F-original.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],policy_issued=[],policy_committed=[],policy_failed=[],metadata_committed=[],
        direct_erase_requests=[],native_D_erase_requested=False,F_writes=0,MON_writes=0,RTC_SET=0,trim_writes=0,
        PF_ACK=0,EEPROM_writes=0,SPI_data_writes=0,resets=0,power_cuts=0,automatic_mutation_retries=0,
        owner_RAM_restored=False,owner_ZP_restored=False,fixture_dirty=False,metadata_dirty=False,
        boot_settings_restored=False,images_restored=False,EEPROM_preserved=False,NVM_verified=False)
    s=None;ram=zp=prefix=outage_before=None;borrowed=False;marker=None;before3=None;after3=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:70]}.txt').write_bytes(face);return face
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        else:
            if s.context in (YES,EYES,BYES):cmd('NO',(t.CLOCK,))
            if s.context in (d.FT,t.CLOCK,t.WB):cmd('Q',(t.MON,))
            if s.context==B0:cmd('B3',(t.MON,))
            if s.context==t.MON:cmd('Q',(t.REC,))
        assert s.context==t.REC
    def mon():
        if s.context in (d.SERVICE,opaque.PROMPT):rec()
        if s.context in (YES,EYES,BYES):cmd('NO',(t.CLOCK,))
        if s.context in (d.FT,t.CLOCK,t.WB):cmd('Q',(t.MON,))
        if s.context==B0:cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def native(name,prompt):
        mon();face=cmd('R '+name,(prompt,t.MON))
        if s.context==t.MON and b'Tools invalid' in face:
            cmd('MAINT LOAD',(t.WB,));cmd('Q',(t.MON,));face=cmd('R '+name,(prompt,t.MON))
            r.setdefault('RAM_loader_reload',[]).append(name);save()
        assert s.context==prompt,(name,face)
        return face
    def check(label):r['checks'].append(label);save();print('PASS2512 BOOT/CLOCK '+label,flush=True)
    def wire():
        rec();s.load(writer,t.sha(writer),opaque.PROMPT)
        return opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda line:print(line,flush=True))
    def current3(label):
        rec();s.service(reader);body=s.client.flash(3);(OUT/(label+'.bin')).write_bytes(body);return body
    def policy(index):
        op=p['operations'][index];text=op['command']
        assert index<6 and text not in r['policy_failed'] and len(r['policy_issued'])<6
        native('FLASH',d.FT)
        if op['journal_sector_erases']:
            assert op['journal_sector_erases']==['B3:D'] and not r['native_D_erase_requested']
            r['native_D_erase_requested']=True
        r['policy_issued'].append(text);save()
        answer=cmd(text);mon()
        reference=(SCOPE/f'journal-after-{index+1}.bin').read_bytes()
        try:
            for write in op['journal_appends']:
                at=int(write['page'],16);actual=s.dump(at,at+255)
                (OUT/f'{write["page"]}-seq{write["sequence"]}.bin').write_bytes(actual)
                assert actual==reference[at-0xC000:at-0xBF00],(text,answer,write)
        except BaseException:r['policy_failed'].append(text);save();raise
        r['policy_committed'].append(text);save();check(text)
    def cleanup_sector(bank,page,original,label):
        w=wire();actual=w.read_sector(bank,page)
        (OUT/(label+'-precleanup.bin')).write_bytes(actual)
        if actual==original:
            if bank==0:r['fixture_dirty']=False
            else:r['metadata_dirty']=False
            save();return
        assert (bank,page) in ((0,0x90),(3,0x90)) and (bank,page) not in [tuple(x) for x in r['direct_erase_requests']]
        assert len(r['direct_erase_requests'])<2
        r['direct_erase_requests'].append([bank,page]);save();s.context=None
        assert not w.replace_sector(bank,page,actual,original)
        s.context=opaque.PROMPT;restored=w.read_sector(bank,page);assert restored==original
        opaque.durable_file(OUT/(label+'-restored.bin'),restored)
        if bank==0:r['fixture_dirty']=False
        else:r['metadata_dirty']=False
        save();check(label+'-exact-restoration')
    def restore_partial_policy():
        body=current3('B3-before-emergency-policy-restore');j=t.classify_journal(body)
        assert j['kind']=='valid-snbt' and j['default']=='B' and j['entries'][1:]==[8,8,8]
        from nf_migrate import valid_snapshot
        row=max((body[i:i+256] for i in range(0x4000,0x6000,256) if valid_snapshot(body[i:i+256])),key=lambda b:int.from_bytes(b[8:12],'little'))
        assert row[18:22]==(16).to_bytes(4,'little') and row[13] in (13,15) and row[14] in (8,9) and row[12] in (10,11)
        needed=[]
        if row[13]!=15:needed.append('BOOT B 1 8000')
        if row[14]!=8:needed.append('BOOT B 0 8000')
        if row[12]!=10:needed.append('BOOT DELAY A')
        assert not any(text in r['policy_failed'] for text in needed),'Failed mutation is not automatically retried'
        assert len(r['policy_committed'])+len(needed)<=6
        for text in needed:
            native('FLASH',d.FT);answer=cmd(text);assert b'REFUSED' not in answer,(text,answer)
            r.setdefault('cleanup_policy_commands',[]).append(text);save()
    save()
    with t.serial_lease('2512-approved-BOOT-CLOCK-positive',timeout=30):
      previous.base.window(300);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not marker['physical_reset_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['monitor_generation']=='00000010' and marker['current_physical_bank_sha256']==p['current_physical_bank_sha256']
      t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'STR8-N MON B  gen 00000010' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(boot_clock_trial_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,boot_clock_trial_pending=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            before3=s.client.flash(3);assert before3==original3;opaque.durable_file(OUT/'B3-before.bin',before3)
            w=wire();blank=w.read_sector(0,0x90);assert blank==original0
            opaque.durable_file(OUT/'B0-9000-before.bin',blank)
            native('CLOCK',t.CLOCK);status=cmd('STATUS')
            assert b'Power-fail latched: no' in status and b'OSCTRIM $0C' in status
            cmd('HISTORY');mon();assert s.dump(0x6B00,0x6B7F)==ee_original
            outage_before=s.dump(0x66D4,0x66DB);(OUT/'RTC-outage-before.bin').write_bytes(outage_before)
            assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'))
            check('fresh-targets-F-journal-EEPROM-calendar-trim-owner-admitted')
            previous.base.window(240)
            if drift_pending():raise InterruptedError('RTC priority before first write; no mutation sent')
            cmd('M 18FF 00');cmd('B0',(B0,));r['fixture_dirty']=True;save()
            answer=cmd('!M 9000 '+bytes.fromhex(p['fixture_hex']).hex(' ').upper());assert b'REFUSED' not in answer
            cmd('B3',(t.MON,));check('eight-byte-opaque-fixture-programmed-without-erase')
            policy(0)
            native('FLASH',d.FT);assert b'REFUSED' in cmd('BOOT RUN 1');check('disabled-RUN-refused')
            policy(1)
            native('FLASH',d.FT);assert b'REFUSED' in cmd('BOOT DELAY 9');check('below-minimum-DELAY-refused')
            policy(2);policy(3)
            native('FLASH',d.FT);face=cmd('BOOT RUN 0',(t.MON,d.FT,t.REC))
            assert s.context==t.MON and b'STR8-N MON B  gen 00000010' in face,face
            assert s.dump(0x18FF,0x18FF)==b'\x47';check('positive-opaque-RUN-marker-public-HOLD-to-B')
            policy(4);policy(5);r['boot_settings_restored']=True;save()
            cleanup_sector(0,0x90,original0,'B0-9000')
            for index,record in enumerate(p['metadata_records']):
                native('CLOCK',t.CLOCK);prompt=EYES if index==0 else YES if index==1 else BYES
                face=cmd(record['command'],(prompt,t.CLOCK));assert s.context==prompt,(record['command'],face)
                r['metadata_dirty']=True;save();answer=cmd('YES',(t.CLOCK,))
                mon();at=int(record['address'].split(':')[1],16);row=s.dump(at,at+31)
                (OUT/f'metadata-{at:04X}.bin').write_bytes(row);assert row==bytes.fromhex(record['hex']),(record['command'],answer,row.hex())
                r['metadata_committed'].append(record['command']);save();check(record['command']+'-committed-and-exact')
                if index<2:
                    native('CLOCK',t.CLOCK);repeat=cmd(record['command'],(t.CLOCK,prompt))
                    assert s.context==t.CLOCK,repeat
                    if index==0:assert b'already remembered' in repeat,repeat
                    mon();assert s.dump(at,at+31)==row and s.dump(at+32,at+63)==b'\xff'*32
                    check(record['command']+'-no-op-repeat-no-extra-record')
            w=wire();actual=w.read_sector(3,0x90);assert actual==expected_meta
            opaque.durable_file(OUT/'B3-9000-trial-metadata.bin',actual)
            # cleanup_sector opens a fresh checked tool session; no write is
            # repeated and the already archived target is compared again.
            cleanup_sector(3,0x90,original9,'B3-9000')
            r['images_restored']=True
            native('CLOCK',t.CLOCK)
            assert b'not remembered' in cmd('EUI')
            assert b'-06:00' in cmd('OFFSET')
            assert b'12/24' in cmd('BATTERY')
            assert b'Power-fail latched: no' in cmd('STATUS')
            cmd('HISTORY');mon();cache=s.dump(0x6B00,0x6B7F)
            opaque.durable_file(OUT/'EEPROM-00-7F-after.bin',cache);assert cache==ee_original;r['EEPROM_preserved']=True
            assert s.dump(0x66D4,0x66DB)==outage_before
            assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'))
            check('original-identity-offset-policy-EEPROM-live-trim-and-PF-restored-preserved')
            after3=current3('B3-after');assert after3==expected3;r['NVM_verified']=True
            check('exact-reviewed-final-B3-and-counters-all-old-C-rows-F-and-MON-preserved')
        except BaseException as error:r['error']=repr(error);save();print('STOP2512 test: '+repr(error)+'; performing only authorized preservation cleanup',flush=True)
        finally:
          try:
            if borrowed:
                if r['policy_issued'] and not r['boot_settings_restored']:
                    restore_partial_policy();r['boot_settings_restored']=True
                if r['fixture_dirty']:cleanup_sector(0,0x90,original0,'B0-9000-failure-cleanup')
                if r['metadata_dirty']:cleanup_sector(3,0x90,original9,'B3-9000-failure-cleanup')
                if after3 is None:after3=current3('B3-after-cleanup')
                j=t.classify_journal(after3)
                assert j['kind']=='valid-snbt'
                assert after3[:0x4000]==original3[:0x4000] and after3[0x6000:]==original3[0x6000:]
                from nf_migrate import valid_snapshot
                latest=max((after3[i:i+256] for i in range(0x4000,0x6000,256) if valid_snapshot(after3[i:i+256])),key=lambda b:int.from_bytes(b[8:12],'little'))
                assert latest[7]==ord('B') and latest[12:30]==original3[0x4A0C:0x4A1E]
                assert all(p['counts_before'][i]<=v<=p['counts_after'][i] for i,v in enumerate(j['counts']))
                r.update(boot_settings_restored=True,images_restored=True,final_journal=j,preservation_NVM_verified=True)
          except BaseException as error:r['cleanup_error']=repr(error);save();print('PRESERVATION HOLD: '+repr(error),flush=True)
          finally:
            try:
                if borrowed:
                    rec();s.service(reader)
                    if ram is None:
                        memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                    r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            finally:
                if s:s.link.close();r['COM4_released']=True
                if borrowed:
                    restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                    safe=restored and r.get('preservation_NVM_verified',False) and not r['fixture_dirty'] and not r['metadata_dirty']
                    fields=dict(boot_clock_trial_worker_active=False,application_RAM_restore_pending=not restored,
                        application_ram_restored=restored,block_snapshot=not safe,boot_clock_trial_pending=not safe,
                        final_prompt='REC>',last_BOOT_CLOCK_positive=str(OUT/'report.json'))
                    if r.get('preservation_NVM_verified'):
                        j=r['final_journal'];hashes=marker['current_physical_bank_sha256'].copy();hashes['B3']=t.sha(after3)
                        counts=marker['current_tracked_erase_counts'].copy()
                        for i,value in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
                        for name,i in zip('ABCDEF',range(26,32)):counts[name]=j['counts'][i]
                        fields.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,current_wear_counts=j['counts'],
                            current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],
                            current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                    mark(**fields)
                save()
    r['erase_requests']=len(r['direct_erase_requests'])+int(r['native_D_erase_requested'])
    r['passed']=bool(r.get('NVM_verified') and len(r['policy_committed'])==6 and len(r['metadata_committed'])==3
        and r['EEPROM_preserved'] and r.get('preservation_NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and not r.get('error') and not r.get('cleanup_error'))
    save();assert r['passed'],r
    print('PASS2512 BOOT/CLOCK:3 erases;seq1177;20 rows;all original settings/images/EEPROM/owner restored;REC>;COM4 free',flush=True)

if __name__=='__main__':run()
