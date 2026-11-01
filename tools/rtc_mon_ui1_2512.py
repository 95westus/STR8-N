"""2512 installed MON UI/1 gA native TIME/NIST sampler: no RAM upload or NVM writes."""
import sys,json,re,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import rtc_drift_campaign as c
import rtc_base1_collect as b
PROFILE='MON-UI1-NATIVE-TIME'
MARK=ROOT/'output/qualification/device-operations/2512.json'
PROMPT=b'B3> '
def inputs():
    m=c.read(MARK)
    assert m['firmware']=='STR8N-F 0.3.0 BASE1 PR05' and m['current_F_sha256']==b.F_SHA
    assert m['final_prompt']=='B3>' and not m.get('block_snapshot')
    assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
    assert not any(m.get(k) for k in ('owner_application_running','application_RAM_restore_pending','physical_reset_pending','one_shot_collection_active'))
    assert m.get('monitor_generation')=='0000000A' and m.get('native_utilities_installation_complete')
    return m

def collect(folder):
    inputs();folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    r=dict(board='2512',port='COM4',usb_serial='A10MQFLCA',capture_profile=PROFILE,passed=False,started_utc=c.NOW(),clock_set_attempted=False,trim_changed=False,flash_written=False,PF_ACK=False,PF_history_written=False,RAM_uploaded=False,trim_freshly_read=False,PF_history_freshly_read=False,readings=[],driver_sha256=c.sha(__file__))
    def save():c.save(folder/'report.json',r)
    save()
    try:
      with b.serial_lease('drift',timeout=30):
        inputs()
        refs=[]
        for n in range(3):
            if n:time.sleep(4)
            refs.append(b.ntp_sample('132.163.96.6'))
        ref=b.Reference(refs);r.update(reference_samples=refs,reference_uncertainty_s=ref.uncertainty)
        with (folder/'serial.jsonl').open('x',encoding='utf-8') as log:
          link=b.transport.RecoveryLink('COM4',log,usb_serial='A10MQFLCA')
          try:
            link.send(b'\r');link.until(PROMPT,seconds=15)
            link.send(b'V\r');version=link.until(PROMPT,seconds=15);(folder/'VERSION.txt').write_bytes(version)
            identity=re.search(rb'g0000000A / MON ([AB])',version);assert identity,'Installed MON gA/UI1 required; no TIME sent'
            r['monitor_slot']=identity[1].decode()
            for n in range(9):
                if n:time.sleep(.137+n*.031)
                start=ref.now();link.send(b'TIME\r');face=link.until(PROMPT,seconds=20);end=ref.now()
                (folder/f'TIME-{n}.txt').write_bytes(face)
                match=re.search(rb'RTCC: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2})',face)
                assert match and b'/ MON ' not in face
                dt=datetime.strptime(match[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                assert dt.date()==datetime.fromtimestamp(end,timezone.utc).date(),'Calendar mismatch'
                flags=int(match[2],16)
                r['readings'].append(dict(rtc_utc=dt.isoformat(),rtc_unix=dt.timestamp(),reference_start_unix=start,reference_end_unix=end,flags=flags,PF_latched=bool(flags&16),rtc_minus_reference_interval_s=[dt.timestamp()-end-ref.uncertainty,dt.timestamp()+1-start+ref.uncertainty]));save()
            last=b.ntp_sample('132.163.96.6')
            difference=last['host_receive_unix']+last['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+last['receive_monotonic']-ref.best['receive_monotonic'])
            assert abs(difference)<=ref.uncertainty+last['estimated_reference_uncertainty_s']
            lo=max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']);hi=min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']);assert lo<=hi
            r.update(passed=True,rtc_minus_reference_interval_s=[lo,hi],baseline_reference_unix=(start+end)/2,baseline_reference_utc=b.iso((start+end)/2),trim_steps=c.read(c.STATE)['baselines']['2512']['trim'],control_register=c.read(c.STATE)['baselines']['2512']['control'],PF_latched=bool(flags&16),final_reference_check=last,final_reference_difference_s=difference,returned_to_original_prompt=True,application_ram_restored=True,original_RAM_untouched=True)
          finally:link.close();r['port_released']=True
      r['finished_utc']=c.NOW();save()
      print('PASS 2512 native TIME',r['baseline_reference_utc'],r['rtc_minus_reference_interval_s'],'B3>; no RAM upload',flush=True)
      return r
    except BaseException as e:r.update(passed=False,error=repr(e),finished_utc=c.NOW());save();raise

def audit_board(item,state):
    path=Path(item['report']);folder=path.parent;r=c.read(path)
    assert c.sha(path)==item['sha256'] and r['passed'] and r['driver_sha256']==c.sha(__file__)
    assert r['capture_profile']==PROFILE and r['usb_serial']=='A10MQFLCA' and r['port']=='COM4'
    assert all(r[k] for k in ('returned_to_original_prompt','port_released','original_RAM_untouched'))
    assert not any(r[k] for k in ('clock_set_attempted','trim_changed','flash_written','PF_ACK','PF_history_written','RAM_uploaded'))
    records=list(map(json.loads,(folder/'serial.jsonl').read_text().splitlines()))
    tx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='TX')
    rx=b''.join(bytes.fromhex(x['hex']) for x in records if x['direction']=='RX')
    assert tx==b'\rV\r'+b'TIME\r'*9 and rx.endswith(PROMPT)
    assert len(r['readings'])==9 and r['readings'][-1]['rtc_unix']>r['readings'][0]['rtc_unix']
    assert len(r['reference_samples'])==3 and all(x['stratum']==1 for x in r['reference_samples']+[r['final_reference_check']])
    for x in r['readings']:
        assert datetime.fromtimestamp(x['rtc_unix'],timezone.utc).date()==datetime.fromtimestamp(x['reference_end_unix'],timezone.utc).date()
    lo,hi=r['rtc_minus_reference_interval_s']
    assert lo==max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']) and hi==min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']) and lo<=hi
    return dict(board='2512',time=r['baseline_reference_unix'],UTC=r['baseline_reference_utc'],low=lo,high=hi,offset=(lo+hi)/2,trim=r['trim_steps'],control=r['control_register'],trim_verified=False,PF_history_freshly_read=False,PF_latched=r['PF_latched'],active_PF_records=None,events=[],report=str(path),report_sha256=c.sha(path),capture_profile=PROFILE)

if __name__=='__main__':
    inputs();print('PASS native MON TIME admission; no port opened')

