"""One B3:8 loader repair, then actual native app and PROGRAM admission."""
import json
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque

t=d.t;BASE=d.BASE;CASE=BASE/'loader-repair-r6';FT=d.FT;SERVICE=d.SERVICE

def run():
    assert json.loads((BASE/'loader-recovery/report.json').read_text())['passed']
    CASE.mkdir(exist_ok=False)
    before_image=(t.REPO/'monitors/candidates/native-g00000001-r5/RTC-BASE1-B3-8000.bin').read_bytes()
    image=(t.REPO/'monitors/candidates/native-g00000001-r6/RTC-BASE1-B3-8000.bin').read_bytes()
    assert before_image[:0xC00]==image[:0xC00]
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    report=dict(board='2512',passed=False,erase_requests=0,F_writes=0,C_D_erases=0,power_cuts=0,
                RTC_SET=0,PF_ACK=0,SRAM_data_writes=0,owner_RAM_restored=False,owner_ZP_restored=False,checks=[])
    def checkpoint():t.save(CASE/'report.json',report)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    def check(name):report['checks'].append(name);checkpoint();print('PASS '+name,flush=True)
    s=None;borrowed=False
    def rec():
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    checkpoint()
    with t.serial_lease('2512-native-loader-one-sector-repair',timeout=30):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                assert b'g0000000A / MON B' in s.command('VERSION')
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                rec();t.transport.recovery_usb(s.link);s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda line:print(line,flush=True))
                before=wire.read_sector(3,0x80);assert before==before_image
                (CASE/'B3-8-before.bin').write_bytes(before)
                report['erase_requests']=1;checkpoint();s.context=None
                assert not wire.replace_sector(3,0x80,before,image)
                s.context=opaque.PROMPT;assert wire.read_sector(3,0x80)==image
                rec();s.monitor();check('one-sector-loader-repair')
                out=s.command('R MAINT',(FT,t.MON));assert s.context==FT
                assert b'DEFAULT=B' in s.command('BOOT')
                assert b'OK' in s.command('BOOT C B')
                report['default_B_generation_bound']='0000000A'
                out=s.command('Q',(t.MON,));assert b'/ MON B' not in out
                check('R-MAINT-BOOT-save-and-quiet-return')
                out=s.command('R FLASH',(FT,t.MON));assert s.context==FT
                assert b'W65C02SXB' in s.command('VERSION')
                s.command('BANK 0');s.command('READ 9000')
                assert b'0000  FF FF' in s.command('VIEW 000')
                s.command('Q',(t.MON,));check('installed-R-FLASH-and-sector-display')
                out=s.command('R CLOCK',(t.CLOCK,t.MON));assert s.context==t.CLOCK and b'CLOCK 1.10' in out
                assert b'Board:' in out
                out=s.command('STATUS');assert b'raw' in out.lower()
                out=s.command('VERSION');assert b'g0000000A / MON B' in out
                out=s.command('SET 2000-02-30 12:00:00');assert b'Invalid command/date' in out
                out=s.command('SET 2026-10-30 12:00:00',(b'Type YES to confirm: ',t.CLOCK));assert s.context==b'Type YES to confirm: '
                assert b'Canceled' in s.command('NO',(t.CLOCK,))
                s.command('Q',(t.MON,));check('full-CLOCK-STATUS-VERSION-invalid-and-canceled-SET')
                s.command('MAINT',(t.WB,t.MON));assert s.context==t.WB
                assert b'SSRAM PROGRAM:' in s.mount()
                for command in ('WORK','TABLE P'):
                    out=s.command(command);assert b'REFUSED' not in out
                assert b'BATCH done' in s.command('BATCH VERSION;TIME')
                s.command('Q',(t.MON,));check('EDU-ON-SRAM-WORK-TABLE-and-BATCH')
                rec();s.service(reader)
                b3=s.client.flash(3);(CASE/'final-B3.bin').write_bytes(b3)
                j=t.classify_journal(b3)
                assert j['default']=='B' and j['enabled_mask']==15 and j['entries']==[8]*4
                assert j['counts'][24:]==[22,17,42,49,53,34,29,24]
                assert j['sequence']==1057
                assert t.sha(b3[0x7000:])==json.loads((t.REPO/'F_FREEZE.json').read_text())['sha256']
                report['journal']=j;check('golden-F-boot-policy-and-wear-history')
            finally:
                try:
                    if borrowed and s is not None:
                        if s.context==b'Type YES to confirm: ':s.command('NO',(t.CLOCK,))
                        rec();s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        assert b'REFUSED' not in s.command('!M 6A20 01')
                        report['EDU_session_ON']=True
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                        application_ram_restored=restored,block_snapshot=not restored,
                        firmware_verification_pending='journal' not in report,
                        last_native_loader_repair=str(CASE/'report.json'),final_prompt='B3>')
                    checkpoint()
    report['passed']='journal' in report and report['owner_RAM_restored'];checkpoint()
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
