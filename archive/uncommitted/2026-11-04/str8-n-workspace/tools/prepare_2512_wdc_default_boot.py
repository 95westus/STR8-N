"""Seal the two-erase default-boot trial; no device access or simulation."""
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
from nf_migrate import valid_snapshot,crc
from journal_rotation_plan import reserve
from native_journal_room import require_zero_erase_room

OUT=t.ROOT/'output/qualification/2512-WDC-default-boot-scope-20261030-r1'
CAP=t.ROOT/'output/qualification/2512-WDC-B0-handoff-trial-20261030-r1'


def set_default(bank3,target):
    status=t.classify_journal(bank3)
    assert status['kind']=='valid-snbt' and target in ('0','B')
    rows=[(int.from_bytes(bank3[a+8:a+12],'little'),a,bank3[a:a+256])
          for a in range(0x4000,0x6000,256) if valid_snapshot(bank3[a:a+256])]
    sequence,where,body=max(rows)
    assert sequence==status['sequence'] and where&0xf00!=0xf00
    dest=next(a for a in range(where+256,(where&0xf000)+0xf00,256) if bank3[a:a+256]==b'\xff'*256)
    row=bytearray(body);row[7]=ord(target)
    if target=='B':row[18:22]=bank3[0x3008:0x300c]
    row[8:12]=(sequence+1).to_bytes(4,'little')
    row[30:32]=crc(row[:30]).to_bytes(2,'little');row[252:254]=crc(row[:252]).to_bytes(2,'little')
    assert valid_snapshot(row)
    changed=bytearray(bank3);changed[dest:dest+256]=row
    return bytes(changed),dict(page=f'{dest+0x8000:04X}',sequence=sequence+1,kind='saved-default-'+target)


def prepare():
    assert OUT.exists() and not (OUT/'plan.json').exists()
    r=json.loads((CAP/'final-receipt.json').read_text())
    assert r['passed'] and r['all_flash_banks_and_journal_unchanged'] and r['owner_RAM_restored']
    banks=[(CAP/f'after-pass1-B{n}.bin').read_bytes() for n in range(4)]
    for n,b in enumerate(banks):assert b==(CAP/f'after-pass2-B{n}.bin').read_bytes()
    assert list(map(t.sha,banks))==r['source_bank_sha256']
    marker=json.loads(t.MARK.read_text())
    assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==list(map(t.sha,banks))
    old=t.classify_journal(banks[3]);assert old['sequence']==1037 and old['valid_records']==24
    assert old['default']=='B' and old['enabled_mask']&1 and old['entries'][0]==8
    assert banks[3][0x3008:0x300c]==(8).to_bytes(4,'little')
    assert t.sha(banks[3][-4096:])==t.live.planning.F_SHA256
    require_zero_erase_room(banks[3],4)
    m=json.loads((OUT/'launcher-manifest.json').read_text())
    launcher=(OUT/'WDC-B0-8000-4096.bin').read_bytes()
    assert len(launcher)==4096 and t.sha(launcher)==m['image_sha256']
    assert t.sha(banks[0][-4096:])==m['vendor_F_sha256']
    original=banks[0][:4096];assert original!=launcher
    (OUT/'original-B0-8000-4096.bin').write_bytes(original)
    state=list(banks);steps=[]
    def stage(name,journal):
        hashes=list(map(t.sha,state))
        for n,b in enumerate(state):(OUT/f'{name}-expected-B{n}.bin').write_bytes(b)
        steps.append(dict(name=name,after_sha256=hashes,journal=journal))
    state[3],j=reserve(state[3],0);assert j['journal_sector_erases']==[]
    state[0]=launcher+state[0][4096:];stage('installed',j['journal_appends'][0])
    state[3],j=set_default(state[3],'0');stage('default0',j)
    state[3],j=set_default(state[3],'B');stage('defaultB',j)
    state[3],j=reserve(state[3],0);assert j['journal_sector_erases']==[]
    state[0]=banks[0];stage('restored',j['journal_appends'][0])
    final=t.classify_journal(state[3])
    assert final['sequence']==1041 and final['valid_records']==28
    assert final['counts']==[v+2 if i==0 else v for i,v in enumerate(old['counts'])]
    assert final['default']==old['default'] and final['entries']==old['entries'] and final['enabled_mask']==old['enabled_mask']
    for a in range(0x4000,0x6000,256):
        if valid_snapshot(banks[3][a:a+256]):assert state[3][a:a+256]==banks[3][a:a+256]
    assert [s['journal']['page'] for s in steps]==['C800','C900','CA00','CB00']
    plan=dict(schema=1,status='PREPARED_WDC_LAUNCHER_DEFAULT_BOOT_TRIAL',board='2512',port='COM4',usb_serial='A10MQFLCA',CPU='65C02',
        authorization_context='User continued after proposed temporary B0 default, RESET, return and full image/settings/RAM restoration',
        source_capture=str(CAP),source_report_sha256=t.sha((CAP/'final-receipt.json').read_bytes()),
        source_bank_sha256=list(map(t.sha,banks)),original_sector_sha256=t.sha(original),launcher=m,
        original_journal=old,final_journal=final,steps=steps,expected_final_bank_sha256=list(map(t.sha,state)),
        target='B0:8000',total_sector_erases=2,sector_erases={'B0:8':2},F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,
        journal_appends=4,all_24_original_records_retained=True,temporary_default='0',restored_default='B',
        bank_enable_and_entry_writes=0,B0_already_enabled_at='8000',restored_MON_generation='00000008',
        physical_RESETs_required=1,reset_requires_fresh_armed_receiver=True,host_chooser_keys_during_physical_boot=0,
        physical_boot_marker='WDC B0 / BASE1 DEFAULT BOOT',return_public_ABI='B3:F004 RESET; receiver selects S',
        restore_default_B_before_restoring_original_sector=True,vendor_F818_reset_executed=False,
        power_cuts=0,SRAM_data_writes=0,WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,
        owner_RAM_ZP_fresh_double_escrow_and_restore=True,assembler_invocations=1,F_rebuilt=False,CPU_simulations=0,
        new_NFM2_engine_executed=False,full_factory_migration_qualified=False,
        final_context='MON B / B3>',other_boards_excluded=True,push=False,published_downloads_changed=False)
    t.save(OUT/'plan.json',plan)
    print(json.dumps(dict(out=str(OUT),plan_sha256=t.sha((OUT/'plan.json').read_bytes()),erases=plan['sector_erases'],
        appends=[s['journal'] for s in steps],B0_8_count_before=old['counts'][0],B0_8_count_after=final['counts'][0],
        C_D_E_F=final['counts'][28:32],original_records_retained=24),indent=2))


if __name__=='__main__':prepare()
