"""One owner-authorized RTC recovery on 2609; no firmware or host memory reads."""
import hashlib,json,math,re,sys,time
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from rtc_utc_baseline import Reference,ntp_sample,iso
from atomic_json import publish

ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
OUT=Q/'2609-RTC-owner-recovery-2026-10-18-r1'
HELPER=ROOT/'tmp/rcv2609e';KIT=ROOT/'tmp/bf1-distribution-r10/migration'
ARCHIVE=Q/'2609-windows-migration-backup-2026-10-18-r1/restore-application-ram.s19'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PROMPT=b'CLOCK> '

def raw_status(text):
    match=re.search(rb'RTC registers \(raw\): ((?:[0-9A-F]{2} ){9})',text)
    assert match,'No complete RTC status'
    return bytes.fromhex(match[1].decode())

def rtc_epoch(raw):
    def bcd(v):
        assert v&15<=9 and v>>4<=9
        return (v>>4)*10+(v&15)
    assert raw[0]&128 and raw[3]&32 and raw[3]&8
    return datetime(2000+bcd(raw[6]),bcd(raw[5]&31),bcd(raw[4]&63),
        bcd(raw[2]&63),bcd(raw[1]&127),bcd(raw[0]&127),tzinfo=timezone.utc).timestamp()

def load_no_readback(link,path,entry):
    link.send(b'L\r');time.sleep(.2)
    for row in path.read_bytes().splitlines():
        link.send(row+b'\r\n');time.sleep(.04)
    text=link.until(b'\r\nB3> ',seconds=60)
    assert f'Entry {entry:04X}'.encode() in text
    assert not any(word in text for word in (b'Bad',b'Protected',b'Wrap',b'Error'))
    return text

