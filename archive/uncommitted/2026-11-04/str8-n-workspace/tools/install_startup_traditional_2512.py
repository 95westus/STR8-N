"""Execute the approved three-sector g10 presentation scope; F is excluded."""
import json,re
from pathlib import Path
import install_named_edu_2512 as base
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=base.t;d=base.d;Q=base.Q
SCOPE=Q/'2512-startup-traditional-scope-20261101-r1'
OUT=Q/'2512-startup-traditional-installed-20261101-r1'

def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve three-erase presentation install'
    assert a['layout_answer']=='Use approved Traditional firmware g10'
    for name,key in [('plan.json','plan_sha256'),('review.json','review_sha256'),('review-document.md','review_document_sha256')]:
        assert t.sha((SCOPE/name).read_bytes())==a[key]
    assert p['total_erases']==3 and p['journal_sector_erases']==p['F_writes']==0
    assert [(v['bank'],v['page']) for v in p['targets']]==[(2,0xA0),(3,0xA0),(3,0xB0)]
    assert p['old_rows_retained_on_chip']==23 and p['sequence_after']==1168
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']==p['F_sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    for target in p['targets']:
        assert t.sha((SCOPE/target['file']).read_bytes())==target['sha256']
    return p

def run():
    p=approved();base.window(240)
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    expected3=(SCOPE/'B3-target.bin').read_bytes();original3=(SCOPE/'B3-original.bin').read_bytes()
    mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,F_writes=0,C_D_erases=0,
           SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,automatic_retries=0,
           owner_RAM_restored=False,owner_ZP_restored=False,scope=str(SCOPE),
           readback_policy='One fresh B3 admission and final B3 comparison for F/history; scoped B2:A readback, no B0/B1 capture or duplicate bank passes')
    s=None;ram=zp=prefix=None;borrowed=False;marker=None;wire=None;before={}
    def save():t.save(OUT/'report.json',r)
    def mark(**fields):m=json.loads(mp.read_text());m.update(fields);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context in (t.WB,t.CLOCK,d.FT,b'SRAM> ',b'WORK> ',b'BM> '):cmd('Q',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(name):r['checks'].append(name);save();print('PASS2512 g10 '+name,flush=True)
    def identity(face,slot):
        assert b'STR8-N F 0.3.0  Foundation  gen 00000001' in face
        assert f'STR8-N MON {slot}  gen 00000010'.encode() in face
        assert b'0.1.0-dev BASE1/PR05 ABI 2' in face and b'CPU: 65C02' in face
        assert b'Board: 2512' in face and b'(-06:00)' in face
    save()
    with t.serial_lease('2512-approved-three-sector-Traditional-install',timeout=30):
      base.window(240);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not marker.get('physical_reset_pending') and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['current_physical_bank_sha256']==p['whole_marker_bank_sha256']
      assert marker['monitor_generation']=='0000000F';t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(startup_install_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,
                 startup_install_pending=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500)
            assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
            opaque.durable_file(OUT/'owner-ram.bin',ram)
            b3=s.client.flash(3);assert b3==original3;opaque.durable_file(OUT/'B3-before.bin',b3)
            check('fresh-owner-F-journal-and-MON-preimages-admitted')
            if drift_pending():raise InterruptedError('RTC priority before first write')
            rec();s.load(writer,t.sha(writer),opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda msg:print(msg,flush=True))
            # Validate every target before the first payload/erase.
            for target in p['targets']:
                bank,page=target['bank'],target['page']
                body=wire.read_sector(bank,page) if bank==2 else b3[(page-0x80)*256:(page-0x70)*256]
                assert t.sha(body)==target['before_sha256'];before[(bank,page)]=body
                opaque.durable_file(OUT/f'B{bank}-{page:02X}-before.bin',body)
            check('all-three-targets-match-reviewed-preimages')
            if drift_pending():raise InterruptedError('RTC priority before first payload')
            for target in p['targets']:
                bank,page=target['bank'],target['page'];body=(SCOPE/target['file']).read_bytes()
                assert len(r['completed'])<3 and (bank,page) in ((2,0xA0),(3,0xA0),(3,0xB0))
                r['erase_requests']+=1;save();s.context=None
                assert not wire.replace_sector(bank,page,before[(bank,page)],body)
                s.context=opaque.PROMPT;actual=wire.read_sector(bank,page);assert actual==body
                opaque.durable_file(OUT/f'B{bank}-{page:02X}-after.bin',actual)
                r['completed'].append(target['address']);check('installed-'+target['address'])
            rec();cmd('A',(t.MON,));identity(cmd('VERSION'),'A')
            assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'));check('installed-A-VERSION-and-TIME')
            rec();startup=cmd('B',(t.MON,));identity(cmd('VERSION'),'B')
            assert b'Recovery / opaque-image boot' in startup and b'CPU:' not in startup and b'MONITOR A gen ' not in startup
            opaque.durable_file(OUT/'installed-B-startup.txt',startup);check('installed-B-selected-startup-and-detailed-VERSION')
            cmd('R FLASH',(d.FT,));face=cmd('BOOT C B')
            assert b'OK' in face and b'REFUSED' not in face;cmd('Q',(t.MON,))
            r['default_B_generation']='00000010';check('single-default-B-generation-binding')
            # Actual ROM UI calls test the header constants and advertised vectors.
            cmd('R CLOCK',(t.CLOCK,));identity(cmd('VERSION'),'B')
            assert b'REFUSED' not in cmd('TIME');cmd('Q',(t.MON,))
            cmd('MAINT LOAD',(t.WB,));identity(cmd('VERSION'),'B');cmd('Q',(t.MON,))
            check('CLOCK-and-workbench-ROM-UI-VERSION-and-return')
            help_text=cmd('?');assert b'VERSION TIME' in help_text and b'S/T/R EDU SRAM WORK BATCH' in help_text
            assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'));check('shared-help-and-native-TIME-retained')
            rec();s.service(reader);actual=s.client.flash(3)
            opaque.durable_file(OUT/'B3-after.bin',actual);assert actual==expected3
            r['NVM_verified']=True;r['functional_checks_passed']=True
            check('all23-old-rows-final27-rows-settings-and-F-exact')
        except BaseException as error:r['error']=repr(error);save();raise
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
                fields=dict(startup_install_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=r['erase_requests']>0 or not restored,
                    startup_install_pending=not r.get('NVM_verified',False),startup_qualification_pending=r['erase_requests']>0,
                    final_prompt='REC>',last_startup_install=str(OUT/'report.json'))
                if r.get('NVM_verified'):
                    hashes=marker['current_physical_bank_sha256'].copy();hashes.update(p['after_bank_sha256'])
                    counts=marker['current_tracked_erase_counts'].copy()
                    for i,value in enumerate(p['counts_after']):counts[f'B{i//8}:{i%8+8:X}']=value
                    for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['counts_after'][i]
                    fields.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,current_wear_counts=p['counts_after'],
                        current_journal_sequence=1168,current_journal_valid_records=27,current_valid_journal_records=27,
                        monitor_generation='00000010',default_monitor_generation='00000010',
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp),
                        status_admission_hold_reason='Approved Traditional g10 installed; physical default boot and versioned RTC readmission pending')
                mark(**fields)
            save()
    r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and len(r['completed'])==3
                     and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS2512 approved g10 install; owner restored; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
