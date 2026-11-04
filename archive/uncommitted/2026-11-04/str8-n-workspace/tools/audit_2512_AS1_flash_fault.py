"""Read entire SPI SRAM after RAM-copy fault; do not repair or mutate data."""
import binascii,json,re,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,ins
OUT=Q/'2512-AS1-FLASH-post-fault-audit-20261102-r1';PRIOR=Q/'2512-AS1-FLASH-loader-recovery-20261102-r1'
def run():
 assert json.loads((PRIOR/'report.json').read_text())['passed']
 print('2512 post-fault SPI/RTC audit waiting for RTC window',flush=True)
 while True:
  try:ins.window(300);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,flash_writes=0,journal_writes=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0)
 with escrow(OUT,r,'2512-SF1-post-fault-read-only-audit',window=300,cache_first=0x6b00,cache_end=0x77ff) as x:
  x.mon();face=x.cmd('TIME');assert b'flags $28 trim $0C ctrl $80' in face;r['TIME']=face.decode();(OUT/'TIME.txt').write_bytes(face)
  x.wb();header=x.raw(0);x.mon();x.rec()
  helper=t.ROOT/'BUILD/2512-AS1-restorer-r1';m=json.loads((helper/'manifest.json').read_text());body=(helper/'AS1-SPI-RESTORER.bin').read_bytes();assert t.sha(body)==m['sha256']=='c45f33b41d15a8caae044d169605f77331f4cca5e793b1f945653f42ce37eb86';x.s.load(body,m['sha256'],t.PB)
  all_bytes=bytearray()
  for a in range(0,0x20000,64):
   x.s.link.send(b'R'+a.to_bytes(3,'big').hex().upper().encode()+b'\r');face=x.s.until((t.PB,));rows=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(rows)==1
   frame=bytes.fromhex(rows[0].decode());assert frame[:3]==a.to_bytes(3,'big') and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big');all_bytes+=frame[3:-2]
   if len(all_bytes)%32768==0:print(f'2512 read-only SPI audit {len(all_bytes)}/131072',flush=True)
  assert all_bytes[:64]==header;(OUT/'SPI-after-fault.bin').write_bytes(all_bytes)
  baseline=Q/'2512-SRAM-WORK-positive-RAM-20261101-r5/SRAM-metadata-before.bin';old=baseline.read_bytes();assert len(old)==len(all_bytes)==131072
  r.update(SPI_sha256=t.sha(all_bytes),historical_SPI_baseline=str(baseline),historical_SPI_sha256=t.sha(old),differing_bytes=sum(a!=b for a,b in zip(old,all_bytes)))
  assert all_bytes==old,'SPI differs from preserved baseline; inspect without writing';r['entire_SPI_exact_historical_baseline']=True
 r['passed']=bool(r.get('entire_SPI_exact_historical_baseline') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored'));t.save(OUT/'report.json',r);assert r['passed']
 with t.serial_lease('2512-SF1-post-fault-host-clearance',timeout=30):
  mp=Q/'device-operations/2512.json';m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'];m.update(block_snapshot=False,AS1_flash_post_fault_inspection_pending=False,last_AS1_flash_post_fault_audit=str(OUT/'report.json'));t.save(mp,m)
  import rtc_drift_campaign as c
  state=c.read(c.STATE);state.setdefault('CPU_reset_events',[]).append(dict(board='2512',recorded_UTC=c.NOW(),reason='Owner physical RESET after RAM SF/1 loader counter fault; full flash, owner/cache and entire SPI exact; TIME flags28 trim0C ctrl80; no power cycle or clock setting',report=str(PRIOR/'report.json'),power_cycle=False));c.save(c.STATE,state)
  import rtc_fleet
  rtc_fleet.admission('2512')
 print('PASS2512 all131072 SPI bytes exact; RTC ctrl/trim/PF status intact; owner/cache restored; RTC eligible',flush=True)
if __name__=='__main__':run()
