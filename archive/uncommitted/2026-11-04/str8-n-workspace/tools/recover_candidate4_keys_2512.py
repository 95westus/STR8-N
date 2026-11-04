"""Restore the existing key-trial escrow; no reset or persistent write."""
import json
from pathlib import Path
import candidate4_2512_common as c

t=c.t;d=c.ds.d
PRE=c.Q/'2512-candidate4-physical-keys-20261102-r1'
OUT=c.Q/'2512-candidate4-keys-owner-recovery-20261102-r1'

def run():
 c.await_window(240);OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
 old=json.loads((PRE/'report.json').read_text());assert old['provider_cache_restored'] and old['port_released'] and not old.get('owner_RAM_restored')
 marker=json.loads((PRE/'marker-before.json').read_text());mp=c.Q/'device-operations/2512.json'
 ram=(PRE/'owner-ram.bin').read_bytes();zp=(PRE/'owner-zp.bin').read_bytes();high=(PRE/'provider-cache-before.bin').read_bytes();hooks=(PRE/'hooks-before.bin').read_bytes()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_SET=0,physical_resets=0)
 with t.serial_lease('2512-candidate4-keys-owner-recovery',timeout=30):
  c.ds.ins.window(240)
  with (OUT/'serial.jsonl').open('x') as log:
   s=d.Session(OUT,log,'2512')
   try:
    s.link.send(b'\r');s.until((t.REC,),seconds=15);s.command('B',(t.MON,))
    assert s.dump(0x6b00,0x77ff)==high
    assert s.dump(0x7e02,0x7e03)+s.dump(0x7e67,0x7e69)==hooks
    r['provider_cache_hooks_exact']=True
    s.command('Q',(t.REC,));s.service(reader)
    for b in range(4):
     body=s.client.flash(b);assert body==(PRE/f'B{b}-before.bin').read_bytes();(OUT/f'B{b}-verified.bin').write_bytes(body)
    r['all_four_banks_exact']=True
    r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    r['passed']=r['owner_RAM_restored'] and r['owner_ZP_restored']
   finally:
    s.link.close();r['port_released']=True;t.save(OUT/'report.json',r)
    if r['passed']:
     m=json.loads(mp.read_text());m.update(application_RAM_restore_pending=False,application_ram_restored=True,block_snapshot=marker['block_snapshot'],final_prompt='REC>',last_candidate4_key_recovery=str(OUT/'report.json'));t.save(mp,m)
 assert r['passed'];print('PASS four banks exact; owner RAM/ZP/cache/hooks restored; REC>; COM4 released',flush=True)

if __name__=='__main__':run()
