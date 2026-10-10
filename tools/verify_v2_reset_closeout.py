"""Final read-only 2609 verification after the captured correct-button test."""
import argparse,hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s19
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request
from qualify_v2_journal_board import records
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--phase6-root',required=True,type=Path);p.add_argument('--port',default='COM8');p.add_argument('--attempt',default='');p.add_argument('--reuse-readbacks',action='store_true');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS['2609']
    capture=json.loads((a.root/'report.json').read_text());assert all(capture[k] for k in ('passed','physical_cold_boot_captured','old_handle_rejected','saved_image_retained','sram_restored','cleanup_latch_cleared'))
    source=a.phase6_root/'2609';out=a.root/('closeout'+a.attempt)
    if a.reuse_readbacks:assert (out/'sram-final.bin').exists() and all((out/f'b{b}.bin').exists() for b in range(4))
    else:out.mkdir(exist_ok=False)
    report=dict(board='2609',flash_written=False,clock_set=False,trim_changed=False,readbacks_reused=a.reuse_readbacks)
    with (out/('serial-finish.jsonl' if a.reuse_readbacks else 'serial.jsonl')).open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            link.command('');link.command('B3');assert link.dump(0x66AE,0x66AF)==b'\x01\0'
            # Five passive snapshots: no ORB read/acknowledgement and no mode writes.
            body=bytearray()
            for i,addr in enumerate((0x7FCD,0x7FCE,0x7FCC,0x7FCB,0x7FC2)):
                body+=bytes((0xAD,addr&255,addr>>8,0x8D,i,0x24))
            body+=bytes.fromhex('4C 67 7E');path=out/'via-snapshot.s19';path.write_bytes(s19(dict(enumerate(body,0x2000)),0x2000));load_image(link,path)
            samples=[]
            for i in range(5):
                link.command('G 2000');data=link.dump(0x2400,0x2404);samples.append(dict(zip(('IFR','IER','PCR','ACR','DDRB'),data)));time.sleep(.1)
            report['passive_via_samples']=samples
            assert all(s['IFR']&0x18==0 and s['IER']==0x80 and s['PCR']==s['ACR']==s['DDRB']==0 for s in samples)
            original=(source/'spi-archive/array.bin').read_bytes()
            if a.reuse_readbacks:
                array=(out/'sram-final.bin').read_bytes();assert array==original
            else:
                load_image(link,BUILD/'hardware-client/client.s19');parts=[]
                for i in range(16):
                    write(link,0x3E20,bytes((1,3,0)));write(link,0x3E00,memory_request(1,i*8192))
                    link.command('G 2003');assert link.dump(0x3E18,0x3E18)==b'\0'
                    part=link.dump(0x4000,0x5FFF);assert part==original[i*8192:(i+1)*8192];parts.append(part)
                    print('PASS 2609 unchanged SRAM',i+1,'/16',flush=True)
                array=b''.join(parts);(out/'sram-final.bin').write_bytes(array)
            report['sram_sha256']=sha(array)
            hashes=[]
            for bank in range(4):
                if a.reuse_readbacks:image=(out/f'b{bank}.bin').read_bytes()
                else:
                    prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                    image=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096));(out/f'b{bank}.bin').write_bytes(image)
                assert image==(source/f'final-check/b{bank}.bin').read_bytes();hashes.append(sha(image))
                print('PASS 2609 unchanged flash B'+str(bank),flush=True)
            link.command('B3');link.command('R CLOCK',b'CLOCK> ')
            status=link.command('STATUS',b'CLOCK> ');history=link.command('HISTORY',b'CLOCK> ');eui=link.command('EUI',b'CLOCK> ');link.command('Q')
            (out/'clock-status.txt').write_bytes(status);(out/'history.txt').write_bytes(history);(out/'eui.txt').write_bytes(eui)
            raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode());assert raw[7:9]==b'\x80\0'
            assert b'Running: yes' in status and b'Backup enabled: yes' in status and b'Power-fail latched: no' in status
            assert eui==(source/'final-check/eui.txt').read_bytes()
            ee=[]
            for i in range(2):
                load_image(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000');data=link.dump(0x2400,0x2494);ee.append(data);(out/f'eeprom-{i}.bin').write_bytes(data)
            assert ee[0]==ee[1]
            old=(source/'final-check/eeprom-0.bin').read_bytes();assert ee[0][128:137]==old[128:137]
            oldrows=records(old[:128]);current=records(ee[0][:128]);maximum=max(r['sequence'] for r in oldrows)
            additions=[r for r in current if r['sequence']>maximum]
            if ee[0][:128]!=old[:128]:
                assert len(additions)==1 and additions[0]['sequence']==maximum+1 and additions[0]['clearance']==0
                changed=additions[0]['slot']-1
                for slot in range(4):
                    if slot!=changed:assert ee[0][slot*32:(slot+1)*32]==old[slot*32:(slot+1)*32]
                c=bytes.fromhex(additions[0]['capture'])
                recorded=datetime(int.from_bytes(c[:2],'little'),c[2],c[3],c[5],c[6],c[7],tzinfo=timezone.utc)
                start=datetime.fromtimestamp(json.loads((a.root/'serial.jsonl').read_text().splitlines()[0])['time'],timezone.utc)
                raw_up=bytes.fromhex(additions[0]['outage'])[4:]
                bcd=lambda v:(v>>4)*10+(v&15)
                up=datetime(recorded.year,bcd(raw_up[3]&0x1F),bcd(raw_up[2]&0x3F),bcd(raw_up[1]&0x3F),bcd(raw_up[0]&0x7F),tzinfo=timezone.utc)
                assert recorded<start and (start-up).total_seconds()>60,'Outage did not precede the captured test; inspect separately'
                report['preexisting_outage_since_phase6']=additions[0]
                report['preexisting_outage_capture_utc']=recorded.isoformat()
                report['preexisting_power_up_utc_inferred_year']=up.isoformat()
                report['diagnostic_start_utc']=start.isoformat()
            else:assert history==(source/'final-check/history.txt').read_bytes()
            assert link.dump(0x66AE,0x66AF)==b'\x01\0'
            report.update(passed=True,final_flash_hashes=hashes,eui_factory_preserved=True,other_eeprom_slots_preserved=True,control_trim='8000',latch_final='0100',ports_closed=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            (a.root/'closeout-index.json').write_text(json.dumps(dict(stage=out.name),indent=2)+'\n')
            print('PASS 2609 correct physical RESET closeout; SRAM/flash/settings/identity preserved, recorded preexisting outage retained; stable passive VIA flags',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
