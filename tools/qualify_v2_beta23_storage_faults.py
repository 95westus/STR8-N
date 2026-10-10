"""Temporary SRAM fault injection, refusal/repair checks and exact restoration."""
import argparse,hashlib,json,time
from pathlib import Path
from beta4_migration import Link,s19
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request,workspace_request


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--cold-restarts',action='store_true');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    model=json.loads((a.build/('storage-fault-cold-model.json' if a.cold_restarts else 'storage-fault-hardware-model.json')).read_text());meta=json.loads((a.build/'build.json').read_text())
    assert model['passed'] and model['artifacts']==meta['artifacts']
    if a.cold_restarts:assert model['cold_restarts']
    original=(a.root/'sram-prior/array-0.bin').read_bytes();assert original==(a.root/'sram-prior/array-1.bin').read_bytes()
    out=a.root/('storage-faults-cold' if a.cold_restarts else 'storage-faults');out.mkdir(exist_ok=False);changed=False;checks=[];report=dict(passed=False,board=a.board,checks=checks,clock_set=False,trim_changed=False,flash_written=False,restored=False,cold_restarts=a.cold_restarts)
    with (out/'serial.jsonl').open('x') as log:
        l=Link(a.port,log)
        try:
            stop=time.monotonic()+.3
            while time.monotonic()<stop:l.read(max(1,l.serial.in_waiting))
            initial=l.command('',b'> ')
            if any(x in initial for x in (b'CLOCK>',b'BM>',b'EDU>',b'SRAM>',b'WORK>')):l.command('Q',b'> ')
            l.command('B3');assert l.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            client=a.build/'hardware-client/client.s19'
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                data=l.command(text,prompt)
                if label:(out/(label+'.txt')).write_bytes(data)
                return data
            def load_work():load_image(l,client);assert b'Done' in cmd('R 2 WORK L')
            def work(req):
                write(l,0x3E21,b'\x03');write(l,0x3E40,req);cmd('G 2006')
                status=l.dump(0x3E38,0x3E38)[0];result=l.dump(0x3E60,0x3E7F);return status,result
            def driver(op,address=0,count=64,priv=False,bulk=False):
                write(l,0x3E20,bytes([1,3,0xA5 if priv else 0]));write(l,0x3E00,memory_request(op,address,count,0x4000))
                cmd('G 2003' if bulk else 'G 2000');r=l.dump(0x3E10,0x3E38)
                assert r[8]==0 and r[9]==count and r[0x23]==r[0x24] and l.dump(0x66AE,0x66AE)==b'\x01'
            def patch(address,value):
                load_image(l,client);write(l,0x4000,bytes([value]));driver(2,address,1,True)
                driver(1,address,1);assert l.dump(0x4000,0x4000)==bytes([value])
            def restart(label,expected):
                text=cmd('J3',b'Enter default [3s]: ');l.send(b'\r');text+=l.until(b'\r\nB3> ');(out/(label+'-cold-start.txt')).write_bytes(text)
                assert l.dump(0x66AE,0x66AF)==b'\x01\0'
                load_image(l,client);driver(1,0,bulk=True);assert l.dump(0x4000,0x5FFF)==expected,'Cold boot modified retained fault state'
            load_image(l,client);driver(1,0,bulk=True);assert l.dump(0x4000,0x5FFF)==original[:8192]
            load_work();changed=True;assert work(workspace_request(6,key=b'FORMAT!!'))[0]==0
            payload=bytes.fromhex(model['payload_hex']);write(l,0x2600,payload)
            cmd('R SRAM',b'SRAM> ');assert b'SRAM: 00' in cmd('S B23FAULT 2600 2605 2600',b'SRAM> ');cmd('Q')
            load_image(l,client);driver(1,0,bulk=True);valid=l.dump(0x4000,0x5FFF);(out/'valid-test-block.bin').write_bytes(valid)
            slots=[i for i in range(8) if valid[64+i*64:66+i*64]==b'SP' and valid[127+i*64]==0xA5]
            assert len(slots)==1;slot=slots[0];base=64+64*slot;page=valid[base+14]*256
            for label,address,bad,status in [('payload-crc',page,valid[page]^1,0x45),('header-crc',base+4,valid[base+4]^1,0x41),('unpublished',base+63,0,0x42)]:
                patch(address,bad)
                if a.cold_restarts:
                    cut=bytearray(valid);cut[address]=bad;restart(label,cut)
                write(l,0x2600,bytes([0x7C])*6);write(l,0x2700,b'\0')
                cmd('R SRAM',b'SRAM> ');text=cmd('R B23FAULT',b'SRAM> ',label)
                assert f'SRAM: {status:02X}'.encode() in text;cmd('Q');assert l.dump(0x2600,0x2605)==bytes([0x7C])*6
                if label=='payload-crc':
                    cmd('R SRAM',b'SRAM> ');assert b'SRAM: 45' in cmd('G B23FAULT',b'SRAM> ',label='corrupt-run-refused');cmd('Q');assert l.dump(0x2700,0x2700)==b'\0'
                patch(address,valid[address]);checks.append(dict(case=label,expected_status=status,destination_preserved=True))
            patch(63,0)
            if a.cold_restarts:
                cut=bytearray(valid);cut[63]=0;restart('primary-unpublished',cut)
            load_work();status,result=work(workspace_request(0));assert status==0 and result[23]==1
            cmd('R SRAM',b'SRAM> ');assert b'SRAM: 40' in cmd('R B23FAULT',b'SRAM> ',label='primary-invalid-refused');cmd('Q')
            load_work();status,_=work(workspace_request(8,key=b'REPAIR!!'));assert status==0
            cmd('R SRAM',b'SRAM> ');assert b'SRAM: 00' in cmd('R B23FAULT',b'SRAM> ',label='after-explicit-repair');cmd('Q');assert l.dump(0x2600,0x2605)==payload
            checks.append(dict(case='primary-unpublished-secondary-explicit-repair',saved_payload_preserved=True))
            report['exercised']=True
        except Exception as e:report['error']=repr(e)
        finally:
            try:
                text=l.command('',b'> ')
                if any(x in text for x in (b'CLOCK>',b'BM>',b'EDU>',b'SRAM>',b'WORK>')):l.command('Q',b'> ')
                l.command('B3')
                if changed:
                    load_image(l,client)
                    # Administrative operations and six-byte test record touch only block 0.
                    path=out/'restore-first-block.s19';path.write_bytes(s19(dict(enumerate(original[:8192],0x4000)),0x4000));load_image(l,path)
                    driver(2,0,priv=True,bulk=True);parts=[]
                    for i in range(16):
                        driver(1,i*8192,bulk=True);part=l.dump(0x4000,0x5FFF);assert part==original[i*8192:(i+1)*8192];parts.append(part)
                        print(a.board,'fault-test original SRAM verified',i+1,'/16',flush=True)
                    final=b''.join(parts);(out/'restored-array.bin').write_bytes(final);report.update(restored=True,sram_sha256=hashlib.sha256(final).hexdigest())
                    start=cmd('J3',b'Enter default [3s]: ');l.send(b'\r');start+=l.until(b'\r\nB3> ');(out/'restored-cold-start.txt').write_bytes(start)
                report['passed']=bool(report.get('exercised') and report['restored'] and 'error' not in report)
            except Exception as e:report['restoration_error']=repr(e)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');l.serial.close()
    print('RESULT',a.board,json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
