"""2512 familiar named-tool/catalogue increment; fresh owner escrow, no NVM writes."""
import json
import install_2512_native_utilities as d
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'RAM-trial-r3';SVC=t.REPO/'monitors/candidates/services-g00000009-workflow-r3';SERVICE=d.SERVICE

def run():
 CASE.mkdir(parents=True,exist_ok=False);r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,owner_RAM_restored=False)
 s=None;borrowed=False;ram=zp=None
 def save():t.save(CASE/'report.json',r)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def check(n):r['checks'].append(n);save();print('PASS '+n,flush=True)
 def rec():
  if s.context==t.WB:s.command('B3');s.command('Q',(t.MON,))
  if s.context==t.CLOCK:s.command('Q',(t.MON,))
  if s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:s.rec()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();packet=(SVC/'STR8N-TOOLS-WB2-SP1-g00000009-RAM.bin').read_bytes()
 save()
 with t.serial_lease('2512-classic-workflow-RAM-only',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12);assert b'g0000000B / MON B' in s.command('VERSION')
    assert json.loads((BASE/'RAM-recovery/report.json').read_text())['passed']
    ram=(BASE/'RAM-trial/owner-ram.bin').read_bytes();zp=(BASE/'RAM-trial/owner-zp.bin').read_bytes();assert s.dump(0x200,0x23F)==ram[:64] and s.dump(0x66C0,0x66FF)==ram[-64:] and s.dump(0,0xDF)==zp
    (CASE/'owner-ram.bin').write_bytes(ram);(CASE/'owner-zp.bin').write_bytes(zp);check('verified-restored-owner-escrow-reused')
    borrowed=True;mark(classic_workflow_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    rec();t.transport.recovery_usb(s.link);s.load(packet,t.sha(packet),t.WB);s.mount()
    assert b'EDU ON' in s.command('R   EDU')
    assert b'PROGRAM' in s.command('RESTORE SRAM')
    assert b'PROGRAM' in s.command('R WORK');check('R-and-RESTORE-EDU-SRAM-WORK-entry-points')
    assert b'REFUSED' in s.command('R EDU BAD')
    out=s.command('BATCH R EDU BAD;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    out=s.command('BATCH R EDU OFF;R WORK;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    s.command('R EDU ON');check('reserved-name-errors-and-unavailable-storage-stop-BATCH')
    assert b'NFCOPY' in s.command('TABLE P');out=s.command('RESTORE P NFCOPY L');assert b'payload CRC verified' in out
    check('existing-PROGRAM-TABLE-RESTORE-remain-usable')
    out=s.command('R    CLOCK',(t.CLOCK,));assert b'CLOCK' in out;s.command('VERSION');s.command('Q',(t.MON,));check('familiar-R-CLOCK-spaces-native-VERSION-and-Q')
    rec();body=bytearray(b'\xff'*0x2e00);bridge=bytes.fromhex('78 D8 A2 FF 9A A9 02 8D FF 69 A9 03 A2 00 A0 03 20 08 20 4C 67 7E');body[:len(bridge)]=bridge;body[0x100:0x105]=b'APPS\0';body[0x1e00:]= (SVC/'STR8N-SERVICES-g00000009-RAM.bin').read_bytes()
    t.recovery.PROMPT=t.MON;s.client=t.recovery.RecoveryClient(t.live.LoggedRecoveryStream(s.link),timeout=90);original=s.client.until;captured=[]
    def capture(token):
     out=original(token);captured.append(out);return out
    s.client.until=capture;s.context=None;s.client.load(bytes(body),t.sha(bytes(body)),REC_observed=True);s.context=t.MON;out=captured[-1];(CASE/'APPS.txt').write_bytes(out)
    assert all(x in out for x in (b'CLOCK B2:B000  R CLOCK',b'FLASH B2:E000  R FLASH',b'MAINT B2:E000  R MAINT',b'EDU SRAM WORK; R tool',b'PROGRAMS: T; R name; APP name'))
    check('classic-APPS-catalogue-with-locations-and-entry-commands')
    rec();s.service(reader);b3=s.client.flash(3);assert b3==(t.ROOT/'output/qualification/2512-batch-wide-20261030-r1/physical-default/B3-final.bin').read_bytes();(CASE/'B3-current.bin').write_bytes(b3);check('F-journal-boot-policy-and-B3-images-unchanged')
   finally:
    try:
     if borrowed:
      if s.context!=SERVICE:rec();s.service(reader)
      r.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor();s.command('!M 6A20 01');r['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();r['COM4_released']=True
     if borrowed:mark(classic_workflow_worker_active=False,application_RAM_restore_pending=not r['owner_RAM_restored'],block_snapshot=not r['owner_RAM_restored'],application_ram_restored=r['owner_RAM_restored'])
     save()
 r['passed']=len(r['checks'])==7 and r['owner_RAM_restored'];save();print('PASS RAM-only familiar workflow / owner RAM restored',flush=True)
if __name__=='__main__':run()
