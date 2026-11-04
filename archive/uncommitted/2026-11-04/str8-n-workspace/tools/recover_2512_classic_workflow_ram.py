import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'RAM-recovery';PRE=BASE/'RAM-trial';CASE.mkdir(exist_ok=False)
r=dict(passed=False,flash_writes=0,SRAM_writes=0)
with t.serial_lease('2512-classic-RAM-recovery',timeout=30):
 with (CASE/'serial.jsonl').open('x') as log:
  s=d.Session(CASE,log,'2512')
  try:
   s.link.send(b'\r');s.until((t.REC,),seconds=15)
   body=bytes.fromhex('78 D8 A2 FF 9A 9C F9 7D 4C 67 7E');s.load(body,t.sha(body),t.MON);s.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
   r.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01');r['passed']=True
  finally:s.link.close();r['COM4_released']=True;t.save(CASE/'report.json',r);m=json.loads(t.MARK.read_text());m.update(classic_workflow_worker_active=False,application_RAM_restore_pending=not r['passed'],application_ram_restored=r['passed'],block_snapshot=not r['passed']);t.save(t.MARK,m)
print('PASS owner RAM/ZP recovery; flash/SRAM unchanged',flush=True)
