"""Preserving 2604/2609 soak. Short leased units yield to RTC acquisition."""
import argparse,contextlib,ctypes,datetime,hashlib,json,os,time,traceback
import serial
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease,drift_pending
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request

ROOT=Path(__file__).resolve().parents[1]
PROBES=ROOT/'BUILD/beta23-soak-probes'
CLIENT=ROOT/'BUILD/beta23-storage-models/hardware-client'
PORTS={'2604':'COM5','2609':'COM8'}
PATTERNS=[('wig-wag',bytes([0xAA,0x55]*4)),('shift-left',bytes(1<<i for i in range(8))),('shift-right',bytes(1<<i for i in reversed(range(8))))]
GROUPS=['monitor','clock','edu','sram','work','maint','saved-example','rtc-sram-20','rtc-sram-30','rtc-sram-40','rtc-sram-50','external-sram','eeprom','flash-0','flash-1','flash-2','flash-3']
GROUPS += ['sector-read-0','sector-read-1','sector-read-2','sector-read-3']
EXCLUDED={'monitor':'flash writes/erase/install, preferences, boot/reset and arbitrary execution',
 'CLOCK':'SET, ACK, CLEAR, ACCEPT EUI, TRIM/OFFSET setters',
 'EDU':'ON/OFF mode changes during drift', 'SRAM':'S/D/C/F and unreviewed saved-program execution',
 'WORK':'P/U/V/F allocation changes, repair and format',
 'MAINT':'E/C/W/X/J persistent writes, transfers and boot; P/F/N/S editor modification/staging'}
def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,data):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)
def drift_window(now=None):
 # Current collector: every three hours at :45, UTC hours 02/05/.../23.
 timestamp=time.time() if now is None else now
 first=datetime.datetime(2026,10,11,23,45,tzinfo=datetime.timezone.utc).timestamp()
 if timestamp<first-900:return False
 phase=(timestamp-9900)%10800
 release=ROOT/'output/qualification/serial-coordination/window-release.json'
 if phase<1500 and release.exists():
  try:
   if timestamp<json.loads(release.read_text())['until_unix']:return False
  except (OSError,ValueError,KeyError):pass
 return phase<1500 or phase>9900
@contextlib.contextmanager
def board_link(port,log,end):
 while time.time()<end:
  if drift_pending() or drift_window():time.sleep(2);continue
  stack=contextlib.ExitStack()
  try:
   stack.enter_context(serial_lease('soak',timeout=2));l=Link(port,log)
  except (TimeoutError,serial.SerialException):
   stack.close();time.sleep(2);continue
  try:yield l
  finally:l.serial.close();stack.close()
  return
 raise TimeoutError('Soak duration ended while waiting without owning a port')
def guards(l):
 assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64','EDU ON descriptor changed'
 assert l.dump(0x7D27,0x7D28)==b'\x01\0','Active/saved EDU ON required'
 assert l.dump(0x66AE,0x66AE)==b'\x01','SRAM protection changed'
def clock_snapshot(l,baseline):
 l.command('R CLOCK',b'CLOCK> ')
 text=l.command('STATUS',b'CLOCK> ')
 import re
 raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
 expected=abs(baseline['trim_steps'])|(0x80 if baseline['trim_steps']>0 else 0)
 assert raw[7]==baseline['control_register'] and raw[8]==expected,'RTC trim/control changed'
 assert b'Running: yes' in text and b'Backup enabled: yes' in text
 history=l.command('HISTORY',b'CLOCK> ');identity=l.command('EUI',b'CLOCK> ')
 assert baseline['eui'].encode() in identity,'RTC identity changed'
 l.command('Q',b'> ');l.command('B3')
 return {'history_hex':history.hex(),'eui_hex':identity.hex(),'rtc_control':raw[7],'rtc_trim':raw[8]}
def led(l,index):
 name,pattern=PATTERNS[index%3];assert load_image(l,PROBES/'led/led.s19')==digest((PROBES/'led/led.bin').read_bytes());write(l,0x3200,pattern)
 l.send(b'G 4000\r')
 try:
  for _ in range(8):l.until(b'~',seconds=5);time.sleep(.12);l.send(b'\r')
  l.until(b'\r\nB3> ',seconds=5)
 except Exception:
  l.send(b'\r'*8)
  l.until(b'\r\nB3> ',seconds=10)
  raise
 return name
