"""Finish approved2512 checks/binding after correcting the cross-Q buffer test.

ZERO additional erases or image writes. Existing five installed images must
match first. Exactly one previously approved CONFIG C B append remains.
"""
import json
import install_status_reviewed as i
t=i.t;d=i.d;CASE=i.BASE/'2512';RESUME=CASE/'finish-checks'
def run():
    initial=json.loads((CASE/'report.json').read_text());assert len(initial['completed'])==5 and initial['owner_RAM_restored']
    plan=json.loads((i.SCOPE/'2512/plan.json').read_text())
    ram=(CASE/'owner-ram.bin').read_bytes();zp=(CASE/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    config=(t.REPO/'firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes()
    RESUME.mkdir(exist_ok=False);(RESUME/'driver-as-executed.py').write_bytes(__import__('pathlib').Path(__file__).read_bytes())
    (RESUME/'initial-failed-report.json').write_bytes((CASE/'report.json').read_bytes())
    r=dict(passed=False,additional_erases=0,image_writes=0,CONFIG_binding_appends=0,owner_RAM_restored=False,
           buffer_test_correction='Cross-Q comparison changed only10 MON-owned6A bytes; active FLASH uses its own VERSION.',checks=[])
    def save():t.save(RESUME/'report.json',r)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False;save()
    with t.serial_lease('2512-approved-STATUS-checks-and-one-B-binding',timeout=30):
      marker=json.loads(t.MARK.read_text());assert not marker['application_RAM_restore_pending']
      with (RESUME/'serial.jsonl').open('x') as log:
       try:
        s=d.Session(RESUME,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
        assert s.dump(0x200,0x1FF+len(reader))==ram[:len(reader)] and s.dump(0,0xDF)==zp
        mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
        s.command('Q',(t.REC,));s.service(reader)
        assert s.client.read(b'M',0x6500)==reader+ram[len(reader):]
        before2=s.client.flash(2);before3=s.client.flash(3)
        assert t.sha(before2)==plan['final_B2_sha256']
        j=t.classify_journal(before3)
        assert j['counts']==plan['counts_after'] and j['sequence']==plan['expected_sequence_after']-1
        for item in plan['targets']:
            if item['bank']==3:
                a=int(item['address'],16)-0x8000;assert t.sha(before3[a:a+4096])==item['sha256']
        s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC;s.command('B',(t.MON,))
        s.command('R FLASH',(d.FT,));s.command('BANK 0');s.command('READ 8000')
        views=[s.command(f'VIEW {p:03X}') for p in range(0,4096,256)]
        s.command('VERSION')
        assert [s.command(f'VIEW {p:03X}') for p in range(0,4096,256)]==views
        r['checks'].append('active-FLASH-VERSION-4K-buffer-exact');save()
        s.command('Q',(t.MON,))
        buf=(s.dump(0x6800,0x69FF),s.dump(0x6B00,0x77FF));s.command('VERSION')
        assert (s.dump(0x6800,0x69FF),s.dump(0x6B00,0x77FF))==buf
        r['checks'].append('MON-VERSION-keeps-non6A-native-buffer');save()
        s.command('Q',(t.REC,));t.transport.recovery_usb(s.link);s.load(config,t.sha(config),i.CONFIG)
        assert b'DEFAULT=B' in s.command('B')
        out=s.command('C B');assert b'OK' in out and b'REFUSED' not in out
        r['CONFIG_binding_appends']=1;save()
        s.command('Q',(t.MON,));assert b'g0000000C / MON B' in s.command('VERSION')
        r['checks'].append('existing-B-default-bound-gC-and-software-boot')
        s.command('Q',(t.REC,));s.service(reader)
        final2=s.client.flash(2);final3=s.client.flash(3)
        assert final2==before2
        original=(CASE/'B3-before.bin').read_bytes()
        assert final3[:0x2000]==original[:0x2000] and final3[0x6000:]==original[0x6000:]
        for off in range(0x5000,0x6000,256):
            if original[off:off+256]!=b'\xff'*256:assert final3[off:off+256]==original[off:off+256]
        j=t.classify_journal(final3)
        assert j['sequence']==plan['expected_sequence_after'] and j['valid_records']==plan['expected_valid_records_after']
        assert j['counts']==plan['counts_after'] and j['default']=='B' and j['entries']==[8]*4 and j['enabled_mask']==15
        latest=[final3[o:o+256] for o in range(0x4000,0x6000,256) if final3[o:o+4]==b'SNBT' and int.from_bytes(final3[o+8:o+12],'little')==j['sequence']]
        assert len(latest)==1 and int.from_bytes(latest[0][0x12:0x16],'little')==12
        (CASE/'B2-after.bin').write_bytes(final2);(CASE/'B3-after.bin').write_bytes(final3)
        r.update(NVM_verified=True,journal=j,final_B2_sha256=t.sha(final2),final_B3_sha256=t.sha(final3))
       finally:
        try:
         if borrowed and s.context is not None:
            if s.context!=i.SERVICE:
                assert s.context==t.MON;s.command('Q',(t.REC,));s.service(reader)
            r.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.command('B',(t.MON,));r['owner_RAM_restored']=True
        finally:
         if s is not None:s.link.close();r['port_released']=True
         mark(status_worker_active=False,application_RAM_restore_pending=not r['owner_RAM_restored'],
              application_ram_restored=r['owner_RAM_restored'],block_snapshot=marker['block_snapshot'] if r['owner_RAM_restored'] else True)
         save()
    assert r.get('NVM_verified') and r['owner_RAM_restored'];r.update(passed=True,finished_utc=t.utc());save()
    result=dict(initial);result.update({k:v for k,v in r.items() if k not in ('checks','additional_erases','image_writes')})
    result.pop('error',None);result['checks']=initial['checks']+r['checks']+['all-reviewed-postimages-history-policy-and-counts']
    result.update(phase='ROM_SOFTWARE_PASSED_PHYSICAL_BOOT_PENDING',host_test_correction_receipt=str(RESUME/'report.json'))
    t.save(CASE/'report.json',result)
    hashes=marker['current_physical_bank_sha256'].copy();hashes.update(B2=r['final_B2_sha256'],B3=r['final_B3_sha256'])
    mark(monitor_generation='0000000C',current_physical_bank_sha256=hashes,current_journal_sequence=j['sequence'],
         current_journal_valid_records=j['valid_records'],status_installation_complete=False,status_physical_boot_pending=True,
         firmware_verification_pending=False,state='MON-gC-STATUS-software-accepted-physical-pending',final_prompt='B3>')
    print(json.dumps(r,indent=2),flush=True)
if __name__=='__main__':run()
