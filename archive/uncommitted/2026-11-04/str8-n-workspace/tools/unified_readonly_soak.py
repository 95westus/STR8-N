"""Bounded all-board MONg10 soak; RTC-priority lease, no normal RAM/NVM writes."""
import argparse,json,os,re,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import install_named_edu_2512 as ins
from installer.common import save
from inventory_boards_readonly import durable
from serial_test_coordination import serial_lease,drift_pending

t=ins.t;Q=ROOT/'output/qualification';CONTROL=Q/'unified-readonly-soak.json'
IDS={'2205':('COM3','A10MPUPNA','65C02'),'2512':('COM4','A10MQFLCA','65C02'),
     '2604':('COM5','A10MQGVHA','65C02'),'2609':('COM8','A10MPQXCA','65C816 emulation')}
F_SHA='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
NOW=lambda:datetime.now(timezone.utc).isoformat()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

class Session(t.Session):
    def __init__(self,out,log,board):
        self.folder=out;self.context=None;self.counter=0;self.client=None
        port,usb,_=IDS[board];self.link=t.transport.RecoveryLink(port,log,usb_serial=usb)

class Defer(Exception):pass

def room(seconds=120):
    due=read(Q/'rtc-hourly-controller-last.json')['next_due']
    return not drift_pending() and time.time()+seconds<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp()

def init():
    if CONTROL.exists():
        state=read(CONTROL)
        assert not state.get('active'),'Existing soak is active; do not create a duplicate'
    out=Q/datetime.now(timezone.utc).strftime('unified-readonly-soak-%Y%m%dT%H%M%SZ');out.mkdir();(out/'.gitignore').write_text('*\n')
    durable(out/'driver-as-started.py',Path(__file__).read_bytes())
    state=dict(active=True,owner_instruction='begin soak across all boards, make way for time drift collection',
        started_utc=NOW(),root=str(out),boards=list(IDS),interval_minutes=10,RTC_priority=True,unit_window_seconds=120,
        driver_sha256=t.sha(Path(__file__).read_bytes()),F_sha256=F_SHA,
        workload=['alternate MON A/B selection from idle REC only','VERSION','TIME','M1','W','APPS','full golden-F read/compare','owner RAM/ZP before/after comparison'],
        no_normal_RAM_uploads=True,flash_writes=0,SPI_writes=0,RTC_setting_writes=0,resets=0,power_cuts=0,
        results={b:dict(passed_units=0,deferrals=0,failed=False) for b in IDS})
    save(CONTROL,state);save(out/'config.json',state)
    print('STARTED unified read-only soak control; one board per lease; RTC first; no persistent writes',flush=True)

def admission(board):
    m=read(Q/f'device-operations/{board}.json')
    assert m['board']==board and m['firmware']=='STR8N-F 0.3.0 BASE1 PR05'
    assert m['monitor_generation']=='00000010' and m['current_F_sha256']==F_SHA
    if not m['application_ram_restored'] or any(m.get(k) for k in ('application_RAM_restore_pending','physical_reset_pending','block_snapshot','owner_application_running')):raise Defer('Board busy/preservation guard')
    if any(v for k,v in m.items() if k.endswith('_worker_active')):raise Defer('Board worker active')
    return m

