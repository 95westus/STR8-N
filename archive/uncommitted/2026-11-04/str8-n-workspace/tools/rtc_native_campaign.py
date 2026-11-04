"""Read-only native MON TIME/NTP campaign. No RAM BIN or board write command."""
import argparse,ast,contextlib,hashlib,json,math,os,socket,struct,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];KIT=ROOT/'release/str8nf-v0.2.0'
sys.path[:0]=[str(KIT/'tools'),str(ROOT/'tools'),str(ROOT/'tmp/migration-python')]
from time_samples import SerialMonitor
from serial_test_coordination import serial_lease,sharing_retry
NTP_EPOCH=2208988800
SOURCE=ROOT/'tmp/phase13-history/tools/rtc_utc_baseline.py'
# Reuse only the established read-only NTP request function, never its SET path.
tree=ast.parse(SOURCE.read_text());names={'iso','ntp_sample_once'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
assert {n.name for n in nodes}==names
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),globals())
utc=lambda:datetime.now(timezone.utc).isoformat(timespec='milliseconds')
sha=lambda b:hashlib.sha256(b).hexdigest()

def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    sharing_retry(lambda:os.replace(tmp,path))

def append(stream,value):
    stream.write(json.dumps(value)+'\n');stream.flush();os.fsync(stream.fileno())

def run(folder,interval=60):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=False)
    state=dict(board='2512',port='COM4',USB_serial='A10MQFLCA',pid=os.getpid(),active=True,
        started_utc=utc(),interval_seconds=interval,samples=0,valid_RTC_samples=0,NTP_queries=0,
        NTP_query_attempts=0,consecutive_NTP_failures=0,
        flash_writes=0,SRAM_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,RAM_BINs=0,
        F_frozen=True,other_boards_accessed=False,serial_port_open=False,
        collector_sha256=sha(Path(__file__).read_bytes()),TIME_transport_sha256=sha((KIT/'tools/time_samples.py').read_bytes()),
        NTP_source_sha256=sha(SOURCE.read_bytes()),NTP_server='132.163.96.6',NTP_refresh_seconds=300,
        comparison_assumption='Board calendar interpreted as UTC only for comparison; no clock or zone setting changed.',
        pending_installation='Paused by owner: no B2/E installation or C rotation during collection.')
    save(folder/'state.json',state)
    save(folder/'control.json',dict(interval_seconds=interval,stop=False))
    (folder/'ntp-readonly-source.py').write_text(ast.unparse(ast.Module(body=nodes,type_ignores=[]))+'\n')
    (folder/'TIME-transport-source.py').write_bytes((KIT/'tools/time_samples.py').read_bytes())
    marker=ROOT/'output/qualification/device-operations/2512.json'
    original=json.loads(marker.read_text());save(folder/'device-marker-before.json',original)
    assert not original['application_RAM_restore_pending'] and original['final_prompt']=='B3>'
    reference=None;due=time.monotonic();failures=0
    try:
      with (folder/'samples.jsonl').open('x',encoding='utf-8',newline='\n') as samples, (folder/'ntp.jsonl').open('x',encoding='utf-8',newline='\n') as ntp:
        while True:
            control=json.loads((folder/'control.json').read_text())
            if control.get('stop'):state['stop_reason']='Owner control file';break
            interval=float(control['interval_seconds'])
            if not math.isfinite(interval) or interval<1:raise ValueError('Positive finite interval >=1 second required')
            now=time.monotonic()
            if now<due:time.sleep(min(1,due-now));continue
            row=dict(board='2512',port='COM4',host_request_utc=utc(),sequence=state['samples']+1)
            # One bounded UDP reference query; failure does not erase RTC data
            # or trigger a resync. Cached-anchor age is explicit in every row.
            if reference is None or interval>=300 or now-reference['receive_monotonic']>=300:
                state['NTP_query_attempts']+=1
                try:
                    candidate=ntp_sample_once(state['NTP_server']);candidate['collected_utc']=utc()
                    packet=bytes.fromhex(candidate['packet_hex'])
                    assert packet[32:40]!=bytes(8) and packet[40:48]!=bytes(8)
                    append(ntp,dict(status='accepted',**candidate));reference=candidate
                    state['NTP_queries']+=1;state['consecutive_NTP_failures']=0
                    state['last_NTP_UTC']=reference['reference_utc_at_receive']
                except (OSError,AssertionError) as error:
                    append(ntp,dict(status='unavailable',utc=utc(),error=repr(error)))
                    row['NTP_error']=repr(error);state['consecutive_NTP_failures']+=1
            try:
                # Priority is held only during the read, not the sleep. No
                # other board is opened, and occupied COM4 is never taken over.
                with serial_lease('drift',timeout=10,priority=True):
                    with SerialMonitor('COM4',115200,'A10MQFLCA') as monitor:
                        state['serial_port_open']=True;save(folder/'state.json',state)
                        start=time.monotonic();row['host_request_utc']=utc()
                        reply=monitor.exchange(b'TIME\r');end=time.monotonic()
                state['serial_port_open']=False
                raw=reply.decode('ascii',errors='replace').replace('\r','')
                from time_samples import RTC
                match=RTC.search(raw);board=None
                if match:
                    try:board=datetime.fromisoformat(match[1])
                    except ValueError:pass
                row.update(host_received_utc=utc(),acquisition_bracket_seconds=end-start,raw_reply=raw,
                    board_time=board.isoformat() if board else None,board_zone=None,
                    status='sample' if board else 'RTC_unavailable')
                if reference:
                    anchor=reference['host_receive_unix']+reference['server_minus_host_s']
                    a=anchor+start-reference['receive_monotonic'];b=anchor+end-reference['receive_monotonic']
                    uncertainty=reference['estimated_reference_uncertainty_s']
                    row.update(NTP_reference_utc_start=iso(a),NTP_reference_utc_end=iso(b),
                        NTP_reference_age_seconds=end-reference['receive_monotonic'],
                        NTP_query_uncertainty_seconds=uncertainty,
                        NTP_server=reference['server'],NTP_address=reference['address'],NTP_stratum=reference['stratum'],
                        reference_projection='Monotonic projection from last accepted UDP sample; aging/frequency error is not included in query uncertainty.')
                    if board:
                        rtc=board.replace(tzinfo=timezone.utc).timestamp()
                        row['RTC_minus_NTP_interval_if_UTC_s']=[rtc-b-uncertainty,rtc+1-a+uncertainty]
                if board:state['valid_RTC_samples']+=1
                failures=0
            except Exception as error:
                state['serial_port_open']=False;failures+=1
                row.update(status='acquisition_error',error=repr(error),host_received_utc=utc())
            append(samples,row);state['samples']+=1;state['last_sample']=row
            state.update(interval_seconds=interval,last_update_utc=utc(),consecutive_serial_failures=failures)
            save(folder/'state.json',state)
            print(row['sequence'],row['status'],row.get('board_time'),row.get('RTC_minus_NTP_interval_if_UTC_s'),flush=True)
            if failures>=3:state['stop_reason']='Three failed acquisitions; no takeover or reset';break
            due+=interval
            if due<=time.monotonic():due=time.monotonic()+interval
    except BaseException as error:
        state.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        state.update(active=False,serial_port_open=False,finished_utc=utc());save(folder/'state.json',state)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--interval',type=float,default=60);args=parser.parse_args();run(args.folder,args.interval)
