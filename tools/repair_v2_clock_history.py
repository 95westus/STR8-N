"""2604-only, backed-up foreign-history initialization and saved-event ACK."""
import json,re,time
from pathlib import Path
from beta4_migration import Link
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease
from qualify_v2_spi_install import load_image
from qualify_v2_beta23_power_retention import records,calendar
import migrate_v2 as u

ROOT=u.ROOT;BASE=ROOT/'output/qualification/beta25-recovery-2026-10-14/2604'

def main():
    prior=BASE/'retained/devices-before';original=(prior/'eeprom-0.bin').read_bytes()[:137]
    assert original==(prior/'eeprom-1.bin').read_bytes()[:137]
    expected=bytearray(b'\xff'*128);expected[32]=0;assert original[:128]==expected,'Foreign contents differ; do not initialize automatically'
    assert u.read(BASE/'clock-history-model.json')['passed'] and u.read(BASE/'retained/sram-prior/report.json')['repeat_verified']
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2604']);out=BASE/'clock-repair';out.mkdir(exist_ok=False)
    with serial_lease('2604-clock-history-repair'),(out/'serial.jsonl').open('x') as log:
        l=Link(port,log)
        try:
            establish_b3(l)
            def eeprom():
                load_image(l,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');l.command('G 2000');data=l.dump(0x2400,0x2494)
                assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
                return data[:137]
            assert eeprom()==original,'EEPROM changed since backup'
            l.command('R CLOCK',b'CLOCK> ');before=l.command('STATUS',b'CLOCK> ');(out/'status-before.txt').write_bytes(before)
            assert b'Power-fail latched: yes' in before
            assert b'History unavailable/error 90' in l.command('HISTORY',b'CLOCK> ')
            text=l.command('CLEAR ALL',b'Type DELETE ALL: ')+l.command('DELETE ALL',b'CLOCK> ')
            assert b'History cleared.' in text;text+=l.command('HISTORY',b'CLOCK> ')
            assert b'History unavailable' not in text
            status=l.command('STATUS',b'CLOCK> ');assert b'Power-fail latched: yes' in status
            text+=l.command('ACK',b'Type YES to confirm: ')+l.command('YES',b'CLOCK> ')
            assert b'latch verified clear' in text,text
            (out/'repair.txt').write_bytes(text)
            after=l.command('STATUS',b'CLOCK> ');(out/'status-after.txt').write_bytes(after)
            assert b'Power-fail latched: no' in after
            history=l.command('HISTORY',b'CLOCK> ');(out/'history.txt').write_bytes(history);assert b'History unavailable' not in history
            (out/'show-1.txt').write_bytes(l.command('SHOW 1',b'CLOCK> '));(out/'eui.txt').write_bytes(l.command('EUI',b'CLOCK> '));l.command('Q')
            image=eeprom();assert image==eeprom();(out/'eeprom-repaired.bin').write_bytes(image)
            assert image[128:]==original[128:] and records(image)=={0:1} and image[30]==0
            raw=lambda s:bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',s)[1].decode())
            assert raw(before)[7:9]==raw(after)[7:9]==b'\0\x0C'
            outage=bytes.fromhex(re.search(rb'Power-fail down/up \(raw, minute precision\): ([0-9A-F ]+)',before)[1].decode())
            assert image[12:20]==outage
            assert (out/'eui.txt').read_bytes()==(prior/'eui.txt').read_bytes()
            hashes=[]
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt);b=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                assert b==(BASE/f'prior-verified/b{bank}.bin').read_bytes();hashes.append(u.sha(b))
            l.command('B3');boot=l.command('J3');(out/'boot.txt').write_bytes(boot)
            assert b'STR8-N 2.0b25' in boot and b'PF logging failed' not in boot
            l.command('R CLOCK',b'CLOCK> ');assert b'History unavailable' not in l.command('HISTORY',b'CLOCK> ');assert b'Power-fail latched: no' in l.command('STATUS',b'CLOCK> ');l.command('Q')
            result=dict(passed=True,board='2604',history_initialized=True,prior_history_sha256=u.sha(original),new_history_sha256=u.sha(image),
                saved_latched_outage_sequence=1,ack_verified=True,raw_outage=outage.hex(),rtc_control_trim_preserved=True,factory_status_eui_preserved=True,
                eui_binding_unchanged=True,flash_hashes=hashes,clock_set=False,trim_changed=False,software_boot_passed=True)
            (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS 2604 history initialized; original outage saved/verified and acknowledged; restart has no history failure; flash/control/trim/factory/EUI preserved',flush=True)
        finally:l.serial.close()

if __name__=='__main__':main()
