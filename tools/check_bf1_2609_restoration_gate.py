"""Verify an owner-reset original-payload restoration; preserve all retained bytes."""
import argparse,json,hashlib,traceback,re
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish
import bf1_2609_readonly as live
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--transaction',type=Path,required=True);ap.add_argument('--reset-confirmation',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    tx=read(a.transaction/'report.json');confirmation=read(a.reset_confirmation)
    assert tx['passed'] and tx['transaction_device_verified'] and tx['physical_reset_pending']
    assert tx['board']=='2609' and tx['case'] in ('restore-A40-retain-Bbf1','restore-original-B35-complete')
    assert confirmation['board']=='2609' and confirmation['case']==tx['case'] and confirmation['user_confirmed_physical_reset']
    backup=Path(tx['backup']);assert sha(backup/'report.json')==tx['backup_report_sha256']
    saved=read(backup/'report.json');assert saved['passed'] and saved['application_ram_restored']
    for name,info in saved['files'].items():assert sha(backup/name)==info['sha256']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205']
    assert sha(Path(active['baseline_index']))==active['baseline_index_sha256']
    expected=next(b for b in read(Path(active['baseline_index']))['boards'] if b['board']=='2609')
    marker=Q/'device-operations/2609.json';guard=read(marker)
    assert guard['state']=='reset-required' and guard['case']==tx['case']
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2609']);assert port==tx['port']
    a.out.mkdir(parents=True,exist_ok=False)
    result=dict(board='2609',case=tx['case'],passed=False,started_utc=datetime.now(timezone.utc).isoformat(),transaction_report_sha256=sha(a.transaction/'report.json'),reset_confirmation_sha256=sha(a.reset_confirmation),clock_set=False,trim_changed=False,persistent_device_writes=False,checks=[])
    save=lambda:publish(a.out/'report.json',result)
    def passed(name):result['checks'].append(dict(name=name,passed=True));save();print('PASS',name,flush=True)
    def flash(link,stem):
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt)
            data=b''.join(link.dump(n,n+4095,prompt) for n in range(0x8000,0x10000,4096));(a.out/f'{stem}-b{bank}.bin').write_bytes(data)
            assert hashlib.sha256(data).hexdigest()==tx['expected_hashes'][bank],f'Flash B{bank} differs; retain evidence'
        link.command('B3')
    save();publish(marker,dict(board='2609',state='checking',case=tx['case'],run=str(a.out.resolve()),block_snapshot=True))
    restore_allowed=False
    with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);version=link.command('VERSION');(a.out/'version.txt').write_bytes(version)
            assert b'Board: 2609' in version and b'65C816' in version
            restore_allowed=True
            wanted=b'2.0bf1' if tx['case']=='restore-A40-retain-Bbf1' else b'2.0b35'
            assert wanted in version and b'Running: MONITOR B' in version
            assert link.dump(0x7D30,0x7D30)==b'\xb0';passed('expected B monitor identity after owner RESET')
            flash(link,'before-checks');passed('all four banks equal modeled restoration including retained fallback')
            result['cpu_mode_before']=live.cpu_mode(link,a.out,'cpu-mode-before');passed('65C816 E=1 runtime and zero banks/direct page')
            assert live.base.load_image(link,live.base.EEPROM)==live.base.EEPROM_HASH
            link.command('G 2000');data=link.dump(0x2400,0x2494)
            assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            (a.out/'eeprom-after.bin').write_bytes(data[:137]);assert data[:137]==(backup/'eeprom.bin').read_bytes();passed('EEPROM identity and power-event bytes preserved')
            assert live.base.load_image(link,live.base.CLIENT)==live.base.CLIENT_HASH
            blocks=[];sram=(backup/'sram.bin').read_bytes()
            for block in range(16):
                link.write_ram(0x3E20,b'\x01\x03\0');link.write_ram(0x3E00,live.base.memory_request(1,block*8192));link.command('G 2003')
                reply=link.dump(0x3E10,0x3E38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
                data=link.dump(0x4000,0x5fff);assert data==sram[block*8192:(block+1)*8192];blocks.append(data)
            (a.out/'sram-after.bin').write_bytes(b''.join(blocks));passed('all 131072 retained SRAM bytes preserved')
            text=link.command('R CLOCK',b'CLOCK> ')
            try:
                assert (b'CLOCK 1.11' if wanted==b'2.0bf1' else b'CLOCK 1.10') in text
                text+=link.command('STATUS',b'CLOCK> ')
                raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
                trim=abs(expected['trim_steps'])|(128 if expected['trim_steps']>0 else 0)
                assert raw[7:9]==bytes([expected['control_register'],trim])
                (a.out/'clock.txt').write_bytes(text)
            finally:link.command('Q')
            passed('expected CLOCK version and unchanged RTC control/trim')
            result['cpu_mode_after']=live.cpu_mode(link,a.out,'cpu-mode-after');flash(link,'after-checks');passed('final E=1 and exact flash preservation')
            result.update(full_flash_verified=True,initial_checks_passed=True)
        except BaseException:
            result['failure']=traceback.format_exc();save();publish(marker,dict(board='2609',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:
            try:
                if restore_allowed:
                    establish_b3(link);original=(backup/'application-ram-original.bin').read_bytes()
                    publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest()))
                    live.old.restore(link,backup/'restore-application-ram.s19',original)
                    clear=dict(needed=False,verified=True,sha256=hashlib.sha256(original).hexdigest())
                    publish(a.out/'restore-needed.json',clear);publish(a.transaction/'restore-needed.json',clear);result['application_ram_restored']=True
            finally:link.serial.close();save()
    result.update(passed=True,ports_released=True,finished_utc=datetime.now(timezone.utc).isoformat());save()
    publish(a.transaction/'activation-completed.json',dict(physical_reset_pending=False,user_physical_reset_confirmed=True,hardware_report_sha256=sha(a.out/'report.json'),application_ram_restored=True))
    publish(marker,dict(board='2609',state='idle',case=tx['case'],hardware_report=str((a.out/'report.json').resolve()),block_snapshot=False))
    print('PASS restoration boot, retained storage, emulation runtime and RAM restoration',flush=True)
if __name__=='__main__':main()
