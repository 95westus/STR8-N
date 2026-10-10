"""After repeated physical RESET, read SRAM from all banks; preserve devices."""
import argparse,hashlib,json,re,time
from pathlib import Path
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image
from qualify_v2_spi_storage import memory_request
from serial.tools.list_ports import comports
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--attempt',default='');a=p.parse_args()
    assert all(c.isalnum() or c=='-' for c in a.attempt)
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/('repeat-check'+a.attempt);out.mkdir(exist_ok=False)
    plan=json.loads((a.root/'upgrade/plan.json').read_text())
    build=ROOT/'output/qualification/beta23-phase1-2026-10-09/frozen/build' if plan['version']=='2.0b23' else ROOT/'BUILD/v2-spi-resident'
    via=json.loads((a.root/'repeat-via/report.json').read_text());assert not via['port_read_acknowledged']
    report=dict(board=a.board,clock_set=False,trim_changed=False,sram_data_written=False,via=via)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            link.command('');text=link.command('TIME');(out/'time.txt').write_bytes(text)
            if a.board=='2512':
                assert link.dump(0x7D04,0x7D0B)==b'SV\x01\0\0\0\xff\x66'
                assert b'RTCC: unavailable' in text;report['edu_mode']='OFF'
            else:
                assert via['IFR']&0x18==0 and via['IER']&0x18==0 and via['DDRB']==0
                load_image(link,build/'hardware-client/client.s19')
                banks=[]
                for bank in range(4):
                    link.write_ram(0x3E20,bytes((1,bank,0)));link.write_ram(0x3E00,memory_request(1,0,64,0x4000))
                    (out/f'bank-{bank}.txt').write_bytes(link.command('G 2000'))
                    r=link.dump(0x3E10,0x3E38);(out/f'bank-{bank}.bin').write_bytes(r)
                    assert r[8:10]==b'\0\x40' and r[0x23]==r[0x24]
                    assert link.dump(0x4000,0x403F)==(a.root/'sram-prior/array-0.bin').read_bytes()[:64]
                    banks.append(bank)
                report['read_success_caller_banks']=banks
                link.command('R CLOCK',b'CLOCK> ')
                for command in ('STATUS','HISTORY','EUI'):
                    data=link.command(command,b'CLOCK> ');(out/(command.lower()+'.txt')).write_bytes(data)
                    if command!='STATUS':assert data==(a.root/'devices-before'/(command.lower()+'.txt')).read_bytes()
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',(out/'status.txt').read_bytes())[1].decode())
                magnitude=18 if a.board=='2205' else 14;assert raw[7:9]==bytes([0x80,magnitude])
                report.update(trim_steps=-magnitude,history_preserved=True,identity_preserved=True)
                link.command('Q')
            if plan['version']=='2.0b23':
                probes=ROOT/'BUILD/v2-board-regression'
                service=json.loads((probes/'service-build.json').read_text())
                assert load_image(link,probes/'service.s19')==service['sha256']
                text=link.command('G 200C');(out/'rtc-all-banks.txt').write_bytes(text)
                if a.board=='2512':
                    assert b'Services unavailable' in text
                    report['rtc_unavailable_before_call']=True
                else:
                    assert b'RTC banks preserved' in text
                    assert link.dump(0x2450,0x2453)==bytes(4)
                    report['rtc_caller_banks']=[0,1,2,3]
            report['passed']=True;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
        finally:link.serial.close()

if __name__=='__main__':main()
