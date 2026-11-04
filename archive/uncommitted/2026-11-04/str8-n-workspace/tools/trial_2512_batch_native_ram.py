"""RAM native command-prompt BATCH tests; no ROM/SRAM/RTC writes.
Only this harness relocates the shared reader and clears the marker at return;
full MON/WB queue-join qualification remains an installed-image test.
"""
import json,re
from pathlib import Path
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1';CASE=BASE/'native-RAM';PRE=BASE/'preflight-resume2';FT=d.FT
NATIVE=t.REPO/'monitors/candidates/native-g00000001-r14';BUILD=t.ROOT/'BUILD/native-apps-g1-r14'
def sy(name):return {n:int(v,16) for v,n in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',(BUILD/(name+'.map')).read_text(),re.M)}
def linked(name,end):
 from build_mona import cells
 symbols=sy(name);m=cells(BUILD/(name+'.s19'));start=min(m);return bytes(m[a] for a in range(start,symbols[end]))
def packet(kind,queue,bank=3):
 image=bytearray(b'\xff'*0x5E00)
 app=(NATIVE/('CLOCK-g00000001-RAM.bin' if kind==0 else 'FLASH-MAINT-g00000001-RAM.bin')).read_bytes()
 assert app.count(bytes.fromhex('20 08 89'))==1
 app=app.replace(bytes.fromhex('20 08 89'),bytes.fromhex('20 08 5A'))
 image[0x1e00:0x1e00+len(app)]=app
 reader=bytearray(linked('batch-reader','BR_END_CODE'));assert reader[8]==0x4c and reader[10]==0x89
 reader[10]=0x5a;reader=reader.replace(bytes.fromhex('A0 89'),bytes.fromhex('A0 5A'))
 image[0x5800:0x5800+len(reader)]=reader
 ret=linked('native-return','NR_END');assert ret.count(bytes.fromhex('9C 00 48'))==1
 ret=ret.replace(bytes.fromhex('9C 00 48'),bytes.fromhex('9C F9 7D'))
 image[0x5c00:0x5c00+len(ret)]=ret
 loader=(NATIVE/'RTC-BASE1-B3-8000.bin').read_bytes()[0xc00:]
 image[0x600:0x600+len(loader)]=loader
 q=bytearray(48);encoded=queue.encode();assert len(encoded)<=34
 q[:len(encoded)]=encoded;q[35]=len(encoded);q[38]=kind+2;q[39]=3
 image[0x100:0x130]=q
 # Escrow MON/ZP, then seed only the private queue and copy the admitted loader.
 prefix=bytes.fromhex('78 D8 A2 00 BD 00 6A 9D 00 5D BD 00 00 9D 00 5C BD 00 08 9D 00 70 BD 00 09 9D 00 71 BD 00 0A 9D 00 72 BD 00 0B 9D 00 73 E8 D0 D9 A2 2F BD 00 03 9D D0 6A 9D D0 5D CA 10 F4 A9 B7 8D F9 7D')
 prefix+=bytes([0xa9,kind,0x8d,2,0x5b,0x8d])+sy('native-loader')['NL_KIND'].to_bytes(2,'little')
 if kind:
  prefix+=bytes([0xa9,bank,0x8d,0,0x5d,0x4c,0,0x20])
 else:
  prefix+=bytes([0xa2,0,0x4c])+sy('native-loader')['NL_GATE_COPY'].to_bytes(2,'little')
 image[:len(prefix)]=prefix;assert len(prefix)<256
 return bytes(image)

def run():
 CASE.mkdir(exist_ok=False);report=dict(board='2512',passed=False,checks=[],F_writes=0,flash_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False,harness='Reader relocated8900->5A00; return clears marker instead of joining old MON gA')
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def check(label):report['checks'].append(label);save();print('PASS '+label,flush=True)
 def mon():
  assert s.context in tuple(f'B{b}> '.encode() for b in range(4))
  s.command('B3',(t.MON,))
 def launch(kind,queue,bank=3):
  if s.context!=t.REC:s.rec()
  t.transport.recovery_usb(s.link);body=packet(kind,queue,bank);(CASE/(str(len(report['checks']))+'-packet.bin')).write_bytes(body)
  s.load(body,t.sha(body),b'__never__')
 save()
 with t.serial_lease('2512-native-BATCH-prompt-RAM-only',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12);borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    # load() waits for its requested final prompt; the queued native Q returns
    # directly to old MON after exercising all native command prompts.
    def run_packet(kind,queue,bank=3,target=None):
     if s.context!=t.REC:s.rec()
     t.transport.recovery_usb(s.link);body=packet(kind,queue,bank)
     t.recovery.PROMPT=target or (t.MON if bank==3 else f'B{bank}> '.encode())
     s.client=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(s.link),timeout=90)
     captured=[];original_until=s.client.until
     def capture(token):
      out=original_until(token);captured.append(out);return out
     s.client.until=capture
     s.context=None;s.client.load(body,t.sha(body),REC_observed=True)
     s.context=t.recovery.PROMPT
     out=captured[-1];(CASE/(str(len(report['checks']))+'-commands.txt')).write_bytes(out)
     return out
    out=run_packet(0,'STATUS;VERSION;Q');assert b'raw' in out.lower() and b'g0000000A / MON B' in out;check('CLOCK-queued-STATUS-VERSION-Q')
    out=run_packet(1,'READ 9000;EDIT 000 12;VIEW 000;Q',bank=0);assert b'0000  12 FF' in out;mon();check('FLASH-queue-survives-4K-READ-and-EDIT-buffer')
    out=run_packet(1,'READ F000;Q',target=b'BATCH stopped\r\nFLASH/MAINT> ');s.context=FT;assert b'REFUSED' in out;s.command('Q',(t.MON,));check('FLASH-protected-error-stops-before-queued-Q')
    run_packet(1,'ERASE 9000;Q',bank=0,target=b'type YES> ')
    s.command('NO',(b'BATCH stopped\r\nFLASH/MAINT> ',));s.context=FT;s.command('Q',(b'B0> ',));mon();check('FLASH-confirmation-is-live-NO-stops-queue')
   finally:
    try:
     if borrowed:
      if s.context in (FT,t.CLOCK):s.command('Q',tuple(f'B{b}> '.encode() for b in range(4)));mon()
      if s.context!=t.REC:s.rec()
      s.service(reader);report.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:mark(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored'])
     save()
 report['passed']=len(report['checks'])==4 and report['owner_RAM_restored'];save();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
