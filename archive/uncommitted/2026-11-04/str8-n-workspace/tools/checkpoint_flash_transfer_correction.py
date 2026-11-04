"""Record verified hardware state and truthful STATUS admission; no port access."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
from native_journal_room import classify_journal
sha=lambda b:hashlib.sha256(b).hexdigest()


def run():
    q=ROOT/'output/qualification';trial=q/'2512-flash-status-correction-RAM-20261101-r1'
    r=json.loads((trial/'report.json').read_text());scope=q/'FLASH-transfer-scope-20261101-r1'
    plan=json.loads((scope/'plan.json').read_text())
    assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['B0_unchanged'] and r['B3_unchanged'] and r['port_released']
    assert all(sha((trial/f'B{b}-before.bin').read_bytes())==plan['final_bank_sha256'][f'B{b}'] for b in range(4))
    b3=(trial/'B3-before.bin').read_bytes();j=classify_journal(b3)
    assert j['counts']==plan['counts_after'] and j['sequence']==1130 and j['valid_records']==21
    assert sum(a-b for a,b in zip(j['counts'],plan['counts_before']))==10
    original3=(scope/'B3-original.bin').read_bytes()
    assert b3[:0x4000]==original3[:0x4000] and b3[-4096:]==original3[-4096:]
    pos=q/'2512-flash-transfer-positive-20261101-r1'
    p=json.loads((pos/'report.json').read_text());assert p['passed']
    archive=Path(p['history_archive_before_rotation']).read_bytes()
    assert classify_journal(archive)['valid_records']==31
    assert archive[0x4000:0x5000]==original3[0x4000:0x5000]
    mp=q/'device-operations/2512.json';m=json.loads(mp.read_text())
    assert m['application_ram_restored'] and not m['application_RAM_restore_pending']
    assert not any(v for k,v in m.items() if k.endswith('_worker_active'))
    m['current_physical_bank_sha256'].update(plan['final_bank_sha256'])
    m['current_journal_sequence']=1130;m['current_journal_valid_records']=m['current_valid_journal_records']=21
    m['current_wear_counts']=j['counts']
    for i,value in enumerate(j['counts']):m['current_tracked_erase_counts'][f'B{i//8}:{i%8+8:X}']=value
    for letter,i in zip('ABCDEF',range(26,32)):m['current_tracked_erase_counts'][letter]=j['counts'][i]
    m.update(flash_transfer_installed=True,flash_transfer_qualification_pending=True,
        status_installation_complete=False,STATUS_runtime_unavailable=True,flash_AUTO_AREA_regression=True,
        flash_status_correction_pending=True,final_prompt='REC>',current_owner_RAM_sha256=r['RAM_sha256'],current_owner_ZP_sha256=r['ZP_sha256'],
        last_verified_flash_transfer_state=str(trial/'report.json'),
        status_admission_hold_reason='STATUS details FA50-FFF9 overwritten by first FLASH expansion; correction RAM-qualified, awaiting three additional erases. Admit RTC only after real STATUS/CPU output is restored.')
    mp.write_text(json.dumps(m,indent=2)+'\n')
    out=q/'FLASH-transfer-ten-erase-checkpoint-20261101-r1';out.mkdir(exist_ok=False);(out/'.gitignore').write_text('*\n')
    report=dict(ten_erase_state_verified=True,full_feature_closeout=False,hardware_access=False,
        consumed_erases=10,sequence=1130,current_records=21,C_D_E_F=j['counts'][28:32],
        all_original_B0_restored=True,original_history_archived_before_C_rotation=True,
        F_MON_boot_settings_owner_RAM_ZP_preserved=True,
        positive_features=['6400-byte flash Store/Table/load-only Restore through66FF','two-sector dense S19 with crossing records'],
        regressions=['Rich STATUS details overlap','AUTO loses AREA on full cache reload'],
        correction_RAM_passed=True,additional_erases_not_authorized=3,final_prompt='REC>',COM4_released=True,
        RTC_code_schedule_history_unchanged=True,RTC_2512_admission_held_for_real_STATUS_incompatibility=True,
        other_boards_accessed=False,published_downloads_changed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS exact ten-erase state/history/owner preservation; STATUS admission truthfully held; three-erase repair awaits approval')


if __name__=='__main__':run()
