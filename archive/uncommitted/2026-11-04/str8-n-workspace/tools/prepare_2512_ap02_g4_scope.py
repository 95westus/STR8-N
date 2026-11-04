"""Prepare the one-erase 2512 AP/02 scope from verified captures; no device/build."""
import binascii
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
from journal_rotation_plan import reserve
from native_journal_room import inspect, require_zero_erase_room
from nf_migrate import valid_snapshot

CAP=t.ROOT/'output/qualification/2512-WDC-default-boot-trial-20261030-r1'
OUT=t.ROOT/'output/qualification/2512-AP02-g4-scope-20261030-r1'


def prepare():
    assert not OUT.exists()
    receipt=json.loads((CAP/'final-receipt.json').read_text())
    marker=json.loads(t.MARK.read_text())
    assert receipt['passed'] and receipt['original_B0_restored']
    assert receipt['owner_RAM_restored'] and receipt['owner_ZP_restored'] and receipt['COM4_released']
    banks=[(CAP/f'final-pass1-B{n}.bin').read_bytes() for n in range(4)]
    for n,body in enumerate(banks):assert body==(CAP/f'final-pass2-B{n}.bin').read_bytes()
    assert list(map(t.sha,banks))==[marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==receipt['final_bank_sha256']
    old=t.classify_journal(banks[3]);room=require_zero_erase_room(banks[3],1)
    assert old['sequence']==1041 and old['valid_records']==28 and old['default']=='B'
    assert old['enabled_mask']==15 and old['entries']==[8]*4
    original=banks[0][0x1000:0x2000]
    assert original==b'\xff'*4096 and all(b'APPDEMO' not in body for body in banks)
    source=t.REPO/'apps/candidates/appdemo-ap02-g1'
    manifest=json.loads((source/'manifest.json').read_text())
    image=(source/manifest['image']['filename']).read_bytes()
    assert len(image)==120 and t.sha(image)==manifest['image']['sha256']
    assert image[:8]==b'AP\x02\x20PR05' and image[15]==2
    assert binascii.crc_hqx(image[:28],65535)==int.from_bytes(image[28:30],'little')
    assert binascii.crc_hqx(image[32:],65535)==int.from_bytes(image[30:32],'little')
    assert all(b!=255 for b in image[28:32])
    valid=image.ljust(4096,b'\xff')
    unsealed=bytearray(valid);unsealed[28:32]=b'\xff'*4;unsealed=bytes(unsealed)
    header_only=bytearray(valid);header_only[30:32]=b'\xff'*2;header_only=bytes(header_only)
    assert all(a&b==b for a,b in zip(unsealed,header_only))
    assert all(a&b==b for a,b in zip(header_only,valid))
    final3,reservation=reserve(banks[3],1)
    assert reservation['journal_sector_erases']==[]
    assert reservation['journal_appends']==[dict(page='CC00',sequence=1042,kind='target-erase-reservation')]
    final=t.classify_journal(final3)
    assert final['counts']==[v+1 if i==1 else v for i,v in enumerate(old['counts'])]
    assert final['counts'][1]==15 and final['counts'][28:32]==[53,33,28,24]
    for key in ['default','enabled_mask','entries','unknown_mask']:assert final[key]==old[key]
    for offset in range(0x4000,0x6000,256):
        if valid_snapshot(banks[3][offset:offset+256]):assert final3[offset:offset+256]==banks[3][offset:offset+256]
    OUT.mkdir();(OUT/'.gitignore').write_text('*\n')
    for name,body in [('original-sector.bin',original),('fixture-unsealed.bin',unsealed),
        ('fixture-header-only.bin',header_only),('fixture-valid.bin',valid),('journal-after-restore-B3.bin',final3)]:
        (OUT/name).write_bytes(body)
    stages={}
    for name,sector,journal in [('unsealed',unsealed,banks[3]),('header-only',header_only,banks[3]),
        ('valid',valid,banks[3]),('restored',original,final3)]:
        expected=list(banks);expected[0]=banks[0][:0x1000]+sector+banks[0][0x2000:];expected[3]=journal
        for n,body in enumerate(expected):(OUT/f'{name}-expected-B{n}.bin').write_bytes(body)
        stages[name]=list(map(t.sha,expected))
    plan=dict(schema=1,status='REVIEW_ONLY_AWAITING_ONE_ERASE_TARGET_APPROVAL',board='2512',CPU='65C02',
        port='COM4',usb_serial='A10MQFLCA',monitor='MON B g8',services='g4',target='B0:9000-9FFF',
        source_capture=str(CAP),source_receipt_sha256=t.sha((CAP/'final-receipt.json').read_bytes()),
        source_bank_sha256=list(map(t.sha,banks)),original_sector_sha256=t.sha(original),
        target_recorded_all_FF=True,fresh_native_double_owner_escrow_required=True,
        fresh_complete_bank_double_read_required=True,require_target_still_all_FF_before_programming=True,
        source_APP_image_sha256=t.sha(image),source_APP_bytes=120,APP_body_bytes=88,
        APP_entry='9020',APP_name='APPDEMO',APP_source_rebuilt=False,
        fixture_sha256={name:t.sha(body) for name,body in [('unsealed',unsealed),('header-only',header_only),('valid',valid)]},
        initial_programming='Native !M, 15 commands of 8 bytes at 9000-9077; identical FF bytes skipped; no erase',
        native_checksum_1_to_0_cells=['901C','901D','901E','901F'],
        total_sector_erases=1,sector_erases={'B0:9':1},erase_operation='Restore entire target to original 4096 FF bytes',
        journal_appends=reservation['journal_appends'],all_28_original_journal_records_retained=True,
        original_journal=old,final_journal=final,initial_append_room=room,final_append_room=inspect(final3),
        B0_9_count_before=14,B0_9_count_after=15,counts_C_D_E_F_unchanged=[53,33,28,24],
        stage_bank_sha256=stages,F_sha256=t.sha(banks[3][-4096:]),F_writes=0,C_D_erases=0,
        MON_A_B_E_or_tool_writes=0,boot_setting_writes=0,power_cuts=0,planned_resets=0,
        SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        firmware_builds=0,CPU_simulations=0,final_context='MON B / B3>',
        owner_RAM_ZP_exact_restore_and_native_comparison_required=True,
        tests=['bad-header-CRC-refusal','bad-payload-CRC-refusal','APPS-valid-inventory',
               'APP-APPDEMO-flash-launch','help-redisplay','bare-Q-public-HOLD-to-MON-B',
               'owner-RAM-ZP-unchanged-after-app','full-original-sector-and-banks-restored',
               'all-old-journal-rows-retained','native-TIME-RTC-NTP-continuity'],
        RTC_profile_unchanged='MON-G8-NATIVE-TIME',RTC_sampler_source_change_required=False,
        RTC_settings_schedule_and_baselines_preserved=True,automatic_retry_erases=0,
        other_boards_excluded=True,push=False,published_downloads_changed=False)
    t.save(OUT/'plan.json',plan)
    print(json.dumps(dict(plan=str(OUT/'plan.json'),sha256=t.sha((OUT/'plan.json').read_bytes()),
        erased_target=plan['target_recorded_all_FF'],erases=1,journal=reservation['journal_appends'],
        B0_9_count=[14,15],final_records=final['valid_records'],free_ordinary_pages=inspect(final3)['ordinary_blank_pages']),indent=2))


if __name__=='__main__':prepare()
