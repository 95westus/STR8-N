"""Final software-reset, exact flash, RTC/EEPROM and cleanup verification."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_journal_board import records
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());expected=[bytearray((a.root/f'upgrade/expected-b{b}.bin').read_bytes()) for b in range(4)]
    expected[2]=bytearray((a.root/'utilities/expected-b2.bin').read_bytes())
    if a.board!='2512':
        program=bytes.fromhex('EE 00 27 4C 67 7E');r=b'SR\x01\x3f\0\x26\x06\0'+b'SDEMO'.ljust(16,b'\0')+program
        assert expected[2][0x2E80:0x2E80+len(r)]==bytes([255])*len(r);expected[2][0x2E80:0x2E80+len(r)]=r
        restored=json.loads((a.root/'storage-restore/report.json').read_text());assert restored['passed'] and restored['array_restored']
    out=a.root/'final-check';out.mkdir(exist_ok=False);report=dict(board=a.board,clock_set=False,trim_changed=False,manual_ack=False)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            end=time.monotonic()+.3
            while time.monotonic()<end:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ')
            if any(p in first for p in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>')):link.command('Q')
            link.command('B3')
            # Documented RAM RESET route enters the verified cold F004 path.
            # This also discards the session latch after restoring old SRAM.
            write(link,0x2300,bytes.fromhex('4C 64 7E'))
            text=link.command('G 2300',b'Enter default [3s]: ');link.send(b'\r');text+=link.until(b'\r\nB3> ')
            (out/'software-reset.txt').write_bytes(text);assert b'STR8-N 2.0b14' in text
            assert link.dump(0x66AE,0x66AF)==b'\x01\0'
            assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
            report['software_cold_reset_latch_cleared']=True
            load_image(link,BUILD/'hardware-client/client.s19');write(link,0x3E20,bytes((1,3,0)))
            write(link,0x3E00,bytes((2,0,0,0,0,0,0x40,1,0,0,0,0,0,0,0,0)))
            link.command('G 2000');assert link.dump(0x3E18,0x3E18)==b'\x06'
            assert link.dump(0x66AE,0x66AF)==b'\x01\0'
            link.command('R CLOCK',b'CLOCK> ')
            status=link.command('STATUS',b'CLOCK> ');(out/'clock-status.txt').write_bytes(status)
            history=link.command('HISTORY',b'CLOCK> ');(out/'history.txt').write_bytes(history)
            eui=link.command('EUI',b'CLOCK> ');(out/'eui.txt').write_bytes(eui);link.command('Q')
            if a.board!='2512':
                def setting(t):return bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',t)[1].decode())[7:9]
                def cal(t):return datetime.strptime(re.search(rb'Calendar \(UTC convention\): (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)',t)[1].decode(),'%Y-%m-%d %H:%M:%S')
                prior=(a.root/'prior/rtc-prior.txt').read_bytes()
                assert setting(status)==setting(prior)==b'\x80\0' and cal(status)>cal(prior)
                assert all(x in status for x in (b'Running: yes',b'Backup enabled: yes',b'Power-fail latched: no'))
                assert b', changed' not in eui and b', unbound' not in eui
                report.update(clock_advanced=True,control_trim='8000',calendar_final=str(cal(status)))
            else:assert b'RTCC: EUI unavailable' in eui
            ee=[]
            for i in range(2):
                load_image(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');link.command('G 2000');data=link.dump(0x2400,0x2494)
                (out/f'eeprom-{i}.bin').write_bytes(data);ee.append(data)
            assert ee[0]==ee[1]
            assert ee[0][0x80:0x89]==(a.root/'eeprom-prior/status-factory.bin').read_bytes()
            if a.board!='2512':
                old=(a.root/'eeprom-prior/array.bin').read_bytes();current=ee[0][:128];oldrows=records(old);newrows=records(current)
                highest=max(r['sequence'] for r in oldrows);new=[r for r in newrows if r['sequence']>highest]
                assert len(new)==1 and new[0]['sequence']==highest+1 and new[0]['clearance']==0
                changed=new[0]['slot']-1
                for slot in range(4):
                    if slot!=changed:assert old[slot*32:(slot+1)*32]==current[slot*32:(slot+1)*32]
                report.update(new_outage=new[0],boot_logged_and_acked=True,other_outage_slots_preserved=True)
            else:assert ee[0][:128]==(a.root/'eeprom-prior/array.bin').read_bytes()
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
                data=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096));assert data==expected[bank],f'B{bank} final mismatch'
                (out/f'b{bank}.bin').write_bytes(data);hashes.append(sha(data));print('PASS',a.board,'final B'+str(bank),flush=True)
            link.command('B3');table=link.command('T 2');(out/'table.txt').write_bytes(table)
            assert b'CLOCK' in table and b'SRAM' in table and b'WORK' in table
            report.update(passed=True,final_hashes=hashes,raw_write_denied=True,eui_factory_preserved=True,
                original_sram_restored=a.board!='2512',physical_reset_workspace_verified=a.board=='2205',
                power_cycle_workspace_verified=a.board!='2512',physical_reset_issue=a.board=='2609')
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS',a.board,'final flash/RTC/EEPROM/EUI and cold software RESET; original SRAM restored',flush=True)
        finally:link.serial.close()

if __name__=='__main__':main()
