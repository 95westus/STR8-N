"""Read-only post-power qualification against retained owner-local snapshots."""
import argparse,hashlib,json,re,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from beta4_migration import Link,crc
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request
from rtc_boards import SERIALS
from serial.tools.list_ports import comports

ROOT=Path(__file__).resolve().parents[1]

def calendar(path):
    match=re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',path.read_bytes())
    assert match,'No valid calendar capture'
    return datetime.strptime(match[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()

def records(data):
    good={}
    for slot in range(4):
        r=data[slot*32:(slot+1)*32]
        if r[:8]==b'PF\x01'+bytes([slot+1])+b'JR\x20\xa5' and r[31]==0xA5 and crc(r[:28])==int.from_bytes(r[28:30],'little'):
            good[slot]=int.from_bytes(r[8:12],'little')
    return good

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--baseline-index',type=Path,required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/'power-check';out.mkdir(exist_ok=False)
    report=dict(passed=False,board=a.board,clock_set=False,trim_changed=False,flash_written=False,sram_written=False,explicit_ack=False,identity_accepted=False)
    try:
        subprocess.run([sys.executable,str(ROOT/'tools/capture_v2_display_devices.py'),'--root',str(out),'--board',a.board,'--port',a.port,'--stage','before','--baseline-index',str(a.baseline_index)],check=True)
        old=a.root/'devices-before';now=out/'devices-before'
        assert (old/'eui.txt').read_bytes()==(now/'eui.txt').read_bytes(),'Identity or binding changed'
        before=(old/'eeprom-0.bin').read_bytes()[:137];after=(now/'eeprom-0.bin').read_bytes()[:137]
        assert before[128:]==after[128:],'Factory/status bytes changed'
        changed=[i for i in range(4) if before[i*32:(i+1)*32]!=after[i*32:(i+1)*32]]
        previous=records(before);current=records(after)
        if b'History unavailable/error 90' in (old/'history.txt').read_bytes():
            assert not changed,'Foreign EEPROM history modified'
            assert b'PF logging failed.' in (a.root.parent/'power-return'/(a.board+'-boot.txt')).read_bytes()
            assert b'Power-fail latched: yes' in (now/'status.txt').read_bytes()
            report['journal_behavior']='foreign layout preserved; power-fail latch retained'
        else:
            assert len(changed)==1,'Expected exactly one outage record update'
            slot=changed[0];assert slot in current and current[slot]==max(previous.values(),default=0)+1
            if len(previous)==4:assert slot==min(previous,key=previous.get),'Unexpected ring slot overwritten'
            else:assert before[slot*32:(slot+1)*32]==b'\xff'*32,'Expected unused journal slot'
            assert after[slot*32+30]==0,'Startup acknowledgement not durable'
            assert b'Power-fail latched: no' in (now/'status.txt').read_bytes()
            report.update(journal_behavior='one verified outage record; automatic startup acknowledgement',new_sequence=current[slot],updated_slot=slot+1,unchanged_slots=[i+1 for i in range(4) if i!=slot])
        old_log=[json.loads(x) for x in (old/'serial.jsonl').read_text().splitlines()]
        new_log=[json.loads(x) for x in (now/'serial.jsonl').read_text().splitlines()]
        rtc_elapsed=calendar(now/'status.txt')-calendar(old/'status.txt')
        host_elapsed=new_log[0]['time']-old_log[0]['time']
        assert rtc_elapsed>0 and abs(rtc_elapsed-host_elapsed)<5,'RTC continuity differs from elapsed host time'
        report.update(rtc_elapsed_s=rtc_elapsed,host_elapsed_s=host_elapsed,identity_preserved=True,trim_control_preserved=True,factory_status_preserved=True)
        with (out/'serial.jsonl').open('x') as log:
            l=Link(a.port,log)
            try:
                stop=time.monotonic()+.3
                while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
                l.command('',b'> ');l.command('B3')
                assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
                session=l.dump(0x66AE,0x66AF);assert session==b'\x01\0','Cold-reset session not cleared'
                report['cold_workspace_session']=session.hex()
                original=(a.root/'sram-prior/array-0.bin').read_bytes();assert original==(a.root/'sram-prior/array-1.bin').read_bytes()
                load_image(l,a.build/'hardware-client/client.s19');parts=[]
                for block in range(16):
                    write(l,0x3E20,b'\x01\x03\0');write(l,0x3E00,memory_request(1,block*8192));l.command('G 2003')
                    r=l.dump(0x3E10,0x3E38);assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    part=l.dump(0x4000,0x5FFF);assert part==original[block*8192:(block+1)*8192],'SRAM retention mismatch'
                    parts.append(part);print(a.board,'power-retained SRAM',block+1,'/16',flush=True)
                image=b''.join(parts);(out/'sram-retained.bin').write_bytes(image);report['sram_sha256']=hashlib.sha256(image).hexdigest()
                hashes=[]
                for bank in range(4):
                    prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                    data=b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096))
                    assert data==(a.root/'standalone-register-probe'/f'b{bank}.bin').read_bytes(),'Flash retention mismatch'
                    (out/f'b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest());print(a.board,'power-retained flash bank',bank,flush=True)
                l.command('B3');report.update(flash_hashes=hashes,edu_mode='ON',trim_steps=0,monitor_ready=True,passed=True)
            finally:l.serial.close()
    except Exception as e:report['error']=repr(e);raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('RESULT',a.board,json.dumps(report),flush=True)

if __name__=='__main__':main()
