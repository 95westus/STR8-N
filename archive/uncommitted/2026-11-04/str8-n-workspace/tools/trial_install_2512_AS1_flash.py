"""Execute the reviewed2512 SF/1 trial + paired-app upgrade exactly once."""
import json,time
from pathlib import Path
from devtools_2512_session import escrow,t,Q,AP,DP,CONF,ins
from serial_test_coordination import drift_pending
import nf_opaque as opaque
import trial_2512_AS1_flash_readonly as ram_candidate
from journal_rotation_plan import reserve
SCOPE=Q/'2512-AS1-FLASH-scope-20261102-r1';BUILD=t.ROOT/'BUILD/asm-flash-source-g2-r4';OUT=Q/'2512-AS1-FLASH-installed-20261102-r1';ALLOC=b'; type YES> ';DBGSTART=b'DBG RAM start 0200-3FFF; Q MON> '

def run():
 p=json.loads((SCOPE/'plan.json').read_text());a=json.loads((SCOPE/'authorization.json').read_text())
 assert a['authorized'] and p['status']=='REVIEWED_WITHIN_STANDING_FLASH_AUTHORIZATION' and p['total_erases']==5 and p['F_writes']==p['MON_writes']==p['E_writes']==p['C_D_erases']==0
 assert t.sha((SCOPE/'plan.json').read_bytes())==a['plan_sha256'] and t.sha((SCOPE/'review-document.md').read_bytes())==a['review_sha256'] and t.sha((BUILD/'manifest.json').read_bytes())==p['build_manifest_sha256']
 print('2512 reviewed SF/1 trial/install waiting for RTC window',flush=True)
 while True:
  try:ins.window(420);break
  except AssertionError:time.sleep(1)
 r=dict(board='2512',passed=False,checks=[],completed=[],erase_requests=0,wear_appends=0,source_fixture_may_exist=False,cleanup_erase_used=False,F_writes=0,MON_writes=0,E_writes=0,C_D_erases=0,SPI_writes=0,RTC_writes=0,resets=0,power_cuts=0,automatic_retries=0,source_byte_programs_maximum=100)
 with escrow(OUT,r,'2512-reviewed-SF1-five-erase-trial-install',window=420,cache_first=0x6b00,cache_end=0x77ff) as x:
  (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());(OUT/'authorization.json').write_bytes((SCOPE/'authorization.json').read_bytes())
  old={b:x.s.client.flash(b) for b in range(4)}
  for b,v in old.items():assert t.sha(v)==p['before_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(v)
  assert old[0][0x1000:0x2000]==b'\xff'*4096;assert old[3][-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
  state=old[3];reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();fixture=(SCOPE/'expected-SF1-sector.bin').read_bytes();fault=(SCOPE/'expected-final-fault-sector.bin').read_bytes()
  wirelog=(OUT/'opaque-wire.jsonl').open('x')
  def check(n):r['checks'].append(n);x.save();print('PASS2512 '+n,flush=True)
  def banks():
   x.rec();x.s.service(reader);return {b:x.s.client.flash(b) for b in range(4)}
  def enter_ram():x.rec();body=ram_candidate.packet();x.s.load(body,t.sha(body),AP)
  def lines():
   for n,line in enumerate(p['source_lines'],1):x.cmd(f'{n*10} {line}')
  def check_source():
   listing=x.cmd('LIST');assert all(f'{n*10} {line}'.encode() in listing for n,line in enumerate(p['source_lines'],1));assert b'OK 8 bytes' in x.cmd('ASM');return listing
  def mount_writer():
   x.rec();x.s.load(writer,t.sha(writer),opaque.PROMPT);return opaque.Wire(x.s.link.serial,timeout=90,trace=wirelog,progress=lambda v:print(v,flush=True))
  def replace(target,before,body):
   nonlocal state
   assert r['erase_requests']<5 and target['bank']==0 and target['page'] in (0x90,0xa0,0xb0,0xc0,0xd0)
   wire=mount_writer();assert wire.read_sector(0,target['page'])==before
   state,op=reserve(state,(target['page']-0x80)//16);assert not op['journal_sector_erases'];x.expected_b3_sha256=t.sha(state)
   r['erase_requests']+=1;x.save();x.s.context=None;assert not wire.replace_sector(0,target['page'],before,body);x.s.context=opaque.PROMPT;assert wire.read_sector(0,target['page'])==body
   r['wear_appends']+=1;r['completed'].append(target['address']);x.save()
  def cleanup_fixture():
   if not r['source_fixture_may_exist'] or r['cleanup_erase_used']:return
   wire=mount_writer();actual=wire.read_sector(0,0x90)
   # Every changed bit must belong to the approved source/fault fixture.
   assert all((v&limit)==limit for v,limit in zip(actual,fault)),'Unexpected B0:9 bits; do not erase blindly'
   r['cleanup_erase_used']=True;x.save();replace(p['targets'][4],actual,b'\xff'*4096);r['source_fixture_may_exist']=False;check('B0-9000-exact-FF-fixture-restoration')
  def bit_fault(address,value):
   assert (address,value) in ((0x9028,8),(0x9002,0));x.mon();x.cmd('B0',(b'B0> ',));face=x.cmd(f'!M {address:04X} {value:02X}',(b'B0> ',));assert b'REFUSED' not in face and b'fail' not in face.lower();x.cmd('B3',(t.MON,))
  try:
   check('fresh-four-bank-preimages-owner-and-golden-F-admitted')
   if drift_pending():raise InterruptedError('RTC requested before first source write')
   enter_ram();lines();face=x.cmd('SAVE FLASH '+p['source_name'],(ALLOC,));assert b'Append source B0:9000 sectors 01' in face
   r['source_fixture_may_exist']=True;x.mark(AS1_flash_fixture_pending=True);x.save();assert b'Source saved' in x.cmd('YES',(AP,))
   v=banks();expected=bytearray(old[0]);expected[0x1000:0x2000]=fixture;assert v[0]==expected and all(v[b]==old[b] for b in (1,2,3));(OUT/'SF1-sector-verified.bin').write_bytes(v[0][0x1000:0x2000]);check('RAM-SAVE-FLASH-exact-SF1-AS1-record-commit-and-zero-erase')
   enter_ram();assert b'Source loaded' in x.cmd('LOAD FLASH '+p['source_name']);check_source();assert b'Source storage: 50' in x.cmd('SAVE FLASH '+p['source_name']);assert b'Source storage: 51' in x.cmd('SAVE FLASH NOFREE');check('fresh-session-FLASH-LOAD-LIST-ASM-duplicate-and-full-refusal')
   x.cmd('30 STA $1901');before=x.cmd('LIST');x.cmd('LOAD FLASH '+p['source_name'],(CONF,));assert b'Load cancelled' in x.cmd('NO',(AP,));assert x.cmd('LIST')==before
   x.cmd('LOAD FLASH '+p['source_name'],(CONF,));assert b'Source loaded' in x.cmd('YES',(AP,));check_source();check('dirty-source-NO-preserved-and-YES-restored')
   for target in p['targets'][:4]:
    at=(target['page']-0x80)*256;body=(SCOPE/target['file']).read_bytes();assert t.sha(body)==target['sha256'];replace(target,old[0][at:at+4096],body);check('installed-'+target['address'])
   x.mon();face=x.cmd('APPS');assert b'ASM B0:A000' in face and b'DBG B0:C000' in face
   x.cmd('R ASM',(AP,));assert b'Source loaded' in x.cmd('LOAD FLASH '+p['source_name']);check_source();x.cmd('QUIT',(t.MON,));assert x.s.dump(0x200,0x207)==bytes.fromhex('A9428D00194C677E');x.cmd('G 0200',(t.MON,));assert x.s.dump(0x1900,0x1900)==b'\x42';check('installed-R-ASM-ROM-provider-FLASH-LOAD-assemble-run-and-HOLD')
   bit_fault(0x9028,8);x.cmd('R ASM',(AP,));lines();x.cmd('30 STA $1901');before=x.cmd('LIST');x.cmd('LOAD FLASH '+p['source_name'],(CONF,));assert b'Invalid source image.' in x.cmd('YES',(AP,));assert x.cmd('LIST')==before;x.cmd('QUIT',(t.MON,));check('real-AS1-payload-CRC-fault-refused-before-source-copy')
   bit_fault(0x9002,0);x.cmd('R ASM',(AP,));lines();before=x.cmd('LIST');x.cmd('LOAD FLASH '+p['source_name'],(CONF,));assert b'Source storage: 52' in x.cmd('YES',(AP,));assert x.cmd('LIST')==before;x.cmd('QUIT',(t.MON,));check('real-SF1-header-fault-refused-before-source-copy')
   cleanup_fixture();x.mon();x.cmd('R ASM',(AP,));assert b'Source storage: 42' in x.cmd('LOAD FLASH '+p['source_name']);x.cmd('QUIT',(t.MON,));check('installed-FLASH-source-missing-after-cleanup')
   x.cmd('R DBG',(DBGSTART,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
   code=bytes.fromhex('A9118D00194C677E')
   for off in range(0,len(code),8):x.cmd(f'M {0x1800+off:04X} '+code[off:off+8].hex(' ').upper())
   x.cmd('R DBG',(DBGSTART,));assert b'PC=1800' in x.cmd('1800',(DP,));assert b'PC=1802' in x.cmd('S');x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and x.s.dump(0x1900,0x1900)==b'\x11';check('paired-DBG-remains-CRC-admitted-step-HOLD-and-hook-cleanup')
   v=banks()
   for b,body in v.items():(OUT/f'B{b}-after.bin').write_bytes(body);assert t.sha(body)==p['after_bank_sha256'][f'B{b}']
   assert t.sha(state)==p['after_bank_sha256']['B3'];r['NVM_verified']=True;r['functional_checks_passed']=True;check('all-final-images-five-appends-and-all25-old-journal-rows-exact')
  finally:
   try:
    if x.s.context==ALLOC:x.cmd('NO',(AP,))
    if x.s.context==DBGSTART:x.cmd('Q',(t.MON,))
    if r['source_fixture_may_exist']:cleanup_fixture()
    if r.get('NVM_verified'):
     marker=json.loads(x.mp.read_text());counts=marker['current_tracked_erase_counts'].copy()
     for i,v in enumerate(p['after_journal']['counts']):counts[f'B{i//8}:{8+i%8:X}']=v
     for n,i in zip('ABCDEF',range(26,32)):counts[n]=p['after_journal']['counts'][i]
     x.mark(current_physical_bank_sha256=p['after_bank_sha256'],current_journal_sequence=1187,current_journal_valid_records=30,current_valid_journal_records=30,current_wear_counts=p['after_journal']['counts'],current_tracked_erase_counts=counts,ASM_FLASH_source_qualified=True,ASM_source_flash_fixture_pending=False,AS1_flash_fixture_pending=False,last_ASM_FLASH_source_trial=str(OUT/'report.json'))
    elif r['erase_requests']:
     # Do not resume RTC against unreviewed/stale image hashes after a partial run.
     x.original['block_snapshot']=True;x.mark(AS1_flash_install_inspection_pending=True)
   finally:wirelog.close()
 r['passed']=bool(r.get('NVM_verified') and r.get('functional_checks_passed') and r.get('planned_B3_verified') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and r.get('provider_cache_restored') and not r['source_fixture_may_exist'] and r['erase_requests']==r['wear_appends']==5);t.save(OUT/'report.json',r);assert r['passed']
 print('PASS2512 FLASH-source persistence installed; fixture erased/restored; all25 old journal rows retained; F/MON/E golden; owner/cache restored; COM4 free',flush=True)
if __name__=='__main__':run()
