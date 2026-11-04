"""Fresh read-only2609 scope capture; no flash or persistent-data writes."""
import json,sys,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,ins
sys.path.insert(0,str(t.REPO/'tools'))
from native_journal_room import inspect as room
OUT=Q/'2609-devtools-flash-preflight-20261102-r1'

def run():
 print('2609 read-only flash-scope capture waiting for RTC window240s',flush=True)
 while True:
  try:ins.window(240);break
  except AssertionError:time.sleep(1)
 r=dict(board='2609',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0)
 with escrow(OUT,r,'2609-devtools-flash-scope-read-only',window=240,cache_first=0x6b00,cache_end=0x77ff,board='2609') as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  accept=Q/'2609-devtools-g2-emulation-RAM-20261102-r1/report.json';prior=json.loads(accept.read_text());assert prior['passed'];r['RAM_acceptance_sha256']=t.sha(accept.read_bytes())
  r['banks']={}
  for b in range(4):
   body=x.s.client.flash(b);assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-original.bin').write_bytes(body);r['banks'][f'B{b}']=t.sha(body)
  b3=(OUT/'B3-original.bin').read_bytes();f=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha(b3[0x7000:])==f['sha256']
  r['journal']=t.classify_journal(b3);r['journal_room']=room(b3)
 r['passed']=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('port_released'));t.save(OUT/'report.json',r);assert r['passed']
 print(json.dumps(dict(passed=True,journal=r['journal'],journal_room=r['journal_room'],owner_cache_restored=True,port_released=True),indent=2))

if __name__=='__main__':run()
