"""Move a tiny flash record into PROGRAM through real STORE/RESTORE commands.

The backed-up blank B0:9 is restored with one tracked erase after the PROGRAM
copy is loaded/run successfully. Existing CLK/CLOCK records are retained.
"""
import json,re,argparse
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque

t=d.t;BASE=d.BASE;CASE=BASE/'flash-to-PROGRAM';FT=d.FT;SERVICE=d.SERVICE
DEMO=bytes.fromhex('A9 50 20 6D 7E 4C 67 7E') # LDA#'P'; JSR RAM PUTC; JMP public HOLD

class Session(d.Session):
    def until(self,tokens,seconds=45):
        expanded=tuple(tokens)+(b'B0> ',b'B1> ',b'B2> ') if t.MON in tokens else tokens
        out=super().until(expanded,seconds)
        if self.context in (b'B0> ',b'B1> ',b'B2> ') and t.MON in tokens:
            self.link.send(b'B3\r');out+=super().until((t.MON,),seconds)
        return out

def run(resume=False):
    global CASE
    prior=CASE
    if resume:
        assert json.loads((prior/'report.json').read_text())['flash_restore_pending']
        CASE=prior/'resume-r1'
    assert json.loads((BASE/'loader-repair-r7/report.json').read_text())['passed']
    CASE.mkdir(exist_ok=False)
    ram=(BASE/'ram-trial/owner-ram.bin').read_bytes();zp=(BASE/'ram-trial/owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',passed=False,source_flash='B0:9000-9FFF, previously blank',
        destination='PROGRAM $9000, new NFCOPY record; invalid slot7 may be reused',
        retained_existing=['CLK','CLOCK'],WORKSPACE_writes=0,RTC_writes=0,F_writes=0,
        flash_restore_pending=False,flash_erase_requests=0,owner_RAM_restored=False,owner_ZP_restored=False,checks=[])
    def checkpoint():t.save(CASE/'report.json',report)
    def check(name):report['checks'].append(name);checkpoint();print('PASS '+name,flush=True)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    s=None;borrowed=False
    def rec():
        if s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    def raw(address):
        out=s.command(f'SRAM READ 0 {address:04X}')
        m=re.search(rb'RAW64 ([0-9A-F ]+)\r',out)
        assert m,'Missing RAW64 response'
        body=bytes.fromhex(m[1].decode());assert len(body)==64
        return body
    def maint():
        s.monitor();s.command('MAINT',(t.WB,t.MON));assert s.context==t.WB
        s.mount()
    checkpoint()
    with t.serial_lease('2512-requested-flash-to-PROGRAM-move',timeout=180):
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                borrowed=True;mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                # The source is an existing admitted disposable sector, restored
                # after copy. No owner image or program is selected for deletion.
                if not resume:
                    s.command('R FLASH',(FT,t.MON));assert s.context==FT
                    s.command('BANK 0');s.command('READ 9000')
                    assert b'0000  FF FF' in s.command('VIEW 000')
                    s.command('Q',(t.MON,))
                    s.modify(0x3000,DEMO)
                else:
                    report['flash_restore_pending']=True
                maint()
                table=s.command('TABLE P');assert b'NFCOPY' not in table
                (CASE/'PROGRAM-table-before.txt').write_bytes(table)
                header_before=raw(0);slot_before=raw(0x200);payload_before=raw(0x9000)
                (CASE/'PROGRAM-header-before.bin').write_bytes(header_before)
                (CASE/'PROGRAM-slot7-before.bin').write_bytes(slot_before)
                (CASE/'PROGRAM-payload9000-before.bin').write_bytes(payload_before)
                if not resume:
                    s.command('AREA 0 9000 9FFF')
                    s.command('STORE 0 AUTO 3000 3007 NFCOPY',(b'type YES> ',t.WB))
                    assert s.context==b'type YES> '
                    report['flash_restore_pending']=True;checkpoint()
                    out=s.command('YES',(t.WB,));assert b'REFUSED' not in out and b'Stored' in out
                s.command('RESTORE 0 NFCOPY L')
                # Read source via the monitor only after returning from shell.
                s.command('Q',(t.MON,));assert s.dump(0x3000,0x3007)==DEMO
                maint()
                out=s.command('STORE P 9000 3000 3007 NFCOPY',(b'type YES> ',t.WB))
                assert s.context==b'type YES> ' and b'Target PROGRAM $9000' in out
                assert b'Stored PROGRAM; CRC verified; commit last' in s.command('YES',(t.WB,))
                table_after=s.command('TABLE P');assert b'NFCOPY' in table_after
                assert all(row in table_after for row in table.split(b'\r\n') if row.startswith((b'P:05/',b'P:06/')))
                (CASE/'PROGRAM-table-after.txt').write_bytes(table_after)
                assert raw(0)==header_before
                payload_after=raw(0x9000);assert payload_after[:8]==DEMO and payload_after[8:]==payload_before[8:]
                s.command('RESTORE P NFCOPY L')
                s.command('Q',(t.MON,));assert s.dump(0x3000,0x3007)==DEMO
                maint();out=s.command('RESTORE P NFCOPY',(t.MON,t.WB))
                assert s.context==t.MON and b'P\r' in out and b'g0000000A / MON B' in out
                check('flash-STORE-RESTORE-to-PROGRAM-STORE-RESTORE-and-run')
                # Source retirement happens only after the destination worked.
                s.command('R FLASH',(FT,t.MON));assert s.context==FT
                s.command('BANK 0');s.command('ERASE 9000',(b'type YES> ',FT));assert s.context==b'type YES> '
                report['flash_erase_requests']=1;checkpoint()
                assert b'OK: verified sector' in s.command('YES',(FT,))
                report['flash_restore_pending']=False;checkpoint()
                s.command('READ 9000');assert b'0000  FF FF' in s.command('VIEW 000')
                s.command('Q',(t.MON,));check('FLASH-erase-restores-original-source-sector-after-verified-copy')
                maint();out=s.command('RESTORE 0 NFCOPY L');assert b'No complete' in out
                out=s.command('RESTORE NFCOPY',(t.MON,t.WB));assert s.context==t.MON and b'g0000000A / MON B' in out
                check('automatic-PROGRAM-restore-run-after-flash-source-removed')
                rec();s.service(reader);b3=s.client.flash(3);(CASE/'final-B3.bin').write_bytes(b3)
                j=t.classify_journal(b3);assert j['sequence']==1060 and j['counts'][1]==16 and j['counts'][28:]==[53,34,29,24]
                report['journal']=j;report['PROGRAM_NFCOPY_retained']=True
            finally:
                try:
                    if borrowed:
                        if s.context==b'type YES> ':s.command('NO',(t.WB,FT,t.MON))
                        if report['flash_restore_pending']:
                            rec();t.transport.recovery_usb(s.link)
                            writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
                            s.load(writer,t.sha(writer),opaque.PROMPT)
                            wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda v:print(v,flush=True))
                            before=wire.read_sector(0,0x90)
                            if before!=b'\xff'*4096:
                                report['flash_erase_requests']+=1;checkpoint()
                                s.context=None;wire.replace_sector(0,0x90,before,b'\xff'*4096);s.context=opaque.PROMPT
                                assert wire.read_sector(0,0x90)==b'\xff'*4096
                            s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
                            report['flash_restore_pending']=False
                        rec();s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        assert b'REFUSED' not in s.command('!M 6A20 01')
                        report['EDU_session_ON']=True
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                        application_ram_restored=restored,block_snapshot=not restored or report['flash_restore_pending'],
                        last_flash_to_PROGRAM=str(CASE/'report.json'),final_prompt='B3>')
                    checkpoint()
    report['passed']='journal' in report and report['owner_RAM_restored'];checkpoint();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args();run(args.resume)
