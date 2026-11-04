"""Requested positive 2512 PROGRAM trial, exactly restored; no flash writes."""
import argparse
import binascii
import json
import re
from pathlib import Path
import preflight_program_apps_20261030 as p
t=p.t
SCOPE=t.ROOT/'output/qualification/2512-PROGRAM-positive-scope-20261030-r1'


class Session(p.Session):
    def workbench(self):
        self.monitor()
        out=self.command('MAINT LOAD',(t.WB,t.MON))
        assert self.context==t.WB and b'WORKBENCH WB2 g00000005' in out
        self.mount()
    def bench(self):
        self.workbench(); self.rec()
        self.load(self.fixture,t.sha(self.fixture),t.PB)
    def raw(self,address):
        assert self.context==t.WB
        out=self.command(f'SRAM READ {address>>16} {address&65535:04X}')
        found=re.findall(rb'RAW64 ((?:[0-9A-F]{2} ){64})',out)
        assert len(found)==1
        return bytes.fromhex(found[0].decode())
    def block(self,address,body):
        assert self.context==t.PB and address in self.allowed and len(body)==64
        fields=bytes([0,address>>8,address&255]); crc=binascii.crc_hqx(fields+body,65535)
        out=self.command('W'+fields.hex().upper()+body.hex().upper()+f'{crc:04X}')
        assert f'O{crc:04X}\r\n'.encode() in out
        out=self.command('R'+fields.hex().upper())
        found=re.findall(rb'D([0-9A-F]{138})\r?\n',out); assert len(found)==1
        frame=bytes.fromhex(found[0].decode())
        assert frame[:3]==fields and frame[3:-2]==body
        assert binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
    def full(self,label):
        self.workbench()
        body=self.sram(self.fixture,label)
        self.workbench()
        return body
    def memory(self,address,body):
        self.monitor(); self.modify(address,body)


