"""One read-only all-board NTP/RTCC collection per invocation; scheduling is external."""
import argparse,binascii,hashlib,json,math,re,statistics,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
STATE=Q/'rtc-drift-3hour-campaign.json'
sys.path[:0]=[str(ROOT/'tmp'),str(ROOT/'tools'),str(ROOT/'tmp/migration-python')]
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
NOW=lambda:datetime.now(timezone.utc).isoformat()
BOARDS=('2205','2512','2604','2609')


def save(path,value):
    from installer.common import save as atomic_save
    import time
    end=time.monotonic()+5
    while True:
        try:return atomic_save(path,value)
        except PermissionError:
            if time.monotonic()>end:raise
            time.sleep(.05)


def load_capture(admitted,state):
    """Exclude unrelated legacy import checks only when 2512 cannot be opened."""
    if '2512' in admitted:
        import rtc_20261027_evening as capture
        return capture
    import types
    name='rtc_20261027_collect';path=ROOT/'tmp'/f'{name}.py'
    assert admitted and set(admitted)<=set(BOARDS)-{'2512'}
    assert sha(path)==state['dependencies']['tmp/rtc_20261027_collect.py']
    source=path.read_text(encoding='utf-8')
    guard="""marker=json.loads((ROOT/'output/qualification/device-operations/2512.json').read_text())
receipt=json.loads((B15_RUN/'audited-results.json').read_text())
assert marker['firmware']=='2.0proto b15' and marker['monitor_generation']==0x8000000f
assert marker['application_ram_restored'] and not marker['block_snapshot']
assert receipt['passed'] and receipt['serial_released'] and receipt['owner_RAM_restored'] and receipt['owner_ZP_preserved']
assert sha(B15_RUN/'audited-results.json')==marker['last_b15_install_report']['sha256']"""
    assert source.count(guard)==1
    adapted=source.replace(guard,"# 2512 is excluded before any serial port can be opened.")
    assert name not in sys.modules and 'rtc_20261027_evening' not in sys.modules
    prior=types.ModuleType(name);prior.__file__=str(path);sys.modules[name]=prior
    exec(compile(adapted,str(path),'exec'),prior.__dict__)
    original_init=prior.ScopedLink.__init__
    def admitted_init(self,port,log,**kwargs):
        identities=[b for b,usb in prior.capture.IDS.items() for p in prior.comports() if p.device==port and p.serial_number==usb]
        assert len(identities)==1 and identities[0] in admitted,'Excluded board; no serial port opened'
        original_init(self,port,log,**kwargs)
    prior.ScopedLink.__init__=admitted_init
    import rtc_20261027_evening as capture
    capture.module.IDS={b:usb for b,usb in capture.module.IDS.items() if b in admitted}
    capture.campaign_admission=dict(admitted=list(admitted),excluded_2512=True,
        legacy_source_sha256=sha(path),adapted_source_sha256=hashlib.sha256(adapted.encode()).hexdigest(),
        change='Only import-time 2512 metadata/receipt checks omitted; all live guards unchanged; excluded USB denied before Link init')
    return capture


def fit(points):
    if len(points)<2:return dict(available=False,reason='Need another checkpoint')
    if points[-1]['time']-points[0]['time']<3600:return dict(available=False,reason='Await a longer powered interval')
    start=points[0]['time'];rows=[(p['time']-start,p['low'],p['high']) for p in points];lower,upper=-math.inf,math.inf
    for n,(t,lo,hi) in enumerate(rows):
        for tt,ll,hh in rows[n+1:]:
            if tt==t:continue
            lower=max(lower,(ll-hi)/(tt-t));upper=min(upper,(hh-lo)/(tt-t))
    if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:return dict(available=False,reason='No compatible constant rate')
    mx=statistics.mean(t for t,_,_ in rows);my=statistics.mean((lo+hi)/2 for _,lo,hi in rows)
    slope=sum((t-mx)*((lo+hi)/2-my) for t,lo,hi in rows)/sum((t-mx)**2 for t,_,_ in rows)
    return dict(available=True,ppm=min(upper,max(lower,slope))*1e6,bounds_ppm=[lower*1e6,upper*1e6],hours=(points[-1]['time']-start)/3600,samples=len(points))


