"""Install reviewed MON/WB/native BATCH increment; F is excluded."""
import json,time
import install_2512_native_utilities as d
import nf_opaque as opaque
t=d.t;BASE=t.ROOT/'output/qualification/2512-batch-wide-20261030-r1';CASE=BASE/'installation';SCOPE=BASE/'scope-r2';PRE=BASE/'preflight-resume2';FT=d.FT;SERVICE=d.SERVICE
PLAN=json.loads((SCOPE/'installation-plan.json').read_text())

def run():
 assert json.loads((BASE/'RAM-trial-r2/report.json').read_text())['passed']
 assert json.loads((BASE/'native-RAM-r2/report.json').read_text())['passed']
 assert json.loads((BASE/'CLOCK-error-RAM/report.json').read_text())['passed']
 CASE.mkdir(exist_ok=False)
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
 ram=(PRE/'owner-ram.bin').read_bytes();zp=(PRE/'owner-zp.bin').read_bytes();reference=(PRE/'B3-planning-reference.bin').read_bytes()
 report=dict(board='2512',passed=False,image_erases=0,checks=[],F_writes=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,owner_RAM_restored=False,power_cuts=0)
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def check(label):report['checks'].append(label);save();print('PASS '+label,flush=True)
 def rec():
  if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
  elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  else:
   if s.context==t.WB:s.command('B3');s.command('Q',(t.MON,))
   if s.context in (FT,t.CLOCK):s.command('Q',(t.MON,))
   if s.context!=t.REC:s.rec()
 def batch(text,expected=t.MON,seconds=90):
  assert len(text)<=34
  s.link.send(('BATCH '+text+'\r').encode());out=s.until((expected,),seconds=seconds)
  (CASE/(str(len(report['checks']))+'-batch.txt')).write_bytes(out);return out
 def stop_native(text,prompt):
  out=batch(text,b'BATCH stopped')
  out+=s.until((prompt,),seconds=20);return out
 save()
 with t.serial_lease('2512-reviewed-BATCH-wide-install',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12)
    assert b'g0000000A / MON B' in s.command('VERSION')
    borrowed=True;mark(batch_wide_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    rec();t.transport.recovery_usb(s.link);s.load(writer,t.sha(writer),opaque.PROMPT)
    wire=opaque.Wire(s.link.serial,timeout=90,trace=log,progress=lambda v:print(v,flush=True))
    assert wire.read_sector(3,0xF0)==reference[0x7000:]
    cd=wire.read_sector(3,0xC0)+wire.read_sector(3,0xD0);assert cd==reference[0x4000:0x6000]
    (CASE/'original-CD-history.bin').write_bytes(cd)
    # Admit every reviewed preimage before the first erase.
    for item in PLAN['system_targets']:
     label=item['label'];old=wire.read_sector(item['bank'],item['page'])
     assert old==(SCOPE/(label+'-expected-before.bin')).read_bytes(),label
     (CASE/(label+'-before.bin')).write_bytes(old)
    for item in PLAN['system_targets']:
     label=item['label'];old=(CASE/(label+'-before.bin')).read_bytes();new=(SCOPE/(label+'-target.bin')).read_bytes()
     assert item['bank']==2 or item['bank']==3 and item['page'] in (0x80,0x90,0xA0,0xB0,0xE0)
     report['image_erases']+=1;save();s.context=None
     assert not wire.replace_sector(item['bank'],item['page'],old,new)
     s.context=opaque.PROMPT;assert wire.read_sector(item['bank'],item['page'])==new
     check('installed-'+label)
    rec();s.monitor();assert b'g0000000B / MON B' in s.command('VERSION')
    s.command('R MAINT',(FT,));assert b'DEFAULT=B' in s.command('BOOT');assert b'OK' in s.command('BOOT C B');s.command('Q',(t.MON,))
    report['B_generation_bound']='0000000B';check('same-B-policy-bound-to-new-generation')
    out=batch('M 3000 AA;D 3000 3000;V');assert b'BATCH done' in out and b'3000: AA' in out and b'g0000000B / MON B' in out
    out=batch('M F000 00;V');assert b'BATCH stopped' in out and b'/ MON B' not in out
    out=batch('M1;W;APPS');assert b'BATCH done' in out and b'CLOCK' in out
    check('MON-command-vector-readonly-services-and-failure-stop')
    out=batch('R CLOCK;STATUS;Q;V');assert b'raw' in out.lower() and b'BATCH done' in out and b'g0000000B / MON B' in out
    check('CLOCK-command-prompt-and-return-to-remaining-queue')
    out=batch('R FLASH;BANK 0;READ 9000;Q;V');assert b'BATCH done' in out and b'g0000000B / MON B' in out
    check('FLASH-4K-buffer-and-return-to-remaining-queue')
    out=stop_native('R FLASH;BANK 3;ERASE F000;Q;V',FT);assert b'REFUSED' in out and b'/ MON B' not in out
    s.command('Q',(t.MON,));check('native-error-discards-queued-Q-and-V')
    out=batch('R FLASH;BANK 0;ERASE 9000;Q',b'type YES> ');assert b'B0:9000' in out
    s.link.send(b'NO\r');out=s.until((b'BATCH stopped',),seconds=45);out+=s.until((FT,));assert b'Canceled' in out
    s.command('Q',(t.MON,));check('native-erase-confirmation-remains-live-and-NO-stops')
    s.command('MAINT',(t.WB,));s.mount()
    out=batch('R CLOCK;TIME;Q;TABLE P',t.WB);assert b'NFCOPY' in out and b'BATCH done' in out
    s.command('B3');s.command('Q',(t.MON,));check('MAINT-interpreter-retained-across-native-handoff')
    # A has the same suite; qualify its distinct active slot/return vector once.
    rec();s.command('A',(t.MON,));assert b'g0000000B / MON A' in s.command('VERSION')
    out=batch('R CLOCK;TIME;Q;V');assert b'g0000000B / MON A' in out and b'BATCH done' in out
    rec();s.monitor();check('MON-A-active-slot-quiet-return')
    # Re-read only journal/F/metadata through the installed HOST interface.
    s.command('R FLASH',(FT,));s.command('HOST',(opaque.PROMPT,));wire=opaque.Wire(s.link.serial,timeout=60,trace=log)
    final=bytearray(reference)
    for item in PLAN['system_targets']:
     if item['bank']==3:final[(item['page']-128)*256:(item['page']-112)*256]=(SCOPE/(item['label']+'-target.bin')).read_bytes()
    final[0x4000:0x6000]=wire.read_sector(3,0xC0)+wire.read_sector(3,0xD0)
    assert wire.read_sector(3,0xF0)==reference[0x7000:]
    history=wire.read_sector(3,0x90);assert history[3072:]==reference[0x1c00:0x2000];final[0x1000:0x2000]=history
    j=t.classify_journal(bytes(final));assert j['sequence']==1080 and j['default']=='B' and j['enabled_mask']==15 and j['entries']==[8]*4
    assert j['counts'][28:]==[54,35,30,24] and j['valid_records']==19
    (CASE/'B3-after-composed.bin').write_bytes(final);report['journal']=j
    wire.send(b'Q\r');wire.text_until(FT);s.context=FT;s.command('Q',(t.MON,));check('golden-F-RTC-metadata-and-journal-rotation-accounting')
   finally:
    try:
     if borrowed:
      rec();s.service(reader);report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:
      restored=report['owner_RAM_restored'];mark(batch_wide_worker_active=False,application_RAM_restore_pending=not restored,block_snapshot=not restored,application_ram_restored=restored,batch_wide_installation_pending='journal' not in report)
     save()
 report['passed']='journal' in report and report['owner_RAM_restored'];save();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
