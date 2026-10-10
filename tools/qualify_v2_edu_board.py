"""Post-RESET EDU mode, WORK UI, RAM/ABI/IRQ and preservation checks."""
import argparse,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from serial.tools.list_ports import comports
from beta4_migration import Link,s19,metadata,config_sum,journal
from install_v2_rtc_upgrade import SERIALS
from qualify_v2_spi_install import load_image,write
from qualify_v2_spi_storage import memory_request
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'BUILD/v2-spi-resident'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',required=True,choices=tuple(SERIALS));p.add_argument('--port',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    assert next(x for x in comports() if x.device.upper()==a.port.upper()).serial_number==SERIALS[a.board]
    plan=json.loads((a.root/'upgrade/plan.json').read_text());candidate=json.loads((BUILD/'candidate-check.json').read_text());assert candidate['passed'] and candidate['version']==plan['version']
    out=a.root/('edu-check-resume' if a.resume else 'edu-check');out.mkdir(exist_ok=False);checks=[];expected=[bytearray((a.root/f'upgrade/expected-b{b}.bin').read_bytes()) for b in range(4)]
    report=dict(board=a.board,port=a.port,passed=False,clock_set=False,trim_changed=False,checks=checks)
    with (out/'serial.jsonl').open('x') as log:
        link=Link(a.port,log)
        try:
            deadline=time.monotonic()+.3
            while time.monotonic()<deadline:link.read(max(1,link.serial.in_waiting))
            first=link.command('',b'> ');(out/'physical-reset.txt').write_bytes(first)
            if any(t in first for t in (b'CLOCK>',b'BM>',b'SRAM>',b'WORK>',b'EDU>')):link.command('Q')
            link.command('B3');off=a.board=='2512'
            def cmd(text,prompt=b'\r\nB3> ',label=None):
                data=link.command(text,prompt)
                if label:(out/(label+'.txt')).write_bytes(data)
                return data
            def state(is_off):
                wanted=b'SV\x01'+(b'\0\0\0\xff\x66' if is_off else b'\x0f\0\x65\xff\x64')
                assert link.dump(0x7D04,0x7D0B)==wanted
                assert link.dump(0x7D27,0x7D27)==bytes((2 if is_off else 1,))
            def reset(slot=b'\r',label='reset'):
                write(link,0x2300,bytes.fromhex('4C 64 7E'));data=cmd('G 2300',b'Enter default [3s]: ');link.send(slot);data+=link.until(b'\r\nB3> ')
                (out/(label+'.txt')).write_bytes(data);assert b'STR8-N 2.0b15' in data
            def banks(label,wanted):
                for b in range(4):
                    prompt=f'\r\nB{b}> '.encode();link.command(f'B{b}',prompt)
                    image=b''.join(link.dump(addr,addr+4095,prompt) for addr in range(0x8000,0x10000,4096));assert image==wanted[b],f'{label} B{b}'
                    (out/f'{label}-b{b}.bin').write_bytes(image)
                link.command('B3')
            if not a.resume:
                state(off);banks('installed',expected);checks.append('Physical restart, correct descriptor and byte-exact four-bank installation')
                load_image(link,BUILD/'edu/edu.s19');em=json.loads((BUILD/'edu/build.json').read_text())
                assert b'Done' in cmd(f'S 2 C600 2000 {em["end"]-1:04X} EDU',label='save-edu')
                expected[2]=bytearray((a.root/'upgrade/expected-provisioned-b2.bin').read_bytes());checks.append('Fresh committed EDU saved record')
                for slot in (b'A',b'B',b'A'):reset(slot,'slot-'+slot.decode());state(off)
                checks.append('Both monitor slots retain configured mode across cold software RESET')
                probes=ROOT/'BUILD/v2-board-regression'
                load_image(link,probes/'abi.s19');assert b'RAM ABI: PASS' in cmd('G 2000',label='abi')
                handlers=link.dump(0x7E00,0x7E1B);load_image(link,probes/'irq.s19')
                assert b'V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS' in cmd('G 2000',label='brk-irq')
                assert link.dump(0x7E00,0x7E1B)==handlers;state(off);checks.append('Actual RAM ABI and BRK/VIA1 timer IRQ restore vectors, registers and stack')
            # Two confirmed configuration changes; hardware absence never selects mode.
            config=bytearray.fromhex(plan['config']);seq=int.from_bytes(expected[3][0x4004:0x4008],'little')
            completed=0
            if a.resume:
                old=a.root/'edu-check';old_report=json.loads((old/'report.json').read_text());assert not old_report['passed'] and old_report['error']=='AssertionError()'
                checks.extend(old_report['checks']);completed=2 if off else 1;expected[2]=bytearray((a.root/'upgrade/expected-provisioned-b2.bin').read_bytes())
                for turn in range(1,completed+1):
                    config[13]=0xA5 if (not off if turn==1 else off) else 0;config[14:]=config_sum(config)
                    start=0x4000+turn*128;expected[3][start:start+128]=metadata(config,plan['counts_after'],seq+turn)
                state(True);banks('resume-preimage',expected)
                program=bytes.fromhex('A9 52 20 6D 7E A9 41 20 6D 7E A9 4D 20 6D 7E 20 7F 7E 4C 67 7E');pattern=bytes((i^0xA6)&255 for i in range(512))
                area=program+pattern[len(program):];assert link.dump(0x6500,0x66FF)==area
                load_image(link,BUILD/'example/example.s19');cmd('G 2000',label='spi-off')
                assert link.dump(0x2418,0x2418)==b'\x80' and link.dump(0x6500,0x66FF)==area
                checks.append('OFF SPI example returns unavailable status80 without touching any reclaimed byte')
            for turn,target_off in list(enumerate((not off,off),1))[completed:]:
                cmd('R EDU',b'EDU> ');status=cmd('?',b'EDU> ',f'edu-status-{turn}')
                assert (b'EDU active: OFF' if (off if turn==1 else not off) else b'EDU active: ON') in status
                cmd('OFF' if target_off else 'ON',b'Apply after RESET? [y/N]: ')
                assert b'Saved; RESET required.' in cmd('Y',b'EDU> ')
                cmd('Q');state(off if turn==1 else not off)
                config[13]=0xA5 if target_off else 0;config[14:]=config_sum(config)
                row=metadata(config,plan['counts_after'],seq+turn);start=0x4000+128*turn;expected[3][start:start+128]=row
                reset(label=f'mode-reset-{turn}');state(target_off)
                if target_off:
                    prior=link.dump(0x6500,0x66FF);pattern=bytes((i^0xA6)&255 for i in range(512));write(link,0x6500,pattern)
                    program=bytes.fromhex('A9 52 20 6D 7E A9 41 20 6D 7E A9 4D 20 6D 7E 20 7F 7E 4C 67 7E')
                    records=s19(dict(enumerate(program,0x6500)),0x6500)
                    cmd('L',b'S19')
                    for line in records.splitlines():link.send(line+b'\r\n');time.sleep(.04)
                    link.until(b'\r\nB3> ');assert link.dump(0x6500,0x6500+len(program)-1)==program
                    expected_ram=program+pattern[len(program):]
                    assert b'\r\nRAM\r\n' in cmd('G 6500',label='free-ram-run')
                    assert link.dump(0x6500,0x66FF)==expected_ram
                    assert b'RTCC: unavailable' in cmd('TIME',label='time-off')
                    cmd('R CLOCK',b'CLOCK> ');assert b'Services unavailable' in cmd('STATUS',b'CLOCK> ',label='clock-off');cmd('Q')
                    cmd('R SRAM',b'SRAM> ');assert b'SRAM: 80' in cmd('T',b'SRAM> ',label='sram-off');cmd('Q')
                    cmd('R WORK',b'WORK> ');assert b'SPI SRAM unavailable.' in cmd('?',b'WORK> ',label='work-off');cmd('Q')
                    load_image(link,BUILD/'example/example.s19');cmd('G 2000',label='spi-off');assert link.dump(0x2418,0x2418)==b'\x80'
                    assert link.dump(0x6500,0x66FF)==expected_ram;write(link,0x6500,prior)
            checks.append('Both mode transitions stay pending until RESET; OFF S19/edit/run and all optional clients preserve reclaimed RAM')
            state(off)
            if not off:
                protected=link.dump(0x6500,0x66FF)
                for text in ('M 6500 12','G 6500'):
                    assert b'Protected' in cmd(text) and link.dump(0x6500,0x66FF)==protected
                cmd('R CLOCK',b'CLOCK> ');status=cmd('STATUS',b'CLOCK> ',label='clock-final');history=cmd('HISTORY',b'CLOCK> ',label='history-final');eui=cmd('EUI',b'CLOCK> ',label='eui-final');cmd('Q')
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',status)[1].decode())
                assert raw[7:9]==b'\x80\0' and b'Running: yes' in status and b'Backup enabled: yes' in status
                assert history==(a.root/'prior/history-prior.txt').read_bytes() and b', changed' not in eui and b', unbound' not in eui
                before=datetime.strptime(re.search(rb'Calendar \(UTC convention\): ([0-9 :\-]+)',(a.root/'prior/rtc-prior.txt').read_bytes())[1].decode(),'%Y-%m-%d %H:%M:%S')
                after=datetime.strptime(re.search(rb'Calendar \(UTC convention\): ([0-9 :\-]+)',status)[1].decode(),'%Y-%m-%d %H:%M:%S');assert after>before
                checks.append('ON RAM protection, retained UTC/trim/backup/history/EUI')
                # Temporary WORK administration is wholly below SRAM 2000.
                original=(a.root/'sram-prior/array-0.bin').read_bytes()[:8192];mutated=False
                def bulk(op,privileged=False):
                    write(link,0x3E20,bytes((1,3,0xA5 if privileged else 0)));write(link,0x3E00,memory_request(op));cmd('G 2003');assert link.dump(0x3E18,0x3E19)==b'\0\x40'
                try:
                    assert b'WORK 1.1' in cmd('R WORK',b'WORK> ',label='work-start')
                    cmd('F',b'Type FORMAT SRAM: ');mutated=True;assert b'Formatted.' in cmd('FORMAT SRAM',b'WORK> ')
                    assert b'Programs: 64 KiB; workspace: 65504 bytes' in cmd('?',b'WORK> ')
                    cmd('P 32',b'Apply? [y/N]: ');assert b'Resized.' in cmd('Y',b'WORK> ',label='work-resize-32')
                    assert b'Programs: 32 KiB; workspace: 98272 bytes' in cmd('?',b'WORK> ',label='work-capacity-32')
                    cmd('P 64',b'Apply? [y/N]: ');assert b'Resized.' in cmd('Y',b'WORK> ')
                    assert b'No change.' in cmd('P 64',b'WORK> ')
                    cmd('Q')
                finally:
                    if mutated:
                        prompt=link.command('',b'> ')
                        if b'WORK>' in prompt:cmd('Q')
                        load_image(link,BUILD/'hardware-client/client.s19')
                        path=out/'restore-sram-block.s19';path.write_bytes(s19(dict(enumerate(original,0x4000)),0x4000));load_image(link,path)
                        bulk(2,True);bulk(1);assert link.dump(0x4000,0x5FFF)==original
                        reset(label='work-restored-reset');state(False)
                load_image(link,ROOT/'BUILD/v2-eeprom-inventory/probe.s19');cmd('G 2000');ee=link.dump(0x2400,0x2494);(out/'eeprom-final.bin').write_bytes(ee)
                assert ee[:128]==(a.root/'eeprom-prior/array.bin').read_bytes() and ee[0x80:0x89]==(a.root/'eeprom-prior/status-factory.bin').read_bytes()
                checks.append('WORK1.1 actual format/resize/no-change, restored original 8KiB; EEPROM/factory intact')
            cmd('R EDU',b'EDU> ');status=cmd('?',b'EDU> ',label='edu-final');cmd('Q')
            assert (b'EDU active: OFF' if off else b'EDU active: ON') in status
            banks('final',expected);(out/'table.txt').write_bytes(cmd('T 2'))
            if a.board=='2609':assert b'\r\nDEMO\r\n' in cmd('R 2 DEMO2',label='demo2-preserved')
            state(off);report.update(passed=True,mode=plan['edu_mode'],user_ram_top='66FF' if off else '64FF',final_hashes=[sha(b) for b in expected],both_slots_verified=True,eeprom_preserved=not off)
            print('PASS',a.board,'beta15 EDU',plan['edu_mode'],'RAM top',report['user_ram_top'],len(checks),'hardware checks',flush=True)
        except Exception as e:report['error']=repr(e);raise
        finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');link.serial.close()
if __name__=='__main__':main()
