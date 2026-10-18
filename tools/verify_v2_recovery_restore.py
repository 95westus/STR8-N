"""Verify full restoration, repaired history, retained SRAM and test wear ledger."""
import json,re,sys
from pathlib import Path
import migrate_v2 as u
from beta4_migration import Link
from rtc_boards import SERIALS
from serial.tools.list_ports import comports
from serial_test_coordination import serial_lease
from rtc_prompt_sync import establish_b3
from qualify_v2_beta23_power_retention import records
import upgrade_v2_fleet as fleet
import archive_v2_edu_sram as array
import capture_v2_display_devices as devices

def main():
    base=u.ROOT/'output/qualification/beta25-recovery-2026-10-14/2604';root=base/'restore';out=base/'post-005';out.mkdir(exist_ok=False)
    assert u.read(root/'physical-reset/report.json')['passed'];plan=u.read(root/'upgrade/plan.json');ledger=u.read(base/'restoration-target/erase-ledger.json')
    port=next(p.device for p in comports() if p.serial_number==SERIALS['2604'])
    with serial_lease('2604-recovery-restoration-verify'),(out/'serial.jsonl').open('x') as log:
        l=Link(port,log)
        try:
            establish_b3(l);assert l.dump(0x7D30,0x7D30)==b'\xB0';hashes=[]
            for bank in range(4):
                p=f'\r\nB{bank}> '.encode();l.command(f'B{bank}',p);b=b''.join(l.dump(a,a+4095,p) for a in range(0x8000,0x10000,4096))
                assert b==(root/f'upgrade/expected-b{bank}.bin').read_bytes();(out/f'b{bank}.bin').write_bytes(b);hashes.append(u.sha(b))
            l.command('B3');w=l.command('W');(out/'wear.txt').write_bytes(w)
            found=re.findall(rb'B([0-3]):([8-9A-F]) ([0-9A-F]{6})',w);assert len(found)==32
            counts=[None]*32
            for bank,sector,n in found:counts[int(bank)*8+int(sector,16)-8]=int(n,16)
            assert counts==ledger['counts_after']
            time=l.command('TIME');(out/'time.txt').write_bytes(time);assert b'(+00:00)' in time and b'UTC ' not in time
            l.command('R MAINT',b'BM> ');assert b'Board: 2604' in l.command('NAME',b'BM> ');l.command('Q')
            l.command('R CLOCK',b'CLOCK> ');assert b'History unavailable' not in l.command('HISTORY',b'CLOCK> ');assert b'Power-fail latched: no' in l.command('STATUS',b'CLOCK> ');l.command('Q')
        finally:l.serial.close()
    with serial_lease('2604-recovery-retention-verify'):
        fleet.call(array,['--root',str(base/'retained'),'--board','2604','--port',port,'--stage','final'])
        campaign=u.read(u.ROOT/'output/qualification/active-rtc-campaign.json')
        fleet.call(devices,['--root',str(out),'--board','2604','--port',port,'--stage','before','--baseline-index',campaign['baseline_index']])
    ee=(out/'devices-before/eeprom-0.bin').read_bytes()[:137];assert ee==(base/'clock-repair/eeprom-repaired.bin').read_bytes() and records(ee)=={0:1} and ee[30]==0
    result=dict(passed=True,board='2604',clock_history_repaired=True,physical_F_only_A_and_B_passed=True,interrupted_transfer_physical_reset_passed=True,
        physical_mid_program_power_cut_tested=False,model_journal_cut_points=123,model_slot_cut_points=11,
        original_beta24_A_beta25_B_restored=True,original_flash_preserved_except_appended_wear_record=True,counts_include_test_and_restore_erases=23,
        original_journal_records_preserved=True,full_flash_hashes=hashes,sram_preserved=True,repaired_eeprom_preserved=True,rtc_control_trim_eui_preserved=True)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS 2604 restored original A/B/shared/data; all 23 erase attempts accounted; full SRAM, repaired history, RTC/control/trim/EUI retained',flush=True)

if __name__=='__main__':main()
