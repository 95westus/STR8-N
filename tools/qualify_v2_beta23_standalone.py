"""Exercise standalone EDU-OFF on an attached EDU, then restore ON exactly."""
import argparse,json,time,hashlib,traceback
from pathlib import Path
from beta4_migration import Link,journal,metadata,config_sum,s19
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from qualify_v2_spi_install import load_image
from qualify_v2_spi_storage import memory_request,workspace_request

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--prior-directory',type=Path);p.add_argument('--attempt',default='');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    out=a.root/('standalone'+a.attempt);out.mkdir(exist_ok=False);report=dict(passed=False,board=a.board,clock_set=False,trim_changed=False,original_on_restored=False)
    prior=a.prior_directory or a.root/'prior'
    banks=[(prior/f'b{i}.bin').read_bytes() for i in range(4)];expected=[bytearray(b) for b in banks]
    old=journal(banks[3]);assert old;cfg=bytearray(old[8:24]);assert cfg[13]!=0xA5
    assert sum(banks[3][0x4000+i:0x4080+i]==b'\xff'*128 for i in range(0,4096,128))>=2,'Insufficient append space for bounded mode test'
    counts=[int.from_bytes(old[24+3*i:27+3*i],'little') for i in range(32)];seq=int.from_bytes(old[4:8],'little')
    with (out/'serial.jsonl').open('x') as log:
        l=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
            text=l.command('',b'> ')
            if any(x in text for x in (b'CLOCK>',b'BM>',b'EDU>',b'WORK>',b'SRAM>')):l.command('Q',b'> ')
            l.command('B3')
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                data=l.command(text,prompt)
                if label:(out/(label+'.txt')).write_bytes(data)
                return data
            def mode(target,turn):
                cmd('R EDU',b'EDU> ');cmd(target,b'Apply after RESET? [y/N]: ')
                assert b'Saved; RESET required.' in cmd('Y',b'EDU> ')
                cmd('Q');start=cmd('J3',b'Enter default [3s]: ');l.send(b'\r');start+=l.until(b'\r\nB3> ')
                (out/f'boot-{target}.txt').write_bytes(start)
                wanted=b'SV\x01\0\0\0\xff\x66' if target=='OFF' else b'SV\x01\x0f\0\x65\xff\x64'
                assert l.dump(0x7D04,0x7D0B)==wanted
                cfg[13]=0xA5 if target=='OFF' else 0;cfg[14:]=config_sum(cfg)
                end=max(i for i in range(0,4096,128) if expected[3][0x4000+i:0x4000+i+128]!=b'\xff'*128)+128
                assert end<4096;expected[3][0x4000+end:0x4080+end]=metadata(cfg,counts,seq+turn)
            assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            mode('OFF',1)
            before=l.dump(0x6500,0x66FF);pattern=bytes((i*37+9)&255 for i in range(512));l.write_ram(0x6500,pattern)
            program=b''.join(bytes([0xA9,c,0x20,0x6D,0x7E]) for c in b'OFFRAM')+bytes.fromhex('20 7F 7E 4C 67 7E')
            records=s19(dict(enumerate(program,0x6500)),0x6500);cmd('L',b'S19')
            for line in records.splitlines():l.send(line+b'\r\n');time.sleep(.04)
            l.until(b'\r\nB3> ');wanted=program+pattern[len(program):]
            assert l.dump(0x6500,0x66FF)==wanted
            assert b'OFFRAM' in cmd('G 6500',label='upper-ram-run')
            assert l.dump(0x6500,0x66FF)==wanted
            assert b'RTCC: unavailable' in cmd('TIME',label='time-off')
            cmd('R CLOCK',b'CLOCK> ');assert b'Services unavailable' in cmd('STATUS',b'CLOCK> ',label='clock-off');cmd('Q')
            assert b'SRAM loader unavailable' in cmd('R SRAM',label='sram-off')
            cmd('R WORK',b'WORK> ');assert b'SPI SRAM unavailable' in cmd('?',b'WORK> ',label='work-off');cmd('Q')
            assert l.dump(0x6500,0x66FF)==wanted
            load_image(l,a.build/'hardware-client/client.s19')
            def pcr_snapshot():
                l.write_ram(0x2300,bytes.fromhex('AD EC 7F 8D FF 23 4C 67 7E'))
                cmd('G 2300');return l.dump(0x23FF,0x23FF)
            for bank in range(4):
                l.write_ram(0x3E20,bytes([1,bank,0]));l.write_ram(0x3E00,memory_request(1,0,1,0x4000))
                pcr=pcr_snapshot()
                cmd('G 2000');r=l.dump(0x3E10,0x3E38);assert r[8]==0x80 and pcr_snapshot()==pcr
            assert l.dump(0x6500,0x66FF)==wanted;l.write_ram(0x6500,before)
            mode('ON',2);report['original_on_restored']=True
            protected=l.dump(0x6500,0x66FF)
            assert b'Protected' in cmd('M 6500 12') and b'Protected' in cmd('G 6500')
            assert l.dump(0x6500,0x66FF)==protected
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                data=b''.join(l.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));assert data==expected[bank]
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(hashlib.sha256(data).hexdigest())
            l.command('B3');report.update(passed=True,upper_s19_edit_run=True,off_clients_preserve_reclaimed_ram=True,
                all_bank_spi_discovery_refused=True,on_protection=True,configuration_appends=2,final_flash_hashes=hashes)
        except Exception as e:
            report['error']=repr(e);report['error_traceback']=traceback.format_exc()
            # Restore ON even when an assertion failed; no RTC/trim commands.
            try:
                text=l.command('',b'> ')
                if any(x in text for x in (b'CLOCK>',b'BM>',b'EDU>',b'WORK>',b'SRAM>')):l.command('Q',b'> ')
                l.command('B3');active=l.dump(0x7D27,0x7D28)
                if active[1]==0xA5:
                    l.command('R EDU',b'EDU> ');l.command('ON',b'Apply after RESET? [y/N]: ');l.command('Y',b'EDU> ');l.command('Q')
                if active[0]!=1:
                    l.command('J3',b'Enter default [3s]: ');l.send(b'\r');l.until(b'\r\nB3> ')
                report['original_on_restored']=l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            except Exception as recovery:report['mode_recovery_error']=repr(recovery)
        finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');l.serial.close()
    print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
