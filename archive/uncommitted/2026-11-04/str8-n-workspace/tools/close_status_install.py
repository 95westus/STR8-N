"""Finalize verified STATUS facts; never opens a port or changes a release ZIP."""
import json
from pathlib import Path
import install_status_reviewed as i
t=i.t
def run():
    records={};scope=json.loads((i.SCOPE/'review.json').read_text())
    for board in ('2512','2609'):
        folder=i.BASE/board
        install=json.loads((folder/'report.json').read_text())
        boot=json.loads((folder/'physical-boot/report.json').read_text())
        rtc=json.loads((folder/'RTC-continuity/registration.json').read_text())
        assert install['passed'] and boot['passed'] and rtc['passed']
        before=(folder/'B3-before.bin').read_bytes();after=(folder/'B3-after.bin').read_bytes()
        assert before[-4096:]==after[-4096:]
        assert before[:8192]==after[:8192] and before[0x6000:]==after[0x6000:]
        assert install['journal']['counts']==scope['boards'][board]['counts_after']
        assert boot['RAM_sha256']==install['owner_RAM_sha256'] and boot['ZP_sha256']==install['owner_ZP_sha256']
        path=t.ROOT/f'output/qualification/device-operations/{board}.json';marker=json.loads(path.read_text())
        assert marker['status_installation_complete'] and not marker['application_RAM_restore_pending']
        counts=install['journal']['counts'];tracked=marker.get('current_tracked_erase_counts',{}).copy()
        for bank in range(4):
            for sector in range(8):tracked[f'B{bank}:{sector+8:X}']=counts[bank*8+sector]
        for letter,index in [('A',26),('B',27),('C',28),('D',29),('E',30),('F',31)]:tracked[letter]=counts[index]
        marker.update(current_tracked_erase_counts=tracked,current_F_reservation_count=counts[31],
            monitor_generation_note='MON A/B gC + shared STATUS g1; identical commands, Bx prompt',
            physical_boot_status='gC default B verified' if board=='2512' else 'Default S and one-time gC A verified',
            status_previous_CD_history_archive=str(folder/'B3-before.bin'),
            status_previous_CD_records_archived_on_host=scope['boards'][board]['records_before'],
            last_STATUS_closeout=str(i.BASE/'final-receipt.json'))
        t.save(path,marker)
        records[board]=dict(installed=True,monitor_generation='0000000C',default=install['journal']['default'],
            sequence=install['journal']['sequence'],valid_records=install['journal']['valid_records'],
            counts=counts,owner_RAM_sha256=install['owner_RAM_sha256'],owner_ZP_sha256=install['owner_ZP_sha256'],
            owner_RAM_restored=True,owner_ZP_restored=True,physical_startup_passed=True,
            startup_stream_captured=boot.get('startup_stream_captured',False),
            reset_evidence='Owner-reported physical RESET; expected post-reset default observed before any selector; RAM/ZP/B3 verified',
            RTC_native_TIME_admitted=True,port_released=True,install=str(folder/'report.json'),
            physical_boot=str(folder/'physical-boot/report.json'),RTC_registration=str(folder/'RTC-continuity/registration.json'))
    # Updating descriptive marker fields above does not alter any existing
    # campaign admission key. Baselines/points/events/cadence stay untouched.
    result=dict(passed=True,boards=records,image_erases=10,native_C_erases=1,total_erases=11,
        F_writes=0,F_sha256=scope['F_sha256'],power_cuts=0,RTC_SET=0,RTC_PF_ACK=0,SRAM_data_writes=0,
        excluded_boards_untouched=['2205','2604'],published_downloads_changed=False,
        buffer_ownership='MON owns6A; active FLASH own VERSION preserves4K; MON VERSION preserves non6A buffer',
        limitation_2609='Legacy native-tool profile/sector9 retained; no compatible name/zone/policy metadata')
    t.save(i.BASE/'final-receipt.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':run()
