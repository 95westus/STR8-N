"""Finish checks of an already exact cleanup; this driver cannot flash."""
import argparse,json
from pathlib import Path
import execute_rec_cleanup as e
import nf_opaque as opaque
import trial_flash_transfer_readonly as ro
from trial_s19_ram import READY
t=e.t;Q=e.Q
def run(board):
 p=e.approved(board);installed=Q/f'{board}-REC-utility-cleanup-installed-20261102-r1';prior=json.loads((installed/'report.json').read_text())
 assert prior['NVM_verified'] and prior['erase_requests']==p['image_erases'] and len(prior['completed'])==p['image_erases']
 assert all(prior[k] for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','port_released'))
 for b in range(4):assert t.sha((installed/f'B{b}-after.bin').read_bytes())==p['after_bank_sha256'][f'B{b}']
 e.await_window(420)
 mp=Q/f'device-operations/{board}.json'
 with t.serial_lease(board+'-admit-completed-cleanup-for-readonly-checks',timeout=30):
  m=json.loads(mp.read_text());assert m['current_physical_bank_sha256']==p['after_bank_sha256'] and m['application_ram_restored'] and not m['application_RAM_restore_pending']
  assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
  m['block_snapshot']=False;t.save(mp,m)
 out=Q/f'{board}-REC-utility-cleanup-verified-20261102-r3'
 r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,RTC_setting_writes=0,original_write_receipt=str(installed/'report.json'),component_erases_already_completed=p['image_erases'],journal_erases_already_completed=len(p['journal_rotation_erases']))
 qa=json.loads((e.SCOPE/'plan.json').read_text())['REC_tools_admission'];maint=(t.ROOT/'BUILD/loadable-maint-full-r2/MAINT.bin').read_bytes();flash=(t.ROOT/'firmware/ram-tools/flash-g2/FLASH.bin').read_bytes();assert t.sha(maint)==qa['MAINT_sha256'] and t.sha(flash)==qa['FLASH_sha256']
 with e.escrow(board,out,r) as x:
  s=x.s;opaque.durable_file(out/'driver-as-executed.py',Path(__file__).read_bytes())
  def check(label):r['checks'].append(label);x.save();print('PASS '+board+' '+label,flush=True)
  def leave(prompt):assert s.context==prompt;x.cmd('Q',(t.MON,t.REC));x.mon()
  for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
  check('installed four-bank result exact; no additional erases')
  x.mon();face=x.cmd('VERSION');assert f'Board: {board}'.encode() in face and b'Battery:' in face and b'unavailable' not in face
  # Reuse the completed positive catalogue output: only the host's expected
  # prompt was wrong. Do not replay successful APPS/map/TABLE hardware checks.
  cat=Q/f'{board}-REC-utility-cleanup-verified-20261102-r2/report.json'
  old=json.loads(cat.read_text());assert 'End; SR01 has no payload CRC.' in old['error'] and 'B2>' in old['error']
  r['accepted_APPS_map_TABLE_receipt']=str(cat)
  x.cmd('R CLOCK',(t.CLOCK,));x.mon();check('VERSION/STATUS/APPS/map/T/CLOCK and ASM/DBG retained')
  x.cmd('STORE 0 9000 5800 66FF CLEANNO',(ro.STORE_YES,));s.link.send(b'NO\r');assert b'Canceled' in s.until(e.MONS);x.mon()
  x.cmd('S19',(READY,));s.link.send(b'\x03');assert b'S19 stopped $03' in s.until((t.MON,));check('shared STORE and S19 cancellation paths retained')
  x.wb();x.cmd('TABLE P');meta=b''.join(x.raw(a) for a in range(0,0x800,64));assert meta==(installed/'SPI-metadata-before.bin').read_bytes();opaque.durable_file(out/'SPI-metadata-after.bin',meta);check('PROGRAM/WORK metadata and geometry exact')
  x.rec();s.load(maint,qa['MAINT_sha256'],e.BM);assert b'Copy RAM or flash' in x.cmd('?',(e.BM,));assert b'REC 0200 r1' in x.cmd('VERSION',(e.BM,));assert b'CLOCK' in x.cmd('TABLE',(e.BM,));x.cmd('M3',(e.BM,))
  x.cmd('N 10 FF',(e.BM,));x.cmd('P 0 12 34',(e.BM,));assert b'12 34 FF' in x.cmd('D 0-F',(e.BM,));assert b'WRITE? TYPE Y' not in x.cmd('E 3 C-D',(e.BM,));leave(e.BM)
  x.rec();s.load(flash,qa['FLASH_sha256'],e.FT);assert b'FLASH g2' in x.cmd('VERSION',(e.FT,));x.cmd('BANK 0',(e.FT,));x.cmd('READ 8000',(e.FT,));assert b'FF FF FF FF' in x.cmd('VIEW 000',(e.FT,));x.cmd('I 9000 9FFF',(ro.YES,));assert b'Canceled' in x.cmd('NO',(e.FT,));leave(e.FT);check('full MAINT and FLASH REC BINs work without resident copies')
  x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
  for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
  check('final four-bank readback exact')
 r['passed']=len(r['checks'])==6 and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released'))
 t.save(out/'report.json',r);assert r['passed']
 m=json.loads(mp.read_text());m.update(REC_cleanup_pending=False,block_snapshot=False,last_REC_utility_cleanup=str(out/'report.json'));t.save(mp,m)
 print('PASS '+board+' completed cleanup verified; RAM restored; port released',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('board',choices=['2604','2609']);a=p.parse_args();run(a.board)