def outage(raw,captured):
    def bcd(v):assert v&15<10 and v>>4<10;return (v>>4)*10+(v&15)
    def values(r):
        h=bcd(r[1]&31) if r[1]&64 else bcd(r[1]&63)
        if r[1]&64:h=h%12+(12 if r[1]&32 else 0)
        return bcd(r[3]&31),bcd(r[2]&63),h,bcd(r[0]&127)
    down,up=values(raw[:4]),values(raw[4:]);c=datetime.fromtimestamp(captured,timezone.utc)
    year=c.year-(up[:2]>(c.month,c.day));u=datetime(year,*up,tzinfo=timezone.utc);d=datetime(year-(down[:2]>up[:2]),*down,tzinfo=timezone.utc)
    assert d<=u and u.timestamp()<=captured+120
    return dict(down=d.timestamp(),up=u.timestamp(),down_UTC=d.isoformat(),up_UTC=u.isoformat(),minutes=(u-d).total_seconds()/60)


def audit_board(item,state):
    if item.get('capture_profile')=='RTC-LED-SECONDS-RAM1':
        from rtc_led_dispatch_g10_2205 import audit_board as led_audit
        return led_audit(item,state)
    board=item['board'];path=Path(item['report']);folder=path.parent;r=read(path);base=state['baselines'][board]
    assert r['passed'] and sha(path)==item['sha256'] and r['clock_advanced'] and r['port_released']
    assert not any(r[k] for k in ('clock_set_attempted','flash_written','trim_changed')) and r['application_ram_restored']
    assert r['eui'].replace(':','').lower()==base['EUI'] and r['trim_steps']==base['trim'] and r['control_register']==base['control']
    for p in folder.glob('ram-*-before.bin'):assert p.read_bytes()==p.with_name(p.name.replace('-before','-repeat')).read_bytes()==p.with_name(p.name.replace('-before','-restored')).read_bytes()
    assert (folder/'owner-zp-before.bin').read_bytes()==(folder/'owner-zp-after.bin').read_bytes()
    assert (folder/'rtc-and-F-before.bin').read_bytes()==(folder/'rtc-and-F-after.bin').read_bytes()
    tx=[bytes.fromhex(e['hex']).rstrip(b'\r\n') for e in map(json.loads,(folder/'serial.jsonl').read_text().splitlines()) if e['direction']=='TX']
    for token in tx:
        assert token in (b'',b'L',b'C1',b'A',b'J3',b'S',b'G 0200',b'G 0203',b'G 0206') or re.fullmatch(rb'D [0-9A-F]{4} [0-9A-F]{4}',token) or re.fullmatch(rb'S[019][0-9A-F]+',token)
        if token.startswith(b'S1'):
            record=bytes.fromhex(token[2:].decode());address=int.from_bytes(record[1:3],'big');size=len(record)-4
            assert sum(record)&255==255 and any(first<=address and address+size<=first+count for first,count in ((0x200,1077),(0x1400,0x186)))
    assert tx.count(b'G 0200')==9 and tx.count(b'G 0203')==2 and tx.count(b'G 0206')==1
    samples=r['readings'];assert len(samples)==9
    for s in samples:
        c=s['calendar'];date=datetime(c[0]+256*c[1],c[2],c[3],c[5],c[6],c[7],tzinfo=timezone.utc)
        assert date.timestamp()==s['rtc_unix'] and date.isoweekday()==c[4] and date.date()==datetime.fromtimestamp(s['reference_end_unix'],timezone.utc).date()
        assert bool(s['raw'][5]&32)==(date.year%4==0) and s['status']==0 and s['flags']&7==7
    assert len(r['reference_samples'])==3 and all(p['stratum']==1 and len(bytes.fromhex(p['packet_hex']))>=48 for p in [*r['reference_samples'],r['final_reference_check']])
    assert abs(r['final_reference_difference_s'])<=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s']
    lo,hi=r['rtc_minus_reference_interval_s'];assert [lo,hi]==[max(s['rtc_minus_reference_interval_s'][0] for s in samples),min(s['rtc_minus_reference_interval_s'][1] for s in samples)] and lo<=hi
    ee=(folder/'pf-eeprom-0.bin').read_bytes();assert len(ee)==128 and ee==(folder/'pf-eeprom-1.bin').read_bytes();events=[];active=0
    for slot in range(4):
        row=ee[32*slot:32*slot+32]
        if row==b'\xff'*32:continue
        assert row[:8]==b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5' and row[31] in (0,165)
        if row[31]==0:continue
        assert binascii.crc_hqx(row[:28],65535)==int.from_bytes(row[28:30],'little');active+=1
        if row[24]&128 and any(row[12:20]):events.append(outage(row[12:20],r['baseline_reference_unix']))
    last=samples[-1]
    if last['flags']&8 and any(last['outage']):events.append(outage(bytes(last['outage']),r['baseline_reference_unix']))
    marker=read(Q/f'device-operations/{board}.json');before=read(folder/'marker-before.json')
    assert marker.get('block_snapshot',False)==before.get('block_snapshot',False) and marker['application_ram_restored']
    if board=='2609' and read(folder/'prompt-admission.json')['entered_from_REC']:assert r['returned_to_original_REC'] and (folder/'final-REC.txt').read_bytes().endswith(b'REC> ')
    return dict(board=board,time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,offset=(lo+hi)/2,
        trim=r['trim_steps'],control=r['control_register'],PF_latched=bool(last['flags']&8),active_PF_records=active,
        events=events,report=str(path),report_sha256=sha(path))


