"""Restore exact escrow after the TABLE test selected a different MON bank."""
import json
import execute_rec_cleanup as e
import inventory_unified_cleanup as inv
t=e.t;Q=e.Q;board='2604';prior=Q/'2604-REC-utility-cleanup-verified-20261102-r2';out=Q/'2604-cleanup-TABLE-prompt-restored-20261102-r1'
p=e.approved(board);r=dict(board=board,passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,hardware_resets=0)
e.await_window(180);out.mkdir();(out/'.gitignore').write_text('*\n');x=inv.Escrow(out,r,board)
x.ram=(prior/'owner-ram.bin').read_bytes();x.zp=(prior/'owner-zp.bin').read_bytes();x.high=(prior/'provider-cache-before.bin').read_bytes();x.oldhooks=(prior/'hooks-before.bin').read_bytes()
with t.serial_lease('2604-known-TABLE-bank-prompt-RAM-restoration',timeout=30):
 with (out/'serial.jsonl').open('x') as log:
  s=x.s=inv.BoardSession(out,log,board)
  try:
   s.link.send(b'\r');face=s.until(e.MONS,seconds=15);x.mon();assert x.hooks()==x.oldhooks
   x.restore_high();x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
   for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
   r.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
  finally:s.link.close();r['port_released']=True;x.save()
 r['passed']=all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'));assert r['passed']
 m=json.loads(x.mp.read_text());m.update(application_ram_restored=True,application_RAM_restore_pending=False,REC_cleanup_worker_active=False,REC_cleanup_write_worker_active=False,block_snapshot=False,final_prompt='REC>',last_cleanup_prompt_restoration=str(out/'report.json'));t.save(x.mp,m);x.save()
print('PASS TABLE bank prompt recovered; exact RAM/ZP/cache restored; no reset or flash writes',flush=True)
