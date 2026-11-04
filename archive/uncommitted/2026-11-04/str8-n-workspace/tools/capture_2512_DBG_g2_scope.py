"""Fresh read-only DBG install preflight after other2512 work closed."""
import json,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,ins
OUT=Q/'2512-DBG-g2-fresh-preflight-20261102-r1'
def run():
 print('2512 fresh DBG review capture waiting for RTC window',flush=True)
 while True:
  try:ins.window(240);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0)
 with escrow(OUT,r,'2512-DBG-g2-review-read-only-capture',window=240,cache_first=0x6b00,cache_end=0x77ff) as x:
  m=x.original;assert not m['block_snapshot'] and not m.get('utility_retirement_pending') and not m.get('legacy_reclaim_pending')
  for key in ('last_utility_retirement','last_legacy_sector_reclamation'):
   receipt=Path(m[key]);prior=json.loads(receipt.read_text());assert prior['passed'];r[key]=dict(path=str(receipt),sha256=t.sha(receipt.read_bytes()))
  r['banks']={}
  for b in range(4):
   body=x.s.client.flash(b);assert t.sha(body)==m['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-original.bin').write_bytes(body);r['banks'][f'B{b}']=t.sha(body)
  sf=(t.ROOT/'BUILD/asm-flash-source-g2-r4/FLASH-SOURCE-7000.bin').read_bytes();assert (OUT/'B0-original.bin').read_bytes()[0x5800:0x6000]==sf
  r['journal']=t.classify_journal((OUT/'B3-original.bin').read_bytes());r['SF_provider_sha256']=t.sha(sf)
 r['passed']=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('B3_F_images_settings_history_unchanged'));t.save(OUT/'report.json',r);assert r['passed']
 print(json.dumps(dict(passed=True,journal=r['journal'],full_provider_cache_restored=True,owner_restored=True,port_released=True),indent=2))
if __name__=='__main__':run()
