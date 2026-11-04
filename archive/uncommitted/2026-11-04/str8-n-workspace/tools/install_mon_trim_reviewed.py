"""Install only the approved gD A/B images and same-B generation binding."""
import argparse,json,re
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from rtc_mon_ui1_gd_trim import parse_time

t=d.t
SCOPE=t.ROOT/'output/qualification/MON-trim-scope-20261031-r1'
CONFIG=b'RAM CONFIG ? B C I W Q> '
BM=b'BM> '


def run(board,folder):
    approval=json.loads((SCOPE/'approval.json').read_text())
    assert approval['approved'] and approval['human_answer']=='Approve reviewed gD installation'
    assert approval['review_sha256']==t.sha((SCOPE/'review.json').read_bytes())
    pp=SCOPE/board/'plan.json';plan=json.loads(pp.read_text())
    assert approval['plan_sha256'][board]==t.sha(pp.read_bytes())
    assert plan['image_erases']==2 and plan['D_erases']==int(board=='2609')
    assert plan['F_writes']==plan['C_erases']==0
    folder=Path(folder).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (folder/'approval.json').write_bytes((SCOPE/'approval.json').read_bytes())
    markpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    config=(t.REPO/'firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes()
    expected=(SCOPE/board/'B3-target.bin').read_bytes();assert t.sha(expected)==plan['target_B3_sha256']
    r=dict(board=board,passed=False,completed=[],checks=[],image_erase_requests=0,binding_requests=0,
           F_writes=0,C_erases=0,RTC_data_writes=0,SRAM_data_writes=0,power_cuts=0,
           owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=prefix=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(markpath.read_text());m.update(kw);t.save(markpath,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def rec():
        if s.context in (BM,t.CLOCK,d.FT,t.WB):s.command('Q',(t.MON,))
        if s.context==t.MON:s.command('Q',(t.REC,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        assert s.context==t.REC,'Unknown state; no blind reset or erase retry'
    def clock_sample():
        face=s.command('TIME');row=parse_time(face)
        assert row['trim_steps']==plan['trim_RAM_observed'] and row['control_register']==plan['control_RAM_observed']
        (folder/f'TIME-{s.counter}.txt').write_bytes(face)
        return row
    save()
    with t.serial_lease(board+'-approved-MON-trim-install',timeout=30):
        marker=json.loads(markpath.read_text())
        assert marker['monitor_generation']=='0000000C' and not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        assert marker['current_physical_bank_sha256']['B3']==plan['before_B3_sha256']
        with (folder/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                assert b'g0000000C / MON B' in s.command('VERSION')
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
                mark(mon_trim_install_worker_active=True,mon_trim_installation_pending=True,
                     application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
                old=s.client.flash(3);assert t.sha(old)==plan['before_B3_sha256']
                (folder/'B3-before.bin').write_bytes(old);(folder/'CD-history-before.bin').write_bytes(old[0x4000:0x6000])
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
                check('fresh-owner-and-exact-reviewed-history-admitted')
                rec();s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda x:print(x,flush=True))
                for item in plan['targets']:
                    prior=wire.read_sector(3,item['page']);assert t.sha(prior)==item['before_sha256']
                    body=(SCOPE/board/item['file']).read_bytes();assert t.sha(body)==item['sha256']
                    r['image_erase_requests']+=1;save();s.context=None
                    assert not wire.replace_sector(3,item['page'],prior,body)
                    s.context=opaque.PROMPT;assert wire.read_sector(3,item['page'])==body
                    r['completed'].append(item['address']);check('installed-MON-'+item['address'])
                rec()
                for slot in ('A','B'):
                    face=s.command(slot,(t.MON,));assert ('g0000000D / MON '+slot).encode() in face
                    r['latest_TIME']=clock_sample()
                    app=s.command('R MAINT',(BM,t.REC,t.MON));assert s.context==BM and b'BANK MAINT 2.4' in app
                    s.command('NAME');s.command('Q',(t.MON,));rec()
                check('A-and-B-live-trim-and-unchanged-MAINT-UI-return')
                s.load(config,t.sha(config),CONFIG)
                assert b'DEFAULT=B' in s.command('B')
                r['binding_requests']=1;save();assert b'OK' in s.command('C B')
                boot=s.command('Q',(t.MON,));(folder/'saved-default-software-startup.txt').write_bytes(boot)
                assert b'g0000000D / MON B' in boot
                clock_sample();check('same-B-default-generation-D-software-startup')
                rec();s.service(reader);final=s.client.flash(3)
                (folder/'B3-after.bin').write_bytes(final)
                assert final==expected,'Exact native journal/image forecast differs; inspect without a retry'
                r.update(NVM_verified=True,final_B3_sha256=t.sha(final),final_journal=t.classify_journal(final))
                check('exact-image-history-counts-metadata-and-golden-F-preservation')
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                            ram=prefix+memory[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['port_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields=dict(mon_trim_install_worker_active=False,application_RAM_restore_pending=not restored,
                                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                                    last_MON_trim_install=str(folder/'report.json'))
                        if r.get('NVM_verified'):
                            hashes=marker['current_physical_bank_sha256'].copy();hashes['B3']=r['final_B3_sha256']
                            counts=marker['current_tracked_erase_counts'].copy()
                            for n,value in enumerate(plan['counts_after']):counts[f'B{n//8}:{n%8+8:X}']=value
                            for letter,index in zip('ABCDEF',range(26,32)):counts[letter]=plan['counts_after'][index]
                            fields.update(current_physical_bank_sha256=hashes,current_tracked_erase_counts=counts,
                                current_wear_counts=plan['counts_after'],current_journal_sequence=plan['sequence_after'],
                                current_journal_valid_records=plan['records_after'],current_valid_journal_records=plan['records_after'],
                                monitor_generation='0000000D',MON_A_generation='0000000D',MON_B_generation='0000000D',
                                saved_default='B',saved_default_generation='0000000D',final_prompt='B3>',
                                mon_trim_installation_pending=False,mon_trim_installed=True,
                                current_owner_RAM_sha256=t.sha(ram),current_owner_ZP_sha256=t.sha(zp))
                        mark(**fields)
                    save()
    r['passed']=bool(r.get('NVM_verified') and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    save();assert r['passed'];print('PASS '+board+' MON gD installed; RAM/ZP restored; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.board,a.out)
