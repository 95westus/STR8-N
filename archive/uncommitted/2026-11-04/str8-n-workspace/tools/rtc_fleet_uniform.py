"""Fixed hourly phase grids beside (never replacing) the fleet drift schedule.

Only the host launch clock is new. Qualified image, collector, audit and transport
remain unchanged. 2604's existing cooperative grid is imported with receipts.
"""
import argparse, contextlib, hashlib, importlib, inspect, json, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('C:/SRC/STR8-N')
Q = ROOT / 'output/qualification'
CONFIG = Q / 'rtc-uniform-sampling.json'
LAST = Q / 'rtc-uniform-controller-last.json'
LOCK = Q / 'rtc-uniform-controller.lock'
INTERVAL, LEAD, LATEST, TOLERANCE, RATE = 3600, 180, 120, .25, 200e-6
MODULES = {'2205':'rtc_led_collect_g10_2205', '2512':'rtc_led_collect_g10',
           '2609':'rtc_led_collect_g10_2609_r2', '2604':'rtc_led_collect_g10_2604_r2'}

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, value):
    from installer.common import save as atomic
    atomic(Path(p), value)

def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()

def segment(state, board, trim, control):
    return json.dumps({'boundary':state.get('segment_boundaries', {}).get(board),
                       'baseline':state.get('baselines', {}).get(board, {}).get('time'),
                       'trim':trim, 'control':control}, sort_keys=True)

def advance(grid, now):
    epoch = grid['next_epoch_unix']
    while now > epoch - LATEST or str(int(epoch)) in grid['slots']:
        grid['slots'].setdefault(str(int(epoch)), {'status':'missed; no interpolation'})
        epoch += INTERVAL
    grid['next_epoch_unix'] = epoch
    return epoch

def phase_point(rows, epoch, reference_uncertainty=None):
    assert len(rows) >= 9
    if reference_uncertainty is not None:
        for r in rows:
            assert r['rtc_minus_reference_interval_s']==[r['rtc_unix']-r['reference_end_unix']-reference_uncertainty,r['rtc_unix']+1-r['reference_start_unix']+reference_uncertainty], 'Saved observation phase interval differs from original RTC/reference evidence'
    ts = [(r['reference_start_unix'] + r['reference_end_unix']) / 2 for r in rows]
    actual = (ts[0] + ts[-1]) / 2
    # Each observation is an interval for instantaneous phase. Project bounds,
    # not values, onto the capture midpoint under a documented 200-ppm limit.
    low = max(r['rtc_minus_reference_interval_s'][0] - RATE*abs(t-actual) for r,t in zip(rows,ts))
    high = min(r['rtc_minus_reference_interval_s'][1] + RATE*abs(t-actual) for r,t in zip(rows,ts))
    assert low <= high, 'Within-capture phase compatibility failed'
    allowance = RATE*abs(actual-epoch)
    return dict(time=epoch, UTC=iso(epoch), actual_midpoint_unix=actual,
                midpoint_error_s=actual-epoch, low=low-allowance, high=high+allowance,
                mid=(low+high)/2, epoch_projection_allowance_s=allowance,
                within_capture_rate_bound_ppm=RATE*1e6)

