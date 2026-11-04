"""Execute the owner's exact 21-erase review, one board per RTC window."""
import argparse,binascii,json,time
from contextlib import contextmanager
from pathlib import Path
import devtools_2512_session as ds
import inventory_unified_cleanup as inv
import nf_opaque as opaque
from journal_rotation_plan import reserve
from serial_test_coordination import drift_pending
t=ds.t;Q=ds.Q;SCOPE=Q/'2604-2609-REC-cleanup-scope-20261102-r3'
BM=b'BM> ';FT=ds.d.FT;MONS=tuple(f'B{b}> '.encode() for b in range(4))

def approved(board):
 review=json.loads((SCOPE/'review.json').read_text());a=json.loads((SCOPE/'approval.json').read_text())
 assert a['approved'] and a['owner_answer']=='Approve both reviewed cleanups'
 for name,key in (('plan.json','plan_sha256'),('review-document.txt','review_document_sha256')):
  assert t.sha((SCOPE/name).read_bytes())==a[key]==review[key]
 p=json.loads((SCOPE/'plan.json').read_text());assert p['total_erases']==21 and p['total_appends']==21 and p['F_writes']==p['MON_writes']==p['SPI_writes']==p['RTC_setting_writes']==0
 assert p['boards'][board]['total_erases']==(9 if board=='2604' else 12)
 assert json.loads((Q/'2609-REC-cleanup-tools-20261102-r1/report.json').read_text())['passed']
 assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
 return p['boards'][board]

def await_window(seconds):
 announced=False
 while True:
  try:ds.ins.window(seconds);return
  except AssertionError:
   if not announced:print('WAIT RTC priority/window; no board port opened',flush=True);announced=True
   time.sleep(1)

