"""RAM-only WB/SP wide-load qualification, using existing owner records read-only."""
import json,re
import install_2512_native_utilities as d
t=d.t
BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1'
CASE=BASE/'RAM-trial'
SERVICE=d.SERVICE

def run():
 CASE.mkdir(exist_ok=False)
 pre=BASE/'preflight-resume2'
 assert json.loads((pre/'report.json').read_text())['passed']
 ram=(pre/'owner-ram.bin').read_bytes();zp=(pre/'owner-zp.bin').read_bytes()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
 packet=(t.REPO/'monitors/candidates/services-g00000007-batch-r6/STR8N-TOOLS-WB2-SP1-g00000007-RAM.bin').read_bytes()
 report=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False)
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def check(label):report['checks'].append(label);save();print('PASS '+label,flush=True)
 def mark(**fields):m=json.loads(t.MARK.read_text());m.update(fields);t.save(t.MARK,m)
 def rec():
  if s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:s.rec()
 def bench():
  rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),t.WB);s.mount()
 def raw(a):
  out=s.command(f'SRAM READ 0 {a:04X}')
  f=re.findall(rb'RAW64 ((?:[0-9A-F]{2} ){64})',out);assert len(f)==1
  return bytes.fromhex(f[0].decode())
 def batch(line,tokens=None):
  assert len(line)<=34
  return s.command('BATCH '+line,tokens)
 save()
 with t.serial_lease('2512-BATCH-wide-RAM-only',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
    assert b'g0000000A / MON B' in s.command('VERSION')
    borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    bench()
    out=batch('V;TIME');assert b'BATCH done' in out and b'RTCC:' in out
    check('shared-UI-backward-compatible-V-TIME')
    out=batch('B0;TABLE P');assert b'NFCOPY' in out and b'BATCH done' in out
    batch('B3;WORK')
    out=batch('B0;;B1');assert b'BATCH refused' in out
    assert b'Data bank B3' in s.command('B')
    check('bank-PROGRAM-table-WORK-empty-list-before-change')
    out=batch('EDU OFF;TABLE P;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    assert b'Data bank B3' in s.command('B');s.command('EDU ON')
    out=batch('V;G 3000;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    out=batch('V;BATCH V;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    check('stop-on-provider-error-raw-jump-and-nesting')
    out=batch('S P AUTO 3000 3007 BQT;V',(b'type YES> ',t.WB));assert s.context==b'type YES> '
    out=s.command('NO',(t.WB,));assert b'BATCH stopped' in out and b'/ MON B' not in out
    check('STORE-requires-live-confirmation-NO-stops-queue')
    out=batch('R P NFCOPY L;V');assert b'payload CRC verified' in out and b'BATCH done' in out
    out=batch('R P NFCOPY;V');assert b'BATCH stopped' in out and b'/ MON B' not in out
    check('small-load-only-and-unregistered-run-refusal')
    out=batch('R P CLK;V');assert b'BATCH stopped' in out and b'/ MON B' not in out
    out=batch('R P CLK L;V');assert b'BATCH stopped' in out and b'/ MON B' not in out
    check('legacy-BT1-not-BASE1-registered-and-wide-L-not-last-refused')
    samples={a:raw(a+0x4000) for a in (0x2000,0x4800,0x4F80)}
    s.link.send(b'R P CLK L\r');out=s.until((t.MON,),seconds=180)
    assert b'PROGRAM loaded; CRC OK' in out
    for a,b in samples.items():assert s.dump(a,a+63)==b
    check('independent-wide-load-crosses-WB-and-preserves-loaded-bytes')
    bench();out=batch('R P CLK L',(t.MON,));assert b'BATCH done' in out and b'PROGRAM loaded; CRC OK' in out
    assert s.dump(0x4800,0x483F)==samples[0x4800]
    check('final-wide-load-only-kept-intact-after-BATCH')
   finally:
    try:
     if borrowed:
      rec();s.service(reader);report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor()
      s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:mark(batch_wide_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored'])
     save()
 report['passed']=len(report['checks'])==8 and report['owner_RAM_restored'];save();print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
