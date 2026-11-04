"""Install the owner's requested native utilities on2512; F is excluded."""
import json
from pathlib import Path
import preflight_program_apps_20261030 as p
import nf_opaque as opaque

t=p.t
BASE=t.ROOT/'output/qualification/2512-native-utilities-20261030-r1'
CASE=BASE/'installation'
RAM=BASE/'ram-trial'
FT=b'FLASH/MAINT> '
SERVICE=b'RAM SERVICE BASE1> '


class Session(p.Session):
    def monitor(self):
        if self.context in (FT,t.CLOCK,t.WB):self.command('Q',(t.MON,))
        if self.context==t.REC:self.command('B',(t.MON,))
        assert self.context==t.MON


def images():
    repo=t.REPO
    mon=repo/'monitors/candidates/g0000000a-ui1'
    mm=json.loads((mon/'manifest.json').read_text())
    slots={a['variant']:(mon/n).read_bytes() for n,a in mm['artifacts'].items()}
    svc=repo/'monitors/candidates/services-g00000006-native-r3'
    sm=json.loads((svc/'manifest.json').read_text())
    parts={a['variant']:(svc/n).read_bytes() for n,a in sm['artifacts'].items()}
    native=repo/'monitors/candidates/native-g00000001-r5'
    rtc=(native/'RTC-HISTORY-B3-9000.bin').read_bytes()[:3072]+(RAM/'RTC-metadata.bin').read_bytes()
    clock=(native/'CLOCK-g00000001-flash.bin').read_bytes()
    flash=(native/'FLASH-MAINT-g00000001-flash.bin').read_bytes()
    # Leave old B as a fallback while testing new A's basic console.
    steps=[('MON-A',3,0xA0,slots['A']),('RTC',3,0x80,(native/'RTC-BASE1-B3-8000.bin').read_bytes()),
           ('HISTORY',3,0x90,rtc)]
    steps += [(f'CLOCK-{n}',2,0xB0+16*n,clock[4096*n:4096*(n+1)]) for n in range(3)]
    steps += [(f'FLASH-MAINT-{n}',2,0xE0+16*n,flash[4096*n:4096*(n+1)]) for n in range(2)]
    bundle=parts['B2 bundle']
    old=t.ROOT/'output/qualification/2512-AP02-g4-trial-20261030-r1/final-pass1-B2.bin'
    assert bundle[8192:12288]==old.read_bytes()[8192:12288], 'B2:A must really be identical'
    steps += [('WB-8',2,0x80,bundle[:4096]),('WB-9',2,0x90,bundle[4096:8192]),
              ('SERVICES',3,0xE0,parts['E']),('MON-B',3,0xB0,slots['B'])]
    assert len(steps)==12 and all(len(b)==4096 and not (bank==3 and page in (0xC0,0xD0,0xF0)) for _,bank,page,b in steps)
    return steps