def rtc_sram(l,out,iteration,address):
 assert load_image(l,PROBES/'rtc-sram/rtc-sram.s19')==json.loads((PROBES/'test-results.json').read_text())['probe_sha256']
 def call(op,address,data=None):
  if data is not None:write(l,0x3100,data)
  write(l,0x3000,bytes((op,address,16,255,0)));l.command('G 4000')
  assert l.dump(0x3003,0x3004)==b'\0\x10','RTC SRAM diagnostic failed'
  return l.dump(0x3100,0x310F) if op==1 else None
 backup=call(1,address)
 assert backup==call(1,address),'RTC backup unstable'
 (out/'rtc-sram-original.bin').write_bytes(backup)
 for a in (address,):
  old=backup;pattern=bytes(((iteration+a+i)^0xA5)&255 for i in range(16))
  save(out/'restore-state.json',dict(device='rtc-sram',address=a,original_hex=old.hex(),needs_restore=True))
  try:call(2,a,pattern);assert call(1,a)==pattern,'RTC write readback mismatch'
  finally:
   call(2,a,old);assert call(1,a)==old,'RTC RESTORATION FAILED'
   save(out/'restore-state.json',dict(device='rtc-sram',address=a,needs_restore=False,verified=True))
 assert call(1,address)==backup
 return dict(address=address,bytes=16,original_sha256=digest(backup),restored=True)
def external_sram(l,out,iteration):
 assert load_image(l,CLIENT/'client.s19')==json.loads((CLIENT/'test-results.json').read_text())['sha256'];address=0x800+(iteration*64)%0x1F780
 def call(op,data=None):
  if data is not None:write(l,0x2600,data)
  write(l,0x3E20,bytes((1,3,0xA5 if op==2 else 0)))
  write(l,0x3E00,memory_request(op,address,count=64,buffer=0x2600));l.command('G 2000')
  r=l.dump(0x3E10,0x3E38)
  assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24],'External SRAM diagnostic failed'
  assert l.dump(0x66AE,0x66AE)==b'\x01','SRAM protection not restored'
  return l.dump(0x2600,0x263F) if op==1 else None
 backup=call(1);assert call(1)==backup,'External SRAM backup unstable'
 (out/'external-sram-original.bin').write_bytes(backup)
 pattern=bytes((iteration+i*29)&255 for i in range(64))
 save(out/'restore-state.json',dict(device='external-sram',address=address,original_hex=backup.hex(),needs_restore=True))
 try:call(2,pattern);assert call(1)==pattern,'External SRAM write readback mismatch'
 finally:
  call(2,backup);assert call(1)==backup,'External SRAM RESTORATION FAILED'
  save(out/'restore-state.json',dict(device='external-sram',address=address,needs_restore=False,verified=True))
 return dict(address=address,bytes=64,original_sha256=digest(backup),restored=True)
def flash_readback(l,out,root,board,bank):
 prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
 try:data=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
 finally:l.command('B3')
 (out/'flash.bin').write_bytes(data);baseline=root/(board+f'-flash-b{bank}-original.bin')
 if baseline.exists():assert data==baseline.read_bytes(),'Flash or stored-program bytes changed during soak'
 else:baseline.write_bytes(data)
 return dict(bank=bank,bytes=len(data),sha256=digest(data),unchanged=True)
