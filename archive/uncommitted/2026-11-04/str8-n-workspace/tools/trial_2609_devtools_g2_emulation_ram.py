"""2609-only 816 emulation qualification; accepted extracted tools, RAM only."""
import importlib.util,json,re,subprocess,sys,time,zipfile
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,ins
from serial_test_coordination import drift_pending
PKG=t.ROOT/'BUILD/devtools-g2-candidate2-20261102-r2'
EXTRACT=t.ROOT/'BUILD/devtools-g2-2609-emulation-20261102-r1'
LABEL='STR8N-DEVTOOLS-g2-candidate2';KIT=EXTRACT/LABEL
OUT=Q/'2609-devtools-g2-emulation-RAM-20261102-r1'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def run():
 zpath=PKG/(LABEL+'.zip');assert t.sha(zpath.read_bytes())=='7cdf5b00322426ad00a8e456bc236d34294dfe8a7f876732113c3ac0362e69d2'
 EXTRACT.mkdir()
 with zipfile.ZipFile(zpath) as z:
  for member in z.infolist():
   dest=(EXTRACT/member.filename).resolve();assert dest.is_relative_to(EXTRACT.resolve())
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
 result=subprocess.run([sys.executable,'verify_kit.py'],cwd=KIT,capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
 mf=json.loads((KIT/'KIT-MANIFEST.json').read_text());core=module('console_core',KIT/'terminal/console_core.py')
 payload={name:core.ram_image(KIT/'payload'/name) for name in ('ASM-RAM.bin','DBG-RAM.bin')}
 for name,(_,body,digest) in payload.items():assert digest==mf['files']['payload/'+name]['sha256']
 f=json.loads((t.REPO/'F_FREEZE.json').read_text());assert f['sha256']==mf['F_sha256']
 assert all(t.sha((t.REPO/name).read_bytes())==h for name,h in f['sources'].items())
 print('2609 extracted ASM/DBG emulation trial waiting for RTC window420s',flush=True)
 while True:
  try:ins.window(420);break
  except AssertionError:time.sleep(1)
 r=dict(board='2609',CPU='65C816 emulation',passed=False,checks=[],ZIP_sha256=t.sha(zpath.read_bytes()),kit_path=str(KIT),transfers=[],ambiguous_opcodes=[],unsupported_opcodes=[],flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_writes=0,resets=0,power_cuts=0,firmware_builds=0,native_mode_tested=False,persistent_source_storage_tested=False,AP02_installation_tested=False)
 with escrow(OUT,r,'2609-ASM-DBG-816-emulation-RAM-only',window=420,cache_first=0x6b00,cache_end=0x77ff,board='2609') as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'escrow-as-executed.py').write_bytes((t.ROOT/'tools/devtools_2512_session.py').read_bytes())
  t.save(OUT/'authorization.json',dict(owner_statement='Continue with 816 emulation qualification on 2609, starting in RAM. Keep F golden, preserve images, settings/history and owner RAM, yield to RTC collection, and leave the other boards alone.',ZIP_sha256=r['ZIP_sha256']))
  def check(name):r['checks'].append(name);x.save();print('PASS2609 '+name,flush=True)
  def boundary():
   if drift_pending():raise InterruptedError('RTC priority at safe boundary; restore and release')
  def poke(addr,body):
   for off in range(0,len(body),8):x.cmd(f'M {addr+off:04X} '+body[off:off+8].hex(' ').upper())
  def context_probe():
   x.mon()
   # SEC/XCE keeps E=1 and records the previous E in C. Long stores avoid
   # depending on DBR. Observe DBR/D/PBR, then normalize the required MON
   # context to zero (a no-op for the admitted context) before returning.
   code=bytes.fromhex('78 D8 38 FB 08 68 8F 00 1E 00 8B 68 8F 01 1E 00 0B 68 8F 02 1E 00 68 8F 03 1E 00 4B 68 8F 04 1E 00 4B AB A9 00 48 48 2B 4C 67 7E')
   poke(0x1d00,code);x.cmd('G 1D00',(t.MON,));v=x.s.dump(0x1e00,0x1e04)
   assert v[0]&1 and v[0]&0x30==0x30 and v[1:]==bytes(4),v.hex()
   assert x.hooks()==x.oldhooks;return dict(E=1,M=1,X=1,DBR=v[1],D=int.from_bytes(v[2:4],'little'),PBR=v[4],status=f'{v[0]:02X}')
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,body in old.items():assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(body)
  assert t.sha(old[3][0x7000:])==f['sha256'];r['journal_before']=t.classify_journal(old[3]);check('fresh-owner-four-bank-boot-history-and-golden-F-admission')
  r['context_before']=context_probe();check('hardware-E1-8bit-D-DBR-PBR-zero-admission')
  with (OUT/'extracted-console-events.jsonl').open('x') as events:
   def load(name,prompt):
    boundary();x.rec();face=x.cmd('',(t.REC,));assert not x.s.link.pending
    def emit(kind,*values):
     values2=[dict(hex=v.hex()) if isinstance(v,bytes) else v for v in values];events.write(json.dumps(dict(time=time.time(),event=kind,values=values2))+'\n');events.flush()
     if kind=='error':raise AssertionError(values)
     if kind=='transfer':r['transfers'].append(values[0]);x.save()
    c=core.Session(emit);c.attach(x.s.link.serial);c.receive(face);path,body,digest=payload[name]
    x.s.context=None;c.start(path,body,digest,from_recovery=True);deadline=time.monotonic()+65
    while time.monotonic()<deadline:
     c.tick()
     if not c.busy and c.tail.endswith(prompt):break
     time.sleep(.002)
    else:raise TimeoutError('RAM load did not reach '+repr(prompt)+'; '+repr(bytes(c.tail)))
    assert c.last_transfer==(str(path),body,digest);x.s.context=prompt;c.port=None
   # Exact packaged example: common instruction subset, physical buffer0200.
   load('ASM-RAM.bin',AP);assert b'SAVE' in x.cmd('?')
   for line in (KIT/'examples/HELLO.asm').read_text().splitlines():
    if re.match(r'^\d+ ',line):x.cmd(line)
   assert b'OK 8 bytes' in x.cmd('ASM');assert b'0200 A9 23' in x.cmd('LST');assert b'0200: A9 23' in x.cmd('DUMP') and b'S1' in x.cmd('S19')
   x.cmd('QUIT',(t.MON,));assert x.s.dump(0x200,0x207)==bytes.fromhex('A923206D7E4C677E');assert b'#' in x.cmd('G 0200',(t.MON,));assert x.hooks()==x.oldhooks
   check('exact-extracted-ASM-example-assemble-list-export-readback-run-HOLD')
   load('ASM-RAM.bin',AP)
   for line in ('10 ORG $0200','20 RMB0 $10','30 BBR0 $10,$0200','40 END'):x.cmd(line)
   assert b'OK 5 bytes' in x.cmd('ASM');assert b'0200: 07 10 0F 10 FB' in x.cmd('DUMP')
   # Cross-assembly is deliberately distinct from executing those bytes.
   x.cmd('NEW');lines=['BASE EQU $0200','ORG BASE','start: LDX #$22','PHX','PLX','LDY #$33','PHY','PLY','STZ $1900','BRA .done','NOP','.done: LDA #$42','STA $1900','JMP $7E67','END']
   for n,line in enumerate(lines,1):x.cmd(f'{10*n} {line}')
   assert b'OK 22 bytes' in x.cmd('ASM');face=x.cmd('SYMS');assert b'0200 BASE' in face and b'020E START.DONE' in face
   x.cmd('120 .done: LDA MISSING');face=x.cmd('ASM');assert b'Symbol: MISSING' in face and b'Error line 120:' in face
   x.cmd('120 .done: LDA #$42');assert b'OK 22 bytes' in x.cmd('ASM');x.cmd('QUIT',(t.MON,))
   expected=bytes.fromhex('A222DAFAA0335A7A9C00198001EAA9428D00194C677E');assert x.s.dump(0x200,0x215)==expected
   x.cmd('G 0200',(t.MON,));assert x.s.dump(0x1900,0x1900)==b'\x42' and x.hooks()==x.oldhooks
   check('ASM-cross-target-contract-EQU-local-labels-diagnostics-and-common-stack-BRA-STZ-execution')
   def regs(face=None):
    face=x.cmd('R') if face is None else face;m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face
    return dict(zip(('PC','A','X','Y','P','S'),(int(v,16) for v in m.groups())))
   def err(line):face=x.cmd(line);assert b'?\r\n' in face,(line,face)
   def logical(a,end=None):
    face=x.cmd(f'D {a:04X}'+(f' {end:04X}' if end is not None else ''));return bytes(int(v,16) for _,v in re.findall(rb'([0-9A-F]{4}): ([0-9A-F]{2})',face))
   def leave():x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
   load('DBG-RAM.bin',DP);assert regs()['PC']==0x1002
   x.cmd('M 0200 A9 11 A2 22 20 00 11 8D');x.cmd('M 0208 00 19 EA 4C 67 7E');x.cmd('M 1100 1A 60');x.cmd('R PC 0200')
   face=x.cmd('U 0200 3');assert b'LDA' in face and b'LDX' in face and b'JSR' in face
   assert regs(x.cmd('S'))['PC']==0x202 and regs(x.cmd('S'))['PC']==0x204
   face=x.cmd('N');assert regs(face)['PC']==0x207 and regs(face)['A']==0x12
   x.cmd('B 020A');assert regs(x.cmd('C',(DP,)))['PC']==0x20a and logical(0x1900)==b'\x12'
   x.cmd('R A 66');assert regs()['A']==0x66;x.cmd('BC');assert regs(x.cmd('S'))['PC']==0x20b;x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x20a,0x20a)==b'\xea'
   check('DBG-real-emulation-BRK-frame-registers-S-N-JSR-RTS-breakpoint-and-HOLD')
   load('DBG-RAM.bin',DP)
   ambiguous=sorted(set(range(7,256,16))|set(range(15,256,16)))
   unsupported=[0x02,0x0b,0x22,0x2b,0x42,0x44,0x4b,0x54,0x5c,0x6b,0x82,0x8b,0xab,0xc2,0xe2,0xeb,0xfb]
   for n,op in enumerate(ambiguous+unsupported):
    a=0x3000+4*n;x.cmd(f'M {a:04X} {op:02X} 10 00 EA');x.cmd(f'R PC {a:04X}')
    assert b'.BYTE' in x.cmd(f'U {a:04X} 1'),f'{op:02X} misdecoded';before=regs()
    for cmd in ('S','N'):err(cmd);assert regs()==before
   r['ambiguous_opcodes']=[f'{op:02X}' for op in ambiguous];r['unsupported_opcodes']=[f'{op:02X}' for op in unsupported]
   check('all32-reassigned-bit-opcodes-and17-unsupported-816-opcodes-refused-without-execution')
   x.cmd('M 1200 D0 02 EA EA 80 FE');x.cmd('M 1210 6C 40 02');x.cmd('M 1220 20 80 12');x.cmd('M 1240 40');x.cmd('M 1260 20 00 40');x.cmd('M 1280 60');x.cmd('M 0240 80 12')
   x.cmd('R PC 1200');x.cmd('R P 24');assert regs(x.cmd('S'))['PC']==0x1204
   x.cmd('R PC 1200');x.cmd('R P 26');assert regs(x.cmd('S'))['PC']==0x1202
   x.cmd('R PC 1210');assert regs(x.cmd('S'))['PC']==0x1280
   x.cmd('R SP F0');x.cmd('R PC 1220');assert regs(x.cmd('S'))['PC']==0x1280 and regs()['S']==0xee;assert logical(0x1ef,0x1f0)==bytes.fromhex('2212');assert regs(x.cmd('S'))['PC']==0x1223 and regs()['S']==0xf0
   x.cmd('M 01F1 24 80 12');x.cmd('R PC 1240');assert regs(x.cmd('S'))['PC']==0x1280 and regs()['S']==0xf3
   x.cmd('R SP F0');x.cmd('M 01EF AA BB');x.cmd('R PC 1260');before=regs();err('S');assert regs()==before and logical(0x1ef,0x1f0)==bytes.fromhex('AABB')
   x.cmd('R P 20');err('C');err('S');err('N');x.cmd('R P 24');leave()
   check('relative-indirect-flow-logical-JSR-RTS-RTI-stack-atomic-call-and-IRQ-guards')
   load('DBG-RAM.bin',DP);x.cmd('M 0200 4C 00 20');x.cmd('M 2000 EA EA EA EA EA EA EA EA');x.cmd('M 2008 4C 67 7E');x.cmd('R PC 0200')
   for a in range(0x2000,0x2008):x.cmd(f'B {a:04X}')
   err('B 2008')
   for a in range(0x2000,0x2008):assert regs(x.cmd('C',(DP,)))['PC']==a
   x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x2000,0x2007)==b'\xea'*8
   check('all-eight-real-emulation-breakpoint-hits-and-complete-patch-cleanup')
   load('DBG-RAM.bin',DP);x.cmd('M 0200 A9 23 20 6D 7E 4C 67 7E');x.cmd('R PC 0200');x.cmd('S');face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x205
   x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks;check('public-PUTC-N-step-over-and-HOLD-through-emulation-vector')
   load('DBG-RAM.bin',DP)
   callback=bytes.fromhex('8D30188E31188C321800808D3318086829018D3418A95A8D0270A96B8D0370A97C8D047060')
   for off in range(0,len(callback),8):x.cmd(f'M {0x2100+off:04X} '+callback[off:off+8].hex(' ').upper())
   x.cmd('M 2200 C0 00 21 00');x.cmd('M 1200 00 80 4C 67 7E');x.cmd('R PC 1200');rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'])==(1,16,4)
   x.cmd('M 1200 00 81');x.cmd('R PC 1200');x.cmd('R A 00');x.cmd('R X 22');rr=regs(x.cmd('S'));assert rr['A']==0 and rr['P']&1
   x.cmd('M 1200 00 C0');x.cmd('R PC 1200');rr=regs(x.cmd('S'));assert (rr['A'],rr['X'],rr['Y'],rr['PC'])==(0x5a,0x6b,0x7c,0x1202)
   assert logical(0x1830,0x1834)==bytes((0,0x70,0xc0,9,0));assert b'C0 2100' in x.cmd('F');leave()
   check('built-in-BRK-services-real-callback-register-edits-and-nested-BRK-frame')
   load('DBG-RAM.bin',DP);wanted=logical(0x10)[0]^255;x.cmd(f'M 0010 {wanted:02X}');x.cmd('M 2000 EA');x.cmd('B 2000');x.cmd('BC');x.cmd('B 2000')
   x.s.link.send(b'\x03');x.s.until((DP,));leave();assert x.s.dump(0x10,0x10)==bytes((wanted,)) and x.s.dump(0x2000,0x2000)==b'\xea'
   check('stopped-X-ZP-Ctrl-C-BC-and-original-hook-byte-restoration')
   r['context_after']=context_probe();assert all(r['context_after'][key]==r['context_before'][key] for key in ('E','M','X','DBR','D','PBR'));check('hardware-emulation-and-zero-bank-direct-page-context-retained')
   x.rec();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();x.s.service(reader)
   for b in range(4):
    body=x.s.client.flash(b);assert body==old[b];(OUT/f'B{b}-after.bin').write_bytes(body)
   check('all-four-flash-banks-images-settings-history-and-golden-F-exact')
  r['functional_checks_passed']=True
 r['passed']=bool(len(r['checks'])==13 and r.get('functional_checks_passed') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and r.get('port_released'))
 t.save(OUT/'report.json',r);assert r['passed'];print('PASS2609 816 emulation ASM/DBG RAM qualification; F/images/history and owner/cache/hooks preserved; REC>; COM8 free',flush=True)

if __name__=='__main__':run()
