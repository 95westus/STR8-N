"""2512-only preserving powered soak; STOP ends after the current leased unit.

Never changes RTC/configuration, flash, EEPROM or retained SRAM. Application
RAM is borrowed, archived twice up front and restored on orderly exit.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import time
import traceback

import run_v2_beta32_soak as base
import run_beta23_soak as probes
from atomic_json import publish
from beta4_migration import Link, s19
from rtc_prompt_sync import establish_b3
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease, drift_pending
from soak_led_patterns import playlist

ROOT = base.ROOT
REFERENCE = ROOT/'output/qualification/beta35-fleet-2026-10-16/2512'
RETAINED = ROOT/'output/qualification/beta34-fleet-2026-10-16/fresh/2512'
READ_GROUPS = ['eeprom','flash-3','clock','monitor','asm','apps','batch','ram'] + [f'sram-{i}' for i in range(16)] + [f'flash-{i}' for i in range(3)]
GROUPS = []
for _index,_group in enumerate(READ_GROUPS):
    GROUPS.append(_group)
    if _index == 1 or _index % 4 == 3:
        GROUPS.append('led')

# Monitor D deliberately protects I/O. Read the LED latch/CRA through CPU RAM,
# then inspect only RAM. LDA $7FA0 / STA $500F / LDA $7FA1 / STA $5010 /
# JMP $7E67; two result bytes. All addresses are in the archived RAM window.
LED_READBACK = bytes.fromhex('AD A0 7F 8D 0F 50 AD A1 7F 8D 10 50 4C 67 7E 00 00')


def led_state(link):
    link.command('G 5000')
    return link.dump(0x500F,0x5010)


def led_show(link,out,*,seed=None,stop_requested=lambda:False):
    """Use the existing RAM-only self-restoring probe; log every visible frame.

    A probe always completes its eight frames before releasing the lease. Drift
    priority / STOP can shorten the playlist between probes, after restoration.
    """
    seed = secrets.randbits(64) if seed is None else seed
    shows = playlist(seed)
    link.write_ram(0x5000,LED_READBACK)
    before = led_state(link)
    original = before[:1]
    assert before[1]&4, 'LED hardware not present'
    proof = base.read_json(probes.PROBES/'build.json')['led']
    image = probes.PROBES/'led/led.bin'
    assert base.sha(image.read_bytes())==proof['sha256']
    publish(out/'led-plan.json',dict(seed_hex=f'{seed:016x}',shows=shows,original_led_hex=original.hex(),
                                    probe_sha256=proof['sha256']))
    assert base.load_image(link,probes.PROBES/'led/led.s19')==proof['sha256']
    completed = []
    for show in shows:
        if drift_pending() or stop_requested():break
        frames = bytes.fromhex(show['frames_hex'])
        assert len(frames)==8 and 120<=show['hold_ms']<=240
        link.write_ram(0x3200,frames)
        publish(out/'led-state.json',dict(needs_restore=True,original_led_hex=original.hex(),show=show))
        link.send(b'G 4000\r')
        try:
            for _ in frames:
                link.until(b'~',seconds=5)
                time.sleep(show['hold_ms']/1000)
                link.send(b'\r')
            link.until(base.PROMPT,seconds=5)
        except Exception:
            # Release every remaining probe frame and allow its own restore path.
            link.send(b'\r'*8)
            link.until(base.PROMPT,seconds=10)
            raise
        finally:
            after = led_state(link)
            restored = after[:1]==original and (after[1]&0x3F)==(before[1]&0x3F)
            publish(out/'led-state.json',dict(needs_restore=not restored,verified=restored,
                                             original_led_hex=original.hex(),show=show))
            assert restored, 'LED restoration failed'
        completed.append(show)
    return dict(seed_hex=f'{seed:016x}',sequences=completed,original_led_hex=original.hex(),
                original_led_restored=True,yielded_early=len(completed)<len(shows))

def port():
    return next(p.device for p in comports() if p.serial_number == SERIALS['2512'])

def ram(link):
    return b''.join(link.dump(a,min(a+4095,0x64FF)) for a in range(0x0200,0x6500,4096))

def restore(link, path, original):
    link.command('L',b'S19')
    for row in path.read_bytes().splitlines():
        link.send(row+b'\r\n');time.sleep(.04)
    reply = link.until(base.PROMPT)
    assert not any(e in reply for e in (b'Bad',b'Protected',b'Wrap',b'Error')),reply
    assert ram(link) == original, 'Application RAM restoration failed'

def clock(link,out,expected):
    text = link.command('R CLOCK',b'CLOCK> ')
    assert b'CLOCK 1.10' in text,text
    try:
        text += link.command('STATUS',b'CLOCK> ')
        raw = bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
        trim = abs(expected['trim_steps']) | (128 if expected['trim_steps']>0 else 0)
        assert raw[7:9] == bytes((expected['control_register'],trim)), 'RTC settings changed'
        assert b'Running: yes' in text and b'Backup enabled: yes' in text
        for c in ('TIME','EUI','TRIM','OFFSET','BATTERY','HELP'):
            text += link.command(c,b'CLOCK> ')
        (out/'clock.txt').write_bytes(text)
        return dict(rtc_epoch=base.rtc_epoch(raw),trim=expected['trim_steps'],control=raw[7])
    finally:link.command('Q')

def workload(link,group,out,plan,sram,iteration,expected):
    if group == 'led':
        return led_show(link,out,stop_requested=lambda:(out.parent/'STOP').exists())
    if group == 'monitor':
        for c in ('VERSION','TIME','APPS','T','M1','W','C','?'):
            text = link.command(c)
            (out/(c.replace('?','help')+'.txt')).write_bytes(text)
            if c=='VERSION':assert b'2.0b35' in text and b'Board: 2512' in text,text
        return dict(queries=8)
    if group == 'asm':
        text = link.command('ASM',b'ASM> ')
        assert b'ASM 0.5' in text,text
        for c in ('NEW','10 ORG $0200',"20 LDA #'S'",'30 JSR $7E6D','40 JMP $7E67','LIST','ASM','DUMP','S19','?'):
            text += link.command(c,b'ASM> ')
        assert b'OK 8 bytes' in text,text
        text += link.command('QUIT')
        assert link.dump(0x200,0x207)==bytes.fromhex('a9 53 20 6d 7e 4c 67 7e')
        text += link.command('G 0200')
        (out/'asm.txt').write_bytes(text)
        return dict(assembly_and_ram_execution=True,stored_to_flash=False)
    if group=='clock':return clock(link,out,expected)
    if group=='batch':
        text = base.batch(link,'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
        text += base.batch(link,'SRAM;G CLK;TIME;Q')
        assert b'CLOCK 1.10' in text,text
        error = link.command('BATCH SRAM;BOGUS;Q',b'BATCH stopped: command failed')
        error += link.until(b'SRAM> ');link.command('Q')
        (out/'batch.txt').write_bytes(text+error)
        return dict(native_handoffs=True,saved_clk=True,error_stops=True)
    return base.unit(link,group,out,plan,sram,iteration)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--cycles',type=int,default=0)
    parser.add_argument('--sram-reference',type=Path,help='Previously captured full SRAM; must match the pinned beta35 model hash')
    args=parser.parse_args()
    assert args.cycles>=0
    args.root.mkdir(parents=True,exist_ok=False)
    active_path=ROOT/'output/qualification/active-rtc-campaign.json'
    active=base.read_json(active_path)
    index=Path(active['baseline_index'])
    assert base.sha(index.read_bytes())==active['baseline_index_sha256']
    expected=next(b for b in base.read_json(index)['boards'] if b['board']=='2512')
    assert '2512' not in active.get('powered_off_boards',[])
    plan=base.read_json(REFERENCE/'plan.json')
    model=base.read_json(REFERENCE/'model.json')
    hardware=base.read_json(REFERENCE/'hardware.json')
    assert model['passed'] and hardware['passed'] and model['expected_hashes']==plan['expected_hashes']
    for i,digest in enumerate(plan['expected_hashes']):assert base.sha((REFERENCE/f'expected-b{i}.bin').read_bytes())==digest
    flash_ref=ROOT/'output/qualification/beta35-soak-flash-baseline-2026-10-16'
    flash_proof=base.read_json(flash_ref/'report.json')
    observed=(flash_ref/'b3.bin').read_bytes()
    assert flash_proof['passed'] and flash_proof['all_other_flash_bytes_match_install_plan']
    assert base.sha(observed)==flash_proof['sha256']
    prior=(REFERENCE/'expected-b3.bin').read_bytes()
    assert len(observed)==32768 and all(a==b or 0x1CE0<=i<0x1D20 for i,(a,b) in enumerate(zip(prior,observed)))
    plan=dict(plan,expected_hashes=plan['expected_hashes'][:])
    plan['expected_hashes'][3]=flash_proof['sha256']
    for image,digest in ((base.CLIENT,base.CLIENT_HASH),(base.EEPROM,base.EEPROM_HASH)):
        cells,_=base.read_application_s19(image)
        assert base.sha(bytes(cells[a] for a in sorted(cells)))==digest
    ledmeta=base.read_json(probes.PROBES/'build.json')['led']
    assert base.sha((probes.PROBES/'led/led.bin').read_bytes())==ledmeta['sha256']
    # Legacy EEPROM workload uses this unchanged retained image only.
    base.REFERENCE=args.root/'legacy-reference'
    (base.REFERENCE/'retained/devices-after').mkdir(parents=True)
    eeprom_ref=ROOT/'output/qualification/beta35-soak-eeprom-baseline-2026-10-16'
    eeprom_proof=base.read_json(eeprom_ref/'report.json')
    assert eeprom_proof['passed'] and eeprom_proof['protected_factory_status_unchanged']
    assert base.sha((eeprom_ref/'eeprom.bin').read_bytes())==eeprom_proof['sha256']
    (base.REFERENCE/'retained/devices-after/eeprom-0.bin').write_bytes((eeprom_ref/'eeprom.bin').read_bytes())
    state=dict(board='2512',usb_serial=SERIALS['2512'],pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        passed_units=0,completed_cycles=0,groups=GROUPS,baseline_index=str(index),baseline_sha256=base.sha(index.read_bytes()),
        flash_reference_hashes=plan['expected_hashes'],
        led_policy='Two varied named eight-frame sequences plus random sparkle; seven interludes per full cycle; drift priority between sequences',
        runner_sha256=base.sha(Path(__file__).read_bytes()),
        led_patterns_sha256=base.sha((ROOT/'tools/soak_led_patterns.py').read_bytes()),
        clock_set=False,settings_changed=False,flash_sram_eeprom_writes=False,
        excluded=['time/settings changes','ACK/CLEAR','flash writes/erase','retained storage writes/format',
                  'boot/reset','unqualified ACIA/crypto hardware paths'],application_ram_borrowed=True)
    (args.root/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    (args.root/'led-patterns-source.py').write_bytes((ROOT/'tools/soak_led_patterns.py').read_bytes())
    publish(args.root/'config.json',state)
    def status(phase,**kw):
        state.update(state=phase,updated=time.time(),**kw);publish(args.root/'status.json',state)
    original=None
    assert ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        status('initializing')
        # Durable CPU RAM archive before any application staging.
        with serial_lease('beta35-soak-2512'):
            with (args.root/'startup.jsonl').open('x') as log:
                link=Link(port(),log)
                try:
                    establish_b3(link);base.guards(link)
                    captured=ram(link)
                    assert captured==ram(link),'Unstable CPU application RAM'
                    (args.root/'application-ram-original.bin').write_bytes(captured)
                    (args.root/'restore-application-ram.s19').write_bytes(s19(dict(enumerate(captured,0x200)),0x200))
                    publish(args.root/'restore-needed.json',dict(needed=True,first=0x200,last=0x64FF,sha256=base.sha(captured)))
                    original=captured
                finally:link.serial.close()
        # Capture full retained SRAM via read-only requests, then match the
        # beta35 installation model before accepting it as comparison data.
        arrays=[]
        if args.sram_reference:
            captured_sram=args.sram_reference.read_bytes()
            assert len(captured_sram)==131072 and base.sha(captured_sram)==model['expected_sram_sha256']
            arrays=[captured_sram]
        for block in (() if args.sram_reference else range(16)):
            status('initializing-sram',group=f'sram-{block}')
            with serial_lease('beta35-soak-2512'):
                with (args.root/'startup.jsonl').open('a') as log:
                    link=Link(port(),log)
                    try:
                        establish_b3(link);base.guards(link)
                        assert base.load_image(link,base.CLIENT)==base.CLIENT_HASH
                        link.write_ram(0x3E20,b'\x01\x03\0')
                        link.write_ram(0x3E00,base.memory_request(1,block*8192));link.command('G 2003')
                        reply=link.dump(0x3E10,0x3E38)
                        assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
                        arrays.append(link.dump(0x4000,0x5FFF))
                    finally:link.serial.close()
        sram=b''.join(arrays);(args.root/'sram-original.bin').write_bytes(sram)
        assert base.sha(sram)==model['expected_sram_sha256'],'Retained SRAM differs from beta35 model'
        while not args.cycles or state['completed_cycles']<args.cycles:
            for group in GROUPS:
                if (args.root/'STOP').exists():status('stopped-by-request');return
                assert base.sha(index.read_bytes())==state['baseline_sha256']
                assert base.read_json(active_path)['baseline_index_sha256']==active['baseline_index_sha256']
                while True:
                    if (args.root/'STOP').exists():status('stopped-by-request');return
                    if drift_pending():status('yielding-to-drift',group=group);time.sleep(2);continue
                    try:
                        with serial_lease('beta35-soak-2512',timeout=2):
                            out=args.root/f"{state['passed_units']:06d}-{group}"
                            with (args.root/'serial.jsonl').open('a') as log:
                                link=Link(port(),log)
                                try:
                                    out.mkdir();status('running',group=group)
                                    establish_b3(link);base.guards(link)
                                    result=workload(link,group,out,plan,sram,state['completed_cycles'],expected)
                                    base.guards(link)
                                    publish(out/'report.json',dict(passed=True,result=result,finished=time.time()))
                                finally:link.serial.close()
                        break
                    except TimeoutError as e:
                        if str(e)!='Serial lease unavailable; no board port opened':raise
                        time.sleep(2)
                state['passed_units']+=1;status('running',group=group)
                print('PASS',state['passed_units'],group,flush=True)
                time.sleep(.2)
            state['completed_cycles']+=1;status('running',group=None)
            for _ in range(15):
                if (args.root/'STOP').exists():break
                time.sleep(2)
        status('completed',group=None)
    except Exception:
        status('stopped-on-failure',error=traceback.format_exc());raise
    finally:
        try:
            if original is not None:
                with serial_lease('beta35-soak-2512'):
                    with (args.root/'restore.jsonl').open('a') as log:
                        link=Link(port(),log)
                        try:establish_b3(link);restore(link,args.root/'restore-application-ram.s19',original)
                        finally:link.serial.close()
                publish(args.root/'restore-needed.json',dict(needed=False,verified=True,sha256=base.sha(original)))
                state['application_ram_restored']=True;publish(args.root/'status.json',state)
        finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

if __name__=='__main__':main()
