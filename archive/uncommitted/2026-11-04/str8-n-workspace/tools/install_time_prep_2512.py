"""Install the pinned owner-approved three-sector TIME/PREP scope once."""
import json,re
from pathlib import Path
import install_named_edu_2512 as base
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=base.t;d=base.d;Q=base.Q;SCOPE=Q/'TIME-PREP-2512-scope-20261101-r1';OUT=Q/'2512-TIME-PREP-installed-20261101-r1'

def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve reviewed three-erase installation'
    for n,k in [('plan.json','plan_sha256'),('review.json','review_sha256'),('review-document.md','review_document_sha256')]:assert t.sha((SCOPE/n).read_bytes())==a[k]
    assert p['total_erases']==3 and p['journal_sector_erases']==p['F_writes']==0
    assert [(v['bank'],v['page']) for v in p['targets']]==[(2,0xF0),(3,0xA0),(3,0xB0)]
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==v for n,v in freeze['sources'].items())
    for n,h in p['build_manifest_sha256'].items():assert t.sha(Path(n).read_bytes())==h
    return p

def run():
    p=approved();base.window(180);OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    expected={b:(SCOPE/f'B{b}-target.bin').read_bytes() for b in (2,3)}
    r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,F_writes=0,C_D_erases=0,SRAM_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,automatic_retries=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;ram=zp=prefix=None;borrowed=False;marker=None;old={}
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:03d}-{re.sub("[^A-Za-z0-9]","_",line)[:36]}.txt').write_bytes(b);return b
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context in (b'SRAM> ',b'WORK> ',b'STORAGE> ',b'BM> ',d.FT,t.CLOCK,t.WB):cmd('Q',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(n):r['checks'].append(n);save();print('PASS2512 TIME/PREP '+n,flush=True)
    save()
    with t.serial_lease('2512-approved-three-sector-TIME-PREP-install',timeout=60):
      base.window(180);marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not marker['physical_reset_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['current_physical_bank_sha256']==p['whole_marker_bank_sha256'];t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon();assert b'g0000000E / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF);opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(time_prep_install_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,time_prep_install_pending=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            for b in (2,3):old[b]=s.client.flash(b);assert t.sha(old[b])==p['before_bank_sha256'][f'B{b}'];opaque.durable_file(OUT/f'B{b}-before.bin',old[b])
            check('fresh-owner-target-images-history-and-golden-F-admitted')
            if drift_pending():raise InterruptedError('RTC requested before first write')
            rec();s.load(writer,t.sha(writer),opaque.PROMPT);wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
            for target in p['targets']:
                b,page=target['bank'],target['page'];off=(page-0x80)*256;before=old[b][off:off+4096];assert t.sha(before)==target['before_sha256']
                body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
                r['erase_requests']+=1;save();s.context=None;assert not wire.replace_sector(b,page,before,body)
                s.context=opaque.PROMPT;actual=wire.read_sector(b,page);assert actual==body
                r['completed'].append(target['address']);check('installed-'+target['address'])
            rec();cmd('A',(t.MON,));assert b'g0000000F / MON A' in cmd('VERSION');assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'));check('installed-A-TIME')
            rec();cmd('B',(t.MON,));assert b'g0000000F / MON B' in cmd('VERSION')
            cmd('R FLASH',(d.FT,));face=cmd('BOOT C B');assert b'OK' in face and b'REFUSED' not in face;cmd('Q',(t.MON,));r['default_B_generation']='0000000F';check('single-default-B-gF-binding')
            rec();s.service(reader)
            for b in (2,3):actual=s.client.flash(b);opaque.durable_file(OUT/f'B{b}-after.bin',actual);assert actual==expected[b]
            r['NVM_verified']=True;check('exact-targets-all21-old-rows-settings-and-F-verified')
            mon();cmd('R SRAM',(b'SRAM> ',));table=cmd('T');assert all(n in table for n in (b'CLK',b'CLOCK',b'NFCOPY'));cmd('Q',(t.MON,));check('installed-SRAM-TABLE-and-Q')
            cmd('R MAINT',(b'BM> ',));assert b'Saved/default: EDU ON' in cmd('EDU');cmd('Q',(t.MON,))
            cmd('R CLOCK',(t.CLOCK,));assert b'REFUSED' not in cmd('TIME');assert b'REFUSED' not in cmd('TRIM');cmd('Q',(t.MON,))
            cmd('R FLASH',(d.FT,));assert b'FLASH g2' in cmd('VERSION');cmd('Q',(t.MON,));check('MAINT-CLOCK-FLASH-read-only-routes')
            r['functional_checks_passed']=True
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
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];kw=dict(time_prep_install_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=r['erase_requests']>0 or not restored,time_prep_install_pending=not r.get('NVM_verified',False),time_prep_qualification_pending=True,final_prompt='REC>',last_TIME_PREP_install=str(OUT/'report.json'))
                if r.get('NVM_verified'):
                    hs=marker['current_physical_bank_sha256'].copy();hs.update(p['after_bank_sha256']);counts=marker['current_tracked_erase_counts'].copy()
                    for i,v in enumerate(p['counts_after']):counts[f'B{i//8}:{i%8+8:X}']=v
                    for n,i in zip('ABCDEF',range(26,32)):counts[n]=p['counts_after'][i]
                    kw.update(current_physical_bank_sha256=hs,current_tracked_erase_counts=counts,current_wear_counts=p['counts_after'],current_journal_sequence=1150,
                        current_journal_valid_records=25,current_valid_journal_records=25,monitor_generation='0000000F',default_monitor_generation='0000000F',
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp),status_admission_hold_reason='Approved gF installation; physical cold boot and versioned RTC readmission pending')
                mark(**kw)
            save()
    r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and len(r['completed'])==3 and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed'];print('PASS2512 three-sector TIME/PREP install; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
