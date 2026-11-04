"""Restore only the exact backed-up 2512 slots4/7, then all owner RAM/ZP."""
import argparse
import binascii
import json
import re
from pathlib import Path
import trial_2512_program_positive as base
t=base.t
CASE=t.ROOT/'output/qualification/2512-PROGRAM-preserving-repair-20261030-r1'
FAILED=t.ROOT/'output/qualification/2512-PROGRAM-positive-trial-20261030-r1'
SCOPE=base.SCOPE


def run():
    plan=json.loads((CASE/'repair-plan.json').read_text())
    original_plan=json.loads((SCOPE/'plan.json').read_text())
    failure=json.loads((FAILED/'report.json').read_text());assert not failure['passed']
    assert failure['final_context']=='WORKBENCH> ' and failure['SRAM_restore_pending']
    fixture=(CASE/plan['restorer_filename']).read_bytes();assert t.sha(fixture)==plan['restorer_sha256']
    ram,zp=(FAILED/'owner-ram.bin').read_bytes(),(FAILED/'owner-zp.bin').read_bytes()
    assert t.sha(ram)==failure['RAM_sha256'] and t.sha(zp)==failure['ZP_sha256']
    snapshot=(SCOPE/original_plan['original_SRAM']).read_bytes()
    bad=(FAILED/'SRAM-restored-131072.bin').read_bytes()
    assert t.sha(snapshot)==plan['original_SRAM_sha256'] and t.sha(bad)==plan['observed_SRAM_sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    report=dict(board='2512',CPU='65C02',passed=False,started_utc=t.utc(),
        restoration_only_addresses=['0140','0200'],restoration_only_bytes=128,
        initial_temporary_scope_met=False,host_directory_planning_error=True,
        flash_writes=0,journal_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        firmware_builds=0,assembler_invocations=0,power_cuts=0,SRAM_restore_pending=True,owner_RAM_restored=False)
    s=None
    def save():t.save(CASE/'report.json',report)
    def mark(**fields):
        m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
    save();print('WAIT: preserving repair waits for active RTC collector; only COM4 will be used',flush=True)
    try:
        with t.serial_lease('2512-preserving-PROGRAM-slot-repair',timeout=300,priority=True):
            m=json.loads(t.MARK.read_text())
            assert m['block_snapshot'] and m['PROGRAM_SRAM_restore_pending'] and m['application_RAM_restore_pending']
            assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
            with (CASE/'serial.jsonl').open('x') as log:
                try:
                    s=base.Session(CASE,log,'2512');s.fixture=fixture;s.allowed=[0x140,0x200]
                    s.link.send(b'\r');s.until((t.WB,),seconds=15);s.monitor()
                    assert b'CPU $02' in s.command('V')
                    mark(program_repair_worker_active=True,block_snapshot=True)
                    s.rec();s.service(reader);s.read_banks('before',original_plan['source_bank_sha256'])
                    s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
                    s.bench()
                    for a in s.allowed:
                        fields=bytes([0,a>>8,a&255]);out=s.command('R'+fields.hex().upper())
                        frame=re.findall(rb'D([0-9A-F]{138})\r?\n',out);assert len(frame)==1
                        packet=bytes.fromhex(frame[0].decode())
                        assert packet[:3]==fields and packet[3:-2]==bad[a:a+64]
                        assert binascii.crc_hqx(packet[:-2],65535)==int.from_bytes(packet[-2:],'big')
                        s.block(a,snapshot[a:a+64])
                        print(f'RESTORED exact original SRAM {a:04X}-{a+63:04X}',flush=True)
                    assert s.full('SRAM-repaired')==snapshot
                    report.update(SRAM_restore_pending=False,all_131072_SRAM_bytes_restored=True,SRAM_sha256=t.sha(snapshot))
                    print('PASS all131072 SRAM bytes equal the original',flush=True)
                    s.rec();s.service(reader);s.read_banks('after',original_plan['source_bank_sha256'])
                    report['all_flash_banks_unchanged']=True
                finally:
                    try:
                        if s is not None and s.context is not None:
                            if s.context!=b'RAM SERVICE BASE1> ':s.rec();s.service(reader)
                            result=s.client.restore_owner(ram,zp)
                            report.update({k:v for k,v in result.items() if k not in ('owner_RAM_restored','owner_ZP_restored')})
                            s.context=t.REC;s.monitor();assert s.owner()==(ram,zp)
                            report.update(owner_RAM_restored=True,owner_ZP_restored=True)
                    finally:
                        if s is not None:
                            s.link.close();report['COM4_released']=True
                            report['final_context']=s.context.decode() if s.context else None
                        good=report['owner_RAM_restored'] and not report['SRAM_restore_pending'] and report.get('all_flash_banks_unchanged',False)
                        mark(program_repair_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],
                            application_ram_restored=report['owner_RAM_restored'],PROGRAM_SRAM_restore_pending=report['SRAM_restore_pending'],
                            block_snapshot=not good,last_PROGRAM_preserving_recovery=str(CASE/'report.json'))
                        save()
        assert report['all_131072_SRAM_bytes_restored'] and report['owner_RAM_restored'] and report['all_flash_banks_unchanged']
        report.update(passed=True,phase='EXACT_ORIGINAL_SRAM_AND_OWNER_RAM_RESTORED',finished_utc=t.utc());save()
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as error:
        report.update(error=repr(error),finished_utc=t.utc());save();raise


if __name__=='__main__':run()
