"""Execute the approved nine-image part of the2512 named/EDU scope once."""
import json,re,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from serial_test_coordination import drift_pending

t=d.t;Q=t.ROOT/'output/qualification'
SCOPE=Q/'NAMED-EDU-2512-scope-20261101-r1'
OUT=Q/'2512-named-EDU-installed-20261101-r1'
BM=b'BM> ';ST=b'STORAGE> ';XY=b'Copy program; source retained. Y to confirm: '
EY=b'Save EDU mode? Type YES: '


def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve reviewed 12-erase trial'
    for n,k in [('plan.json','plan_sha256'),('review.json','review_sha256'),('review-document.md','review_document_sha256')]:
        assert t.sha((SCOPE/n).read_bytes())==a[k]
    assert p['total_erases']==12 and p['F_writes']==0 and p['journal_sector_erases']==['B3:D']
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    return p


def window(seconds=240):
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    assert time.time()+seconds<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp(),'RTC window; no port opened'
    assert not drift_pending(),'RTC priority; no port opened'


def forecast(p):
    from journal_rotation_plan import reserve
    state=(SCOPE/'B3-original.bin').read_bytes()
    for target in p['targets']:
        bank,page=target['bank'],target['page']
        state,op=reserve(state,bank*8+(page-0x80)//16)
        if bank==3:
            a=bytearray(state);off=(page-0x80)*256;a[off:off+4096]=(SCOPE/target['file']).read_bytes();state=bytes(a)
    return state


def run():
    p=approved();window();expected3=forecast(p)
    assert t.classify_journal(expected3)['sequence']==1143
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    (OUT/'B3-predicted.bin').write_bytes(expected3)
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,F_writes=0,
        SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,resets=0,
        owner_RAM_restored=False,owner_ZP_restored=False,automatic_retries=0)
    s=None;ram=zp=prefix=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:s.until((t.MON,t.REC,BM,ST,opaque.PROMPT),seconds=10)
        if s.context in (XY,EY):cmd('NO',(BM,ST))
        if s.context in (BM,ST,t.WB,t.CLOCK,d.FT,b'SRAM> ',b'WORK> '):cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(n):r['checks'].append(n);save();print('PASS2512 named/EDU '+n,flush=True)
    save()
    with t.serial_lease('2512-approved-named-EDU-image-install',timeout=60):
      window()
      marker=json.loads(mp.read_text());assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert all(marker['current_physical_bank_sha256'][f'B{b}']==h for b,h in [(0,p['before_bank_sha256']['B0']),(1,p['before_bank_sha256']['B1']),(3,p['before_bank_sha256']['B3'])])
      t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(named_edu_install_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,named_edu_qualification_pending=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            for bank in (0,1,3):
                body=s.client.flash(bank);assert t.sha(body)==p['before_bank_sha256'][f'B{bank}']
                opaque.durable_file(OUT/f'B{bank}-before.bin',body)
            check('fresh-owner-images-history-and-golden-F-admitted')
            if drift_pending():raise InterruptedError('RTC requested before first write')
            rec();s.load(writer,t.sha(writer),opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
            for target in p['targets']:
                bank,page=target['bank'],target['page'];before=wire.read_sector(bank,page)
                assert t.sha(before)==target['before_sha256']
                body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256']
                r['erase_requests']+=1;save();s.context=None
                assert not wire.replace_sector(bank,page,before,body)
                s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
                r['completed'].append(target['address']);check('installed-'+target['address'])
            rec();s.service(reader)
            for bank,expected in [(1,(SCOPE/'B1-target.bin').read_bytes()),(3,expected3)]:
                actual=s.client.flash(bank);opaque.durable_file(OUT/f'B{bank}-after.bin',actual);assert actual==expected
            r['NVM_verified']=True;check('exact-installed-images-and-native-D-rotation')
            mon();assert b'g0000000E / MON B' in cmd('VERSION')
            cmd('R MAINT',(BM,));assert b'EDU [SAVE]' in cmd('?')
            assert b'Saved/default: EDU ON' in cmd('EDU')
            cmd('X P NFCOPY 0 XBACK',(XY,));assert b'Canceled' in cmd('NO',(BM,))
            check('actual-ROM-decompression-and-BM-SRAM-BM-handoff-NO')
            cmd('Q',(t.MON,));cmd('R SRAM',(b'SRAM> ',));assert b'CLK' in cmd('T');cmd('Q',(t.MON,))
            cmd('R WORK',(b'WORK> ',));cmd('?');cmd('Q',(t.MON,))
            check('packed-SRAM-WORK-loads-table-and-Q')
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
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                kw=dict(named_edu_install_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=r['erase_requests']>0 or not restored,final_prompt='REC>',last_named_edu_install=str(OUT/'report.json'))
                if r.get('NVM_verified'):
                    j=t.classify_journal(expected3);hs=marker['current_physical_bank_sha256'].copy();hs.update(B1=t.sha((SCOPE/'B1-target.bin').read_bytes()),B3=t.sha(expected3))
                    counts=marker['current_tracked_erase_counts'].copy()
                    for i,v in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=v
                    for n,i in zip('ABCDEF',range(26,32)):counts[n]=j['counts'][i]
                    kw.update(current_physical_bank_sha256=hs,current_wear_counts=j['counts'],current_tracked_erase_counts=counts,
                        current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],
                        monitor_generation='0000000E',bank_maint_generation='00000003',storage_generation='00000003',
                        current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp),
                        named_edu_RTC_admission_pending=True,status_admission_hold_reason='MON gE installed; approved transfer/EDU acceptance and RTC readmission pending')
                mark(**kw)
            save()
    r['passed']=bool(r.get('NVM_verified') and len(r['checks'])==13 and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS2512 named/EDU installation; REC>; COM4 released',flush=True)


if __name__=='__main__':run()
