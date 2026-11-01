"""Measure RTC tick phase and explicitly correct it with bounded temporary RAM code."""
import argparse,hashlib,json,math,socket,struct,time,statistics
from datetime import datetime,timezone
from pathlib import Path
import rtc_fleet as f
from rtc_phase_contract import DEFAULT_BUILD, load_image
ROOT=f.ROOT;BUILD=DEFAULT_BUILD
IMAGE=b'';SY={};PROOF={}

def ntp_once(server):
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  sock.settimeout(5);sock.connect((server,123));req=bytearray(48);req[0]=0x23
  stamp=time.time()+2208988800;sec=int(stamp);struct.pack_into('!II',req,40,sec,int((stamp-sec)*2**32))
  a=time.perf_counter();sock.send(req);packet=sock.recv(512);b=time.perf_counter()
 if len(packet)<48 or packet[0]&7!=4 or packet[0]>>6==3 or not 1<=packet[1]<=15 or packet[24:32]!=req[40:48]:raise ValueError('Invalid/unsynchronized NTP response')
 def ts(n):
  x,y=struct.unpack_from('!II',packet,n);return x-2208988800+y/2**32
 t2,t3=ts(32),ts(40)
 if not 0<=t3-t2<=b-a or b-a>.3:raise ValueError('NTP exchange too slow/inconsistent')
 extra=struct.unpack_from('!I',packet,8)[0]/65536+max(0,struct.unpack_from('!i',packet,4)[0]/65536)/2+.002
 return dict(server=server,send_perf=a,receive_perf=b,server_receive=t2,server_transmit=t3,origin_bounds=[t3-b-extra,t2-a+extra],packet_hex=packet.hex())

class Reference:
 def __init__(self,samples):
  self.samples=samples;self.low=max(s['origin_bounds'][0] for s in samples);self.high=min(s['origin_bounds'][1] for s in samples);self.created=time.perf_counter()
  if self.low>self.high or self.high-self.low>.10:raise ValueError('NIST references inconsistent or exceed 50 ms half-width')
  self.origin=(self.low+self.high)/2
 def now(self):return time.perf_counter()+self.origin
 @property
 def uncertainty(self):return (self.high-self.low)/2+.000020*(time.perf_counter()-self.created)

def reference(server,count=5):
 samples=[]
 for n in range(count):
  if n:time.sleep(4.05)
  samples.append(ntp_once(server))
 return Reference(samples)

def exact(link,count):
 deadline=time.perf_counter()+15
 while len(link.pending)<count:
  if time.perf_counter()>deadline:raise TimeoutError('Incomplete phase reply')
  link.pending.extend(link.read(max(1,link.serial.in_waiting)))
 result=bytes(link.pending[:count]);del link.pending[:count];return result

def receive_packet(link):
 link.until(b'@',seconds=15);packet=exact(link,18)
 if packet[0]:raise RuntimeError('RAM phase routine status '+hex(packet[0]))
 return packet[1:]

def run_agent(link,entry,ref,phase_mid=None,add_seconds=0):
 link.send(f'G {entry:04X}\r'.encode());link.until(b'!',seconds=15)
 if phase_mid is not None:
  tick=math.ceil(ref.now()+phase_mid)-phase_mid;
  if add_seconds and int(round(tick+phase_mid))%60==59:tick+=1
  f.wait_deadline(ref,tick+.04)
 start=ref.now();link.send(b'r');raw=receive_packet(link);end=ref.now();link.until(f.MON,seconds=15)
 return start,end,raw

