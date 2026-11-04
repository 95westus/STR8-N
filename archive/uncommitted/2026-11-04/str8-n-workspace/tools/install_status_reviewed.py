"""Owner-approved five-sector STATUS install; exact reviewed preimages only.

2512 additionally uses its reviewed native C rotation and one B-generation
binding. No retry, rollback, power cut, F write or unreviewed image target.
"""
import argparse,json,re
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
t=d.t
SCOPE=t.ROOT/'output/qualification/STATUS-install-scope-20261031-r1'
BASE=t.ROOT/'output/qualification/STATUS-install-20261031-r1'
SERVICE=d.SERVICE;CONFIG=b'RAM CONFIG ? B C I W Q> '

def run(board):
    review=json.loads((SCOPE/'review.json').read_text());plan=review['boards'][board]
    assert review['total_erases']==11 and len(plan['targets'])==5
    assert plan['native_C_rotation_erases']==(board=='2512')
    CASE=BASE/board;CASE.mkdir(parents=True,exist_ok=False);(CASE/'.gitignore').write_text('*\n')
    t.save(CASE/'approval.json',dict(human_answer='Approve both reviewed installs',
        review_sha256=t.sha((SCOPE/'review.json').read_bytes()),approved_image_erases=5,
        approved_native_C_erases=int(board=='2512'),F_writes=0,power_cuts=0))
    (CASE/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    config=(t.REPO/'firmware/payload/STR8N-F-CONFIG-RAM.bin').read_bytes()
    assert t.sha(reader)==t.live.READBACK_SHA256
    markpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,phase='prepared',image_erase_requests=0,completed=[],checks=[],
        F_writes=0,power_cuts=0,SRAM_data_writes=0,RTC_SET=0,PF_ACK=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;marker=None;ram=zp=None;before3=None
    def save():t.save(CASE/'report.json',r)
    def mark(**kw):
        m=json.loads(markpath.read_text());m.update(kw);t.save(markpath,m)
    def check(name):r['checks'].append(name);save();print('PASS '+board+' '+name,flush=True)
    def rec():
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context in (d.FT,t.CLOCK,t.WB):s.command('Q',(t.MON,));s.command('Q',(t.REC,))
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC,'Unknown execution state; no blind recovery command'
    def face(slot):
        out=s.command(slot,(t.MON,))
        assert f'g0000000C / MON {slot}'.encode() in out
        assert (b'CPU: 65C02' if board=='2512' else b'CPU: 65C816 emulation') in out
        assert b'STATUS tools unavailable' not in out and b'MONITOR A gen 0000000C VALID' in out
        return out
    save()
    try:
      with t.serial_lease(board+'-approved-STATUS-five-sector-install',timeout=30):
       marker=json.loads(markpath.read_text());assert not marker['application_RAM_restore_pending']
       assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
       with (CASE/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(CASE,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15)
            if s.context==t.REC:s.command('B',(t.MON,))
            assert (b'g0000000B' if board=='2512' else b'g00000008') in s.command('V')
            ram,zp=s.owner();opaque.durable_file(CASE/'owner-ram.bin',ram);opaque.durable_file(CASE/'owner-zp.bin',zp)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp));check('fresh-native-owner-escrow')
            mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);s.service(reader)
            assert s.client.read(b'M',0x6500)==reader+ram[len(reader):] and s.client.read(b'Z',0xE0)==zp
            old2=s.client.flash(2);before3=s.client.flash(3)
            assert t.sha(old2)==plan['before_B2_sha256'] and t.sha(before3)==plan['before_B3_sha256']
            opaque.durable_file(CASE/'B2-before.bin',old2);opaque.durable_file(CASE/'B3-before.bin',before3)
            check('reviewed-B2-B3-preimages-and-history-admitted')
            for item in plan['targets']:
                if s.context!=opaque.PROMPT:
                    rec();t.transport.recovery_usb(s.link);s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda v:print(board+': '+v,flush=True))
                bank=item['bank'];page=int(item['address'],16)>>8
                before=wire.read_sector(bank,page);after=(SCOPE/board/item['file']).read_bytes()
                assert t.sha(before)==item['before_sha256'] and t.sha(after)==item['sha256']
                assert before!=after and (bank,page) in ((2,0x80),(2,0xA0),(2,0xF0),(3,0xA0),(3,0xB0))
                r.update(phase=f'replace-B{bank}-{page:02X}',image_erase_requests=r['image_erase_requests']+1);save()
                mark(firmware_verification_pending=True);s.context=None
                assert not wire.replace_sector(bank,page,before,after)
                s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==after
                r['completed'].append(dict(bank=bank,address=item['address'],sha256=t.sha(after)));save()
                check(f'installed-B{bank}-{page:02X}')
                if (bank,page)==(3,0xA0):
                    rec();face('A');assert b'flags $' in s.command('TIME');check('ROM-A-status-and-TIME');rec()
            rec();out=face('B');assert b'MONITOR B gen 0000000C VALID' in out
            for command in ('VERSION','TIME','M1','W','APPS'):
                out=s.command(command)
                assert b'STATUS tools unavailable' not in out
                if command=='TIME':assert b'flags $' in out and b'/ MON ' not in out
            check('ROM-B-status-TIME-and-existing-readonly-tools')
            if board=='2512':
                # Current policy remains within stage0; CLOCK latches only stage
                # advances. No SET/ACK/policy command, and sector9 is checked exact.
                s.command('R CLOCK',(t.CLOCK,));out=s.command('VERSION')
                assert b'g0000000C / MON B' in out and b'RTCC: ' in out
                s.command('Q',(t.MON,));check('native-CLOCK-VERSION-and-quiet-return')
                s.command('R FLASH',(d.FT,));s.command('BANK 0');s.command('READ 8000')
                views=[s.command(f'VIEW {page:03X}') for page in range(0,4096,256)]
                s.command('VERSION')
                assert [s.command(f'VIEW {page:03X}') for page in range(0,4096,256)]==views
                s.command('Q',(t.MON,))
                buffer=(s.dump(0x6800,0x69FF),s.dump(0x6B00,0x77FF));s.command('VERSION')
                assert (s.dump(0x6800,0x69FF),s.dump(0x6B00,0x77FF))==buffer
                check('active-FLASH-VERSION-preserves-4K-and-MON-keeps-non6A-buffer')
                rec();t.transport.recovery_usb(s.link);s.load(config,t.sha(config),CONFIG)
                assert b'DEFAULT=B' in s.command('B')
                out=s.command('C B');assert b'OK' in out and b'REFUSED' not in out
                s.command('Q',(t.MON,));assert b'g0000000C / MON B' in s.command('V')
                check('existing-B-choice-bound-to-gC-and-software-default-boot')
            rec();s.service(reader)
            final2=s.client.flash(2);final3=s.client.flash(3)
            assert t.sha(final2)==plan['final_B2_sha256']
            assert final3[:0x2000]==before3[:0x2000] and final3[0x6000:]==before3[0x6000:]
            for item in plan['targets']:
                if item['bank']==3:
                    a=int(item['address'],16)-0x8000;assert t.sha(final3[a:a+4096])==item['sha256']
            start=0x5000 if board=='2512' else 0x4000
            for off in range(start,0x6000,256):
                old=before3[off:off+256]
                if old!=b'\xff'*256:assert final3[off:off+256]==old
            j=t.classify_journal(final3)
            for key,expected in [('sequence',plan['expected_sequence_after']),('valid_records',plan['expected_valid_records_after']),
                                 ('counts',plan['counts_after']),('default',plan['boot_default_after']),
                                 ('enabled_mask',plan['enabled_mask']),('entries',plan['entries']),('unknown_mask',plan['unknown_mask'])]:
                assert j[key]==expected,(key,j[key],expected)
            if board=='2512':
                rows=[final3[o:o+256] for o in range(0x4000,0x6000,256) if final3[o:o+4]==b'SNBT' and int.from_bytes(final3[o+8:o+12],'little')==j['sequence']]
                assert len(rows)==1 and int.from_bytes(rows[0][0x12:0x16],'little')==12
            opaque.durable_file(CASE/'B2-after.bin',final2);opaque.durable_file(CASE/'B3-after.bin',final3)
            r.update(journal=j,final_B2_sha256=t.sha(final2),final_B3_sha256=t.sha(final3),NVM_verified=True)
            check('all-reviewed-postimages-history-policy-and-counts')
        finally:
          try:
            if borrowed and s.context is not None:
                if s.context!=SERVICE:rec();s.service(reader)
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if board=='2512':face('B')
                r.update(owner_RAM_restored=True,owner_ZP_restored=True)
          finally:
            if s is not None:s.link.close();r.update(port_released=True,final_prompt=s.context.decode() if s.context else None)
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];verified=r.get('NVM_verified',False)
                fields=dict(status_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                    firmware_verification_pending=not verified if r['image_erase_requests'] else marker.get('firmware_verification_pending',False),
                    last_STATUS_install=str(CASE/'report.json'))
                if verified:
                    hashes=marker['current_physical_bank_sha256'].copy();hashes.update(B2=r['final_B2_sha256'],B3=r['final_B3_sha256'])
                    fields.update(monitor_generation='0000000C',current_physical_bank_sha256=hashes,
                        current_journal_sequence=r['journal']['sequence'],current_journal_valid_records=r['journal']['valid_records'],
                        status_installation_complete=False,status_physical_boot_pending=True,
                        state='MON-gC-STATUS-software-accepted-physical-pending',final_prompt='B3>' if board=='2512' else 'REC>')
                mark(**fields)
            save()
      r.update(passed=r.get('NVM_verified',False) and r['owner_RAM_restored'],phase='ROM_SOFTWARE_PASSED_PHYSICAL_BOOT_PENDING',finished_utc=t.utc());save()
      print(json.dumps(r,indent=2),flush=True)
    except BaseException as error:r.update(error=repr(error),finished_utc=t.utc());save();raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True);a=p.parse_args();run(a.board)
