"""Physical startup shortcuts, recovery and exact retained-device verification."""
import json,time,shutil
from contextlib import ExitStack
from deploy_v2_startup_keys import BASE,ROOT,BUILD,REPAIR_BASE,port
from beta4_migration import Link
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from qualify_v2_beta24 import valid_names
from qualify_v2_spi_install import load_image
import qualify_v2_beta24_power as power
import run_beta23_soak as smoke

PROMPT=b'\r\nB3> '
MENU=b'Enter default [3s]: '
BOARDS=('2604','2609')
GENERATION=34
RETEST_NAME='corrected-retest'
CAPTURE_STEM='physical-reset-corrected'

def capture():
    with serial_lease('startup-key-reset-capture'),ExitStack() as stack:
        links={};buffers={}
        for b in BOARDS:
            log=stack.enter_context((BASE/b/(CAPTURE_STEM+'.jsonl')).open('x'))
            links[b]=Link(port(b),log);stack.callback(links[b].serial.close);buffers[b]=bytearray()
        print('ARMED: receive-only physical RESET capture on '+', '.join(BOARDS)+' for 15 minutes',flush=True)
        end=time.monotonic()+900
        while time.monotonic()<end:
            for b,l in links.items():
                if l.serial.in_waiting:
                    buffers[b].extend(l.read(l.serial.in_waiting));(BASE/b/(CAPTURE_STEM+'.txt')).write_bytes(buffers[b])
            if all(PROMPT in data for data in buffers.values()):break
            time.sleep(.025)
        for b,data in buffers.items():
            assert b'STR8-N 2.0b24' in data and PROMPT in data,b
            assert data.count(f'gen {GENERATION:08X} VALID'.encode())==2,(b,bytes(data))
            pending=json.loads((REPAIR_BASE/b/'upgrade/install/reset-pending.json').read_text())
            pending['physical_reset_pending']=False
            (REPAIR_BASE/b/'upgrade/install/reset-pending.json').write_text(json.dumps(pending,indent=2)+'\n')
        print('PASS physical RESET boots on '+', '.join(BOARDS)+'; A/B generation '+str(GENERATION)+' valid',flush=True)

