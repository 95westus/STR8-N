"""Passive COM4 reset receiver; release fleet lease while waiting for owner."""
import json,re,time
from pathlib import Path
import install_time_prep_2512 as ins
t=ins.t;d=ins.d;Q=ins.Q;SCOPE=ins.SCOPE;OUT=Q/'2512-TIME-PREP-cold-installed-20261101-r1'

def run():
    p=ins.approved();assert json.loads((ins.OUT/'installation-acceptance.json').read_text())['passed']
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    ram=(ins.OUT/'owner-ram.bin').read_bytes();zp=(ins.OUT/'owner-zp.bin').read_bytes();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,phase='arming',flash_writes=0,journal_writes=0,SRAM_data_writes=0,RTC_settings_writes=0,power_cuts=0,resets=0,owner_RAM_restored=True,owner_ZP_restored=True)
    s=None;borrowed=False
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        b=s.command(line,tokens);(OUT/f'{s.counter:03d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(b);return b
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==b'SRAM> ':cmd('Q',(t.MON,));cmd('Q',(t.REC,))
        elif s.context==t.MON:cmd('Q',(t.REC,))
        assert s.context==t.REC
    save()
    with (OUT/'serial.jsonl').open('x') as log:
      try:
        with t.serial_lease('2512-gF-reset-receiver-arming',timeout=60):
            m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending'] and m['monitor_generation']=='0000000F'
            assert m['current_owner_RAM_sha256']==t.sha(ram) and m['current_owner_ZP_sha256']==t.sha(zp)
            mark(physical_reset_pending=True,time_prep_reset_waiting=True)
            s=d.Session(OUT,log,'2512');s.link.serial.reset_input_buffer();s.link.pending.clear()
            r['phase']='waiting-for-physical-reset';save()
        # COM4 alone is held passively. physical_reset_pending excludes2512
        # from the collector; the global lease is free for the other boards.
        print('ARMED2512 RESET; passive COM4 receiver; fleet lease released while waiting',flush=True)
        deadline=time.monotonic()+12*3600
        while time.monotonic()<deadline:
            try:face=s.until((t.MON,),seconds=30)
            except TimeoutError:continue
            if b'g0000000F / MON B' not in face:continue
            (OUT/'startup.txt').write_bytes(face);break
        else:raise TimeoutError('Reset receiver expired after12 hours; no additional writes')
        r['resets']=1;r['phase']='cold-boot-captured';save()
        while True:
            try:
                with t.serial_lease('2512-gF-cold-acceptance',timeout=30):
                    mark(time_prep_reset_waiting=False,time_prep_reset_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
                    r['owner_RAM_restored']=r['owner_ZP_restored']=False
                    try:
                        assert b'EDU ON' in face and b'SSRAM: PROGRAM payload 63488 bytes' in face and b'SSRAM: WORKSPACE 65504 bytes' in face
                        assert b'MONITOR B gen 0000000F VALID default' in face
                        assert s.dump(0x6A20,0x6A20)==b'\x01';r['automatic_cold_capacity']=True
                        sample=cmd('TIME');assert re.search(rb'trim \$0C ctrl \$80',sample) and b'RTCC error' not in sample
                        cmd('R SRAM',(b'SRAM> ',));table=cmd('T');assert all(n in table for n in (b'CLK',b'CLOCK',b'NFCOPY'));cmd('Q',(t.MON,));r['cold_PROGRAM_TABLE']=True
                        rec();s.service(reader)
                        for b in (2,3):actual=s.client.flash(b);assert actual==(SCOPE/f'B{b}-target.bin').read_bytes();(OUT/f'B{b}-after.bin').write_bytes(actual)
                        r['NVM_verified']=True
                    finally:
                        rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(time_prep_reset_worker_active=False,physical_reset_pending=not restored,application_RAM_restore_pending=not restored,application_ram_restored=restored,final_prompt='REC>',last_TIME_PREP_cold_acceptance=str(OUT/'report.json'))
                    break
            except TimeoutError:
                if borrowed:raise
                continue
      except BaseException as e:r['error']=repr(e);save();raise
      finally:
        if s:s.link.close();r['port_released']=True
        mark(time_prep_reset_waiting=False);save()
    r['passed']=bool(r.get('NVM_verified') and r.get('automatic_cold_capacity') and r.get('cold_PROGRAM_TABLE') and r['owner_RAM_restored'] and r['owner_ZP_restored']);r['phase']='cold-accepted';save();assert r['passed'];print('PASS2512 gF cold boot and preservation; REC>; COM4 released',flush=True)
    from readmit_time_prep_rtc_2512 import run as readmit
    readmit()

if __name__=='__main__':run()
