"""Passive RESET recovery for SF/1 RAM overlay-copy fault; never flash."""
import json,time
from pathlib import Path
import devtools_2512_session as ds
t=ds.t;d=ds.ins.d;Q=ds.Q
PRIOR=Q/'2512-AS1-FLASH-readonly-RAM-20261102-r1';OUT=Q/'2512-AS1-FLASH-loader-recovery-20261102-r1'
def run():
 old=json.loads((PRIOR/'report.json').read_text());assert old['port_released'] and old['error'].startswith('TimeoutError(') and not old.get('owner_RAM_restored')
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 ram=(PRIOR/'owner-ram.bin').read_bytes();zp=(PRIOR/'owner-zp.bin').read_bytes();cache=(PRIOR/'provider-cache-before.bin').read_bytes();hooks=(PRIOR/'hooks-before.bin').read_bytes();original=json.loads((PRIOR/'marker-before.json').read_text());assert len(cache)==3328
 r=dict(board='2512',passed=False,phase='arming',physical_resets=0,flash_writes=0,journal_writes=0,requested_SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,limits='RAM copy fault may have crossed I/O; flash and RTC must be inspected rather than assuming no side effects')
 x=ds.Session(OUT,r);x.cache_first=0x6b00;x.high=cache;x.ram=ram;x.zp=zp;s=None;reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 with (OUT/'serial.jsonl').open('x') as log:
  try:
   with t.serial_lease('2512-SF1-loader-reset-arming',timeout=30):
    x.mark(physical_reset_pending=True,AS1_flash_reset_waiting=True,block_snapshot=True)
    s=x.s=d.Session(OUT,log,'2512');s.link.serial.reset_input_buffer();s.link.pending.clear();r['phase']='waiting-for-physical-reset';x.save()
   print('ARMED2512 SF/1 loader recovery; passive COM4; fleet lease released',flush=True)
   tail=b'';deadline=time.monotonic()+12*3600
   while time.monotonic()<deadline:
    tail=(tail+s.link.read(max(1,s.link.serial.in_waiting)))[-2048:]
    if b'Boot : ' in tail:
     (OUT/'reset-startup.txt').write_bytes(tail);s.link.send(b'S');s.until((t.REC,),seconds=20);break
   else:raise TimeoutError('No physical reset captured')
   r.update(physical_resets=1,phase='golden-recovery-captured');x.save()
   with t.serial_lease('2512-SF1-loader-owner-recovery',timeout=90):
    x.mark(AS1_flash_reset_waiting=False,AS1_flash_recovery_worker_active=True)
    x.mon();assert x.hooks()==hooks;face=x.cmd('TIME');(OUT/'native-TIME-after-reset.txt').write_bytes(face)
    x.restore_high();x.rec();s.service(reader)
    for b in range(4):
     v=s.client.flash(b);(OUT/f'B{b}-after-reset.bin').write_bytes(v);assert t.sha(v)==original['current_physical_bank_sha256'][f'B{b}']
    r['all_flash_images_settings_history_F_exact']=True
    r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];x.mark(physical_reset_pending=not restored,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=True,AS1_flash_post_fault_inspection_pending=True,final_prompt='REC>',last_AS1_flash_recovery=str(OUT/'report.json'))
  except BaseException as e:r['error']=repr(e);x.save();raise
  finally:
   if s:s.link.close();r['port_released']=True
   x.mark(AS1_flash_reset_waiting=False,AS1_flash_recovery_worker_active=False);x.save()
 r['passed']=bool(r.get('provider_cache_restored') and r.get('all_flash_images_settings_history_F_exact') and r['owner_RAM_restored'] and r['owner_ZP_restored']);x.save();assert r['passed'];print('PASS2512 flash/hooks/full cache/owner verified; REC>; COM4 free; RTC/SPI post-fault audit remains',flush=True)
if __name__=='__main__':run()
