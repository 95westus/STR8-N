"""2512 post-owner-RESET migration checks; read persistent devices and restore borrowed RAM."""
import argparse,json,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
from beta4_migration import Link
from serial.tools.list_ports import comports
from rtc_boards import SERIALS
from rtc_prompt_sync import establish_b3
from atomic_json import publish
import bf1_2604_readonly as live
old=live.old;base=live.base;ROOT=base.ROOT;Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--install',type=Path,required=True);ap.add_argument('--reset-confirmation',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    install=read(a.install/'report.json');confirmation=read(a.reset_confirmation);assert install['passed'] and install['transaction_device_verified'] and install['physical_reset_pending'] and install['board']=='2512'
    assert confirmation['board']=='2512' and confirmation['user_confirmed_physical_reset'] and confirmation['install_report_sha256']==sha(a.install/'report.json')
    backup=Path(install['fresh_backup']);assert read(backup/'report.json')['passed'] and not read(backup/'restore-needed.json')['needed'];original=(backup/'application-ram-original.bin').read_bytes();sram=(backup/'sram.bin').read_bytes()
    model=Q/'bf1-monitor-reentry-2026-10-17-r1/report.json';m=read(model);assert m['passed'] and m['persistent_devices_unchanged']
    final=install.get('phase')=='final-bf1'
    beta4=install.get('phase')=='v2-0b4-convert' or final
    if beta4:
        # The separate A/B prompt-entry proof runs the identical ROM/providers.
        # Only conservative wear journal contents differ for the second route.
        proof=Q/'bf1-2512-legacy-offline-2026-10-17-r6/wdcmonv2-convert'
        current=Path(install['plan']).parent
        assert m['bank_hashes']==[sha(proof/f'expected-b{n}.bin') for n in range(4)]
        assert m['bank_hashes'][:3]==install['expected_hashes'][:3]
        before=(proof/'expected-b3.bin').read_bytes();after=(current/'expected-b3.bin').read_bytes()
        assert before[:0x4000]==after[:0x4000] and before[0x6000:]==after[0x6000:]
    else:assert m['bank_hashes']==install['expected_hashes']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256'];expected=next(b for b in read(Path(active['baseline_index']))['boards'] if b['board']=='2512')
    marker=Q/'device-operations/2512.json';operation=read(marker);assert operation['block_snapshot']
    assert (operation['state']=='legacy-reset-required' and operation['phase']==install['phase']) if beta4 else operation['state']=='reset-required-bf1-from-wdc'
    ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1;assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board='2512',route_id=install.get('route_id','2512-owner-final-bf1' if final else '2512-v2.0b4-to-bf1' if beta4 else None),target_version='2.0bf1',passed=False,expected_hashes=install['expected_hashes'],install_report_sha256=sha(a.install/'report.json'),source_sha256=sha(Path(__file__)),reset_confirmation_sha256=sha(a.reset_confirmation),monitor_reentry_model_sha256=sha(model),monitor_reentry_equivalence='Identical B0/B1/B2 and B3 outside wear journal' if beta4 else 'Identical four-bank source',started_utc=datetime.now(timezone.utc).isoformat(),clock_set=False,trim_changed=False,persistent_device_writes=False,checks=[])
    def save():publish(a.out/'report.json',report)
    def passed(name,**values):report['checks'].append(dict(name=name,passed=True,**values));save();print('PASS',name,flush=True)
    def flash(link,stem):
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'{stem}-b{bank}.bin').write_bytes(data)
            assert hashlib.sha256(data).hexdigest()==install['expected_hashes'][bank],f'{stem} B{bank} mismatch; preserve evidence'
        link.command('B3')
    save();publish(marker,dict(board='2512',state='checking-bf1-migration',run=str(a.out.resolve()),block_snapshot=True))
    publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest(),source=str(backup/'application-ram-original.bin')))
    with (a.out/'serial.jsonl').open('x') as log:
      link=Link(ports[0],log)
      try:
        establish_b3(link);text=link.command('VERSION');(a.out/'physical-boot-version.txt').write_bytes(text);assert b'2.0bf1' in text and b'Board: 2512' in text and b'Running: MONITOR B' in text
        live.guards(link,0xb0);passed('Physical boot into bf1 MON B, board 2512 and protected SRAM ABI')
        flash(link,'before');passed('Four flash banks exactly match qualified conversion')
        for page in (0xa0,0xb0):
            out=a.out/f'mon-{page:02x}';out.mkdir();entry=f'G {page:02X}87';link.command(entry);text=link.command('VERSION');(out/'version.txt').write_bytes(text);assert b'2.0bf1' in text and b'Board: 2512' in text and (b'Running: MONITOR A' if page==0xa0 else b'Running: MONITOR B') in text
            live.guards(link,page);live.clock(link,out,expected);live.batch(link,out,cancel=False)
            asm=out/'asm';asm.mkdir();old.workload(link,'asm',asm,dict(expected_hashes=install['expected_hashes']),sram,0,expected);passed(f'MON {page:02X}: identity, CLOCK, native BATCH success/errors and ASM execution')
        for n in range(2):
            assert base.load_image(link,base.EEPROM)==base.EEPROM_HASH;link.command('G 2000');data=link.dump(0x2400,0x2494);assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0
            (a.out/f'eeprom-{n}.bin').write_bytes(data[:137]);assert data[:137]==(backup/'eeprom.bin').read_bytes(),'EEPROM or power evidence changed'
        passed('Double EEPROM read matches original user bytes, PF records and EUI')
        assert base.load_image(link,base.CLIENT)==base.CLIENT_HASH;blocks=[]
        for block in range(16):
            link.write_ram(0x3E20,b'\x01\x03\0');link.write_ram(0x3E00,base.memory_request(1,block*8192));link.command('G 2003');reply=link.dump(0x3E10,0x3E38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24]
            data=link.dump(0x4000,0x5fff);assert data==sram[block*8192:(block+1)*8192],f'Retained SRAM block {block} differs';blocks.append(data);print('PASS retained SRAM block',block,flush=True)
        (a.out/'sram-after.bin').write_bytes(b''.join(blocks));passed('All 131072 retained SRAM bytes preserved')
        live.clock(link,a.out,expected);flash(link,'after');live.guards(link,0xb0);passed('Final four-bank flash and RTC control/trim preservation');report.update(full_flash_verified=True,initial_checks_passed=True,retained_storage_preserved=True,clocks_trims_unchanged=True)
      except BaseException:report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',run=str(a.out.resolve()),block_snapshot=True));raise
      finally:
        try:
            establish_b3(link);old.restore(link,backup/'restore-application-ram.s19',original);report['application_ram_restored']=True;publish(a.out/'restore-needed.json',dict(needed=False,verified=True,sha256=hashlib.sha256(original).hexdigest()));publish(a.install/'restore-needed.json',dict(needed=False,verified=True,sha256=hashlib.sha256(original).hexdigest(),receipt=str((a.out/'restore-needed.json').resolve())))
        finally:link.serial.close();save()
    report.update(passed=True,finished_utc=datetime.now(timezone.utc).isoformat(),ports_released=True);save();publish(marker,dict(board='2512',state='bf1-final-hardware-checks-passed' if final else 'bf1-b4-hardware-checks-passed' if beta4 else 'bf1-wdc-hardware-checks-passed',run=str(a.out.resolve()),block_snapshot=False,application_ram_restored=True));print('PASS migration bf1 A/B hardware checks, storage and RAM restoration',flush=True)
if __name__=='__main__':main()
