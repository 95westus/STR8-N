"""Reviewed 2512 PROGRAM/AP/02 BATCH positives and exact restoration."""
import json,re,time,binascii
import install_2512_native_utilities as d
import nf_opaque as opaque
t=d.t;BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1';CASE=BASE/'cancel-resume';SCOPE=BASE/'scope-r2';PRE=BASE/'preflight-resume2';PB=b'PB> ';SERVICE=d.SERVICE
class Session(d.Session):
 def monitor(self):
  if self.context==PB:self.link.send(b'Q');self.until((t.MON,))
  if self.context==t.WB:self.command('B3');self.command('Q',(t.MON,))
  super().monitor()

def run():
 assert json.loads((BASE/'context-repair/report.json').read_text())['passed']
 CASE.mkdir(exist_ok=False)
 scope=json.loads((SCOPE/'temporary-SRAM-scope.json').read_text());allowed=[int(a,16) for a in scope['allowed_64_byte_writes']]
 original=(BASE/'scope-capture/original-target-bytes.bin').read_bytes();assert len(original)==14272
 backup={a:original[i*64:(i+1)*64] for i,a in enumerate(allowed)}
 fixture=(SCOPE/'PRIVATE-BATCH-WIDE-SRAM-RAM.bin').read_bytes();assert t.sha(fixture)==scope['restorer_sha256']
 payload=(SCOPE/'BQLARGE-3000-66FF.bin').read_bytes();header=(SCOPE/'BQLARGE-slot4.bin').read_bytes()
 small=(SCOPE/'BQS-3000-32.bin').read_bytes();bad_app=(SCOPE/'BQAPP-pending-CRC-B0-9000.bin').read_bytes();good_app=(SCOPE/'BQAPP-good-B0-9000.bin').read_bytes()
 packet=(t.REPO/'monitors/candidates/services-g00000008-batch/STR8N-TOOLS-WB2-SP1-g00000008-RAM.bin').read_bytes()
 writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes();reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 ram=(PRE/'owner-ram.bin').read_bytes();zp=(PRE/'owner-zp.bin').read_bytes()
 report=dict(board='2512',passed=False,checks=[],B0_9_erases=0,temporary_SRAM_bytes=14272,SRAM_restore_pending=False,APP_restore_pending=False,owner_RAM_restored=False,F_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,power_cuts=0)
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def check(label):report['checks'].append(label);save();print('PASS '+label,flush=True)
 def rec():
  if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
  elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:s.rec()
 def bench():
  # Explicit packet avoids relying on mutable caches while repairing a fixture.
  rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),t.WB);s.mount();s.command('B3');s.command('Q',(t.MON,));s.rec();s.load(fixture,t.sha(fixture),PB)
 def readblock(a):
  assert s.context==PB
  fields=bytes([0,a>>8,a&255]);s.link.send(b'R'+fields.hex().upper().encode()+b'\r');out=s.until((PB,))
  m=re.findall(rb'D([0-9A-F]{138})\r?\n',out);assert len(m)==1
  frame=bytes.fromhex(m[0].decode());assert frame[:3]==fields and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
  return frame[3:-2]
 def block(a,b):
  assert s.context==PB and a in allowed and len(b)==64
  fields=bytes([0,a>>8,a&255]);crc=binascii.crc_hqx(fields+b,65535)
  out=s.command('W'+fields.hex().upper()+b.hex().upper()+f'{crc:04X}')
  assert f'O{crc:04X}\r\n'.encode() in out
  assert readblock(a)==b
 def leave_bench():
  assert s.context==PB;s.link.send(b'Q');s.until((t.MON,));s.command('EDU ON',(t.MON,))
 def batch(text,token=t.MON,seconds=180):
  assert len(text)<=34
  s.link.send(('BATCH '+text+'\r').encode());out=s.until((token,),seconds=seconds)
  (CASE/(str(len(report['checks']))+'-batch.txt')).write_bytes(out);return out
 def restore_sram():
  bench()
  for i,a in enumerate(allowed):
   block(a,backup[a])
   if i%32==0:print('Restore SRAM',i+1,'/',len(allowed),'blocks',flush=True)
  actual=b''.join(readblock(a) for a in allowed);assert actual==original
  report['SRAM_restore_pending']=False;mark(BATCH_PROGRAM_restore_pending=False)
  leave_bench();check('all-14272-temporary-SRAM-bytes-restored')
 def restore_app():
  rec();s.load(writer,t.sha(writer),opaque.PROMPT);wire=opaque.Wire(s.link.serial,timeout=90,trace=log)
  actual=wire.read_sector(0,0x90);assert actual in (good_app,bad_app)
  report['B0_9_erases']+=1;save();s.context=None
  assert not wire.replace_sector(0,0x90,actual,b'\xff'*4096)
  s.context=opaque.PROMPT;assert wire.read_sector(0,0x90)==b'\xff'*4096
  report['APP_restore_pending']=False;mark(BATCH_APP_restore_pending=False);rec();s.monitor();check('B0-9-original-FF-restored')
 save()
 with t.serial_lease('2512-reviewed-BATCH-wide-and-AP02-positive',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12);assert b'g0000000B / MON B' in s.command('VERSION')
    borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    bench()
    # Freshly re-admit exact targets before their first write, not all SRAM.
    assert b''.join(readblock(a) for a in allowed)==original
    report['SRAM_restore_pending']=True;mark(BATCH_PROGRAM_restore_pending=True);save()
    for offset in range(0,len(payload),64):
     block(0xA000+offset,payload[offset:offset+64])
     if offset%2048==0:print('PROGRAM fixture',offset+64,'/',len(payload),'bytes',flush=True)
    pending=bytearray(header);pending[63]=0;block(0x140,bytes(pending));block(0x140,header)
    leave_bench();check('14K-registered-PR05-PROGRAM-installed-commit-last')
    # Observe the admitted wide-copy phase, then cancel while RAM is borrowed.
    s.modify(0x3000,b'\xa5'*64);s.command('!M 6600 A5')
    s.link.send(b'R P BQLARGE L\r');out=s.until((b'>',),seconds=180)
    time.sleep(.5);s.link.send(b'\x03');out+=s.until((t.MON,),seconds=180)
    (CASE/'wide-copy-cancel.txt').write_bytes(out)
    (CASE/'cancel-state.bin').write_bytes(s.dump(0x69B8,0x69CC))
    (CASE/'cancel-first.bin').write_bytes(s.dump(0x3000,0x303F))
    (CASE/'cancel-last.bin').write_bytes(s.dump(0x6600,0x660F))
    assert b'Partial; not run' in out
    assert s.dump(0x3000,0x3009)==payload[:10] and s.dump(0x6600,0x6600)==b'\xa5'
    check('partial-wide-copy-cancel-returns-from-resident-tail-without-run')
    restore_sram()
   finally:
    try:
     if borrowed:
      if report['SRAM_restore_pending'] and s.context is not None:restore_sram()
      if report['APP_restore_pending'] and s.context is not None:restore_app()
      if s.context!=SERVICE:rec();s.service(reader)
      report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:
      restored=report['owner_RAM_restored'] and not report['SRAM_restore_pending'] and not report['APP_restore_pending'];mark(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=True,application_ram_restored=report['owner_RAM_restored'])
     save()
 report['passed']='partial-wide-copy-cancel-returns-from-resident-tail-without-run' in report['checks'] and report['owner_RAM_restored'] and not report['SRAM_restore_pending'] and not report['APP_restore_pending'];save();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
