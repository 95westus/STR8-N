"""Post-physical-reset bf1 checks; restore borrowed application RAM on exit."""
import argparse,hashlib,json,traceback,os,time
from pathlib import Path
from datetime import datetime,timezone
from serial.tools.list_ports import comports
from beta4_migration import Link
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from serial_test_coordination import serial_lease
from atomic_json import publish
import bf1_2604_readonly as live
old=live.old;base=live.base;ROOT=old.ROOT;sha=base.sha;read=base.read_json
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--install',type=Path,required=True);ap.add_argument('--reset-confirmation',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    install=read(a.install/'report.json');confirmation=read(a.reset_confirmation)
    assert install['passed'] and install['transaction_device_verified'] and install['physical_reset_pending'] and install['board']=='2604'
    assert confirmation['board']=='2604' and confirmation['phase']==install['phase'] and confirmation['user_confirmed_physical_reset']
    phase=install['phase'];page=0xb0 if phase=='B' else 0xa0;backup=ROOT/'output/qualification/2604-return-backup-2026-10-17-1724Z';prior=read(backup/'report.json');assert prior['passed'] and prior['application_ram_restored']
    active=read(ROOT/'output/qualification/active-rtc-campaign.json');assert set(active['powered_off_boards'])=={'2205','2609'} and sha(Path(active['baseline_index']).read_bytes())==active['baseline_index_sha256'];expected=next(b for b in read(Path(active['baseline_index']))['boards'] if b['board']=='2604')
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2604']);assert port==install['port']
    a.out.mkdir(parents=True,exist_ok=False);marker=ROOT/'output/qualification/device-operations/2604.json';assert read(marker)['state']=='reset-required'
    report=dict(board='2604',phase=phase,passed=False,port=port,active_page=page,expected_hashes=install['expected_hashes'],clock_set=False,trim_changed=False,persistent_device_writes=False,started_utc=datetime.now(timezone.utc).isoformat(),reset_confirmation_sha256=sha(a.reset_confirmation.read_bytes()),install_report_sha256=sha((a.install/'report.json').read_bytes()),checks=[])
    def save():publish(a.out/'report.json',report)
    def passed(name,**kw):report['checks'].append(dict(name=name,passed=True,**kw));save();print('PASS',phase,name,flush=True)
    def flash(link,stem):
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'{stem}-b{bank}.bin').write_bytes(data)
            assert sha(data)==install['expected_hashes'][bank],f'{stem} B{bank} differs from exact expected image; preserve evidence'
        link.command('B3')
    def eeprom(link,name):
        assert base.load_image(link,base.EEPROM)==base.EEPROM_HASH;link.command('G 2000');data=link.dump(0x2400,0x2494)
        assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
        (a.out/name).write_bytes(data[:137]);assert data[:137]==(backup/'eeprom.bin').read_bytes(),'EEPROM/power-event evidence changed';return data[:137]
    save()
    with serial_lease('bf1-initial-checks-2604',timeout=600,priority=True):
      publish(marker,dict(board='2604',state='checking',phase=phase,run=str(a.out.resolve()),block_snapshot=True))
      with (a.out/'serial.jsonl').open('x') as log:
        link=Link(port,log)
        try:
            establish_b3(link);text=link.command('VERSION');(a.out/'version.txt').write_bytes(text)
            assert b'2.0bf1' in text and b'Board: 2604' in text and (b'Running: MONITOR B' if phase=='B' else b'Running: MONITOR A') in text,text
            live.guards(link,page);passed('bf1 identity, active monitor, BATCH and managed-SRAM ABI')
            flash(link,'before-checks');passed('all four flash banks exactly match modeled transaction')
            report['clock']=live.clock(link,a.out,expected);passed('CLOCK 1.11 read-only status and unchanged control/trim')
            plan=dict(expected_hashes=install['expected_hashes']);sram=(backup/'sram.bin').read_bytes()
            for group in ('monitor','apps','asm'):
                out=a.out/group;out.mkdir();result=live.workload(link,group,out,plan,sram,0,expected);passed(group,**result)
            out=a.out/'batch';out.mkdir();passed('native/CLOCK BATCH success, error, unsupported and native Escape',**live.batch(link,out,cancel=True))
            out=a.out/'led';out.mkdir()
            from serial_test_coordination import ROOT as coordination
            def foreign_drift():
                for mark in coordination.glob('drift-*.json'):
                    value=read(mark)
                    if value.get('pid')!=os.getpid() and not value.get('released') and time.time()-value['created']<900:return True
                return False
            old.drift_pending=foreign_drift
            led=old.led_show(link,out);passed('LED readback and latch restoration',**led)
            eeprom(link,'eeprom-after-0.bin');eeprom(link,'eeprom-after-1.bin');passed('EEPROM user bytes, power records, factory status and EUI preserved')
            assert base.load_image(link,base.CLIENT)==base.CLIENT_HASH;arrays=[]
            for block in range(16):
                link.write_ram(0x3E20,b'\x01\x03\0');link.write_ram(0x3E00,base.memory_request(1,block*8192));link.command('G 2003');reply=link.dump(0x3E10,0x3E38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
                data=link.dump(0x4000,0x5fff);assert data==sram[block*8192:(block+1)*8192],f'Retained SRAM block {block} differs';arrays.append(data)
            (a.out/'sram-after.bin').write_bytes(b''.join(arrays));passed('full 131072-byte retained SRAM preserved')
            live.clock(link,a.out,expected);flash(link,'after-checks');live.guards(link,page);passed('final full flash and RTC settings preservation')
            report.update(full_flash_verified=True,initial_checks_passed=True)
        except BaseException:
            report['failure']=traceback.format_exc();save();publish(marker,dict(board='2604',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
        finally:
            try:
                establish_b3(link);original=(backup/'application-ram-original.bin').read_bytes();publish(a.out/'restore-needed.json',dict(needed=True,sha256=sha(original)))
                old.restore(link,backup/'restore-application-ram.s19',original);report['application_ram_restored']=True;publish(a.out/'restore-needed.json',dict(needed=False,verified=True,sha256=sha(original)))
            finally:link.serial.close();save()
      report.update(passed=True,ports_released=True,finished_utc=datetime.now(timezone.utc).isoformat());save();publish(marker,dict(board='2604',state='B-initial-checks-passed' if phase=='B' else 'idle',phase=phase,hardware_report=str((a.out/'report.json').resolve()),block_snapshot=phase=='B'))
    print('PASS',phase,'hardware checks and RAM restoration',flush=True)
if __name__=='__main__':main()
