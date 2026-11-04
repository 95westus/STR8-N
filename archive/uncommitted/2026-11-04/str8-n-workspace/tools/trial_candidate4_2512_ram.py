"""Exact candidate4 console/BIN acceptance on2512; RAM only, no persistent writes."""
import binascii,json,re,time
from pathlib import Path
import candidate4_2512_common as c
ds=c.ds;t=c.t;Q=c.Q;OUT=Q/'2512-candidate4-extracted-RAM-20261102-r1';AP=ds.AP;DP=ds.DP;START=b'DBG RAM start 0200-3FFF; Q MON> '
def run():
 mf,core,console=c.prepare();c.await_window(600)
 r=dict(board='2512',CPU='65C02',passed=False,checks=[],ZIP_sha256=c.PIN,kit=str(c.KIT),terminal='0.1.2',transfers=[],flash_writes=0,journal_appends=0,settings_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,physical_resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,software_F_restarts=0,GUI_keys_tested=False,source_SAVE_tested=False)
 with ds.escrow(OUT,r,'2512-candidate4-extracted-RAM-acceptance',window=600,cache_first=0x6b00,cache_end=0x77ff) as x:
  s=x.s;(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
  def check(label):r['checks'].append(label);x.save();print('PASS2512 '+label,flush=True)
  old={b:s.client.flash(b) for b in range(4)}
  for b,body in old.items():assert t.sha(body)==x.original['current_physical_bank_sha256'][f'B{b}'];(OUT/f'B{b}-before.bin').write_bytes(body)
  catalog=json.loads((c.KIT/'NATIVE-COMPONENTS.json').read_text())
  for item in catalog['targets']:
   v=item['variants']['65c02'] if 'variants' in item else item;body=(c.KIT/v['file']).read_bytes();off=int(item['address'],16)-0x8000
   assert old[item['bank']][off:off+len(body)]==body
  assert t.sha(old[3][-4096:])==mf['F_sha256'];check('fresh owner escrow; all20 extracted component extents and CPU02 pairing exact')
  x.wb();x.cmd('TABLE P');meta=b''.join(x.raw(a) for a in range(0,0x800,64));(OUT/'SPI-metadata-before.bin').write_bytes(meta)
  files={name:core.ram_image(c.KIT/path) for name,path in (('ASM','developer/ASM-RAM.bin'),('DBG','developer/DBG-RAM.bin'),('MAINT','rec/MAINT.bin'),('FLASH','rec/FLASH.bin'))}
  events=(OUT/'extracted-console-events.jsonl').open('x')
  def sender():
   def emit(kind,*values):
    events.write(json.dumps(dict(time=time.time(),event=kind,values=[dict(hex=v.hex()) if isinstance(v,bytes) else v for v in values]))+'\n');events.flush()
    if kind=='error':raise AssertionError(values)
    if kind=='transfer':r['transfers'].append(values[0]);x.save()
   tx=core.Session(emit);tx.attach(s.link.serial);return tx
  def load(name,prompt):
   c.boundary();x.rec();face=x.cmd('',(t.REC,));assert not s.link.pending
   tx=sender();tx.receive(face);path,body,digest=files[name];assert digest==mf['files'][path.relative_to(c.KIT).as_posix()]['sha256']
   s.context=None;tx.start(path,body,digest,from_recovery=True);end=time.monotonic()+65
   while time.monotonic()<end:
    tx.tick()
    if not tx.busy and tx.tail.endswith(prompt):break
    time.sleep(.002)
   else:raise TimeoutError('Extracted '+name+' sender did not reach '+repr(prompt)+' '+repr(bytes(tx.tail[-200:])))
   assert tx.last_transfer==(str(path),body,digest) and r['transfers'][-1]['host_complete'];s.context=prompt;tx.port=None
  def leave(prompt):
   assert s.context==prompt;x.cmd('Q',c.MONS+(t.REC,));x.mon();r['software_F_restarts']+=1
  try:
   c.boundary();x.rec();face=x.cmd('L',(core.SEND_BIN,));tx=sender();tx.receive(face);assert tx.prompt=='send-bin' and tx.cancel()
   end=time.monotonic()+12
   while time.monotonic()<end:
    tx.tick()
    if tx.prompt=='rec':break
    time.sleep(.002)
   else:raise TimeoutError('SEND BIN Ctrl-C did not return REC>')
   assert not tx.transfer and not tx.last_transfer;s.context=t.REC;tx.port=None;check('extracted terminal SEND BIN Ctrl-C with zero payload')
   load('ASM',AP);assert b'SAVE' in x.cmd('?')
   lines=[line for line in (c.KIT/'examples/HELLO.asm').read_text().splitlines() if re.match(r'^\d+ ',line)];assert len(lines)==6
   for line in lines:x.cmd(line)
   assert b'OK 8 bytes' in x.cmd('ASM');assert b'0202 20 6D 7E' in x.cmd('LST');assert b'Error' not in x.cmd('SYMS');assert b'0200: A9 23' in x.cmd('DUMP') and b'S1' in x.cmd('S19')
   x.cmd('QUIT',(t.MON,));expected=bytes.fromhex('A923206D7E4C677E');assert s.dump(0x200,0x207)==expected;assert b'#' in x.cmd('G 0200',(t.MON,));assert x.hooks()==x.oldhooks
   check('extracted ASM assemble/list/symbols/dump/S19; exact output/run/HOLD')
   def regs(face=None):
    face=x.cmd('R') if face is None else face;m=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',face);assert m,face
    return dict(zip(('PC','A','X','Y','P','S'),(int(v,16) for v in m.groups())))
   def fixture():x.cmd('M 0200 '+expected.hex(' ').upper());x.cmd('R PC 0200')
   load('DBG',DP);assert regs()['PC']==0x1002;fixture();face=x.cmd('U 0200 3');assert all(v in face for v in (b'LDA',b'JSR',b'JMP'))
   assert regs(x.cmd('S'))['PC']==0x202;face=x.cmd('N');assert b'#' in face and regs(face)['PC']==0x205;x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and s.dump(0x200,0x207)==expected
   check('extracted DBG seed/register/disassembly/step/public step-over/continue/HOLD')
   load('DBG',DP);fixture();x.cmd('B 0205');assert b'0205\r\n' in x.cmd('B');x.cmd('BC');assert b'0205\r\n' not in x.cmd('B');s.link.send(b'\x03');s.until((DP,));assert regs()['PC']==0x200
   x.cmd('B 0205');x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks and s.dump(0x200,0x207)==expected
   check('extracted DBG breakpoints/BC/Ctrl-C/X; hooks and patched bytes restored')
   c.boundary();assert b'ASM B0:A000' in x.cmd('APPS');x.cmd('R ASM',(AP,));assert b'SAVE' in x.cmd('?');x.cmd('QUIT',(t.MON,));x.cmd('R DBG',(START,));x.cmd('Q',(t.MON,));assert x.hooks()==x.oldhooks
   check('installed AP02 front doors remain usable after extracted RAM tools')
   load('MAINT',c.BM);assert b'Copy RAM or flash' in x.cmd('?',(c.BM,));assert b'REC 0200 r1' in x.cmd('VERSION',(c.BM,));assert b'Board: 2512' in x.cmd('NAME',(c.BM,));assert b'DEFAULT=B' in x.cmd('BOOT',(c.BM,));assert b'CLOCK' in x.cmd('TABLE',(c.BM,))
   x.cmd('NAME TEST',(b'Type YES: ',));x.cmd('NO',(c.BM,));x.cmd('N 1000 FF',(c.BM,));x.cmd('P 0 12 34 56',(c.BM,));x.cmd('F 10-1F A5',(c.BM,));assert b'12 34 56' in x.cmd('D 0-1F',(c.BM,))
   buf=bytearray(b'\xff'*4096);buf[:3]=b'\x12\x34\x56';buf[0x10:0x20]=b'\xa5'*16;want=binascii.crc_hqx(buf,65535)
   for command in ('K','M1','K','M3','K'):
    face=x.cmd(command,(c.BM,))
    if command=='K':assert f'CRC16-CCITT-FALSE {want:04X}'.encode() in face
   for command in ('W R 1000','C R 1000-100F R 1100'):
    x.cmd(command,(b'WRITE? TYPE Y> ',));assert b'VERIFIED' in x.cmd('Y',(c.BM,))
   assert b'MATCH' in x.cmd('V R 1000-100F R 1100',(c.BM,))
   for command in ('E 3 F','E 3 C-D'):
    face=x.cmd(command,(c.BM,));assert b'WRITE? TYPE Y' not in face and (b'CANCELED' in face or b'PROTECTED' in face)
   leave(c.BM);check('extracted full REC MAINT query/cancel/maps/4K editor/CRC/RAM copy/compare/protection/Q')
   load('FLASH',c.FT);assert b'FLASH g2' in x.cmd('VERSION',(c.FT,));assert b'I first last' in x.cmd('?',(c.FT,));x.cmd('BANK 0',(c.FT,));x.cmd('READ 8000',(c.FT,));assert b'FF FF FF FF' in x.cmd('VIEW 000',(c.FT,));x.cmd('EDIT 000 FE',(c.FT,));assert b'FE FF FF FF' in x.cmd('VIEW 000',(c.FT,))
   assert b'REFUSED' in x.cmd('I 9001 9FFF',(c.FT,));x.cmd('I 9000 9FFF',(b'type YES> ',));assert b'Canceled' in x.cmd('NO',(c.FT,));leave(c.FT)
   check('extracted REC FLASH version/menu/read/RAM edit/view/refusal/erase cancellation/Q')
   c.boundary();x.wb();aftermeta=b''.join(x.raw(a) for a in range(0,0x800,64));assert aftermeta==meta;(OUT/'SPI-metadata-after.bin').write_bytes(aftermeta);check('SPI PROGRAM/WORK metadata and settings exact; no persistent source writes')
   x.rec();s.service((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())
   for b in range(4):
    data=s.client.flash(b);assert data==old[b];(OUT/f'B{b}-after.bin').write_bytes(data)
   check('all four flash banks exact including F/images/metadata/boot-wear history')
  finally:
   events.close()
   if s.context==b'Type YES: ':x.cmd('NO',(c.BM,))
   if s.context==b'WRITE? TYPE Y> ':x.cmd('NO',(c.BM,))
   if s.context==b'type YES> ':x.cmd('NO',(c.FT,))
   if s.context in (c.BM,c.FT):leave(s.context)
 r['passed']=len(r['checks'])==10 and len(r['transfers'])==5 and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','provider_cache_restored','B3_F_images_settings_history_unchanged','port_released'))
 t.save(OUT/'report.json',r);assert r['passed'];print('PASS candidate4 extracted RAM phase; owner restored; REC>; COM4 free',flush=True)
if __name__=='__main__':run()
