"""Bounded four-board qualification load; no flash, UTC, trim or device writes."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from beta4_migration import Link,read_s19
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from qualify_v2_spi_install import load_image
from qualify_v2_spi_storage import memory_request

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--baseline-index',type=Path,required=True);p.add_argument('--until-utc',required=True);p.add_argument('--attempt',default='');a=p.parse_args()
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    deadline=datetime.fromisoformat(a.until_utc.replace('Z','+00:00')).timestamp();assert 0<deadline-time.time()<7200
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    for name in ('offset-check','storage-faults-cold'):assert json.loads((a.root/name/'report.json').read_text())['passed'],name
    expected=[(a.root/'offset-check'/f'b{i}.bin').read_bytes() for i in range(4)]
    original=(a.root/'sram-prior/array-0.bin').read_bytes();assert original==(a.root/'sram-prior/array-1.bin').read_bytes()
    probes=ROOT/'BUILD/v2-board-regression';meta=json.loads((probes/'build.json').read_text())['probes'];service=json.loads((probes/'service-build.json').read_text())
    def probe_hash(name):
        cells,_=read_s19(probes/(name+'.s19'));return hashlib.sha256(bytes(cells[x] for x in sorted(cells))).hexdigest()
    for name in ('abi','irq'):assert probe_hash(name)==meta[name]['sha256']
    assert probe_hash('service')==service['sha256']
    out=a.root/('endurance'+a.attempt);out.mkdir(exist_ok=False);shutil.copytree(a.root/'offset-check/devices-after',out/'devices-before');shutil.copytree(a.root/'sram-prior',out/'sram-prior')
    report=dict(passed=False,board=a.board,started_utc=datetime.now(timezone.utc).isoformat(),rounds=0,rtc_bank_calls=0,sram_bank_reads=0,abi_irq_pairs=0,cold_starts=0,clock_set=False,trim_changed=False,flash_written=False,sram_written=False,full_soak=False)
    with (out/'serial.jsonl').open('x') as log:
        l=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
            l.command('',b'> ');l.command('B3');vectors=l.dump(0x7E00,0x7E1B)
            last_rtc=None;last_host=None
            while time.time()<deadline:
                started=time.monotonic();n=report['rounds']
                assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
                load_image(l,probes/'service.s19');text=l.command('G 200C');assert b'RTC banks preserved' in text and l.dump(0x2450,0x2453)==bytes(4);report['rtc_bank_calls']+=4
                load_image(l,a.build/'hardware-client/client.s19')
                for bank in range(4):
                    address=((n*977+bank*8191)%(len(original)-64))
                    l.write_ram(0x3E20,bytes((1,bank,0)));l.write_ram(0x3E00,memory_request(1,address,64,0x4000));l.command('G 2000')
                    r=l.dump(0x3E10,0x3E38);assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    assert l.dump(0x4000,0x403F)==original[address:address+64];report['sram_bank_reads']+=1
                text=l.command('TIME');m=re.search(rb'RTCC: UTC \w{3} (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',text);assert m
                now=datetime.strptime(m[1].decode(),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp();host=time.time()
                if last_rtc is not None:assert now>last_rtc and abs((now-last_rtc)-(host-last_host))<3,'UTC continuity changed'
                last_rtc=now;last_host=host
                if n%4==0:
                    for name,needle in (('abi',b'RAM ABI: PASS'),('irq',b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS')):
                        load_image(l,probes/(name+'.s19'));assert needle in l.command('G 2000')
                    assert l.dump(0x7E00,0x7E1B)==vectors;report['abi_irq_pairs']+=1
                if n%12==0:
                    slot='A' if (n//12)%2==0 else 'B';text=l.command('J3',b'Enter default [3s]: ');l.send(slot.encode());text+=l.until(b'\r\nB3> ')
                    assert b'STR8-N 2.0b23' in text and l.dump(0x66AE,0x66AF)==b'\x01\0';report['cold_starts']+=1
                    (out/f'boot-{n:04d}-{slot}.txt').write_bytes(text)
                quiet=l.command('M1');assert b'B3:8-F protected.' in quiet
                assert not any(x in quiet for x in (b'STR8-N ',b'ABI ',b'RAM $',b'EDU ON',b'RTCC:',b'SSRAM:')),'Ordinary return became noisy'
                assert l.dump(0x7E00,0x7E1B)==vectors
                report['rounds']+=1;report['last_verified_utc']=datetime.now(timezone.utc).isoformat()
                (out/'progress.json').write_text(json.dumps(report,indent=2)+'\n')
                print(a.board,'round',report['rounds'],'RTC calls',report['rtc_bank_calls'],'SRAM reads',report['sram_bank_reads'],'ABI/IRQ',report['abi_irq_pairs'],'cold starts',report['cold_starts'],flush=True)
                delay=min(max(0,15-(time.monotonic()-started)),max(0,deadline-time.time()))
                if delay:time.sleep(delay)
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                image=b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));assert image==expected[bank],'Flash changed during endurance checks'
                (out/f'b{bank}.bin').write_bytes(image);hashes.append(hashlib.sha256(image).hexdigest())
            l.command('B3');report.update(exercised=True,flash_hashes=hashes,ended_load_utc=datetime.now(timezone.utc).isoformat())
        except Exception as e:report['error']=repr(e)
        finally:l.serial.close()
    try:
        if report.get('exercised'):
            subprocess.run([sys.executable,str(ROOT/'tools/capture_v2_display_devices.py'),'--root',str(out),'--board',a.board,'--port',a.port,'--stage','after','--baseline-index',str(a.baseline_index)],check=True)
            subprocess.run([sys.executable,str(ROOT/'tools/archive_v2_edu_sram.py'),'--root',str(out),'--board',a.board,'--port',a.port,'--stage','final','--build',str(a.build)],check=True)
            report.update(passed=True,full_sram_preserved=True,rtc_eeprom_identity_preserved=True,edu_mode='ON',trim_steps=0,monitor_ready=True)
    except Exception as e:report['postcheck_error']=repr(e)
    report['ended_utc']=datetime.now(timezone.utc).isoformat();(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