def adev(points):
    ps = {int(p['time']):p for p in points}
    out = []
    if not ps:return out
    max_m = int((max(ps)-min(ps))//(2*INTERVAL))
    for m in range(1, max_m+1):
        tau=m*INTERVAL; values=[]; lows=[]; highs=[]; epochs=[]
        for t,a in sorted(ps.items()):
            if t+tau not in ps or t+2*tau not in ps:continue
            b,c=ps[t+tau],ps[t+2*tau]
            v=c['mid']-2*b['mid']+a['mid']
            lo=c['low']-2*b['high']+a['low'];hi=c['high']-2*b['low']+a['high']
            values.append(v*v);lows.append(0 if lo<=0<=hi else min(lo*lo,hi*hi));highs.append(max(lo*lo,hi*hi));epochs.append(t)
        if values:
            scale=2*tau*tau*len(values)
            out.append(dict(tau_seconds=tau, terms=len(values), adev=math.sqrt(sum(values)/scale),
                            compatibility_bounds=[math.sqrt(sum(lows)/scale),math.sqrt(sum(highs)/scale)], term_start_epochs=epochs))
    return out

class TimingDefer(Exception):pass

@contextlib.contextmanager
def timing_hooks(module, epoch, evidence, clock=time.monotonic, sleep=time.sleep, guard=lambda:None):
    """Process-local launch delay; no collector, image or global scheduler edits."""
    import installer.engine.legacy_transport as transport
    from serial_test_coordination import serial_lease
    old_link, old_reference, old_lease = transport.Link, module.b.Reference, module.serial_lease
    holder = {}
    class Reference(old_reference):
        def __init__(self, samples):
            super().__init__(samples)
            guard()
            wait=epoch-31-self.now()
            if wait < 0:raise TimingDefer('Setup missed observation start; safely restore RAM')
            if wait > LEAD:raise TimingDefer('Reference target outside bounded launch window')
            self.uniform_target=clock()+wait
            # Original uncertainty checks run first. Bound additional reference
            # aging while waiting, without relaxing packet/quality checks.
            self.uncertainty += wait*100e-6
            holder['reference']=self
            evidence.update(reference_wait_seconds=wait, additional_reference_aging_s=wait*100e-6)
    class Link(old_link):
        def send(self, data):
            if data == b'G 2000\r':
                ref=holder['reference']
                while clock()<ref.uniform_target:sleep(min(.05,ref.uniform_target-clock()))
                evidence.update(command_reference_unix=ref.now(), command_monotonic=clock())
            return super().send(data)
    transport.Link, module.b.Reference = Link, Reference
    @contextlib.contextmanager
    def lease(*args,**kwargs):
        with serial_lease('uniform-fleet',timeout=2):
            guard()
            yield
    module.serial_lease=lease
    try:yield
    finally:
        transport.Link, module.b.Reference, module.serial_lease=old_link,old_reference,old_lease

def components():
    import rtc_led_mode_g10_2205 as mode
    modules={b:importlib.import_module(name) for b,name in MODULES.items()}
    readiness={'2205':mode.ready,'2604':mode.previous.ready,
               '2609':mode.previous.previous.ready,'2512':mode.previous.previous.previous.ready}
    return mode,modules,readiness

def verify(config):
    assert sha(__file__)==config['scheduler_sha256'], 'Uniform scheduler differs from validated source'
    for path,pin in config['pins'].items():assert sha(path)==pin, f'Pinned component changed: {path}'
    proof=read(config['validation'])
    assert proof['passed'] and proof['scheduler_sha256']==config['scheduler_sha256']

def import_2604(config, state):
    source=read(Q/'2604-uniform-sampling.json')
    from rtc_calibration_points import merged_points
    verified={p['report']:p for p in merged_points(state,[]) if p['board']=='2604'}
    grid=config['boards']['2604']
    assert source['anchor_unix']==grid['anchor_unix'] and source['interval_seconds']==INTERVAL
    for point in source['points']:
        if any(p['report']==point['report'] for p in grid['points']):continue
        original=verified.get(point['report'])
        if original is None:continue  # Old segments remain in their original files.
        assert abs((point['time']-grid['anchor_unix']) % INTERVAL)<1e-6
        assert point['mid']==original['offset']
        assert abs(point['actual_midpoint_unix']-original['time'])<1e-6
        assert abs(point['midpoint_error_s'])<=TOLERANCE
        allowance=RATE*abs(original['time']-point['time'])
        assert abs(point['low']-(original['low']-allowance))<1e-9
        assert abs(point['high']-(original['high']+allowance))<1e-9
        p=dict(point, report_sha256=original['report_sha256'], segment=segment(state,'2604',original['trim'],original['control']), source='existing qualified cooperative grid')
        grid['points'].append(p)
    if grid.get('external_sampler',True):
        grid['slots']=dict(source['slots']);grid['next_epoch_unix']=source['next_epoch_unix']

def render(config, state):
    import_2604(config,state)
    result={'updated_utc':iso(time.time()),'interval_seconds':INTERVAL,'boards':{},
            'limitations':'Hourly 62-second phase captures with dead time, reference/quantization noise and bounded phase projection. Not continuous no-dead-time oscillator data. No interpolation or noise-law claim. Compatibility bounds are deterministic, not statistical confidence intervals.'}
    lines=['# All-board uniform stability', '', result['limitations'], '',
           'Original drift monitoring, random 2512 extras and board catch-ups are unchanged. Only timing-qualified fixed-grid points enter this report; every point retains its original capture/restoration receipt.', '',
           '| Board | Hourly UTC minute | Accepted uniform points | Next nominal epoch UTC |', '|---|---:|---:|---|']
    for board,grid in config['boards'].items():
        groups={}
        for p in grid['points']:
            assert sha(p['report'])==p['report_sha256'],'Uniform source receipt changed'
            assert read(p['report'])['passed'],'Uniform source capture failed'
            if p.get('uniform_receipt'):assert sha(p['uniform_receipt'])==p['uniform_receipt_sha256'],'Uniform derivation receipt changed'
            groups.setdefault(p['segment'],[]).append(p)
        segments=[{'segment':key,'points':ps,'allan_deviation':adev(ps)} for key,ps in groups.items()]
        result['boards'][board]={'segments':segments,'accepted_points':len(grid['points']),'slots':grid['slots'],'next_epoch_unix':grid['next_epoch_unix']}
        lines.append(f"| {board} | :{grid['minute']:02d} | {len(grid['points'])} | {iso(grid['next_epoch_unix'])} |")
    lines+=['','## Overlapping phase Allan deviation','','Only existing grid endpoints in the same clock/trim/control segment form a second-difference term. Missing captures remain gaps. Counts describe overlapping terms, not independent degrees of freedom.','', '| Board / segment | Tau seconds | Terms | ADEV ppm | Compatible bounds ppm |','|---|---:|---:|---:|---|']
    count=0
    for board,data in result['boards'].items():
        for n,s in enumerate(data['segments']):
            for a in s['allan_deviation']:
                count+=1;lines.append(f"| {board} / {n+1} | {a['tau_seconds']} | {a['terms']} | {a['adev']*1e6:.6f} | {a['compatibility_bounds'][0]*1e6:.6f} .. {a['compatibility_bounds'][1]*1e6:.6f} |")
    if not count:lines+=['','Waiting for at least three suitable fixed-grid points in a segment. No standard Allan-deviation curve is available yet.']
    save(Q/'rtc-uniform-stability.json',result)
    (Q/'rtc-uniform-stability-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    plot(result)
    save(CONFIG,config)

def plot(result):
    # Scientific plotting is optional on lean hardware-controller runtimes.
    from PIL import Image, ImageDraw
    im=Image.new('RGB',(1300,760),'white');d=ImageDraw.Draw(im)
    d.text((45,22),'All-board hourly phase Allan deviation (with dead time)',fill='black')
    d.text((45,45),'Reference/quantization noise included. Bounds are compatibility bounds. Segments never joined.',fill='black')
    series=[]
    colors={'2205':'#2475b0','2512':'#cc6f13','2604':'#278248','2609':'#8c48aa'}
    for b,v in result['boards'].items():
        d.text((50+300*list(colors).index(b),90),f"{b}: {v['accepted_points']} fixed-grid points",fill=colors[b])
        for s in v['segments']:
            aa=s['allan_deviation']
            if aa:series.append((b,aa))
    d.line((100,650,1220,650),fill='black');d.line((100,150,100,650),fill='black')
    d.text((540,700),'Averaging time tau (seconds, logarithmic)',fill='black')
    d.text((15,125),'ADEV (ppm)',fill='black')
    if not series:
        d.text((300,350),'Waiting for three suitable fixed-grid points per clock/trim segment.',fill='black')
    else:
        xs=[a['tau_seconds'] for _,aa in series for a in aa];ys=[max(a['adev']*1e6,1e-6) for _,aa in series for a in aa]
        x0,x1=math.floor(math.log10(min(xs))),max(math.ceil(math.log10(max(xs))),math.floor(math.log10(min(xs)))+1)
        y0,y1=math.floor(math.log10(min(ys))),max(math.ceil(math.log10(max(ys))),math.floor(math.log10(min(ys)))+1)
        X=lambda v:100+(math.log10(v)-x0)/(x1-x0)*1120
        Y=lambda v:650-(math.log10(max(v,10**y0))-y0)/(y1-y0)*500
        for e in range(x0,x1+1):
            x=X(10**e);d.line((x,150,x,650),fill='#dddddd');d.text((x,660),f'1e{e}',fill='black')
        for e in range(y0,y1+1):
            y=Y(10**e);d.line((100,y,1220,y),fill='#dddddd');d.text((40,y),f'1e{e}',fill='black')
        for b,aa in series:
            pts=[(X(a['tau_seconds']),Y(a['adev']*1e6)) for a in aa]
            if len(pts)>1:d.line(pts,fill=colors[b],width=2)
            for (x,y),a in zip(pts,aa):
                lo,hi=a['compatibility_bounds'];d.line((x,Y(hi*1e6),x,Y(lo*1e6)),fill=colors[b])
                d.ellipse((x-4,y-4,x+4,y+4),fill=colors[b]);d.text((x+6,y),f"n={a['terms']}",fill=colors[b])
    im.save(Q/'rtc-uniform-stability.png')

def reconcile(config, state):
    for board,grid in config['boards'].items():
        if board=='2604' and grid.get('external_sampler',True):continue
        for key,slot in list(grid['slots'].items()):
            if slot['status']!='in flight; audit before retry':continue
            folder=Path(slot['folder']);path=folder/'report.json'
            if not path.exists() or not read(path).get('passed'):
                config.setdefault('held_boards',{})[board]={'error':'Interrupted unit: inspect saved evidence and pending restoration before any retry','folder':str(folder)}
                slot['status']='interrupted; board held; no hardware retry'
                continue
            module=importlib.import_module(MODULES[board])
            item=dict(board=board,report=str(path),sha256=sha(path),RAM_restored=True,capture_profile=module.PROFILE)
            original=module.audit_board(item,state)
            rows=[json.loads(line) for line in (folder/'observations.jsonl').read_text().splitlines()]
            point=phase_point(rows,int(key),read(path).get('reference_uncertainty_s'))
            point.update(report=str(path),report_sha256=sha(path),segment=segment(state,board,original['trim'],original['control']),source='re-audited completed original capture')
            assert not original['PF_latched'],'Interrupted capture contains PF indication'
            accepted=abs(point['midpoint_error_s'])<=TOLERANCE
            receipt=dict(passed=True,original_audit_passed=True,accepted_uniform=accepted,point=point,original_point=original,recovered_without_hardware_retry=True)
            save(folder/'uniform-receipt.json',receipt)
            if accepted and not any(p['report']==str(path) for p in grid['points']):
                point['uniform_receipt']=str(folder/'uniform-receipt.json');point['uniform_receipt_sha256']=sha(folder/'uniform-receipt.json')
                grid['points'].append(point)
            slot.update(status='accepted' if accepted else 'drift only; midpoint outside tolerance',report=str(path),uniform_receipt=str(folder/'uniform-receipt.json'))


def run_once():
    import rtc_drift_campaign as c
    import rtc_hourly_schedule as hourly
    from serial_test_coordination import drift_pending
    config=read(CONFIG);state=read(c.STATE);plan=read(hourly.PLAN)
    verify(config)
    if not config['active'] or not state['active'] or state.get('owner_stopped') or not plan['active'] or plan.get('owner_stopped'):
        return {'action':'pause_automation','notify':False,'reason':'Owner stop; no ports opened'}
    previous_holds=set(config.get('held_boards',{}))
    reconcile(config,state)
    new_holds=set(config.get('held_boards',{}))-previous_holds
    now=time.time(); candidates=[]
    for board,grid in config['boards'].items():
        if board=='2604' and grid.get('external_sampler',True):continue # Existing qualified cooperative sampler owns :25.
        candidates.append((advance(grid,now),board))
    epoch,board=min(candidates);grid=config['boards'][board]
    def finish(action='wait',**extra):
        render(config,read(c.STATE))
        next_epoch,next_board=min((g['next_epoch_unix'],b) for b,g in config['boards'].items() if b!='2604' or not g.get('external_sampler',True))
        minutes=max(1,min(5,math.floor((next_epoch-LEAD-time.time()-120)/60)))
        result=dict(action=action,notify=False,next_interval_minutes=minutes,next_board=next_board,next_epoch_utc=iso(next_epoch),**extra)
        save(LAST,result);return result
    if new_holds:
        result=finish('failure',new_holds=sorted(new_holds));result['notify']=True;save(LAST,result);return result
    if now<epoch-LEAD-120:return finish()
    # Enter up to two minutes early so minute-granularity heartbeat jitter
    # cannot push NIST preflight past the one-minute launch window.
    while time.time()<epoch-LEAD:time.sleep(min(1,epoch-LEAD-time.time()))
    now=time.time()
    if board in config.get('held_boards',{}):
        grid['slots'][str(int(epoch))]={'status':'held after saved material failure'};advance(grid,now);return finish()
    if board in plan.get('owner_blocked_boards',{}):
        grid['slots'][str(int(epoch))]={'status':'owner-blocked; no port opened'};advance(grid,now);return finish()
    due,_,_=hourly.next_event(plan)
    if drift_pending() or time.time()+300>=due:
        grid['slots'][str(int(epoch))]={'status':'RTC priority gap; no port opened'};advance(grid,now);return finish()
    mode,modules,ready=components();module=modules[board]
    try:
        assert mode.enabled(state) and ready[board](state),'Current qualified profile unavailable'
        module.f.admission(board)
    except AssertionError as e:
        grid['slots'][str(int(epoch))]={'status':'unavailable/profile deferred; no port opened','reason':str(e)};advance(grid,now);return finish()
    def guard():
        fresh=read(c.STATE);fresh_plan=read(hourly.PLAN)
        if not fresh['active'] or fresh.get('owner_stopped') or not fresh_plan['active'] or board in fresh_plan.get('owner_blocked_boards',{}):raise TimingDefer('Owner stop/hold takes precedence')
        if fresh.get('segment_boundaries',{}).get(board)!=state.get('segment_boundaries',{}).get(board):raise TimingDefer('Clock/trim segment changed during setup')
        if drift_pending() or time.time()+300>=hourly.next_event(fresh_plan)[0]:raise TimingDefer('RTC priority takes precedence')
    network=[]
    try:
        for n in range(3):
            if n:time.sleep(4.1)
            network.append(module.b.ntp_sample('132.163.96.6'))
        module.b.Reference(network)
    except TimeoutError:
        grid['slots'][str(int(epoch))]={'status':'NIST preflight gap; no serial access'};advance(grid,time.time());return finish()
    if time.time()>epoch-LATEST:
        grid['slots'][str(int(epoch))]={'status':'preflight missed launch window; no serial access'};advance(grid,time.time());return finish()
    # Save intent before any hardware work. A subsequent wake must audit this
    # receipt, never repeat an in-flight or completed epoch.
    folder=Q/'rtc-uniform-captures'/board/datetime.fromtimestamp(epoch,timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence={'board':board,'epoch':epoch,'scheduler_sha256':sha(__file__),'preflight':network,'driver_sha256':sha(module.__file__),'pins':config['pins']}
    grid['slots'][str(int(epoch))]={'status':'in flight; audit before retry','folder':str(folder)}
    save(CONFIG,config)
    try:
        with timing_hooks(module,epoch,evidence,guard=guard):r=module.collect(board,folder)
        save(folder/'uniform-launch.json',evidence)
        if not r['passed']:
            restored=all(r.get(k) for k in ('application_ram_restored','LED_restored','returned_to_original_prompt','port_released')) and not r.get('restoration_error')
            if restored and str(r.get('error','')).startswith('TimingDefer('):
                grid['slots'][str(int(epoch))]={'status':'late setup gap; exactly restored','report':str(folder/'report.json')};advance(grid,time.time());return finish()
            raise RuntimeError(r.get('restoration_error',r.get('error','Capture failed')))
        item=dict(board=board,report=str(folder/'report.json'),sha256=sha(folder/'report.json'),RAM_restored=True,capture_profile=module.PROFILE)
        original=module.audit_board(item,state)
        rows=[json.loads(line) for line in (folder/'observations.jsonl').read_text().splitlines()]
        point=phase_point(rows,epoch,r['reference_uncertainty_s'])
        point.update(report=item['report'],report_sha256=item['sha256'],segment=segment(state,board,original['trim'],original['control']),source='qualified LED collector with separately pinned host launch timing')
        if original['PF_latched']:raise RuntimeError('New PF indication; preserve latch/history and inspect capture')
        accepted=abs(point['midpoint_error_s'])<=TOLERANCE
        receipt=dict(passed=True,original_audit_passed=True,accepted_uniform=accepted,point=point,launch=evidence,original_point=original)
        save(folder/'uniform-receipt.json',receipt)
        if accepted:
            point['uniform_receipt']=str(folder/'uniform-receipt.json')
            point['uniform_receipt_sha256']=sha(folder/'uniform-receipt.json')
            grid['points'].append(point)
        grid['slots'][str(int(epoch))]={'status':'accepted' if accepted else 'drift only; midpoint outside tolerance','report':item['report'],'uniform_receipt':str(folder/'uniform-receipt.json')}
    except TimingDefer as e:
        grid['slots'][str(int(epoch))]={'status':'priority/owner deferral before serial access','reason':str(e)}
    except TimeoutError:
        grid['slots'][str(int(epoch))]={'status':'busy lease gap; no port borrowed','folder':str(folder)}
    except Exception as e:
        config.setdefault('held_boards',{})[board]={'error':repr(e),'folder':str(folder),'epoch':epoch}
        grid['slots'][str(int(epoch))]={'status':'material failure; board held','error':repr(e),'folder':str(folder)}
        advance(grid,time.time());result=finish('failure',error=repr(e),board=board);result['notify']=True;save(LAST,result);return result
    attempted_status=grid['slots'][str(int(epoch))]['status']
    advance(grid,time.time());return finish('collected' if attempted_status in ('accepted','drift only; midpoint outside tolerance') else 'wait',board=board)

def run():
    # Separate host mutex prevents a second heartbeat from interpreting an
    # actively running capture as interrupted. It never claims a serial lease.
    import msvcrt
    with LOCK.open('a+b') as lock:
        if lock.seek(0,2)==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return {'action':'wait','notify':False,'reason':'Uniform controller already running','next_interval_minutes':1}
        try:return run_once()
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--report',action='store_true');args=parser.parse_args()
    if args.run:print(json.dumps(run()))
    elif args.report:
        import rtc_drift_campaign as c
        config=read(CONFIG);verify(config);render(config,read(c.STATE))
if __name__=='__main__':main()
