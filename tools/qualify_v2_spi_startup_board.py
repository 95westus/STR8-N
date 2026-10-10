"""Beta22/23 post-RESET image/display and read-only software cold-boot tests."""
import argparse,hashlib,json,re,time
from pathlib import Path
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image
from qualify_v2_spi_storage import memory_request
from serial.tools.list_ports import comports
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());assert plan['version'] in ('2.0b22','2.0b23')
    build=ROOT/'output/qualification/beta23-phase1-2026-10-09/frozen/build' if plan['version']=='2.0b23' else ROOT/'BUILD/v2-spi-resident'
    if plan['version']=='2.0b23':
        physical=json.loads((a.root.parent/'physical-boot/report.json').read_text())[a.board]
        assert physical['monitor_ready'] and physical['banner_matches'] and physical['expected_version']==plan['version']
    out=a.root/'installed-check';out.mkdir(exist_ok=False);checks=[]
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ');(out/'startup.txt').write_bytes(initial)
            assert re.search(rb'B[0-3]> $',initial),'Physical RESET still required; board is not at monitor'
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                assert data==(a.root/f'upgrade/expected-b{bank}.bin').read_bytes()
                digest=hashlib.sha256(data).hexdigest();assert digest==plan['expected_hashes'][bank]
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(digest)
            link.command('B3');checks.append('exact four-bank installed image')
            expected=b'SV\x01\0\0\0\xff\x66' if a.board=='2512' else b'SV\x01\x0f\0\x65\xff\x64'
            assert link.dump(0x7D04,0x7D0B)==expected
            text=link.command('TIME');(out/'time.txt').write_bytes(text)
            if a.board=='2512':assert b'RTCC: unavailable' in text and b'Trim' not in text
            else:
                assert re.search(rb'RTCC: UTC (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{4}-\d{2}-\d{2}',text)
                trim=-18 if a.board=='2205' else -14
                assert f'RTCC: Trim {trim} steps:'.encode() in text and b'RTCC: Local ' in text
                clock=link.command('R CLOCK',b'CLOCK> ');(out/'clock-start.txt').write_bytes(clock);assert b'CLOCK 1.6' in clock
                link.command('Q')
            checks.append('saved EDU mode and read-only weekday/local/trim display')
            for n,slot in enumerate(('A','B','A')):
                start=link.command('J3' if plan['version']=='2.0b23' else 'G F004',b'Enter default [3s]: ');link.send(slot.encode());text=link.until(b'\r\nB3> ')
                (out/f'cold-{n}-{slot}.txt').write_bytes(start+text)
                assert ('STR8-N '+plan['version']).encode() in text and link.dump(0x7D04,0x7D0B)==expected
                if a.board=='2512':
                    assert b'EDU OFF' in text and b'SSRAM:' not in text and b'RTCC:' not in text
                else:
                    assert b'SSRAM:' in text and b'SSRAM: Unavailable' not in text
                    if plan['version']=='2.0b23':
                        lines=[line for line in text.split(b'\r\n') if line.startswith(b'RTCC:')]
                        assert len(lines)==1 and re.fullmatch(rb'RTCC: (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \([+-]\d{2}:\d{2}\)',lines[0])
                    assert link.dump(0x66AE,0x66AF)==b'\x01\0'
                    load_image(link,build/'hardware-client/client.s19')
                    link.write_ram(0x3E20,bytes((1,3,0)))
                    link.write_ram(0x3E00,memory_request(1,0,64,0x4000))
                    (out/f'read-{n}.txt').write_bytes(link.command('G 2000'))
                    r=link.dump(0x3E10,0x3E38);(out/f'result-{n}.bin').write_bytes(r)
                    assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    assert link.dump(0x4000,0x403F)==(a.root/'sram-prior/array-0.bin').read_bytes()[:64]
            checks.append('three A/B/A software cold boots; read-only SRAM succeeds without manual acknowledgment' if a.board!='2512' else 'three A/B/A software cold boots with EDU OFF and no device blocks')
            mapped=link.command('M1');(out/'m1.txt').write_bytes(mapped)
            assert b'B3:8-F protected.' in mapped and b'STR8-N ' not in mapped and b'RTCC:' not in mapped
            checks.append('quiet M1 return')
            report=dict(passed=True,board=a.board,version=plan['version'],final_hashes=hashes,checks=checks,clock_set=False,trim_changed=False,sram_data_written=False,software_cold_resets=3,physical_reset_operator_reported=True,repeated_physical_reset_qualification_pending=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS',a.board,'; '.join(checks),flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
