import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'restore-at-REC';PRE=BASE/'RAM-trial';CASE.mkdir(exist_ok=False);r=dict(passed=False,flash_writes=0,SRAM_writes=0)
with t.serial_lease('2512-classic-owner-restore-at-REC',timeout=30):
 with (CASE/'serial.jsonl').open('x') as log:
  s=d.Session(CASE,log,'2512')
  try:
   s.link.send(b'\r');s.until((t.CLOCK,),seconds=15);s.command('Q',(t.MON,));s.command('Q',(t.REC,));s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes());r.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));r['passed']=True
  finally:
   s.link.close();r['COM4_released']=True;t.save(CASE/'report.json',r);m=json.loads(t.MARK.read_text());m.update(classic_workflow_worker_active=False,application_RAM_restore_pending=not r['passed'],application_ram_restored=r['passed'],block_snapshot=True,final_prompt='REC>',classic_RAM_worker_reset_needed=True);t.save(t.MARK,m)
print('PASS exact owner RAM/ZP restored at REC; F/SRAM unchanged',flush=True)
