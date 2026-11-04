"""Passive2512 default-B reset receiver; global lease free while owner waits."""
import json,re,time
from pathlib import Path
import install_startup_traditional_2512 as ins

t=ins.t;d=ins.d;Q=ins.Q;SCOPE=ins.SCOPE
OUT=Q/'2512-startup-traditional-reset-20261101-r1'

def run():
    p=ins.approved();installed=json.loads((ins.OUT/'report.json').read_text())
    assert installed['passed'] and installed['NVM_verified'] and installed['erase_requests']==3
    assert installed['owner_RAM_restored'] and installed['owner_ZP_restored'] and installed['COM4_released']
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    ram=(ins.OUT/'owner-ram.bin').read_bytes();zp=(ins.OUT/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,phase='arming',flash_writes=0,journal_writes=0,SRAM_data_writes=0,
           RTC_settings_writes=0,power_cuts=0,resets=0,owner_RAM_restored=True,owner_ZP_restored=True,
           installation_NVM_receipt=str(ins.OUT/'report.json'),installation_NVM_receipt_sha256=t.sha((ins.OUT/'report.json').read_bytes()))
    s=None;borrowed=False
    def save():t.save(OUT/'report.json',r)
    def mark(**fields):m=json.loads(mp.read_text());m.update(fields);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:cmd('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with (OUT/'serial.jsonl').open('x') as log:
      try:
        with t.serial_lease('2512-g10-passive-reset-arming',timeout=30):
            m=json.loads(mp.read_text())
            assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m.get('physical_reset_pending')
            assert m['monitor_generation']=='00000010' and m['current_journal_sequence']==1168
            assert m['current_owner_RAM_sha256']==t.sha(ram) and m['current_owner_ZP_sha256']==t.sha(zp)
            mark(physical_reset_pending=True,startup_reset_waiting=True)
            s=d.Session(OUT,log,'2512');s.link.serial.reset_input_buffer();s.link.pending.clear()
            r['phase']='waiting-for-physical-reset';save()
        print('ARMED2512 g10 RESET; passive COM4 receiver; fleet lease released while waiting',flush=True)
        deadline=time.monotonic()+12*3600
        while time.monotonic()<deadline:
            try:face=s.until((t.MON,),seconds=30)
            except TimeoutError:continue
            if b'STR8-N MON B  gen 00000010' not in face:continue
            (OUT/'full-startup.txt').write_bytes(face);break
        else:raise TimeoutError('Reset receiver expired; no flash writes were issued')
        r['resets']=1;r['phase']='default-B-startup-captured';save()
        with t.serial_lease('2512-g10-reset-acceptance',timeout=60):
            mark(startup_reset_waiting=False,startup_reset_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
            borrowed=True;r['owner_RAM_restored']=r['owner_ZP_restored']=False
            try:
                # BASE1's frozen countdown has no slot inventory. Inventory is
                # deliberately a VERSION detail, checked below after startup.
                assert b'Boot : 6 5 4 3 2 1 0' in face
                start=face.index(b'\r\nSTR8-N F 0.3.0  Foundation')
                startup=face[start:];(OUT/'monitor-startup.txt').write_bytes(startup)
                for text in (b'Recovery / opaque-image boot',b'STR8-N MON B  gen 00000010',b'Board: 2512',
                             b'EDU ON',b'SSRAM: PROGRAM payload 63488 bytes',b'SSRAM: WORKSPACE 65504 bytes',
                             b'(-06:00)',b'FLASH: B2:8 tracked max 604*',b'Battery: within age policy*'):
                    assert text in startup,(text,startup)
                assert b'CPU:' not in startup and b'MONITOR A gen ' not in startup
                r['selected_startup_and_cold_capacity']=True
                version=cmd('VERSION')
                assert b'0.1.0-dev BASE1/PR05 ABI 2' in version and b'CPU: 65C02' in version
                assert b'MONITOR A gen 00000010 VALID' in version and b'MONITOR B gen 00000010 VALID default' in version
                assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'));r['VERSION_and_TIME']=True
            finally:
                rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(startup_reset_worker_active=False,physical_reset_pending=not restored,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,final_prompt='REC>',last_startup_reset_acceptance=str(OUT/'report.json'))
      except BaseException as error:r['error']=repr(error);save();raise
      finally:
        if s:s.link.close();r['COM4_released']=True
        mark(startup_reset_waiting=False);save()
    r['passed']=bool(r.get('selected_startup_and_cold_capacity') and r.get('VERSION_and_TIME')
                     and r['owner_RAM_restored'] and r['owner_ZP_restored'])
    r['phase']='default-boot-accepted';save();assert r['passed']
    print('PASS2512 g10 physical default B; owner restored; REC>; COM4 released',flush=True)
    from readmit_startup_traditional_rtc_2512 import run as readmit
    readmit()

if __name__=='__main__':run()
