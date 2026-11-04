"""Owner-requested installed ASM/DBG soak on2205; bounded RAM-only units."""
import sys,json,time,re,random,msvcrt,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('C:/SRC/STR8-N');sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c,rtc_fleet as f
import devtools_2512_session as ds
from install_2205_foundation_profile import Session as BoardSession
from serial_test_coordination import serial_lease,drift_pending
t=ds.t;Q=c.Q;CONTROL=Q/'2205-intensive-asm-dbg-soak.json'
START=b'DBG RAM start 0200-3FFF; Q MON> '
class Defer(Exception):pass
def room(seconds):
 due=datetime.fromisoformat(c.read(Q/'rtc-hourly-controller-last.json')['next_due']).timestamp()
 return not drift_pending() and time.time()+seconds<due
def cache_code():
 code=bytearray(bytes.fromhex('78D8A200'));loop=0x3004
 for page in range(13):code+=bytes((0xbd,0,(0x2000+256*page)>>8,0x9d,0,(0x6b00+256*page)>>8))
 code+=bytes((0xe8,0xd0,(loop-(0x3000+len(code)+3))&255));code+=bytes.fromhex('A92F85E0AD307D85E16CE000')
 return bytes(code)
def offline():
 from py65.devices.mpu65c02 import MPU
 for seed in range(12):
  rnd=random.Random(seed);memory=[rnd.randrange(256) for _ in range(65536)]
  high=bytes(memory[0x6b00:0x7800]);memory[0x2000:0x2d00]=high;memory[0x6b00:0x7800]=[v^255 for v in high];code=cache_code();memory[0x3000:0x3000+len(code)]=code;memory[0x7d30]=0x7e
  before=memory[:];cpu=MPU(memory=memory,pc=0x3000)
  for _ in range(15000):
   if cpu.pc==0x7e2f:break
   cpu.step()
  else:raise AssertionError('Cache helper did not return')
  assert bytes(memory[0x6b00:0x7800])==high
  assert all(a==b or 0x6b00<=n<0x7800 or n in (0xe0,0xe1) for n,(a,b) in enumerate(zip(before,memory)))
 for value in (0,1,0x7f,0x80,0xfe,0xff):
  memory=[0]*65536;body=bytes((0xa9,value,0xa2,0x42,0x20,0x0e,0x18,0x8d,0,0x1a,0xea,0x4c,0x67,0x7e,0x1a,0x60));memory[0x1800:0x1810]=body;cpu=MPU(memory=memory,pc=0x1800)
  for _ in range(20):
   if cpu.pc==0x7e67:break
   cpu.step()
  assert cpu.pc==0x7e67 and memory[0x1a00]==(value+1)&255 and cpu.x==0x42
 assert t.sha((t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes())==t.live.READBACK_SHA256
 return dict(passed=True,cache_restore_CPU_cases=12,DBG_fixture_CPU_cases=6,cache_helper_sha256=t.sha(cache_code()))
class Work(ds.Session):
 def __init__(self,out,report):
  self.out=out;self.r=report;self.s=None;self.borrowed=False;self.ram=self.zp=self.high=None;self.cache_first=0x6b00;self.mp=Q/'device-operations/2205.json';self.cleanup=False
 def cmd(self,line,tokens=None):
  if not self.cleanup and self.borrowed and not c.read(CONTROL)['active']:raise Defer('Owner stop; restore and release')
  if not self.cleanup and self.borrowed and not room(150):raise Defer('RTC priority; restore before releasing lease')
  assert not re.match(r'(SAVE|SET|TRIM|ACK|ERASE|OFFSET|BATTERY|BOOT|EDU|LOAD|COPY)\b',line)
  if self.s.context==t.MON and line.startswith('M '):
   parts=line.split();a=int(parts[1],16);assert 0x200<=a and a+len(parts)-2<=0x4000
  return super().cmd(line,tokens)
def unit(state):
 if not room(360):raise Defer('RTC window; no port opened')
 out=Path(state['root'])/f'unit-{state["passed_units"]:06d}-{time.time_ns()}';out.mkdir()
 r=dict(board='2205',passed=False,started_utc=c.NOW(),cycles=0,checks=[],flash_writes=0,SPI_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
 x=Work(out,r);reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();banks=None;m=None
 def check(n):r['checks'].append(n);x.save()
 def dump(a,z):return b''.join(x.s.dump(n,min(z,n+511)) for n in range(a,z+1,512))
 def regs(face):
  found=re.search(rb'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2})',face);assert found,face
  return tuple(int(n,16) for n in found.groups())
 def poke(a,body):
  for n in range(0,len(body),8):x.cmd(f'M {a+n:04X} '+body[n:n+8].hex(' ').upper())
 baseline=c.read(c.STATE)['baselines'];segments=c.read(c.STATE).get('segment_boundaries');x.save()
 with serial_lease('2205-intensive-ASM-DBG-soak',timeout=1):
  if not room(360):raise Defer('RTC admission changed; no port opened')
  m=f.admission('2205');assert m['monitor_generation']=='00000010' and m['ASM_DBG_flash_installed'];c.save(out/'marker-before.json',m)
  with (out/'serial.jsonl').open('x') as log:
   try:
    x.s=BoardSession(out,log);s=x.s;s.link.send(b'\r');s.until((t.REC,t.MON),seconds=10)
    if s.context!=t.REC:raise Defer('Idle REC required; leave current monitor/application unchanged')
    x.mon();v=x.cmd('VERSION');assert b'Board: 2205' in v and b'CPU: 65C02' in v and b'gen 00000010' in v
    prefix=dump(0x200,0x1ff+len(reader));x.zp=dump(0,0xdf);x.high=dump(0x6b00,0x77ff);x.oldhooks=x.hooks();assert x.oldhooks==bytes.fromhex('577E4C937E')
    assert dump(0x200,0x1ff+len(reader))==prefix and dump(0,0xdf)==x.zp
    for name,body in [('prefix-before.bin',prefix),('owner-zp.bin',x.zp),('provider-cache-before.bin',x.high),('hooks-before.bin',x.oldhooks)]:(out/name).write_bytes(body)
    x.mark(ASM_DBG_soak_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True,ASM_DBG_soak_escrow=str(out));x.borrowed=True
    x.rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;x.ram=prefix+memory[len(reader):];(out/'owner-ram.bin').write_bytes(x.ram)
    banks=[s.client.flash(n) for n in range(4)]
    assert all(t.sha(body)==m['current_physical_bank_sha256'][f'B{n}'] for n,body in enumerate(banks));check('fresh RAM/ZP/cache/hooks and all four flash banks admitted')
    x.mon();assert b'ASM B0:A000' in x.cmd('APPS')
    # Rotate a complete application with the small regression fixtures.
    which=state['passed_units']%3
    if which in (0,1):
     source=ROOT/('release/rc1-uchess/uchess.a' if which==0 else 'tests/baselines/phase12-evidence/kit/hello-a/source.asm')
     lines=[re.sub(r'\s+EQU\s+', ' = ', line.strip(), flags=re.I) for line in source.read_text().splitlines() if line.strip() and not line.lstrip().startswith(';')]
     assert len(lines)<1000 and all(len(line)<110 for line in lines)
     r['real_program']=dict(source=str(source),source_sha256=t.sha(source.read_bytes()),name='Microchess' if which==0 else 'hello-a debugger walkthrough');x.save()
     x.cmd('R ASM',(ds.AP,));x.cmd('NEW')
     for n,line in enumerate(lines,1):x.cmd(f'{n} {line}')
     assembled=x.cmd('ASM');assert b'OK ' in assembled and b'Error' not in assembled,assembled
     assert b'S1' in x.cmd('S19')
     x.cmd('QUIT',(t.MON,))
     if which==0:
      assert b'OK 1439 bytes' in assembled
      binary=dump(0x200,0x79e)
      assert t.sha(binary)=='d390d1d992b6796904d559c95fab5807ec4afaa7793d376e7ceab1e8309f2030'
      r['real_program']['executable_sha256']=t.sha(binary)
     x.cmd('R DBG',(START,));x.cmd('0200',(ds.DP,))
     assert b'SEI' in x.cmd('U 0200 3')
     assert regs(x.cmd('S'))[0]==0x201
     assert regs(x.cmd('S'))[0]==0x202
     x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks
     if which==0:
      # The game consumes single keys, not command lines.
      s.link.send(b'G 0200\r');s.context=None
      face=s.link.until(b'benlo.com',seconds=15);(out/'microchess-startup.txt').write_bytes(face)
      s.link.send(b'Q');s.until((t.MON,),seconds=15)
      assert x.hooks()==x.oldhooks
     else:
      x.cmd('R DBG',(START,));x.cmd('0200',(ds.DP,))
      x.cmd('C',(ds.DP,));face=x.cmd('C',(ds.DP,));assert b'A' in face
      x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks
     r['real_program']['passed']=True;r['cycles']+=1
     check('real application: source assemble/export; DBG disassemble/step/exit; run and clean return')
    rng=random.Random(state['passed_units'])
    for turn in range(2 if which in (0,1) else 8):
     if not room(190):break
     value=([0,1,0x7f,0x80,0xfe,0xff]+[rng.randrange(256),rng.randrange(256)])[turn];xx=rng.randrange(256)
     x.cmd('R ASM',(ds.AP,));x.cmd('NEW')
     for line in ('10 ORG $0200',f'20 LDA #${value:02X}','30 STA $1800','40 JMP $7E67','50 END'):x.cmd(line)
     assert b'OK 8 bytes' in x.cmd('ASM');assert b'0200 A9' in x.cmd('LST') and b'S1' in x.cmd('S19')
     x.cmd('20 LDA MISSING');bad=x.cmd('ASM');assert b'MISSING' in bad and b'Error line 20' in bad
     assert b'Assemble successfully first' in x.cmd('LST');x.cmd(f'20 LDA #${value:02X}');assert b'OK 8 bytes' in x.cmd('ASM')
     x.cmd('QUIT',(t.MON,));assert s.dump(0x200,0x207)==bytes((0xa9,value,0x8d,0,0x18,0x4c,0x67,0x7e))
     x.cmd('G 0200',(t.MON,));assert s.dump(0x1800,0x1800)==bytes((value,));assert x.hooks()==x.oldhooks
     program=bytes((0xa9,value,0xa2,xx,0x20,0x0e,0x18,0x8d,0,0x1a,0xea,0x4c,0x67,0x7e,0x1a,0x60));poke(0x1800,program)
     x.cmd('R DBG',(START,));assert regs(x.cmd('1800',(ds.DP,)))[0]==0x1800
     assert b'LDA' in x.cmd('U 1800 3');assert regs(x.cmd('S'))[:2]==(0x1802,value);assert regs(x.cmd('S'))==(0x1804,value,xx)
     assert regs(x.cmd('N'))==(0x1807,(value+1)&255,xx)
     x.cmd('B 180A');assert regs(x.cmd('C',(ds.DP,)))[0]==0x180a;assert f'1A00: {(value+1)&255:02X}'.encode() in x.cmd('D 1A00')
     x.cmd('BC');assert regs(x.cmd('S'))[0]==0x180b;x.cmd('C',(t.MON,));assert x.hooks()==x.oldhooks and s.dump(0x180a,0x180a)==b'\xea'
     x.cmd('R DBG',(START,));x.cmd('1800',(ds.DP,));x.cmd('B 180A');x.cmd(f'R A {xx:02X}');assert regs(x.cmd('R'))[1]==xx
     x.cmd('X',(t.MON,));assert x.hooks()==x.oldhooks and s.dump(0x180a,0x180a)==b'\xea'
     r['cycles']+=1;check(f'cycle{turn}: ASM edit/error/reassemble/export/execute; DBG S/N/JSR/RTS/breakpoint/register/X/HOLD')
    r['workload_passed']=r['cycles']>0
   except Defer as e:r['deferred']=str(e)
   except Exception as e:r['error']=repr(e)
   finally:
    x.cleanup=True
    try:
     if x.borrowed:
      x.mon();assert x.hooks()==x.oldhooks,'Debugger hooks need controlled cleanup';x.restore_high();assert x.hooks()==x.oldhooks
      x.rec();x.s.service(reader)
      try:
       if banks is not None:
        assert all(x.s.client.flash(n)==banks[n] for n in range(4));r['all_flash_banks_unchanged']=True
      finally:
       assert x.ram is not None,'No verified RAM authority; retain restoration guard'
       r.update(x.s.client.restore_owner(x.ram,x.zp));x.s.context=t.REC;r['original_prompt_restored']=True
      state_now=c.read(c.STATE);assert state_now['baselines']==baseline and state_now.get('segment_boundaries')==segments;r['RTC_baselines_segments_unchanged']=True
    except Exception as e:r['restoration_error']=repr(e)
    finally:
     if x.s:x.s.link.close();r['port_released']=True
     if x.borrowed:
      restored=r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and not r.get('restoration_error')
      x.mark(ASM_DBG_soak_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=bool(restored),block_snapshot=m.get('block_snapshot',False) if restored else True,last_ASM_DBG_soak=str(out/'report.json'))
     r.update(finished_utc=c.NOW(),passed=bool(r.get('workload_passed') and r.get('all_flash_banks_unchanged') and r.get('owner_RAM_restored') and r.get('owner_ZP_restored') and not r.get('error') and not r.get('restoration_error')));x.save()
 if not x.borrowed and r.get('deferred'):raise Defer(r['deferred'])
 return out/'report.json',r
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--run',action='store_true');args=p.parse_args();proof=offline();print('PASS offline',json.dumps(proof),flush=True)
 if args.init:
  assert not CONTROL.exists(),'Existing soak: no duplicate'
  root=Q/('2205-intensive-ASM-DBG-soak-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));root.mkdir();(root/'driver.py').write_bytes(Path(__file__).read_bytes());c.save(root/'offline-proof.json',proof)
  c.save(CONTROL,dict(active=True,board='2205',owner_instruction='worst clock? begin intensive ASM/DBG soak on a different board',root=str(root),passed_units=0,cycles=0,driver=str(Path(__file__)),driver_sha256=c.sha(__file__),RTC_priority=True,window_seconds=360,restore_reserve_seconds=150))
 if not args.run:return
 state=c.read(CONTROL);assert c.sha(__file__)==state['driver_sha256']
 if not state['active']:print('STOPPED');return
 root=Path(state['root']);handle=(root/'supervisor.lock').open('a+b');held=False
 try:
  if handle.seek(0,2)==0:handle.write(b'0');handle.flush()
  handle.seek(0)
  try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);held=True
  except OSError:print('DEFER overlap');return
  try:
   path,r=unit(state);state['last_report']=str(path);state['last_result']=r
   if r['passed']:state['passed_units']+=1;state['cycles']+=r['cycles'];print('PASS2205',json.dumps(r),flush=True)
   elif r.get('error') or r.get('restoration_error'):state['active']=False;state['failed']=True;print('FAIL2205',json.dumps(r),flush=True)
   else:print('DEFER',r.get('deferred'))
  except (Defer,TimeoutError) as e:state['last_defer']=str(e);print('DEFER',str(e),flush=True)
  state['active']=bool(state['active'] and c.read(CONTROL)['active']);state['updated_utc']=c.NOW();c.save(CONTROL,state)
 finally:
  if held:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
  handle.close()
if __name__=='__main__':main()
