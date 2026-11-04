"""Approved2609 Candidate3 install, bounded16 erases; no F/device-data writes."""
import importlib.util,json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
from serial_test_coordination import drift_pending
from journal_rotation_plan import reserve
from prepare_boot_clock_scope_2512 import append_policy
t=ins.t;d=ins.d;Q=ins.Q
SCOPE=Q/'2609-candidate3-scope-20261102-r1';FIRST=Q/'2609-candidate3-installed-20261102-r1';OUT=FIRST
KIT=t.ROOT/'BUILD/unified-g10-candidate3-20261101-r3/fresh-extraction/STR8N-MON-g00000010-candidate3'
spec=importlib.util.spec_from_file_location('c3_opaque',KIT/'foundation/tools/nf_opaque.py');opaque=importlib.util.module_from_spec(spec);spec.loader.exec_module(opaque)
BM=b'BM> ';SRAM=b'SRAM> ';WORK=b'WORK> '

def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve reviewed 16-erase upgrade and tests'
    for n,k in [('plan.json','plan_sha256'),('review.json','review_sha256'),('review-document.md','review_document_sha256')]:assert t.sha((SCOPE/n).read_bytes())==a[k]
    assert p['total_erases']==16 and p['image_erases']==15 and p['journal_appends']==17 and p['F_writes']==0
    assert p['journal_sector_erases']==['B3:C'] and p['sequence_after']==1089
    for x in p['targets']:assert t.sha((SCOPE/x['file']).read_bytes())==x['sha256']
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((KIT/'F.bin').read_bytes())==f['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    return p

def run(resume=False):
    global OUT
    p=approved();print('Approved2609 scope accepted; waiting for RTC window',flush=True)
    while True:
      try:ins.window(360);break
      except AssertionError:time.sleep(1)
    skip=0
    if resume:
      prior=json.loads((FIRST/'report.json').read_text())
      assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['port_released']
      assert prior['image_erase_requests']==1 and prior['pending_target']=='B3:A000'
      assert prior['error']=="ValueError('Protected/noncanonical target')"
      OUT=Q/'2609-candidate3-installed-20261102-r2';skip=1
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    for n in ('approval.json','plan.json','review.json','review-document.md'):(OUT/n).write_bytes((SCOPE/n).read_bytes())
    reader=(KIT/'foundation/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(KIT/'foundation/firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    old={b:(SCOPE/f'B{b}-original.bin').read_bytes() for b in (1,2,3)};expected=old.copy()
    if resume:
      first=p['targets'][0];assert (first['bank'],first['address'])==(3,'A000')
      future,op=reserve(expected[3],26);a=bytearray(future);a[0x2000:0x3000]=(SCOPE/first['file']).read_bytes();expected[3]=bytes(a)
    admitted_preimages=expected.copy()
    mp=Q/'device-operations/2609.json';s=None;ram=zp=prefix=None;borrowed=False;marker=None;changed=bool(skip)
    r=dict(board='2609',passed=False,checks=[],completed=['B3:A000'] if resume else [],image_erase_requests=skip,journal_appends=skip,
      native_journal_erases=[],F_writes=0,settings_metadata_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
      SPI_writes=0,WORKSPACE_writes=0,physical_resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
      automatic_erase_retries=0,owner_RAM_restored=False,owner_ZP_restored=False,port_released=False)
    if resume:r['resumes']=dict(receipt=str(FIRST/'report.json'),receipt_sha256=t.sha((FIRST/'report.json').read_bytes()),
      reason='Host inspection attempted protected OPAQUE C/D read after verified A replacement; use readback service; never repeat A erase')
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
      face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:45]}.txt').write_bytes(face);return face
    def mon():
      if s.context is None:s.link.send(b'\x03\r');s.until((t.MON,t.REC,opaque.PROMPT,t.WB,d.FT,t.CLOCK,BM,SRAM,WORK),seconds=12)
      if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
      if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
      if s.context in (t.WB,d.FT,t.CLOCK,BM,SRAM,WORK):cmd('Q',(t.MON,))
      if s.context==t.REC:cmd('B',(t.MON,))
      assert s.context==t.MON
    def rec():
      if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
      elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
      elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
      assert s.context==t.REC
    def wire():
      if s.context!=opaque.PROMPT:rec();s.load(writer,t.sha(writer),opaque.PROMPT)
      return opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:None)
    def check(name):r['checks'].append(name);save();print('PASS2609 '+name,flush=True)
    def journal(future,label):
      rec();s.service(reader);actual=s.client.flash(3)
      assert actual==future,label+' B3/journal mismatch'
      (OUT/(label+'-CD.bin')).write_bytes(actual[0x4000:0x6000])
    save()
    with t.serial_lease('2609-approved-candidate3-install',timeout=30):
      ins.window(360);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      if resume:assert marker['RTC_LED_owner_hold_reason']=='Approved Candidate3 install/readmission in progress'
      else:assert not marker['RTC_LED_owner_hold']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert all(marker['current_physical_bank_sha256'][f'B{b}']==t.sha(old[b]) for b in old)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
          s=d.Session(OUT,log,'2609');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
          face=cmd('VERSION');assert b'g0000000D / MON ' in face and b'65C816' in face
          assert re.search(rb'trim \$0E ctrl \$80',cmd('TIME'))
          prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
          (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
          mark(candidate3_install_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
          rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
          ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
          for b in (1,2,3):
            actual=s.client.flash(b);assert actual==admitted_preimages[b],f'Fresh B{b} differs from reviewed/resumed preimage'
            (OUT/f'B{b}-before.bin').write_bytes(actual)
          (OUT/'boot-wear-history-before.bin').write_bytes(old[3][0x4000:0x6000]);check('fresh-images-F-history-trim-and-owner-admitted')
          if resume:
            t.save(FIRST/'inspection-resolution.json',dict(first_target_and_journal_verified=True,
              continuation=str(OUT/'report.json'),B3_sha256=t.sha(admitted_preimages[3]),sequence=1073,image_erases_consumed=1,
              original_approval_unchanged=True,repeat_A_erases=0))
            check('first-A-replacement-and-DA1073-verified-without-rewrite')
          # Prevent only2609 sampling until the new profile is readmitted.
          mark(RTC_LED_owner_hold=True,RTC_LED_owner_hold_reason='Approved Candidate3 install/readmission in progress',candidate3_install_pending=True)
          for number,target in enumerate(p['targets']):
            if number<skip:continue
            if drift_pending():raise InterruptedError('RTC priority; no next erase started')
            ins.window(60)
            bank,address=target['bank'],int(target['address'],16);page=address>>8;off=address-0x8000
            assert r['image_erase_requests']<15 and not r.get('uncertain_flash_mutation')
            w=wire();before=w.read_sector(bank,page);assert before==old[bank][off:off+4096]
            body=(SCOPE/target['file']).read_bytes();future,op=reserve(expected[3],bank*8+(address-0x8000)//4096)
            assert op==p['operations'][number]
            r['image_erase_requests']+=1;r['pending_target']=f'B{bank}:{address:04X}';save();changed=True;s.context=None
            try:
              assert not w.replace_sector(bank,page,before,body)
              s.context=opaque.PROMPT;assert w.read_sector(bank,page)==body
              if bank==3:a=bytearray(future);a[off:off+4096]=body;future=bytes(a)
              journal(future,f'{number+1:02d}')
            except BaseException:r['uncertain_flash_mutation']=r['pending_target'];save();raise
            a=bytearray(expected[bank]);a[off:off+4096]=body;expected[bank]=bytes(a);expected[3]=future
            r['completed'].append(r.pop('pending_target'));r['journal_appends']+=len(op['journal_appends']);r['native_journal_erases']+=op['journal_sector_erases']
            (OUT/'B3-current-predicted.bin').write_bytes(future);save();check('installed-'+r['completed'][-1])
          rec();face=cmd('A',(t.MON,));assert b'STR8-N MON A  gen 00000010' in face
          face=cmd('VERSION');assert b'CPU: 65C816 emulation' in face and b'Board: 2609' in face
          assert re.search(rb'trim \$0E ctrl \$80',cmd('TIME'));check('MON-A-g10-CPU16-and-TIME')
          rec();cmd('B',(t.MON,));face=cmd('VERSION');assert b'STR8-N MON B  gen 00000010' in face and b'CPU: 65C816 emulation' in face
          face=cmd('R FLASH',(d.FT,t.MON))
          if s.context==t.MON:
            assert b'Tools invalid' in face;cmd('MAINT LOAD',(t.WB,));cmd('Q',(t.MON,));cmd('R FLASH',(d.FT,))
          assert s.context==d.FT
          future,op=append_policy(expected[3],{18+i:v for i,v in enumerate((16).to_bytes(4,'little'))},'BOOT C B: retain B default, bind g10')
          assert op==p['operations'][-1] and not op['journal_sector_erases']
          r['default_binding_issued']=True;save();answer=cmd('BOOT C B');assert b'OK' in answer and b'REFUSED' not in answer
          expected[3]=future;r['journal_appends']+=1;r['default_B_generation_bound']='00000010';save()
          rec();s.service(reader)
          for b in (1,2,3):
            actual=s.client.flash(b);assert actual==expected[b]==(SCOPE/f'B{b}-expected.bin').read_bytes()
            (OUT/f'B{b}-after.bin').write_bytes(actual)
          assert r['image_erase_requests']==15 and r['native_journal_erases']==['B3:C'] and r['journal_appends']==17
          r['NVM_verified']=True;check('all-targets-journal-settings-F-and-B-binding-exact')
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if borrowed:
              rec();s.service(reader)
              if ram is None:
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
              r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
              restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];safe=restored and (not changed or r.get('NVM_verified'))
              fields=dict(candidate3_install_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                block_snapshot=marker['block_snapshot'] if safe else True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',
                last_candidate3_install=str(OUT/'report.json'),candidate3_install_pending=changed and not r.get('NVM_verified'),
                candidate3_RTC_readmission_pending=changed,candidate3_physical_boot_pending=bool(r.get('NVM_verified')))
              if not changed:fields.update(RTC_LED_owner_hold=marker['RTC_LED_owner_hold'],RTC_LED_owner_hold_reason=marker['RTC_LED_owner_hold_reason'])
              if r.get('NVM_verified'):
                j=t.classify_journal(expected[3]);counts=marker['current_tracked_erase_counts'].copy()
                for i,v in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=v
                for n,i in zip('ABCDEF',range(26,32)):counts[n]=j['counts'][i]
                hs=marker['current_physical_bank_sha256'].copy();hs.update({f'B{b}':t.sha(v) for b,v in expected.items()})
                fields.update(current_physical_bank_sha256=hs,current_wear_counts=j['counts'],current_tracked_erase_counts=counts,
                  current_journal_sequence=1089,current_journal_valid_records=27,current_valid_journal_records=27,
                  monitor_generation='00000010',default_monitor_generation='00000010',workbench_generation='0000000E',storage_generation='00000004',
                  current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
              mark(**fields)
            save()
    r['passed']=bool(r.get('NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save()
    assert r['passed'];print('PASS2609 installed Candidate3:16 erases,17 appends;F golden;owner restored;REC>;COM8 free;startup/RTC pending',flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--resume-verified-A',action='store_true')
    run(parser.parse_args().resume_verified_A)
