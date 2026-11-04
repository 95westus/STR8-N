"""Audit the completed four-erase copy/restore receipt; no port access or build."""
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
from nf_migrate import valid_snapshot

CASE=t.ROOT/'output/qualification/2512-WDC-backup-copy-trial-20261030-r5'
SCOPE=t.ROOT/'output/qualification/2512-WDC-backup-copy-scope-20261030-r1'
CAP=t.ROOT/'output/qualification/2512-PROGRAM-preserving-repair-20261030-r1'


def closeout():
    r=json.loads((CASE/'final-receipt.json').read_text())
    plan=json.loads((SCOPE/'plan.json').read_text())
    assert r['passed'] and r['COM4_released'] and r['final_context']=='B3> '
    assert r['owner_RAM_restored'] and r['owner_ZP_restored'] and not r['owner_RAM_restore_pending']
    assert r['erase_requests']==r['erases_completed']==4 and not r['flash_restore_pending']
    assert r['completed_steps']==[s['label'] for s in plan['steps']]
    for k in ('F_writes','C_D_erases','MON_A_B_E_writes','SRAM_data_writes','WORKSPACE_writes',
              'RTC_SET','trim_writes','PF_ACK','power_cuts','resets','firmware_builds','CPU_simulations'):
        assert r[k]==0,k
    assert not any(r[k] for k in ('new_NFM2_engine_executed','full_factory_migration_qualified','WDC_B0_boot_qualified'))
    original=[(CAP/f'after-pass1-B{n}.bin').read_bytes() for n in range(4)]
    before=[(CASE/f'before-pass1-B{n}.bin').read_bytes() for n in range(4)]
    final=[(CASE/f'final-pass1-B{n}.bin').read_bytes() for n in range(4)]
    assert before==original
    for n in range(4):
        assert before[n]==(CASE/f'before-pass2-B{n}.bin').read_bytes()
        assert final[n]==(CASE/f'final-pass2-B{n}.bin').read_bytes()
        assert final[n]==(SCOPE/f'final-expected-B{n}.bin').read_bytes()
    assert list(map(t.sha,final))==plan['expected_final_bank_sha256']==r['final_bank_sha256']
    assert final[:3]==original[:3]
    assert t.sha(final[3][-4096:])==t.live.planning.F_SHA256
    copied=(CASE/'WDC-copy-B0-32768.bin').read_bytes()
    assert copied==(CASE/'wdcmonv2-host-backup-32768.bin').read_bytes()
    assert copied==(SCOPE/'wdcmonv2-original-32768.bin').read_bytes()
    assert t.sha(copied)==plan['vendor_bank_sha256']
    old=t.classify_journal(original[3]);new=t.classify_journal(final[3])
    assert new==plan['final_journal']==r['final_journal']
    assert old['sequence']==1033 and old['valid_records']==20
    assert new['sequence']==1037 and new['valid_records']==24
    assert new['counts']==[n+2 if i in (0,1) else n for i,n in enumerate(old['counts'])]
    retained=[]
    for off in range(0x4000,0x6000,256):
        row=original[3][off:off+256]
        if valid_snapshot(row):
            assert final[3][off:off+256]==row
            retained.append(f'{off+0x8000:04X}')
    assert len(retained)==20
    old_row=next(original[3][a:a+256] for a in range(0x4000,0x6000,256)
                 if valid_snapshot(original[3][a:a+256]) and int.from_bytes(original[3][a+8:a+12],'little')==1033)
    final_row=final[3][0x4700:0x4800]
    changed=[n for n,(a,b) in enumerate(zip(old_row,final_row)) if a!=b]
    assert set(changed)<=set(range(8,12))|{30,31,252,253}|set(range(64,70))
    for stem,key in [('owner-ram','RAM_sha256'),('owner-zp','ZP_sha256')]:
        assert t.sha((CASE/f'{stem}.bin').read_bytes())==r[key]
    marker=json.loads(t.MARK.read_text())
    assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
    assert not marker['block_snapshot'] and not marker['WDC_backup_copy_worker_active']
    assert not marker['WDC_backup_copy_flash_restore_pending']
    assert marker['current_journal_sequence']==1037 and marker['current_journal_valid_records']==24
    assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==r['final_bank_sha256']
    import rtc_mon_time_2512 as rtc
    rtc.inputs()  # Existing native TIME admission, no sampler/clock operation.
    receipt=dict(schema=1,passed=True,board='2512',CPU='65C02',transport='FT245',
        scope='Separate archived-WDC host-to-B0 copy and preserving restoration; not factory migration',
        completed_utc=r['finished_utc'],source_commit='3e7600b',scope_commit='7f2ff42',
        serial_port='COM4',port_released=True,final_context='B3>',sector_erases={'B0:8':2,'B0:9':2},
        total_sector_erases=4,F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,
        owner_RAM_restored=True,owner_ZP_restored=True,owner_RAM_sha256=r['RAM_sha256'],owner_ZP_sha256=r['ZP_sha256'],
        original_B0_restored=True,host_backup_and_B0_copy_equal=True,vendor_bank_sha256=plan['vendor_bank_sha256'],
        all_bank_postimages_independently_double_read=True,final_bank_sha256=r['final_bank_sha256'],
        original_journal_records_retained=20,retained_record_addresses=retained,
        journal_appends=[s['journal']['journal_appends'][0] for s in plan['steps']],
        sequence_before=1033,sequence_after=1037,valid_records_before=20,valid_records_after=24,
        counts_before={'B0:8':6,'B0:9':12,'C':53,'D':33,'E':28,'F':24},
        counts_after={'B0:8':8,'B0:9':14,'C':53,'D':33,'E':28,'F':24},
        saved_boot_policy_and_MON_generation_preserved=True,all_other_latest_record_fields_preserved=True,
        F_sha256=t.live.planning.F_SHA256,writer_sha256=r['writer_sha256'],readback_sha256=r['readback_sha256'],
        driver_sha256=t.sha((CASE/'trial-driver.py').read_bytes()),
        RTC_profile=rtc.PROFILE,RTC_native_admission_preserved=True,RTC_instrument_changed=False,
        RTC_SET=0,trim_writes=0,PF_ACK=0,SRAM_data_writes=0,WORKSPACE_writes=0,full_SRAM_comparison=False,
        firmware_builds=0,CPU_simulations=0,resets=0,power_cuts=0,other_boards_accessed=False,
        new_NFM2_engine_executed=False,full_factory_migration_qualified=False,WDC_B0_boot_qualified=False,
        push=False,published_downloads_changed=False,
        private_evidence=str(CASE),plan_sha256=t.sha((SCOPE/'plan.json').read_bytes()),
        final_receipt_sha256=t.sha((CASE/'final-receipt.json').read_bytes()),
        serial_trace_sha256=t.sha((CASE/'serial.jsonl').read_bytes()),
        limits=['Archived original vendor bank; no fresh live WDC-source capture',
                'Existing frozen OPAQUE writer; new NFM2 RAM engine not exercised',
                'WDC execution/reset from B0 not tested','65C02/FT245 only; no 65C816 or power-loss claim'])
    t.save(CASE/'independent-audit.json',receipt)
    t.save(t.REPO/'monitors/validation/2512-wdc-backup-copy.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':closeout()
