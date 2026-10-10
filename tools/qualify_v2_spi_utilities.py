"""Provision normal saved SRAM/WORK records after exact resident verification."""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,read_application_s19
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    qualified=json.loads((BUILD/'workspace/candidate-check.json').read_text());assert qualified['passed']
    wm=json.loads((BUILD/'workspace/build.json').read_text());sm=json.loads((BUILD/'store/build.json').read_text())
    assert wm['sha256']==qualified['workspace_sha256'] and sm['sha256']==qualified['store_sha256']
    expected=bytearray((a.root/'resident-check/b2.bin').read_bytes())
    specs=[('SRAM',0xA000,BUILD/'store/sram.s19',BUILD/'store/sram.bin',sm['load_end']),
           ('WORK',0xB000,BUILD/'workspace/workspace.s19',BUILD/'workspace/workspace.bin',wm['end']-1)]
    for name,addr,_,binpath,end in specs:
        body=binpath.read_bytes();assert end==0x4000+len(body)-1
        meta=sm if name=='SRAM' else wm
        assert sha(body)==meta['sha256']
        srecpath=BUILD/('store/sram.s19' if name=='SRAM' else 'workspace/workspace.s19')
        cells,entry=read_application_s19(srecpath)
        assert entry==0x4000 and bytes(cells[a] for a in range(min(cells),max(cells)+1))==body
        record=b'SR\x01\x3f\0\x40'+len(body).to_bytes(2,'little')+name.encode().ljust(16,b'\0')+body
        offset=addr-0x8000;assert expected[offset:offset+len(record)]==bytes([255])*len(record),f'{name} target is occupied'
        expected[offset:offset+len(record)]=record
    out=a.root/'utilities';out.mkdir(exist_ok=False)
    (out/'expected-b2.bin').write_bytes(expected)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            link.command('');link.command('B2',b'\r\nB2> ')
            before=b''.join(link.dump(addr,addr+4095,b'\r\nB2> ') for addr in range(0x8000,0x10000,4096))
            assert before==(a.root/'resident-check/b2.bin').read_bytes();link.command('B3')
            for name,addr,srec,binpath,end in specs:
                load_image(link,srec)
                text=link.command(f'S 2 {addr:04X} 4000 {end:04X} {name}');(out/f'save-{name}.txt').write_bytes(text)
                assert b'Done' in text,text
                print('PASS',a.board,'saved',name,f'B2:{addr:04X}',flush=True)
            link.command('B2',b'\r\nB2> ')
            after=b''.join(link.dump(addr,addr+4095,b'\r\nB2> ') for addr in range(0x8000,0x10000,4096))
            (out/'b2.bin').write_bytes(after);assert after==expected;link.command('B3')
            table=link.command('T 2');(out/'table.txt').write_bytes(table)
            assert b'CLOCK' in table and b'SRAM' in table and b'WORK' in table
            s=link.command('R SRAM',b'SRAM> ');(out/'sram-start.txt').write_bytes(s);assert b'SRAM 1.1' in s
            t=link.command('T',b'SRAM> ');(out/'sram-initial-table.txt').write_bytes(t);link.command('Q')
            w=link.command('R WORK',b'WORK> ');(out/'work-start.txt').write_bytes(w);assert f"WORK {wm['version']}".encode() in w
            c=link.command('?',b'WORK> ');(out/'work-initial-capacity.txt').write_bytes(c);link.command('Q')
            (out/'report.json').write_text(json.dumps(dict(passed=True,board=a.board,records=['SRAM','WORK'],b2_sha256=sha(after),
                workspace_sha256=wm['sha256'],store_sha256=sm['sha256'],sram_initialized=False,clock_unchanged=True),indent=2)+'\n')
            print('PASS',a.board,'stored utilities, byte-exact B2, R SRAM / R WORK / table; no SRAM formatting',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