def stage(link,address,data):
 if not data or address<0x2000 or address+len(data)>0x2000+len(IMAGE):raise ValueError('Write outside borrowed phase RAM block')
 if getattr(link,'phase_board',None)=='2604':
  # Use the existing qualified g0034 S-record transport, never its M route.
  from installer.engine.legacy_transport import s19
  body=s19(dict(enumerate(data,address)),address)
  link.command('L',b'S19')
  for line in body.splitlines():link.send(line+b'\r\n');time.sleep(.04)
  reply=link.until(f.MON,seconds=45)
  if any(x in reply for x in (b'Bad',b'error',b'REFUSED',b'Protected')):raise ValueError('S-record RAM load refused')
  if f.dump_ram(link,address,address+len(data)-1)!=data:raise ValueError('S-record RAM readback mismatch')
  return
 for n in range(0,len(data),8):
  reply=link.command(f'M {address+n:04X} '+' '.join(f'{v:02X}' for v in data[n:n+8]),f.MON)
  if any(x in reply for x in (b'REFUSED',b'Bad',b'Protected',b'Invalid',b'Long line',b'Wrap',b'Range',b'Error')):raise ValueError('RAM staging refused')
 if f.dump_ram(link,address,address+len(data)-1)!=data:raise ValueError('RAM staging readback mismatch')

def decode(raw):
 def bcd(x):
  if x&15>9 or (x>>4)>9:raise ValueError('Invalid RTC BCD')
  return (x>>4)*10+(x&15)
 return datetime(2000+bcd(raw[6]),bcd(raw[5]&31),bcd(raw[4]&63),bcd(raw[2]&63),bcd(raw[1]&127),bcd(raw[0]&127),tzinfo=timezone.utc).timestamp()

def measure(link,ref,expected=None,count=200):
 readings=[];last=None
 link.send(f"G {SY['OBSERVE']:04X}\r".encode())
 try:
  for n in range(count):
   link.until(b'!',seconds=15);a=ref.now();link.send(b'r');raw=receive_packet(link);b=ref.now()
   if raw[0]&128==0 or raw[3]&0x30!=0x20:raise ValueError('Stopped RTC or PF latch; preserve evidence')
   if expected is not None and (raw[7:9]!=expected[7:9] or raw[9:]!=expected[9:]):raise ValueError('Trim/control or PF timestamps changed')
   value=decode(raw);unc=ref.uncertainty
   readings.append(dict(start=a,end=b,rtc=value,low=value-b-unc,high=value+1-a+unc,raw=raw.hex()));last=raw
 finally:
  link.until(b'!',seconds=15);link.send(b'q');link.until(f.MON,seconds=15)
 lo=max(x['low'] for x in readings);hi=min(x['high'] for x in readings)
 if lo>hi or len(set(x['rtc'] for x in readings))<3:raise ValueError('Inconsistent tick observations')
 return dict(low=lo,high=hi,mid=(lo+hi)/2,readings=readings),last

def calibrate(link,ref):
 runs=[]
 for ticks in (1000,4000,1000,4000,1000,4000):
  stage(link,SY['TICKS'],ticks.to_bytes(2,'little'));a,b,_=run_agent(link,SY['CALIBRATE'],ref);runs.append((ticks,b-a))
 slope=(statistics.median(d for n,d in runs if n==4000)-statistics.median(d for n,d in runs if n==1000))/3000
 if not .000025<slope<.001:raise ValueError('CPU delay calibration out of range')
 return slope,runs

