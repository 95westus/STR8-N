"""Prepare a preserving WDC bank-copy trial; no port, firmware build or simulation."""
import json
from pathlib import Path
import qualify_services_g4_2512_ram as t
from journal_rotation_plan import reserve
from native_journal_room import require_zero_erase_room

CAP = t.ROOT/'output/qualification/2512-PROGRAM-preserving-repair-20261030-r1'
VENDOR = t.ROOT/'output/qualification/board-inventory-20261028/wdcmonv2-private-backups/65c02-2512-pre-FLASH-B0.bin'
VENDOR_SHA = '8c73a910ee02d86d25039e5189d379e80d45117a4fcbb2ae509f146d1aaa3616'
OUT = t.ROOT/'output/qualification/2512-WDC-backup-copy-scope-20261030-r1'


def prepare():
    assert not OUT.exists(), 'Fresh private output required'
    report=json.loads((CAP/'report.json').read_text())
    assert report['passed'] and report['all_flash_banks_unchanged'] and report['owner_RAM_restored']
    banks=[(CAP/f'after-pass1-B{n}.bin').read_bytes() for n in range(4)]
    for n, body in enumerate(banks):
        assert len(body)==32768 and body==(CAP/f'after-pass2-B{n}.bin').read_bytes()
    marker=json.loads(t.MARK.read_text())
    assert [marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]==list(map(t.sha,banks))
    old=t.classify_journal(banks[3])
    assert old['sequence']==1033 and old['valid_records']==20
    assert t.sha(banks[3][-4096:])==t.live.planning.F_SHA256
    vendor=VENDOR.read_bytes()
    assert len(vendor)==32768 and t.sha(vendor)==VENDOR_SHA and vendor[-4096:]==banks[0][-4096:]
    differing=[a for a in range(0x8000,0x10000,4096)
               if banks[0][a-0x8000:a-0x7000]!=vendor[a-0x8000:a-0x7000]]
    assert differing==[0x8000,0x9000], 'Target differs from the reviewed two-sector copy shape'
    require_zero_erase_room(banks[3],4)
    OUT.mkdir(parents=True);(OUT/'.gitignore').write_text('*\n')
    (OUT/'wdcmonv2-original-32768.bin').write_bytes(vendor)
    (OUT/'original-B0-32768.bin').write_bytes(banks[0])
    state=list(banks);steps=[]
    for kind,source in [('copy',vendor),('restore',banks[0])]:
        for address in differing:
            index=address//4096-8
            before=list(state)
            state[3],journal=reserve(state[3],index)
            assert journal['journal_sector_erases']==[] and len(journal['journal_appends'])==1
            target=source[address-0x8000:address-0x7000]
            original=state[0][address-0x8000:address-0x7000]
            assert original!=target
            b0=bytearray(state[0]);b0[address-0x8000:address-0x7000]=target;state[0]=bytes(b0)
            label=f'{kind}-B0-{address:04X}'
            (OUT/f'{label}-before.bin').write_bytes(original)
            (OUT/f'{label}-target.bin').write_bytes(target)
            for n,body in enumerate(state):(OUT/f'{label}-expected-B{n}.bin').write_bytes(body)
            steps.append(dict(label=label,bank=0,address=address,page=address>>8,
                              before_sha256=list(map(t.sha,before)),after_sha256=list(map(t.sha,state)),
                              original_sector_sha256=t.sha(original),target_sector_sha256=t.sha(target),journal=journal))
        assert state[0]==source
    final=t.classify_journal(state[3])
    assert final['sequence']==1037 and final['valid_records']==24
    assert final['counts']==[v+2 if n in (0,1) else v for n,v in enumerate(old['counts'])]
    assert final['default']==old['default']=='B'
    for key in ('entries','enabled_mask','unknown_mask'):assert final[key]==old[key]
    permitted=set()
    for step in steps:
        for row in step['journal']['journal_appends']:
            assert row['kind']=='target-erase-reservation'
            offset=int(row['page'],16)-0x8000
            assert banks[3][offset:offset+256]==b'\xff'*256
            permitted.update(range(offset,offset+256))
    assert all(a==b for n,(a,b) in enumerate(zip(banks[3],state[3])) if n not in permitted)
    assert state[:3]==banks[:3]
    for n,body in enumerate(state):(OUT/f'final-expected-B{n}.bin').write_bytes(body)
    plan=dict(schema=1,board='2512',port='COM4',usb_serial='A10MQFLCA',CPU='65C02',
              status='PREPARED_SEPARATE_BACKUP_COPY_TRIAL',
              authorization=['continue, flash approved','Keep F golden; prepare a separate 2512 backup-copy trial'],
              source_capture=str(CAP),source_report_sha256=t.sha((CAP/'report.json').read_bytes()),
              source_bank_sha256=list(map(t.sha,banks)),vendor_source=str(VENDOR),vendor_bank_sha256=VENDOR_SHA,
              vendor_reset_vector='F818',vendor_CPU='65C02',vendor_provenance='Preserved 2512 pre-FLASH bank, retained privately',
              exact_copy_bank='B0',target_sectors=['B0:8','B0:9'],steps=steps,total_sector_erases=4,
              sector_erases={'B0:8':2,'B0:9':2},F_writes=0,C_D_erases=0,MON_A_B_E_writes=0,
              all_20_original_journal_records_retained=True,original_journal=old,final_journal=final,
              expected_final_bank_sha256=list(map(t.sha,state)),
              saved_default='B',saved_MON_generation='00000008',
              owner_RAM_ZP_fresh_double_escrow_and_restore=True,SRAM_data_writes=0,WORKSPACE_writes=0,
              RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,firmware_builds=0,CPU_simulations=0,
              writer='Existing frozen BASE1 OPAQUE RAM writer, native commit-before-erase reservations',
              new_NFM2_engine_executed=False,full_factory_migration_qualified=False,WDC_B0_boot_qualified=False,
              final_context='MON B / B3>',other_boards_excluded=True,published_downloads_changed=False,push=False)
    t.save(OUT/'plan.json',plan)
    print(json.dumps(dict(out=str(OUT),plan_sha256=t.sha((OUT/'plan.json').read_bytes()),
        erases=plan['sector_erases'],journal_appends=[s['journal']['journal_appends'][0] for s in steps],
        old_counts=old['counts'][:2],final_counts=final['counts'][:2],C_D_E_F=final['counts'][28:32],
        existing_records_retained=20,F_writes=0,C_D_erases=0,hardware_access=False),indent=2))


if __name__=='__main__':prepare()
