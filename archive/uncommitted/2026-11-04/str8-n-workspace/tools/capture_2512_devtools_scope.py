"""Fresh read-only devtool layout review with complete owner escrow."""
import json
from pathlib import Path
from devtools_2512_session import escrow,t,Q

OUT=Q/'2512-devtools-flash-preflight-20261102-r1'
def run():
 r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0)
 with escrow(OUT,r,'2512-devtools-flash-read-only-scope',window=180) as x:
  r['banks']={}
  for b in range(4):
   body=x.s.client.flash(b);assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}']
   (OUT/f'B{b}-original.bin').write_bytes(body)
   r['banks'][f'B{b}']=[dict(sector=f'{s+8:X}',blank=body[s*4096:(s+1)*4096]==b'\xff'*4096,first=body[s*4096:s*4096+24].hex(),sha256=t.sha(body[s*4096:(s+1)*4096])) for s in range(8)]
  r['journal']=t.classify_journal((OUT/'B3-original.bin').read_bytes())
 r['passed']=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r)
 print(json.dumps(dict(passed=r['passed'],B0=r['banks']['B0'],B1=r['banks']['B1'],journal=r['journal']),indent=2))
if __name__=='__main__':run()
