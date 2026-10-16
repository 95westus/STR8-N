"""Fresh retained-device references and physical power retest of fixed helper."""
import json,shutil,sys
import re
from pathlib import Path
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from serial_test_coordination import serial_lease
from deploy_v2_fix006 import ROOT,BASE
import qualify_v2_beta24_power as power


def main():
    stage=sys.argv[1]
    if stage=='reference':
        campaign=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
        with serial_lease('fix006-reference'):
            for b in ('2604','2609'):
                root=BASE/b;port=next(p.device for p in comports() if p.serial_number==SERIALS[b])
                reference=root/'reference';prior=reference/'sram-prior';prior.mkdir(parents=True,exist_ok=False)
                old=ROOT/'output/qualification/beta24-tests-2026-10-14/retry1'/b/'power/sram-final/array-0.bin'
                shutil.copyfile(old,prior/'array-0.bin')
                power.call(power.array,['--root',str(reference),'--board',b,'--port',port,'--stage','final'])
                target=root/'power';(target/'sram-prior').mkdir(parents=True,exist_ok=False)
                shutil.copyfile(reference/'sram-final/array-0.bin',target/'sram-prior/array-0.bin')
                shutil.copyfile(root/'name-state.json',target/'name-state.json')
                power.call(power.devices,['--root',str(target),'--board',b,'--port',port,'--stage','before','--baseline-index',campaign['baseline_index']])
                print('PASS',b,'fresh full SRAM/RTC/EEPROM reference',flush=True)
    elif stage=='capture':
        for b in ('2604','2609'):
            for bank in range(4):shutil.copyfile(BASE/b/f'upgrade/expected-b{bank}.bin',BASE/b/f'final-b{bank}.bin')
        power.call(power,['--root',str(BASE),'--stage','capture','--capture-seconds','900'])
        for b in ('2604','2609'):
            output=(BASE/b/'power/boot.txt').read_bytes()
            message=b'RTCC: PF logging failed.' if b=='2604' else b'RTCC: PF logged, ACK'
            assert message+b'\r\nBoard: LAB-'+b.encode()+b'\r\n' in output,output
        print('PASS STR8N-006 both physical power-fail line boundaries',flush=True)
    elif stage=='verify':
        power.call(power,['--root',str(BASE),'--stage','verify'])
        for b in ('2604','2609'):
            receipt=json.loads((BASE/b/'power/verify-report.json').read_text())
            assert receipt['passed'] and receipt['board_label_separate_line'] and not receipt['known_formatting_issue']
        print('PASS STR8N-006 retest and original-state restoration on both boards',flush=True)
    elif stage=='final':
        from beta4_migration import Link
        from rtc_prompt_sync import establish_b3
        with serial_lease('fix006-final'):
            for b in ('2604','2609'):
                root=BASE/b;port=next(p.device for p in comports() if p.serial_number==SERIALS[b])
                original=json.loads((root/'name-state.json').read_text())['original']
                setting=json.loads((root/'power/devices-before/report.json').read_text())
                with (root/'final-serial.jsonl').open('x') as log:
                    l=Link(port,log)
                    try:
                        establish_b3(l)
                        for slot in ('B','A'):
                            text=l.command('J3',b'Enter default [3s]: ');l.send(slot.encode());text+=l.until(b'\r\nB3> ')
                            assert b'STR8-N 2.0b24' in text
                            if original:assert ('\r\nBoard: '+original+'\r\n').encode() in text
                            else:assert b'Board:' not in text
                            (root/('final-slot-'+slot+'.txt')).write_bytes(text)
                        l.command('R CLOCK',b'CLOCK> ');status=l.command('STATUS',b'CLOCK> ')
                        raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
                        assert raw[7]==setting['control_register'] and raw[8]==setting['trim_register']
                        (root/'final-status.txt').write_bytes(status);l.command('Q',b'> ');l.command('B3')
                        l.command('R MAINT',b'BM> ');reply=l.command('NAME',b'BM> ')
                        assert ('Board: '+(original or 'unnamed')).encode() in reply
                        (root/'final-name.txt').write_bytes(reply);l.command('Q')
                    finally:l.serial.close()
                pending=json.loads((root/'upgrade/install/reset-pending.json').read_text());pending['physical_reset_pending']=False
                (root/'upgrade/install/reset-pending.json').write_text(json.dumps(pending,indent=2)+'\n')
                (root/'final-report.json').write_text(json.dumps(dict(passed=True,board=b,original_name=original,
                    trim_steps=setting['trim_steps'],edu='ON',a_b_startup_verified=True),indent=2)+'\n')
                print('PASS',b,'final A/B startup, original name and RTC trim/control',flush=True)
    else:raise ValueError(stage)


if __name__=='__main__':main()
