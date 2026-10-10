"""Archive/model-bound removal of the incomplete demo, preserving WORK tail."""
import argparse,hashlib,json,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,journal
from install_v2_rtc_upgrade import SERIALS
ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--stage',choices=('archive','repair'),required=True);a=p.parse_args()
    port=next(x for x in comports() if x.serial_number==SERIALS['2609']).device;assert port.upper()=='COM8'
    out=a.root/'flash-repair';out.mkdir(exist_ok=a.stage=='repair')
    if a.stage=='repair':
        model=json.loads((ROOT/'BUILD/v2-spi-resident/demo-flash-repair-model.json').read_text());assert model['passed']
        info=json.loads((out/'archive.json').read_text());assert info['passed']
    with (out/('archive-serial.jsonl' if a.stage=='archive' else 'repair-serial.jsonl')).open('x') as log:
        link=Link(port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if b'BM>' in first:link.command('Q')
            link.command('B3')
            def bank_image(bank):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                return b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
            if a.stage=='archive':
                images={}
                for bank in (2,3):
                    data=bank_image(bank);(out/f'before-b{bank}.bin').write_bytes(data);images[bank]=data
                original=(a.root/'flash-b2-before.bin').read_bytes();current=images[2]
                assert current[:0x4240]==original[:0x4240] and current[0x4272:]==original[0x4272:]
                assert current[0x4240:0x4258]==b'SR\x01\x3f\0\x26\x1a\0'+b'DEMO'.ljust(16,b'\0')
                desired=original[0x4000:0x5000];(out/'desired-c-sector.bin').write_bytes(desired)
                (out/'archive.json').write_text(json.dumps(dict(passed=True,b2_sha256=sha(current),b3_sha256=sha(images[3]),sector_sha256=sha(desired)),indent=2)+'\n')
                print('PASS 2609 exact repair preimage archived; only incomplete demo differs from original B2',flush=True)
            else:
                actual=bank_image(2);assert sha(actual)==info['b2_sha256'];link.command('B3')
                transcript=link.command('R MAINT',b'BM> ')
                transcript+=link.command('R 2 C000-CFFF',b'BM> ')
                transcript+=link.command('F 0240-0271 FF',b'BM> ')
                desired=(out/'desired-c-sector.bin').read_bytes()
                display=link.command('D 0000-0FFF',b'BM> ');cells={}
                for line in display.decode('ascii').splitlines():
                    match=re.fullmatch(r'([0-9A-F]{4}):((?: [0-9A-F]{2}){1,16})',line.strip())
                    if match:cells.update((int(match[1],16)+i,v) for i,v in enumerate(bytes.fromhex(match[2])))
                assert set(cells)==set(range(4096)) and bytes(cells[i] for i in range(4096))==desired
                transcript+=link.command('W 2 C000',b'WRITE? TYPE Y> ')
                transcript+=link.command('Y',b'BM> ');assert b'VERIFIED' in transcript
                transcript+=link.command('Q');(out/'repair.txt').write_bytes(transcript)
                after=bank_image(2);assert after==(a.root/'flash-b2-before.bin').read_bytes()
                (out/'after-b2.bin').write_bytes(after);b3=bank_image(3);(out/'after-b3.bin').write_bytes(b3)
                previous=(out/'before-b3.bin').read_bytes()
                assert b3[:0x4000]==previous[:0x4000] and b3[0x6000:]==previous[0x6000:]
                old=journal(previous);new=journal(b3);assert old is not None and new is not None
                counts=lambda record:[int.from_bytes(record[24+i*3:27+i*3],'little') for i in range(32)]
                expected=counts(old);expected[20]+=1
                assert counts(new)==expected and new[8:24]==old[8:24]
                assert int.from_bytes(new[4:8],'little')==int.from_bytes(old[4:8],'little')+1
                report=dict(passed=True,b2_sha256=sha(after),b3_sha256=sha(b3),work_tail_preserved=True,wear_journal_changed=b3!=previous,erase_attempt_delta={'B2:C':1})
                (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
                print('PASS 2609 incomplete demo removed by verified C-sector rewrite; WORK and all other B2 bytes preserved',flush=True)
            link.command('B3')
        finally:link.serial.close()

if __name__=='__main__':main()
