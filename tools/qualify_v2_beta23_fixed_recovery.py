"""Read-only fixed F recovery after endurance; preserve every retained byte."""
import argparse,hashlib,json,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from beta4_migration import Link
from rtc_boards import SERIALS
from serial.tools.list_ports import comports

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--baseline-index',type=Path,required=True);p.add_argument('--wait-endurance',action='store_true');a=p.parse_args()
    model=json.loads((a.build/'fixed-recovery-test-results.json').read_text());meta=json.loads((a.build/'build.json').read_text());assert model['passed'] and model['artifacts']==meta['artifacts']
    prior=a.root/'endurance';receipt=prior/'report.json';end=datetime(2026,10,10,2,48,tzinfo=timezone.utc).timestamp()
    if a.wait_endurance:
        print(a.board,'queued fixed-recovery checks after endurance closes its port',flush=True)
        while not receipt.exists():
            assert time.time()<end,'Recovery start cutoff reached; no port opened'
            time.sleep(.2)
    assert json.loads(receipt.read_text())['passed'],'Endurance did not pass; no port opened'
    assert time.time()<end,'Recovery start cutoff reached; no port opened'
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    banks=[(prior/f'b{i}.bin').read_bytes() for i in range(4)]
    out=a.root/'fixed-recovery-check';out.mkdir(exist_ok=False);shutil.copytree(prior/'devices-after',out/'devices-before');shutil.copytree(a.root/'sram-prior',out/'sram-prior')
    report=dict(passed=False,board=a.board,clock_set=False,trim_changed=False,flash_written=False,sram_written=False,checks=[])
    with (out/'serial.jsonl').open('x') as log:
        l=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
            l.command('',b'> ');l.command('B3')
            assert l.dump(0xC000,0xDFFF)==banks[3][0x4000:0x6000],'Wear/configuration preimage changed'
            for slot in ('A','B'):
                text=l.command('J3',b'Enter default [3s]: ');l.send(b'S');text+=l.until(b'REC> ')
                (out/f'entry-{slot}.txt').write_bytes(text);assert b'FIXED F RECOVERY' in text
                wear=l.command('W',b'REC> ');(out/f'wear-{slot}.txt').write_bytes(wear)
                text=l.command(slot);(out/f'return-{slot}.txt').write_bytes(text)
                assert l.dump(meta['boot']['BOOT_ACTIVE'],meta['boot']['BOOT_ACTIVE'])==bytes([0xA0 if slot=='A' else 0xB0])
                assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64' and l.dump(0x66AE,0x66AF)==b'\x01\0'
                text=l.command('TIME');(out/f'time-{slot}.txt').write_bytes(text);assert b'RTCC: UTC' in text
                report['checks'].append('forced S / W wear / '+slot+' return / services and cold session')
                print(a.board,'fixed F recovery and return through',slot,'passed',flush=True)
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                data=b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));assert data==banks[bank],'Recovery changed flash'
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest())
            l.command('B3');report.update(exercised=True,flash_hashes=hashes)
        except Exception as e:
            report['error']=repr(e)
            try:
                text=l.command('',b'> ')
                if b'REC> ' in text:l.command('A')
                l.command('B3')
            except Exception as recovery:report['return_error']=repr(recovery)
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
