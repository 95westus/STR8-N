"""Scoped named-storage/workspace tests, with full retained-array restoration."""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def memory_request(op,address=0,count=64,buffer=0x4000):
    return bytes((op,0,address&255,address>>8&255,address>>16,buffer&255,buffer>>8,count,0,0,0,0,0,0,0,0))
def workspace_request(op,handle=None,owner=0xBEEF,size=0,units=4,count=0,offset=0,buffer=0x2600,key=b''):
    r=bytearray(32);r[0]=op;r[2:4]=owner.to_bytes(2,'little')
    if handle is not None:r[4:12]=handle
    r[12:15]=offset.to_bytes(3,'little');r[15]=count;r[16:18]=buffer.to_bytes(2,'little')
    r[18:21]=size.to_bytes(3,'little');r[21]=units;r[24:32]=key.ljust(8,b'\0');return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True)
    p.add_argument('--stage',required=True,choices=('exercise','reset-check','power-check','restore','initialize'));p.add_argument('--attempt',default='')
    p.add_argument('--handle-stage');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    qualified=json.loads((BUILD/'workspace/candidate-check.json').read_text());assert qualified['passed']
    client=json.loads((BUILD/'hardware-client/build.json').read_text());ct=json.loads((BUILD/'hardware-client/test-results.json').read_text());assert ct['passed'] and ct['sha256']==client['sha256']
    out=a.root/('storage-'+a.stage+a.attempt);out.mkdir(exist_ok=False);report=dict(board=a.board,stage=a.stage,clock_set=False,trim_changed=False,calls=[])
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if b'CLOCK>' in first or b'BM>' in first:link.command('Q')
            link.command('B3')
            def driver(req,bank=3,bulk=False,privileged=False):
                write(link,0x3E20,bytes((1,bank,0xA5 if privileged else 0)));write(link,0x3E00,req)
                text=link.command('G 2003' if bulk else 'G 2000');r=link.dump(0x3E10,0x3E38)
                assert r[0x23]==r[0x24] and bool(r[0x27]&1)==(r[8]==0)
                assert link.dump(0x66AE,0x66AE)==b'\x01'
                return r[8],r,text
            def work(req,bank=3,expected=0):
                write(link,0x3E21,bytes((bank,)));write(link,0x3E40,req)
                text=link.command('G 2006');r=link.dump(0x3E60,0x3E7F);state=link.dump(0x3E30,0x3E38)
                assert state[3]==state[4] and state[8]==expected,(expected,state.hex(),text)
                assert link.dump(0x66AE,0x66AE)==b'\x01'
                item=dict(op=req[0],status=state[8],result_hex=r.hex(),bank=bank);report['calls'].append(item)
                return r
            def load_work():
                load_image(link,BUILD/'hardware-client/client.s19')
                assert b'Done' in link.command('R 2 WORK L')
            if a.stage=='exercise':
                load_work()
                if a.board=='2512':
                    for bank in range(4):work(workspace_request(0),bank,7)
                    assert driver(memory_request(2,count=1))[0]==6
                    report.update(passed=True,optional_hardware_refused=True)
                else:
                    work(workspace_request(6,key=b'FORMAT!!'))
                    for units in (1,2,3,4):
                        r=work(workspace_request(5,units=units,key=b'RESIZE!!'))
                        assert r[21]==units and int.from_bytes(r[18:21],'little')==0x1FFE0-units*0x4000
                    r=work(workspace_request(1,size=512));h=r[4:12]
                    pattern=bytes(range(64));write(link,0x2600,pattern)
                    for bank in range(4):
                        work(workspace_request(4,h,count=64),bank)
                        work(workspace_request(3,h,count=64,buffer=0x2700),bank)
                        assert link.dump(0x2700,0x273F)==pattern
                    work(workspace_request(3,h,owner=1,count=1),expected=0x4B)
                    work(workspace_request(3,h,count=1,offset=512),expected=0x44)
                    work(workspace_request(5,units=1,key=b'RESIZE!!'))
                    low=work(workspace_request(1,size=256))[4:12]
                    work(workspace_request(5,units=4,key=b'RESIZE!!'),expected=0x4A)
                    work(workspace_request(2,low));work(workspace_request(5,units=4,key=b'RESIZE!!'))
                    work(workspace_request(2,h));work(workspace_request(3,h,count=1),expected=0x4B)
                    # Exact named program restored/run from both providers.
                    program=bytes.fromhex('EE 00 27 4C 67 7E');write(link,0x2600,program);write(link,0x2700,b'\0')
                    link.command('B2',b'\r\nB2> ');assert link.dump(0xAE80,0xAE9D,b'\r\nB2> ')==bytes([255])*30;link.command('B3')
                    assert b'Done' in link.command('S 2 AE80 2600 2605 SDEMO')
                    link.command('R SRAM',b'SRAM> ')
                    assert b'SRAM: 00' in link.command('S SDEMO 2600 2605 2600',b'SRAM> ')
                    assert b'SDEMO' in link.command('T',b'SRAM> ')
                    assert b'SRAM: 00' in link.command('R SDEMO',b'SRAM> ');link.command('Q')
                    assert link.dump(0x2600,0x2605)==program
                    link.command('R 2 SDEMO');assert link.dump(0x2700,0x2700)==b'\x01'
                    link.command('R SRAM',b'SRAM> ');link.command('G SDEMO');assert link.dump(0x2700,0x2700)==b'\x02'
                    load_image(link,BUILD/'workspace/example/example.s19');assert b'Done' in link.command('R 2 WORK L')
                    assert b'W: 00' in link.command('G 2000')
                    load_work();h=work(workspace_request(1,size=256))[4:12]
                    (out/'handle.json').write_text(json.dumps(dict(owner=0xBEEF,handle=h.hex()),indent=2)+'\n')
                    # A fresh loader call and HOLD already occur between every operation.
                    assert b'Done' in link.command('R 2 WORK L');work(workspace_request(3,h,count=1))
                    report.update(passed=True,handle_pending_reset=h.hex(),named_program_same_bytes=True,cache_client_passed=True)
            elif a.stage in ('reset-check','power-check'):
                if a.board=='2512':raise ValueError('No workspace retention on 2512')
                oldstage=a.handle_stage or ('storage-exercise' if a.stage=='reset-check' else 'storage-reset-check')
                old=json.loads((a.root/oldstage/'handle.json').read_text());h=bytes.fromhex(old['handle'])
                # Descriptor/latch must be captured before the first WORK use.
                assert link.dump(0x66AE,0x66AF)==b'\x01\0'
                link.command('R SRAM',b'SRAM> ');assert b'SDEMO' in link.command('T',b'SRAM> ');link.command('Q')
                load_work();work(workspace_request(3,h,count=1),expected=0x4B)
                new=work(workspace_request(1,size=256))[4:12];assert new!=h
                (out/'handle.json').write_text(json.dumps(dict(owner=0xBEEF,handle=new.hex()),indent=2)+'\n')
                assert driver(memory_request(2,count=1))[0]==6
                report.update(passed=True,old_handle_rejected=True,new_handle=new.hex(),saved_program_retained=True)
            elif a.stage=='restore':
                assert a.board!='2512'
                original=(a.root/'spi-archive/array.bin').read_bytes();assert original==(a.root/'spi-archive/array-repeat.bin').read_bytes()
                load_image(link,BUILD/'hardware-client/client.s19')
                for i in range(16):
                    part=original[i*8192:(i+1)*8192];path=out/f'block-{i:02d}.s19';path.write_bytes(s19(dict(enumerate(part,0x4000)),0x4000))
                    load_image(link,path);assert driver(memory_request(2,i*8192),bulk=True,privileged=True)[0]==0
                    print(a.board,'restored SRAM',i+1,'/16',flush=True)
                blocks=[]
                for i in range(16):
                    assert driver(memory_request(1,i*8192),bulk=True)[0]==0
                    part=link.dump(0x4000,0x5FFF);assert part==original[i*8192:(i+1)*8192];blocks.append(part)
                    print(a.board,'verified SRAM',i+1,'/16',flush=True)
                final=b''.join(blocks);(out/'array-final.bin').write_bytes(final)
                report.update(passed=True,array_restored=True,array_sha256=sha(final))
            else:
                assert a.board!='2512';load_work();work(workspace_request(6,key=b'FORMAT!!'))
                r=work(workspace_request(0));assert r[21]==4 and int.from_bytes(r[18:21],'little')==65504
                report.update(passed=True,initialized=True,program_region=65536,workspace_bytes=65504)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            if a.attempt:
                canonical=a.root/('storage-'+a.stage);canonical.mkdir(exist_ok=True)
                report['successful_attempt']=out.name
                (canonical/'report.json').write_text(json.dumps(report,indent=2)+'\n')
                if (out/'handle.json').exists():(canonical/'handle.json').write_bytes((out/'handle.json').read_bytes())
            print('PASS',a.board,a.stage,'SPI named storage/workspace',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
