"""Read-only physical saved-default acceptance; restore owner RAM/ZP."""
import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1';CASE=BASE/'physical-default';PRE=BASE/'preflight-resume2';SERVICE=d.SERVICE

def run():
 assert json.loads((BASE/'AP02-one-erase-resume/report.json').read_text())['passed']
 CASE.mkdir(exist_ok=False);r=dict(board='2512',passed=False,checks=[],flash_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False)
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',r)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 with t.serial_lease('2512-BATCH-physical-default-boot-readonly',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');mark(batch_wide_worker_active=True,physical_reset_pending=True,block_snapshot=True)
    print('ARMED: press only 2512 physical RESET; no chooser key; saved B default.',flush=True)
    out=s.until((t.MON,),seconds=1200);(CASE/'startup.txt').write_bytes(out)
    assert b'BASE1' in out and b'PR05' in out and b'g0000000B / MON B' in out
    assert s.dump(0x7DF9,0x7DF9)==b'\0';r['checks'].append('physical-reset-default-B-and-volatile-queue-cleared')
    assert b'g0000000B / MON B' in s.command('VERSION')
    assert b'RTCC: 2026-' in s.command('TIME');r['checks'].append('VERSION-and-fresh-TIME')
    borrowed=True;s.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();s.service(reader)
    b3=s.client.flash(3);assert b3==(BASE/'AP02-one-erase-resume/B3-after.bin').read_bytes();(CASE/'B3-final.bin').write_bytes(b3);r['journal']=t.classify_journal(b3);r['checks'].append('entire-B3-unchanged-after-physical-boot')
   finally:
    try:
     if borrowed:
      r.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01');r['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();r['COM4_released']=True
     mark(batch_wide_worker_active=False,physical_reset_pending=False,application_RAM_restore_pending=borrowed and not r['owner_RAM_restored'],block_snapshot=True,application_ram_restored=r['owner_RAM_restored'],final_prompt='B3>')
     save()
 r['passed']='journal' in r and r['owner_RAM_restored'];save();print('PASS physical saved-default / owner restoration / COM4 released',flush=True)
if __name__=='__main__':run()