def report(state):
    points=read(Path(state['root'])/'points.json');events=read(Path(state['root'])/'events.json');rows={}
    lines=['# Three-hour NTP/RTCC drift campaign','',f'Baseline epoch: {state["started_utc"]}. {('Owner-authorized clock synchronization is recorded; current fits start after the latest per-board boundary. Trim unchanged.' if state.get('clock_sync_operations') else 'No time reset or trim change. Only post-clear measurements belong to this campaign.')}','',
        '| Board | Latest UTC | RTCÃ¢Ë†â€™NIST seconds | Powered ppm (bounds) | Span h | Trim | PF latch |','|---|---|---:|---|---:|---:|---|']
    if state.get('last_owner_baseline'):
        lines[0]='# Hourly NTP/RTCC drift campaign'
        lines[2]=f"Campaign began {state['started_utc']}. Latest owner-requested baseline window completed {state['last_owner_baseline']['completed_UTC']}. Earlier measurements are retained; current fits begin at each board's latest baseline or clock-adjustment boundary. Trim unchanged."
    for board in BOARDS:
        ps=sorted([p for p in points if p['board']==board],key=lambda p:p['time']);last=ps[-1]
        es=[e for e in events if e['board']==board and e['up']<=last['time']];boundary=max([state['baselines'][board]['time'],state.get('segment_boundaries',{}).get(board,{}).get('time',0),*[e['up'] for e in es]])
        current=[p for p in ps if p['time']>=boundary and p['trim']==last['trim'] and p['control']==last['control']]
        f=fit(current);decision='Keep current trim';step=2/(32768*60)*1e6
        if f.get('available') and f['hours']>=24 and last.get('trim_verified',True) and not last['control']&4:
            low,high=f['bounds_ppm'];change=round(-f['ppm']/step);candidate=max(-127,min(127,last['trim']+change));delta=(candidate-last['trim'])*step
            if (low>step/2 and delta<0 or high < -step/2 and delta>0) and max(abs(low+delta),abs(high+delta))<max(abs(low),abs(high)):
                decision=f'Consider trim {candidate}; not applied'
        if last.get('trim_verified') is False:decision='Keep current trim; latest sample has no live trim read'
        elif last['control']&4:decision='Keep current trim; coarse mode needs separate calibration'
        rows[board]=dict(latest=last,fit=f,recommendation=decision)
        rate=(f'{f["ppm"]:+.3f} [{f["bounds_ppm"][0]:+.3f}, {f["bounds_ppm"][1]:+.3f}]' if f.get('available') else f['reason'])
        lines.append(f'| {board} | {last["UTC"]} | {last["offset"]:+.3f} | {rate} | {f.get("hours",0):.2f} | {last["trim"]} | {last.get("PF_latched",False)} |')
    lines+=['','PF events split powered fits. An uncleared latch may retain an older event, so absence of a new timestamp cannot prove continuous power. Bounds are measurement compatibility ranges, not statistical confidence intervals.']
    save(Path(state['root'])/'latest-analysis.json',dict(passed=True,generated_utc=NOW(),boards=rows,events=events,trim_applied=False))
    (Path(state['root'])/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    from rtc_drift_statistics import write_statistics
    write_statistics(state)
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--initialize',type=Path);parser.add_argument('--preflight',action='store_true');parser.add_argument('--collect',action='store_true');parser.add_argument('--board',action='append',choices=BOARDS);args=parser.parse_args()
    if args.initialize:
        audit=read(args.initialize);assert audit['passed'] and set(audit['boards'])==set(BOARDS)
        if STATE.exists():raise ValueError('An existing campaign must be reviewed before replacement')
        root=Q/'rtc-drift-3hour-20261028';root.mkdir();points=[]
        for board,p in audit['boards'].items():points.append(dict(p,PF_latched=False,events=[]))
        save(root/'points.json',points);save(root/'events.json',[])
        dependencies=['tmp/rtc_20261026_collect.py','tmp/rtc_20261027_collect.py','tmp/rtc_20261027_evening.py','BUILD/rtc-ram-0200-20261026/collector.bin','BUILD/rtc-ram-0200-20261026/proof.json']
        state=dict(active=True,root=str(root),started_utc=min(datetime.fromtimestamp(p['time'],timezone.utc).isoformat() for p in points),initialized_utc=NOW(),interval_hours=3,authorization='clear all pf history, begin every 3 hour drift collection',
            clear_audit=str(args.initialize.resolve()),clear_audit_sha256=sha(args.initialize),baselines=audit['boards'],dependencies={name:sha(ROOT/name) for name in dependencies},
            clock_set=False,trim_change=False,PF_ACK=False,PF_history_clear_on_scheduled_runs=False)
        state['board_admission']={board:{key:read(Q/f'device-operations/{board}.json').get(key) for key in ('firmware','monitor_generation','state','profile','preferred_monitor')} for board in BOARDS}
        save(STATE,state)
        active=read(Q/'active-rtc-campaign.json');active.update(RTC_sampling_owner_stopped=False,three_hour_campaign=str(STATE),PF_history_reset_audit=state['clear_audit'],collection_interval_hours=3)
        save(Q/'active-rtc-campaign.json',active)
        report(state);print('PASS initialized new campaign from four verified post-clear NTP baselines',root,flush=True);return
    state=read(STATE)
    if not state['active']:print('SKIP campaign inactive',flush=True);return
    for name,expected in state['dependencies'].items():assert sha(ROOT/name)==expected,'Campaign dependency changed: '+name
    admitted=[];skipped=[]
    for board in dict.fromkeys(args.board or BOARDS):
        marker=read(Q/f'device-operations/{board}.json')
        busy=any(v for k,v in marker.items() if k.endswith('_worker_active')) or any(marker.get(k) for k in ('application_RAM_restore_pending','physical_reset_pending','owner_application_running'))
        changed={key:marker.get(key) for key in state['board_admission'][board]}!=state['board_admission'][board]
        if busy or changed:skipped.append(dict(board=board,error='Board busy; do not interfere' if busy else 'Board profile/state changed; re-admission required'))
        else:admitted.append(board)
    if args.preflight:print('PASS read-only campaign admission; no port opened; admitted',admitted,'skipped',skipped,flush=True);return
    assert args.collect
    if not admitted:
        state.update(last_attempt_utc=NOW(),last_issues=skipped);save(STATE,state)
        print('ATTENTION no board admitted',json.dumps(skipped),flush=True);return
    from rtc_led_mode_g10_2205 import enabled as led_enabled, campaign as led_campaign
    if led_enabled(state):
        return led_campaign(state,admitted,skipped)
    day=Path(state['root'])/'captures'/datetime.now(timezone.utc).strftime('%Y%m%d');day.mkdir(parents=True,exist_ok=True)
    base1_boards=[b for b in admitted if (b=='2512' and state.get('base1_profile',{}).get('qualified',False)) or state.get('base1_profiles',{}).get(b,{}).get('qualified',False)]
    legacy=[b for b in admitted if b not in base1_boards]
    if legacy:
        capture=load_capture(legacy,state)
        capture.module.BASE=day;capture.module.OWNER=state['authorization']+'; recurring read-only NTP/RTCC and PF capture only. Do not repeat the one-time history clear; no UTC SET, trim, EEPROM, ACK or flash writes. Restore RAM and return original prompts.'
        argv=sys.argv;sys.argv=[__file__,*[part for board in legacy for part in ('--board',board)]]
        try:capture.module.main()
        finally:sys.argv=argv
        latest=max(day.glob('batch-*/summary.json'),key=lambda p:p.stat().st_mtime_ns);summary=read(latest)
        if hasattr(capture,'campaign_admission'):save(latest.parent/'capture-admission.json',capture.campaign_admission)
    else:
        run=day/datetime.now(timezone.utc).strftime('batch-%H%M%SZ');run.mkdir()
        latest=run/'summary.json';summary=dict(passed=False,started_utc=NOW(),boards=[],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
        save(latest,summary)
    for base1_board in base1_boards:
        folder=latest.parent/base1_board
        try:
            selected_profile=state.get('base1_profile',{}) if base1_board=='2512' else state.get('base1_profiles',{}).get(base1_board,{})
            if selected_profile.get('profile')=='MON-UI1-G10-2205-TIME-TRIM':
                from rtc_mon_ui1_g10_2205_trim import collect as g10_2205_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:g10_2205_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-G10-2604-TIME-TRIM':
                from rtc_mon_ui1_g10_2604_trim import collect as g10_2604_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:g10_2604_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-G10-2609-TIME-TRIM':
                from rtc_mon_ui1_g10_2609 import collect as g10_2609_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:g10_2609_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-G10-TIME-TRIM':
                from rtc_mon_ui1_g10_trim import collect as g10_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:g10_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GF-TIME-TRIM':
                from rtc_mon_ui1_gf_trim import collect as gf_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:gf_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GE-TIME-TRIM':
                from rtc_mon_ui1_ge_trim import collect as ge_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:ge_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GD-TIME-TRIM':
                from rtc_mon_ui1_gd_trim import collect as gd_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:gd_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GC-AUTO-PROMPT-TIME':
                from rtc_mon_ui1_gc_auto2609 import collect as gc_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:gc_collect(base1_board,folder)
            elif selected_profile.get('profile')=='MON-UI1-GC-NATIVE-TIME':
                from rtc_mon_ui1_gc import collect as gc_collect,PROFILE as base1_capture_profile
                base1_collect=lambda folder:gc_collect(base1_board,folder)
            elif base1_board=='2512' and state.get('base1_profile',{}).get('native_ui1_gb'):
                from rtc_mon_ui1_gb_2512 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2512' and state.get('base1_profile',{}).get('native_ui1'):
                from rtc_mon_ui1_2512 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2512' and state.get('base1_profile',{}).get('native_time'):
                from rtc_mon_time_2512 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2609' and state.get('base1_profiles',{}).get('2609',{}).get('profile')=='BASE1-MONB8-RTC-RAM1-2609':
                from rtc_monb8_2609 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2609':
                from rtc_base1_2609 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2512' and state.get('base1_profile',{}).get('mona_g6'):
                from rtc_mona_g6_2512 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2512' and state.get('base1_profile',{}).get('mona_g5'):
                from rtc_mona_g5_2512 import collect as base1_collect,PROFILE as base1_capture_profile
            elif base1_board=='2512' and state.get('base1_profile',{}).get('post_mona'):
                from rtc_base1_2512_post_mona import collect as base1_collect
                base1_capture_profile='BASE1-RTC-RAM1'
            else:
                from rtc_base1_collect import collect as base1_collect
                base1_capture_profile='BASE1-RTC-RAM1'
            r=base1_collect(folder)
            summary['boards'].append(dict(board=base1_board,report=str(folder/'report.json'),sha256=sha(folder/'report.json'),offset=r['rtc_minus_reference_interval_s'],trim=r['trim_steps'],RAM_restored=r['application_ram_restored'],capture_profile=base1_capture_profile))
        except Exception as error:summary['failures'].append(dict(board=base1_board,error=repr(error),report=str(folder/'report.json')))
        summary.update(passed=not summary['failures'],finished_utc=NOW());save(latest,summary)
    points=read(Path(state['root'])/'points.json');events=read(Path(state['root'])/'events.json');issues=[*skipped,*summary['failures']];new_events=[]
    for item in summary['boards']:
        try:
            if item.get('capture_profile')=='MON-UI1-G10-2205-TIME-TRIM':
                from rtc_mon_ui1_g10_2205_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-G10-2604-TIME-TRIM':
                from rtc_mon_ui1_g10_2604_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-G10-2609-TIME-TRIM':
                from rtc_mon_ui1_g10_2609 import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-G10-TIME-TRIM':
                from rtc_mon_ui1_g10_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GF-TIME-TRIM':
                from rtc_mon_ui1_gf_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GE-TIME-TRIM':
                from rtc_mon_ui1_ge_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GD-TIME-TRIM':
                from rtc_mon_ui1_gd_trim import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GC-AUTO-PROMPT-TIME':
                from rtc_mon_ui1_gc_auto2609 import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GC-NATIVE-TIME':
                from rtc_mon_ui1_gc import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board=item['board'],error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-GB-NATIVE-TIME':
                from rtc_mon_ui1_gb_2512 import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board='2512',error='Native TIME reports PF latched; no ACK sent'))
            elif item.get('capture_profile')=='MON-UI1-NATIVE-TIME':
                from rtc_mon_ui1_2512 import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board='2512',error='Native TIME reports PF latched; full PF history read needed; no ACK sent'))
            elif item.get('capture_profile')=='MON-G8-NATIVE-TIME':
                from rtc_mon_time_2512 import audit_board as native_audit
                p=native_audit(item,state)
                if p['PF_latched']:issues.append(dict(board='2512',error='Native TIME reports PF latched; full PF history read needed; no ACK sent'))
            elif item.get('capture_profile')=='BASE1-MONB8-RTC-RAM1-2609':
                from rtc_monb8_2609 import audit_board as base1_audit
                p=base1_audit(item,state)
            elif item.get('capture_profile')=='BASE1-RTC-RAM1-2609':
                from rtc_base1_2609 import audit_board as base1_audit
                p=base1_audit(item,state)
            elif item.get('capture_profile')=='BASE1-RTC-RAM1-MONA-G6':
                from rtc_mona_g6_2512 import audit_board as base1_audit
                p=base1_audit(item,state)
            elif item.get('capture_profile')=='BASE1-RTC-RAM1-MONA-G5':
                from rtc_mona_g5_2512 import audit_board as base1_audit
                p=base1_audit(item,state)
            elif item.get('capture_profile')=='BASE1-RTC-RAM1':
                if state.get('base1_profile',{}).get('post_mona'):
                    from rtc_base1_2512_post_mona import audit_board as base1_audit
                else:
                    from rtc_base1_audit import audit_board as base1_audit
                p=base1_audit(item,state)
            else:p=audit_board(item,state)
            if not any(x['board']==p['board'] and x['time']==p['time'] for x in points):points.append(p)
            for e in p['events']:
                e=dict(e,board=p['board'])
                if e['up']>=state['baselines'][p['board']]['time']-120 and not any(x['board']==e['board'] and x['down']==e['down'] and x['up']==e['up'] for x in events):events.append(e);new_events.append(e)
        except Exception as error:issues.append(dict(board=item['board'],error=repr(error)))
    save(Path(state['root'])/'points.json',points);save(Path(state['root'])/'events.json',events)
    save(latest.parent/'campaign-audit.json',dict(passed=not issues,issues=issues,new_PF_events=new_events,summary_sha256=sha(latest)))
    state.update(last_attempt_utc=NOW(),last_summary=str(latest),last_issues=issues,last_new_PF_events=new_events);save(STATE,state)
    rows=report(state)
    print('PASS' if not issues else 'ATTENTION','campaign collection',latest.parent,flush=True)
    print(json.dumps(dict(issues=issues,new_PF_events=new_events,trim_recommendations={b:r['recommendation'] for b,r in rows.items()},report=str(Path(state['root'])/'report.md')),indent=2),flush=True)


if __name__=='__main__':main()

