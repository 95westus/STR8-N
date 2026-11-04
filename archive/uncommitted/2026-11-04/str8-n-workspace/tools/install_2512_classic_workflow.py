"""Three RAM-qualified workflow sectors; F and C/D are not image targets."""
import json
import install_2512_native_utilities as d
import nf_opaque as opaque
t=d.t;BASE=t.ROOT/'output/qualification/2512-classic-workflow-20261030-r1';CASE=BASE/'installation';SCOPE=BASE/'scope-r4';PRE=BASE/'RAM-trial';SERVICE=d.SERVICE

def run():
 assert json.loads((BASE/'RAM-trial-r4/report.json').read_text())['passed']
 plan=json.loads((SCOPE/'plan.json').read_text());assert plan['erases']==3
 CASE.mkdir(exist_ok=False);report=dict(board='2512',passed=False,repair_erases=0,checks=[],F_writes=0,C_D_erases=0,SRAM_writes=0,RTC_writes=0,owner_RAM_restored=False)
 ram=(PRE/'owner-ram.bin').read_bytes();zp=(PRE/'owner-zp.bin').read_bytes()
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
 s=None;borrowed=False
 def save():t.save(CASE/'report.json',report)
 def mark(**kw):m=json.loads(t.MARK.read_text());m.update(kw);t.save(t.MARK,m)
 def check(n):report['checks'].append(n);save();print('PASS '+n,flush=True)
 def rec():
  if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
  elif s.context==SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  else:
   if s.context==t.WB:s.command('B3');s.command('Q',(t.MON,))
   if s.context in (d.FT,t.CLOCK):s.command('Q',(t.MON,))
   if s.context!=t.REC:s.rec()
 def batch(text,target=t.MON):
  assert len(text)<=34;s.link.send(('BATCH '+text+'\r').encode());out=s.until((target,),seconds=120);(CASE/(str(len(report['checks']))+'-batch.txt')).write_bytes(out);return out
 save()
 with t.serial_lease('2512-three-sector-classic-workflow-install',timeout=30):
  with (CASE/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(CASE,log,'2512');s.link.send(b'\r');s.until((t.MON,),seconds=12);assert b'g0000000B / MON B' in s.command('VERSION')
    borrowed=True;mark(classic_workflow_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
    rec();s.service(reader);before=s.client.flash(3);j=t.classify_journal(before);assert j['sequence']==1087 and j['counts'][28:]==[54,35,31,24]
    assert before==(BASE/'RAM-trial-r4/B3-current.bin').read_bytes()
    (CASE/'B3-before.bin').write_bytes(before)
    rec();s.load(writer,t.sha(writer),opaque.PROMPT);wire=opaque.Wire(s.link.serial,timeout=90,trace=log)
    for item in plan['targets']:
     old=wire.read_sector(item['bank'],item['page']);assert old==(SCOPE/(item['label']+'-before.bin')).read_bytes();(CASE/(item['label']+'-before.bin')).write_bytes(old)
    for item in plan['targets']:
     old=(CASE/(item['label']+'-before.bin')).read_bytes();new=(SCOPE/(item['label']+'-target.bin')).read_bytes();assert t.sha(new)==item['after_sha256'];report['repair_erases']+=1;save();s.context=None
     assert not wire.replace_sector(item['bank'],item['page'],old,new);s.context=opaque.PROMPT;assert wire.read_sector(item['bank'],item['page'])==new;check('repaired-'+item['label'])
    rec();s.monitor();out=s.command('APPS');assert all(x in out for x in (b'CLOCK B2:B000',b'FLASH B2:E000',b'MAINT B2:E000',b'EDU SRAM WORK',b'PROGRAMS: T; R name'))
    check('installed-classic-APPS-catalogue')
    s.command('R EDU ON');assert b'EDU ON' in s.command('R EDU');assert b'PROGRAM' in s.command('RESTORE SRAM');assert b'PROGRAM' in s.command('R WORK');assert b'NFCOPY' in s.command('TABLE P')
    check('installed-familiar-R-RESTORE-tools-and-stored-program-catalogue')
    out=batch('R CLOCK BAD;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    out=batch('R EDU BAD;B0');assert b'BATCH stopped' in out and b'Data bank B0' not in out
    check('installed-reserved-errors-stop-without-stale-fallback')
    s.command('R   CLOCK',(t.CLOCK,));s.command('VERSION');s.command('Q',(t.MON,))
    s.command('R MAINT',(d.FT,));assert b'DEFAULT=B' in s.command('BOOT');s.command('Q',(t.MON,));check('installed-CLOCK-and-MAINT-BOOT-and-Q')
    rec();s.service(reader);final=s.client.flash(3);j=t.classify_journal(final)
    assert j['sequence']==1090 and j['valid_records']==29 and j['counts'][28:]==[54,35,32,24]
    for off in range(0x4000,0x6000,256):
     if before[off:off+256]!=b'\xff'*256:assert final[off:off+256]==before[off:off+256]
    assert final[:0x4000]==before[:0x4000]
    assert final[0x7000:]==before[0x7000:] and final[0x1c00:0x2000]==before[0x1c00:0x2000]
    assert j['default']=='B' and j['enabled_mask']==15 and j['entries']==[8]*4
    (CASE/'B3-after.bin').write_bytes(final);report['journal']=j;check('journal-metadata-and-golden-F-preserved')
   finally:
    try:
     if borrowed:
      if s.context!=SERVICE:rec();s.service(reader)
      report.update(s.client.restore_owner(ram,zp));s.context=t.REC;s.monitor();s.command('!M 6A20 01');report['owner_RAM_restored']=True
    finally:
     if s is not None:s.link.close();report['COM4_released']=True
     if borrowed:mark(classic_workflow_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],block_snapshot=not report['owner_RAM_restored'],application_ram_restored=report['owner_RAM_restored'],classic_workflow_installation_pending='journal' not in report)
     save()
 report['passed']='journal' in report and report['owner_RAM_restored'];save();print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':run()
