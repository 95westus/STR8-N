"""Fleet RTC collection, calendar setting and measured NIST tick alignment.

Use --check-phase followed by --align-ticks for precise tick alignment.
The older --sync command sets the whole calendar through CLOCK only.

Sync drives installed CLOCK applications. Their normal app RAM is backed up to
disk before entry; CLOCK remains loaded in app RAM when returning to MON.
No flash, EEPROM, SRAM configuration, trim, reset, or host-clock writes.
"""
import argparse,json,math,re,sys,time,statistics
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tmp/migration-python')]
import rtc_drift_campaign as campaign
from serial_test_coordination import serial_lease
IDS={'2205':'A10MPUPNA','2512':'A10MQFLCA','2604':'A10MQGVHA','2609':'A10MPQXCA'}
MON=b'B3> ';REC=b'REC> ';CLOCK=b'CLOCK> ';CONFIRM=b'Type YES to confirm: '
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def calendar(body):
 m=re.search(rb'(?:UTC:\s+(?:[A-Za-z]{3} )?|Calendar \(UTC convention\):\s+)(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d)',body)
 if not m:raise ValueError('Missing UTC calendar')
 return datetime.strptime(m[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()
def raw_status(body):
 m=re.search(rb'RTC registers \(raw\):((?: [0-9A-F]{2}){9})',body)
 if not m:raise ValueError('Missing fresh RTC register status')
 return bytes.fromhex(m[1].decode())
def dump_ram(link,first,last):
 body=link.command(f'D {first:04X} {last:04X}',MON)
 cells={}
 for line in body.decode('ascii').splitlines():
  m=re.match(r'^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})(?:$| )',line.strip())
  if m:
   for i,v in enumerate(bytes.fromhex(m[2])):
    a=int(m[1],16)+i
    if first<=a<=last:
     assert a not in cells,'Duplicate dump address'
     cells[a]=v
 assert set(cells)==set(range(first,last+1)),'Incomplete memory readback'
 return bytes(cells[a] for a in range(first,last+1))

def until_any(link,tokens,seconds=30):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  for token in tokens:
   n=link.pending.find(token)
   if n>=0:
    n+=len(token);body=bytes(link.pending[:n]);del link.pending[:n];return token,body
  link.pending.extend(link.read(max(1,link.serial.in_waiting)))
 raise TimeoutError('Unrecognized/incomplete reply: '+repr(bytes(link.pending[-180:])))
def menu(link):
 token,body=until_any(link,[CLOCK,b'Local UTC offset +/-HH:MM (Enter keeps +00:00): '])
 if token!=CLOCK:
  link.send(b'\r');body+=link.until(CLOCK,seconds=15)
 return body
def admission(board):
 state=campaign.read(campaign.STATE);assert state['active'] and not state.get('owner_stopped')
 m=campaign.read(campaign.Q/f'device-operations/{board}.json')
 assert not any(v for k,v in m.items() if k.endswith('_worker_active')),'Board worker busy'
 assert not any(m.get(k) for k in ('application_RAM_restore_pending','physical_reset_pending','owner_application_running','one_shot_collection_active')),'Board not idle'
 assert {k:m.get(k) for k in state['board_admission'][board]}==state['board_admission'][board],'Profile changed'
 return m
def reference(server):
 from rtc_base1_collect import ntp_sample,Reference
 ss=[]
 for n in range(3):
  if n:time.sleep(4)
  ss.append(ntp_sample(server))
 r=Reference(ss);assert r.uncertainty<=.15,'NIST reference uncertainty exceeds 150 ms; no SET'
 # Bridge the existing NIST anchor to the high-resolution performance clock.
 # Include Windows monotonic quantization/bridge error in the reported bounds.
 anchor=r.now();counter=time.perf_counter();r.uncertainty+=.020
 r.now=lambda:anchor+time.perf_counter()-counter
 return r,ss
def wait_deadline(ref,deadline):
 while True:
  remain=deadline-ref.now()
  if remain<=0:return
  if remain>.004:time.sleep(min(.02,remain-.002))
def boundary(board,case,target):
 s=campaign.read(campaign.STATE);s.setdefault('clock_sync_operations',[]).append(dict(board=board,UTC=campaign.NOW(),target_UTC=datetime.fromtimestamp(target,timezone.utc).isoformat(),receipt=str(case/'report.json'),owner_authorization='Synchronize all four once after validation',status='intent; inspect receipt for result'))
 s.setdefault('segment_boundaries',{})[board]=dict(time=target,UTC=datetime.fromtimestamp(target,timezone.utc).isoformat(),reason='Owner-authorized UTC synchronization; never fit across clock adjustment',report=str(case/'report.json'))
 campaign.save(campaign.STATE,s)
def operate(board,case,args):
 from installer.engine.legacy_transport import Link
 from serial.tools.list_ports import comports
 case.mkdir();r=dict(board=board,passed=False,sync_requested=args.sync,set_trigger_sent=False,clock_set_verified=False,trim_changed=False,PF_ACK=False,flash_written=False,history_clear=False,app_RAM_restored=False,readings=[])
 def checkpoint():save(case/'report.json',r)
 checkpoint();link=None;log=None;original=None;context=None;confirmation=False
 try:
  admission(board);ports=[p.device for p in comports() if p.serial_number==IDS[board]];assert len(ports)==1,'USB identity unavailable/ambiguous'
  ref,refs=reference(args.server);r.update(reference_samples=refs,reference_uncertainty_s=ref.uncertainty)
  log=(case/'serial.jsonl').open('x')
  link=Link(ports[0],log);link.send(b'\r');_,face=until_any(link,[b'> '],15)
  original=next((p for p in (MON,REC,CLOCK) if face.endswith(p)),None);assert original,'Active application: leave it alone'
  context=original;r['original_prompt']=original.decode().strip()
  if original==REC:link.command('B',MON);context=MON
  if context==MON:
   if args.sync or args.check_interface:
    # Preserve app memory before loading the ordinary installed CLOCK app.
    ram=bytearray()
    for a in range(0x200,0x6700,0x800):ram.extend(dump_ram(link,a,min(a+0x7ff,0x66ff)))
    (case/'app-RAM-before.bin').write_bytes(ram);(case/'ZP-before.bin').write_bytes(dump_ram(link,0,0xdf));r['app_RAM_backup']=str(case/'app-RAM-before.bin');checkpoint()
   link.send(b'R CLOCK\r');context=CLOCK;entry=menu(link);(case/'CLOCK-entry.txt').write_bytes(entry)
   assert b'CLOCK ' in entry and b'Services unavailable' not in entry
  helpface=link.command('HELP',CLOCK);assert b'SET yyyy-mm-dd hh:mm:ss' in helpface
  before=link.command('STATUS',CLOCK);hist=link.command('HISTORY',CLOCK)
  (case/'before-status.txt').write_bytes(before);(case/'before-history.txt').write_bytes(hist)
  raw=raw_status(before);r['before_control_trim_hex']=raw[7:9].hex()
  assert b'Power-fail latched: no' in before,'PF evidence latched: preserve it; no SET'
  assert b'Calendar valid: yes' in before and b'Running: yes' in before
  assert not raw[7]&0x30,'Enabled alarms: no SET'
  # Command-response RTT is only a transport estimate, not a proven SET latency.
  delays=[]
  for n in range(5):
   t=ref.now();link.command('',CLOCK);delays.append(ref.now()-t)
  lead=args.lead_ms/1000 if args.lead_ms is not None else min(delays)/2
  assert 0<=lead<=.25
  r.update(prompt_round_trip_s=delays,estimated_trigger_lead_s=lead,lead_method='explicit calibrated lead' if args.lead_ms is not None else 'half minimum prompt RTT; SET execution delay not measured')
  if args.sync:
   target=math.ceil(ref.now()+12);cmd='SET '+datetime.fromtimestamp(target,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
   link.send(cmd.encode()+b'\r');confirmation=True;confirm=link.until(CONFIRM,seconds=15);(case/'SET-confirmation.txt').write_bytes(confirm)
   assert b'SET changes UTC' in confirm and datetime.fromtimestamp(target,timezone.utc).strftime('%Y-%m-%d %H:%M:%S').encode() in confirm
   assert target-ref.now()>2,'Missed preparation deadline; cancel without SET'
   r.update(target_unix=target,target_UTC=datetime.fromtimestamp(target,timezone.utc).isoformat());boundary(board,case,target);checkpoint()
   link.send(b'YES');link.until(b'YES',seconds=5)
   assert ref.now()<target-lead,'Late trigger preparation; cancel without SET'
   wait_deadline(ref,target-lead);r['trigger_reference_before_s']=ref.now();r['set_trigger_sent']=True
   # Only the final Enter is released at the chosen second boundary.
   assert link.serial.write(b'\r')==1
   link.serial.flush();r['trigger_reference_after_s']=ref.now();link.record('TX',b'\r');confirmation=False;checkpoint()
   result=menu(link);(case/'SET-result.txt').write_bytes(result)
   assert b'SET completed.' in result and b'SET failed' not in result,'SET outcome uncertain; never retry automatically'
   r['clock_set_verified']=True;checkpoint()
  # Varied/persistent TIME reads bracket whole-second phase without claiming
  # that a single displayed integer timestamp provides subsecond accuracy.
  for n in range(40 if args.sync else 9):
   start=ref.now();body=link.command('TIME',CLOCK);end=ref.now();rtc=calendar(body)
   r['readings'].append(dict(rtc_unix=rtc,reference_start=start,reference_end=end,offset_bounds_s=[rtc-end-ref.uncertainty,rtc+1-start+ref.uncertainty]));checkpoint();time.sleep(.031+(n%5)*.017)
  after=link.command('STATUS',CLOCK);hist2=link.command('HISTORY',CLOCK);(case/'after-status.txt').write_bytes(after);(case/'after-history.txt').write_bytes(hist2)
  assert calendar(b'UTC:   Sun 2026-11-01 00:00:00')==1793491200
  assert raw_status(after)[7:9]==raw[7:9],'Control/trim changed'
  assert b'Power-fail latched: no' in after
  # With the latch clear before SET, no journal append/ACK is expected.
  assert hist2==hist,'PF history changed'
  from rtc_base1_collect import ntp_sample
  check=ntp_sample(args.server);difference=check['host_receive_unix']+check['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+check['receive_monotonic']-ref.best['receive_monotonic'])
  assert abs(difference)<=ref.uncertainty+check['estimated_reference_uncertainty_s'],'Reference changed during operation'
  lo=max(x['offset_bounds_s'][0] for x in r['readings']);hi=min(x['offset_bounds_s'][1] for x in r['readings']);assert lo<=hi,'Read intervals incompatible'
  r.update(passed=True,offset_bounds_s=[lo,hi],reference_final=check,history_preserved=True,control_trim_unchanged=True,PF_latched=False)
 except Exception as e:r['error']=repr(e)
 finally:
  if link:
   try:
    if confirmation and not r['set_trigger_sent']:
     # An incomplete YES is deliberately made invalid; no clock write.
     link.send(b'NO\r');menu(link);confirmation=False
    if context==CLOCK and not confirmation and original!=CLOCK:link.command('Q',MON);context=MON
    if context==MON and original==REC:link.command('Q',REC);context=REC
    r['original_prompt_restored']=context==original
   except Exception as e:r['cleanup_error']=repr(e);r['passed']=False
   link.serial.close();r['port_released']=not link.serial.is_open
  if log:log.close()
  r['finished_UTC']=campaign.NOW();checkpoint()
 print(json.dumps(r),flush=True);return r
def rebase(state,board,latest,receipt,reason):
 previous=state['baselines'][board]
 identity=previous.get('EUI')
 if identity is None:
  identity=next((h['previous']['EUI'] for h in state.get('baseline_history',[]) if h['board']==board and h['previous'].get('EUI')),None)
 if identity is None:raise ValueError('Cannot rebase without the pinned EUI identity')
 state.setdefault('baseline_history',[]).append(dict(board=board,previous=previous,reason=reason,receipt=receipt))
 state['baselines'][board]=dict(latest,EUI=identity)

def collect(boards):
 old=sys.argv;sys.argv=[__file__,'--collect',*[v for b in boards for v in ('--board',b)]]
 try:campaign.main()
 finally:sys.argv=old
def main():
 if any(x in sys.argv for x in ('--align-ticks','--check-phase')):
  from rtc_phase_align import main as phase_main
  return phase_main()
 p=argparse.ArgumentParser(description=__doc__,epilog='Tick alignment: --check-phase, then --align-ticks --phase-validation <summary.json>. These modes restore the borrowed RAM block exactly.');g=p.add_mutually_exclusive_group();g.add_argument('--collect',action='store_true');g.add_argument('--check-interface',action='store_true');g.add_argument('--sync',action='store_true');p.add_argument('--board',action='append',choices=IDS);p.add_argument('--server',default='132.163.96.6');p.add_argument('--lead-ms',type=float);p.add_argument('--out',type=Path);p.add_argument('--validation',type=Path);p.add_argument('--self-test',action='store_true');args=p.parse_args()
 if args.self_test:
  assert calendar(b'UTC:   2026-11-01 00:00:00')==1793491200;assert calendar(b'Calendar (UTC convention): 2026-11-01 00:00:00')==1793491200
  assert calendar(b'UTC:   Sun 2026-11-01 00:00:00')==1793491200
  assert raw_status(b'RTC registers (raw): 80 00 00 29 01 11 26 80 0E ')[7:]==b'\x80\x0e'
  try:calendar(b'Local: 2026-11-01 00:00:00')
  except ValueError:pass
  else:raise AssertionError('Must never parse local time as UTC')
  print('PASS offline UTC/status parser and rejection cases');return
 boards=list(dict.fromkeys(args.board or IDS))
 if args.sync:
  assert args.validation,'--sync requires a successful --check-interface summary via --validation'
  proof=json.loads(args.validation.read_text())
  validated={x['board'] for x in proof['boards'] if x['passed'] and not x['sync_requested'] and x.get('original_prompt_restored') and x.get('history_preserved')}
  assert set(boards)<=validated,'Every selected board must pass read-only interface validation'
  assert time.time()-args.validation.stat().st_mtime<3600,'Interface validation expired'

 with serial_lease('drift',timeout=30):
  if not args.sync and not args.check_interface:collect(boards);return
  out=args.out or campaign.Q/datetime.now(timezone.utc).strftime('rtc-fleet-%Y%m%dT%H%M%SZ');out.mkdir(exist_ok=False)
  rows=[];save(out/'authorization.json',dict(sync=args.sync,owner='Synchronize all four once after validation' if args.sync else 'Read-only CLOCK interface validation',time_set_repeats=False))
  for b in boards:
   r=operate(b,out/b,args);rows.append(r);save(out/'summary.json',dict(passed=all(x['passed'] for x in rows),boards=rows))
  if args.sync:
   # Always capture after a possible write; retain the old series and explicitly
   # publish new per-board baselines only for verified successful SETs.
   collect(boards);state=campaign.read(campaign.STATE);points=campaign.read(Path(state['root'])/'points.json')
   for r in rows:
    if r['clock_set_verified']:
     ps=[x for x in points if x['board']==r['board'] and x['time']>=r['target_unix']]
     if ps:
      latest=max(ps,key=lambda x:x['time']);rebase(state,r['board'],latest,str(out/r['board']/'report.json'),'Owner-authorized UTC sync')
   campaign.save(campaign.STATE,state);campaign.report(state)
  print('FLEET_REPORT',out,flush=True)
  if not all(x['passed'] for x in rows):raise SystemExit(1)
if __name__=='__main__':main()
