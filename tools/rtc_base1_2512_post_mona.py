"""Post-Mona 2512 admission; unchanged qualified read/load/restore driver and RAM binary."""
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
import rtc_base1_collect as d
import rtc_base1_audit as a
Q=ROOT/'output/qualification'
RECEIPT=Q/'2512-mona-monab-20261029-r1/final-receipt.json'
RECEIPT_SHA='dce84d476e75f08c1077bd2b5ad9253c2e04edd90271b29ac93b328045c75a9f'
PROFILE='BASE1-RTC-RAM1'
original_inputs=d.inputs

def inputs():
    marker,old_receipt,meta,bodies,proof,image,reader,banks=original_inputs()
    assert c.sha(RECEIPT)==RECEIPT_SHA
    r=c.read(RECEIPT)
    assert marker['state']=='BASE1-Mona-A-B-trial-passed-original-images-restored'
    latest=Q/'2512-mona-g2-rtcc-20261029-r1/final-receipt.json'
    assert c.sha(latest)=='bcf08e228e4267f7b9fa6a18bb84e6c66b5e1194373b8a0b6af655127565b6af'
    assert Path(marker['last_preservation_report']).resolve()==latest.resolve()
    g=c.read(latest)
    assert g['passed'] and g['original_owner_RAM_ZP_restored'] and g['COM4_released'] and g['final_context']=='REC>'
    assert g['flash_writes']==g['journal_writes']==g['F_writes']==g['power_cuts']==0
    assert g['before_bank_sha256']==g['after_bank_sha256']==r['final_bank_sha256']
    assert g['owner_restore']['RAM_sha256']==r['RAM_sha256'] and g['owner_restore']['ZP_sha256']==r['ZP_sha256']
    for name,expected in g['evidence_sha256'].items():
        assert c.sha(latest.parent/name)==expected, name
    assert r['passed'] and r['board']=='2512' and r['CPU']=='65C02'
    assert all(r[k] for k in ('original_A_B_restored','original_owner_images_preserved','boot_settings_preserved','owner_RAM_restored','owner_ZP_restored','COM4_released','old_records_retained_exactly'))
    assert r['final_context']=='REC>' and r['F_writes']==0 and r['C_D_erases']==0 and r['power_cuts']==0
    assert r['foundation']['F_sha256']==d.F_SHA
    assert d.digest(bodies['owner-ram.bin'])==r['RAM_sha256']
    assert d.digest(bodies['owner-zp.bin'])==r['ZP_sha256']
    assert banks==r['original_bank_sha256'] and banks[:3]==r['final_bank_sha256'][:3]
    for name,expected in r['evidence_sha256'].items():
        assert c.sha(RECEIPT.parent/name)==expected, name
    banks=r['final_bank_sha256']
    marker=dict(marker,current_physical_bank_sha256={f'B{n}':v for n,v in enumerate(banks)},
                current_journal_sequence=r['journal_after']['sequence'],
                current_journal_valid_records=r['journal_after']['valid_records'])
    return marker,RECEIPT,meta,bodies,proof,image,reader,banks

d.inputs=inputs

def collect(folder):
    r=d.collect(folder)
    c.save(Path(folder)/'post-maintenance-authority.json',dict(receipt=str(RECEIPT),sha256=RECEIPT_SHA,adapter_sha256=c.sha(__file__),frozen_driver_sha256=c.sha(ROOT/'tools/rtc_base1_collect.py'),no_RAM_binary_changes=True))
    return r

def audit_board(item,state):
    p=a.audit_board(item,state)
    r=c.read(item['report'])
    assert r['initial_qualified_receipt_sha256']==RECEIPT_SHA
    authority=c.read(Path(item['report']).parent/'post-maintenance-authority.json')
    assert authority['adapter_sha256']==c.sha(__file__)
    return p

def accept(path):
    path=Path(path).resolve()
    with d.serial_lease('drift',timeout=30):
        state=c.read(c.STATE);r=c.read(path)
        item=dict(board='2512',report=str(path),sha256=c.sha(path),offset=r['rtc_minus_reference_interval_s'],trim=r['trim_steps'],RAM_restored=True,capture_profile=PROFILE)
        point=audit_board(item,state);root=Path(state['root']);run=path.parent.parent
        points=c.read(root/'points.json');events=c.read(root/'events.json');new=[]
        if not any(p['board']=='2512' and p['time']==point['time'] for p in points): points.append(point)
        for event in point['events']:
            event=dict(event,board='2512')
            if event['up']>=state['baselines']['2512']['time']-120 and not any(e['board']=='2512' and e['down']==event['down'] and e['up']==event['up'] for e in events):
                events.append(event);new.append(event)
        summary=dict(passed=True,started_utc=r['started_utc'],finished_utc=r['finished_utc'],boards=[item],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=False,flash_writer=False,ports_released=True)
        c.save(run/'summary.json',summary)
        c.save(run/'campaign-audit.json',dict(passed=True,issues=[],new_PF_events=new,summary_sha256=c.sha(run/'summary.json'),serial_trace_exact_read_load_restore_only=True,post_Mona_receipt_sha256=RECEIPT_SHA))
        marker=c.read(d.MARK)
        state['board_admission']['2512']={k:marker.get(k) for k in state['board_admission']['2512']}
        state['base1_profile'].update(post_mona=True,qualification_report=str(path),qualification_report_sha256=c.sha(path),qualification_audit=str(run/'campaign-audit.json'),qualification_audit_sha256=c.sha(run/'campaign-audit.json'))
        state['dependencies']['tools/rtc_base1_2512_post_mona.py']=c.sha(__file__)
        state.setdefault('segment_boundaries',{})['2512']=dict(time=point['time'],UTC=point['UTC'],reason='First qualified post-Mona collection; resets during maintenance, do not bridge unverified continuity',report=str(path))
        state.update(last_attempt_utc=c.NOW(),last_summary=str(run/'summary.json'),last_issues=[],last_new_PF_events=new)
        c.save(root/'points.json',points);c.save(root/'events.json',events);c.save(c.STATE,state);c.report(state)
    print('PASS 2512 post-Mona admission and exact serial audit',path,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--collect',action='store_true');p.add_argument('--out',type=Path);p.add_argument('--accept-report',type=Path);args=p.parse_args()
    if args.accept_report: accept(args.accept_report)
    else:
        inputs()
        if args.collect: collect(args.out)
        else: print('PASS post-Mona inputs; no ports opened')


