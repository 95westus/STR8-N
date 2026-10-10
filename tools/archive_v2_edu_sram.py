"""Repeated preserving resident-SRAM readback before/after EDU-mode updates."""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
def main():
    global BUILD
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);p.add_argument('--stage',choices=('prior','final'),default='prior');p.add_argument('--build',type=Path);a=p.parse_args()
    if a.build: BUILD=a.build.resolve()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/('sram-'+a.stage);out.mkdir(exist_ok=False)
    meta=json.loads((BUILD/'hardware-client/test-results.json').read_text());assert meta['passed']
    assert hashlib.sha256((BUILD/'hardware-client/client.bin').read_bytes()).hexdigest()==meta['sha256']
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ')
            if any(t in initial for t in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3');assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64','EDU ON required for SRAM archive';load_image(link,BUILD/'hardware-client/client.s19');images=[]
            for copy in range(2 if a.stage=='prior' else 1):
                blocks=[]
                for block in range(16):
                    write(link,0x3E20,b'\x01\x03\0');write(link,0x3E00,memory_request(1,block*8192))
                    link.command('G 2003');r=link.dump(0x3E10,0x3E38)
                    assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    data=link.dump(0x4000,0x5FFF);blocks.append(data)
                    print(a.board,a.stage,'copy',copy+1,'block',block+1,'/16',flush=True)
                image=b''.join(blocks);(out/f'array-{copy}.bin').write_bytes(image);images.append(image)
            assert images[0]==images[-1]
            if a.stage=='final':assert images[0]==(a.root/'sram-prior/array-0.bin').read_bytes()
            (out/'report.json').write_text(json.dumps(dict(passed=True,board=a.board,repeat_verified=a.stage=='prior',array_bytes=len(images[0]),sha256=hashlib.sha256(images[0]).hexdigest(),array_written=False),indent=2)+'\n')
        finally:link.serial.close()
if __name__=='__main__':main()
