"""Backup-backed named power-on retention test; operator cycles main power."""
import argparse
import binascii
import json
import re
import sys
import time
import serial
from pathlib import Path
from contextlib import ExitStack
from serial.tools.list_ports import comports
from beta4_migration import Link,journal,metadata,config_sum
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from qualify_v2_beta24 import valid_names
from update_v2_beta24 import ROOT,sha
import archive_v2_edu_sram as array
import capture_v2_display_devices as devices
from qualify_v2_beta23_power_retention import records,calendar


def call(module, arguments):
    old=sys.argv
    try:sys.argv=[module.__name__]+arguments;module.main()
    finally:sys.argv=old


def append(l, name):
    before=l.dump(0x9C00,0x9FFF);values=valid_names(before)
    old=max(values)[1] if values else ''
    if name==old:return before
    offset=next(i for i in range(0,1024,32) if before[i:i+32]==b'\xff'*32)
    seq=max((v[0] for v in values),default=0)+1
    r=bytearray(b'\xff'*32);r[:8]=b'BN\x01\0'+seq.to_bytes(4,'little')
    r[8]=len(name);r[9:17]=name.encode().ljust(8,b'\0')
    r[28:30]=binascii.crc_hqx(r[:28],0xFFFF).to_bytes(2,'little');r[31]=0
    target=bytearray(before);target[offset:offset+32]=r
    l.command('R MAINT',b'BM> ')
    l.command('NAME '+(name or 'CLEAR'),b'Save board name? Type YES: ')
    text=l.command('YES',b'BM> ');assert ('Board: '+(name or 'unnamed')).encode() in text
    l.command('Q');actual=l.dump(0x9C00,0x9FFF);assert actual==target
    return actual


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--stage',choices=('prepare','capture','verify'),required=True)
    p.add_argument('--capture-kind',choices=('power','reset'),default='power')
    p.add_argument('--capture-seconds',type=int,default=240);a=p.parse_args()
    assert 1<=a.capture_seconds<=1800
    ports={b:next(p.device for p in comports() if p.serial_number==SERIALS[b]) for b in ('2604','2609')}
    campaign=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
    with serial_lease('beta24-power'):
        if a.stage=='capture':
            with ExitStack() as stack:
                links={};logs={};buffers={b:bytearray() for b in ports}
                for b,port in ports.items():
                    log=stack.enter_context((a.root/b/'power/capture.jsonl').open('a'))
                    logs[b]=log
                    links[b]=Link(port,log);stack.callback(links[b].serial.close)
                print('ARMED: receive-only named '+a.capture_kind+' capture on 2604 and 2609; TX=0',flush=True)
                end=time.monotonic()+a.capture_seconds
                while time.monotonic()<end:
                    for b,l in links.items():
                        try:
                            if l is None:
                                port=next(p.device for p in comports() if p.serial_number==SERIALS[b])
                                l=links[b]=Link(port,logs[b]);stack.callback(l.serial.close)
                            if l.serial.in_waiting:
                                buffers[b].extend(l.read(l.serial.in_waiting))
                                (a.root/b/'power/boot.txt').write_bytes(buffers[b])
                        except (serial.SerialException,OSError,StopIteration):
                            if l is not None:l.serial.close()
                            links[b]=None
                    if all(b'\r\nB3> ' in buf for buf in buffers.values()):break
                    time.sleep(.025)
                for b,buf in buffers.items():
                    assert b'STR8-N 2.0b24' in buf and ('Board: LAB-'+b+'\r\n').encode() in buf and b'\r\nB3> ' in buf,b
                    separate=re.search(('(?:^|\\r\\n)Board: LAB-'+b+'\\r\\n').encode(),buf) is not None
                    (a.root/b/'power/capture-report.json').write_text(json.dumps(dict(passed=True,board=b,capture_kind=a.capture_kind,tx_bytes=0,board_label_separate_line=separate),indent=2)+'\n')
                print('PASS both named physical '+a.capture_kind+' boots',flush=True)
            return
        for b,port in ports.items():
            base=a.root/b;power=base/'power'
            if a.stage=='prepare':
                assert json.loads((base/'report.json').read_text())['passed']
                power.mkdir(exist_ok=False)
            else:
                confirmation=json.loads((a.root/'power-cycle-confirmation.json').read_text())
                assert confirmation.get('operator_confirmed') or confirmation.get('power_cycle_observed')
                boot=(power/'boot.txt').read_bytes()
                captured=json.loads((power/'capture-report.json').read_text())
                assert captured['passed']
                assert ('Board: LAB-'+b+'\r\n').encode() in boot and b'\r\nB3> ' in boot
                assert b'STR8-N 2.0b24' in boot or captured.get('power_fail_boot_captured_without_initial_header')
            call(array,['--root',str(power),'--board',b,'--port',port,'--stage','prior' if a.stage=='prepare' else 'final'])
            call(devices,['--root',str(power),'--board',b,'--port',port,'--stage','before' if a.stage=='prepare' else 'after' if b=='2604' else 'before','--baseline-index',campaign['baseline_index']]) if a.stage=='prepare' or b=='2604' else None
            # For 2609 power-on legitimately appends one outage record, so use
            # a fresh read-only snapshot rather than the no-change comparator.
            if a.stage=='verify' and b=='2609':
                fresh=power/'post-power';fresh.mkdir(exist_ok=False)
                call(devices,['--root',str(fresh),'--board',b,'--port',port,'--stage','before','--baseline-index',campaign['baseline_index']])
                before=power/'devices-before';after=fresh/'devices-before'
                old=(before/'eeprom-0.bin').read_bytes()[:137];new=(after/'eeprom-0.bin').read_bytes()[:137]
                changed=[i for i in range(4) if old[i*32:i*32+32]!=new[i*32:i*32+32]]
                assert len(changed)==1 and old[128:]==new[128:]
                slot=changed[0];previous=records(old);current=records(new)
                assert current[slot]==max(previous.values(),default=0)+1 and new[slot*32+30]==0
                assert (before/'eui.txt').read_bytes()==(after/'eui.txt').read_bytes()
                assert calendar(after/'status.txt')>calendar(before/'status.txt')
            with (power/(a.stage+'-serial.jsonl')).open('x') as log:
                l=Link(port,log)
                try:
                    establish_b3(l)
                    expected3=bytearray((base/'final-b3.bin').read_bytes())
                    if a.stage=='prepare':
                        original=json.loads((base/'report.json').read_text())['original_name_restored']
                        tail=append(l,'LAB-'+b)
                        (power/'name-state.json').write_text(json.dumps(dict(original=original,named_tail=tail.hex()),indent=2)+'\n')
                    else:
                        state=json.loads((power/'name-state.json').read_text());assert l.dump(0x9C00,0x9FFF).hex()==state['named_tail']
                        j=journal(expected3);cfg=bytearray(j[8:24]);assert cfg[13]==0
                        counts=[int.from_bytes(j[24+3*i:27+3*i],'little') for i in range(32)]
                        seq=int.from_bytes(j[4:8],'little');off_saved=False
                        def named_mode(target):
                            nonlocal seq,off_saved
                            offset=max(i for i in range(0,4096,128) if expected3[0x4000+i:0x4080+i]!=b'\xff'*128)+128
                            assert offset<4096,'No room for preserving mode test'
                            l.command('R EDU',b'EDU> ');l.command(target,b'Apply after RESET? [y/N]: ')
                            assert b'Saved; RESET required.' in l.command('Y',b'EDU> ')
                            l.command('Q');off_saved=target=='OFF'
                            cfg[13]=0xA5 if off_saved else 0;cfg[14:]=config_sum(cfg);seq+=1
                            expected3[0x4000+offset:0x4080+offset]=metadata(cfg,counts,seq)
                            boot=l.command('J3',b'Enter default [3s]: ');l.send(b'A');boot+=l.until(b'\r\nB3> ')
                            assert ('Board: LAB-'+b+'\r\n').encode() in boot
                            assert l.dump(0x7D04,0x7D0B)==(b'SV\x01\0\0\0\xff\x66' if off_saved else b'SV\x01\x0f\0\x65\xff\x64')
                            (power/('named-edu-'+target+'.txt')).write_bytes(boot)
                        try:named_mode('OFF')
                        finally:
                            if off_saved:named_mode('ON')
                        tail=append(l,state['original'])
                        boot=l.command('J3',b'Enter default [3s]: ');l.send(b'A');boot+=l.until(b'\r\nB3> ')
                        assert b'STR8-N 2.0b24' in boot
                        if state['original']:assert ('Board: '+state['original']+'\r\n').encode() in boot
                        else:assert b'Board:' not in boot
                        (power/'restored-name-boot.txt').write_bytes(boot)
                    for bank in range(4):
                        prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                        data=b''.join(l.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096))
                        expected=bytearray((base/f'final-b{bank}.bin').read_bytes())
                        if bank==3:
                            expected=expected3;expected[0x1C00:0x2000]=tail
                        assert data==expected,'Power-stage flash mismatch'
                        (power/(a.stage+f'-b{bank}.bin')).write_bytes(data)
                    l.command('B3')
                finally:l.serial.close()
            (power/(a.stage+'-report.json')).write_text(json.dumps(dict(passed=True,board=b,stage=a.stage,
                named_physical_boot_verified=a.stage=='verify',complete_sram_retention=a.stage=='verify',
                capture_kind=json.loads((power/'capture-report.json').read_text())['capture_kind'] if a.stage=='verify' else None,
                power_cycle_operator_confirmed=json.loads((a.root/'power-cycle-confirmation.json').read_text()).get('operator_confirmed',False) if a.stage=='verify' else False,
                power_cycle_observed=a.stage=='verify',
                board_label_separate_line=json.loads((power/'capture-report.json').read_text()).get('board_label_separate_line') if a.stage=='verify' else None,
                known_formatting_issue='STR8N-006' if a.stage=='verify' and not json.loads((power/'capture-report.json').read_text()).get('board_label_separate_line') else None,
                exact_flash_preserved=True,original_name_restored=a.stage=='verify',
                named_edu_on_off_verified=a.stage=='verify'),indent=2)+'\n')
            print('PASS',b,'power stage',a.stage,flush=True)


if __name__=='__main__':main()
