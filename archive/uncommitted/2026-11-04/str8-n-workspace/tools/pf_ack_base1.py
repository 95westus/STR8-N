"""Explicit one-time 2512 save-before-ACK through BASE1 RAM; never scheduled."""
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'tools/rtc_base1_collect.py'
assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()=='fea08bf9f2d8cd98b76fb31e2ebf56271a329601c3af1532c69b3d9834eab92e'
source=ORIGINAL.read_text()
def change(old,new):
    global source
    assert source.count(old)==1,old
    source=source.replace(old,new)
source=source.replace('rtc-base1-2512-20261029','pf-ack-base1-2512-20261029').replace('2512-RTC-BASE1-RAM.bin','2512-PF-ACK-BASE1-RAM.bin').replace('RTC BASE1 READ ONLY> ','PF ACK BASE1> ').replace('BASE1-RTC-RAM1','BASE1-PF-ACK1')
change('and len(image)==1733','and len(image)==2804')
change("ROOT/'tools/build_rtc_base1.py'","ROOT/'tools/build_pf_ack_base1.py'")
change("with serial_lease('drift',timeout=30):","with serial_lease('drift',timeout=1200):")
change("r['passed']=bool(r.get('acquisition_passed') and r['application_ram_restored'] and r.get('port_released'))","r['passed']=bool(r.get('acquisition_passed') and r.get('PF_ACK_verified') and r['application_ram_restored'] and r.get('port_released'))")
operation=r'''
            # Preserve every existing committed record; only a clean empty slot may be appended.
            before=r['readings'][-1];ee=(folder/'pf-eeprom-0.bin').read_bytes()
            assert ee==(folder/'pf-eeprom-1.bin').read_bytes()
            assert r['eui'].replace(':','').lower()=='5410ecb6743c'
            assert all(s['raw'][7:9]==[0x80,0x0c] for s in r['readings'])
            r.update(PF_latched_before=bool(before['flags']&8),before_readings=list(r['readings']),before_offset_bounds_s=list(r['rtc_minus_reference_interval_s']))
            if r['PF_latched_before']:
                outage=bytes(before['outage']);assert any(outage)
                assert all(s['flags']&31==31 and bytes(s['outage'])==outage for s in r['readings'])
                rows=[ee[n*32:n*32+32] for n in range(4)]
                for n,row in enumerate(rows):
                    assert row[:8]==b'PF\x01'+bytes([n+1])+b'JR\x20\xa5'
                    assert crc(row[:28])==int.from_bytes(row[28:30],'little') and row[31] in (0,165)
                slots=[n for n,row in enumerate(rows) if row[31]==0 and not any(row[8:28])]
                assert slots,'No clean empty PF slot; preserve all existing history and do not ACK'
                slot=slots[0];seq=max(int.from_bytes(row[8:12],'little') for row in rows)+1;assert seq<2**32
                cal=bytearray(before['calendar']);cal[4]|=0xe0
                record=bytearray(b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5'+seq.to_bytes(4,'little')+outage+cal)
                record+=crc(record).to_bytes(2,'little')+b'\xff\xa5';record=bytes(record);assert len(record)==32
                request=b'PAK1'+bytes([slot,0,0x80,0x0c])+outage+record+ee;request+=crc(request).to_bytes(2,'little');assert len(request)==178
                (folder/'request.bin').write_bytes(request);(folder/'new-PF-record.bin').write_bytes(record)
                save(folder/'intent.json',dict(recorded_utc=now(),PF_slot=slot+1,PF_sequence=seq,old_row=list(rows[slot]),outage=list(outage),before_RTC=before,existing_history_sha256=digest(ee),action='Append to empty owned PF slot, verify, then ACK RTC and verify acknowledgment marker',UTC_SET=False,trim_changed=False))
                print('2512: saving PF event in empty MCP EEPROM slot',slot+1,'sequence',seq,'before ACK',flush=True)
                client.send(b'T');client.paced(request);client.until(PROMPT)
                status,_,_=packet(b'C',4);(folder/'commit-status.bin').write_bytes(status)
                assert status[:2]==b'\0\1','PF commit failed: no ACK issued; do not automatically retry'
                expected=bytearray(ee);expected[32*slot:32*slot+32]=record
                for n in range(2):
                    captured,_,_=packet(b'H',256);assert captured[0]==0 and captured[128:]==expected
                    (folder/f'EEPROM-committed-{n}.bin').write_bytes(captured[128:])
                save(folder/'log-committed.json',dict(passed=True,recorded_utc=now(),slot=slot+1,sequence=seq,EEPROM_sha256=digest(expected),record_sha256=digest(record),outage_preserved_before_ACK=True))
                r.update(PF_log_committed=True,PF_slot=slot+1,PF_sequence=seq);checkpoint()
                print('2512: PF history committed and double-verified; acknowledging latch once',flush=True)
                status,_,_=packet(b'A',4);(folder/'ACK-status.bin').write_bytes(status)
                assert status[:2]==b'\0\3','ACK not verified; stop and inspect, do not retry automatically'
                expected[32*slot+30]=0
                for n in range(2):
                    captured,_,_=packet(b'H',256);assert captured[0]==0 and captured[128:]==expected
                    (folder/f'EEPROM-after-{n}.bin').write_bytes(captured[128:])
                r.update(PF_ACK_verified=True,PF_latched_after=False,existing_PF_records_preserved=True)
            else:
                r.update(PF_ACK_verified=True,PF_latched_after=False,no_op_already_clear=True,existing_PF_records_preserved=True)
            r['readings']=[]
            for n in range(9):
                if n:time.sleep(.137+n*.031)
                data,first,last=packet(b'R',64);(folder/f'after-{n}.bin').write_bytes(data)
                assert data[0]==0 and data[1]&31==23 and not any(data[20:28])
                item=dict(status=data[0],flags=data[1],calendar=list(data[2:10]),raw=list(data[11:20]),outage=list(data[20:28]),evidence_valid=data[28],captured_outage=list(data[48:56]),reference_start_utc=iso(first),reference_end_utc=iso(last),reference_start_unix=first,reference_end_unix=last,bracket_seconds=last-first)
                rtc=decoded(data);item.update(rtc_utc=iso(rtc),rtc_unix=rtc,rtc_minus_reference_interval_s=[rtc-last-ref.uncertainty,rtc+1-first+ref.uncertainty])
                assert item['raw'][7:9]==before['raw'][7:9] and item['raw'][3]&15==before['raw'][3]&15
                r['readings'].append(item);checkpoint()
            low=max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']);high=min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']);assert low<=high
            assert max(low,r['before_offset_bounds_s'][0])<=min(high,r['before_offset_bounds_s'][1]),'UTC continuity not verified'
            last=r['readings'][-1];r.update(rtc_minus_reference_interval_s=[low,high],baseline_reference_unix=(last['reference_start_unix']+last['reference_end_unix'])/2,UTC_continuity_verified=True,trim_control_unchanged=True,outage_timestamps_cleared=True)
            r['baseline_reference_utc']=iso(r['baseline_reference_unix'])
            ident,_,_=packet(b'I',7);assert ident==identity
            r['EUI_preserved']=True;checkpoint()
'''
change("            r['final_reference_check']=reference_sample();check=r['final_reference_check']",operation+"\n            r['final_reference_check']=reference_sample();check=r['final_reference_check']")
source=source.replace('no MON, reset or NVM writer','no MON, reset, time setter or flash writer').replace('BASE1 RAM-only read-only RTC/PF/EUI','BASE1 owner-authorized save-before-ACK RTC/PF/EUI').replace('PASS 2512 BASE1','PASS 2512 BASE1 PF SAVE/ACK')
namespace=dict(__name__='pf_ack_live_base1',__file__=str(Path(__file__).resolve()))
exec(compile(source,str(Path(__file__).resolve()),'exec'),namespace)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--preflight',action='store_true');group.add_argument('--execute',action='store_true');args=parser.parse_args()
    namespace['inputs']()
    if args.preflight:print('PASS explicit 2512 BASE1 save-before-ACK admission; no board port opened')
    else:
        out=ROOT/'output/qualification'/datetime.now(timezone.utc).strftime('pf-ack-base1-2512-%Y%m%dT%H%M%SZ')
        result=namespace['collect'](out)
        (out/'adapted-driver.py').write_text(source,encoding='utf-8')
        (out/'owner-authorization.json').write_text(json.dumps(dict(owner_authorized=True,user_text='ack pf on 2512, preserve the pf history, and continue the 3 hour drift collection on all boards. keep time and trim unchanged.',PF_ACK_only=True,UTC_SET=False,trim_changed=False,scheduled_ACK=False),indent=2)+'\n')
        print('ACK_REPORT',out,flush=True)