def unit(board,state):
    if not room():raise Defer('RTC due/pending; no port opened')
    root=Path(state['root']);index=state['results'][board]['passed_units'];out=root/f'{board}-{index:06d}-{time.time_ns()}'
    out.mkdir();r=dict(board=board,passed=False,started_utc=NOW(),commands=[],flash_writes=0,SPI_writes=0,
        RTC_setting_writes=0,resets=0,power_cuts=0,RAM_uploaded=False,owner_RAM_write_commands=0)
    s=None;marked=False;original=None;before=zp=None;slot='A' if index%2==0 else 'B';mp=Q/f'device-operations/{board}.json'
    def mark(**kw):m=read(mp);m.update(kw);save(mp,m)
    def checkpoint(**kw):r.update(kw);save(out/'report.json',r)
    def check_priority():
        if not read(CONTROL).get('active') or (root/'STOP').exists():raise Defer('Owner stop requested')
        if not room(35):raise Defer('RTC priority at command boundary')
    def command(line,*,priority=True):
        if priority:check_priority()
        # Explicit command allowlist: no input can become a writer or app launch.
        assert line in ('A','B','Q','VERSION','TIME','M1','W','APPS') or re.fullmatch(r'D [0-9A-F]{4} [0-9A-F]{4}',line)
        r['commands'].append(line);s.link.send(line.encode()+b'\r');face=s.until((t.MON,t.REC),seconds=60)
        durable(out/f'{len(r["commands"]):03d}-{line.replace(" ","_")}.txt',face)
        return face
    def dump(first,last):
        cells={}
        for start in range(first,last+1,512):
            end=min(last,start+511);face=command(f'D {start:04X} {end:04X}')
            part={}
            for match in re.finditer(rb'(?m)^([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})(?:$| )',face):
                address=int(match[1],16)
                for n,value in enumerate(bytes.fromhex(match[2].decode()),address):
                    if start<=n<=end:assert n not in part;part[n]=value
            assert set(part)==set(range(start,end+1)),'Incomplete/duplicate RAM or ROM dump'
            cells.update(part)
        return bytes(cells[n] for n in range(first,last+1))
    checkpoint()
    try:
      with serial_lease('unified-readonly-soak-'+board,timeout=1):
        if not room():raise Defer('RTC window changed; no port opened')
        m=admission(board);durable(out/'marker-before.json',mp.read_bytes())
        with (out/'serial.jsonl').open('x',encoding='utf-8') as log:
          try:
            s=Session(out,log,board);s.link.send(b'\r');face=s.link.until(b'> ',seconds=8)
            original=t.REC if face.endswith(t.REC) else t.MON if face.endswith(t.MON) else None
            if original is None:raise Defer('Foreground application; no commands sent beyond CR')
            s.context=original;checkpoint(original_prompt=original.decode().strip())
            mark(soak_read_worker_active=True,current_soak_worker_pid=os.getpid());marked=True
            if original==t.REC:command(slot)
            before=dump(0x200,0x66ff);zp=dump(0,0xdf)
            durable(out/'owner-RAM-before.bin',before);durable(out/'owner-ZP-before.bin',zp)
            version=command('VERSION');assert b'STR8-N MON ' in version and b'gen 00000010' in version
            assert f'Board: {board}'.encode() in version and ('CPU: '+IDS[board][2]).encode() in version
            active=re.search(rb'STR8-N MON ([AB])  gen 00000010',version);assert active
            sample=command('TIME');assert re.search(rb'RTCC: 20.*flags \$[0-9A-F]{2} trim \$[0-9A-F]{2} ctrl \$[0-9A-F]{2}',sample)
            grid=command('M1');assert all(f'B{n}'.encode() in grid for n in range(4)) and b'Tools invalid' not in grid
            wear=command('W');assert b'REFUSED' not in wear and b'Tools invalid' not in wear
            apps=command('APPS');assert b'ASM B0:A000' in apps and b'DBG B0:C000' in apps and b'CLOCK' in apps
            flash=dump(0xf000,0xffff);assert t.sha(flash)==F_SHA;checkpoint(F_exact=True)
            after=dump(0x200,0x66ff);za=dump(0,0xdf)
            assert after==before and za==zp,'Owner RAM/ZP changed during read-only commands'
            checkpoint(passed=True,MON_slot=active[1].decode(),owner_RAM_unchanged=True,owner_ZP_unchanged=True,
                       owner_RAM_sha256=t.sha(before),owner_ZP_sha256=t.sha(zp))
          except Defer as error:checkpoint(deferred=str(error));raise
          except BaseException as error:checkpoint(error=repr(error));raise
          finally:
            try:
                if s and original is not None and s.context==t.MON and original==t.REC:command('Q',priority=False)
                if s and original is not None:assert s.context==original,'Original prompt not restored'
                if s:r['original_prompt_restored']=original is not None
            finally:
                if s:s.link.close();r['port_released']=True
                if marked:
                    hold=bool(r.get('error'))
                    mark(soak_read_worker_active=False,current_soak_worker_pid=None,
                        **(dict(block_snapshot=True,soak_inspection_required=True) if hold else {}))
                checkpoint(finished_utc=NOW())
    except Defer:raise
    except TimeoutError as error:
        if not s:raise Defer('Serial lease unavailable; no port opened') from error
        raise
    return str(out/'report.json'),r

def sweep():
    state=read(CONTROL);root=Path(state['root'])
    if not state.get('active') or (root/'STOP').exists():
        state['active']=False;save(CONTROL,state);print('SOAK STOPPED: no ports opened',flush=True);return
    assert t.sha(Path(__file__).read_bytes())==state['driver_sha256'],'Driver changed; inspect instead of silently continuing'
    sweep_log=dict(started_utc=NOW(),passed=[],deferred=[],failures=[])
    for board in state['boards']:
        row=state['results'][board]
        if row.get('failed'):continue
        try:
            path,r=unit(board,state);row.update(passed_units=row['passed_units']+1,last_pass_utc=NOW(),last_report=path)
            sweep_log['passed'].append(board);print('PASS soak '+board+' '+r['MON_slot'],flush=True)
        except Defer as error:
            row['deferrals']+=1;row['last_defer']=str(error);sweep_log['deferred'].append(dict(board=board,reason=str(error)))
        except BaseException as error:
            row.update(failed=True,error=repr(error));sweep_log['failures'].append(dict(board=board,error=repr(error)))
            print('FAIL soak '+board+' '+repr(error),flush=True)
        state.update(updated_utc=NOW(),last_sweep=sweep_log);save(CONTROL,state);save(root/'status.json',state)
    sweep_log['finished_utc']=NOW();save(root/f'sweep-{time.time_ns()}.json',sweep_log)
    print(json.dumps(sweep_log),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--init',action='store_true');a.add_argument('--sweep',action='store_true');args=a.parse_args()
    if args.init:init()
    if args.sweep:sweep()
