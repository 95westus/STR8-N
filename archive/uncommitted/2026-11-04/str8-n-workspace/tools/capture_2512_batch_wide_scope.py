"""Read only the exact temporary PROGRAM blocks and preserve owner escrow."""
import json,re,binascii
import install_2512_native_utilities as d
t=d.t
BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1';CASE=BASE/'scope-capture';PRE=BASE/'preflight-resume2'
PB=b'PB> '
def run():
 CASE.mkdir(exist_ok=False)
 scope=json.loads((BASE/'scope/temporary-SRAM-scope.json').read_text());allowed=[int(v,16) for v in scope['allowed_64_byte_writes']]
 fixture=(BASE/'scope/PRIVATE-BATCH-WIDE-SRAM-RAM.bin').read_bytes();assert t.sha(fixture)==scope['restorer_sha256']
 packet=(t.REPO/'monitors/candidates/services-g00000007-batch-r8/STR8N-TOOLS-WB2-SP1-g00000007-RAM.bin').read_bytes()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 report=dict(board='2512',passed=False,flash_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False,target_bytes=scope['temporary_byte_scope'])
 def save():t.save(CASE/'report.json',report)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 s=None;borrowed=False
 save()
 with t.serial_lease('2512-batch-wide-exact-SRAM-target-escrow',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
    assert b'g0000000A / MON B' in s.command('VERSION')
    borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    s.rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),t.WB);s.mount();s.command('B3');s.command('Q',(t.MON,));s.rec();s.load(fixture,t.sha(fixture),PB)
    original=bytearray()
    for index,a in enumerate(allowed):
     fields=bytes([0,a>>8,a&255]);s.link.send(b'R'+fields.hex().upper().encode()+b'\r');out=s.until((PB,))
     m=re.findall(rb'D([0-9A-F]{138})\r?\n',out);assert len(m)==1
     b=bytes.fromhex(m[0].decode());assert b[:3]==fields and binascii.crc_hqx(b[:-2],65535)==int.from_bytes(b[-2:],'big')
     original.extend(b[3:-2])
     if index%32==0:print('Target escrow',index+1,'/',len(allowed),'blocks',flush=True)
    assert len(original)==scope['temporary_byte_scope'];(CASE/'original-target-bytes.bin').write_bytes(original)
    report['target_sha256']=t.sha(original)
    s.link.send(b'Q');s.until((t.MON,));report['passed']=True
   finally:
    try:
     if borrowed:
      if s.context==PB:s.link.send(b'Q');s.until((t.MON,))
      s.rec();s.service(reader);report.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:mark(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored'])
     save()
 print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