def board_run(board,case,args,validation):
 from installer.engine.legacy_transport import Link
 from serial.tools.list_ports import comports
 case.mkdir();r=dict(board=board,borrowed_RAM_range='2000-2434',zero_page_storage_used=False,passed=False,phase_requested=args.align_ticks,corrections=[],clock_write=False,trim_changed=False,PF_ACK=False,EEPROM_written=False,flash_written=False,owner_RAM_restored=False)
 def save():f.save(case/'report.json',r)
 save();link=None;log=None;original=None;backup=None;borrowed=False;marker_path=f.campaign.Q/f'device-operations/{board}.json';previous=None
 try:
  previous=f.admission(board);ports=[p.device for p in comports() if p.serial_number==f.IDS[board]]
  if len(ports)!=1:raise ValueError('USB unavailable/ambiguous')
  log=(case/'serial.jsonl').open('x');link=Link(ports[0],log);link.phase_board=board;link.send(b'\r');_,face=f.until_any(link,[b'> '],15)
  original=f.MON if face.endswith(f.MON) else f.REC if face.endswith(f.REC) else None
  if original is None:raise ValueError('Leave active application alone')
  if original==f.REC:link.command('B',f.MON)
  backup=f.dump_ram(link,0x2000,0x1fff+len(IMAGE));(case/'RAM-before.bin').write_bytes(backup)
  if f.dump_ram(link,0x2000,0x1fff+len(IMAGE))!=backup:raise ValueError('RAM backup unstable')
  marker=f.campaign.read(marker_path);marker.update(one_shot_collection_active=True,application_RAM_restore_pending=True,block_snapshot=True);f.campaign.save(marker_path,marker);borrowed=True
  stage(link,0x2000,IMAGE)
  ref=reference(args.server);r['NIST_samples']=ref.samples;r['NIST_uncertainty_s']=ref.uncertainty;save()
  slope,runs=calibrate(link,ref);r.update(seconds_per_tick=slope,calibration_runs=runs);save()
  before,raw=measure(link,ref);r['before']=before;r['before_raw']=raw.hex();r['EUI_guard']='Exact USB serial and current admitted profile';save()
  if raw[7]&0x30:raise ValueError('Alarms enabled; phase adjustment refused')
  current=before
  if args.align_ticks:
   if board not in validation:raise ValueError('Board lacks fresh successful phase validation')
   response_bias=0.0
   for attempt in range(5):
    if current['low']>=-args.tolerance and current['high']<=args.tolerance:break
    if current['high']-current['low']>2*args.tolerance:raise ValueError('Measurement bounds too wide for requested accuracy')
    mid=current['mid']
    if not -0.8<mid<1.05:raise ValueError('Calendar error outside phase correction range; explicit calendar SET needed')
    add=1 if mid-response_bias<=.005 else 0;hold=mid+add-response_bias
    if not .005<hold<1.05:raise ValueError('Unresolvable correction duration')
    ticks=round(hold/slope)
    if not 1<=ticks<0x4000:raise ValueError('Delay count out of bounds')
    stage(link,SY['EXPECTED'],raw[7:9]);stage(link,SY['ADJUST'],bytes([add]));stage(link,SY['TICKS'],ticks.to_bytes(2,'little'));stage(link,SY['KEY'],b'PH')
    target=ref.now()
    state=f.campaign.read(f.campaign.STATE)
    state.setdefault('clock_sync_operations',[]).append(dict(board=board,UTC=f.campaign.NOW(),operation='bounded RTC tick phase correction',receipt=str(case/'report.json'),owner_authorization='Improve the program to get all four clocks much closer to NIST, with the second ticks lined up',status='intent; inspect receipt'))
    state.setdefault('segment_boundaries',{})[board]=dict(time=target,UTC=datetime.fromtimestamp(target,timezone.utc).isoformat(),reason='Owner-authorized RTC tick phase correction; never fit across adjustment',report=str(case/'report.json'))
    f.campaign.save(f.campaign.STATE,state)
    correction=dict(estimated_offset_s=mid,requested_hold_s=hold,response_bias_s=response_bias,ticks=ticks,add_seconds=add,started_UTC=datetime.fromtimestamp(target,timezone.utc).isoformat(),status='intent')
    r['corrections'].append(correction);r['clock_write']=True;save()
    a,b,afterraw=run_agent(link,SY['PAUSE_CLOCK'],ref,phase_mid=mid,add_seconds=add);correction.update(start=a,end=b,status='completed')
    current,afterraw=measure(link,ref,raw);correction['after']=current
    response_bias=mid+add-hold-current['mid'];correction['observed_response_bias_s']=response_bias;save()
    if not -.05<=response_bias<=.35:raise ValueError('Unstable RTC phase response; no further correction')
   if current['low']< -args.tolerance or current['high']>args.tolerance:raise ValueError('Tick alignment did not meet requested tolerance; bounded corrections exhausted')
  final=ntp_once(args.server);r['NIST_final']=final
  if max(ref.low,final['origin_bounds'][0])>min(ref.high,final['origin_bounds'][1])+.002:raise ValueError('NIST reference shifted during run')
  r.update(after=current,passed=True,accuracy_verified=args.align_ticks,trim_control_unchanged=True,PF_timestamps_preserved=True,PF_latched=False)
 except Exception as e:r['error']=repr(e)
 finally:
  if link:
   try:
    if borrowed and backup is not None:
     stage(link,0x2000,backup);restored=f.dump_ram(link,0x2000,0x1fff+len(IMAGE));(case/'RAM-restored.bin').write_bytes(restored)
     if restored!=backup:raise ValueError('Original RAM restoration mismatch')
     r['owner_RAM_restored']=True
     marker=f.campaign.read(marker_path)
     for key in ('one_shot_collection_active','application_RAM_restore_pending','block_snapshot'):
      if key in previous:marker[key]=previous[key]
      else:marker.pop(key,None)
     f.campaign.save(marker_path,marker)
    if original==f.REC:link.command('Q',f.REC)
    r['original_prompt_restored']=original is not None
   except Exception as e:r['restoration_error']=repr(e);r['passed']=False
   link.serial.close()
  if log:log.close()
  r['finished_UTC']=f.campaign.NOW();save()
 print(board,'PASS' if r['passed'] else 'FAIL',json.dumps({k:r.get(k) for k in ('error','restoration_error','after','owner_RAM_restored')})[:180],flush=True)
 return r

