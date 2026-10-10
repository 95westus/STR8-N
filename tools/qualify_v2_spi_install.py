"""Readback/RTC/optional-hardware qualification after physical resident RESET."""
import argparse,hashlib,json,re,time
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def read_application_s19(path):
    """Validate a dense RAM application without relaxing installer limits."""
    cells={};entry=None
    for line in Path(path).read_text(encoding='ascii').splitlines():
        if entry is not None:raise ValueError('Records after S9 application entry')
        if not re.fullmatch(r'S[019][0-9A-Fa-f]+',line):raise ValueError('Unsupported application S-record')
        try:raw=bytes.fromhex(line[2:])
        except ValueError as e:raise ValueError('Invalid application S-record hex') from e
        if len(raw)<4 or len(raw)!=raw[0]+1 or sum(raw)&255!=255:
            raise ValueError('Application S-record checksum/count mismatch')
        address=int.from_bytes(raw[1:3],'big')
        if line[1]=='1':
            for offset,value in enumerate(raw[3:-1],address):
                if offset in cells:raise ValueError('Application S-record overlap')
                cells[offset]=value
        elif line[1]=='9':
            if len(raw)!=4:raise ValueError('Invalid S9 application entry')
            entry=address
    if not cells or entry is None or set(cells)!=set(range(min(cells),max(cells)+1)):
        raise ValueError('Incomplete/sparse RAM application')
    if not 0x2000<=min(cells)<=entry<=max(cells)<=0x64FF:
        raise ValueError('RAM application outside approved range')
    return cells,entry

def load_image(link,path):
    cells,entry=read_application_s19(path)
    link.command('L',b'S19')
    for row in Path(path).read_bytes().splitlines():link.send(row+b'\r\n');time.sleep(.04)
    link.until(b'\r\nB3> ')
    body=bytes(cells[a] for a in range(min(cells),max(cells)+1))
    assert link.dump(min(cells),max(cells))==body,'RAM load verification failed'
    return sha(body)

def write(link,address,data):
    link.write_ram(address,data)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True)
    p.add_argument('--attempt',default='');p.add_argument('--resume-after-via-setup',action='store_true');a=p.parse_args()
    assert next(p for p in comports() if p.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());out=a.root/('resident-check'+a.attempt);out.mkdir(exist_ok=False)
    report=dict(board=a.board,port=a.port,clock_set=False,trim_changed=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            initial=link.command('',b'> ');(out/'physical-reset.txt').write_bytes(initial)
            if b'CLOCK>' in initial or b'BM>' in initial:link.command('Q')
            link.command('B3')
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                (out/f'b{bank}.bin').write_bytes(data);assert data==(a.root/f'upgrade/expected-b{bank}.bin').read_bytes()
                hashes.append(sha(data));print('PASS',a.board,'installed B'+str(bank),flush=True)
            link.command('B3')
            if a.resume_after_via_setup:
                assert a.board=='2609' and len(list((a.root/'resident-check').glob('slot-*.txt')))==3
                assert all(b'STR8-N 2.0b14' in f.read_bytes() for f in (a.root/'resident-check').glob('slot-*.txt'))
            for slot in (() if a.resume_after_via_setup else ('A','B','A')):
                link.command('G F004',b'Enter default [3s]: ');link.send(slot.encode());data=link.until(b'\r\nB3> ')
                (out/f'slot-{slot}-{time.monotonic_ns()}.txt').write_bytes(data);assert b'STR8-N 2.0b14' in data
                assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0F\0\x65\xff\x64'
                assert link.dump(0x66AE,0x66AF)==b'\x01\0'
            # Model-qualified preserving client and public denial before use.
            load_image(link,BUILD/'hardware-client/client.s19')
            for bank in range(4):
                write(link,0x3E20,bytes((1,bank,0)))
                write(link,0x3E00,bytes((2,0,0,0,0,0,0x40,1,0,0,0,0,0,0,0,0)))
                link.command('G 2000');result=link.dump(0x3E10,0x3E38);assert result[8]==6 and result[0x23]==result[0x24]
                write(link,0x3E00,bytes(16));link.command('G 2000');result=link.dump(0x3E10,0x3E38)
                assert result[8]==(7 if a.board=='2512' else 0) and result[0x23]==result[0x24]
            status=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.5' in status
            status=link.command('STATUS',b'CLOCK> ');(out/'clock-status.txt').write_bytes(status)
            history=link.command('HISTORY',b'CLOCK> ');(out/'history.txt').write_bytes(history)
            identity=link.command('EUI',b'CLOCK> ');(out/'eui.txt').write_bytes(identity);link.command('Q')
            if a.board!='2512':
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
                assert raw[7:9]==b'\x80\0' and b'Running: yes' in status and b'Backup enabled: yes' in status
                assert b', changed' not in identity and b', unbound' not in identity
                assert history==(a.root/'prior/history-prior.txt').read_bytes()
            else:assert b'RTCC: EUI unavailable' in identity
            # EEPROM and factory/status repeated readback after RESET.
            inventories=[]
            for i in range(2):
                load_image(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000')
                data=link.dump(0x2400,0x2494);(out/f'eeprom-{i}.bin').write_bytes(data);inventories.append(data)
            assert inventories[0]==inventories[1]
            assert inventories[0][:128]==(a.root/'eeprom-prior/array.bin').read_bytes()
            assert inventories[0][0x80:0x89]==(a.root/'eeprom-prior/status-factory.bin').read_bytes()
            report.update(passed=True,installed_hashes=hashes,both_slots_verified=True,raw_write_denied=True,
                sram_present=a.board!='2512',eeprom_preserved=True,identity_preserved=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            if a.attempt:
                report['successful_attempt']=out.name
                (a.root/'resident-check/report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS',a.board,'resident beta14, both slots, optional SRAM, public denial, retained CLOCK/EEPROM/EUI',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
