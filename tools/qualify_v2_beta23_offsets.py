"""Bounded fixed-offset hardware checks, exact append accounting and restoration."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from beta4_migration import Link,crc
from rtc_boards import SERIALS
from serial.tools.list_ports import comports

ROOT=Path(__file__).resolve().parents[1]

def record(offset,sequence):
    r=bytearray(b'\xff'*32);r[:4]=b'TZ\x01\0';r[4:8]=sequence.to_bytes(4,'little');r[8:10]=offset.to_bytes(2,'little',signed=True)
    r[28:30]=crc(r[:28]).to_bytes(2,'little');r[31]=0;return r

def setting(bank):
    good=[]
    for pos in range(0x1C00,0x2000,32):
        r=bank[pos:pos+32]
        if r[:4]==b'TZ\x01\0' and r[31]==0 and crc(r[:28])==int.from_bytes(r[28:30],'little'):
            offset=int.from_bytes(r[8:10],'little',signed=True)
            if -720<=offset<=840:good.append((int.from_bytes(r[4:8],'little'),offset))
    return max(good,default=(0,0))

def label(offset):
    return ('-' if offset<0 else '+')+f'{abs(offset)//60:02d}:{abs(offset)%60:02d}'

def check_time(text,offset):
    utc=re.search(rb'RTCC: UTC (\w{3} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',text)
    local=re.search(rb'RTCC: Local (\w{3} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \(([+-]\d\d:\d\d)\)',text)
    assert utc and local,text
    dt=datetime.strptime(utc[1].decode(),'%a %Y-%m-%d %H:%M:%S');want=dt+timedelta(minutes=offset)
    assert local[1].decode()==want.strftime('%a %Y-%m-%d %H:%M:%S') and local[2].decode()==label(offset)
    assert b'RESET required' not in text
    return dict(utc=dt.isoformat(),local=want.isoformat(),offset=label(offset))

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--baseline-index',type=Path,required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    model=json.loads((a.build/'local-time-test-results.json').read_text());meta=json.loads((a.build/'build.json').read_text());assert model['passed'] and model['artifacts']==meta['artifacts']
    prior=a.root/'power-check';assert json.loads((prior/'report.json').read_text())['passed']
    banks=[(prior/f'b{i}.bin').read_bytes() for i in range(4)];expected=[bytearray(b) for b in banks];sequence,original=setting(banks[3])
    offsets=[345,-210,-720,840,original];current=original
    changes=sum(x!=y for x,y in zip([original]+offsets,offsets));free=sum(banks[3][p:p+32]==b'\xff'*32 for p in range(0x1C00,0x2000,32));assert free>=changes and sequence+changes<=0xFFFFFFFF
    out=a.root/'offset-check';out.mkdir(exist_ok=False);shutil.copytree(prior/'devices-before',out/'devices-before');shutil.copytree(a.root/'sram-prior',out/'sram-prior')
    report=dict(passed=False,board=a.board,original_offset=label(original),clock_set=False,trim_changed=False,identity_accepted=False,offset_restored=False,appends=0,checks=[])
    with (out/'serial.jsonl').open('x') as log:
        l=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
            l.command('',b'> ');l.command('B3');assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                assert b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))==banks[bank],'Flash preimage changed'
            l.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',name=None):
                data=l.command(text,prompt)
                if name:(out/(name+'.txt')).write_bytes(data)
                return data
            def change(offset):
                nonlocal current,sequence
                cmd('R CLOCK',b'CLOCK> ')
                if current==offset:
                    assert b'No change.' in cmd('OFFSET '+label(offset),b'CLOCK> ')
                else:
                    assert b'UTC and clock settings stay unchanged' in cmd('OFFSET '+label(offset),b'Type YES to confirm: ')
                    data=cmd('YES',b'CLOCK> ',f'save-{report["appends"]+1}');assert ('Local UTC offset: '+label(offset)).encode() in data and b'RESET required' not in data
                    sequence+=1;pos=next(p for p in range(0x1C00,0x2000,32) if expected[3][p:p+32]==b'\xff'*32)
                    expected[3][pos:pos+32]=record(offset,sequence);report['appends']+=1;current=offset
                cmd('Q')
            cmd('R CLOCK',b'CLOCK> ')
            for i,line in enumerate(('OFFSET +14:01','OFFSET -12:01','OFFSET +05:60','OFFSET 05:30','SET 2026-02-29 00:00:00','TRIM +128')):
                data=cmd(line,b'CLOCK> ',f'invalid-{i}');assert b'Type YES' not in data and b'RESET required' not in data
            for i,answer in enumerate(('NO','Y')):
                cmd('OFFSET '+label(345 if original!=345 else -210),b'Type YES to confirm: ');assert b'Canceled' in cmd(answer,b'CLOCK> ',f'offset-cancel-{i}')
            cmd('SET 2000-01-01 00:00:00',b'Type YES to confirm: ');assert b'Canceled' in cmd('NO',b'CLOCK> ',name='set-canceled')
            cmd('TRIM +1',b'Type YES to confirm: ');assert b'Canceled' in cmd('NO',b'CLOCK> ',name='trim-canceled')
            assert b'No change.' in cmd('OFFSET '+label(original),b'CLOCK> ',name='unchanged-offset');cmd('Q')
            assert l.dump(0x9C00,0x9FFF)==banks[3][0x1C00:0x2000],'Refusal/cancellation wrote settings'
            report['cancellation_no_change_and_invalid_read_only']=True
            for i,offset in enumerate(offsets):
                change(offset);detail=cmd('TIME',name=f'time-immediate-{i}');check=check_time(detail,offset)
                start=cmd('J3',b'Enter default [3s]: ');l.send(b'\r');start+=l.until(b'\r\nB3> ');(out/f'boot-{i}.txt').write_bytes(start)
                compact=re.findall(rb'^RTCC: (\w{3} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \(([+-]\d\d:\d\d)\)',start,re.M)
                assert len(compact)==1 and compact[0][1].decode()==label(offset),'Compact boot offset mismatch'
                check_time(cmd('TIME',name=f'time-retained-{i}'),offset);assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
                report['checks'].append(check);print(a.board,'offset immediate and J3 retained',label(offset),flush=True)
            report['offset_restored']=current==original
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                data=b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));assert data==expected[bank],'Unaccounted flash change'
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest())
            l.command('B3');report.update(exercised=True,flash_hashes=hashes,firmware_and_existing_records_preserved=True,no_erase=True)
        except Exception as e:
            report['error']=repr(e)
            try:
                text=l.command('',b'> ')
                if b'CLOCK> ' in text:l.command('Q')
                l.command('B3');change(original);report['offset_restored']=True
            except Exception as recovery:report['restore_error']=repr(recovery)
        finally:l.serial.close()
    try:
        if report.get('exercised'):
            subprocess.run([sys.executable,str(ROOT/'tools/capture_v2_display_devices.py'),'--root',str(out),'--board',a.board,'--port',a.port,'--stage','after','--baseline-index',str(a.baseline_index)],check=True)
            subprocess.run([sys.executable,str(ROOT/'tools/archive_v2_edu_sram.py'),'--root',str(out),'--board',a.board,'--port',a.port,'--stage','final','--build',str(a.build)],check=True)
            report.update(rtc_eeprom_identity_preserved=True,full_sram_preserved=True,edu_mode='ON',trim_steps=0,passed=True)
    except Exception as e:report['postcheck_error']=repr(e)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
