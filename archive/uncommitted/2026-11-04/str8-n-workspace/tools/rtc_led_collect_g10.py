"""Owner-authorized temporary RTC/LED collector. No firmware or clock writes."""
import argparse,json,re,time,hashlib,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('C:/SRC/STR8-N');sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tmp/migration-python')]
import rtc_drift_campaign as c
import rtc_fleet as f
import rtc_base1_collect as b
from serial_test_coordination import serial_lease
PROFILE='RTC-LED-SECONDS-RAM1'
BUILD=ROOT/'BUILD/rtc-led-seconds-r1'
CONFIG=c.Q/'rtc-led-seconds.json'
IMAGE_SHA='9782c1c4b26b906a44bcb9ecf5dd817ae09b28c612eb88dccb58bb8fa23ee71b'
def load():
 image=(BUILD/'collector.bin').read_bytes();proof=c.read(BUILD/'proof.json')
 assert proof['passed'] and proof['image_sha256']==hashlib.sha256(image).hexdigest()==IMAGE_SHA and len(image)==794
 assert len(proof['checks'])==18 and all(x['passed'] for x in proof['checks'])
 assert proof['RTC_data_writes']==proof['LED_DDR_writes']==0
 return image,proof
def exact(link,n):
 deadline=time.monotonic()+15
 while len(link.pending)<n:
  if time.monotonic()>deadline:raise TimeoutError('Incomplete LED collector packet')
  link.pending.extend(link.read(max(1,link.serial.in_waiting)))
 value=bytes(link.pending[:n]);del link.pending[:n];return value
def stage(link,data):
 # Keep each monitor's established RAM transport. 2604 must never use M.
 from installer.engine.legacy_transport import s19
 assert 0<len(data)<0x1000
 if getattr(link,'led_board',None) in ('2512','2609'):
  for n in range(0,len(data),8):
   reply=link.command(f'M {0x2000+n:04X} '+' '.join(f'{v:02X}' for v in data[n:n+8]),f.MON)
   assert not any(t in reply for t in [b'Bad',b'error',b'REFUSED',b'Protected',b'Long line',b'Wrap',b'Invalid']),reply
  assert f.dump_ram(link,0x2000,0x1fff+len(data))==data,'RAM load verification failed'
  return
 link.command('L',b'S19')
 for line in s19(dict(enumerate(data,0x2000)),0x2000).splitlines():
  link.send(line+b'\r\n');time.sleep(.04)
 reply=link.until(f.MON,seconds=45)
 assert not any(t in reply for t in [b'Bad',b'error',b'REFUSED',b'Protected']),reply
 assert f.dump_ram(link,0x2000,0x1fff+len(data))==data,'RAM load verification failed'
def decode(raw):
 def dec(v):
  assert v&15<10 and v>>4<10,'Invalid RTC BCD'
  return (v>>4)*10+(v&15)
 assert raw[0]&128 and raw[3]&32,'RTC not running'
 return datetime(2000+dec(raw[6]),dec(raw[5]&31),dec(raw[4]&63),dec(raw[2]&63),dec(raw[1]&127),dec(raw[0]&127),tzinfo=timezone.utc).timestamp()
