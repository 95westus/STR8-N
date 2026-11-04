"""Qualify native HOST/OIP1 prompt lifecycle in RAM, with read-only requests."""
import json
import install_2512_native_utilities as d
import nf_opaque as opaque

t=d.t;BASE=d.BASE;CASE=BASE/'HOST-RAM-r8';FT=d.FT;SERVICE=d.SERVICE

def run():
    CASE.mkdir(exist_ok=False)
    build=t.ROOT/'BUILD/native-apps-g1-r8'
    app=(build/'FLASH-MAINT-g00000001-RAM.bin').read_bytes()
    ret=(build/'RTC-HISTORY-B3-9000.bin').read_bytes()[0xA00:0xC00]
    packet=bytearray(b'\xff'*0x5E00)
    code=bytes.fromhex('78 D8 A2 00 BD 00 6A 9D 00 5D BD 00 00 9D 00 5C E8 D0 F1 4C 00 20')
    packet[:len(code)]=code;packet[0x1E00:0x1E00+len(app)]=app;packet[0x5C00:]=ret
    packet=bytes(packet);ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    def checkpoint():t.save(CASE/'report.json',report)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False
    with t.serial_lease('2512-native-HOST-OIP1-RAM',timeout=180):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                s.rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),FT)
                s.command('HOST',(opaque.PROMPT,));assert s.context==opaque.PROMPT
                wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda v:print(v,flush=True))
                assert wire.read_sector(0,0x90)==b'\xff'*4096
                assert wire.read_sector(0,0x90)==b'\xff'*4096
                wire.send(b'Q\r');wire.text_until(FT);s.context=FT
                assert b'DEFAULT=B' in s.command('BOOT')
                s.command('Q',(t.MON,));report['HOST_two_reads_Q_to_FLASH_Q_to_MON']=True
            finally:
                try:
                    if borrowed:
                        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(FT);s.context=FT
                        if s.context!=t.REC:s.rec()
                        s.service(reader);report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        assert b'REFUSED' not in s.command('!M 6A20 01')
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                         application_ram_restored=restored,block_snapshot=not restored)
                    checkpoint()
    report['passed']=report.get('HOST_two_reads_Q_to_FLASH_Q_to_MON',False) and report['owner_RAM_restored'];checkpoint();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
