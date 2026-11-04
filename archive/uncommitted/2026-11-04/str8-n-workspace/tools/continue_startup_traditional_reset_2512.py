"""Carry captured g10 default boot; finish read-only checks without another reset."""
import json,re
from pathlib import Path
import install_startup_traditional_2512 as ins

t=ins.t;d=ins.d;Q=ins.Q
PRIOR=Q/'2512-startup-traditional-reset-20261101-r1'
OUT=Q/'2512-startup-traditional-reset-20261101-r2'

def run():
    p=ins.approved();previous=json.loads((PRIOR/'report.json').read_text())
    assert previous['error']=='AssertionError()' and previous['phase']=='default-B-startup-captured'
    assert previous['resets']==1 and previous['owner_RAM_restored'] and previous['owner_ZP_restored'] and previous['COM4_released']
    assert json.loads((ins.OUT/'report.json').read_text())['passed']
    full=(PRIOR/'full-startup.txt').read_bytes()
    assert b'Boot : 6 5 4 3 2 1 0' in full
    start=full.index(b'\r\nSTR8-N F 0.3.0  Foundation');startup=full[start:]
    for text in (b'Recovery / opaque-image boot',b'STR8-N MON B  gen 00000010',b'Board: 2512',
                 b'EDU ON',b'SSRAM: PROGRAM payload 63488 bytes',b'SSRAM: WORKSPACE 65504 bytes',
                 b'(-06:00)',b'FLASH: B2:8 tracked max 604*',b'Battery: within age policy*'):
        assert text in startup,(text,startup)
    assert b'CPU:' not in startup and b'MONITOR A gen ' not in startup and startup.endswith(t.MON)
    ins.base.window(180);OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'monitor-startup.txt').write_bytes(startup)
    ram=(ins.OUT/'owner-ram.bin').read_bytes();zp=(ins.OUT/'owner-zp.bin').read_bytes()
    mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,phase='captured-boot-accepted-readonly-continuation',
           resets=1,new_resets=0,flash_writes=0,journal_writes=0,SRAM_data_writes=0,RTC_settings_writes=0,power_cuts=0,
           selected_startup_and_cold_capacity=True,owner_RAM_restored=previous['owner_RAM_restored'],
           owner_ZP_restored=previous['owner_ZP_restored'],owner_RAM_untouched_in_continuation=True,
           carried_reset_receipt=str(PRIOR/'report.json'),carried_reset_receipt_sha256=t.sha((PRIOR/'report.json').read_bytes()),
           startup_capture_sha256=t.sha(full),
           correction='BASE1 countdown has no inventory rows; validate A/B/default with post-reset VERSION. No firmware change or second reset.')
    s=None;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**fields):m=json.loads(mp.read_text());m.update(fields);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)}.txt').write_bytes(face);return face
    save()
    with t.serial_lease('2512-g10-captured-boot-readonly-continuation',timeout=30):
      ins.base.window(180);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['physical_reset_pending']
      assert marker['monitor_generation']=='00000010' and marker['current_journal_sequence']==1168
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            mark(startup_reset_worker_active=True)
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.REC,),seconds=12)
            cmd('B',(t.MON,));version=cmd('VERSION')
            assert b'0.1.0-dev BASE1/PR05 ABI 2' in version and b'CPU: 65C02' in version
            assert b'MONITOR A gen 00000010 VALID' in version and b'MONITOR B gen 00000010 VALID default' in version
            assert b'STR8-N MON B  gen 00000010' in version
            assert re.search(rb'trim \$0C ctrl \$80',cmd('TIME'));r['VERSION_and_TIME']=True;save()
            actual_ram,actual_zp=s.owner()
            assert actual_ram==ram and actual_zp==zp
            r.update(owner_RAM_readback_verified=True,owner_ZP_readback_verified=True,RAM_sha256=t.sha(actual_ram),ZP_sha256=t.sha(actual_zp))
        except BaseException as error:r['error']=repr(error);save();raise
        finally:
            try:
                if s and s.context==t.MON:cmd('Q',(t.REC,))
            finally:
                if s:s.link.close();r['COM4_released']=True
                mark(startup_reset_worker_active=False,final_prompt='REC>',last_startup_reset_acceptance=str(OUT/'report.json'))
                save()
    r['passed']=bool(r['selected_startup_and_cold_capacity'] and r.get('VERSION_and_TIME')
                     and r.get('owner_RAM_readback_verified') and r.get('owner_ZP_readback_verified'))
    r['phase']='default-boot-accepted';save();assert r['passed']
    print('PASS2512 captured default B; VERSION/TIME; exact owner verified; zero new resets; REC>; COM4 free',flush=True)
    from readmit_startup_traditional_rtc_2512 import run as readmit
    readmit()

if __name__=='__main__':run()
