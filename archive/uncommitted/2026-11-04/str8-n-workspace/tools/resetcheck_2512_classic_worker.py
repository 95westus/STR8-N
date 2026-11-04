import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'physical-worker-reset';CASE.mkdir(exist_ok=False);PRE=BASE/'RAM-trial';r=dict(passed=False,flash_writes=0,SRAM_writes=0,owner_RAM_written=False)
assert json.loads((BASE/'restore-at-REC/report.json').read_text())['passed']
with t.serial_lease('2512-classic-physical-worker-reset-readonly',timeout=30):
 with (CASE/'serial.jsonl').open('x') as log:
  s=d.Session(CASE,log,'2512');m=json.loads(t.MARK.read_text());m.update(classic_workflow_worker_active=True,physical_reset_pending=True,block_snapshot=True);t.save(t.MARK,m)
  try:
   print('ARMED: 2512 physical RESET; keep power connected, no chooser key.',flush=True)
   out=s.until((t.MON,),seconds=1200);(CASE/'startup.txt').write_bytes(out);assert b'g0000000B / MON B' in out
   ram=(PRE/'owner-ram.bin').read_bytes();zp=(PRE/'owner-zp.bin').read_bytes()
   first=s.dump(0x200,0x23F);last=s.dump(0x66C0,0x66FF);(CASE/'owner-samples.bin').write_bytes(first+last)
   assert first==ram[:64] and last==ram[-64:],'Fresh worker owner samples differ; keep install held'
   assert s.dump(0,0xDF)==zp
   worker=s.dump(0x7800,0x7E5F);(CASE/'worker-after-reset.bin').write_bytes(worker)
   r.update(passed=True,owner_samples_match=True,owner_ZP_match=True,worker_reinitialized=True);s.command('!M 6A20 01')
  finally:
   s.link.close();r['COM4_released']=True;t.save(CASE/'report.json',r);m=json.loads(t.MARK.read_text());m.update(classic_workflow_worker_active=False,physical_reset_pending=False,block_snapshot=not r['passed'],classic_RAM_worker_reset_needed=not r['passed'],final_prompt='B3>');t.save(t.MARK,m)
print('PASS fresh Foundation RAM worker and owner preservation',flush=True)
