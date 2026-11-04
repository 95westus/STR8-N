"""Execute the approved SS2 management-only scope, one board per RTC window."""
import argparse,binascii,json,re,time
from contextlib import contextmanager
from pathlib import Path
import devtools_2512_session as ds
import inventory_unified_cleanup as inv
from serial_test_coordination import drift_pending
import nf_opaque

t=ds.t;Q=ds.Q;SCOPE=Q/'SS2-64K-three-board-scope-20261102-r1'
WORK=b'WORK> ';MENU=b'STORAGE> ';UNLOCK=b'Enable SRAM writes for this RAM session? Type YES: '
CONFIRM=b'Changes storage metadata. Type YES: ';APPLY=b'Apply? [y/N]: '

def approved():
 p=json.loads((SCOPE/'plan.json').read_text());a=json.loads((SCOPE/'approval.json').read_text());v=json.loads((SCOPE/'review.json').read_text())
 assert a['approved'] and a['owner_answer']=='approved' and a['SPI_address_allowance']==586
 for n,k in (('plan.json','plan_sha256'),('review-document.txt','review_document_sha256')):assert t.sha((SCOPE/n).read_bytes())==a[k]==v[k]
 assert p['flash_erases']==p['flash_writes']==p['journal_appends']==0
 f=json.loads((t.REPO/'F_FREEZE.json').read_text());assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==p['F_sha256']==f['sha256']
 assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
 return p

def wait_window(seconds):
 last=0
 while True:
  try:ds.ins.window(seconds);return
  except AssertionError as error:
   if time.monotonic()-last>50:print('WAIT RTC priority/window; no board port opened: '+str(error),flush=True);last=time.monotonic()
   time.sleep(1)

