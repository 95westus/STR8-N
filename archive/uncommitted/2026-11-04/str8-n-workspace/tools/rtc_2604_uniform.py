"""Anchored hourly 2604 phase captures around an unchanged qualified r8 agent.



No clock/trim writes. No interpolation or filling missing samples. Phase bounds

at a nominal epoch retain the existing 200-ppm within-capture rate allowance.

"""

import argparse, hashlib, importlib.util, json, math, time

from pathlib import Path

from datetime import datetime, timezone



ROOT=Path('C:/SRC/STR8-N');Q=ROOT/'output/qualification'

CONTROL=Q/'2604-untrimmed-ntp-campaign.json'

GRID=Q/'2604-uniform-sampling.json'

DRIVER=ROOT/'BUILD/ntp2604-r8/source/ntp2604_host.py'

PIN='8e75dc319f9c1de2b542d611c65a8c0a67dcfd332a743c36ac39b36ce4422993'

INTERVAL=3600;LEAD=180;LATEST_LEAD=120;TOLERANCE=.25



def save(p,v):

    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(v,indent=2)+'\n');temp.replace(p)

def select_slot(anchor,now,completed):

    slot=anchor+max(0,math.floor((now-anchor)/INTERVAL))*INTERVAL

    while str(int(slot)) in completed or now>slot-LATEST_LEAD:slot+=INTERVAL

    return slot

def derive(point,epoch):

    delta=epoch-point['time']

    assert abs(delta)<=TOLERANCE,'Capture midpoint missed uniform timing tolerance'

    allowance=abs(delta)*200e-6

    return dict(time=epoch,UTC=datetime.fromtimestamp(epoch,timezone.utc).isoformat(),low=point['low']-allowance,high=point['high']+allowance,mid=point['mid'],actual_midpoint_unix=point['time'],midpoint_error_s=-delta,epoch_projection_allowance_s=allowance)

