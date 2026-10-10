"""Preserving 2609 storage timings: timer SRAM, host-bracketed stock flash."""
import argparse,hashlib,json,statistics,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,fnv,s19,journal
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-storage';sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);a=p.parse_args();out=a.root;out.mkdir(parents=True,exist_ok=False)
    assert next(x for x in comports() if x.device.upper()=='COM8').serial_number==SERIALS['2609']
    check=json.loads((BUILD/'timing/model-check.json').read_text());assert check['passed']
    model=json.loads((BUILD/'timing/sram-cycle-model.json').read_text());assert max(r['max_call_cycles'] for r in model['results'])<65536
    report=dict(board='2609',clock_hz=8000000,flash_sector='B2:D000-DFFF',sram_range='18000-18FFF',sram=[],flash=[],flash_method='host command-to-marker with matched no-op baseline; approximate, no console HOLD/readback inside interval',sram_method='VIA Timer 2 cycle counter sampled between <=64-byte calls; excludes serial and later verify; includes API/mode checks and tiny probe bookkeeping')
    link=None;sram_original=None;flash_erased=True
    with (out/'serial.jsonl').open('x') as log:
        link=Link('COM8',log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if any(x in first for x in (b'CLOCK>',b'SRAM>',b'WORK>',b'EDU>',b'BM>')):link.command('Q')
            link.command('B2',b'\r\nB2> ');before=link.dump(0x8000,0xFFFF,b'\r\nB2> ');(out/'before-b2.bin').write_bytes(before)
            assert before[0x5000:0x6000]==b'\xff'*4096,'Scratch sector not empty; no erase/write'
            link.command('B3');b3=link.dump(0x8000,0xFFFF);(out/'before-b3.bin').write_bytes(b3)
            # Monitor D refuses I/O registers. The separate RAM snapshot and
            # probe's live IER refusal protect borrowing this idle timer.
            via=json.loads((ROOT/'output/qualification/storage-timing-2026-10-08-2609-via/report.json').read_text())
            assert not via['IER']&0x7F and not via['ACR']&0x1F,'VIA is not idle'
            load_image(link,BUILD/'timing/probe.s19')
            def run(op,n=1):
                write(link,0x6200,bytes((op,0,n&255,n>>8)));start=time.perf_counter();link.send(b'G 2000\r');marker=link.until(b'~');elapsed=time.perf_counter()-start;link.until(b'\r\nB3> ')
                data=link.dump(0x6210,0x6214);assert data[4]==0,(op,n,data.hex(),marker[-100:])
                return int.from_bytes(data[:4],'little'),elapsed
            # READ itself warms the resident code cache and changes no SRAM.
            run(4,4096);sram_original=link.dump(0x4000,0x4FFF);(out/'sram-original.bin').write_bytes(sram_original)
            def buffer(data,label):
                path=out/(label+'.s19');path.write_bytes(s19(dict(enumerate(data,0x4000)),0x4000));load_image(link,path)
            for fill in (0,0x55,0xFF):
                buffer(bytes([fill])*4096,f'pattern-{fill:02x}')
                for n in (1,32,64,256,1024,4096):
                    values=[run(0,n)[0] for _ in range(3)]
                    report['sram'].append(dict(fill=fill,size=n,cycles=values,ms_min=min(values)/8000,ms_max=max(values)/8000,ms_median=statistics.median(values)/8000))
                    print('SRAM',n,'fill',hex(fill),f'{statistics.median(values)/8000:.4f} ms',flush=True)
                run(4,4096);assert link.dump(0x4000,0x4FFF)==bytes([fill])*4096
            buffer(sram_original,'restore-sram');run(0,4096);run(4,4096);assert link.dump(0x4000,0x4FFF)==sram_original
            report['sram_restored']=True
            # No-op baseline quantifies transport/parser/fill overhead. Flash
            # operations use the original worker and preserve durable wear counts.
            blank=[run(5)[1] for _ in range(9)];fillbase=[run(6)[1] for _ in range(9)]
            report['host_baseline_ms']=[x*1000 for x in blank];report['host_fill_baseline_ms']=[x*1000 for x in fillbase]
            for repeat in range(3):
                flash_erased=False;_,program=run(2)
                link.command('B2',b'\r\nB2> ');assert link.dump(0xD000,0xDFFF,b'\r\nB2> ')==b'\x55'*4096;link.command('B3')
                run(3);_,erase=run(1);flash_erased=True
                link.command('B2',b'\r\nB2> ');assert link.dump(0xD000,0xDFFF,b'\r\nB2> ')==b'\xff'*4096;link.command('B3')
                report['flash'].append(dict(repeat=repeat+1,program_ms_raw=program*1000,erase_ms_raw=erase*1000,program_ms_adjusted=(program-statistics.median(fillbase))*1000,erase_ms_adjusted=(erase-statistics.median(blank))*1000))
                print('FLASH',repeat+1,f'write {program*1000:.3f} ms raw; erase {erase*1000:.3f} ms raw',flush=True)
            link.command('B2',b'\r\nB2> ');after=link.dump(0x8000,0xFFFF,b'\r\nB2> ');assert after==before;(out/'after-b2.bin').write_bytes(after);link.command('B3')
            after3=link.dump(0x8000,0xFFFF);(out/'after-b3.bin').write_bytes(after3);oldj=journal(b3);newj=journal(after3)
            assert oldj[8:24]==newj[8:24]
            oldcounts=[int.from_bytes(oldj[24+3*i:27+3*i],'little') for i in range(32)];newcounts=[int.from_bytes(newj[24+3*i:27+3*i],'little') for i in range(32)]
            oldcounts[21]+=3;assert oldcounts==newcounts
            assert after3[:0x4000]==b3[:0x4000] and after3[0x6000:]==b3[0x6000:]
            report.update(passed=True,flash_restored=True,flash_sha256=sha(after),erase_count_increment=3,firmware_changed=False)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS timing measurements; SRAM restored; scratch flash erased; firmware intact; wear counts recorded',flush=True)
        finally:
            if link:
                if sram_original is not None and not report.get('sram_restored'):
                    try:buffer(sram_original,'emergency-restore-sram');run(0,4096);run(4,4096);assert link.dump(0x4000,0x4FFF)==sram_original
                    except Exception as e:report['sram_restore_error']=repr(e)
                if not flash_erased:
                    try:run(3);run(1);report['emergency_flash_erase']=True
                    except Exception as e:report['flash_restore_error']=repr(e)
                (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()

if __name__=='__main__':main()