def eeprom_readback(l,out,root,board):
 load_image(l,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');images=[]
 for _ in range(2):
  l.command('G 2000');data=l.dump(0x2400,0x2494)
  assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
  images.append(data[:0x89])
 assert images[0]==images[1],'EEPROM repeated read mismatch'
 data=images[0];(out/'eeprom.bin').write_bytes(data);baseline=root/(board+'-eeprom-original.bin')
 if baseline.exists():assert data==baseline.read_bytes(),'EEPROM changed during soak'
 else:baseline.write_bytes(data)
 return dict(bytes=len(data),sha256=digest(data),unchanged=True,written=False)

def sector_read(l,out,iteration,bank):
 receipt=json.loads((PROBES/'sector-read-test-results.json').read_text())
 assert receipt['passed'] and load_image(l,PROBES/'sector-read/sector-read.s19')==receipt['sha256']
 address=0x8000+(iteration%8)*4096
 write(l,0x3000,bytes((bank,address>>8,255,0)));l.command('G 4000')
 status=l.dump(0x3002,0x3005)
 assert status[:2]==b'\0\x10','Sector reader failed/short read'
 assert status[2]==status[3],'Sector reader did not restore bank PCR'
 data=l.dump(0x2000,0x2FFF)
 prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
 try:expected=l.dump(address,address+4095,prompt)
 finally:l.command('B3')
 assert data==expected,'RAM sector reader differs from direct monitor read'
 (out/'sector.bin').write_bytes(data)
 return dict(bank=bank,address=address,bytes=4096,sha256=digest(data),monitor_match=True,bank_restored=True,flash_written=False)
def saved_example(l,board):
 table=l.command('T 2')
 if b' SDEMO' not in table:return dict(excluded=True,reason='No installed reviewed saved example')
 old=l.dump(0x2700,0x2700);code=l.dump(0x2600,0x2605)
 try:
  l.command('R 2 SDEMO L');actual=l.dump(0x2600,0x2605)
  assert actual==bytes.fromhex('EE 00 27 4C 67 7E'),'Unreviewed saved example: execution refused'
  l.command('G 2600');assert l.dump(0x2700,0x2700)==bytes([(old[0]+1)&255])
 finally:write(l,0x2700,old);write(l,0x2600,code)
 return dict(program='SDEMO',bounded_execution=True,cpu_scratch_restored=True)
def commands(l,group):
 replies=[]
 def cmd(c,p=b'\r\nB3> '):
  d=l.command(c,p);replies.append(dict(command=c,reply_hex=d.hex()));return d
 if group=='monitor':
  for c in ('?','TIME','APPS','T 0','T 1','T 2','T 3','M 1','M 2','M 3','C','D 7D04 7D0B'):cmd(c)
  for b in range(4):cmd('B'+str(b),f'\r\nB{b}> '.encode())
  cmd('B3')
 elif group=='clock':
  cmd('R CLOCK',b'CLOCK> ')
  for c in ('HELP','?','R','TIME','S','STATUS','EUI','HISTORY','SHOW 1','SHOW 2','SHOW 3','SHOW 4','TRIM','OFFSET','OFFSET ?'):cmd(c,b'CLOCK> ')
  cmd('QUIT',b'> ');cmd('B3')
 elif group in ('edu','sram','work','maint'):
  app=group.upper();p=b'BM> ' if group=='maint' else (app+'> ').encode()
  cmd('R '+app,p)
  cs={'edu':['?'],'sram':['?','T'],'work':['HELP','?'],
      'maint':['?','M 1','M 2','M 3','T 0','T 1','T 2','T 3','R 1 8000-803F','D 0-3F','K','V 1 8000-803F 1 8000']}[group]
  for c in cs:cmd(c,p)
  if group=='sram':
   table=cmd('T',p)
   if b'SOAKMISS' not in table:
    for c in ('R SOAKMISS','G SOAKMISS'):
     reply=cmd(c,p);assert b'SRAM: ' in reply and b'SRAM: 00' not in reply,'Missing-name refusal required'
  cmd('Q',b'> ');cmd('B3')
 return replies
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--hours',type=float,default=48);p.add_argument('--smoke',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--groups',nargs='+',choices=GROUPS,default=GROUPS);a=p.parse_args()
 assert a.hours>0,'Soak duration must be positive'
 out=a.root.resolve();out.mkdir(parents=True,exist_ok=True)
 campaign_path=ROOT/'output/qualification/active-rtc-campaign.json';campaign=json.loads(campaign_path.read_text());index=Path(campaign['baseline_index'])
 assert digest(index.read_bytes())==campaign['baseline_index_sha256']
 baseline={b['board']:b for b in json.loads(index.read_text())['boards']}
 test=json.loads((PROBES/'test-results.json').read_text());assert test['passed']
 sector_test=json.loads((PROBES/'sector-read-test-results.json').read_text());assert sector_test['passed']
 client=json.loads((CLIENT/'test-results.json').read_text());assert client['passed'] and digest((CLIENT/'client.bin').read_bytes())==client['sha256']
 start=time.time();end=start+a.hours*3600;iteration=0;passed=0;retained={}
 if a.resume:
  prior=json.loads((out/'config.json').read_text());assert prior['baseline']==campaign
  start=datetime.datetime.fromisoformat(prior['start_utc']).timestamp();end=datetime.datetime.fromisoformat(prior['end_utc']).timestamp()
  reports=list(out.glob('*/report.json'));assert all(json.loads(p.read_text())['passed'] for p in reports)
  assert all(not json.loads(p.read_text()).get('needs_restore') for p in out.glob('*/restore-state.json'))
  passed=len(reports);iteration=max((int(p.parent.name.split('-')[0]) for p in reports),default=0)
  retained={b:json.loads((out/(b+'-retained-rtc.json')).read_text()) for b in PORTS}
 def finished():
  save(out/'status.json',dict(state='smoke-passed' if a.smoke else 'completed',pid=os.getpid(),passed_units=passed,rounds=iteration,updated=time.time(),elapsed_hours=(time.time()-start)/3600))
 config=dict(pid=os.getpid(),start_utc=datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),end_utc=datetime.datetime.fromtimestamp(end,datetime.timezone.utc).isoformat(),boards=PORTS,baseline=campaign,groups=a.groups,sector_probe=sector_test,excluded=EXCLUDED,drift_reservation='15 minutes before through 25 minutes after every three hours at :45; pending unscheduled drift requests also take priority',patterns=[p[0] for p in PATTERNS],known_issue='APPS prints corrupt FF names on both boards; valid T record tables used instead')
 save(out/'config.json',config)
 assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001),'Cannot inhibit idle sleep for continuous soak'
 try:
  while time.time()<end:
   for group in a.groups:
    for board,port in PORTS.items():
     if a.resume and (out/f'{iteration:05d}-{board}-{group}'/'report.json').exists():continue
     if time.time()>=end:finished();return
     while drift_window() or drift_pending():
      save(out/'status.json',dict(state='yielding-to-drift',pid=os.getpid(),passed_units=passed,updated=time.time()));time.sleep(10)
      if time.time()>=end:finished();return
     assert json.loads(campaign_path.read_text())['baseline_index_sha256']==campaign['baseline_index_sha256'],'Drift campaign changed; stop soak for review'
     unit=out/f'{iteration:05d}-{board}-{group}';unit.mkdir(exist_ok=False)
     save(out/'status.json',dict(state='running',pid=os.getpid(),board=board,group=group,passed_units=passed,updated=time.time()))
     with (unit/'serial.jsonl').open('x') as log:
      assert next(x for x in comports() if x.device.upper()==port).serial_number==SERIALS[board]
      with board_link(port,log,end) as l:
       establish_b3(l);guards(l);before=clock_snapshot(l,baseline[board])
       if board in retained:assert before==retained[board],'Retained RTC state changed between soak units'
       else:
        retained[board]=before;save(out/(board+'-retained-rtc.json'),before)
       result=sector_read(l,unit,iteration,int(group[-1])) if group.startswith('sector-read-') else rtc_sram(l,unit,iteration,int(group.rsplit('-',1)[1],16)) if group.startswith('rtc-sram-') else external_sram(l,unit,iteration) if group=='external-sram' else eeprom_readback(l,unit,out,board) if group=='eeprom' else saved_example(l,board) if group=='saved-example' else flash_readback(l,unit,out,board,int(group[-1])) if group.startswith('flash-') else commands(l,group)
       after=clock_snapshot(l,baseline[board]);assert after==before,'RTC retained settings/history changed'
       pattern=led(l,passed);guards(l)
       save(unit/'report.json',dict(passed=True,board=board,group=group,pattern=pattern,result=result,rtc_preserved=True,finished=time.time()))
       passed+=1;print('PASS',board,group,pattern,passed,flush=True)
     save(out/'status.json',dict(state='running',pid=os.getpid(),passed_units=passed,updated=time.time()))
     time.sleep(.5)
   iteration+=1
   if a.smoke:break
   for _ in range(30):
    if time.time()>=end:break
    time.sleep(10)
  finished()
 except Exception:
  save(out/'status.json',dict(state='stopped-on-failure',pid=os.getpid(),passed_units=passed,updated=time.time(),error=traceback.format_exc()));raise
 finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
if __name__=='__main__':main()
