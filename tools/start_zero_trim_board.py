"""Explicitly authorized EDU activation and zero normal trim; no UTC SET here."""
import argparse,json,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--enable-edu',action='store_true');p.add_argument('--attempt',default='');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    out=a.root/a.board/('zero-trim'+a.attempt);out.mkdir(parents=True,exist_ok=False)
    report=dict(board=a.board,edu_enabled=False,trim_zero_attempted=False,clock_set=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            original_command=link.command
            def aligned_command(text,prompt=b'\r\nB3> '):
                reply=original_command(text,prompt)
                while text and text.encode('ascii')+b'\r\n' not in reply:
                    reply+=link.until(prompt)
                return reply
            link.command=aligned_command
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            link.command('',b'> ');link.command('B3')
            descriptor=link.dump(0x7D04,0x7D0B);report['prior_service_descriptor']=descriptor.hex()
            if descriptor==b'SV\x01\0\0\0\xff\x66':
                assert a.enable_edu,'EDU is OFF; explicit activation flag required'
                (out/'edu-start.txt').write_bytes(link.command('R EDU',b'EDU> '))
                (out/'edu-request.txt').write_bytes(link.command('ON',b'Apply after RESET? [y/N]: '))
                saved=link.command('Y',b'EDU> ');(out/'edu-saved.txt').write_bytes(saved);assert b'Saved; RESET required.' in saved
                link.command('Q');boot=link.command('J3',b'Enter default [3s]: ');link.send(b'\r');boot+=link.until(b'\r\nB3> ')
                (out/'edu-cold-start.txt').write_bytes(boot);report['edu_enabled']=True
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            (out/'clock-start.txt').write_bytes(link.command('R CLOCK',b'CLOCK> '))
            for command in ('STATUS','HISTORY','EUI'):
                (out/('before-'+command.lower()+'.txt')).write_bytes(link.command(command,b'CLOCK> '))
            report['trim_zero_attempted']=True
            requested=link.command('TRIM 0',b'Type YES to confirm: ');(out/'trim-request.txt').write_bytes(requested)
            result=link.command('YES',b'CLOCK> ');(out/'trim-result.txt').write_bytes(result)
            status=link.command('STATUS',b'CLOCK> ');(out/'after-status.txt').write_bytes(status)
            raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
            assert raw[8]==0 and raw[7]&0x7F==0,'Zero normal trim was not verified'
            identity=link.command('EUI',b'CLOCK> ');(out/'after-eui.txt').write_bytes(identity)
            assert b', changed' not in identity,'RTC identity mismatch requires review'
            eui=re.search(rb'EUI ([0-9A-F:]{17})',identity)[1].decode()
            report.update(passed=True,trim_steps=0,trim_register=0,control_register=raw[7],eui=eui,identity_bound=b', unbound' not in identity)
            link.command('Q');(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        finally:
            if not report.get('passed'):(out/'failed-report.json').write_text(json.dumps(report,indent=2)+'\n')
            link.serial.close()

if __name__=='__main__':main()
