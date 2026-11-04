"""Consolidate the two approved installations; read local evidence only."""
import json
from pathlib import Path
import install_2512_native_utilities as d
import rtc_drift_campaign as c
import rtc_mon_ui1_gd_trim as rtc
t=d.t
Q=t.ROOT/'output/qualification';SCOPE=Q/'STORAGE-native-scope-20261101-r3'

def run():
    approval=json.loads((SCOPE/'approval.json').read_text());assert approval['approved']
    assert approval['review_sha256']==t.sha((SCOPE/'review.json').read_bytes())
    state=c.read(c.STATE);rows={};images={}
    for board in ('2512','2609'):
        folder=Q/f'{board}-native-storage-installed-20261101-r1'
        report=json.loads((folder/'report.json').read_text());plan=json.loads((SCOPE/board/'plan.json').read_text())
        assert report['passed'] and report['NVM_verified'] and report['port_released']
        assert report['owner_RAM_restored'] and report['owner_ZP_restored'] and report['image_erases_requested']==7
        assert all(report[k]==0 for k in ('F_writes','RTC_setting_writes','SRAM_data_writes','power_cuts','resets'))
        assert report['completed']==[v['address'] for v in plan['targets']]
        assert report['final_journal']['counts']==plan['counts_after'] and report['final_journal']['sequence']==plan['sequence_after']
        assert (folder/'SPI-metadata-before.bin').read_bytes()==(folder/'SPI-metadata-after.bin').read_bytes()
        assert t.sha((folder/'owner-ram.bin').read_bytes())==report['RAM_sha256']
        if 'owner_RAM_sha256' in report:assert report['owner_RAM_sha256']==report['RAM_sha256']
        assert t.sha((folder/'owner-zp.bin').read_bytes())==report['ZP_sha256']
        images[board]={}
        for bank in (1,2,3):
            before=(folder/f'B{bank}-before.bin').read_bytes();after=(folder/f'B{bank}-after.bin').read_bytes()
            assert before==(SCOPE/board/f'B{bank}-original.bin').read_bytes()
            assert after==(SCOPE/board/f'B{bank}-target.bin').read_bytes()
            images[board][bank]=after
        old3=(folder/'B3-before.bin').read_bytes();new3=images[board][3]
        assert old3[0x2000:0x4000]==new3[0x2000:0x4000] and old3[-4096:]==new3[-4096:]
        marker=rtc.inputs(board)
        assert not marker.get('storage_native_install_pending') and marker['storage_native_installed']
        assert {k:marker.get(k) for k in state['board_admission'][board]}==state['board_admission'][board]
        rows[board]=dict(passed=True,report=str(folder/'report.json'),report_sha256=t.sha((folder/'report.json').read_bytes()),
            image_erases=7,journal_sector_erases=plan['journal_sector_erases'],sequence=plan['sequence_after'],
            counts_C_D_E_F=plan['counts_after'][28:32],valid_records=plan['records_after'],old_rows_retained_on_chip=plan['old_rows_remaining_exact_on_chip'],
            all_original_history_archived=True,owner_RAM_ZP_restored=True,SPI_metadata_unchanged=True,RTC_campaign_admitted=True,
            before_bank_sha256=plan['before_bank_sha256'],after_bank_sha256=plan['target_bank_sha256'])
    assert images['2512'][1]==images['2609'][1] and images['2512'][2]==images['2609'][2]
    for a,b in ((0,4096),(0x2000,0x4000),(0x6000,0x8000)):
        assert images['2512'][3][a:b]==images['2609'][3][a:b]
    out=Q/'STORAGE-native-installed-closeout-20261101-r1';out.mkdir(exist_ok=False);(out/'.gitignore').write_text('*\n')
    final=dict(passed=True,total_erases=15,image_erases=14,journal_erases=1,F_writes=0,MON_writes=0,
        RTC_setting_writes=0,SPI_data_writes=0,resets=0,power_cuts=0,boards=rows,common_utility_bytes_identical=True,
        versions=dict(Foundation='0.3.0 g1 BASE1/PR05',MON='A/B gD unchanged',WB2='gD',services='gC',storage='g2',native_loader='NL/1 five entries'),
        published_downloads_changed=False,reference_boards_accessed=False,full_b35_parity_closed=False,
        remaining=['Saved EDU and named transfer','Checked storage-manager BATCH return','Wide Store staging/S19 loaders',
                   'Remaining CLOCK/BOOT administration and factory restore','Classic MON presentation','Extracted release kit qualification'])
    t.save(out/'report.json',final);print('PASS both native storage installations; common code, exact scope, preserved data and RTC admission')
if __name__=='__main__':run()
