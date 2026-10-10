"""Read-only pre/post flash device evidence; never sets UTC or trim."""
import argparse,hashlib,json,re,time
from pathlib import Path
from beta4_migration import Link
from qualify_v2_spi_install import load_image
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--board',choices=tuple(SERIALS),required=True);p.add_argument('--port',required=True);p.add_argument('--stage',choices=('before','after'),required=True);p.add_argument('--baseline-index',type=Path);a=p.parse_args()
    expected_boards={b['board']:b for b in json.loads(a.baseline_index.read_text())['boards']} if a.baseline_index else {}
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    out=a.root/('devices-'+a.stage);out.mkdir(exist_ok=False)
    report=dict(board=a.board,stage=a.stage,clock_set=False,trim_changed=False,eeprom_written=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ');(out/'startup.txt').write_bytes(initial)
            assert re.search(rb'B[0-3]> $',initial),'Monitor not ready'
            link.command('B3')
            descriptor=link.dump(0x7D04,0x7D0B);report['service_descriptor']=descriptor.hex()
            (out/'time.txt').write_bytes(link.command('TIME'))
            if a.board=='2512' and a.board not in expected_boards:
                assert descriptor==b'SV\x01\0\0\0\xff\x66'
                assert b'RTCC: unavailable' in (out/'time.txt').read_bytes()
                report.update(edu_mode='OFF',rtc_available=False)
            else:
                assert descriptor==b'SV\x01\x0f\0\x65\xff\x64'
                start=link.command('R CLOCK',b'CLOCK> ');(out/'clock-start.txt').write_bytes(start)
                for command in ('STATUS','HISTORY','EUI','TRIM'):
                    text=link.command(command,b'CLOCK> ');(out/(command.lower()+'.txt')).write_bytes(text)
                status=(out/'status.txt').read_bytes()
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
                setting=expected_boards.get(a.board,{});steps=setting.get('trim_steps',-18 if a.board=='2205' else -14)
                expected=abs(steps)|(0x80 if steps>0 else 0);control=setting.get('control_register',0x80)
                assert raw[7:9]==bytes([control,expected]),'Current normal trim differs from calibrated expectation'
                assert b'Running: yes' in status and b'Backup enabled: yes' in status
                identity=(out/'eui.txt').read_bytes();assert b', changed' not in identity and (b', unbound' not in identity)==setting.get('identity_bound',True)
                if 'eui' in setting: assert setting['eui'].encode() in identity
                link.command('Q')
                probe=ROOT/'BUILD/v2-eeprom-inventory/probe.s19';images=[]
                for i in range(2):
                    load_image(link,probe);link.command('G 2000');data=link.dump(0x2400,0x2494)
                    (out/f'eeprom-{i}.bin').write_bytes(data);assert data[0x90]==0 and data[0x91]==data[0x92]
                    assert (data[0x93]^data[0x94])&data[0x91]==0
                    images.append(data[:0x89])
                assert images[0]==images[1],'EEPROM repeated read mismatch'
                report.update(edu_mode='ON',rtc_available=True,trim_steps=steps,control_register=raw[7],trim_register=raw[8],eeprom_sha256=hashlib.sha256(images[0]).hexdigest())
                if a.stage=='after':
                    before=a.root/'devices-before'
                    for name in ('history.txt','eui.txt'):assert (out/name).read_bytes()==(before/name).read_bytes(),name+' changed'
                    assert images[0]==(before/'eeprom-0.bin').read_bytes()[:0x89],'EEPROM changed'
                    old=json.loads((before/'report.json').read_text());assert old['trim_steps']==report['trim_steps']
                    report.update(history_preserved=True,identity_preserved=True,eeprom_preserved=True)
            report['passed']=True;(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
        finally:link.serial.close()

if __name__=='__main__':main()
