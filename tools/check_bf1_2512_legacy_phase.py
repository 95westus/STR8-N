"""Post-owner-RESET legacy/source restoration checks; exact flash and original application RAM."""
import argparse,json,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
from beta4_migration import Link
from rtc_prompt_sync import establish_b3,drain
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from atomic_json import publish
import bf1_2604_readonly as live
old=live.old;base=live.base;ROOT=base.ROOT;Q=ROOT/'output/qualification';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--install',type=Path,required=True);ap.add_argument('--reset-confirmation',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    install=read(a.install/'report.json');confirmation=read(a.reset_confirmation);assert install['passed'] and install['transaction_device_verified'] and install['physical_reset_pending'] and install['board']=='2512'
    assert confirmation['board']=='2512' and confirmation['user_confirmed_physical_reset'] and confirmation['install_report_sha256']==sha(a.install/'report.json')
    phase=install['phase'];original_phase=phase.endswith('restore-original');assert original_phase or phase in ('v2-0b4-stage-source','v2-0b4-restore-historical-source')
    page=0xb0 if original_phase else 0xa0;backup=Path(install['fresh_backup']);original=(backup/'application-ram-original.bin').read_bytes();sram=(backup/'sram.bin').read_bytes();assert read(backup/'report.json')['passed']
    marker=Q/'device-operations/2512.json';op=read(marker);assert op['state']=='legacy-reset-required' and op['phase']==phase and op['block_snapshot']
    active=read(Q/'active-rtc-campaign.json');assert active['powered_off_boards']==['2205'] and sha(Path(active['baseline_index']))==active['baseline_index_sha256'];expected=next(b for b in read(Path(active['baseline_index']))['boards'] if b['board']=='2512')
    ports=[p.device for p in comports() if p.serial_number==SERIALS['2512']];assert len(ports)==1;assert not a.out.exists();a.out.mkdir(parents=True)
    report=dict(board='2512',phase=phase,passed=False,expected_hashes=install['expected_hashes'],install_report_sha256=sha(a.install/'report.json'),reset_confirmation_sha256=sha(a.reset_confirmation),source_sha256=sha(Path(__file__)),clock_set=False,trim_changed=False,persistent_device_writes=False,started_utc=datetime.now(timezone.utc).isoformat(),checks=[])
    def save():publish(a.out/'report.json',report)
    def passed(name):report['checks'].append(dict(name=name,passed=True));save();print('PASS',name,flush=True)
    save();publish(marker,dict(board='2512',state='checking-legacy-phase',phase=phase,run=str(a.out.resolve()),block_snapshot=True));publish(a.out/'restore-needed.json',dict(needed=True,sha256=hashlib.sha256(original).hexdigest()))
    with (a.out/'serial.jsonl').open('x') as log:
      link=Link(ports[0],log)
      try:
        banner=drain(link);(a.out/'boot-output.txt').write_bytes(banner);establish_b3(link);(a.out/'help.txt').write_bytes(link.command('?'));assert link.dump(0x7d30,0x7d30)==bytes([page]);passed('Physical boot into expected monitor slot')
        for bank in range(4):
            prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'b{bank}.bin').write_bytes(data);assert sha(a.out/f'b{bank}.bin')==install['expected_hashes'][bank],f'B{bank} mismatch'
        link.command('B3');passed('All four flash banks match qualified phase exactly')
        if original_phase:
            text=link.command('VERSION');(a.out/'version.txt').write_bytes(text);assert b'2.0b35' in text and b'Board: 2512' in text and b'Running: MONITOR B' in text
            assert all((a.out/f'b{n}.bin').read_bytes()==(backup/f'b{n}.bin').read_bytes() for n in range(3));before=(backup/'b3.bin').read_bytes();after=(a.out/'b3.bin').read_bytes();assert after[:0x4000]==before[:0x4000] and after[0x6000:]==before[0x6000:]
            report['clock']=old.clock(link,a.out,expected)
            for n in range(2):
                assert base.load_image(link,base.EEPROM)==base.EEPROM_HASH;link.command('G 2000');data=link.dump(0x2400,0x2494);assert data[0x90]==0 and data[0x91]==data[0x92] and (data[0x93]^data[0x94])&data[0x91]==0;(a.out/f'eeprom-{n}.bin').write_bytes(data[:137]);assert data[:137]==(backup/'eeprom.bin').read_bytes()
            passed('Restored beta35 identity, RTC control/trim, user EEPROM and power evidence preserved')
            assert base.load_image(link,base.CLIENT)==base.CLIENT_HASH;blocks=[]
            for block in range(16):
                link.write_ram(0x3E20,b'\x01\x03\0');link.write_ram(0x3E00,base.memory_request(1,block*8192));link.command('G 2003');reply=link.dump(0x3E10,0x3E38);assert reply[8:10]==b'\0\x40' and reply[0x23]==reply[0x24];data=link.dump(0x4000,0x5fff);assert data==sram[block*8192:(block+1)*8192];blocks.append(data);print('PASS retained SRAM block',block,flush=True)
            (a.out/'sram-after.bin').write_bytes(b''.join(blocks));passed('Original payload restored with conservative new wear and exact full retained SRAM')
            report.update(original_payload_restored=True,retained_storage_preserved=True,clocks_trims_unchanged=True)
            for bank in range(4):
                prompt=f'\r\nB{bank}> '.encode();link.command(f'B{bank}',prompt);data=b''.join(link.dump(x,x+4095,prompt) for x in range(0x8000,0x10000,4096));(a.out/f'final-b{bank}.bin').write_bytes(data);assert sha(a.out/f'final-b{bank}.bin')==install['expected_hashes'][bank],f'Final B{bank} mismatch'
            link.command('B3')
            from plan_bf1_2512_legacy import latest
            latest_row=latest([(a.out/f'final-b{n}.bin').read_bytes() for n in range(4)])[2]
            counts=[int.from_bytes(latest_row[24+i*3:27+i*3],'little') for i in range(32)];planned=read(Path(install['plan']))['transaction']['reserved_counts'];assert counts==planned
            report.update(conservative_wear_retained=True,wear_counts=counts);passed('Final complete flash unchanged and conservative wear counts match qualified reservation')
        else:
            from plan_bf1_2512_legacy import admit_source
            admit_source('v2.0b4',[(a.out/f'b{n}.bin').read_bytes() for n in range(4)]);passed('Exact published beta4 generation-13 MON A source admitted')
        report['full_flash_verified']=True
      except BaseException:report['failure']=traceback.format_exc();save();publish(marker,dict(board='2512',state='inspection-required',phase=phase,run=str(a.out.resolve()),block_snapshot=True));raise
      finally:
        try:
            establish_b3(link);old.restore(link,backup/'restore-application-ram.s19',original);report['application_ram_restored']=True;receipt=dict(needed=False,verified=True,sha256=hashlib.sha256(original).hexdigest());publish(a.out/'restore-needed.json',receipt);publish(a.install/'restore-needed.json',receipt)
        finally:link.serial.close();save()
    report.update(passed=True,finished_utc=datetime.now(timezone.utc).isoformat(),ports_released=True);save();publish(marker,dict(board='2512',state='legacy-phase-checked',phase=phase,run=str(a.out.resolve()),block_snapshot=not original_phase,application_ram_restored=True));print('PASS',phase,'boot, exact flash and original RAM restoration',flush=True)
if __name__=='__main__':main()
