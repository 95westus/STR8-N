"""2512-only initial ASM/DBG RAM workflow; zero nonvolatile writes."""
import json,re,time
from pathlib import Path
import install_named_edu_2512 as ins
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q
OUT=Q/'2512-ASM-DBG-BASE1-RAM-20261102-r3'
ASM=t.ROOT/'BUILD/asm-base1-g1-r6';DBG=t.ROOT/'BUILD/dbg-base1-g1-r5'
AP=b'ASM> ';DP=b'DBG> ';CONF=b'Discard unsaved edits? Type YES: '

def run():
 ins.window(360)
 am=json.loads((ASM/'manifest.json').read_text());dm=json.loads((DBG/'manifest.json').read_text())
 ab=(ASM/'ASM-BASE1-RAM.bin').read_bytes();db=(DBG/'DBG-BASE1-RAM.bin').read_bytes()
 assert t.sha(ab)==am['artifact_sha256'] and t.sha(db)==dm['artifact_sha256'] and dm['paired_ASM']==t.sha(ab)
 assert len(ab)<=0x6300 and len(db)<=0x6300
 OUT.mkdir();(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
 reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
 s=None;ram=zp=high=None;borrowed=False;hooks=None
 r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,SPI_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,ASM_sha256=t.sha(ab),DBG_sha256=t.sha(db))
 def save():t.save(OUT/'report.json',r)
 def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
 def cmd(line,tokens=None):
  face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:45]}.txt').write_bytes(face);return face
 def mon():
  if s.context is None:
   s.link.send(b'\x03\r');s.until((t.MON,t.REC,AP,DP,CONF,t.WB,d.SERVICE),seconds=15)
  if s.context==CONF:cmd('NO',(AP,))
  if s.context==AP:cmd('QUIT',(t.MON,))
  if s.context==DP:cmd('X',(t.MON,))
  if s.context==t.WB:cmd('Q',(t.MON,))
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  if s.context==t.REC:cmd('B',(t.MON,))
  assert s.context==t.MON
 def rec():
  if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
  elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
 def check(name):r['checks'].append(name);save();print('PASS2512 '+name,flush=True)
 def boundary():
  if drift_pending():raise InterruptedError('RTC priority; restore before releasing lease')
 def current_hooks():return s.dump(0x7e02,0x7e03)+s.dump(0x7e67,0x7e69)
 def restore_high():
  if high is None:return
  mon()
  # Copy the saved provider-cache pages without running STATUS afterward.
  for off in range(0,len(high),8):cmd(f'M {0x2000+off:04X} '+high[off:off+8].hex(' ').upper())
  code=bytearray(bytes.fromhex('78D8A200'));loop=0x3004
  for page in range(5):code+=bytes((0xbd,0,(0x2000+256*page)>>8,0x9d,0,(0x7000+256*page)>>8))
  code+=bytes((0xe8,0xd0,(loop-(0x3000+len(code)+3))&255))
  code+=bytes.fromhex('A92F85E0AD307D85E16CE000') # active UI/1 BYPASS vector
  for off in range(0,len(code),8):cmd(f'M {0x3000+off:04X} '+code[off:off+8].hex(' ').upper())
  cmd('G 3000',(t.MON,));assert s.dump(0x7000,0x74ff)==high;r['provider_cache_restored']=True
 def debug_packet(fixture):
  packet=bytearray(db);packet[0xe00:0xe00+len(fixture)]=fixture;rec();s.load(bytes(packet),t.sha(packet),DP)
 save()
 with t.serial_lease('2512-BASE1-ASM-DBG-RAM',timeout=30):
  ins.window(360);m=json.loads(mp.read_text());assert m['application_ram_restored'] and not m['application_RAM_restore_pending'] and not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
  t.save(OUT/'marker-before.json',m)
  with (OUT/'serial.jsonl').open('x') as log:
   try:
    s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=15);mon()
    face=cmd('VERSION');assert b'STR8-N MON B  gen 00000010' in face and b'CPU: 65C02' in face
    prefix=s.dump(0x200,0x1ff+len(reader));zp=s.dump(0,0xdf);high=s.dump(0x7000,0x74ff);hooks=current_hooks();assert hooks==bytes.fromhex('577E4C937E')
    for name,body in [('owner-zp.bin',zp),('provider-cache-before.bin',high),('hooks-before.bin',hooks)]:(OUT/name).write_bytes(body)
    mark(ASM_DBG_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
    rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
    assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3'];check('fresh-owner-F-and-default-hooks-admitted')
    mon();cmd('MAINT LOAD',(t.WB,));cmd('SRAM');cmd('Q',(t.MON,))
    provider=s.dump(0x6b00,0x77ff);assert t.sha(provider)=='8128b9c542ecdc335d400465ed9a3cb8f3a1fbfce6ed37a507ddfe1bafc4f667'
    boundary();rec();s.load(ab,am['artifact_sha256'],AP);cmd('?')
    lines=['BASE EQU $0200','PORT EQU $1800','ORG BASE','start: LDA #$42','.loop: STA PORT','BNE .loop','BYTE 1,2,3,4,5,6','END']
    for n,line in enumerate(lines,1):cmd(f'{n*10} {line}')
    face=cmd('ASM');assert b'OK 13 bytes' in face,face
    symbols=cmd('SYMS');assert b'0200 BASE' in symbols and b'1800 PORT' in symbols and b'0202 START.LOOP' in symbols
    listing=cmd('LST');assert b'0200 A9 42' in listing and b'020B 05 06' in listing
    assert b'0200: A9 42' in cmd('DUMP');assert b'S1' in cmd('S19');check('resident-edit-EQU-local-labels-ASM-LST-SYMS-DUMP-S19')
    cmd('40 start: LDA MISSING');face=cmd('ASM');assert b'Symbol: MISSING' in face and b'Error line 40:' in face
    face=cmd('LST');assert b'Assemble successfully first' in face
    cmd('40 start: LDA #$42');cmd('90 NOP\x08\x08\x08END');face=cmd('LIST');assert b'90 END' in face
    cmd('90');check('diagnostics-invalid-result-refusal-line-edit-and-delete')
    face=cmd('LOAD SRAM MISSING',(CONF,));assert s.context==CONF;assert b'Load cancelled' in cmd('NO',(AP,))
    face=cmd('SAVE FLASH NOTEST');assert b'Source storage: 81' in face
    check('unsaved-load-cancel-and-unlinked-flash-source-refusal-without-writes')
    cmd('NEW')
    for line in ('10 ORG $0200','20 LDA #$42','30 STA $1800','40 JMP $7E67','50 END'):cmd(line)
    assert b'OK 8 bytes' in cmd('ASM');cmd('QUIT',(t.MON,));expected=bytes.fromhex('A9428D00184C677E');assert s.dump(0x200,0x207)==expected
    cmd('G 0200',(t.MON,));assert s.dump(0x1800,0x1800)==b'\x42';check('assembled-RAM-output-run-and-public-HOLD')
    boundary();fixture=bytes.fromhex('0000A911A2222015108D0018EA00004C677EEAEAEA1A60');assert len(fixture)==23
    debug_packet(fixture);face=cmd('R');assert b'PC=1002' in face
    face=cmd('U 1002 3');assert b'LDA' in face and b'LDX' in face and b'JSR' in face
    assert b'PC=1004' in cmd('S') and b'PC=1006' in cmd('S');face=cmd('N');assert b'PC=1009' in face and b'A=12' in face
    cmd('B 100C');face=cmd('C',(DP,));assert b'PC=100C' in face;assert b'1800: 12' in cmd('D 1800')
    cmd('M 1800 55');assert b'1800: 55' in cmd('D 1800');assert b'A=66' in cmd('R A 66')
    cmd('BC');assert b'PC=100D' in cmd('S');assert b'PC=100F' in cmd('S');cmd('C',(t.MON,))
    assert current_hooks()==hooks and s.dump(0x100c,0x100c)==b'\xea';check('BRK-registers-disassembly-S-N-breakpoint-D-M-C-and-HOLD-hook-cleanup')
    boundary();debug_packet(fixture);cmd('B 100C');cmd('X',(t.MON,));assert current_hooks()==hooks and s.dump(0x100c,0x100c)==b'\xea';check('DBG-X-restores-hooks-and-original-breakpoint-byte')
    restore_high();assert current_hooks()==hooks
    rec();s.service(reader);assert t.sha(s.client.flash(3))==m['current_physical_bank_sha256']['B3'];r['B3_F_images_settings_history_unchanged']=True
   except BaseException as e:r['error']=repr(e);save();raise
   finally:
    try:
     if borrowed:
      mon();assert current_hooks()==hooks,'Stop: active debugger hook needs controlled cleanup before RAM restoration'
      # Entering MON from the readback service can reload STATUS. Always
      # restore the cache after that last MON entry, before final REC/escrow.
      restore_high()
      rec();s.service(reader);r.update(s.client.restore_owner(ram,zp));s.context=t.REC
    finally:
     if s:s.link.close();r['port_released']=True
     if borrowed:
      restored=r['owner_RAM_restored'] and r['owner_ZP_restored'];mark(ASM_DBG_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,block_snapshot=m['block_snapshot'] if restored else True,final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_ASM_DBG_RAM_trial=str(OUT/'report.json'))
     save()
 r['passed']=bool(len(r['checks'])==7 and r.get('B3_F_images_settings_history_unchanged') and r.get('provider_cache_restored') and r['owner_RAM_restored'] and r['owner_ZP_restored']);save();assert r['passed']
 print('PASS2512 initial ASM/DBG RAM workflow; F/SPI/RTC unchanged; hooks/cache/owner restored; REC>;COM4 free',flush=True)

if __name__=='__main__':run()
