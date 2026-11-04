"""2512 extracted-kit RAM acceptance; exact kit payloads and console sender."""
import importlib.util,json,re,subprocess,sys,time,zipfile
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,ins
from serial_test_coordination import drift_pending
PACKAGE=t.ROOT/'BUILD/devtools-g2-candidate2-20261102-r2'
EXTRACT=t.ROOT/'BUILD/devtools-g2-extracted-acceptance-20261102-r2'
LABEL='STR8N-DEVTOOLS-g2-candidate2'
KIT=EXTRACT/LABEL
OUT=Q/'2512-devtools-g2-extracted-RAM-20261102-r2'
START=b'DBG RAM start 0200-3FFF; Q MON> '

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def run():
 pr=json.loads((PACKAGE/'packaging-receipt.json').read_text());zpath=PACKAGE/(LABEL+'.zip')
 assert pr['passed'] and t.sha(zpath.read_bytes())==pr['ZIP_sha256']=='7cdf5b00322426ad00a8e456bc236d34294dfe8a7f876732113c3ac0362e69d2'
 EXTRACT.mkdir()
 with zipfile.ZipFile(zpath) as z:
  for member in z.infolist():
   dest=(EXTRACT/member.filename).resolve();assert dest.is_relative_to(EXTRACT.resolve())
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
 for command in ([sys.executable,'verify_kit.py'],[sys.executable,'terminal/nf_console.py','--help']):
  result=subprocess.run(command,cwd=KIT,capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
 mf=json.loads((KIT/'KIT-MANIFEST.json').read_text());core=module('console_core',KIT/'terminal/console_core.py');console=module('extracted_devtools_console',KIT/'terminal/nf_console.py')
 assert console.VERSION=='0.1.2' and Path(core.__file__).is_relative_to(KIT) and Path(console.__file__).is_relative_to(KIT)
 payload={name:core.ram_image(KIT/'payload'/name) for name in ('ASM-RAM.bin','DBG-RAM.bin')}
 for name,(path,body,digest) in payload.items():assert digest==mf['files']['payload/'+name]['sha256']
 print('Extracted developer kit verified; waiting for RTC-priority window (360s)',flush=True)
 while True:
  try:ins.window(360);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',CPU='65C02',passed=False,checks=[],ZIP_sha256=pr['ZIP_sha256'],kit_path=str(KIT),console_version=console.VERSION,console_core_sha256=t.sha((KIT/'terminal/console_core.py').read_bytes()),transfers=[],flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0,GUI_physical_keys_tested=False,source_SAVE_tested=False)
 with escrow(OUT,r,'2512-extracted-devtools-g2-RAM-only',window=360,cache_first=0x6b00,cache_end=0x77ff) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  t.save(OUT/'authorization.json',dict(owner_statement='Continue with the extracted-kit RAM-only acceptance on 2512. Keep F golden, preserve settings/history and owner RAM, yield to RTC collection, and leave the other boards alone.',ZIP_sha256=pr['ZIP_sha256']))
  def check(name):r['checks'].append(name);x.save();print('PASS2512 '+name,flush=True)
  def boundary():
   if drift_pending():raise InterruptedError('RTC priority at safe case boundary; restore and release')
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,body in old.items():
   assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(body)
  assert old[0][0x2000:0x4000]==(KIT/'payload/ASM-FLASH.bin').read_bytes()
  assert old[0][0x4000:0x6000]==(KIT/'payload/DBG-FLASH.bin').read_bytes()
  assert old[0][0x5800:0x6000]==(KIT/'payload/FLASH-SOURCE-7000.bin').read_bytes()
  assert t.sha(old[3][0x7000:])==mf['F_sha256'];check('fresh-owner-four-bank-and-extracted-installed-image-pairing')
  with (OUT/'extracted-console-events.jsonl').open('x') as events:
   def sender():
    def emit(kind,*values):
     encoded=[dict(hex=v.hex()) if isinstance(v,bytes) else v for v in values]
     events.write(json.dumps(dict(time=time.time(),event=kind,values=encoded))+'\n');events.flush()
     if kind=='error':raise AssertionError(values)
     if kind=='transfer':r['transfers'].append(values[0]);x.save()
    c=core.Session(emit);c.attach(x.s.link.serial);return c
   def load(name,prompt):
    boundary();x.rec();face=x.cmd('',(t.REC,));assert not x.s.link.pending
    c=sender();c.receive(face);path,body,digest=payload[name]
    x.s.context=None;c.start(path,body,digest,from_recovery=True);deadline=time.monotonic()+65
    while time.monotonic()<deadline:
     c.tick()
     if not c.busy and c.tail.endswith(prompt):break
     time.sleep(.002)
    else:raise TimeoutError('Extracted sender did not reach '+repr(prompt)+'; tail '+repr(bytes(c.tail)))
    assert c.last_transfer==(str(path),body,digest) and r['transfers'][-1]['host_complete']
    x.s.context=prompt;c.port=None
   boundary();x.rec();face=x.cmd('L',(core.SEND_BIN,));c=sender();c.receive(face);assert c.prompt=='send-bin';assert c.cancel()
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    c.tick()
    if c.prompt=='rec':break
    time.sleep(.002)
   else:raise TimeoutError('Ctrl-C did not return to REC>')
   assert not c.transfer and not c.last_transfer;x.s.context=t.REC;c.port=None
   check('extracted-console-Ctrl-C-at-SEND-BIN-with-zero-payload')
   load('ASM-RAM.bin',AP);assert b'SAVE' in x.cmd('?')
   lines=[line for line in (KIT/'examples/HELLO.asm').read_text().splitlines() if re.match(r'^\d+ ',line)]
   assert len(lines)==6
   for line in lines:x.cmd(line)
   assert b'OK 8 bytes' in x.cmd('ASM')
   face=x.cmd('LST');assert b'0200 A9 23' in face and b'0202 20 6D 7E' in face
   face=x.cmd('SYMS');assert b'Error' not in face and b'REFUSED' not in face
   assert b'0200: A9 23' in x.cmd('DUMP') and b'S1' in x.cmd('S19')
   x.cmd('QUIT',(t.MON,));expected=bytes.fromhex('A923206D7E4C677E');assert x.s.dump(0x200,0x207)==expected
   face=x.cmd('G 0200',(t.MON,));assert b'#' in face and x.hooks()==x.oldhooks
   check('exact-extracted-ASM-BIN-example-assemble-export-readback-run-and-HOLD')
   def regs(face=None):
    face=x.cmd('R') if face is None else face;m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face
    return dict(zip(('PC','A','X','Y','P','S'),(int(v,16) for v in m.groups())))
   def fixture():x.cmd('M 0200 '+expected.hex(' ').upper());x.cmd('R PC 0200')
   load('DBG-RAM.bin',DP);assert regs()['PC']==0x1002;fixture()
   face=x.cmd('U 0200 3');assert b'LDA' in face and b'JSR' in face and b'JMP' in face
   assert regs(x.cmd('S'))['PC']==0x202;face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x205
   x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x200,0x207)==expected
   check('exact-extracted-DBG-BIN-seed-R-U-S-public-N-C-and-HOLD')
   load('DBG-RAM.bin',DP);fixture();x.cmd('B 0205');assert b'0205\r\n' in x.cmd('B');x.cmd('BC');assert b'0205\r\n' not in x.cmd('B')
   x.s.link.send(b'\x03');x.s.until((DP,));assert regs()['PC']==0x200
   x.cmd('B 0205');x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x200,0x207)==expected
   check('extracted-DBG-BC-Ctrl-C-and-X-hook-patch-cleanup')
   boundary();x.cmd('APPS');x.cmd('R ASM',(AP,));assert b'SAVE' in x.cmd('?');x.cmd('QUIT',(t.MON,))
   x.cmd('R DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
   check('installed-AP02-R-ASM-R-DBG-front-doors-remain-usable')
   x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
   for b in range(4):
    after=x.s.client.flash(b);assert after==old[b];(OUT/f'B{b}-after.bin').write_bytes(after)
   check('all-four-flash-banks-boot-settings-journal-and-golden-F-exact')
  r['functional_checks_passed']=True
 r['passed']=bool(len(r['checks'])==7 and len(r['transfers'])==3 and r.get('functional_checks_passed') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('port_released'))
 t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 extracted developer kit RAM acceptance; owner/cache/hooks restored; no NVM writes; REC>; COM4 free',flush=True)

if __name__=='__main__':run()
