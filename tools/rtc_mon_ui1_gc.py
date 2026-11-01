"""Opt-in gC native TIME sampler; no RAM upload or persistent device writes.

Prepared for the reviewed STATUS installation. Inactive until its exact profile
is admitted in campaign state. Historical gB/g8 drivers remain unchanged.
"""
import json,re,time
from pathlib import Path
from datetime import datetime,timezone
import rtc_drift_campaign as c
import rtc_base1_collect as b
PROFILE='MON-UI1-GC-NATIVE-TIME'
PROMPT=b'B3> ';REC=b'REC> '
IDENTITIES={'2512':('COM4','A10MQFLCA',b'CPU: 65C02'),
            '2609':('COM8','A10MPQXCA',b'CPU: 65C816 emulation')}

def inputs(board):
    assert board in IDENTITIES
    m=c.read(c.Q/f'device-operations/{board}.json')
    assert m['firmware']=='STR8N-F 0.3.0 BASE1 PR05' and m['current_F_sha256']==b.F_SHA
    assert m['monitor_generation']=='0000000C' and m.get('status_installation_complete')
    assert not m.get('application_RAM_restore_pending') and m['application_ram_restored']
    assert not m.get('physical_reset_pending') and not any(v for k,v in m.items() if k.endswith('_worker_active'))
    assert m['final_prompt']==('B3>' if board=='2512' else 'REC>')
    return m

def collect(board,folder):
    inputs(board);folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    port,usb,cpu=IDENTITIES[board]
    r=dict(board=board,port=port,usb_serial=usb,capture_profile=PROFILE,passed=False,
        started_utc=c.NOW(),driver_sha256=c.sha(__file__),readings=[],clock_set_attempted=False,
        trim_changed=False,flash_written=False,PF_ACK=False,PF_history_written=False,RAM_uploaded=False,
        trim_freshly_read=False,PF_history_freshly_read=False,original_RAM_untouched=True)
    def save():c.save(folder/'report.json',r)
    save();entered=False
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
            link.send(b'\r');link.until(PROMPT if board=='2512' else REC,seconds=15)
            if board=='2609':link.send(b'B\r');link.until(PROMPT,seconds=20);entered=True
            link.send(b'V\r');version=link.until(PROMPT,seconds=20);(folder/'VERSION.txt').write_bytes(version)
            identity=re.search(rb'g0000000C / MON ([AB])',version);assert identity and cpu in version
            r['monitor_slot']=identity[1].decode()
            for n in range(9):
                if n:time.sleep(.137+n*.031)
                start=ref.now();link.send(b'TIME\r');face=link.until(PROMPT,seconds=20);end=ref.now()
                (folder/f'TIME-{n}.txt').write_bytes(face)
                match=re.search(rb'RTCC: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2})',face)
                assert match and b'/ MON ' not in face
                date=datetime.strptime(match[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                assert date.date()==datetime.fromtimestamp(end,timezone.utc).date()
                flags=int(match[2],16)
                r['readings'].append(dict(rtc_utc=date.isoformat(),rtc_unix=date.timestamp(),
                    reference_start_unix=start,reference_end_unix=end,flags=flags,PF_latched=bool(flags&16),
                    rtc_minus_reference_interval_s=[date.timestamp()-end-ref.uncertainty,date.timestamp()+1-start+ref.uncertainty]));save()
            last=b.ntp_sample('132.163.96.6')
            difference=last['host_receive_unix']+last['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+last['receive_monotonic']-ref.best['receive_monotonic'])
            assert abs(difference)<=ref.uncertainty+last['estimated_reference_uncertainty_s']
            lo=max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']);hi=min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']);assert lo<=hi
            base=c.read(c.STATE)['baselines'][board]
            r.update(passed=True,rtc_minus_reference_interval_s=[lo,hi],baseline_reference_unix=(start+end)/2,
                baseline_reference_utc=b.iso((start+end)/2),trim_steps=base['trim'],control_register=base['control'],
                PF_latched=bool(flags&16),final_reference_check=last,final_reference_difference_s=difference,
                application_ram_restored=True)
          finally:
            try:
                if entered:link.send(b'Q\r');link.until(REC,seconds=15);r['returned_to_original_REC']=True
                r['returned_to_original_prompt']=True
            finally:link.close();r['port_released']=True
      r['finished_utc']=c.NOW();save();return r
    except BaseException as error:r.update(passed=False,error=repr(error),finished_utc=c.NOW());save();raise

def audit_board(item,state):
    path=Path(item['report']);folder=path.parent;r=c.read(path);board=item['board']
    port,usb,_=IDENTITIES[board]
    assert c.sha(path)==item['sha256'] and r['passed'] and r['driver_sha256']==c.sha(__file__)
    assert r['board']==board and r['port']==port and r['usb_serial']==usb and r['capture_profile']==PROFILE
    assert all(r[k] for k in ('returned_to_original_prompt','port_released','original_RAM_untouched','application_ram_restored'))
    assert not any(r[k] for k in ('clock_set_attempted','trim_changed','flash_written','PF_ACK','PF_history_written','RAM_uploaded'))
    records=list(map(json.loads,(folder/'serial.jsonl').read_text().splitlines()))
    tx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='TX')
    rx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='RX')
    expected=b'\r'+(b'B\r' if board=='2609' else b'')+b'V\r'+b'TIME\r'*9+(b'Q\r' if board=='2609' else b'')
    assert tx==expected and rx.endswith(REC if board=='2609' else PROMPT)
    if board=='2609':assert r['returned_to_original_REC']
    assert len(r['readings'])==9 and r['readings'][-1]['rtc_unix']>r['readings'][0]['rtc_unix']
    assert len(r['reference_samples'])==3 and all(x['stratum']==1 for x in r['reference_samples']+[r['final_reference_check']])
    for x in r['readings']:
        assert datetime.fromtimestamp(x['rtc_unix'],timezone.utc).date()==datetime.fromtimestamp(x['reference_end_unix'],timezone.utc).date()
    lo,hi=r['rtc_minus_reference_interval_s']
    assert lo==max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']) and hi==min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']) and lo<=hi
    base=state['baselines'][board];assert r['trim_steps']==base['trim'] and r['control_register']==base['control']
    return dict(board=board,time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,
        offset=(lo+hi)/2,trim=base['trim'],control=base['control'],trim_verified=False,
        PF_history_freshly_read=False,PF_latched=r['PF_latched'],active_PF_records=None,events=[],
        report=str(path),report_sha256=c.sha(path),capture_profile=PROFILE)
