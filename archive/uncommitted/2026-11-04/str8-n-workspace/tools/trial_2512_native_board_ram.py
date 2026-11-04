"""One fresh owner-RAM escrow and native FLASH/BOOT RAM trial; no flash writes."""
import json
import re
from pathlib import Path
import preflight_program_apps_20261030 as p

t = p.t
CASE = t.ROOT/'output/qualification/2512-native-utilities-20261030-r1/ram-trial'
FT = b'FLASH/MAINT> '


def run():
    CASE.mkdir(exist_ok=False)
    report = dict(board='2512', passed=False, phase='prepared', flash_writes=0,
                  journal_writes=0, SRAM_writes=0, RTC_writes=0, F_writes=0,
                  full_board_backup_passes=0, owner_RAM_restored=False, owner_ZP_restored=False)
    t.save(CASE/'report.json', report)
    native = t.REPO/'monitors/candidates/native-g00000001-r5'
    app = (native/'FLASH-MAINT-g00000001-RAM.bin').read_bytes()
    build = t.ROOT/'BUILD/native-apps-g1-r5'
    sy = {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$', (build/'native-loader.map').read_text(), re.M)}
    loader = (native/'RTC-BASE1-B3-8000.bin').read_bytes()[0xC00:]
    ret = loader[sy['NL_RETURN_IMAGE']-0x7000:sy['NL_RETURN_IMAGE']-0x7000+512]
    assert len(ret)==512 and len(app)==6573
    packet = bytearray(b'\xff'*0x5E00)
    packet[:22] = bytes.fromhex('78 D8 A2 00 BD 00 6A 9D 00 5D BD 00 00 9D 00 5C E8 D0 F1 4C 00 20')
    packet[0x1E00:0x1E00+len(app)] = app
    packet[0x5C00:0x5E00] = ret
    packet = bytes(packet)
    (CASE/'RAM-trial.bin').write_bytes(packet)
    reader = (t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    borrowed = False
    s = None
    ram = zp = None
    marker = json.loads(t.MARK.read_text())
    def mark(**fields):
        current=json.loads(t.MARK.read_text());current.update(fields);t.save(t.MARK,current)
    def checkpoint():t.save(CASE/'report.json',report)
    with t.serial_lease('2512-native-utilities-RAM-only', timeout=30):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=p.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                assert b'g00000008 / MON B' in s.command('V')
                ram,zp=s.owner()
                (CASE/'owner-ram.bin').write_bytes(ram);(CASE/'owner-zp.bin').write_bytes(zp)
                report.update(phase='fresh-single-native-owner-escrow', owner_RAM_sha256=t.sha(ram), owner_ZP_sha256=t.sha(zp))
                # Only the journal and RTC metadata need preservation for the new layout.
                (CASE/'journal-CD.bin').write_bytes(s.dump(0xC000,0xDFFF))
                (CASE/'RTC-metadata.bin').write_bytes(s.dump(0x9C00,0x9FFF))
                checkpoint()
                mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;s.rec();t.transport.recovery_usb(s.link)
                s.load(packet,t.sha(packet),FT)
                out=s.command('VERSION');assert b'W65C02SXB' in out and b'Rev D' in out
                out=s.command('?');assert b'ERASE' in out and b'EDIT' in out and b'BOOT' in out
                out=s.command('BOOT');assert b'DEFAULT=B' in out
                s.command('BANK 0');s.command('READ 9000')
                out=s.command('VIEW 000');assert b'0000  FF FF' in out
                s.command('EDIT 000 12 34');out=s.command('VIEW 000');assert b'0000  12 34' in out
                out=s.command('WRITE',(b'type YES> ',));assert b'B0:9000' in out
                out=s.command('NO',(FT,));assert b'Canceled' in out
                s.command('READ 9000');out=s.command('VIEW 000');assert b'0000  FF FF' in out
                out=s.command('BYTE 9000 FE',(b'type YES> ',));assert b'B0:9000=FE' in out
                assert b'Canceled' in s.command('NO',(FT,))
                s.command('ERASE 9000',(b'type YES> ',));assert b'Canceled' in s.command('NO',(FT,))
                # Protected targets are refused before a confirmation or writer call.
                s.command('BANK 3');out=s.command('READ F000');assert b'REFUSED' in out
                for cmd in ('BYTE C000 00','ERASE D000'):
                    assert b'REFUSED' in s.command(cmd)
                s.command('Q',(t.MON,))
                assert s.dump(0xC000,0xDFFF)==(CASE/'journal-CD.bin').read_bytes()
                report.update(phase='RAM-commands-passed',commands_passed=['VERSION','BOOT show','READ/VIEW','EDIT RAM','WRITE cancel','BYTE cancel','ERASE cancel','C/D/F refusal','Q MON'])
                checkpoint()
            finally:
                try:
                    if borrowed and s is not None:
                        if s.context==FT:s.command('Q',(t.MON,))
                        if s.context==t.MON:s.rec()
                        assert s.context==t.REC,'Unknown program; do not guess a restoration command'
                        t.transport.recovery_usb(s.link);s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    if borrowed:
                        restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                        mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                             application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True)
                    checkpoint()
    report['passed']=report['phase']=='RAM-commands-passed' and report['owner_RAM_restored']
    checkpoint();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':run()
