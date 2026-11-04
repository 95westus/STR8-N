"""RAM test the WB-exit origin and VERSION/TIME gateway-scratch fixes."""
import json
import trial_2512_batch_native_ram_r2 as h
import install_2512_native_utilities as d
t=d.t;BASE=h.BASE;CASE=BASE/'context-fix-RAM';PRE=BASE/'preflight-resume2';h.NATIVE=t.REPO/'monitors/candidates/native-g00000001-r16';h.BUILD=t.ROOT/'BUILD/native-apps-g1-r16'
def run():
 CASE.mkdir(exist_ok=False)
 report=dict(board='2512',passed=False,checks=[],flash_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False)
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 packet=(t.REPO/'monitors/candidates/services-g00000008-batch/STR8N-TOOLS-WB2-SP1-g00000008-RAM.bin').read_bytes()
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def check(n):report['checks'].append(n);save();print('PASS '+n,flush=True)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context==t.WB:s.command('B3');s.command('Q',(t.MON,));s.rec()
  elif s.context!=t.REC:s.rec()
 save()
 with t.serial_lease('2512-BATCH-context-fix-RAM',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12);assert b'g0000000B / MON B' in s.command('VERSION')
    borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),t.WB)
    assert b'BATCH done' in s.command('BATCH V;TIME')
    s.command('Q',(t.MON,));assert s.dump(0x6565,0x6565)==b'\0'
    s.modify(0x3100,b'BATCH V;TIME\0')
    bridge=bytes.fromhex('78 D8 A2 FF 9A A9 02 8D 50 65 A9 03 A2 00 A0 31 20 08 48 4C 67 7E');s.modify(0x3000,bridge)
    out=s.command('G 3000',(t.MON,t.WB));assert s.context==t.MON and b'BATCH done' in out
    check('WB-Q-clears-origin-and-next-MON-BATCH-returns-MON')
    rec();t.transport.recovery_usb(s.link);body=h.packet(0,'VERSION;TIME;Q')
    t.recovery.PROMPT=t.MON;s.client=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(s.link),timeout=90)
    original=s.client.until;captured=[]
    def capture(token):
     out=original(token);captured.append(out);return out
    s.client.until=capture;s.context=None;s.client.load(body,t.sha(body),REC_observed=True);s.context=t.MON
    out=captured[-1];(CASE/'CLOCK-VERSION-TIME.txt').write_bytes(out)
    assert b'g0000000B / MON B' in out and b'CLOCK> TIME' in out and b'UTC:' in out and b'RTCC error' not in out
    check('native-VERSION-does-not-overwrite-CLOCK-gateway-TIME-still-works')
   finally:
    try:
     if borrowed:
      rec();s.service(reader);report.update(s.client.restore_owner((PRE/'owner-ram.bin').read_bytes(),(PRE/'owner-zp.bin').read_bytes()));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:mark(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored'])
     save()
 report['passed']=len(report['checks'])==2 and report['owner_RAM_restored'];save();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