@contextmanager
def escrow(board,out,r,resume=False):
 ds.ins.window(720);out.mkdir();(out/'.gitignore').write_text('*\n');x=inv.Escrow(out,r,board);x.save()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 with t.serial_lease(board+'-approved-SS2-64K-standardization',timeout=30):
  ds.ins.window(720);m=x.original=json.loads(x.mp.read_text())
  assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m['physical_reset_pending']
  if resume:
   prior=json.loads((Q/f'{board}-SS2-64K-standardized-20261102-r1/report.json').read_text())
   assert prior['metadata_operation_started'] and prior['SPI_change_pending'] and prior['port_released'] and prior['owner_RAM_restored'] and prior['owner_ZP_restored']
   assert prior['error']=="AssertionError(b'E80\\r\\nPB> ')" and m['block_snapshot'] and m['SS2_SPI_restore_pending']
  else:assert not m['block_snapshot']
  assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
  t.save(out/'marker-before.json',m)
  with (out/'serial.jsonl').open('x') as log:
   try:
    s=x.s=inv.BoardSession(out,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);x.mon()
    face=x.cmd('VERSION');assert inv.IDS[board][2] in face and b'STR8-N MON B  gen 00000010' in face
    prefix=s.dump(0x200,0x1ff+len(reader));x.zp=s.dump(0,0xdf);x.high=s.dump(0x6b00,0x77ff);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
    for n,v in (('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)):nf_opaque.durable_file(out/n,v)
    x.mark(SS2_standardization_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);x.borrowed=True
    x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;x.ram=prefix+memory[len(reader):];nf_opaque.durable_file(out/'owner-ram.bin',x.ram)
    yield x
   except BaseException as error:r['error']=repr(error);x.save();raise
   finally:
    try:
     if x.borrowed:
      if x.s.context in (CONFIRM,APPLY):x.cmd('NO',(WORK,))
      if x.s.context==UNLOCK:x.cmd('NO',(MENU,))
      if x.s.context==MENU:x.cmd('Q',(t.MON,))
      x.mon();assert x.hooks()==x.oldhooks;x.restore_high();x.rec();s=x.s;s.service(reader)
      try:
       assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3'];r['F_images_settings_history_exact']=True
      finally:r.update(s.client.restore_owner(x.ram,x.zp));s.context=t.REC
    finally:
     if x.s:x.s.link.close();r['port_released']=True
     if x.borrowed:
      restored=bool(r.get('owner_RAM_restored') and r.get('owner_ZP_restored'));pending=bool(r.get('SPI_change_pending'))
      x.mark(SS2_standardization_worker_active=False,application_ram_restored=restored,application_RAM_restore_pending=not restored,block_snapshot=not restored or pending,SS2_SPI_restore_pending=pending,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_SS2_standardization=str(out/'report.json'))
     x.save()

def reader_packet():
 folder=t.ROOT/'BUILD/SRAM-reader-current-r2';m=json.loads((folder/'manifest.json').read_text());pb=(folder/m['filename']).read_bytes()
 provider=(t.REPO/'monitors/candidates/program-sp1-g00000002-wide-r5/STR8N-PROGRAM-SP1-6B00.bin').read_bytes()
 assert t.sha(pb)==m['sha256']=='12b4836319b6bf77e6031079c18f856df94bb52779a837c5f05be164040b9126'
 assert len(provider)==3328 and t.sha(provider)==m['provider_sha256'] and binascii.crc_hqx(provider,65535)==0
 # Reuse the already-qualified read-only helper and paired provider exactly.
 # This RAM transport copies the provider, restores the helper's first3 bytes,
 # then enters it. No assembly/build, SPI write command or flash writer exists.
 a=bytearray(b'\xff'*0x1c00);a[:len(pb)]=pb;a[0x0f00:0x1c00]=provider
 code=bytearray(bytes.fromhex('78 D8 A2 00'))
 for page in range(13):code+=bytes((0xbd,0,0x11+page,0x9d,0,0x6b+page))
 code+=bytes((0xe8,0xd0,(0x1004-(0x1000+len(code)+3))&255))
 for i,v in enumerate(pb[:3]):code+=bytes((0xa9,v,0x8d,i,2))
 # The paired reader calls SP_TRANSFER directly. WORK uses this scratch area;
 # initialize that provider's volatile profile instead of inheriting WB state.
 code+=bytes.fromhex('A9 01 8D CC 69')
 code+=bytes.fromhex('4C 00 02');assert len(code)<256
 a[0xe00:0xe00+len(code)]=code;a[:3]=bytes.fromhex('4C 00 10')
 return bytes(a)

def finish_readonly_verification(board):
 p=approved();plan=p['boards'][board];prior=Q/f'{board}-SS2-64K-standardized-20261102-r1';out=Q/f'{board}-SS2-64K-readonly-continuation-20261102-r1'
 old=json.loads((prior/'report.json').read_text());assert old['metadata_operation_started'] and old['SPI_change_pending'] and old['owner_RAM_restored'] and old['port_released']
 before=(prior/'SPI-before.bin').read_bytes();expected=(SCOPE/board/'SPI-metadata-expected.bin').read_bytes()+before[2048:]
 wait_window(900);r=dict(board=board,passed=False,SPI_change_pending=True,flash_writes=0,journal_appends=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,physical_resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,native_operation_replayed=False)
 with escrow(board,out,r,resume=True) as x:
  # Finish restoration to the original operation's escrow, not a new target.
  x.ram=(prior/'owner-ram.bin').read_bytes();x.zp=(prior/'owner-zp.bin').read_bytes();x.high=(prior/'provider-cache-before.bin').read_bytes();x.oldhooks=(prior/'hooks-before.bin').read_bytes()
  for n,body in (('owner-ram.bin',x.ram),('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)):(out/('restoration-target-'+n)).write_bytes(body)
  current=metadata(x);assert current==expected[:2048],'Native upgrade metadata differs from exact reviewed forecast'
  after=capture(x,'after',reader_packet());assert after==expected
  r['whole_SPI_matches_exact_plan']=True;r['SPI_change_pending']=False;x.save()
  from program_format import inspect
  layout=inspect(after);assert layout['format']=='SS2' and layout['boundary']=='10000' and not layout['records'];t.save(out/'layout-after.json',layout)
  x.rec();x.s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
  for b in range(4):
   v=x.s.client.flash(b);assert v==(prior/f'B{b}-before.bin').read_bytes();nf_opaque.durable_file(out/f'B{b}-after.bin',v)
  r['all_four_banks_exact']=True
 r['passed']=r['whole_SPI_matches_exact_plan'] and r['all_four_banks_exact'] and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','port_released'));t.save(out/'report.json',r);assert r['passed']
 nf_opaque.durable_file(prior/'report-before-readonly-continuation.json',(prior/'report.json').read_bytes())
 nf_opaque.durable_file(prior/'SPI-after.bin',(out/'SPI-after.bin').read_bytes())
 for b in range(4):nf_opaque.durable_file(prior/f'B{b}-after.bin',(out/f'B{b}-after.bin').read_bytes())
 t.save(prior/'layout-after.json',layout)
 old['initial_verification_error']=old.pop('error');old.update(passed=True,SPI_change_pending=False,whole_SPI_matches_exact_plan=True,all_four_banks_exact=True,readonly_continuation=str(out/'report.json'),native_operation_replayed=False)
 old['checks']+=['Read-only continuation: SS2/64K exact; all128KiB SPI matches reviewed delta','All four flash banks exact; original ownerRAM/ZP/cache/hooks restored']
 t.save(prior/'report.json',old)
 mp=Q/f'device-operations/{board}.json';m=json.loads(mp.read_text());m.update(SPI_format='SS2',PROGRAM_boundary='10000',WORKSPACE_start='10000',SS2_SPI_restore_pending=False,block_snapshot=False,last_SS2_standardization=str(prior/'report.json'));t.save(mp,m)
 print('PASS '+board+' SS2 verified read-only; native operation not repeated; original owner restored; REC>; port released',flush=True)

def capture(x,label,packet,priority=True):
 s=x.s;x.rec();s.load(packet,t.sha(packet),t.PB);parts=bytearray()
 for address in range(0,0x20000,64):
  if priority and drift_pending():raise InterruptedError('RTC priority during pre-write read; no layout operation started')
  s.link.send(b'R'+address.to_bytes(3,'big').hex().upper().encode()+b'\r');face=s.until((t.PB,))
  match=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(match)==1,face
  frame=bytes.fromhex(match[0].decode());assert int.from_bytes(frame[:3],'big')==address and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
  parts.extend(frame[3:-2])
  if (address+64)%32768==0:print(f'{x.r["board"]} {label}: {address+64}/131072',flush=True)
 body=bytes(parts);nf_opaque.durable_file(x.out/f'SPI-{label}.bin',body);x.mon();return body

def metadata(x):
 x.wb();x.cmd('TABLE P');face=x.cmd('WORK');assert b'WORKSPACE' in face.upper() or b'WORK' in face.upper()
 body=b''.join(x.raw(a) for a in range(0,0x800,64));x.mon();return body

def run(board):
 p=approved();plan=p['boards'][board];out=Q/f'{board}-SS2-64K-standardized-20261102-r1';assert not out.exists()
 packet=reader_packet();wait_window(720)
 r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_appends=0,RTC_SET=0,trim_writes=0,PF_ACK=0,physical_resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,SPI_change_pending=False,metadata_operation_started=False,automatic_retries=0,scope_plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()))
 oldmeta=(SCOPE/board/'SPI-metadata-original.bin').read_bytes();newmeta=(SCOPE/board/'SPI-metadata-expected.bin').read_bytes();assert t.sha(oldmeta)==plan['original_metadata_sha256'] and t.sha(newmeta)==plan['expected_metadata_sha256']
 storage=(t.ROOT/'BUILD/storage-installed-auto-r2/SRAM-WORK-g4-flash.bin').read_bytes();assert t.sha(storage)==p['installed_storage_image_sha256']
 archive=t.ROOT/f'local-archives/SS2-64K-standardization-20261102/{board}'
 with escrow(board,out,r) as x:
  s=x.s;nf_opaque.durable_file(out/'driver-as-executed.py',Path(__file__).read_bytes());t.save(out/'plan.json',plan)
  def check(text):r['checks'].append(text);x.save();print('PASS '+board+' '+text,flush=True)
  original={b:s.client.flash(b) for b in range(4)}
  for b,v in original.items():assert t.sha(v)==plan['reference_flash_bank_sha256'][f'B{b}'];nf_opaque.durable_file(out/f'B{b}-before.bin',v)
  assert original[1][0x3000:0x6000]==storage
  current=metadata(x);assert current==oldmeta,'Metadata differs from reviewed original; no write allowed'
  before=capture(x,'before',packet);assert before[:2048]==oldmeta
  from program_format import inspect
  layout=inspect(before);assert not layout['records']
  if board=='2604':assert all(before[0x31f+32*i]!=0xa5 for i in range(4)),'Preexisting WORK claim; no epoch rollover allowed'
  check('fresh full128KiB SPI and four-bank captures; empty PROGRAM and no conflicting claim')
  archive.mkdir(parents=True);(archive/'.gitignore').write_text('*\n')
  files={file.name:file for file in list(out.glob('*before.bin'))+[out/'owner-ram.bin',out/'owner-zp.bin',out/'marker-before.json',out/'plan.json']}
  for file in files.values():
   nf_opaque.durable_file(archive/file.name,file.read_bytes())
  ds.ins.window(420);assert not drift_pending(),'RTC priority before any SPI management mutation'
  x.cmd('R WORK',(WORK,));x.cmd('!',(MENU,));x.cmd('UNLOCK',(UNLOCK,));x.cmd('YES',(MENU,));x.cmd('W',(WORK,))
  face=x.cmd('?',(WORK,));assert b'PROGRAM' in face.upper() or b'WORKSPACE' in face.upper()
  if board=='2604':x.cmd('P 64',(APPLY,));confirm='Y';success=b'Resized.'
  else:x.cmd('U',(CONFIRM,));confirm='YES';success=b'Upgraded.'
  if drift_pending():
   x.cmd('NO',(WORK,));raise InterruptedError('RTC priority; confirmation cancelled without storage writes')
  r['SPI_change_pending']=True;r['metadata_operation_started']=True;x.save();x.mark(SS2_SPI_restore_pending=True)
  face=x.cmd(confirm,(WORK,));assert success in face,face
  # Do not issue another mutating WORK request: it could start another epoch.
  x.cmd('?',(WORK,));x.mon();check('native management operation reported success; no payload operation issued')
  after=capture(x,'after',packet,priority=False)
  wanted=newmeta+before[2048:];assert after==wanted,'Unexpected metadata or payload delta; retain originals for reviewed recovery'
  r['SPI_change_pending']=False;r['whole_SPI_matches_exact_plan']=True;x.save()
  assert after[0x40:0x240]==before[0x40:0x240] and after[0x800:]==before[0x800:]
  post=inspect(after);assert post['format']=='SS2' and post['boundary']=='10000' and not post['records'];t.save(out/'layout-after.json',post)
  check('SS2/64K verified; PROGRAM directory and every payload byte unchanged')
  assert metadata(x)==newmeta
  x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
  for b in range(4):
   v=s.client.flash(b);assert v==original[b];nf_opaque.durable_file(out/f'B{b}-after.bin',v)
  r['all_four_banks_exact']=True;check('F/MON/images/settings/boot-wear history byte-for-byte exact')
 r['passed']=r['whole_SPI_matches_exact_plan'] and r['all_four_banks_exact'] and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','F_images_settings_history_exact','port_released'))
 t.save(out/'report.json',r);assert r['passed']
 marker_path=Q/f'device-operations/{board}.json';m=json.loads(marker_path.read_text());m.update(SPI_format='SS2',PROGRAM_boundary='10000',WORKSPACE_start='10000',SS2_SPI_restore_pending=False,block_snapshot=False,last_SS2_standardization=str(out/'report.json'));t.save(marker_path,m)
 print('PASS '+board+' SS2/64K; data and owner restored; REC>; port released',flush=True)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('board',choices=['2512','2604','2609']);a.add_argument('--finish-readonly',action='store_true');args=a.parse_args()
 if args.finish_readonly:finish_readonly_verification(args.board)
 else:run(args.board)
