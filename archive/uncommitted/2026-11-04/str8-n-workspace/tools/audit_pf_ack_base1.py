"""File-only audit and campaign bookkeeping for explicit one-time 2512 PF ACK."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
from rtc_base1_audit import crc,digest


def audit(folder):
    folder=Path(folder).resolve();r=c.read(folder/'report.json');state=c.read(c.STATE);root=Path(state['root'])
    assert r['passed'] and r['capture_profile']=='BASE1-PF-ACK1'
    assert all(r[k] for k in ('PF_ACK_verified','application_ram_restored','returned_to_original_REC','port_released','UTC_continuity_verified','trim_control_unchanged','outage_timestamps_cleared','EUI_preserved'))
    assert not any(r[k] for k in ('clock_set_attempted','trim_changed','flash_written'))
    assert r['driver_sha256']==c.sha(ROOT/'tools/pf_ack_base1.py')
    build=ROOT/'BUILD/pf-ack-base1-2512-20261029';proof=c.read(build/'proof.json')
    assert proof['passed'] and len(proof['checks'])==13 and all(p['passed'] for p in proof['checks'])
    assert r['client_sha256']==proof['sha256']==c.sha(build/'2512-PF-ACK-BASE1-RAM.bin')
    assert r['client_proof_sha256']==c.sha(build/'proof.json') and r['eui'].replace(':','').lower()=='5410ecb6743c'
    before=c.read(folder/'marker-before.json')
    for bank in range(4):
        blobs=[(folder/f'flash-{label}-{n}-b{bank}.bin').read_bytes() for label in ('before','after') for n in (1,2)]
        assert len(blobs[0])==32768 and all(b==blobs[0] for b in blobs)
        assert digest(blobs[0])==before['current_physical_bank_sha256'][f'B{bank}']
    ram=(folder/'owner-ram-before.bin').read_bytes();zp=(folder/'owner-zp-before.bin').read_bytes()
    assert ram==(folder/'owner-ram-restored.bin').read_bytes() and len(ram)==0x6500
    assert zp==(folder/'owner-zp-restored.bin').read_bytes() and len(zp)==224
    assert digest(ram)==r['RAM_sha256'] and digest(zp)==r['ZP_sha256']
    assert (folder/'final-REC.txt').read_bytes().endswith(b'REC> ')
    records=list(map(json.loads,(folder/'serial.jsonl').read_text().splitlines()))
    tx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='TX')
    rx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='RX');assert rx.endswith(b'REC> ')
    reader=(ROOT/'release/str8nf-v0.2.0/firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();image=(build/'2512-PF-ACK-BASE1-RAM.bin').read_bytes()
    flashes=b''.join(b'F'+bytes([b]) for n in (1,2) for b in (3,0,1,2))
    restore=b'W'+ram+crc(ram).to_bytes(2,'little')+b'Y'+zp+crc(zp).to_bytes(2,'little')+b'MZQ'
    ee=(folder/'pf-eeprom-0.bin').read_bytes();assert ee==(folder/'pf-eeprom-1.bin').read_bytes()
    if not r.get('no_op_already_clear'):
        assert r['PF_log_committed'] and r['PF_latched_before'] and r['existing_PF_records_preserved']
        slot=r['PF_slot']-1;record=(folder/'new-PF-record.bin').read_bytes();request=(folder/'request.bin').read_bytes()
        assert 0<=slot<4 and len(record)==32 and len(request)==178
        assert ee[slot*32+31]==0 and not any(ee[slot*32+8:slot*32+28]),'Existing PF history overwritten'
        assert record[:8]==b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5' and crc(record[:28])==int.from_bytes(record[28:30],'little')
        assert record[12:20]==bytes(r['before_readings'][-1]['outage']) and record[30:]==b'\xff\xa5'
        assert crc(request[:-2])==int.from_bytes(request[-2:],'little') and request[:4]==b'PAK1'
        assert request[16:48]==record and request[48:176]==ee and request[6:8]==b'\x80\x0c'
        committed=bytearray(ee);committed[32*slot:32*slot+32]=record
        assert all((folder/f'EEPROM-committed-{n}.bin').read_bytes()==committed for n in range(2))
        assert c.read(folder/'log-committed.json')['EEPROM_sha256']==digest(committed)
        final=bytearray(committed);final[32*slot+30]=0
        assert all((folder/f'EEPROM-after-{n}.bin').read_bytes()==final for n in range(2))
        assert (folder/'commit-status.bin').read_bytes()[:2]==b'\0\1' and (folder/'ACK-status.bin').read_bytes()[:2]==b'\0\3'
        mutation=b'T'+request+b'CHHAHH'
    else:mutation=b'';final=ee
    expected=b'\rC1\rL\r'+reader+b'MMZZ'+flashes+restore+b'C1\rL\r'+image+b'MMZIH'+b'R'*9+b'H'+mutation+b'R'*9+b'I'+flashes+restore
    assert tx==expected,'Unexpected operation in complete serial TX trace'
    for label,samples in (('before',r['before_readings']),('after',r['readings'])):
        assert len(samples)==9
        for sample in samples:
            cal=sample['calendar'];date=datetime(cal[0]+256*cal[1],cal[2],cal[3],cal[5],cal[6],cal[7],tzinfo=timezone.utc)
            assert date.timestamp()==sample['rtc_unix'] and date.isoweekday()==cal[4]
            assert date.date()==datetime.fromtimestamp(sample['reference_end_unix'],timezone.utc).date()
            assert sample['raw'][7:9]==[128,12] and sample['flags']&7==7
            if label=='after':assert sample['flags']&31==23 and not any(sample['outage'])
    lo,hi=r['rtc_minus_reference_interval_s'];assert [lo,hi]==[max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']),min(x['rtc_minus_reference_interval_s'][1] for x in r['readings'])]
    assert max(lo,r['before_offset_bounds_s'][0])<=min(hi,r['before_offset_bounds_s'][1])
    assert abs(r['final_reference_difference_s'])<=r['reference_uncertainty_s']+r['final_reference_check']['estimated_reference_uncertainty_s']
    lease_observed=c.read(c.Q/'serial-coordination/owner.json')
    events=[];active=0
    for n in range(4):
        row=final[32*n:32*n+32]
        assert row[:8]==b'PF\x01'+bytes([n+1])+b'JR\x20\xa5' and crc(row[:28])==int.from_bytes(row[28:30],'little')
        if row[31]==165:
            active+=1
            if row[24]&128 and any(row[12:20]):events.append(c.outage(row[12:20],r['baseline_reference_unix']))
    point=dict(board='2512',time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,offset=(lo+hi)/2,trim=-12,control=128,PF_latched=False,active_PF_records=active,events=events,report=str(folder/'report.json'),report_sha256=c.sha(folder/'report.json'),capture_profile='BASE1-PF-ACK1',purpose='Owner-authorized one-time PF ACK; post-ACK reads only in this point')
    points=c.read(root/'points.json');history=c.read(root/'events.json')
    if not any(p['board']=='2512' and p['time']==point['time'] for p in points):points.append(point)
    for e in events:
        e=dict(e,board='2512')
        if not any(x['board']==e['board'] and x['down']==e['down'] and x['up']==e['up'] for x in history):history.append(e)
    c.save(root/'points.json',points);c.save(root/'events.json',history)
    item=dict(board='2512',report=str(folder/'report.json'),sha256=c.sha(folder/'report.json'),offset=[lo,hi],trim=-12,RAM_restored=True,capture_profile='BASE1-PF-ACK1')
    summary=dict(passed=True,started_utc=r['started_utc'],finished_utc=r['finished_utc'],boards=[item],failures=[],clock_set=False,trim_changed=False,explicit_ACK_sent=not r.get('no_op_already_clear',False),flash_writer=False,ports_released=True,purpose='Explicit one-time ACK; never an automatic campaign action')
    c.save(folder/'summary.json',summary)
    result=dict(passed=True,PF_latch_clear=True,PF_history_preserved=True,PF_slot=r.get('PF_slot'),PF_sequence=r.get('PF_sequence'),existing_history_records_not_overwritten=True,log_double_verified_before_ACK=True,UTC_continuity_verified=True,time_set=False,trim_changed=False,flash_changed=False,full_RAM_ZP_restored=True,original_REC_restored=True,ports_released=True,serial_lease_observed_after_release=lease_observed,serial_trace_exactly_matches_authorized_operations=True,summary_sha256=c.sha(folder/'summary.json'),issues=[],new_PF_events=[])
    c.save(folder/'campaign-audit.json',result);c.save(folder/'audit.json',result)
    state.setdefault('manual_PF_ACKs',[]).append(dict(board='2512',audit=str(folder/'audit.json'),audit_sha256=c.sha(folder/'audit.json'),clock_set=False,trim_changed=False,power_cycle=False,segment_boundary_unchanged=True))
    state.update(last_attempt_utc=c.NOW(),last_summary=str(folder/'summary.json'),last_issues=[],last_new_PF_events=[])
    c.save(c.STATE,state);c.report(state)
    mpath=c.Q/'device-operations/2512.json';m=c.read(mpath);m.update(PF_latched=False,PF_ack_verified=True,last_PF_ack=str(folder/'report.json'),last_PF_ack_audit=str(folder/'audit.json'),last_one_shot_RTC_evidence=str(folder/'report.json'));c.save(mpath,m)
    text=f"2512 PF latch acknowledged. Event preserved in MCP EEPROM PF journal slot {r.get('PF_slot')}, sequence {r.get('PF_sequence')}, with its acknowledgment marker verified. Existing history retained. UTC continuity and trim -12 verified unchanged; all flash banks and RAM/ZP preserved. Returned to REC>; ports released. Three-hour read-only collection remains active on all four boards.\n"
    (folder/'report.md').write_text(text,encoding='utf-8')
    c.save(folder/'manifest.json',{p.name:c.sha(p) for p in folder.iterdir() if p.is_file() and p.name!='manifest.json'})
    print(json.dumps(result,indent=2));print('REPORT',folder/'report.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);audit(parser.parse_args().folder)
