"""Exercise the corrected banked loader in RAM before another sector write."""
import json
from pathlib import Path
import install_2512_native_utilities as d

t=d.t;BASE=d.BASE;CASE=BASE/'loader-RAM-r7';FT=d.FT;SERVICE=d.SERVICE

def packet(kind):
    build=t.ROOT/'BUILD/native-apps-g1-r7'
    loader=(build/'RTC-BASE1-B3-8000.bin').read_bytes()[0xC00:]
    ret=(build/'RTC-HISTORY-B3-9000.bin').read_bytes()[0xA00:0xC00]
    # Runtime logic is exact r7. Only the return-template source is staged in
    # RAM for this no-flash trial, since r7 history has not been installed yet.
    assert loader.count(bytes.fromhex('BD 00 9A'))==loader.count(bytes.fromhex('BD 00 9B'))==1
    loader=loader.replace(bytes.fromhex('BD 00 9A'),bytes.fromhex('BD 00 5E')).replace(bytes.fromhex('BD 00 9B'),bytes.fromhex('BD 00 5F'))
    out=bytearray(b'\xff'*0x700)
    code=bytearray(bytes.fromhex('78 D8 A2 00'))
    for source,destination in ((0x300,0x7000),(0x400,0x7100),(0x500,0x7200),(0x600,0x7300)):
        code+=b'\xbd'+source.to_bytes(2,'little')+b'\x9d'+destination.to_bytes(2,'little')
    code+=bytes.fromhex('E8 D0 E5 A2 00')
    for source,destination in ((0x700,0x5E00),(0x800,0x5F00)):
        code+=b'\xbd'+source.to_bytes(2,'little')+b'\x9d'+destination.to_bytes(2,'little')
    code+=bytes.fromhex('E8 D0 F1 A9')+bytes((kind,))+bytes.fromhex('4C 08 70')
    assert len(code)<256
    out[:len(code)]=code;out[0x100:0x500]=loader;out[0x500:0x700]=ret
    return bytes(out)


def run():
    assert json.loads((BASE/'loader-recovery-2b/report.json').read_text())['passed']
    CASE.mkdir(exist_ok=False)
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',passed=False,intentional_flash_writes=0,journal_writes=0,
                RTC_SET=0,PF_ACK=0,SRAM_data_writes=0,owner_RAM_restored=False,owner_ZP_restored=False,checks=[])
    def checkpoint():t.save(CASE/'report.json',report)
    def check(name):report['checks'].append(name);checkpoint();print('PASS '+name,flush=True)
    s=None;borrowed=False
    def rec():
        if s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    with t.serial_lease('2512-native-loader-RAM-before-flash',timeout=60,priority=True):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                rec();t.transport.recovery_usb(s.link)
                body=packet(1);(CASE/'FLASH-RAM-packet.bin').write_bytes(body)
                s.load(body,t.sha(body),FT)
                assert b'W65C02SXB' in s.command('VERSION')
                assert b'DEFAULT=B' in s.command('BOOT')
                s.command('BANK 0');s.command('READ 9000')
                assert b'0000  FF FF' in s.command('VIEW 000')
                s.command('Q',(t.MON,));check('RAM-loader-FLASH-ROM-to-RAM-copy-and-quiet-Q')
                rec();t.transport.recovery_usb(s.link)
                body=packet(0);(CASE/'CLOCK-RAM-packet.bin').write_bytes(body)
                s.load(body,t.sha(body),t.CLOCK)
                out=s.command('STATUS');assert b'raw' in out.lower()
                assert b'g0000000A / MON B' in s.command('VERSION')
                assert b'Invalid command/date' in s.command('SET 2000-02-30 12:00:00')
                s.command('SET 2026-10-30 12:00:00',(b'Type YES to confirm: ',t.CLOCK))
                assert s.context==b'Type YES to confirm: '
                assert b'Canceled' in s.command('NO',(t.CLOCK,))
                s.command('Q',(t.MON,));check('RAM-loader-full-CLOCK-STATUS-VERSION-and-SET-cancel')
            finally:
                try:
                    if borrowed:
                        if s.context==b'Type YES to confirm: ':s.command('NO',(t.CLOCK,))
                        rec();s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                         application_ram_restored=restored,block_snapshot=True,firmware_verification_pending=True)
                    checkpoint()
    report['passed']=len(report['checks'])==2 and report['owner_RAM_restored'];checkpoint();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
