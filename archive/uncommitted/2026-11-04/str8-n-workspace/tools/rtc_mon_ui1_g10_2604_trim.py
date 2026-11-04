"""MON g10 TIME: fresh clock/control/trim on both BASE1 boards, no RAM upload."""
import json,re,time
from datetime import datetime,timezone
from pathlib import Path
import rtc_drift_campaign as c
import rtc_base1_collect as b

PROFILE='MON-UI1-G10-2604-TIME-TRIM'
PROMPT=b'B3> ';REC=b'REC> '
IDENTITIES={'2604':('COM5','A10MQGVHA',b'CPU: 65C02'),
            '2609':('COM8','A10MPQXCA',b'CPU: 65C816 emulation')}
TIME_RE=rb'RTCC: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2}) trim \$([0-9A-F]{2}) ctrl \$([0-9A-F]{2})'


def parse_time(face):
    m=re.search(TIME_RE,face)
    assert m and b'/ MON ' not in face,'No fresh g10 TIME control/trim sample'
    raw,control=int(m[3],16),int(m[4],16)
    return dict(rtc_utc=m[1].decode(),rtc_unix=datetime.strptime(m[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp(),
                flags=int(m[2],16),trim_raw=raw,trim_steps=raw&127 if raw&128 else -(raw&127),
                control_register=control,coarse_trim=bool(control&4))


def inputs(board):
    assert board=='2604' and board in IDENTITIES
    m=c.read(c.Q/f'device-operations/{board}.json')
    assert m['firmware']=='STR8N-F 0.3.0 BASE1 PR05' and m['current_F_sha256']==b.F_SHA
    assert m['monitor_generation']=='00000010' and m.get('status_installation_complete')
    assert m['application_ram_restored'] and not m.get('application_RAM_restore_pending')
    assert not m.get('physical_reset_pending') and not m.get('mon_trim_installation_pending')
    assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
    assert m['final_prompt'] in ('B3>','REC>')
    return m


def collect(board,folder):
    inputs(board);folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    port,usb,cpu=IDENTITIES[board]
    r=dict(board=board,port=port,usb_serial=usb,capture_profile=PROFILE,passed=False,
           started_utc=c.NOW(),driver_sha256=c.sha(__file__),readings=[],clock_set_attempted=False,
           trim_changed=False,flash_written=False,PF_ACK=False,PF_history_written=False,RAM_uploaded=False,
           trim_freshly_read=False,control_freshly_read=False,PF_history_freshly_read=False,original_RAM_untouched=True)
    def save():c.save(folder/'report.json',r)
    save();entered=False;known_prompt=False
    try:
      with b.serial_lease('drift',timeout=30):
        inputs(board);refs=[]
        for n in range(3):
            if n:time.sleep(4)
            refs.append(b.ntp_sample('132.163.96.6'))
        ref=b.Reference(refs);r.update(reference_samples=refs,reference_uncertainty_s=ref.uncertainty)
        with (folder/'serial.jsonl').open('x',encoding='utf-8') as log:
          link=b.transport.RecoveryLink(port,log,usb_serial=usb)
          try:
            link.send(b'\r');initial=link.until(b'> ',seconds=15);(folder/'initial-prompt.txt').write_bytes(initial)
            original=REC if initial.endswith(REC) else PROMPT if initial.endswith(PROMPT) else None
            assert original is not None,'Leave active apps alone; TIME collection requires REC> or B3>'
            known_prompt=True;r['original_prompt']=original.decode().strip()
            if original==REC:link.send(b'B\r');link.until(PROMPT,seconds=20);entered=True
            link.send(b'V\r');version=link.until(PROMPT,seconds=20);(folder/'VERSION.txt').write_bytes(version)
            slot=re.search(rb'STR8-N MON ([AB])  gen 00000010',version);assert slot and cpu in version
            r['monitor_slot']=slot[1].decode()
            for n in range(9):
                if n:time.sleep(.137+n*.031)
                start=ref.now();link.send(b'TIME\r');face=link.until(PROMPT,seconds=20);end=ref.now()
                (folder/f'TIME-{n}.txt').write_bytes(face);row=parse_time(face)
                assert datetime.fromtimestamp(row['rtc_unix'],timezone.utc).date()==datetime.fromtimestamp(end,timezone.utc).date()
                row.update(reference_start_unix=start,reference_end_unix=end,PF_latched=bool(row['flags']&16),
                           rtc_minus_reference_interval_s=[row['rtc_unix']-end-ref.uncertainty,row['rtc_unix']+1-start+ref.uncertainty])
                r['readings'].append(row);save()
            assert len({(x['trim_raw'],x['control_register']) for x in r['readings']})==1,'Trim/control changed during burst'
            last=b.ntp_sample('132.163.96.6')
            difference=last['host_receive_unix']+last['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+last['receive_monotonic']-ref.best['receive_monotonic'])
            assert abs(difference)<=ref.uncertainty+last['estimated_reference_uncertainty_s']
            lo=max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']);hi=min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']);assert lo<=hi
            live=r['readings'][-1]
            r.update(passed=True,rtc_minus_reference_interval_s=[lo,hi],baseline_reference_unix=(start+end)/2,
                     baseline_reference_utc=b.iso((start+end)/2),trim_steps=live['trim_steps'],trim_raw=live['trim_raw'],
                     control_register=live['control_register'],coarse_trim=live['coarse_trim'],
                     PF_latched=live['PF_latched'],final_reference_check=last,final_reference_difference_s=difference,
                     application_ram_restored=True,trim_freshly_read=True,control_freshly_read=True)
          finally:
            try:
                if entered:link.send(b'Q\r');link.until(REC,seconds=15);r['returned_to_original_REC']=True
                r['returned_to_original_prompt']=known_prompt
            finally:link.close();r['port_released']=True
      r['finished_utc']=c.NOW();save();return r
    except BaseException as error:r.update(passed=False,error=repr(error),finished_utc=c.NOW());save();raise


def audit_board(item,state):
    assert item['board']=='2604'
    path=Path(item['report']);folder=path.parent;r=c.read(path);board=item['board']
    port,usb,_=IDENTITIES[board]
    assert c.sha(path)==item['sha256'] and r['passed'] and r['driver_sha256']==c.sha(__file__)
    assert r['board']==board and r['port']==port and r['usb_serial']==usb and r['capture_profile']==PROFILE
    assert all(r[k] for k in ('returned_to_original_prompt','port_released','original_RAM_untouched',
                             'application_ram_restored','trim_freshly_read','control_freshly_read'))
    assert not any(r[k] for k in ('clock_set_attempted','trim_changed','flash_written','PF_ACK','PF_history_written','RAM_uploaded'))
    log=list(map(json.loads,(folder/'serial.jsonl').read_text().splitlines()))
    tx=b''.join(bytes.fromhex(x['hex']) for x in log if x['direction']=='TX')
    rx=b''.join(bytes.fromhex(x['hex']) for x in log if x['direction']=='RX')
    assert r['original_prompt'] in ('REC>','B3>');entered=r['original_prompt']=='REC>'
    assert tx==b'\r'+(b'B\r' if entered else b'')+b'V\r'+b'TIME\r'*9+(b'Q\r' if entered else b'')
    assert rx.endswith(REC if entered else PROMPT)
    assert (folder/'initial-prompt.txt').read_bytes().endswith(REC if entered else PROMPT)
    assert len(r['readings'])==9 and r['readings'][-1]['rtc_unix']>r['readings'][0]['rtc_unix']
    assert len(r['reference_samples'])==3 and all(x['stratum']==1 for x in r['reference_samples']+[r['final_reference_check']])
    for n,row in enumerate(r['readings']):
        decoded=parse_time((folder/f'TIME-{n}.txt').read_bytes())
        assert all(row[k]==v for k,v in decoded.items())
        assert row['trim_steps']==r['trim_steps'] and row['control_register']==r['control_register'] and row['trim_raw']==r['trim_raw']
    lo,hi=r['rtc_minus_reference_interval_s']
    assert lo==max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']) and hi==min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']) and lo<=hi
    # Values are admitted observations, never copied from the immutable baseline.
    return dict(board=board,time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,
                offset=(lo+hi)/2,trim=r['trim_steps'],control=r['control_register'],trim_raw=r['trim_raw'],
                trim_verified=True,control_verified=True,coarse_trim=r['coarse_trim'],
                PF_history_freshly_read=False,PF_latched=r['PF_latched'],active_PF_records=None,events=[],
                report=str(path),report_sha256=c.sha(path),capture_profile=PROFILE)