def adev(points):

    ps={int(p['time']):p for p in points};result=[]

    for m in range(1,max(2,len(ps)//3+1)):

        tau=m*INTERVAL;terms=[];mins=[];maxs=[]

        for t,a in sorted(ps.items()):

            if t+tau not in ps or t+2*tau not in ps:continue

            b=ps[t+tau];c=ps[t+2*tau]

            v=c['mid']-2*b['mid']+a['mid']

            lo=c['low']-2*b['high']+a['low'];hi=c['high']-2*b['low']+a['high']

            terms.append(v*v);mins.append(0 if lo<=0<=hi else min(lo*lo,hi*hi));maxs.append(max(lo*lo,hi*hi))

        if terms:

            scale=2*tau*tau*len(terms)

            result.append(dict(tau_seconds=tau,terms=len(terms),adev=math.sqrt(sum(terms)/scale),compatibility_bounds=[math.sqrt(sum(mins)/scale),math.sqrt(sum(maxs)/scale)]))

    return result

def render(g):

    g['allan_deviation']=adev(g['points']);save(GRID,g)

    lines=['# 2604 uniform phase sampling','',f"Nominal spacing: {INTERVAL} seconds. Capture duration: 62 seconds. Midpoint tolerance: {TOLERANCE} seconds.",'','This is hourly capture-averaged phase evidence with dead time between captures. It is not a continuous no-dead-time oscillator measurement. Actual timestamps and original bounds are retained. No missing-slot interpolation. Nominal-epoch projection expands bounds by 200 ppm times the actual timing displacement.','',f"Accepted uniform points: {len(g['points'])}. Allan deviation is descriptive and includes measurement noise; short records cannot identify oscillator noise types.",'','| Averaging time s | Second-difference terms | ADEV ppm | Compatible bounds ppm |','|---:|---:|---:|---|']

    for a in g['allan_deviation']:lines.append(f"| {a['tau_seconds']} | {a['terms']} | {a['adev']*1e6:.6f} | {[v*1e6 for v in a['compatibility_bounds']]} |")

    if not g['allan_deviation']:lines+=['','Waiting for at least three appropriately spaced points.']

    (Q/'2604-uniform-stability-report.md').write_text('\n'.join(lines)+'\n')

def offline():

    assert select_slot(10000,9800,{})==10000

    assert select_slot(10000,9950,{})==13600

    assert select_slot(10000,9800,{'10000':{}})==13600

    ps=[dict(time=i*INTERVAL,mid=1+i*.036,low=1+i*.036,high=1+i*.036) for i in range(9)]

    assert all(a['adev']<1e-15 for a in adev(ps))

    ps[4]['mid']+=.001

    assert adev(ps)[0]['adev']>0

    sparse=[p for p in ps if p['time']!=INTERVAL*4]

    assert adev(sparse)[0]['terms']==4

    d=derive(dict(time=10000.2,low=-.04,high=.04,mid=0),10000)

    assert d['low']<-.04 and d['high']>.04

    try:derive(dict(time=10001,low=0,high=1,mid=.5),10000)

    except AssertionError:pass

    else:raise AssertionError('Timing guard absent')

    assert hashlib.sha256(DRIVER.read_bytes()).hexdigest()==PIN

    print('PASS uniform-grid, skipped-slot, constant-rate ADEV, perturbation, gaps and epoch-bound checks',flush=True)

def retry_ntp_once(original,server,events,sleep=time.sleep):
    """Retry only missing replies; original packet/quality validation stays authoritative."""
    for attempt in range(1,4):
        try:
            row=original(server)
        except TimeoutError as exc:
            events.append(dict(server=server,attempt=attempt,status='timeout',error=repr(exc),UTC=datetime.now(timezone.utc).isoformat()))
            if attempt==3:raise
            sleep(4.1)
        else:
            events.append(dict(server=server,attempt=attempt,status='accepted',sample=row))
            return row

def await_launch(epoch,now=time.time,sleep=time.sleep):
    # A heartbeat may arrive late. Wait on the host near the window, without a
    # serial lease, instead of requiring another heartbeat in a 60-second window.
    while now()<epoch-LEAD:
        sleep(min(30,epoch-LEAD-now()))

def main():

    p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--offline',action='store_true');a=p.parse_args();offline()

    if a.offline or not a.run:return

    control=json.loads(CONTROL.read_text());main=json.loads((Q/'rtc-drift-3hour-campaign.json').read_text());g=json.loads(GRID.read_text())

    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==g['scheduler_sha256']

    if not control.get('active') or control.get('failed') or main.get('owner_stopped') or not main.get('active'):print('STOPPED');return

    assert control['driver_sha256']==PIN

    assert g['segment_boundary']==control['segment_boundary']==main.get('segment_boundaries',{}).get('2604')

    now=time.time();epoch=select_slot(g['anchor_unix'],now,g['slots'])

    # Missed slots are explicit omissions; never collect a burst to catch up.

    for slot in range(int(g['anchor_unix']),int(epoch),INTERVAL):

        g['slots'].setdefault(str(slot),dict(status='missed; no interpolation'))

    g['next_epoch_unix']=epoch;g['next_launch_unix']=epoch-LEAD;render(g)

    if now<epoch-LEAD-120:

        print(json.dumps(dict(action='wait',next_epoch_utc=datetime.fromtimestamp(epoch,timezone.utc).isoformat(),next_interval_minutes=max(1,min(5,math.floor((epoch-LEAD-now-120)/60))))));return

    await_launch(epoch)
    if time.time()>epoch-LATEST_LEAD:print('DEFER late uniform launch');return

    spec=importlib.util.spec_from_file_location('ntp2604_uniform_r8',DRIVER);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);h.offline()

    transport=ROOT/'tools/rtc_phase_align.py'
    assert hashlib.sha256(transport.read_bytes()).hexdigest()==g['reference_transport_sha256']
    network=dict(epoch=epoch,server=control['server'],events=[],preflight_before_serial=True)
    network_path=Q/'2604-uniform-network-last.json'
    ntp_once=h.phase.ntp_once
    def resilient_ntp(server):
        try:return retry_ntp_once(ntp_once,server,network['events'])
        finally:save(network_path,network)
    h.phase.ntp_once=resilient_ntp
    try:
        preflight=h.reference(control['server'])
    except TimeoutError:
        network['status']='preflight timeout; no serial access';save(network_path,network)
        g['slots'][str(int(epoch))]=dict(status='NIST preflight unavailable; no hardware capture',network_receipt=str(network_path))
        render(g);print(json.dumps(dict(action='wait',next_interval_minutes=5,reason=network['status'])));return
    network['preflight_samples']=preflight.samples;network['status']='preflight passed';save(network_path,network)
    if time.time()>epoch-LATEST_LEAD:
        print('DEFER NIST preflight exceeded launch deadline; no serial access');return
    control=json.loads(CONTROL.read_text())
    if not control.get('active') or control.get('failed'):print('STOPPED');return
    original=h.observe

    def observe(w,ref,seconds):

        assert seconds==62,'Uniform sampler permits read-only sample mode only'

        target=epoch-31-ref.origin

        if time.perf_counter()>target:raise h.Defer('Setup missed nominal observation start; restore without a late capture')

        # Poll the unchanged read-only agent while armed, preserving its timer.

        while time.perf_counter()<target:

            w.command('p');time.sleep(min(.1,max(0,target-time.perf_counter())))

        return original(w,ref,seconds)

    h.observe=observe

    try:out,r=h.trial('sample',control['server'])

    except (h.Defer,TimeoutError) as e:print('DEFER',e);return

    (out/'uniform-network-evidence.json').write_text(json.dumps(network,indent=2)+'\n')
    if not r['passed']:

        if str(r.get('error','')).startswith('Defer(') and all(r.get(k) for k in ('owner_RAM_restored','owner_ZP_restored','original_prompt_restored','port_released')) and not r.get('restoration_error'):

            g['slots'][str(int(epoch))]=dict(status='missed observation start; safely restored',report=str(out/'report.json'));render(g);print('DEFER uniform timing; restored');return

        raise SystemExit('Uniform hardware unit failed; inspect saved receipt')

    point={k:r['after'][k] for k in ('time','UTC','low','high','mid')}

    (out/'uniform-scheduler-as-executed.py').write_bytes(Path(__file__).read_bytes())

    g=json.loads(GRID.read_text())

    try:uniform=derive(point,epoch)

    except AssertionError:

        g['slots'][str(int(epoch))]=dict(status='capture retained for drift only; midpoint outside tolerance',report=str(out/'report.json'),actual_midpoint_unix=point['time'])

    else:

        uniform['report']=str(out/'report.json');g['points'].append(uniform);g['slots'][str(int(epoch))]=dict(status='accepted',report=uniform['report'])

    g['next_epoch_unix']=epoch+INTERVAL;g['next_launch_unix']=epoch+INTERVAL-LEAD;render(g)

    control=json.loads(CONTROL.read_text());control['next_sample_unix']=g['next_launch_unix'];save(CONTROL,control)

    print('PASS uniform capture/restoration; accepted points',len(g['points']))

if __name__=='__main__':main()

