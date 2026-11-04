"""Approved second physical RESET: saved-B g10 startup and owner restoration."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from install_2205_foundation_profile import Session,t,SCOPE,CONVERSION,MP
from installer.common import save
from installer.engine.runtime import sha
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease

INSTALL=ROOT/'output/qualification/2205-foundation-profile-installed-20261102-r1'
OUT=ROOT/'output/qualification/2205-foundation-default-reset-20261102-r1'


def run():
    install=json.loads((INSTALL/'report.json').read_text());assert install['passed'] and install['total_rollout_erases']==34
    p=json.loads((SCOPE/'compact/plan.json').read_text());ram=(CONVERSION/'owner-ram.bin').read_bytes();zp=(CONVERSION/'owner-zp.bin').read_bytes()
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n');durable(OUT/'driver-as-executed.py',Path(__file__).read_bytes())
    r=dict(board='2205',passed=False,phase='arming',physical_resets=0,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,power_cuts=0)
    def checkpoint(**kw):r.update(kw);save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(MP.read_text());m.update(kw);save(MP,m)
    checkpoint();s=None
    with (OUT/'serial.jsonl').open('x') as log:
      try:
        with serial_lease('2205-g10-default-reset-arming',timeout=600):
          m=json.loads(MP.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending']
          s=Session(OUT,log);s.link.serial.reset_input_buffer();s.link.pending.clear()
          mark(physical_reset_pending=True,foundation_default_reset_waiting=True)
          checkpoint(phase='waiting-for-physical-reset')
        print('ARMED2205 FINAL RESET: press RESET only2205; no chooser key; no flash writes',flush=True)
        face=s.until((t.MON,),seconds=12*3600);durable(OUT/'full-startup.txt',face)
        assert b'STR8N-F 0.3.0 g00000001\r\nBASE1 / PR05' in face
        assert b'STR8-N MON B  gen 00000010' in face and b'Board: 2205' in face and b'EDU ON' in face
        assert b'CPU:' not in face and b'REC> ' not in face
        checkpoint(physical_resets=1,phase='saved-B-startup-captured',saved_default_B_verified=True)
        with serial_lease('2205-g10-default-reset-owner-restoration',timeout=600):
          mark(physical_reset_pending=False,foundation_default_reset_waiting=False,foundation_rollout_worker_active=True,
               application_RAM_restore_pending=True,application_ram_restored=False)
          try:
            version=s.command('VERSION');durable(OUT/'VERSION.txt',version)
            assert b'Board: 2205' in version and b'STR8-N MON B  gen 00000010' in version and b'CPU: 65C02' in version
            sample=s.command('TIME');durable(OUT/'TIME.txt',sample)
            r['detailed_VERSION_TIME_passed']=True
          finally:
            if s.context==t.MON:s.command('Q',(t.REC,))
            assert s.context==t.REC
            reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();s.service(reader)
            try:
              for bank in range(4):assert sha(s.client.flash(bank))==p['expected_bank_sha256'][f'B{bank}']
              r['all_four_banks_exact']=True
            finally:
              r.update(s.client.restore_owner(ram,zp));s.context=t.REC
            assert r['owner_RAM_restored'] and r['owner_ZP_restored']
          mark(foundation_rollout_worker_active=False,application_RAM_restore_pending=False,application_ram_restored=True,
            physical_reset_pending=False,foundation_default_reset_waiting=False,foundation_profile_acceptance_pending=False,
            foundation_physical_boot_qualified=True,foundation_RTC_readmission_pending=True,final_prompt='REC>',
            last_foundation_default_reset=str(OUT/'report.json'))
          checkpoint(passed=True,phase='default-boot-verified-owner-restored',all_four_banks_exact=True,final_prompt='REC>')
      except BaseException as error:checkpoint(error=repr(error));raise
      finally:
        if s:s.link.close();checkpoint(port_released=True)
    print(json.dumps(r,indent=2),flush=True)


if __name__=='__main__':run()
