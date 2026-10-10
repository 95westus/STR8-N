"""Show actual flash/SPI saves and resize prompts on board 2609 only.

Keep the new flash DEMO2 record. Independently archive the first SRAM 8 KiB
before temporary layout operations, then restore/verify those original bytes.
No other port, flash erase, RTC setting or EEPROM administration is used.
"""
import argparse,hashlib,json,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    port=next(x for x in comports() if x.serial_number==SERIALS['2609']).device
    assert port.upper()=='COM8';a.out.mkdir(parents=True,exist_ok=False)
    client=json.loads((BUILD/'hardware-client/test-results.json').read_text());assert client['passed'] and sha((BUILD/'hardware-client/client.bin').read_bytes())==client['sha256']
    report=dict(board='2609',port=port,passed=False,clock_set=False,trim_changed=False,flash_erased=False)
    original=None;mutated=False;sections={};current=None
    # LDA/PUTC spells DEMO, NEWLINE, then HOLD; exactly 26 bytes at 2600.
    program=b''.join(bytes((0xA9,c,0x20,0x6D,0x7E)) for c in b'DEMO')+bytes.fromhex('20 7F 7E 4C 67 7E')
    assert len(program)==26
    flash_offset=0x4280
    record=b'SR\x01\x3f\0\x26'+len(program).to_bytes(2,'little')+b'DEMO2'.ljust(16,b'\0')+program
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if any(s in first for s in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3')
            def cmd(text,prompt=b'\r\nB3> '):
                data=link.command(text,prompt)
                if current:sections[current]+=data
                return data
            def section(name):
                nonlocal current
                current=name;sections[name]=link.command('')
            def bulk(op,privileged=False):
                write(link,0x3E20,bytes((1,3,0xA5 if privileged else 0)));write(link,0x3E00,memory_request(op))
                text=link.command('G 2003');r=link.dump(0x3E10,0x3E38)
                assert r[8]==0 and r[0x23]==r[0x24],(r.hex(),text)
                assert link.dump(0x66AE,0x66AE)==b'\x01'
            # Archive current first 8 KiB independently, regardless of earlier backups.
            load_image(link,BUILD/'hardware-client/client.s19');copies=[]
            for i in range(2):
                bulk(1);part=link.dump(0x4000,0x5FFF);copies.append(part);(a.out/f'sram-prior-{i}.bin').write_bytes(part)
            assert copies[0]==copies[1];original=copies[0];report['sram_prior_sha256']=sha(original)
            # Exact B2 pre-image is retained, to prove the only flash change.
            link.command('B2',b'\r\nB2> ')
            flash=b''.join(link.dump(addr,addr+4095,b'\r\nB2> ') for addr in range(0x8000,0x10000,4096));(a.out/'flash-b2-before.bin').write_bytes(flash)
            assert flash[flash_offset:flash_offset+len(record)]==bytes([255])*len(record),'Flash DEMO2 target occupied'
            link.command('B3');table=link.command('T 2');assert not re.search(rb' C DEMO2\r?\n',table),'DEMO2 name already exists in flash'
            section('flash')
            for i in range(0,len(program),8):
                text=cmd(f'M {0x2600+i:04X} '+' '.join(f'{v:02X}' for v in program[i:i+8]));assert b'Long line' not in text
            assert link.dump(0x2600,0x2619)==program
            assert b'Done' in cmd('S 2 C280 2600 2619 DEMO2')
            cmd('T 2');assert b'\r\nDEMO\r\n' in cmd('R 2 DEMO2')
            report['flash_demo_saved']=True
            section('initialize')
            assert b'WORK 1.0' in cmd('R WORK',b'WORK> ')
            cmd('?',b'WORK> ')
            cmd('F',b'Type FORMAT SRAM: ');mutated=True
            assert b'WORK: 00' in cmd('FORMAT SRAM',b'WORK> ')
            assert b'04 00FFE0' in cmd('?',b'WORK> ');cmd('Q')
            section('spisram')
            assert b'SRAM 1.1' in cmd('R SRAM',b'SRAM> ')
            assert b'SRAM: 00' in cmd('S DEMO 2600 2619 2600',b'SRAM> ')
            assert b'DEMO 2600 001A' in cmd('T',b'SRAM> ')
            assert b'SRAM: 00' in cmd('R DEMO',b'SRAM> ')
            cmd('Q');assert link.dump(0x2600,0x2619)==program
            cmd('R SRAM',b'SRAM> ')
            assert b'\r\nDEMO\r\n' in cmd('G DEMO')
            section('resize')
            cmd('R WORK',b'WORK> ');assert b'04 00FFE0' in cmd('?',b'WORK> ')
            cmd('P 2',b'Type YES: ');assert b'WORK: 00' in cmd('YES',b'WORK> ')
            assert b'02 017FE0' in cmd('?',b'WORK> ')
            cmd('P 4',b'Type YES: ');assert b'WORK: 00' in cmd('YES',b'WORK> ')
            assert b'04 00FFE0' in cmd('?',b'WORK> ');cmd('Q')
            report.update(passed=True,spi_demo_saved=True,loaded_bytes_identical=True,resize_units=[4,2,4],workspace_bytes=[65504,98272,65504])
        except Exception as e:
            report['error']=repr(e);raise
        finally:
            current=None
            if mutated and original is not None:
                try:
                    first=link.command('',b'> ')
                    if any(s in first for s in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
                    load_image(link,BUILD/'hardware-client/client.s19')
                    path=a.out/'sram-restore.s19';path.write_bytes(s19(dict(enumerate(original,0x4000)),0x4000));load_image(link,path)
                    bulk(2,True);bulk(1);restored=link.dump(0x4000,0x5FFF);assert restored==original
                    (a.out/'sram-restored.bin').write_bytes(restored);report['sram_restored']=True
                    write(link,0x2300,bytes.fromhex('4C 64 7E'));link.command('G 2300',b'Enter default [3s]: ');link.send(b'\r');link.until(b'\r\nB3> ')
                    assert link.dump(0x66AE,0x66AF)==b'\x01\0'
                except Exception as e:
                    report['cleanup_error']=repr(e);report['passed']=False
            if report.get('flash_demo_saved'):
                try:
                    link.command('B2',b'\r\nB2> ')
                    after=b''.join(link.dump(addr,addr+4095,b'\r\nB2> ') for addr in range(0x8000,0x10000,4096))
                    expected=bytearray(flash);expected[flash_offset:flash_offset+len(record)]=record;assert after==expected
                    (a.out/'flash-b2-after.bin').write_bytes(after);report['flash_after_sha256']=sha(after);link.command('B3')
                except Exception as e:report['flash_check_error']=repr(e);report['passed']=False
            for name,body in sections.items():(a.out/(name+'.txt')).write_bytes(body)
            (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()
            for name,body in sections.items():print('\n### '+name+'\n'+body.decode('ascii','backslashreplace'),flush=True)
            print('RESULT',json.dumps(report),flush=True)

if __name__=='__main__':main()
