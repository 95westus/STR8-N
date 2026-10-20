"""Explicit owner-authorized DBG1 hardware closeout. No promotion or native tests."""
import argparse,contextlib,hashlib,json,re,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';KIT=ROOT/'BUILD/rc1-debugger-boardtest-r1'
sys.path.insert(0,str(KIT))
import board_link as wire
import rc1_dbg_closeout_cases as tests
from atomic_json import publish
from rtc_prompt_sync import establish_b3,drain
import serial_test_coordination as coordination
coordination.ROOT=Q/'serial-coordination'
from serial_test_coordination import serial_lease
from run_rc1_dbg_soak import Runner as Soak
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
NOW=lambda:datetime.now(timezone.utc).isoformat()
BOARDS={'2604':('COM5','A10MQGVHA','B',2),'2609':('COM8','A10MPQXCA','A',0x16)}
class Closeout:
 def __init__(self,run,board,registrations_only=False,only_slot=None):
  self.run=run.resolve();self.board=board;self.only_slot=only_slot;self.registrations_only=registrations_only;self.out=self.run/board/(('registrations-only-'+only_slot) if only_slot else ('registrations-only' if registrations_only else 'pre-rollback'));self.out.mkdir(parents=True,exist_ok=False)
  self.port,self.usb,self.preferred,self.cpu=BOARDS[board];self.root=ROOT;self.transport=wire;self.drain=drain;self.establish=establish_b3
  self.auth=READ(self.run/'owner-authorization.json');assert self.auth['owner_authorized'] and self.auth['registration_tests'] and self.auth['supported_app_regression'] and self.auth['rollback_reinstall'] and self.auth['promotion_held'] and not self.auth['native_debugging']
  self.manifest=wire.plans.package(KIT);assert SHA(KIT/'board-test-manifest.json')=='3287d719b703b1ae87300c05ffba9fe803594995e4a9156781c03c86d4fb0e9c'
  self.backup=self.run/f'{board}-before';self.identity,self.banks=wire.plans.capture(self.backup);assert self.identity['board']==board and self.identity['usb_serial']==self.usb and READ(self.backup/'report.json')['passed']
  self.original=(self.backup/'application-ram.bin').read_bytes();assert len(self.original)==25344
  self.observer=Q/'rc1-debugger-2609-boardtest-2026-10-19-030225Z/mode-observer';self.observer_sha256=READ(self.observer/'report.json')['s19_sha256']
  for name in ('registration-model-02.json','registration-model-816.json'):
   proof=READ(self.run/name);assert proof['passed'] and proof['case_source_sha256']==SHA(ROOT/'tools/rc1_dbg_closeout_cases.py') and len(proof['groups'])==36
  self.result=dict(passed=False,board=board,generation=50,native_debugging=False,native_applications_tested=False,promotion_held=True,supported_app_regression_requested=not registrations_only,clock_set=False,trim_changed=False,started_utc=NOW(),slots={},RAM_restored_host_verified=False)
  self.save()
 def save(self):publish(self.out/'report.json',self.result)
 def marker(self,**fields):
  path=Q/'device-operations'/f'{self.board}.json';m=READ(path);assert m['run']==str(self.run);m.update(fields);publish(path,m)
 @contextlib.contextmanager
 def connection(self):
  from serial.tools.list_ports import comports
  assert sum(p.device==self.port and p.serial_number==self.usb for p in comports())==1
  active=READ(Q/'active-rtc-campaign.json');assert self.board not in active['powered_off_boards']
  with serial_lease('dbg1-closeout-'+self.board,timeout=60,priority=True):
   with (self.out/'serial.jsonl').open('x') as log:
    link=wire.wire.Link(self.port,log)
    try:yield link
    finally:link.serial.close()
 def identity_slot(self,link,slot):
  text=wire.identity(link,self.board,50);assert f'Running: MONITOR {slot}, gen 00000032' in text
  assert link.dump(0x7D30,0x7D30)==bytes([0xA0 if slot=='A' else 0xB0]) and link.dump(0x7D01,0x7D01)==bytes([self.cpu])
  assert link.dump(0x7E02,0x7E03)==b'\x81\x7B' and link.dump(0x7BFC,0x7BFF)==bytes(4)
  return text
 def switch(self,link,slot):
  if link.dump(0x7D30,0x7D30)[0]!=(0xA0 if slot=='A' else 0xB0):
   text=link.command('P '+slot);assert f'Preferred {slot} 00000032'.encode() in text
   link.send(b'J3\r');link.until(b'\r\nB3> ',90);establish_b3(link)
  return self.identity_slot(link,slot)
 def clock(self,link):
  text=link.command('R CLOCK',b'CLOCK> ')+link.command('STATUS',b'CLOCK> ')+link.command('Q')
  raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
  expected=(0,12) if self.board=='2604' else (128,14)
  assert raw[7:9]==bytes(expected) and raw[0]&128 and raw[3]&8 and b'Running: yes' in text and b'Backup enabled: yes' in text
  return dict(passed=True,raw=raw.hex(),controls_trim_oscillator_backup_preserved=True)
 def flash_guard(self,link):
  banks=[]
  for bank in range(4):
   prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);banks.append(wire.read_range(link,0x8000,0xFFFF,prompt))
  link.command('B3')
  for bank in range(4):
   for offset in range(0,32768,4096):
    if bank==3 and offset in (0x4000,0x5000):continue
    assert banks[bank][offset:offset+4096]==self.banks[bank][offset:offset+4096],f'Unexpected flash change B{bank}:{offset+0x8000:04X}'
  _,_,old,_=wire.r.clean_journal(self.banks);_,_,new,_=wire.r.clean_journal(banks)
  assert old[8:24]==new[8:24],'Configuration/preference changed'
  assert old[24:120]==new[24:120],'Erase counts changed during RAM/app checks'
  return dict(passed=True,all_firmware_and_other_flash_unchanged=True,original_config_and_preference_restored=True,erase_counts_unchanged=True,bank_sha256=wire.r.hashes(banks))
 def registrations(self,link,slot):
  results=[]
  for index,case in enumerate(tests.cases()):
   image=self.run/'registration-images'/f'{index:02d}.s19';cells=wire.load(link,image)
   if case['bank']!=3:link.command('B1',b'\r\nB1> ')
   class DebugLink:
    prompt=b'DBG> '
    def command(self,text,prompt=b'\r\nB3> '):
     self.prompt=prompt;return link.command(text,prompt)
    def dump(self,first,last):return link.dump(first,last,self.prompt)
   result=tests.exercise(DebugLink(),case);result['image_sha256']=SHA(image);results.append(result)
   publish(self.out/f'{slot}-registrations.json',dict(passed=False,completed=results))
   print('PASS',self.board,slot,'registration',index+1,case['name'],flush=True)
  proof=dict(passed=True,completed=results,cases=len(results),native_debugging=False);publish(self.out/f'{slot}-registrations.json',proof);return proof
 def apps(self,link,slot):
  text=link.command('APPS')+link.command('T 1');assert b'ASM' in text and b'UCHESS' in text and b'CLOCK' in text;(self.out/f'{slot}-apps.txt').write_bytes(text)
  link.send(b'R 1 UCHESS\r');game=link.until(b'Microchess Copyright',30);time.sleep(.3);link.send(b'Q');game+=link.until(b'\r\nB3> ',30);assert b'Peter Jennings' in game;(self.out/f'{slot}-uchess.txt').write_bytes(game)
  text=link.command('ASM',b'ASM> ');assert b'ASM 0.5' in text
  for command in ('NEW','10 ORG $0200',"20 LDA #'R'",'30 JSR $7E6D','40 JMP $7E67','ASM','S19'):
   answer=link.command(command,b'ASM> ');text+=answer
   if command=='ASM':assert b'OK 8 bytes' in answer
  text+=link.command('QUIT');assert wire.read_range(link,0x200,0x207)==bytes.fromhex('A9 52 20 6D 7E 4C 67 7E')
  text+=link.command('G 0200');assert b'R\r\nB3> ' in text;(self.out/f'{slot}-asm.txt').write_bytes(text)
  text=link.command('BATCH MAINT;Q;SRAM;Q;WORK;Q;EDU;Q',b'BATCH done')+link.until(b'\r\nB3> ');assert b'BATCH stopped' not in text
  for token in (b'BANK MAINT',b'SRAM>',b'WORK>',b'EDU>'):assert token in text,(token,text)
  (self.out/f'{slot}-batch.txt').write_bytes(text)
  return dict(passed=True,UCHESS_launch_copyright_HOLD=True,ASM_05_assembly_S19_RAM_execution=True,MAINT_SRAM_WORK_EDU_BATCH=True,CLOCK_111=self.clock(link))
 def execute(self):
  self.marker(state='dbg1-closeout-registration-app-checks',block_snapshot=True,application_RAM_restore_pending=True)
  publish(self.out/'restore-needed.json',dict(needed=True,archive=str(self.backup),RAM_sha256=SHA(self.backup/'application-ram.bin')))
  with self.connection() as link:
   try:
    establish_b3(link);self.identity_slot(link,self.preferred)
    for slot in ((self.only_slot,) if self.only_slot else (self.preferred,'A' if self.preferred=='B' else 'B')):
     version=self.switch(link,slot);mode=Soak.mode(self,link,self.board)
     registrations=self.registrations(link,slot);apps=dict(skipped=True,reason='Known MAINT boot-compatibility guard failure on 2604') if self.registrations_only else self.apps(link,slot);after=Soak.mode(self,link,self.board)
     self.result['slots'][slot]=dict(passed=True,version=version,mode_before=mode,registrations=registrations,apps=apps,mode_after=after);self.save()
     print('PASS',self.board,'MON',slot,'registrations' if self.registrations_only else 'registration and supported-app regression',flush=True)
    self.result['checks_passed']=True
   except BaseException:self.result['failure']=traceback.format_exc();self.save()
   finally:
    try:
     Soak.recover_idle(self,link);self.switch(link,self.preferred);self.result['final_mode']=Soak.mode(self,link,self.board);self.result['final_RTC']=self.clock(link)
     wire.load(link,self.backup/'restore-application-ram.s19');assert wire.read_range(link,0x200,0x64FF)==self.original
     self.result['RAM_restored_host_verified']=True;publish(self.out/'restore-needed.json',dict(needed=False,host_verified=True,archive=str(self.backup),RAM_sha256=SHA(self.backup/'application-ram.bin')))
     self.result['final_flash']=self.flash_guard(link)
    except BaseException:self.result['restoration_failure']=traceback.format_exc()
    self.result.update(passed=self.result.get('checks_passed',False) and self.result['RAM_restored_host_verified'] and 'restoration_failure' not in self.result,finished_utc=NOW());self.save()
    self.marker(state=('dbg1-closeout-registration-only-passed' if self.registrations_only else 'dbg1-closeout-pre-rollback-passed') if self.result['passed'] else 'inspection-required',application_RAM_restore_pending=not self.result['RAM_restored_host_verified'],application_RAM_restore_verified=self.result['RAM_restored_host_verified'],block_snapshot=True)
  print('END',self.board,self.result['passed'],self.out/'report.json',flush=True)
  if not self.result['passed']:raise RuntimeError(json.dumps(self.result))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--board',choices=BOARDS,required=True);ap.add_argument('--registrations-only',action='store_true');ap.add_argument('--only-slot',choices=('A','B'));a=ap.parse_args();assert not a.only_slot or a.registrations_only;Closeout(a.run,a.board,a.registrations_only,a.only_slot).execute()
if __name__=='__main__':main()