def collect(board,folder,duration=62):
 assert board=='2512','This reader is only for2512 MON g10'
 assert duration==62,'Only qualified 62-second session allowed'
 image,proof=load();folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
 r=dict(board=board,capture_profile=PROFILE,passed=False,started_utc=c.NOW(),driver_sha256=c.sha(__file__),image_sha256=proof['image_sha256'],readings=[],clock_set_attempted=False,trim_changed=False,flash_written=False,PF_ACK=False,PF_history_written=False,PF_history_freshly_read=False,application_ram_restored=False,LED_restored=True,port_released=False,returned_to_original_prompt=False,collection_duration_s=duration)
 def save():c.save(folder/'report.json',r)
 save();link=None;original=None;backup=None;borrowed=False;running=False;previous=None;log=None
 marker_path=c.Q/f'device-operations/{board}.json';rows=[]
 with serial_lease('drift',timeout=30):
  try:
   from installer.engine.legacy_transport import Link
   from serial.tools.list_ports import comports
   previous=f.admission(board)
   ports=[p.device for p in comports() if p.serial_number==f.IDS[board]]
   assert len(ports)==1,'USB identity unavailable/ambiguous'
   r.update(port=ports[0],usb_serial=f.IDS[board]);c.save(folder/'marker-before.json',previous)
   log=(folder/'serial.jsonl').open('x');link=Link(ports[0],log);link.led_board=board
   link.send(b'\r');_,face=f.until_any(link,[b'> '],15)
   original=f.MON if face.endswith(f.MON) else f.REC if face.endswith(f.REC) else None
   assert original,'Leave foreground application alone'
   r['original_prompt']=original.decode().strip()
   if original==f.REC:link.command('B',f.MON)
   if board in ('2512','2609'):
    version=link.command('V',f.MON);(folder/'VERSION.txt').write_bytes(version)
    cpu=b'65C816' if board=='2609' else b'65C02'
    assert cpu in version,'CPU identification missing; no RAM borrowed'
    assert b'EDU ON' in version,'Saved/session EDU OFF; do not borrow RAM'
    assert b'  gen 00000010' in version
   else:
    descriptor=f.dump_ram(link,0x7d00,0x7d3f);abi=f.dump_ram(link,0x7e60,0x7e63)
    (folder/'CPU-descriptor.bin').write_bytes(descriptor);(folder/'ABI-descriptor.bin').write_bytes(abi)
    assert descriptor[1]==2 and abi==b'RA\x01\x0d','Legacy 65C02/ABI identity mismatch'
   f.admission(board)
   backup=f.dump_ram(link,0x2000,0x1fff+len(image));(folder/'RAM-before.bin').write_bytes(backup)
   assert f.dump_ram(link,0x2000,0x1fff+len(image))==backup,'Unstable RAM backup'
   c.save(folder/'RAM-escrow.json',dict(sha256=hashlib.sha256(backup).hexdigest(),start=0x2000,bytes=len(backup),two_matching_reads=True))
   m=c.read(marker_path);m.update(one_shot_collection_active=True,application_RAM_restore_pending=True,block_snapshot=True,RTC_LED_RAM_escrow=str(folder));c.save(marker_path,m);borrowed=True
   stage(link,image)
   refs=[]
   for n in range(3):
    if n:time.sleep(4)
    refs.append(b.ntp_sample('132.163.96.6'))
   ref=b.Reference(refs);uncertainty=ref.uncertainty+.002 # bounded 62-second reference aging
   r.update(reference_samples=refs,reference_uncertainty_s=uncertainty);save()
   running=True;r['LED_restored']=False;link.send(b'G 2000\r');started=time.monotonic()
   while time.monotonic()-started<duration:
    cycle=time.monotonic();token,_=f.until_any(link,[b'!',b'%'],15)
    if token==b'%':
     receipt=exact(link,6);link.until(f.MON,seconds=15);running=False
     r['LED_exit_receipt']=list(receipt);r['LED_restored']=receipt[0]==0 and receipt[4]==receipt[5]
     raise ValueError('LED direction/control admission refused; no LED output changed')
    phase=int(time.monotonic()*10)&1;start=ref.now();link.send(b's' if phase else b'r')
    link.until(b'@',seconds=15);packet=exact(link,20);end=ref.now()
    assert packet[0]==0,'RTC/LED agent refused: '+hex(packet[0])
    raw=packet[1:18];stamp=decode(raw);second=raw[0]&127
    expected=(15 if phase else 240) if second==0 else second
    assert packet[-1]==expected,'LED latch verification failed'
    assert datetime.fromtimestamp(stamp,timezone.utc).date()==datetime.fromtimestamp(end,timezone.utc).date(),'Calendar mismatch'
    row=dict(rtc_unix=stamp,rtc_utc=datetime.fromtimestamp(stamp,timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),raw=list(raw),reference_start_unix=start,reference_end_unix=end,rtc_minus_reference_interval_s=[stamp-end-uncertainty,stamp+1-start+uncertainty],trim_raw=raw[8],trim_steps=(raw[8]&127)*(1 if raw[8]&128 else -1),control_register=raw[7],PF_latched=bool(raw[3]&16),led_entry=packet[-2],led_value=packet[-1],flash_phase=phase)
    rows.append(row)
    with (folder/'observations.jsonl').open('a') as obs:obs.write(json.dumps(row)+'\n')
    time.sleep(max(0,.1-(time.monotonic()-cycle)))
   assert len(rows)>=9 and rows[-1]['rtc_unix']-rows[0]['rtc_unix']>=60,'Incomplete minute observation'
   assert len({(x['trim_raw'],x['control_register']) for x in rows})==1,'Trim/control changed'
   zeros={x['led_value'] for x in rows if x['raw'][0]&127==0}
   assert zeros=={15,240},'Both zero-second flash phases not observed'
   last=b.ntp_sample('132.163.96.6');difference=last['host_receive_unix']+last['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+last['receive_monotonic']-ref.best['receive_monotonic'])
   assert abs(difference)<=uncertainty+last['estimated_reference_uncertainty_s'],'Reference shifted'
   readings=[rows[round(i*(len(rows)-1)/8)] for i in range(9)]
   lo=max(x['rtc_minus_reference_interval_s'][0] for x in readings);hi=min(x['rtc_minus_reference_interval_s'][1] for x in readings);assert lo<=hi
   live=rows[-1];t=(live['reference_start_unix']+live['reference_end_unix'])/2
   r.update(readings=readings,observation_count=len(rows),rtc_minus_reference_interval_s=[lo,hi],baseline_reference_unix=t,baseline_reference_utc=b.iso(t),trim_steps=live['trim_steps'],trim_raw=live['trim_raw'],control_register=live['control_register'],coarse_trim=bool(live['control_register']&4),PF_latched=any(x['PF_latched'] for x in rows),final_reference_check=last,final_reference_difference_s=difference,zero_flash_verified=True,acquisition_passed=True)
  except Exception as e:r['error']=repr(e)
  finally:
   if link:
    try:
     if running:
      # Exit before any RAM restoration. On a transport failure keep the
      # restoration-pending guard instead of issuing writes to a running app.
      link.until(b'!',seconds=15);link.send(b'q');link.until(b'%',seconds=15);receipt=exact(link,6);link.until(f.MON,seconds=15);running=False
      r['LED_exit_receipt']=list(receipt);assert receipt[0]==1 and receipt[2]==receipt[3] and receipt[4]==receipt[5],'LED/CRA restoration failed'
      r['LED_restored']=True
     if borrowed:
      assert not running and r['LED_restored'],'Restore LEDs before releasing RAM'
      stage(link,backup);restored=f.dump_ram(link,0x2000,0x1fff+len(backup));(folder/'RAM-restored.bin').write_bytes(restored);assert restored==backup
      r['application_ram_restored']=True
      m=c.read(marker_path)
      for key in ('one_shot_collection_active','application_RAM_restore_pending','block_snapshot','RTC_LED_RAM_escrow'):
       if key in previous:m[key]=previous[key]
       else:m.pop(key,None)
      c.save(marker_path,m)
     if original==f.REC:link.command('Q',f.REC)
     r['returned_to_original_prompt']=original is not None
    except Exception as e:r['restoration_error']=repr(e)
    link.serial.close();r['port_released']=True
   if log:log.close()
   r.update(passed=bool(r.get('acquisition_passed') and r['LED_restored'] and r['application_ram_restored'] and r['returned_to_original_prompt'] and r['port_released'] and not r.get('restoration_error')),finished_utc=c.NOW());save()
 return r
def audit_board(item,state):
 p=Path(item['report']);r=c.read(p);folder=p.parent;image,proof=load()
 assert item['board']=='2512'
 assert c.sha(p)==item['sha256'] and r['passed'] and r['driver_sha256']==c.sha(__file__)
 assert r['image_sha256']==proof['image_sha256'] and r['capture_profile']==PROFILE
 assert r['usb_serial']==f.IDS[item['board']]
 if item['board'] in ('2512','2609'):
  version=(folder/'VERSION.txt').read_bytes();assert (b'65C816' if item['board']=='2609' else b'65C02') in version and b'  gen 00000010' in version
 else:assert (folder/'CPU-descriptor.bin').read_bytes()[1]==2 and (folder/'ABI-descriptor.bin').read_bytes()==b'RA\x01\x0d'
 assert all(r[x] for x in ['LED_restored','application_ram_restored','returned_to_original_prompt','port_released','zero_flash_verified'])
 assert not any(r[x] for x in ['clock_set_attempted','trim_changed','flash_written','PF_ACK','PF_history_written'])
 assert (folder/'RAM-before.bin').read_bytes()==(folder/'RAM-restored.bin').read_bytes()
 receipt=r['LED_exit_receipt'];assert receipt[0]==1 and receipt[1]==0 and receipt[2]==receipt[3] and receipt[4]==receipt[5]
 rows=[json.loads(x) for x in (folder/'observations.jsonl').read_text().splitlines()]
 assert len(rows)==r['observation_count'] and rows[-1]['rtc_unix']-rows[0]['rtc_unix']>=60
 for x in rows:
  assert decode(bytes(x['raw']))==x['rtc_unix']
  sec=x['raw'][0]&127;assert x['led_value']==((15 if x['flash_phase'] else 240) if sec==0 else sec)
 assert {x['led_value'] for x in rows if x['raw'][0]&127==0}=={15,240}
 assert r['readings']==[rows[round(i*(len(rows)-1)/8)] for i in range(9)]
 for x in r['readings']:
  assert x['rtc_minus_reference_interval_s']==[x['rtc_unix']-x['reference_end_unix']-r['reference_uncertainty_s'],x['rtc_unix']+1-x['reference_start_unix']+r['reference_uncertainty_s']]
 assert len(r['reference_samples'])==3 and all(x['stratum']==1 for x in r['reference_samples']+[r['final_reference_check']])
 assert abs(r['final_reference_difference_s'])<=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s']
 lo,hi=r['rtc_minus_reference_interval_s'];assert lo<=hi and lo==max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']) and hi==min(x['rtc_minus_reference_interval_s'][1] for x in r['readings'])
 # Audit exact serial commands and bound every S1 write to saved RAM.
 entries=[bytes.fromhex(x['hex']) for x in map(json.loads,(folder/'serial.jsonl').read_text().splitlines()) if x['direction']=='TX']
 loads=[];cells=None;m_cells={};m_loads=[]
 for x in entries:
  v=x.rstrip(b'\r\n')
  assert v in [b'',b'B',b'Q',b'V',b'L',b'G 2000',b'r',b's',b'q'] or re.fullmatch(rb'D [0-9A-F]{4} [0-9A-F]{4}',v) or re.fullmatch(rb'S[019][0-9A-F]+',v) or re.fullmatch(rb'M [0-9A-F]{4}(?: [0-9A-F]{2}){1,8}',v),(v,'unexpected command')
  if v.startswith(b'M '):
   assert item['board'] in ('2512','2609'),'M forbidden on legacy boards'
   parts=v.split();addr=int(parts[1],16);data=bytes.fromhex(b' '.join(parts[2:]).decode())
   assert 0x2000<=addr and addr+len(data)<=0x2000+len(image)
   for n,value in enumerate(data,addr):assert n not in m_cells;m_cells[n]=value
   if len(m_cells)==len(image):m_loads.append(bytes(m_cells[n] for n in sorted(m_cells)));m_cells={}
  if v.startswith(b'S1'):
   body=bytes.fromhex(v[2:].decode());addr=int.from_bytes(body[1:3],'big');assert sum(body)&255==255 and 0x2000<=addr and addr+len(body)-4<=0x2000+len(image)
   assert cells is not None and body[0]==len(body)-1
   for n,value in enumerate(body[3:-1],addr):assert n not in cells;cells[n]=value
  elif v==b'L':assert cells is None;cells={}
  elif v.startswith(b'S9'):
   body=bytes.fromhex(v[2:].decode());assert sum(body)&255==255 and int.from_bytes(body[1:3],'big')==0x2000
   assert cells is not None and set(cells)==set(range(0x2000,0x2000+len(image)))
   loads.append(bytes(cells[n] for n in sorted(cells)));cells=None
  if v.startswith(b'D '):
   _,start,end=v.split();first,last=int(start,16),int(end,16)
   assert 0x2000<=first<=last<0x2000+len(image) or (first,last) in [(0x7d00,0x7d3f),(0x7e60,0x7e63)]
 assert cells is None and not m_cells and (loads or m_loads)==[image,(folder/'RAM-before.bin').read_bytes()],'Uploaded/restored RAM differs from proof'
 assert not (loads and m_loads),'Mixed loading transports'
 commands=[x.rstrip(b'\r\n') for x in entries]
 assert commands.count(b'G 2000')==1 and commands.count(b'q')==1
 assert sum(x in [b'r',b's'] for x in commands)==len(rows)
 return dict(board=item['board'],time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,offset=(lo+hi)/2,trim=r['trim_steps'],control=r['control_register'],trim_verified=True,control_verified=True,PF_history_freshly_read=False,PF_latched=r['PF_latched'],active_PF_records=None,events=[],report=str(p),report_sha256=c.sha(p),capture_profile=PROFILE)
def campaign(state,admitted,skipped):
 run=Path(state['root'])/'captures'/datetime.now(timezone.utc).strftime('%Y%m%d/batch-%H%M%SZ');run.mkdir(parents=True)
 summary=dict(passed=False,started_utc=c.NOW(),boards=[],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
 issues=list(skipped);points=c.read(Path(state['root'])/'points.json')
 for board in admitted:
  try:r=collect(board,run/board)
  except TimeoutError:
   # Foreground leases are quiet deferrals; controller reschedules the board.
   raise
  if not r['passed']:summary['failures'].append(dict(board=board,error=r.get('restoration_error',r.get('error','LED collection failed')),report=str(run/board/'report.json')))
  else:
   item=dict(board=board,report=str(run/board/'report.json'),sha256=c.sha(run/board/'report.json'),offset=r['rtc_minus_reference_interval_s'],trim=r['trim_steps'],RAM_restored=True,capture_profile=PROFILE)
   try:
    point=audit_board(item,state);points.append(point);summary['boards'].append(item)
    if point['PF_latched']:issues.append(dict(board=board,error='Native TIME reports PF latched; no ACK sent'))
   except Exception as e:summary['failures'].append(dict(board=board,error=repr(e),report=item['report']))
  summary.update(passed=not summary['failures'],finished_utc=c.NOW());c.save(run/'summary.json',summary)
  print(board,'PASS' if r['passed'] else 'FAIL',r.get('error',''),flush=True)
 issues+=summary['failures'];c.save(Path(state['root'])/'points.json',points)
 c.save(run/'campaign-audit.json',dict(passed=not issues,issues=issues,new_PF_events=[],summary_sha256=c.sha(run/'summary.json')))
 # Reload state so intervening owner metadata is not overwritten.
 latest=c.read(c.STATE);latest.update(last_attempt_utc=c.NOW(),last_summary=str(run/'summary.json'),last_issues=issues,last_new_PF_events=[]);c.save(c.STATE,latest);c.report(latest)
 print('LED_COLLECTION_RESULT',run,flush=True)
def enabled(state):
 if not CONFIG.exists():return False
 cfg=c.read(CONFIG)
 if not cfg.get('enabled'):return False
 assert cfg['profile']==PROFILE and cfg['driver_sha256']==c.sha(__file__) and cfg['image_sha256']==IMAGE_SHA,'LED collector configuration differs from qualification'
 summary=Path(cfg['qualification_summary']);assert c.sha(summary)==cfg['qualification_summary_sha256']
 q=c.read(summary);assert q['passed'] and not q['failures'] and {r['board'] for r in q['boards']}==set(c.BOARDS)
 for item in q['boards']:assert item['capture_profile']==PROFILE and item['RAM_restored']
 load();return True
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--board',action='append',choices=['2512']);args=p.parse_args();state=c.read(c.STATE)
 assert state['active'] and not state.get('owner_stopped')
 campaign(state,list(dict.fromkeys(args.board or ['2512'])),[])
