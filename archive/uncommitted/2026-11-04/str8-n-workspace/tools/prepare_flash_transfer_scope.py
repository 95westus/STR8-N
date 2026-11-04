"""Review the new2512 temporary flash trial using completed RAM evidence only."""
import json
from pathlib import Path
import sys
import install_2512_native_utilities as d

t=d.t
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
from native_journal_room import valid_snapshot


def run():
    root=t.ROOT/'output/qualification'
    ram=root/'2512-flash-transfer-RAM-20261101-r2'
    receipt=json.loads((ram/'report.json').read_text())
    assert receipt['passed'] and receipt['B0_unchanged'] and receipt['B3_unchanged']
    assert receipt['owner_RAM_restored'] and receipt['owner_ZP_restored'] and receipt['port_released']
    b0=(ram/'B0-before.bin').read_bytes();b3=(ram/'B3-before.bin').read_bytes()
    marker=json.loads((root/'device-operations/2512.json').read_text())
    assert not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
    assert t.sha(b0)==marker['current_physical_bank_sha256']['B0']
    assert t.sha(b3)==marker['current_physical_bank_sha256']['B3']
    assert b0[0x1000:0x2000]==b'\xff'*4096
    assert b0[0x2000:0x3000]!=b'\xff'*4096,'This plan explicitly includes the occupied A setup erase'
    assert b3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    build=t.ROOT/'BUILD/flash-transfer-g1-r5'
    mf=json.loads((build/'manifest.json').read_text())
    packed=t.ROOT/'BUILD/flash-dispatch-g1-r3'
    pm=json.loads((packed/'manifest.json').read_text())
    out=root/'FLASH-transfer-scope-20261101-r1'
    out.mkdir(exist_ok=False);(out/'.gitignore').write_text('*\n')
    (out/'B0-original.bin').write_bytes(b0);(out/'B3-original.bin').write_bytes(b3)
    for name,meta in mf['artifacts'].items():
        data=(build/name).read_bytes();assert t.sha(data)==meta['sha256'];(out/name).write_bytes(data)
    installed=root/'2512-transfer-installed-20261101-r3'
    old={0:b0,1:(installed/'B1-composed-after.bin').read_bytes(),
         2:(installed/'B2-composed-after.bin').read_bytes(),3:b3}
    assert all(t.sha(v)==marker['current_physical_bank_sha256'][f'B{b}'] for b,v in old.items())
    images={b:bytearray(v) for b,v in old.items()}
    def artifact(name):
        data=(packed/name).read_bytes();assert t.sha(data)==pm['artifacts'][name]['sha256'];return data
    maint=artifact('BANK-MAINT-with-transfer.bin');flash=artifact('FLASH-S19-flash.bin');dispatcher=artifact('FLASH-DISPATCH-E.bin')
    assert maint[:8192]==old[1][:8192]
    images[1][:12288]=maint
    images[2][0x6000:0x8000]=flash
    images[3][0x6000:0x7000]=dispatcher
    current=b3;operations=[]
    for phase,bank,sector in (('prepare occupied A for blank-only Store',0,10),
                              ('native dense S19',0,9),('native dense S19',0,10),
                              ('restore original sector',0,9),('restore original sector',0,10)):
        current,op=reserve(current,bank*8+sector-8)
        if phase!='restore original sector' or sector!=10:assert not op['journal_sector_erases']
        operations.append(dict(phase=phase,target=f'B{bank}:{sector:X}',**op))
    targets=[]
    for bank,page in ((1,0xA0),(2,0xE0),(2,0xF0),(3,0xE0)):
        offset=(page-0x80)*256;data=bytes(images[bank][offset:offset+4096]);before_sector=old[bank][offset:offset+4096]
        assert data!=before_sector
        filename=f'B{bank}-{page:02X}-target.bin';(out/filename).write_bytes(data)
        (out/f'B{bank}-{page:02X}-original.bin').write_bytes(before_sector)
        current,op=reserve(current,bank*8+(page-0x80)//16)
        operations.append(dict(phase='install qualified utility',target=f'B{bank}:{page:02X}00',**op))
        targets.append(dict(bank=bank,page=page,address=f'B{bank}:{page:02X}00',file=filename,sha256=t.sha(data),before_sha256=t.sha(before_sector)))
    before=t.classify_journal(b3);after=t.classify_journal(current)
    rotations=[op for v in operations for op in v['journal_sector_erases']]
    assert len(rotations)==1 and sum(len(v['journal_appends']) for v in operations)==10
    # Rotation replaces C on chip. Archive the original history and all new
    # trial rows before the last target-restoration reservation rotates it.
    on_chip_retained=sum(valid_snapshot(b3[o:o+256]) and b3[o:o+256]==current[o:o+256] for o in range(0x4000,0x6000,256))
    for key in ('default','enabled_mask','entries','unknown_mask'):assert before[key]==after[key]
    assert current[:0x4000]==b3[:0x4000] and current[0x6000:]==b3[0x6000:]
    (out/'B3-after-reservations.bin').write_bytes(current)
    current=bytearray(current);current[0x6000:0x7000]=dispatcher;images[3]=current
    for bank,data in images.items():
        (out/f'B{bank}-target.bin').write_bytes(data)
    for bank,data in old.items():(out/f'B{bank}-original.bin').write_bytes(data)
    plan=dict(status='REVIEW_READY_NOT_APPROVED',board='2512',port='COM4',
        target_sectors=['B0:9','B0:A'],target_original='B0:9 blank; B0:A occupied and archived. A is temporarily erased before Store, then restored exactly. Neither is scratch without approval.',
        image_installations=4,installation_targets=targets,temporary_target_erases=5,total_erases=10,journal_appends=10,journal_sector_erases=1,F_writes=0,
        operations=operations,sequence_before=before['sequence'],sequence_after=after['sequence'],
        counts_before=before['counts'],counts_after=after['counts'],old_rows_archived=before['valid_records'],old_rows_retained_on_chip=on_chip_retained,
        old_C_rows_replaced_on_chip=before['valid_records']-on_chip_retained,rows_after=after['valid_records'],
        temporary_Store=dict(source='CPU4E00-66FF',payload_bytes=6400,header_bytes=24,target='B0:9000-A917',
            syntax='STORE 0 9000 4E00 66FF WIDEFL',erases=0,occupied_A_setup_erases=1,
            qualification=['source exact before/after Store','commit-last SR01 header','existing TABLE visibility',
                'exact flash payload readback','RAM candidate RESTORE 0 WIDEFL L through66FF']),
        dense_S19=dict(target='B0:9000-AFFF',payload_bytes=8192,erases=2,
            qualification=['S0/S1/S9','252-byte records crossing4K boundary','complete-sector durable reservations and verified writes',
                           'exact8192-byte readback','S9 completion/no auto-run']),
        restoration=dict(target='B0:9/A',erases=2,byte_exact=True,owner_RAM='0200-66FF',owner_ZP='00-DF'),
        preserved=['F and MON A/B','other images including B0:8 FLASH','all old boot/wear rows archived on host;16 C rows replaced on chip','default/binding/mask/entries',
                   'RTC settings/history','SPI SRAM/WORKSPACE','fresh owner RAM/ZP'],
        installed_checks=['exact target-sector readback','native STORE confirmation/NO and range guards','R FLASH dense-I guards/cancellation',
                          'actual flash-source gate loads and CRC admission','S19 RAM cancellation','TABLE and existing utility routes'],
        excluded=['2609 including COM8','2205/2604','power cuts','factory restoration','published downloads','new CLOCK/RTC settings'],
        before_B0_sha256=t.sha(b0),before_B3_sha256=t.sha(b3),after_B3_sha256=t.sha(current),
        build_manifest_sha256=t.sha((build/'manifest.json').read_bytes()),
        packing_manifest_sha256=t.sha((packed/'manifest.json').read_bytes()),
        final_bank_sha256={f'B{b}':t.sha(v) for b,v in images.items()},
        RAM_receipt=str(ram/'report.json'),RAM_receipt_sha256=t.sha((ram/'report.json').read_bytes()),
        integration_limit='Positive writes first qualify the exact RAM payloads; installed routes then admit those same bytes. Only load-only Restore is a positive gate here; default raw run uses the existing G contract.')
    t.save(out/'plan.json',plan)
    print(json.dumps({k:plan[k] for k in ('total_erases','journal_appends','sequence_before','sequence_after','old_rows_archived','old_C_rows_replaced_on_chip','rows_after')},indent=2))
    print('C/D/F final',after['counts'][28],after['counts'][29],after['counts'][31])


if __name__=='__main__':run()