def run():
    assert json.loads((RAM/'report.json').read_text())['passed']
    steps=images();CASE.mkdir(exist_ok=False)
    report=dict(board='2512',passed=False,phase='prepared',F_writes=0,full_board_backup_passes=0,
                power_cuts=0,RTC_SET=0,PF_ACK=0,SRAM_data_writes=0,WORKSPACE_writes=0,
                component_erase_requests=0,completed=[],owner_RAM_restored=False,owner_ZP_restored=False)
    t.save(CASE/'scope.json',dict(owner_direction='Fix utilities, put them on a board, then test; forgo repeated full-board backup/checksum passes',
        scope_review=str(t.REPO/'docs/2512_NATIVE_UTILITIES_SCOPE.md'),
        steps=[dict(label=label,bank=bank,page=f'{page:02X}',sha256=t.sha(b)) for label,bank,page,b in steps],
        component_erases=12,native_D_rotation_erases=1,F_writes=0,bind_default_B_generation='0000000A'))
    ram,zp=(RAM/'owner-ram.bin').read_bytes(),(RAM/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
    marker=json.loads(t.MARK.read_text());s=None;borrowed=False
    def checkpoint():t.save(CASE/'report.json',report)
    def mark(**kw):
        m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
    def check(name):report.setdefault('checks',[]).append(name);checkpoint();print('PASS '+name,flush=True)
    def rec():
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC,seconds=15);s.context=t.REC
        elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:s.rec()
    checkpoint()
    with t.serial_lease('2512-requested-native-utilities-install',timeout=30):
        assert not marker['block_snapshot'] and not marker['application_RAM_restore_pending']
        t.save(CASE/'marker-before.json',marker)
        with (CASE/'serial.jsonl').open('x') as log:
            try:
                s=Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
                assert b'g00000008 / MON B' in s.command('V')
                mark(native_utility_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,
                     firmware_verification_pending=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link)
                for label,bank,page,body in steps:
                    if s.context!=opaque.PROMPT:
                        s.load(writer,t.sha(writer),opaque.PROMPT)
                    wire=opaque.Wire(s.link.serial,timeout=60,trace=log,progress=lambda line:print(label+': '+line,flush=True))
                    before=wire.read_sector(bank,page)
                    (CASE/(label+'-before.bin')).write_bytes(before)
                    (CASE/(label+'-target.bin')).write_bytes(body)
                    if label=='HISTORY':assert before[3072:]==body[3072:]
                    report.update(phase='replace-'+label,component_erase_requests=report['component_erase_requests']+(before!=body));checkpoint()
                    s.context=None
                    identical=wire.replace_sector(bank,page,before,body)
                    s.context=opaque.PROMPT
                    assert wire.read_sector(bank,page)==body
                    report['completed'].append(dict(label=label,bank=bank,page=f'{page:02X}',identical=identical));checkpoint()
                    print('INSTALLED '+label,flush=True)
                    if label=='MON-A':
                        rec();face=s.command('A',(t.MON,));assert b'g0000000A / MON A' in face
                        assert b'BASE1 / PR05' in s.command('VERSION')
                        out=s.command('TIME');assert b'RTCC: 20' in out and b'/ MON A' not in out
                        check('installed-A-VERSION-and-concise-TIME');rec();t.transport.recovery_usb(s.link)
                rec();face=s.command('B',(t.MON,));assert b'g0000000A / MON B' in face
                assert b'BASE1 / PR05' in s.command('VERSION')
                out=s.command('APPS');assert b'CLOCK MAINT FLASH' in out
                out=s.command('R MAINT',(FT,t.MON));assert s.context==FT
                assert b'DEFAULT=B' in s.command('BOOT')
                out=s.command('BOOT C B');assert b'OK' in out and b'REFUSED' not in out
                report['default_B_generation_bound']='0000000A';checkpoint()
                s.command('Q',(t.MON,));check('cold-R-MAINT-BOOT-default-binding-and-quiet-Q')
                out=s.command('R CLOCK',(t.CLOCK,t.MON));assert s.context==t.CLOCK and b'CLOCK 1.10' in out
                assert b'Board:' in out and b'Running' in out
                out=s.command('STATUS');assert b'raw' in out.lower() and b'REFUSED' not in out
                out=s.command('VERSION');assert b'g0000000A / MON B' in out
                out=s.command('SET 2000-02-30 12:00:00');assert b'Invalid command/date' in out
                out=s.command('SET 2026-10-30 12:00:00',(b'Type YES to confirm: ',t.CLOCK));assert s.context==b'Type YES to confirm: '
                assert b'Canceled' in s.command('NO',(t.CLOCK,))
                s.command('Q',(t.MON,));check('full-CLOCK-details-VERSION-invalid-SET-and-canceled-SET')
                out=s.command('R FLASH',(FT,t.MON));assert s.context==FT
                assert b'W65C02SXB' in s.command('VERSION');s.command('Q',(t.MON,))
                out=s.command('MAINT',(t.WB,t.MON));assert s.context==t.WB
                assert b'SSRAM PROGRAM:' in s.mount()
                for command in ('WORK','TABLE P'):
                    out=s.command(command);assert b'REFUSED' not in out and b'Error' not in out
                assert b'BATCH done' in s.command('BATCH VERSION;TIME')
                s.command('Q',(t.MON,));check('installed-FLASH-MAINT-EDU-SRAM-WORK-TABLE-BATCH')
                rec();s.service(reader)
                # Read only the journal, not another whole-board capture.
                after=s.client.flash(3)[0x4000:0x6000]
                (CASE/'journal-CD-after.bin').write_bytes(after)
                j=t.classify_journal(b'\xff'*0x4000+after+b'\xff'*0x2000)
                assert j['default']=='B' and j['enabled_mask']==15 and j['entries']==[8]*4
                assert j['counts'][28:]==[53,34,29,24]
                assert j['sequence']==1056
                report['journal']=j;check('boot-policy-and-native-wear-rotation')
            finally:
                try:
                    if borrowed and s is not None:
                        if s.context==b'Type YES to confirm: ':s.command('NO',(t.CLOCK,))
                        rec()
                        if s.context!=SERVICE:s.service(reader)
                        report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
                        report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                        # Session state is outside owner RAM; the next cold tool load retains EDU ON.
                        out=s.command('!M 6A20 01');assert b'REFUSED' not in out
                        report['EDU_session_ON']=True
                finally:
                    if s is not None:s.link.close();report['COM4_released']=True
                    restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                    mark(native_utility_worker_active=False,application_RAM_restore_pending=not restored,
                        application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                        firmware_verification_pending=len(report['completed'])!=12,
                        last_native_utility_install=str(CASE/'report.json'),final_prompt='B3>')
                    checkpoint()
    report.update(passed=len(report['completed'])==12 and 'journal' in report,phase='installed-ready-for-operator')
    checkpoint();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':run()