def run(folder):
    folder=folder.resolve(); assert folder.is_relative_to(t.ROOT/'output/qualification') and not folder.exists()
    plan=json.loads((SCOPE/'plan.json').read_text())
    assert plan['driver_sha256']==t.sha(Path(__file__).read_bytes())
    assert plan['board']=='2512' and plan['temporary_byte_scope']==1280
    assert plan['flash_writes']==plan['journal_writes']==0
    snapshot=(SCOPE/plan['original_SRAM']).read_bytes(); assert t.sha(snapshot)==plan['SRAM_sha256']
    fixture=(SCOPE/plan['restorer']['filename']).read_bytes(); assert t.sha(fixture)==plan['restorer']['sha256']
    fixtures={n:(SCOPE/f'PROGRAM-{n}-23.bin').read_bytes() for n in ('OK','UP')}
    assert {n:t.sha(v) for n,v in fixtures.items()}==plan['fixture_sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert t.sha(reader)==t.live.READBACK_SHA256
    folder.mkdir(parents=True); (folder/'.gitignore').write_text('*\n')
    (folder/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    t.save(folder/'authorization.json',dict(owner_request=plan['authorization'],plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()),
        temporary_byte_scope=1280,flash_writes=0,journal_writes=0))
    report=dict(board='2512',CPU='65C02',passed=False,started_utc=t.utc(),checks=[],stores=[],
        flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        power_cuts=0,firmware_builds=0,SRAM_restore_pending=False,owner_RAM_restored=False,
        plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()))
    s=None; borrowed=False; marker=None; ram=zp=None
    def save(): t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(t.MARK.read_text()); m.update(fields); t.save(t.MARK,m)
    def check(label):
        report['checks'].append(label); save(); print('PASS '+label,flush=True)
    def store(name,source,target):
        s.memory(source,fixtures['UP' if source==0x3020 else 'OK']); s.workbench()
        out=s.command(f'S P {target:04X} {source:04X} {source+22:04X} {name}',(b'type YES> ',t.WB))
        assert s.context==b'type YES> ' and f'Target PROGRAM ${target:04X}'.encode() in out
        report['SRAM_restore_pending']=True; mark(PROGRAM_SRAM_restore_pending=True); save()
        out=s.command('YES',(t.WB,)); assert b'Stored PROGRAM; CRC verified; commit last' in out
        report['stores'].append(dict(name=name,source=f'{source:04X}',target=f'{target:04X}'))
        check('store-'+name+'-'+f'{target:04X}')
    def restore_sram():
        s.bench()
        for a in s.allowed: s.block(a,snapshot[a:a+64])
        s.workbench()
        assert s.full('SRAM-restored')==snapshot
        report.update(SRAM_restore_pending=False,all_131072_SRAM_bytes_restored=True,SRAM_sha256=t.sha(snapshot))
        mark(PROGRAM_SRAM_restore_pending=False); check('complete-SRAM-restoration-and-equality')
    save()
    try:
        with t.serial_lease('2512-requested-PROGRAM-positive-trial',timeout=30):
            marker,_,_,_=t.inputs()
            assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==plan['source_bank_sha256']
            t.save(folder/'marker-before.json',marker)
            with (folder/'serial.jsonl').open('x') as log:
                try:
                    s=Session(folder,log,'2512'); s.fixture=fixture
                    s.allowed=[int(v,16) for v in plan['allowed_64_byte_writes']]
                    s.link.send(b'\r'); s.until((t.MON,),seconds=12)
                    assert b'CPU $02' in s.command('V')
                    ram,zp=s.owner(); assert s.owner()==(ram,zp)
                    (folder/'owner-ram.bin').write_bytes(ram); (folder/'owner-zp.bin').write_bytes(zp)
                    report.update(RAM_sha256=t.sha(ram),ZP_sha256=t.sha(zp)); check('fresh-native-owner-double-escrow')
                    borrowed=True
                    mark(program_trial_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                    s.rec(); t.transport.recovery_usb(s.link); s.service(reader)
                    assert s.client.read(b'M',0x6500)==reader+ram[len(reader):]
                    assert s.client.read(b'Z',0xe0)==zp
                    s.read_banks('before',plan['source_bank_sha256'])
                    s.client.restore_owner(ram,zp); s.context=t.REC
                    s.workbench(); assert s.full('SRAM-fresh-before')==snapshot
                    live=t.inspect_sram(snapshot)
                    assert all(a in [v['slot'] for v in live['free_slots']] for a in range(4))
                    actual_slots=[v['slot'] for v in reversed(live['free_slots'])][:4]
                    assert all(64*(a+1) in s.allowed for a in actual_slots), 'Restorer omits actual last-free directory slots; stop before Store'
                    assert all(f'{n:02X}' in live['free_pages'] for n in range(0xc0,0xc4))
                    assert b'NF30' not in s.command('T P')
                    check('fresh-full-SRAM-and-target-admission')
                    s.memory(0x3000,fixtures['OK']); s.workbench()
                    out=s.command('S P AUTO 3000 3016 NF30PROGRAM_LONG',(b'type YES> ',t.WB))
                    assert s.context==b'type YES> ' and b'Target PROGRAM $0800' in out
                    assert b'Canceled; no record written' in s.command('NO',(t.WB,))
                    for a in s.allowed: assert s.raw(a)==snapshot[a:a+64]
                    check('AUTO-0800-preview-NO-unchanged')
                    store('NF30PROGRAM_LONG',0x3000,0xc000)
                    store('NF30P',0x3000,0xc100)
                    store('NF30P',0x3020,0xc200)
                    store('NF30EX',0x3000,0xc300)
                    assert b'SSRAM error $43' in s.command('S P C000 3000 3016 NF30OVERLAP')
                    check('occupied-payload-refused')
                    assert b'NF30PROGRAM_LONG' in s.command('T P')
                    assert b'NF30P' in s.command('T')
                    s.memory(0x3020,b'\xaa'*23); s.workbench()
                    assert b'Loaded PROGRAM; payload CRC verified' in s.command('R P NF30P L')
                    s.monitor(); assert s.dump(0x3020,0x3036)==fixtures['UP']
                    check('latest-version-load-only-exact')
                    s.workbench(); out=s.command('R P NF30P',(t.MON,))
                    assert b'UP\r\n' in out and b'CPU $02' in out
                    check('positive-PROGRAM-run-public-HOLD-return')
                    s.workbench(); good=s.raw(0xc200); assert good[:23]==fixtures['UP']
                    s.bench(); s.block(0xc200,bytes([good[0]^1])+good[1:])
                    s.memory(0x3020,b'\xa5'*23); s.workbench()
                    assert b'SSRAM error $45' in s.command('R P NF30P L')
                    s.monitor(); assert s.dump(0x3020,0x3036)==b'\xa5'*23
                    check('payload-CRC-refused-before-destination-copy')
                    s.bench(); s.block(0xc200,good); s.workbench()
                    assert b'Loaded PROGRAM; payload CRC verified' in s.command('R P NF30P L')
                    s.monitor(); assert s.dump(0x3020,0x3036)==fixtures['UP']
                    check('CRC-repair-and-restore')
                finally:
                    try:
                        if borrowed and s.context==b'type YES> ': s.command('NO',(t.WB,))
                        try:
                            if report['SRAM_restore_pending']: restore_sram()
                        finally:
                            if borrowed:
                                if s.context!=b'RAM SERVICE BASE1> ': s.rec(); s.service(reader)
                                try:
                                    s.read_banks('after',plan['source_bank_sha256']); report['all_flash_banks_unchanged']=True
                                finally:
                                    result=s.client.restore_owner(ram,zp)
                                    report.update({k:v for k,v in result.items() if k not in ('owner_RAM_restored','owner_ZP_restored')})
                                    s.context=t.REC; s.monitor(); assert s.owner()==(ram,zp)
                                    report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close(); report['COM4_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        if marker is not None:
                            restored=report['owner_RAM_restored'] if borrowed else True
                            mark(program_trial_worker_active=False,application_RAM_restore_pending=not restored,
                                application_ram_restored=restored,PROGRAM_SRAM_restore_pending=report['SRAM_restore_pending'],
                                block_snapshot=marker['block_snapshot'] if restored and not report['SRAM_restore_pending'] else True,
                                last_PROGRAM_positive_trial=str(folder/'report.json'))
                        save()
        assert report['all_131072_SRAM_bytes_restored'] and report['owner_RAM_restored'] and report['all_flash_banks_unchanged']
        report.update(passed=True,phase='PROGRAM_65C02_PASSED',finished_utc=t.utc()); save()
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc()); save(); raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--folder',type=Path,required=True)
    run(parser.parse_args().folder)
