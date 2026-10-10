"""Capture an actual S2 reset with live workspace/saved-image evidence.

Temporary SRAM management/image changes are confined to its first 8 KiB;
that region is read twice first and restored/verified on every exit. No flash,
UTC, trim or EEPROM administrative writes. Bootstrap may journal a real outage.
"""
import argparse,hashlib,json,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request,workspace_request
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',default='2609',choices=tuple(SERIALS));p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    qualified=json.loads((BUILD/'workspace/candidate-check.json').read_text());ct=json.loads((BUILD/'hardware-client/test-results.json').read_text())
    assert qualified['passed'] and ct['passed'] and sha((BUILD/'hardware-client/client.bin').read_bytes())==ct['sha256']
    a.root.mkdir(parents=True,exist_ok=False);report=dict(board=a.board,port=a.port,passed=False,flash_written=False,rtc_set=False,trim_changed=False)
    original=None;mutated=False
    with (a.root/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if any(t in first for t in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3')
            def via_snapshot(label):
                # Monitor protects direct I/O display. Use the qualified RAM
                # snapshot pattern; never read either data/handshake register.
                body=bytearray()
                for index,addr in enumerate((0x7FCD,0x7FCE,0x7FCC,0x7FCB,0x7FC2)):
                    body+=bytes((0xAD,addr&255,addr>>8,0x8D,index,0x24))
                body+=bytes.fromhex('4C 67 7E')
                path=a.root/(label+'.s19');path.write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
                load_image(link,path);link.command('G 2000');data=link.dump(0x2400,0x2404)
                values=dict(zip(('IFR','IER','PCR','ACR','DDRB'),data))
                (a.root/(label+'.json')).write_text(json.dumps(values,indent=2)+'\n');return values
            report['via_before']=via_snapshot('via-before')
            assert report['via_before']['IFR']&0x18==0,'Pending CB evidence: archive/setup before diagnostic'
            def bulk(op,privileged=False):
                write(link,0x3E20,bytes((1,3,0xA5 if privileged else 0)));write(link,0x3E00,memory_request(op))
                text=link.command('G 2003');state=link.dump(0x3E10,0x3E38)
                assert state[8]==0 and state[0x23]==state[0x24],text
            def work(req,expected=0):
                write(link,0x3E21,b'\x03');write(link,0x3E40,req)
                text=link.command('G 2006');state=link.dump(0x3E30,0x3E38)
                assert state[8]==expected and state[3]==state[4],(expected,state.hex(),text)
                assert link.dump(0x66AE,0x66AE)==b'\x01'
                return link.dump(0x3E60,0x3E7F)
            load_image(link,BUILD/'hardware-client/client.s19')
            archives=[]
            for i in range(2):
                bulk(1);part=link.dump(0x4000,0x5FFF);(a.root/f'sram-first8k-{i}.bin').write_bytes(part);archives.append(part)
            assert archives[0]==archives[1];original=archives[0]
            assert b'Done' in link.command('R 2 WORK L')
            mutated=True;work(workspace_request(6,key=b'FORMAT!!'))
            assert b'Done' in link.command('R 2 SDEMO L')
            program=link.dump(0x2600,0x2605);assert program==bytes.fromhex('EE 00 27 4C 67 7E')
            link.command('R SRAM',b'SRAM> ');assert b'SRAM: 00' in link.command('S RESETCHK 2600 2605 2600',b'SRAM> ');link.command('Q')
            load_image(link,BUILD/'hardware-client/client.s19');assert b'Done' in link.command('R 2 WORK L')
            h=work(workspace_request(1,size=256))[4:12]
            assert link.dump(0x66AE,0x66AF)==b'\x01\x01'
            report.update(handle_before=h.hex(),sram_backup_sha256=sha(original))
            (a.root/'armed.json').write_text(json.dumps(report|dict(armed=True),indent=2)+'\n')
            print('ARMED',a.board,'PRESS MAIN SXB S2/RESB RESET ONCE',flush=True)
            # Keep the serial session open: no discarded startup stream.
            boot=link.until(b'Enter default [3s]: ',150);link.send(b'\r');boot+=link.until(b'\r\nB3> ')
            (a.root/'physical-reset.txt').write_bytes(boot);assert b'MONITOR A gen' in boot and b'STR8-N 2.0b14' in boot
            latch=link.dump(0x66AE,0x66AF);report['latch_after']=latch.hex();assert latch==b'\x01\0'
            report['via_after']=via_snapshot('via-after')
            link.command('R SRAM',b'SRAM> ');assert b'RESETCHK' in link.command('T',b'SRAM> ');assert b'SRAM: 00' in link.command('R RESETCHK',b'SRAM> ');link.command('Q')
            assert link.dump(0x2600,0x2605)==program
            load_image(link,BUILD/'hardware-client/client.s19');assert b'Done' in link.command('R 2 WORK L')
            work(workspace_request(3,h,count=1),expected=0x4B)
            report.update(passed=True,physical_cold_boot_captured=True,old_handle_rejected=True,saved_image_retained=True)
            print('PASS',a.board,'captured physical S2 cold reset, latch clear, saved image and stale handle',flush=True)
        except Exception as e:
            report['error']=repr(e);raise
        finally:
            if mutated and original is not None:
                try:
                    # Ensure foreground monitor before cleanup after the bounded capture.
                    link.command('',b'\r\nB3> ')
                    load_image(link,BUILD/'hardware-client/client.s19')
                    path=a.root/'restore-first8k.s19';path.write_bytes(s19(dict(enumerate(original,0x4000)),0x4000));load_image(link,path)
                    bulk(2,True);bulk(1);observed=link.dump(0x4000,0x5FFF);assert observed==original
                    (a.root/'sram-first8k-restored.bin').write_bytes(observed);report['sram_restored']=True
                    # Drop the temporary session after returning the original metadata.
                    write(link,0x2300,bytes.fromhex('4C 64 7E'));cold=link.command('G 2300',b'Enter default [3s]: ');link.send(b'\r');cold+=link.until(b'\r\nB3> ')
                    (a.root/'cleanup-software-reset.txt').write_bytes(cold);assert link.dump(0x66AE,0x66AF)==b'\x01\0'
                    report['cleanup_latch_cleared']=True
                except Exception as e:
                    report['cleanup_error']=repr(e);report['passed']=False
                    print('CLEANUP FAILED; preserve power and inspect saved archive',e,flush=True)
            (a.root/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()
            print('RESULT',a.board,json.dumps(report),flush=True)

if __name__=='__main__':main()
