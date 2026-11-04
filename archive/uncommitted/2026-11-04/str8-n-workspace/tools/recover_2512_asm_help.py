"""Passive2512 RESET recovery after ASM help printer loops; zero NVM writes."""
import json,time
from pathlib import Path
import install_named_edu_2512 as ins
t=ins.t;d=ins.d;Q=ins.Q
PRIOR=Q/'2512-ASM-DBG-BASE1-RAM-20261102-r1';OUT=Q/'2512-ASM-help-recovery-20261102-r1'

def run():
 old=json.loads((PRIOR/'report.json').read_text());assert old.get('error','').startswith('TimeoutError(') and old['port_released'] and not old['owner_RAM_restored']
 assert old['checks']==['fresh-owner-F-and-default-hooks-admitted']
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 ram=(PRIOR/'owner-ram.bin').read_bytes();zp=(PRIOR/'owner-zp.bin').read_bytes();high=(PRIOR/'provider-cache-before.bin').read_bytes();hooks=(PRIOR/'hooks-before.bin').read_bytes();original=json.loads((PRIOR/'marker-before.json').read_text())
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json';s=None
 r=dict(board='2512',passed=False,phase='arming',physical_resets=0,flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):return s.command(line,tokens)
 save()
 with (OUT/'serial.jsonl').open('x') as log:
  try:
   with t.serial_lease('2512-ASM-help-reset-arming',timeout=30):
    mark(physical_reset_pending=True,ASM_help_reset_waiting=True)
    s=d.Session(OUT,log,'2512');s.link.serial.reset_input_buffer();s.link.pending.clear();r['phase']='waiting-for-physical-reset';save()
   print('ARMED2512 RESET recovery; passive COM4; fleet lease released',flush=True)
   deadline=time.monotonic()+12*3600;tail=b''
   while time.monotonic()<deadline:
    tail=(tail+s.link.read(max(1,s.link.serial.in_waiting)))[-2048:]
    if b'Boot : ' in tail:
     (OUT/'reset-startup.txt').write_bytes(tail);s.link.send(b'S');s.until((t.REC,),seconds=20);break
   else:raise TimeoutError('No physical reset captured')
   r['physical_resets']=1;r['phase']='golden-recovery-captured';save()
   with t.serial_lease('2512-ASM-help-owner-recovery',timeout=90):
    mark(ASM_help_reset_waiting=False,ASM_help_recovery_worker_active=True)
    cmd('B',(t.MON,));assert s.dump(0x7e02,0x7e03)+s.dump(0x7e67,0x7e69)==hooks
    for off in range(0,len(high),8):cmd(f'M {0x2000+off:04X} '+high[off:off+8].hex(' ').upper())
    code=bytearray(bytes.fromhex('78D8A200'));loop=0x3004
    for page in range(5):code+=bytes((0xbd,0,(0x2000+256*page)>>8,0x9d,0,(0x7000+256*page)>>8))
    code+=bytes((0xe8,0xd0,(loop-(0x3000+len(code)+3))&255));code+=bytes.fromhex('A92F85E0AD307D85E16CE000')
    for off in range(0,len(code),8):cmd(f'M {0x3000+off:04X} '+code[off:off+8].hex(' ').upper())
    cmd('G 3000',(t.MON,));assert s.dump(0x7000,0x74ff)==high;r['provider_cache_restored']=True
    cmd('Q',(t.REC,));s.service(reader);assert t.sha(s.client.flash(3))==original['current_physical_bank_sha256']['B3'];r['B3_F_images_settings_history_unchanged']=True
    r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(ASM_help_recovery_worker_active=False,physical_reset_pending=not restored,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=original['block_snapshot'] if restored else True,final_prompt='REC>',last_ASM_help_recovery=str(OUT/'report.json'))
  except BaseException as e:r['error']=repr(e);save();raise
  finally:
   if s:s.link.close();r['port_released']=True
   mark(ASM_help_reset_waiting=False,ASM_help_recovery_worker_active=False);save()
 r['passed']=bool(r.get('provider_cache_restored') and r.get('B3_F_images_settings_history_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2512 ASM-help recovery; F/history exact; cache/hooks/owner restored; REC>;COM4 free',flush=True)

if __name__=='__main__':run()