@contextmanager
def escrow(board,out,r):
 ds.ins.window(420);out.mkdir();(out/'.gitignore').write_text('*\n');x=inv.Escrow(out,r,board);x.save()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 with t.serial_lease(board+'-approved-REC-utility-cleanup',timeout=30):
  ds.ins.window(420);m=x.original=json.loads(x.mp.read_text())
  assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['block_snapshot'] and not m['physical_reset_pending']
  assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
  t.save(out/'marker-before.json',m)
  with (out/'serial.jsonl').open('x') as log:
   try:
    s=x.s=inv.BoardSession(out,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);x.mon()
    face=x.cmd('VERSION');assert b'STR8-N MON B  gen 00000010' in face and inv.IDS[board][2] in face
    prefix=s.dump(0x200,0x1ff+len(reader));x.zp=s.dump(0,0xdf);x.high=s.dump(0x6b00,0x77ff);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
    for name,data in (('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)):
     opaque.durable_file(out/name,data)
    x.mark(REC_cleanup_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);x.borrowed=True
    x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;x.ram=prefix+memory[len(reader):];opaque.durable_file(out/'owner-ram.bin',x.ram)
    assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3']
    yield x
   except BaseException as e:r['error']=repr(e);x.save();raise
   finally:
    try:
     if x.borrowed:
      x.mon();assert x.hooks()==x.oldhooks;x.restore_high();x.rec();s.service(reader)
      try:
       actual=s.client.flash(3);assert t.sha(actual)==getattr(x,'expected_b3_sha256',m['current_physical_bank_sha256']['B3']);r['planned_B3_verified']=True
      finally:r.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
    finally:
     if x.s:x.s.link.close();r['port_released']=True
     if x.borrowed:
      restored=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored'))
      x.mark(REC_cleanup_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=bool(r.get('write_phase_started')) or not restored,final_prompt='REC>' if restored else 'RESTORATION REQUIRED')
     x.save()

def run(board):
 assert board in ('2604','2609');p=approved(board);out=Q/f'{board}-REC-utility-cleanup-installed-20261102-r1';assert not out.exists()
 before={b:(SCOPE/board/f'B{b}-original.bin').read_bytes() for b in range(4)}
 r=dict(board=board,passed=False,completed=[],checks=[],erase_requests=0,automatic_retries=0,F_writes=0,MON_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0,reviewed_total_erases=p['total_erases'],plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()))
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
 maint=t.ROOT/'BUILD/loadable-maint-full-r2/MAINT.bin';flash=t.ROOT/'firmware/ram-tools/flash-g2/FLASH.bin';top=json.loads((SCOPE/'plan.json').read_text());qa=top['REC_tools_admission']
 assert t.sha(maint.read_bytes())==qa['MAINT_sha256'] and t.sha(flash.read_bytes())==qa['FLASH_sha256']
 await_window(420)
 try:
  with escrow(board,out,r) as x:
   s=x.s
   def check(label):r['checks'].append(label);x.save();print('PASS '+board+' '+label,flush=True)
   def leave(prompt):
    assert s.context==prompt;x.cmd('Q',(t.MON,t.REC));x.mon()
   opaque.durable_file(out/'driver-as-executed.py',Path(__file__).read_bytes());t.save(out/'plan.json',p)
   assert x.original['current_physical_bank_sha256']==p['before_bank_sha256']
   for b in range(4):
    actual=s.client.flash(b);assert actual==before[b];opaque.durable_file(out/f'B{b}-before.bin',actual)
   x.wb();x.cmd('TABLE P');meta=b''.join(x.raw(a) for a in range(0,0x800,64));assert all(meta[0x40+64*k+63]!=0xa5 for k in range(8));opaque.durable_file(out/'SPI-metadata-before.bin',meta)
   archive=t.ROOT/f'local-archives/2604-2609-REC-cleanup-20261102/{board}';archive.mkdir(parents=True);(archive/'.gitignore').write_text('*\n')
   for file in (list(out.glob('*before.bin'))+[out/'owner-ram.bin',out/'owner-zp.bin',out/'marker-before.json',out/'plan.json']):
    opaque.durable_file(archive/file.name,file.read_bytes())
   for row in p['old_journal_rows']:opaque.durable_file(archive/row['file'],(SCOPE/board/row['file']).read_bytes())
   check('fresh preimages, empty PROGRAM and permanent originals/history archive admitted')
   ds.ins.window(300);assert not drift_pending(),'Yield before any flash write'
   r['write_phase_started']=True;x.save();x.mark(REC_cleanup_write_worker_active=True,REC_cleanup_pending=True)
   x.rec();s.load(writer,t.sha(writer),opaque.PROMPT);wire=opaque.Wire(s.link.serial,timeout=90,progress=lambda v:print(board+' '+v,flush=True))
   state=before[3]
   for index,target in enumerate(p['targets']):
    b,page=target['bank'],target['page'];assert (b,page) not in ((3,0xa0),(3,0xb0),(3,0xc0),(3,0xd0),(3,0xf0))
    old=wire.read_sector(b,page);assert t.sha(old)==target['before_sha256'];body=(SCOPE/board/target['file']).read_bytes();assert len(body)==4096 and t.sha(body)==target['sha256'] and old!=body
    forecast,op=reserve(state,b*8+(page-0x80)//16);assert op==p['operations'][index]
    if b==3:
     buf=bytearray(forecast);offset=(page-0x80)*256;buf[offset:offset+4096]=body;forecast=bytes(buf)
    r['pending_target']=target['address'];r['erase_requests']+=1;x.save();s.context=None
    assert not wire.replace_sector(b,page,old,body);s.context=opaque.PROMPT;assert wire.read_sector(b,page)==body
    state=forecast;x.expected_b3_sha256=t.sha(state);opaque.durable_file(out/f'B{b}-{page:02X}-after.bin',body)
    r['completed'].append(target['address']);r.pop('pending_target');x.save();print('VERIFIED '+board+' '+target['address'],flush=True)
   x.rec();s.service(reader)
   for b in range(4):
    actual=s.client.flash(b);assert t.sha(actual)==p['after_bank_sha256'][f'B{b}'];opaque.durable_file(out/f'B{b}-after.bin',actual)
   assert t.classify_journal((out/'B3-after.bin').read_bytes())==p['journal_after'];r['NVM_verified']=True
   check('all four banks match exact approved result; F/MON/settings/history retained as reviewed')
   s.client.restore_owner(x.ram,x.zp);s.context=t.REC;x.mon()
   face=x.cmd('VERSION');assert f'Board: {board}'.encode() in face and b'Battery:' in face and b'unavailable' not in face
   apps=x.cmd('APPS');assert b'FLASH/MAINT: RAM BIN' in apps and b'ASM B0:A000' in apps and b'DBG B0:C000' in apps
   assert b'B1:A xfer' in x.cmd('M2');table=x.cmd('TABLE 2',MONS);assert b'End; SR01 has no payload CRC.' in table and b'Syntax' not in table;x.mon()
   x.cmd('R CLOCK',(t.CLOCK,));x.mon();check('VERSION/STATUS/APPS/map/TABLE/CLOCK and current ASM/DBG retained')
   import trial_flash_transfer_readonly as ro
   x.cmd('STORE 0 9000 5800 66FF CLEANNO',(ro.STORE_YES,));s.link.send(b'NO\r');assert b'Canceled' in s.until(MONS);x.mon()
   from trial_s19_ram import READY
   x.cmd('S19',(READY,));s.link.send(b'\x03');assert b'S19 stopped $03' in s.until((t.MON,));check('shared STORE admission and S19 loader retain cancel paths')
   x.wb();x.cmd('TABLE P');after_meta=b''.join(x.raw(a) for a in range(0,0x800,64));assert after_meta==meta;opaque.durable_file(out/'SPI-metadata-after.bin',after_meta);check('PROGRAM/WORK metadata and geometry exact; no SPI data writes')
   x.rec();s.load(maint.read_bytes(),qa['MAINT_sha256'],BM)
   assert b'Copy RAM or flash' in x.cmd('?',(BM,));assert b'REC 0200 r1' in x.cmd('VERSION',(BM,));assert b'CLOCK' in x.cmd('TABLE',(BM,));x.cmd('M3',(BM,))
   x.cmd('N 10 FF',(BM,));x.cmd('P 0 12 34',(BM,));assert b'12 34 FF' in x.cmd('D 0-F',(BM,));assert b'WRITE? TYPE Y' not in x.cmd('E 3 C-D',(BM,));leave(BM)
   x.rec();s.load(flash.read_bytes(),qa['FLASH_sha256'],FT);assert b'FLASH g2' in x.cmd('VERSION',(FT,));x.cmd('BANK 0',(FT,));x.cmd('READ 8000',(FT,));assert b'FF FF FF FF' in x.cmd('VIEW 000',(FT,))
   x.cmd('I 9000 9FFF',(ro.YES,));assert b'Canceled' in x.cmd('NO',(FT,));leave(FT);check('full MAINT and FLASH REC BINs work after resident copies are removed')
   x.rec();s.service(reader)
   for b in range(4):assert t.sha(s.client.flash(b))==p['after_bank_sha256'][f'B{b}']
   check('final four-bank readback exact; positive checks added no flash writes')
  r['passed']=len(r['checks'])==7 and r.get('NVM_verified') and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','planned_B3_verified','port_released'))
  t.save(out/'report.json',r);assert r['passed']
 finally:
  if out.exists():
   t.save(out/'report.json',r)
   mp=Q/f'device-operations/{board}.json';m=json.loads(mp.read_text())
   if r.get('write_phase_started'):
    m.update(REC_cleanup_write_worker_active=False,REC_cleanup_pending=not r['passed'],block_snapshot=not r['passed'])
    if r.get('NVM_verified'):
     counts=m['current_tracked_erase_counts'].copy()
     for i,value in enumerate(p['journal_after']['counts']):counts[f'B{i//8}:{i%8+8:X}']=value
     for name,i in zip('ABCDEF',range(26,32)):counts[name]=p['journal_after']['counts'][i]
     m.update(current_physical_bank_sha256=p['after_bank_sha256'],current_tracked_erase_counts=counts,current_wear_counts=p['journal_after']['counts'],current_journal_sequence=p['journal_after']['sequence'],current_journal_valid_records=p['journal_after']['valid_records'],current_valid_journal_records=p['journal_after']['valid_records'],FLASH_installed=False,bank_maint_installed=False,flash_utility_installed=False,FLASH_residency='Host-loaded RAM BIN',MAINT_residency='Host-loaded RAM BIN',shared_MON_transfer_services_retained=True,legacy_ASM_B1_E_F_present=False,last_REC_utility_cleanup=str(out/'report.json'),total_erased_flash_bytes=36864)
    t.save(mp,m)
 print('PASS '+board+' approved cleanup; 36 KiB erased; F/MON exact; RAM restored; port free',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('board',choices=['2604','2609']);a=p.parse_args();run(a.board)