def main(argv=None):
 global IMAGE,SY,PROOF
 p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--align-ticks',action='store_true');mode.add_argument('--check-phase',action='store_true');p.add_argument('--board',action='append',choices=f.IDS);p.add_argument('--server',default='132.163.96.6');p.add_argument('--tolerance',type=float,default=.100);p.add_argument('--phase-validation',type=Path);p.add_argument('--build',type=Path,default=BUILD);args=p.parse_args(argv)
 if not .05<=args.tolerance<=.15:raise ValueError('Tolerance must be 50..150 ms')
 IMAGE,SY,PROOF=load_image(args.build)
 boards=list(dict.fromkeys(args.board or f.IDS));validated=set()
 if args.align_ticks:
  if not args.phase_validation or time.time()-args.phase_validation.stat().st_mtime>3600:raise ValueError('Fresh --check-phase summary required')
  proof=json.loads(args.phase_validation.read_text())
  if proof.get('image_sha256')!=PROOF['image_sha256']:raise ValueError('Phase validation used a different RAM image')
  validated={r['board'] for r in proof['boards'] if r['passed'] and not r['phase_requested'] and r['owner_RAM_restored'] and r.get('original_prompt_restored')}
  if not set(boards)<=validated:raise ValueError('Every selected board must pass phase validation')
 out=f.campaign.Q/datetime.now(timezone.utc).strftime('rtc-phase-%Y%m%dT%H%M%SZ');out.mkdir();(out/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes());rows=[]
 with f.serial_lease('drift',timeout=30):
  for b in boards:
   rows.append(board_run(b,out/b,args,validated));f.save(out/'summary.json',dict(passed=all(r['passed'] for r in rows),boards=rows,image_sha256=PROOF['image_sha256'],tolerance_s=args.tolerance))
  if args.align_ticks:
   f.collect(boards);state=f.campaign.read(f.campaign.STATE);points=f.campaign.read(Path(state['root'])/'points.json')
   for r in rows:
    if r['clock_write']:
     ps=[x for x in points if x['board']==r['board'] and x['time']>=datetime.fromisoformat(r['finished_UTC']).timestamp()]
     if ps:
      f.rebase(state,r['board'],max(ps,key=lambda x:x['time']),str(out/r['board']/'report.json'),'Owner-authorized tick phase alignment')
   f.campaign.save(f.campaign.STATE,state);f.campaign.report(state)
 print('PHASE_REPORT',out,flush=True)
 if not all(r['passed'] for r in rows):raise SystemExit(1)
if __name__=='__main__':main()
