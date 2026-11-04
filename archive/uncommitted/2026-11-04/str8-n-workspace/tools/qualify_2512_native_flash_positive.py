"""Real BYTE/edited WRITE/ERASE on admitted B0:9; restore original all-FF."""
import json
import install_2512_native_utilities as d

t=d.t;BASE=d.BASE;CASE=BASE/'FLASH-positive';FT=d.FT;SERVICE=d.SERVICE

def run():
    prior=BASE/'flash-to-PROGRAM/resume-r1'
    assert json.loads((prior/'report.json').read_text())['passed']
    CASE.mkdir(exist_ok=False)
    # Native rotation will compact C. Retain its complete current raw history.
    before=(prior/'final-B3.bin').read_bytes()
    (CASE/'journal-CD-before.bin').write_bytes(before[0x4000:0x6000])
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',passed=False,target='B0:9, restore FF',F_writes=0,
        target_erase_requests=0,native_C_rotation_erases=1,RTC_writes=0,SRAM_writes=0,
        owner_RAM_restored=False,owner_ZP_restored=False,flash_restore_pending=False,checks=[])
    def checkpoint():t.save(CASE/'report.json',report)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False
    with t.serial_lease('2512-requested-native-FLASH-positive',timeout=180):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                s.command('R FLASH',(FT,t.MON));assert s.context==FT
                s.command('BANK 0');s.command('READ 9000')
                assert b'0000  FF FF' in s.command('VIEW 000')
                s.command('BYTE 9000 FE',(b'type YES> ',FT));assert s.context==b'type YES> '
                report['flash_restore_pending']=True;checkpoint()
                assert b'OK' in s.command('YES',(FT,))
                s.command('READ 9000');assert b'0000  FE FF' in s.command('VIEW 000')
                report['checks'].append('BYTE-1-to-0-readback');checkpoint();print('PASS BYTE',flush=True)
                s.command('EDIT 000 12 34');s.command('WRITE',(b'type YES> ',FT))
                assert s.context==b'type YES> '
                report['target_erase_requests']=1;checkpoint()
                assert b'OK: verified sector' in s.command('YES',(FT,))
                s.command('READ 9000');assert b'0000  12 34' in s.command('VIEW 000')
                report['checks'].append('WRITE-edited-4K-buffer-verified');checkpoint();print('PASS edited WRITE',flush=True)
                s.command('ERASE 9000',(b'type YES> ',FT));assert s.context==b'type YES> '
                report['target_erase_requests']=2;checkpoint()
                assert b'OK: verified sector' in s.command('YES',(FT,))
                report['flash_restore_pending']=False;checkpoint()
                s.command('READ 9000');assert b'0000  FF FF' in s.command('VIEW 000')
                s.command('Q',(t.MON,));report['checks'].append('ERASE-original-sector-restored');checkpoint();print('PASS ERASE and Q',flush=True)
                s.rec();s.service(reader)
                b3=s.client.flash(3);(CASE/'final-B3.bin').write_bytes(b3)
                j=t.classify_journal(b3)
                assert j['sequence']==1063 and j['counts'][1]==18 and j['counts'][28:]==[54,34,29,24]
                report['journal']=j
            finally:
                try:
                    if borrowed and s is not None:
                        if s.context==b'type YES> ':s.command('NO',(FT,))
                        s.monitor() if s.context!=SERVICE else None
                        if s.context!=SERVICE:s.rec();s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        assert b'REFUSED' not in s.command('!M 6A20 01')
                        report['EDU_session_ON']=True
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                        application_ram_restored=restored,block_snapshot=not restored or report['flash_restore_pending'],
                        native_FLASH_restore_pending=report['flash_restore_pending'],
                        last_native_FLASH_positive=str(CASE/'report.json'),final_prompt='B3>')
                    checkpoint()
    report['passed']='journal' in report and report['owner_RAM_restored'];checkpoint();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
