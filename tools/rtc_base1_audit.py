"""Strict file-only audit/acceptance of the BASE1 read-only RAM sampler."""
import argparse,binascii,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';BUILD=ROOT/'BUILD/rtc-base1-2512-20261029';REPO=ROOT/'release/str8nf-v0.2.0'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest=lambda b:hashlib.sha256(bytes(b)).hexdigest()
crc=lambda b:binascii.crc_hqx(bytes(b),65535)


def audit_board(item,state):
    import rtc_drift_campaign as campaign
    path=Path(item['report']);folder=path.parent;r=read(path);base=state['baselines']['2512'];proof=read(BUILD/'proof.json')
    assert r['board']=='2512' and r['capture_profile']=='BASE1-RTC-RAM1' and r['passed'] and sha(path)==item['sha256']
    assert proof['passed'] and r['client_sha256']==proof['sha256'] and r['client_proof_sha256']==sha(BUILD/'proof.json')
    assert r['driver_sha256']==sha(ROOT/'tools/rtc_base1_collect.py')
    assert all(r[k] for k in ('application_ram_restored','returned_to_original_REC','port_released','clock_advanced','acquisition_passed'))
    assert not any(r[k] for k in ('clock_set_attempted','flash_written','trim_changed'))
    assert sha(r['initial_qualified_receipt'])==r['initial_qualified_receipt_sha256'] and read(r['initial_qualified_receipt'])['passed']
    before=read(folder/'marker-before.json')
    for bank in range(4):
        bodies=[(folder/f'flash-{label}-{n}-b{bank}.bin').read_bytes() for label in ('before','after') for n in (1,2)]
        assert len(bodies[0])==32768 and all(b==bodies[0] for b in bodies)
        assert digest(bodies[0])==before['current_physical_bank_sha256'][f'B{bank}']
    assert digest((folder/'flash-before-1-b3.bin').read_bytes()[-4096:])==before['current_F_sha256']=='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
    ram=(folder/'owner-ram-before.bin').read_bytes();zp=(folder/'owner-zp-before.bin').read_bytes()
    assert len(ram)==0x6500 and len(zp)==0xe0
    assert ram==(folder/'owner-ram-restored.bin').read_bytes() and zp==(folder/'owner-zp-restored.bin').read_bytes()
    assert digest(ram)==r['RAM_sha256'] and digest(zp)==r['ZP_sha256']
    assert (folder/'final-REC.txt').read_bytes().endswith(b'REC> ')
    records=list(map(json.loads,(folder/'serial.jsonl').read_text().splitlines()))
    tx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='TX')
    rx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='RX');assert rx.endswith(b'REC> ')
    reader=(REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();image=(BUILD/'2512-RTC-BASE1-RAM.bin').read_bytes()
    flashes=b''.join(b'F'+bytes([b]) for n in (1,2) for b in (3,0,1,2))
    restore=b'W'+ram+crc(ram).to_bytes(2,'little')+b'Y'+zp+crc(zp).to_bytes(2,'little')+b'MZQ'
    expected=b'\rC1\rL\r'+reader+b'MMZZ'+flashes+restore+b'C1\rL\r'+image+b'MMZI H'.replace(b' ',b'')+b'R'*9+b'H'+flashes+restore
    assert tx==expected,'Serial trace contains an operation outside the exact read/load/restore sequence'
    assert r['eui'].replace(':','').lower()==base['EUI']
    assert r['trim_steps']==base['trim'] and r['control_register']==base['control']
    samples=r['readings'];assert len(samples)==9
    for sample in samples:
        c=sample['calendar'];date=datetime(c[0]+256*c[1],c[2],c[3],c[5],c[6],c[7],tzinfo=timezone.utc)
        assert date.timestamp()==sample['rtc_unix'] and date.isoweekday()==c[4]
        assert date.date()==datetime.fromtimestamp(sample['reference_end_unix'],timezone.utc).date()
        assert bool(sample['raw'][5]&32)==(date.year%4==0) and sample['status']==0 and sample['flags']&7==7
        assert sample['raw'][7:9]==samples[0]['raw'][7:9]
    assert len(r['reference_samples'])==3 and all(p['stratum']==1 and len(bytes.fromhex(p['packet_hex']))>=48 for p in [*r['reference_samples'],r['final_reference_check']])
    assert abs(r['final_reference_difference_s'])<=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s']
    lo,hi=r['rtc_minus_reference_interval_s'];assert [lo,hi]==[max(x['rtc_minus_reference_interval_s'][0] for x in samples),min(x['rtc_minus_reference_interval_s'][1] for x in samples)] and lo<=hi
    ee=(folder/'pf-eeprom-0.bin').read_bytes();assert len(ee)==128 and ee==(folder/'pf-eeprom-1.bin').read_bytes()
    events=[];active=0
    for slot in range(4):
        row=ee[32*slot:32*slot+32]
        if row==b'\xff'*32:continue
        assert row[:8]==b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5' and row[31] in (0,165)
        if row[31]==0:continue
        assert crc(row[:28])==int.from_bytes(row[28:30],'little');active+=1
        if row[24]&128 and any(row[12:20]):events.append(campaign.outage(row[12:20],r['baseline_reference_unix']))
    last=samples[-1]
    if last['flags']&8 and any(last['outage']):events.append(campaign.outage(bytes(last['outage']),r['baseline_reference_unix']))
    return dict(board='2512',time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,offset=(lo+hi)/2,trim=r['trim_steps'],control=r['control_register'],PF_latched=bool(last['flags']&8),active_PF_records=active,events=events,report=str(path),report_sha256=sha(path),capture_profile='BASE1-RTC-RAM1')


def accept(path):
    import rtc_drift_campaign as c
    state=read(c.STATE);path=Path(path).resolve();r=read(path);run=path.parent.parent
    item=dict(board='2512',report=str(path),sha256=sha(path),offset=r['rtc_minus_reference_interval_s'],trim=r['trim_steps'],RAM_restored=True,capture_profile='BASE1-RTC-RAM1')
    point=audit_board(item,state)
    assert read(Q/'serial-coordination/owner.json')['kind']=='idle'
    root=Path(state['root']);points=read(root/'points.json');events=read(root/'events.json');new=[]
    if not any(p['board']=='2512' and p['time']==point['time'] for p in points):points.append(point)
    for event in point['events']:
        event=dict(event,board='2512')
        if event['up']>=state['baselines']['2512']['time']-120 and not any(e['board']=='2512' and e['down']==event['down'] and e['up']==event['up'] for e in events):events.append(event);new.append(event)
    summary=dict(passed=True,started_utc=r['started_utc'],finished_utc=r['finished_utc'],boards=[item],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
    c.save(run/'summary.json',summary);c.save(root/'points.json',points);c.save(root/'events.json',events)
    audit=dict(passed=True,issues=[],new_PF_events=new,summary_sha256=sha(run/'summary.json'),serial_trace_exact_read_load_restore_only=True,all_four_flash_banks_double_verified_unchanged=True,RAM_ZP_restoration_verified=True,returned_to_original_REC=True)
    c.save(run/'campaign-audit.json',audit)
    marker=read(Q/'device-operations/2512.json')
    state['board_admission']['2512']={k:marker.get(k) for k in state['board_admission']['2512']}
    state['base1_profile']=dict(board='2512',qualified=True,profile='BASE1-RTC-RAM1',F_sha256=marker['current_F_sha256'],qualification_report=str(path),qualification_report_sha256=sha(path),qualification_audit=str(run/'campaign-audit.json'),qualification_audit_sha256=sha(run/'campaign-audit.json'))
    state.setdefault('segment_boundaries',{})['2512']=dict(time=point['time'],UTC=point['UTC'],reason='First qualified BASE1 reading after firmware maintenance and power-cut trials; do not bridge unverified power continuity',report=str(path))
    for name in ('tools/rtc_base1_collect.py','tools/rtc_base1_audit.py','tools/build_rtc_base1.py','BUILD/rtc-base1-2512-20261029/proof.json','BUILD/rtc-base1-2512-20261029/2512-RTC-BASE1-RAM.bin','BUILD/rtc-base1-2512-20261029/sampler.bin'):
        state['dependencies'][name]=sha(ROOT/name)
    state.update(last_attempt_utc=c.NOW(),last_summary=str(run/'summary.json'),last_issues=[],last_new_PF_events=new)
    c.save(c.STATE,state);c.report(state)
    print(json.dumps({'passed':True,'accepted':point,'new_PF_events':new,'qualified_for_scheduled_collection':True},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--accept-report',type=Path,required=True);args=parser.parse_args();accept(args.accept_report)
