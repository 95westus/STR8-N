"""Install the RAM-qualified native HOST prompt fix at B2:E/F only."""
import json
import install_2512_native_utilities as d
import nf_opaque as opaque

t=d.t;BASE=d.BASE;CASE=BASE/'HOST-install-r8';FT=d.FT;SERVICE=d.SERVICE

def run():
    assert json.loads((BASE/'HOST-RAM-r8/report.json').read_text())['passed']
    CASE.mkdir(exist_ok=False)
    old=(t.REPO/'monitors/candidates/native-g00000001-r7/FLASH-MAINT-g00000001-flash.bin').read_bytes()
    image=(t.REPO/'monitors/candidates/native-g00000001-r8/FLASH-MAINT-g00000001-flash.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    report=dict(board='2512',passed=False,image_erases=0,F_writes=0,C_D_erases=0,
        RTC_writes=0,SRAM_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    def checkpoint():t.save(CASE/'report.json',report)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False
    def rec():
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    with t.serial_lease('2512-native-HOST-r8-install',timeout=180):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                rec();t.transport.recovery_usb(s.link);s.load(writer,t.sha(writer),opaque.PROMPT)
                wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda v:print(v,flush=True))
                for n in range(2):
                    page=0xE0+16*n;before=wire.read_sector(2,page);assert before==old[n*4096:(n+1)*4096]
                    (CASE/f'B2-{page:02X}-before.bin').write_bytes(before)
                    body=image[n*4096:(n+1)*4096]
                    report['image_erases']+=1;checkpoint();s.context=None
                    assert not wire.replace_sector(2,page,before,body)
                    s.context=opaque.PROMPT;assert wire.read_sector(2,page)==body
                rec();s.monitor();s.command('R FLASH',(FT,t.MON));assert s.context==FT
                s.command('HOST',(opaque.PROMPT,))
                wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda v:print(v,flush=True))
                blank=wire.read_sector(0,0x90);assert blank==b'\xff'*4096
                assert wire.replace_sector(0,0x90,blank,blank)
                wire.send(b'Q\r');wire.text_until(FT);s.context=FT
                assert b'DEFAULT=B' in s.command('BOOT')
                s.command('Q',(t.MON,));report['HOST_read_identical_replace_and_Q_passed']=True
                rec();s.service(reader);b3=s.client.flash(3);(CASE/'final-B3.bin').write_bytes(b3)
                j=t.classify_journal(b3);assert j['sequence']==1065 and j['counts'][22:24]==[19,14] and j['counts'][28:]==[54,34,29,24]
                report['journal']=j
            finally:
                try:
                    if borrowed:
                        rec();s.service(reader);report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        assert b'REFUSED' not in s.command('!M 6A20 01')
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                         application_ram_restored=restored,block_snapshot=not restored,
                         last_native_HOST_r8=str(CASE/'report.json'),final_prompt='B3>')
                    checkpoint()
    report['passed']='journal' in report and report['owner_RAM_restored'];checkpoint();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