def verify():
    campaign=json.loads((ROOT/'output/qualification/active-rtc-campaign.json').read_text())
    with serial_lease('startup-key-hardware-retest'):
        for b in BOARDS:
            root=BASE/b/RETEST_NAME;root.mkdir(exist_ok=False);checks=[];results=[]
            retained=root/'retained';(retained/'sram-prior').mkdir(parents=True)
            shutil.copyfile(BASE/b/'retained/sram-reference/array-0.bin',retained/'sram-prior/array-0.bin')
            shutil.copytree(BASE/b/'retained/devices-before',retained/'devices-before')
            with (root/'retest-serial.jsonl').open('x') as log:
                l=Link(port(b),log)
                try:
                    establish_b3(l);tail=l.dump(0x9C00,0x9FFF);names=valid_names(tail);original=max(names)[1] if names else ''
                    def active(slot):assert l.dump(0x7D30,0x7D30)==bytes((0xA0 if slot.upper()=='A' else 0xB0,))
                    def reboot(key=None,choice=None,recovery=False):
                        l.send(b'J3\r');text=l.until(b'.')
                        if key is not None:
                            l.send(key)
                            if choice is not None or recovery:
                                text+=l.until(MENU)
                                dots=text.count(b'.')
                                assert 0<dots<160,(key,dots,text)
                                if recovery:
                                    l.send(b'S');text+=l.until(b'REC> ')
                                    assert b'FIXED F RECOVERY' in text
                                    l.send(b'A\r');text+=l.until(PROMPT);active('A')
                                else:
                                    l.send(choice.encode());text+=l.until(PROMPT);active(choice)
                            else:
                                text+=l.until(PROMPT);dots=text.split(b'STR8-N')[0].count(b'.')
                                assert MENU not in text and 0<dots<160,(key,dots,text)
                                active(key.decode())
                                old=l.dump(0x3E20,0x3E22)
                                try:l.write_ram(0x3E20,b'\x01\x03\0')
                                finally:l.write_ram(0x3E20,old)
                        else:
                            text+=l.until(PROMPT);dots=text.split(b'MONITOR ')[0].count(b'.');assert dots==160,(dots,text)
                        if not recovery:
                            if original:assert ('\r\nBoard: '+original+'\r\n').encode() in text,(original,text)
                            else:assert b'Board:' not in text
                        i=len(results);(root/f'key-{i:02d}.txt').write_bytes(text)
                        results.append(dict(key_hex=key.hex() if key is not None else None,menu_choice=choice,
                                            recovery=recovery,startup_dots=dots,passed=True))
                    for key in (b'A',b'a',b'B',b'b'):reboot(key)
                    checks.append('Early A/a/B/b starts the selected validated monitor without the chooser')
                    for key,choice in ((b'\x1b','A'),(b'x','B'),(b' ','A'),(b'\r','B'),(b'S','A'),(b'\x03','B')):reboot(key,choice)
                    checks.append('ESC, other letter, space, Enter, S and Ctrl-C skip dots and retain validated A/B menu')
                    reboot(b'\x1b',recovery=True);checks.append('S at skipped-dot menu enters independent fixed F recovery; A returns')
                    reboot();checks.append('No-key startup retains 160 dots and timed default boot')
                    smoke.guards(l)
                    probes=ROOT/'BUILD/v2-board-regression';pm=json.loads((probes/'build.json').read_text())['probes']
                    assert load_image(l,probes/'abi.s19')==pm['abi']['sha256'];assert b'RAM ABI: PASS' in l.command('G 2000')
                    pointers=l.dump(0x7E00,0x7E1B)
                    assert load_image(l,probes/'irq.s19')==pm['irq']['sha256']
                    assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in l.command('G 2000')
                    assert l.dump(0x7E00,0x7E1B)==pointers
                    checks.append('RAM ABI and actual BRK/VIA1 IRQ preserve vector pointers and stack')
                    groups={g:smoke.commands(l,g) for g in ('monitor','clock','edu','sram','work','maint')}
                    (root/'command-regression.json').write_text(json.dumps(groups,indent=2)+'\n')
                    checks.append('Monitor, CLOCK, EDU, SRAM, WORK and MAINT command smoke')
                    assert l.dump(0x9C00,0x9FFF)==tail
                    hashes=[]
                    for bank in range(4):
                        prompt=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',prompt)
                        data=b''.join(l.dump(a,a+4095,prompt) for a in range(0x8000,0x10000,4096))
                        assert data==(REPAIR_BASE/b/f'upgrade/expected-b{bank}.bin').read_bytes(),(b,bank)
                        (root/f'final-b{bank}.bin').write_bytes(data)
                        import hashlib
                        hashes.append(hashlib.sha256(data).hexdigest())
                    l.command('B3');checks.append('All four flash banks exactly match the planned image; names and settings unchanged')
                finally:l.serial.close()
            power.call(power.array,['--root',str(retained),'--board',b,'--port',port(b),'--stage','final'])
            power.call(power.devices,['--root',str(retained),'--board',b,'--port',port(b),'--stage','after','--baseline-index',campaign['baseline_index']])
            checks.append('Entire 128 KiB SRAM, EEPROM, history, identity, control and trim unchanged')
            report=dict(passed=True,board=b,generation=GENERATION,version='2.0b24',checks=checks,key_cases=results,
                        original_name=original,final_flash_hashes=hashes,physical_reset_verified=True,
                        physical_power_cycle_tested=False,physical_nmi_tested=False)
            (root/'retest-report.json').write_text(json.dumps(report,indent=2)+'\n')
            print('PASS',b,'startup keys, recovery, command/IRQ regressions and complete retained data',flush=True)

if __name__=='__main__':
    import sys
    if sys.argv[1]=='capture':capture()
    elif sys.argv[1]=='verify':verify()
    else:raise ValueError(sys.argv[1])
