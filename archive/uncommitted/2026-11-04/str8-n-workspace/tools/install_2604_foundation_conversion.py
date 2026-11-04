"""Approved 2604-only three-erase conversion; immutable qualified RAM engine."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from installer.engine.legacy_transport import Link
from installer.engine import install_transport
from installer.engine.runtime import sha
from installer.common import save
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease,drift_pending
import install_named_edu_2512 as guard

SCOPE=ROOT/'output/qualification/2604-foundation-rollout-scope-20261102-r1'
ENGINE=SCOPE/'conversion-engine-review'
OUT=ROOT/'output/qualification/2604-foundation-conversion-installed-20261102-r1'
MP=ROOT/'output/qualification/device-operations/2604.json'
MON=b'\r\nB3> ';REC=b'REC> '


def run():
    approval=json.loads((SCOPE/'approval.json').read_text());plan=json.loads((SCOPE/'plan.json').read_text())
    review=json.loads((SCOPE/'review.json').read_text())
    assert approval['owner_statement']=='Approve reviewed 27-erase 2604 rollout' and approval['approved']
    assert approval['runtime_policy']=='Use Foundation runtime; archive rc1 cache/vectors'
    assert approval['plan_sha256']==review['plan_sha256']==sha((SCOPE/'plan.json').read_bytes())
    assert approval['review_document_sha256']==sha((SCOPE/'review-document.md').read_bytes())
    assert plan['total_erases']==27 and plan['conversion_erases']==3 and plan['F_replacements']==1
    proof=json.loads((ENGINE/'static-review.json').read_text());assert proof['passed'] and proof['unchanged_executable_bytes']
    assert sha((ENGINE/'installer-model-only.s19').read_bytes())==proof['installer_sha256']
    print('2604 approved conversion waiting for RTC window240s',flush=True)
    while True:
        try:guard.window(240);break
        except AssertionError:time.sleep(1)
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
    durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes());durable(OUT/'approval.json',(SCOPE/'approval.json').read_bytes())
    report=dict(board='2604',passed=False,phase='preflight',conversion_erase_allowance=3,
        flash_mutation_started=False,F_replacements=0,physical_resets=0,power_cuts=0,
        SPI_writes=0,RTC_setting_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    def checkpoint(**kw):report.update(kw);save(OUT/'report.json',report)
    def mark(**kw):m=json.loads(MP.read_text());m.update(kw);save(MP,m)
    checkpoint();link=None
    with (OUT/'serial.jsonl').open('x') as log:
      try:
        with serial_lease('2604-approved-WC-SNBT-C-F-D-conversion',timeout=30):
          guard.window(240);m=json.loads(MP.read_text())
          assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m.get('physical_reset_pending')
          assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
          from serial.tools.list_ports import comports
          ports=[p for p in comports() if p.serial_number=='A10MQGVHA'];assert len(ports)==1 and ports[0].device=='COM5'
          durable(OUT/'marker-before.json',MP.read_bytes())
          link=Link('COM5',log);link.send(b'\r');link.until(MON,seconds=10)
          def dump(first,last,prompt=MON):return b''.join(link.dump(a,min(a+511,last),prompt) for a in range(first,last+1,512))
          ram=dump(0x200,0x66ff);zp=dump(0,0xdf);cache=dump(0x6b00,0x77ff);hooks=dump(0x7e00,0x7e8f)
          for name,body in [('owner-ram.bin',ram),('owner-zp.bin',zp),('rc1-provider-cache.bin',cache),('rc1-runtime-vectors.bin',hooks)]:durable(OUT/name,body)
          for bank in (3,0,1,2):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);body=dump(0x8000,0xffff,prompt)
            assert body==(SCOPE/f'B{bank}-original.bin').read_bytes(),f'Source B{bank} changed'
            durable(OUT/f'B{bank}-fresh.bin',body)
          link.command('B3',MON)
          assert dump(0x7d30,0x7d30)==b'\xb0' and dump(0x7df9,0x7df9)==b'\0'
          if drift_pending():raise InterruptedError('RTC priority before RAM-engine upload')
          mark(foundation_rollout_worker_active=True,application_RAM_restore_pending=True,application_ram_restored=False,
            block_snapshot=True,RTC_LED_owner_hold=True,RTC_collection_pending_monitor_recovery=True,
            foundation_rollout_scope=str(SCOPE),foundation_rollout_qualification_pending=True)
          checkpoint(phase='executing-approved-conversion',flash_mutation_started=True)
          def progress(n,op):
            checkpoint(transfers_sent=n,last_destination=f'B{op["bank"]}:{op["address"]:04X}')
            print('2604 conversion transfer',n,report['last_destination'],flush=True)
          result=install_transport.execute(link,ENGINE,host_readback=True,progress=progress)
          checkpoint(**result,phase='waiting-for-physical-reset',F_replacements=1,conversion_erases_completed=3)
          mark(foundation_rollout_worker_active=False,physical_reset_pending=True,foundation_conversion_reset_waiting=True)
        print('ARMED2604 RESET1: C/F/D device-verified; passive COM5; fleet lease released',flush=True)
        face=link.until(REC,seconds=12*3600);durable(OUT/'Foundation-reset-console.txt',face)
        assert b'BASE1' in face and b'PR05' in face
        checkpoint(physical_resets=1,phase='golden-recovery-captured')
        link.serial.close();link=None
        with serial_lease('2604-post-conversion-readback-owner-restoration',timeout=90):
          mark(foundation_rollout_worker_active=True,physical_reset_pending=False,foundation_conversion_reset_waiting=False)
          t=guard.t
          s=t.Session.__new__(t.Session)
          s.folder=OUT;s.context=None;s.counter=0;s.client=None
          s.link=t.transport.RecoveryLink('COM5',log,usb_serial='A10MQGVHA');link=s.link
          s.link.send(b'\r');s.until((t.REC,),seconds=15)
          reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();s.service(reader)
          for bank in range(4):
            body=s.client.flash(bank);assert body==(ENGINE/f'expected-b{bank}.bin').read_bytes()
            durable(OUT/f'B{bank}-converted.bin',body)
          restored=s.client.restore_owner(ram,zp);checkpoint(**restored)
          assert restored['owner_RAM_restored'] and restored['owner_ZP_restored']
          expected={f'B{b}':sha((ENGINE/f'expected-b{b}.bin').read_bytes()) for b in range(4)}
          journal=proof['post_conversion_journal']
          mark(firmware='STR8N-F 0.3.0 BASE1 PR05',current_F_sha256=plan['target_F_sha256'],
            current_fixed_F_sha256=plan['target_F_sha256'],current_physical_bank_sha256=expected,
            current_wear_counts=journal['counts'],current_journal_sequence=journal['sequence'],
            foundation_rollout_worker_active=False,physical_reset_pending=False,application_ram_restored=True,
            application_RAM_restore_pending=False,block_snapshot=True,final_prompt='REC>',
            foundation_conversion_complete=True,last_foundation_conversion=str(OUT/'report.json'),
            rc1_cache_vectors_preservation='Permanent host archive; approved Foundation runtime replaces legacy defaults')
          checkpoint(passed=True,phase='converted-owner-restored',physical_reset_pending=False,final_prompt='REC>',journal=journal,
            all_four_banks_verified=True,rc1_cache_vectors_archived=True,Foundation_runtime_initialized=True)
      except BaseException as error:checkpoint(error=repr(error));raise
      finally:
        if link:
          if hasattr(link,'close'):link.close()
          else:link.serial.close()
        checkpoint(port_released=True)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':run()