def main():
    assert not OUT.exists();OUT.mkdir()
    active=read(Q/'active-rtc-campaign.json');baseline=Path(active['baseline_index'])
    assert sha(baseline)==active['baseline_index_sha256']
    assert set(active['powered_off_boards'])=={'2205','2512'}
    initial=next(b for b in read(baseline)['boards'] if b['board']=='2609')
    assert initial['trim_steps']==-14 and initial['control_register']==128
    model=read(HELPER/'report.json');assert model['passed'] and model['cases']==6
    assert sha(HELPER/'control-recovery.s19')==model['image_sha256']
    assert sha(ARCHIVE)=='8c77399ab303aaec0aae467863a6ff00b28035f54b4ee5ae654bf1df3a98e1f0'
    sys.path.insert(0,str(KIT));import legacy_transport as wire
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['state']=='RTC-inspection-required' and guard['block_snapshot']
    ports=[p for p in comports() if p.serial_number==SERIALS['2609']]
    assert len(ports)==1 and ports[0].device=='COM8'
    authorization=dict(board='2609',owner_authorized=True,
        owner_reply='could wdcmonv2 65c816 have affected the clock? sync and set trim based on the trim set initially',
        preceding_question='Recover stopped RTC using fresh NIST UTC, restart oscillator/backup, restore recorded control $80 and trim -14',
        scope='One RTC recovery and a separate measurement segment; original baseline and evidence retained',
        trim_steps=-14,control_register=128,recorded_utc=iso(time.time()))
    publish(OUT/'owner-authorization.json',authorization)
    publish(OUT/'previous-guard.json',guard)
    guard.update(state='RTC-owner-recovery',reason='Owner authorized NIST sync and original trim/control recovery',run=str(OUT))
    publish(marker,guard)
    report=dict(board='2609',passed=False,mode='owner-authorized RTC continuity recovery',
        clock_set_attempted=False,trim_changed=False,firmware_written=False,host_memory_readbacks=False,
        original_baseline_index=str(baseline),original_baseline_sha256=sha(baseline),
        control_helper_report_sha256=sha(HELPER/'report.json'),owner_authorization_sha256=sha(OUT/'owner-authorization.json'),
        reference_samples=[],readings=[],original_application_RAM_written=False,application_RAM_host_verified=False)
    def save():publish(OUT/'report.json',report)
    save();link=None;in_clock=False
    try:
        for i in range(3):
            if i:time.sleep(4)
            report['reference_samples'].append(ntp_sample('132.163.96.6'));save()
        reference=Reference(report['reference_samples']);report['reference_uncertainty_s']=reference.uncertainty
        with (OUT/'serial.jsonl').open('x') as log:
            link=wire.Link(ports[0].device,log);establish_b3(link)
            version=link.command('VERSION');(OUT/'version.txt').write_bytes(version)
            assert b'2.0bf1' in version and b'65C816' in version and b'Board: 2609' in version
            link.command('R CLOCK',PROMPT);in_clock=True
            before=link.command('STATUS',PROMPT);(OUT/'status-before.txt').write_bytes(before)
            assert raw_status(before)==bytes(9),'Unexpected changed RTC; inspect before SET'
            target=math.ceil(reference.now()+4)
            command='SET '+datetime.fromtimestamp(target,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            link.command(command,b'Type YES to confirm: ')
            assert target-reference.now()>.1,'Missed target; no SET confirmation sent'
            report.update(requested_rtc_utc=iso(target),scheduled_set_reference_unix=target);save()
            while reference.now()<target:time.sleep(min(.01,max(.001,target-reference.now())))
            report['clock_set_attempted']=True;report['set_reference_start_unix']=reference.now();save()
            result=link.command('YES',PROMPT);(OUT/'set-result.txt').write_bytes(result)
            assert b'SET completed.' in result and b'SET failed' not in result
            report['set_reference_end_unix']=reference.now();save();time.sleep(2)
            link.command('TRIM -14',b'Type YES to confirm: ')
            result=link.command('YES',PROMPT);(OUT/'trim-result.txt').write_bytes(result)
            assert b'Trim -14 steps; coarse OFF; OSCTRIM $0E' in result
            report['trim_changed']=True;save()
            check=link.command('STATUS',PROMPT);raw=raw_status(check)
            assert raw[8]==14 and raw[7]==0;rtc_epoch(raw)
            link.command('Q');in_clock=False
            publish(OUT/'restore-needed.json',dict(needed=True,verified=False,source=str(ARCHIVE),sha256=sha(ARCHIVE)))
            load_no_readback(link,HELPER/'control-recovery.s19',model['entry'])
            result=link.command(f'G {model["entry"]:04X}');(OUT/'control-result.txt').write_bytes(result)
            assert b'RTC CONTROL STATUS 00' in result,'Fixed control helper failed; inspect evidence'
            link.command('R CLOCK',PROMPT);in_clock=True
            for i in range(8):
                time.sleep((.2,.65,.4,.85)[i%4]);first=reference.now()
                text=link.command('STATUS',PROMPT);last=reference.now();raw=raw_status(text);epoch=rtc_epoch(raw)
                assert raw[7:9]==bytes([128,14])
                (OUT/f'status-{i+1}.txt').write_bytes(text)
                report['readings'].append(dict(status=0,raw=list(raw),rtc_unix=epoch,
                    reference_start_unix=first,reference_end_unix=last,reference_end_utc=iso(last),
                    rtc_minus_reference_interval_s=[epoch-last-reference.uncertainty,epoch+1-first+reference.uncertainty]))
                save()
            assert report['readings'][-1]['rtc_unix']>report['readings'][0]['rtc_unix']
            low=max(s['rtc_minus_reference_interval_s'][0] for s in report['readings'])
            high=min(s['rtc_minus_reference_interval_s'][1] for s in report['readings']);assert low<=high
            final=ntp_sample('132.163.96.6')
            difference=final['host_receive_unix']+final['server_minus_host_s']+time.monotonic()-final['receive_monotonic']-reference.now()
            assert abs(difference)<=reference.uncertainty+final['estimated_reference_uncertainty_s']
            report.update(baseline_reference_unix=report['readings'][-1]['reference_end_unix'],
                baseline_reference_utc=report['readings'][-1]['reference_end_utc'],rtc_minus_reference_interval_s=[low,high],
                clock_advanced=True,trim_steps=-14,control_register=128,backup_enabled=True,oscillator_running=True,
                final_reference_check=final,final_reference_difference_s=difference)
            save();link.command('Q');in_clock=False
            load_no_readback(link,ARCHIVE,0x200)
            report.update(original_application_RAM_written=True,loader_acknowledged=True,
                passed=True,finished_utc=iso(time.time()),ports_released=True)
            publish(OUT/'restore-needed.json',dict(needed=False,verified=False,write_completed=True,
                source=str(ARCHIVE),sha256=sha(ARCHIVE),host_readback_disabled_by_owner=True))
            save()
    except Exception as error:
        report['error']=str(error);save();raise
    finally:
        if link:link.serial.close()
        report['ports_released']=True;save()
    # Keep the board guarded until the new comparison segment is registered.
    guard.update(state='RTC-recovered-segment-registration',reason='RTC recovered; register separate segment before sampling',
        application_RAM_restore_written=True,application_RAM_restore_verified=False,recovery_report=str(OUT/'report.json'))
    publish(marker,guard)
    print('PASS 2609 NIST sync; trim -14/control $80 restored, RTC advancing and backup enabled; separate segment registration pending')

if __name__=='__main__':main()
